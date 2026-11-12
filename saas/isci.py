"""Isci: kuyruktaki isleri yapar (Cloud Run Job ya da yerelde alt surec).

Her is icin:
  1) indir   : musterinin profili, veri paketi, Meta baglantisi ve icerik kayitlari gecici bir klasore
  2) calistir: ofis/ ajanlari o klasorde, o musteri icin ayri bir surecte calisir (calistir.py, yayinla.py...)
  3) geri yaz: yeni/degisen icerikler, gorseller, veri paketi ve ofis panosu depoya
Gecici klasor is bitince silinir; kalici olan her sey depodadir. Ayni musteride ayni anda tek is calisir.

Kullanim: python -m saas.isci            (kuyruk bosalana kadar)
          python -m saas.isci --bir-is   (tek is)
"""
import io
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path

from . import ayar, guvenlik
from .depo import Cakisma, depo

MEDYA = {".jpg", ".jpeg", ".png", ".mp4", ".webp"}
EK_SINIRI = 300_000                       # bundan buyuk metin dosyasi icerik kaydina girmez
VERI_HARIC = {"meta.json", "yayin.kilit", "gorsel_onbellek", "proje_onbellek", "yayinci_hata.log", "gunluk.log"}
MEDYA_GEREKEN_DURUMLAR = {"onaylandi", "yayinlaniyor", "kismen", "hata", "kacirildi", "kaldiriliyor",
                          "kaldirma_hatasi", "revize_isteniyor"}
ISCI_DURUMLARI = {"yayinlaniyor", "yayinlandi", "kismen", "hata", "kaldirildi", "kaldirma_hatasi", "kacirildi",
                  "revize_edildi"}


