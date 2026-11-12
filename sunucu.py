"""2D ofis ekrani icin kucuk yerel web sunucusu.
Tarayicida: http://localhost:8780 (canli ofis 8765 kullanir; ikisi ayni anda acik olabilir)
"""
import json
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import threading  # noqa: E402
import time  # noqa: E402

from ofis import analiz, meta, pano, plan, yayin  # noqa: E402
from ofis.ayarlar import AYAR, KOK, MUSTERI_KOK, VERI, CIKTI  # noqa: E402

_surec = None
_surec_adi = ""
_yayin_surec = None


def yayin_zamanlayici():
    """Her dakika yayinciyi bir tur calistirir (otomatik planlama, Meta planlari, saati gelen yayinlar,
    kaldirma istekleri, istatistik, aksam iletisim raporu). Gorev Zamanlayici da ayni isi yapar; kilit sayesinde
    ikisi cakismaz."""
    global _yayin_surec
    while True:
        try:
            if _yayin_surec is None or _yayin_surec.poll() is not None:
                _yayin_surec = subprocess.Popen([sys.executable, "yayinla.py", "--otomatik"], cwd=str(KOK))
        except Exception as e:
            print("zamanlayici:", e)
        time.sleep(60)


def son_cikti():
    kok = CIKTI
    if not kok.exists():
        return None
    klasorler = sorted([k for k in kok.iterdir() if k.is_dir() and (k / "post_1080x1350.jpg").exists()],
                       key=lambda k: k.stat().st_mtime, reverse=True)
    if not klasorler:
        return None
    k = klasorler[0]
    cap = k / "caption.txt"
    return {"klasor": k.name, "dosyalar": sorted(f.name for f in k.iterdir()),
            "caption": cap.read_text(encoding="utf-8") if cap.exists() else ""}


def calisiyor():
    return _surec is not None and _surec.poll() is None


def baslat(argumanlar, ad):
    global _surec, _surec_adi
    if calisiyor():
        return False
    _surec = subprocess.Popen([sys.executable] + argumanlar, cwd=str(KOK))
    _surec_adi = ad
    return True


_SAYFALAR = []


def _sayfa_onbellek(token):
    """Anahtari sadece bellekte tutar; kullanici sayfa secince veri/meta.json'a yazilir."""
    global _SAYFALAR
    _SAYFALAR = meta.sayfalari_bul(token.strip())
    return _SAYFALAR


def urun_listesi():
    from ofis import fiyat, urun_cekici
    urunler = urun_cekici.tum_onbellekten() or urun_cekici.onbellekten()
    secili = plan.tercih_oku().get("kategoriler")
    urunler = [u for u in urunler if (any(plan.eslesir(u, k) for k in secili) if secili
                                      else urun_cekici.kategori_uygun(u))]
    for u in urunler:
        fiyat.hazirla(u)
    return urunler