def gunluk(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- indir
def _guvenli_ac(arsiv, hedef):
    with tarfile.open(fileobj=io.BytesIO(arsiv), mode="r:gz") as t:
        t.extractall(hedef, filter="data")


def indir(m, kok, tur, parametre):
    """Musterinin calisma klasorunu kurar. -> anlik goruntu (geri yazarken neyin degistigini bilmek icin)."""
    d, mid = depo(), m["id"]
    veri, cikti = kok / "veri", kok / "cikti"
    veri.mkdir(parents=True)
    cikti.mkdir(parents=True)
    (kok / "profil.json").write_text(json.dumps(m["profil"], ensure_ascii=False, indent=2), encoding="utf-8")

    paket = kok.parent / "_veri.tar.gz"
    if d.dosya_indir(f"{mid}/veri.tar.gz", paket):
        _guvenli_ac(paket.read_bytes(), veri)
        paket.unlink()
    if m.get("yayin_ayar"):
        (veri / "yayin_ayar.json").write_text(json.dumps(m["yayin_ayar"], ensure_ascii=False), encoding="utf-8")
    baglanti = guvenlik.coz(m.get("meta_token"))
    if baglanti:
        (veri / "meta.json").write_text(json.dumps(baglanti, ensure_ascii=False), encoding="utf-8")

    goruntu = {}
    hedef_klasor = (parametre or {}).get("klasor")
    for ic in d.icerikler(mid, 80):
        k = cikti / ic["klasor"]
        k.mkdir()
        for ad, metin in (ic.get("ekler") or {}).items():
            if "/" not in ad and "\\" not in ad and ad not in ("meta.json", "yayin.json", "caption.txt"):
                (k / ad).write_text(metin, encoding="utf-8")
        (k / "meta.json").write_text(json.dumps(ic.get("meta") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
        (k / "yayin.json").write_text(json.dumps(ic.get("yayin") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
        (k / "caption.txt").write_text(ic.get("caption") or "", encoding="utf-8")
        gerek = tur in ("yayin_turu", "kaldir", "revize") and (
            (ic.get("yayin") or {}).get("durum") in MEDYA_GEREKEN_DURUMLAR or ic["klasor"] == hedef_klasor)
        if gerek:
            for ad in ic.get("dosyalar") or []:
                d.dosya_indir(f"{mid}/cikti/{ic['klasor']}/{ad}", k / ad)
        goruntu[ic["klasor"]] = {"surum": ic["surum"], "yayin": ic.get("yayin") or {}, "meta": ic.get("meta") or {},
                                 "caption": ic.get("caption") or "", "ekler": ic.get("ekler") or {},
                                 "dosyalar": set(ic.get("dosyalar") or [])}
    return {"icerik": goruntu, "pano_son": _pano_son_id(veri), "yayin_ayar": m.get("yayin_ayar") or {}}


def _pano_son_id(veri):
    db = veri / "pano.db"
    if not db.exists():
        return 0
    try:
        with sqlite3.connect(db) as c:
            return c.execute("SELECT COALESCE(MAX(id),0) FROM mesajlar").fetchone()[0]
    except sqlite3.Error:
        return 0


# ---------------------------------------------------------------- calistir
def komutlar(tur, parametre, kok):
    py = sys.executable
    adimlar = []
    if any((json.loads(p.read_text(encoding="utf-8")).get("bekleyen_iptal"))
           for p in (kok / "cikti").glob("*/yayin.json")):
        adimlar.append([py, "-m", "saas.ofis_kopru", "iptaller"])
    p = parametre or {}
    if tur == "uret":
        adimlar.append([py, "calistir.py"] + (["--demo"] if p.get("demo") else []) +
                       (["--plansiz"] if p.get("plansiz", True) else []))
    elif tur == "yayin_turu":
        adimlar.append([py, "yayinla.py", "--otomatik"])
    elif tur == "kaldir":
        adimlar.append([py, "-m", "saas.ofis_kopru", "kaldir", p["klasor"]])
    elif tur == "revize":
        adimlar.append([py, "calistir.py", "--revize", p["klasor"]])
    elif tur == "plan":
        adimlar.append([py, "planla.py"] + (["--demo"] if p.get("demo") else []))
    return adimlar


def calistir(mid, tmp, paylasik, adimlar, sure_sn):
    ortam = {**os.environ, "AJAN_MUSTERI": mid, "AJAN_MUSTERILER_KOK": str(tmp / "musteriler"),
             "AJAN_PAYLASIK_KOK": str(paylasik), "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    for sir in [k for k in ortam if k.startswith(("SUPABASE_", "SAAS_SIFRELEME", "SAAS_IMZA", "SAAS_ZAMANLAYICI",
                                                  "META_APP_SECRET"))]:
        ortam.pop(sir)          # ajan sureci platform sirlarini gormez; yalnizca kendi musterisinin verisini
    cikti, basari = [], True
    bitis = time.time() + sure_sn
    for komut in adimlar:
        kalan = max(30, bitis - time.time())
        try:
            r = subprocess.run(komut, cwd=str(ayar.KOK), env=ortam, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=kalan)
            cikti.append(f"$ {' '.join(komut[1:])} -> {r.returncode}\n{r.stdout[-3000:]}{r.stderr[-1500:]}")
            basari &= r.returncode == 0
        except subprocess.TimeoutExpired:
            cikti.append(f"$ {' '.join(komut[1:])} -> ZAMAN ASIMI ({int(kalan)} sn)")
            basari = False
            break
    return basari, "\n".join(cikti)


# ---------------------------------------------------------------- geri yaz
def _klasor_oku(k):
    meta = json.loads((k / "meta.json").read_text(encoding="utf-8"))
    y_yol = k / "yayin.json"
    yayin = json.loads(y_yol.read_text(encoding="utf-8")) if y_yol.exists() else {"durum": "bekliyor"}
    caption = (k / "caption.txt").read_text(encoding="utf-8") if (k / "caption.txt").exists() else ""
    ekler, medya = {}, []
    for f in sorted(k.iterdir()):
        if not f.is_file() or f.name in ("meta.json", "yayin.json", "caption.txt"):
            continue
        if f.suffix.lower() in MEDYA:
            medya.append(f.name)
        elif f.suffix.lower() in (".json", ".txt", ".md") and f.stat().st_size <= EK_SINIRI:
            ekler[f.name] = f.read_text(encoding="utf-8", errors="replace")
    tur = meta.get("format") or meta.get("tur") or (k.name.rsplit("_", 1)[-1] if "_" in k.name else None)
    return {"klasor": k.name, "tur": tur, "meta": meta, "yayin": yayin, "caption": caption, "ekler": ekler,
            "dosyalar": medya}


def birlestir(db_yayin, isci_yayin):
    """Iscinin calistigi surede kullanici panelden karar verdiyse: kararlar (durum, hedef, saat, metin, onay)
    kullanicinindir; Meta'da olusan kimlikler (sonuc) ASLA kaybolmaz; iscinin yayin sonucu durumlari korunur."""
    y = dict(db_yayin)
    sonuc = {**(db_yayin.get("sonuc") or {})}
    for h, r in (isci_yayin.get("sonuc") or {}).items():
        if r.get("id") or h not in sonuc:
            sonuc[h] = {**sonuc.get(h, {}), **r}
    y["sonuc"] = sonuc
    if isci_yayin.get("durum") in ISCI_DURUMLARI and db_yayin.get("durum") not in ("kaldiriliyor", "reddedildi"):
        for k in ("durum", "yayin_zamani", "kaldirma_zamani", "kacirilan", "yeni_versiyon", "revize_hata"):
            if k in isci_yayin:
                y[k] = isci_yayin[k]
    return y


def geri_yaz(m, kok, goruntu, tur, basari):
    d, mid = depo(), m["id"]
    veri, cikti = kok / "veri", kok / "cikti"
    yazilan = 0
    for k in sorted(cikti.iterdir()):
        if not (k / "meta.json").exists():
            continue
        kayit = _klasor_oku(k)
        eski = goruntu["icerik"].get(k.name)
        for ad in kayit["dosyalar"]:
            if not eski or ad not in eski["dosyalar"]:
                d.dosya_yukle(f"{mid}/cikti/{k.name}/{ad}", k / ad)
        if eski:
            kayit["dosyalar"] = sorted(set(kayit["dosyalar"]) | eski["dosyalar"])   # indirilmemis olanlar da kalir
            if all(kayit[a] == (eski[a] if a != "dosyalar" else sorted(eski["dosyalar"]))
                   for a in ("yayin", "meta", "caption", "ekler", "dosyalar")):
                continue
            try:
                d.icerik_yaz(mid, kayit, beklenen_surum=eski["surum"])
            except Cakisma:
                guncel = d.icerik_al(mid, k.name)
                kayit["yayin"] = birlestir(guncel.get("yayin") or {}, kayit["yayin"])
                kayit["caption"] = guncel.get("caption", kayit["caption"]) if kayit["caption"] == eski["caption"] \
                    else kayit["caption"]
                d.icerik_yaz(mid, kayit, beklenen_surum=guncel["surum"])
        else:
            d.icerik_yaz(mid, kayit)
        yazilan += 1

    # veri paketi (Meta anahtari ve onbellekler haric)
    paket = kok.parent / "_veri_yeni.tar.gz"
    with tarfile.open(paket, "w:gz") as t:
        for f in sorted(veri.iterdir()):
            if f.name not in VERI_HARIC:
                t.add(f, arcname=f.name)
    d.dosya_yukle(f"{mid}/veri.tar.gz", paket, "application/gzip")

    guncelle = {}
    ya = veri / "yayin_ayar.json"
    if ya.exists():
        yeni = json.loads(ya.read_text(encoding="utf-8"))
        if yeni != goruntu["yayin_ayar"]:
            guncel_m = d.musteri_al(mid)
            # panelden degisen alanlar kazanir; ajanlarin degistirdigi (saatler vb.) eklenir
            panel_degisen = {k: v for k, v in (guncel_m.get("yayin_ayar") or {}).items()
                             if goruntu["yayin_ayar"].get(k) != v}
            guncelle["yayin_ayar"] = {**yeni, **panel_degisen}
    if tur == "uret" and basari:
        guncelle["son_uretim"] = time.strftime("%Y-%m-%d")
    if guncelle:
        d.musteri_guncelle(mid, **guncelle)

    db = veri / "pano.db"
    if db.exists():
        with sqlite3.connect(db) as c:
            satirlar = c.execute("SELECT zaman, gonderen, alici, tur, icerik FROM mesajlar WHERE id>? ORDER BY id",
                                 (goruntu["pano_son"],)).fetchall()
        d.pano_ekle(mid, [{"zaman": None, "gonderen": g, "alici": a, "tur": t, "icerik": (i or "")[:2000]}
                          for _, g, a, t, i in satirlar][-300:])
    return yazilan


# ---------------------------------------------------------------- is dongusu
def paylasik_hazirla(hedef):
    """Ortak varliklar (takvimler + depodaki muzik/font arsivi). Isci calismasi boyunca bir kez."""
    import shutil
    if not hedef.exists():
        shutil.copytree(ayar.KOK / "paylasilan", hedef)
        arsiv = hedef.parent / "_paylasilan.tar.gz"
        if depo().dosya_indir("_paylasilan/varliklar.tar.gz", arsiv):
            _guvenli_ac(arsiv.read_bytes(), hedef)
    return hedef


def bir_is(isci_adi, paylasik):
    d = depo()
    is_ = d.is_al(isci_adi, ayar.ISCI_EN_UZUN_DK + 10)
    if not is_:
        return None
    mid, tur = is_["musteri_id"], is_["tur"]
    gunluk(f"IS {is_['id'][:8]} {mid} {tur} {is_.get('parametre')}")
    try:
        m = d.musteri_al(mid)
        if not m:
            raise RuntimeError("Musteri yok")
        if m["durum"] in ("duraklatildi", "kapali") and tur not in ("kaldir",):
            d.is_bitir(is_["id"], "hata", f"Abonelik {m['durum']}: is yapilmadi")
            return is_
        with tempfile.TemporaryDirectory(prefix="ajan_") as t:
            tmp = Path(t)
            kok = tmp / "musteriler" / mid
            kok.mkdir(parents=True)
            goruntu = indir(m, kok, tur, is_.get("parametre"))
            adimlar = komutlar(tur, is_.get("parametre"), kok)
            basari, kayit = calistir(mid, tmp, paylasik, adimlar, ayar.ISCI_EN_UZUN_DK * 60)
            yazilan = geri_yaz(m, kok, goruntu, tur, basari)
        d.is_bitir(is_["id"], "bitti" if basari else "hata", f"{yazilan} icerik guncellendi\n{kayit}")
        gunluk(f"IS {is_['id'][:8]} {'bitti' if basari else 'HATA'} ({yazilan} icerik)")
    except Exception:
        hata = traceback.format_exc()
        gunluk(hata)
        d.is_bitir(is_["id"], "hata", hata[-3000:])
    return is_


def main():
    isci_adi = f"{socket.gethostname()}-{os.getpid()}"
    bitis = time.time() + ayar.ISCI_EN_UZUN_DK * 60
    with tempfile.TemporaryDirectory(prefix="ajan_paylasilan_") as p:
        paylasik = paylasik_hazirla(Path(p) / "paylasilan")
        sayi = 0
        while time.time() < bitis:
            if bir_is(isci_adi, paylasik) is None:
                break
            sayi += 1
            if "--bir-is" in sys.argv:
                break
    gunluk(f"Isci bitti: {sayi} is")
    return 0


if __name__ == "__main__":
    sys.exit(main())