class Isleyici(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(KOK / "ofis_ekrani"), **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        if getattr(self, "_statik", False):      # ofis ekrani dosyalari: guncelleme sonrasi eski surum gorunmesin
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _json(self, veri, kod=200):
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _govde(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/durum":
            sonra = int(q.get("sonra", ["0"])[0])
            return self._json({"ajanlar": pano.ajan_listesi(), "mesajlar": pano.son_mesajlar(60, sonra),
                               "calisiyor": calisiyor(), "is": _surec_adi if calisiyor() else "",
                               "son_cikti": son_cikti()})
        if u.path == "/api/baslat":   # eski butonlar
            baslat(["calistir.py"] + (["--demo"] if q.get("demo") == ["1"] else []), "Gunluk uretim")
            return self._json({"ok": True})
        if u.path == "/api/plan":
            return self._json(plan.oku())
        if u.path == "/api/kategoriler":
            from ofis import urun_cekici
            if q.get("demo") == ["1"]:
                from ofis.demo import demo_urunler
                tum = demo_urunler()
            else:
                tum = urun_cekici.tum_onbellekten()
                if not tum:   # ilk sefer: feed'i indir (10-30 sn)
                    urun_cekici.urunleri_cek(lambda m: None)
                    tum = urun_cekici.tum_onbellekten()
            t = plan.tercih_oku()
            return self._json({"agac": plan.kategori_agaci(tum),
                               "secili": t.get("kategoriler") or [k.title() for k in AYAR.get("kategoriler", [])],
                               "gunler": t.get("gunler") or [""] * 7})
        if u.path == "/api/yayin":
            return self._json({"liste": yayin.liste(30), "meta": meta.durum(), "hedefler": yayin.HEDEFLER,
                               "simdi": yayin.simdi().strftime("%Y-%m-%dT%H:%M"), "ayar": yayin.ayar_oku()})
        if u.path == "/musteri.js":        # ekranin musteriye ozel ayarlari (ad, saat dilimi, para, dil)
            from ofis import fiyat, musteri
            b = musteri.bilgi()
            veri = {"id": AYAR["musteri_id"], "ad": musteri.ad(), "marka": AYAR["marka"].get("ad", musteri.ad()),
                    "kisaltma": "".join(w[0] for w in musteri.ad().split() if w[:1].isalnum())[:3].upper(),
                    "tz": b["saat_dilimi"], "tz_kisa": musteri.KISALTMA, "para": AYAR.get("para_sembolu") or fiyat.yerel_para(),
                    "dil": AYAR.get("arayuz_dili", "en")}
            govde = ("window.MUSTERI = " + json.dumps(veri, ensure_ascii=False) + ";").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)
            return
        if u.path == "/logo.png":          # ofis ekranindaki marka logosu
            try:
                from ofis import marka
                yol = marka.logolar().get("altin")
                veri = yol.read_bytes() if yol else b""
            except Exception:
                veri = b""
            if not veri:
                return self._json({"hata": "logo yok"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(veri)))
            self.send_header("Cache-Control", "max-age=86400")
            self.end_headers()
            self.wfile.write(veri)
            return
        if u.path == "/api/oneriler":
            from ofis import oneriler
            return self._json(oneriler.liste())
        if u.path == "/api/projeler":
            from ofis import ofis_ayar, projeler
            return self._json({"liste": projeler.liste(), "siradaki": projeler.siradaki(),
                               "proje_gunu": ofis_ayar.oku().get("proje_gunu", 5), "klasor": str(projeler.KLASOR)})
        if u.path.startswith("/proje_foto/"):     # proje klasorundeki fotografin kucuk onizlemesi
            from ofis import projeler
            parca = unquote(u.path[len("/proje_foto/"):]).split("/")
            if len(parca) == 1:
                k = (projeler.KLASOR / parca[0]).resolve()
                fotolar = projeler._fotolar(k) if k.is_dir() and projeler.KLASOR.resolve() in k.parents else []
                yol = fotolar[0] if fotolar else None
            else:
                yol = (projeler.KLASOR / "/".join(parca)).resolve()
                yol = yol if projeler.KLASOR.resolve() in yol.parents and yol.is_file() else None
            if not yol:
                return self._json({"hata": "yok"}, 404)
            try:
                from PIL import Image, ImageOps
                import io
                im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
                im.thumbnail((480, 480))
                b = io.BytesIO()
                im.save(b, "JPEG", quality=80)
                veri = b.getvalue()
            except Exception:
                return self._json({"hata": "okunamadi"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(veri)))
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(veri)
            return
        if u.path == "/api/ofis_ayar":
            from ofis import ofis_ayar
            return self._json(ofis_ayar.oku())
        if u.path == "/api/rakip":
            from ofis import rakip
            return self._json(rakip.son())
        if u.path == "/api/raporlar":
            from ofis import haftalik_rapor
            return self._json(haftalik_rapor.liste())
        if u.path == "/api/saglik":
            from ofis import saglik
            return self._json(saglik.son())
        if u.path.startswith("/raporlar/"):
            yol = (CIKTI / unquote(u.path.lstrip("/"))).resolve()
            if (CIKTI / "raporlar").resolve() in yol.parents and yol.is_file():
                veri = yol.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(veri)))
                self.end_headers()
                self.wfile.write(veri)
                return
            return self._json({"hata": "yok"}, 404)
        if u.path == "/api/meta/tani":
            t = VERI / "meta_tani.json"
            return self._json(json.loads(t.read_text(encoding="utf-8")) if t.exists() else {})
        if u.path == "/api/iletisim":
            from ofis import iletisim
            r = iletisim.son_rapor()
            if r:
                r["ozet"] = iletisim.ozet_satirlari(r)
                r["konu_adlari"] = iletisim.ADLAR
            return self._json({"rapor": r, "hesap": yayin.hesap_gecmisi()})
        if u.path == "/api/kurallar":
            from ofis import kurallar, sanat
            return self._json({"kurallar": kurallar.oku(), "secenekler": {
                "duzen": sanat.DUZENLER, "fontlar": sanat.FONTLAR, "motif": sanat.MOTIFLER,
                "fiyat_stili": sanat.FIYAT_STILLERI, "efekt": sanat.EFEKTLER}})
        if u.path == "/api/ciktilar":
            return self._json(analiz.ciktilar(30))
        if u.path == "/api/rapor":
            r = VERI / "analiz_raporu.md"
            return self._json({"ogrenimler": analiz.ogrenimler(),
                               "rapor": r.read_text(encoding="utf-8") if r.exists() else ""})
        if u.path.startswith("/cikti/"):
            yol = (MUSTERI_KOK / unquote(u.path.lstrip("/"))).resolve()
            if CIKTI.resolve() in yol.parents and yol.is_file():
                tip = {".jpg": "image/jpeg", ".mp4": "video/mp4", ".txt": "text/plain; charset=utf-8",
                       ".md": "text/markdown; charset=utf-8", ".json": "application/json"}.get(yol.suffix,
                                                                                               "application/octet-stream")
                veri = yol.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", tip)
                self.send_header("Content-Length", str(len(veri)))
                self.end_headers()
                self.wfile.write(veri)
                return
            return self._json({"hata": "yok"}, 404)
        self._statik = True
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        g = self._govde()
        demo = ["--demo"] if g.get("demo") else []
        try:
            if u.path == "/api/plan/olustur":
                if "kategoriler" in g:
                    plan.tercih_kaydet(g.get("kategoriler") or [], (g.get("gunler") or [""] * 7)[:7])
                ok = baslat(["planla.py"] + demo, "Haftalik plan toplantisi")
                return self._json({"ok": ok, "mesaj": "" if ok else "Baska bir is suruyor"})
            if u.path == "/api/plan/onayla":
                p = plan.oku()
                for gun in p.get("gunler", []):
                    if (g.get("hepsi") or gun["tarih"] == g.get("tarih")) and gun.get("durum") == "taslak":
                        gun["durum"] = "onayli"
                plan.kaydet(p)
                return self._json(p)
            if u.path == "/api/plan/geri_al":
                return self._json(plan.guncelle(g["tarih"], durum="taslak"))
            if u.path == "/api/plan/degistir":
                return self._json(plan.urun_degistir(g["tarih"], urun_listesi(), g.get("tur", "post")))
            if u.path == "/api/plan/uret":
                if g.get("tarih"):
                    plan.guncelle(g["tarih"], durum="onayli") if plan.gun(g["tarih"]).get("durum") == "taslak" else None
                    ok = baslat(["calistir.py", "--gun", g["tarih"]] + demo, f"{g['tarih']} uretiliyor")
                else:
                    ok = baslat(["calistir.py", "--hafta"] + demo, "Onayli gunler uretiliyor")
                return self._json({"ok": ok, "mesaj": "" if ok else "Baska bir is suruyor"})
            # --- ONAY: yalnizca kullanicinin tiklamasiyla buraya gelinir ---
            if u.path == "/api/yayin/onayla":
                with yayin.kilit(bekle=30):    # planli Facebook gonderisi varsa iptal edilip yeniden planlanir
                    r = yayin.onayla(g["klasor"], g.get("hedefler") or [], g.get("zaman") or "", g.get("caption") or "")
                pano.yaz("Kullanici", "SosyalMedya", f"Onaylandi: {g['klasor']} → "
                         + ", ".join(yayin.HEDEFLER[h] for h in r["hedefler"])
                         + (f" ({r['zaman'].replace('T', ' ')} {yayin.musteri.KISALTMA})" if r["zaman"] else " (hemen)"), "rapor")
                return self._json(r)
            if u.path == "/api/yayin/reddet":
                return self._json(yayin.reddet(g["klasor"]))
            if u.path == "/api/yayin/geri_al":
                with yayin.kilit(bekle=30):
                    return self._json(yayin.geri_al(g["klasor"]))
            if u.path == "/api/yayin/kaldir":   # KULLANICI ISTEGI: planliysa iptal, yayindaysa Meta'dan sil
                try:
                    with yayin.kilit(bekle=5):
                        r = yayin.kaldir(g["klasor"])
                    pano.yaz("Kullanici", "SosyalMedya", f"Yayindan kaldirildi: {g['klasor']}", "rapor")
                    return self._json(r)
                except TimeoutError:
                    y = yayin.oku(g["klasor"])
                    y["durum"] = "kaldiriliyor"
                    yayin._yaz(g["klasor"], y)
                    return self._json({**y, "mesaj": "Şu an bir yayın işlemi sürüyor; biter bitmez kaldırılacak."})
            if u.path == "/api/yayin/ayar":
                a = yayin.ayar_kaydet(g)
                pano.yaz("Kullanici", "SosyalMedya", "Otomatik yayin " + ("ACIK" if a["otomatik"] else "KAPALI")
                         + " olarak ayarlandi.", "rapor")
                return self._json(a)
            if u.path == "/api/iletisim/yenile":
                subprocess.Popen([sys.executable, "yayinla.py", "--iletisim"], cwd=str(KOK))
                return self._json({"ok": True})
            if u.path == "/api/yayin/revize":
                if calisiyor():
                    return self._json({"hata": f"Şu an başka bir iş sürüyor ({_surec_adi}). Bitince tekrar deneyin."}, 409)
                r = yayin.revize_iste(g["klasor"], g.get("secenekler") or [], g.get("not") or "")
                baslat(["calistir.py", "--revize", yayin._yol(g["klasor"]).name], "Revizyon hazirlaniyor")
                return self._json(r)
            if u.path == "/api/kurallar":
                from ofis import kurallar
                d = kurallar.kaydet(g)
                pano.yaz("Kullanici", "Herkes", f"Marka Kurallari guncellendi ({len([k for k in d['kurallar'] if k['aktif']])} "
                         f"aktif kural). Bundan sonraki tum iceriklerde uygulanacak.", "rapor")
                return self._json(d)
            if u.path == "/api/yayin/tekrar":
                with yayin.kilit(bekle=30):
                    return self._json(yayin.tekrar_dene(g["klasor"]))
            if u.path == "/api/meta/baglan":
                return self._json({"sayfalar": [{k: v for k, v in s.items() if k != "token"} | {"i": i}
                                                for i, s in enumerate(_sayfa_onbellek(g["token"]))]})
            if u.path == "/api/meta/sec":
                s_ = _SAYFALAR[int(g["i"])]
                return self._json(meta.sayfa_sec(s_))
            if u.path == "/api/oneri/karar":    # YALNIZCA kullanicinin tiklamasi
                from ofis import oneriler
                o = oneriler.karar(g["id"], bool(g.get("onay")))
                pano.yaz("Kullanici", "Yonetici", ("Onaylandi: " if o["durum"] == "onaylandi" else "Reddedildi: ")
                         + o["baslik"] + (f" → {o['sonuc']}" if o.get("sonuc") and o["durum"] == "onaylandi" else ""), "rapor")
                return self._json(o)
            if u.path == "/api/toplanti":
                ok = baslat(["yayinla.py", "--toplanti"], "Haftalik toplanti")
                return self._json({"ok": ok, "mesaj": "" if ok else "Baska bir is suruyor"})
            if u.path == "/api/projeler/ac":      # proje klasorunu Windows Gezgini'nde ac
                from ofis import projeler
                projeler.hazirla()
                import os
                if hasattr(os, "startfile"):
                    os.startfile(str(projeler.KLASOR))
                return self._json({"ok": True, "klasor": str(projeler.KLASOR)})
            if u.path == "/api/projeler/tekrar":
                from ofis import projeler
                projeler.tekrar_kullan(g["klasor"])
                return self._json({"ok": True})
            if u.path == "/api/ofis_ayar":
                from ofis import ofis_ayar
                if "rakipler" in g:
                    g["rakipler"] = [str(x).strip().lstrip("@").lower()[:40] for x in g["rakipler"] if str(x).strip()][:8]
                if "deneme_reels" in g and g["deneme_reels"] not in ("kapali", "yeni_formatlar", "hepsi"):
                    g.pop("deneme_reels")
                if "proje_gunu" in g:
                    g["proje_gunu"] = max(-1, min(6, int(g["proje_gunu"])))
                return self._json(ofis_ayar.guncelle(**{k: v for k, v in g.items() if k in ("rakipler", "deneme_reels", "proje_gunu")}))
            if u.path == "/api/rakip/yenile":
                subprocess.Popen([sys.executable, "yayinla.py", "--rakip"], cwd=str(KOK))
                return self._json({"ok": True})
            if u.path == "/api/rapor/olustur":
                subprocess.Popen([sys.executable, "yayinla.py", "--rapor"], cwd=str(KOK))
                return self._json({"ok": True})
            if u.path == "/api/saglik/kontrol":
                from ofis import saglik
                return self._json(saglik.kontrol())
            if u.path == "/api/meta/tani":   # sadece okuma testleri; hicbir sey yayinlamaz
                return self._json(meta.tani())
            if u.path == "/api/meta/kes":
                meta.baglantiyi_kes()
                return self._json(meta.durum())
            if u.path == "/api/puan":
                return self._json(analiz.performans_kaydet(g.pop("klasor"), g))
            if u.path == "/api/analiz":
                ok = baslat(["analiz_et.py"], "Performans analizi")
                return self._json({"ok": ok})
        except Exception as e:
            return self._json({"hata": f"{type(e).__name__}: {e}"}, 400)
        return self._json({"hata": "bilinmeyen istek"}, 404)


def _yarim_kalan_revizyonlar():
    """Sunucu acilirken: yarida kalmis revizyon istekleri eski durumlarina doner."""
    try:
        for x in yayin.liste(100):
            if x["yayin"].get("durum") == "revize_isteniyor":
                yayin.revize_hata(x["klasor"], "Revizyon yarida kaldi (program kapandi). Tekrar isteyebilirsiniz.")
    except Exception as e:
        print("revizyon kontrolu:", e)


if __name__ == "__main__":
    pano.kur()
    _yarim_kalan_revizyonlar()
    threading.Thread(target=yayin_zamanlayici, daemon=True).start()
    port = AYAR.get("sunucu_port", 8780)
    print(f"Ajan ofisi acik: http://localhost:{port}  (kapatmak icin bu pencereyi kapat)")
    ThreadingHTTPServer(("127.0.0.1", port), Isleyici).serve_forever()
