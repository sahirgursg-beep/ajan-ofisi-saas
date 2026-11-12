"""Gunluk ofis akisi. Kullanim:
    python calistir.py                 -> bugun (haftalik planda bugun varsa plana gore)
    python calistir.py --gun 2026-11-12 -> plandaki belirli bir gunu simdiden uret
    python calistir.py --hafta          -> plandaki onayli, henuz uretilmemis tum gunleri uret
    python calistir.py --demo           -> ornek urunlerle (siteye baglanmadan)
    python calistir.py --revize <klasor> -> Onay kartindan istenen revizyonu uretir (yeni versiyon, yine onay bekler)
"""
import hashlib
import sys
import time
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ofis import llm, pano  # noqa: E402
from ofis.ajanlar import bugunun_temasi, tum_ekip  # noqa: E402
from ofis.ayarlar import AYAR, KOK, VERI, CIKTI  # noqa: E402


def _arg(ad):
    return sys.argv[sys.argv.index(ad) + 1] if ad in sys.argv and sys.argv.index(ad) + 1 < len(sys.argv) else None


def main(plan_tarihi=None):
    """Gunun 3 icerigini (post 12:00, carousel 15:00, reels 18:30) - her biri farkli urun - sirayla uretir."""
    from ofis import plan
    demo = "--demo" in sys.argv
    pano.kur()
    plan_tarihi = plan_tarihi or _arg("--gun")
    tarih = plan_tarihi or date.today().isoformat()
    plan_gunu = plan.gun(tarih)
    if plan_gunu and all(plan_gunu["icerikler"].get(t, {}).get("klasor") for t in plan.FORMATLAR) and not plan_tarihi:
        print(f"Bugunun 3 icerigi zaten hazir.")
        return 0
    baslangic = pano.son_id()
    ekip = _ekip()
    Y, U, P = ekip["Yonetici"], ekip["UrunSorumlusu"], ekip["PazarlamaUzmani"]
    print("=" * 60)
    print(f" {AYAR['marka']['ad']} - AJAN OFISI  [{AYAR['musteri_id']}]")
    print(f" LLM: {llm.saglayici_adi()} / {llm.model_adi()}" if llm.hazir() else " LLM: YOK -> sablon modu")
    print("=" * 60)
    pano.yaz("Sistem", "Herkes", "LLM baglantisi: " + ("✅ " + llm.model_adi() if llm.hazir()
                                                      else "❌ yok, ajanlar sablon modunda"), "sistem")
    tema = (plan_gunu or {}).get("tema") or bugunun_temasi()
    if plan_gunu:
        Y.soyle("Herkes", f"Haftalik plana gore {plan_gunu['tarih']} ({plan_gunu['gun']}) icin 3 icerik uretiyoruz: "
                "post 12:00, carousel 15:00, Reels 18:30" + (f" — {plan_gunu['etkinlik']}" if plan_gunu.get("etkinlik") else "") + ".")
    Y.toplanti_ac(tema)
    if not demo:
        try:                     # ilk uretimde (ve haftada bir) sektor arastirmasi: istemler sektore gore sekillenir
            from ofis import arastirma
            if arastirma.eski_mi():
                Y.soyle("Herkes", "Sektor arastirmacisi bu haftanin sektor raporunu hazirliyor...")
                arastirma.guncelle(gunluk=lambda m: pano.yaz("SektorArastirmaci", "SanatYonetmeni", m, "rapor"))
        except Exception as e:
            print("arastirma:", e)

    adaylar = U.urunleri_getir(demo=demo)
    if not adaylar:
        Y.soyle("Herkes", "Urun olmadan devam edemiyoruz, bugunluk bu kadar.", "hata")
        return 1
    from ofis import urun_cekici
    tum = getattr(U, "tum_urunler", []) or urun_cekici.onbellekten() or adaylar
    if plan_gunu:
        plan.eksikleri_doldur(tum, tarih, gunluk=lambda m: P.soyle("Yonetici", m))
        plan_gunu = plan.gun(tarih)

    kullanilan, uretilen = set(), []
    proje = _proje_gunu_mu(tarih, plan_gunu, demo)
    if proje:
        Y.soyle("Herkes", f"🏗 Bugun proje gunu! Tamamlanan isimiz '{proje['baslik']}' ({proje['foto_sayisi']} fotograf) "
                "icin post, carousel ve Reels hazirliyoruz. Gercek fotograflar: yapay zeka ile degistirmiyoruz.", "rapor")
    for tur in plan.FORMATLAR:
        slot = (plan_gunu or {}).get("icerikler", {}).get(tur) if plan_gunu else None
        if slot and slot.get("klasor"):
            kullanilan.add(slot["urun"]["url"])
            continue
        Y.soyle("Herkes", f"— {plan.FORMAT_AD[tur]} icerigine geciyoruz —")
        urun = aci = None
        if proje:
            from ofis import projeler
            urun = projeler.urun_benzeri(proje)
            aci = ("Project showcase: a real, recently completed interior project by our team"
                   + (f" in {proje['konum']}" if proje.get("konum") else "") + ". Inspire people to plan their own home.")
            try:
                klasor = _icerik_uret(urun, aci, tur, tema, plan_gunu, baslangic, ekip)
            except Exception as e:
                Y.soyle("Herkes", f"{plan.FORMAT_AD[tur]} (proje) uretilemedi: {type(e).__name__}: {e}", "hata")
                klasor = None
            if klasor:
                projeler.kullanildi_isaretle(proje, tur, klasor)
                uretilen.append(klasor)
                if plan_gunu:
                    plan.icerik_guncelle(plan_gunu["tarih"], tur, klasor=klasor.name, urun=plan._ozet(urun))
                continue
            urun = aci = None          # proje icerigi cikmadiysa bu format normal urunle devam
        if slot and slot.get("urun"):
            urun, aci = P.plandan(dict(plan_gunu, urun=slot["urun"], aci=slot.get("aci", "")), adaylar, tum)
        if not urun:
            havuz = [u for u in adaylar if u["url"] not in kullanilan] or adaylar
            if tur == "carousel":
                havuz = [u for u in havuz if len(u.get("gorseller") or []) >= 3] or havuz
            urun, aci = P.urun_sec(havuz, tema)
        kullanilan.add(urun["url"])
        try:
            klasor = _icerik_uret(urun, aci, tur, tema, plan_gunu, baslangic, ekip)
        except Exception as e:
            Y.soyle("Herkes", f"{plan.FORMAT_AD[tur]} uretilemedi: {type(e).__name__}: {e}", "hata")
            continue
        if not klasor:
            continue
        uretilen.append(klasor)
        if plan_gunu:
            plan.icerik_guncelle(plan_gunu["tarih"], tur, klasor=klasor.name, urun=plan._ozet(urun))
    if uretilen:
        Y.kapanis(uretilen[-1], 0)
        Y.soyle("Kullanici", f"Bugun {len(uretilen)} icerik hazir: " + ", ".join(k.name for k in uretilen)
                + ". 📤 Onay sekmesinde her biri ayri onay bekliyor.", "rapor")
    print("\nCiktilar:", *[str(k) for k in uretilen], sep="\n  ")
    try:
        from ofis import fal_ai
        h = fal_ai._harcamalar()
        kalem = (h.get("_kalemler") or {}).get(fal_ai._ay(), {})
        print(f"\nBu ay yapay zeka harcamasi: ${fal_ai.bu_ay():.3f} / tavan ${fal_ai.tavan():.0f} :: "
              + ", ".join(f"{k} {v['adet']}x ${v['usd']:.3f}" for k, v in kalem.items()))
    except Exception:
        pass
    time.sleep(1)
    return 0 if uretilen else 1


def _proje_gunu_mu(tarih, plan_gunu, demo):
    """Haftanin proje gunu mu ve paylasilmamis yeni proje var mi? Varsa proje bilgisi."""
    if demo:
        return None
    try:
        from ofis import ofis_ayar, projeler
        gun = int(ofis_ayar.oku().get("proje_gunu", 5))
        if gun < 0 or date.fromisoformat(tarih).weekday() != gun:
            return None
        if plan_gunu and any((plan_gunu.get("icerikler") or {}).get(t, {}).get("klasor") for t in ("post", "carousel", "reels")):
            return None          # gunun bir kismi zaten uretilmis -> karistirma
        return projeler.siradaki()
    except Exception as e:
        print("proje kontrolu:", e)
        return None


def _icerik_uret(urun, aci, tur, tema, plan_gunu, baslangic, ekip):
    M, K, S, R = ekip["MetinYazari"], ekip["KaliteKontrol"], ekip["SanatYonetmeni"], ekip["Rotuscu"]
    Y = ekip["Yonetici"]
    gorsel_yollari, gorseller, dikey = _gorseller(urun, R)
    if not gorseller:
        Y.soyle("Herkes", f"'{urun['ad']}' gorseli indirilemedi, bu icerik atlandi.", "hata")
        return None
    yon = S.sec(urun, tema, gorsel_yollari, tarih=(plan_gunu or {}).get("tarih"))
    satis = (yon in ("C", "E")) if isinstance(yon, str) else (yon["fiyat_stili"] in ("rozet", "serit") or bool(yon["banner"]))
    aci += " Tone: sales-focused, short and energetic." if satis else " Tone: calm, elegant and premium."
    taslak, revizyon = _metin_dongusu(M, K, urun, aci)
    on_ek = plan_gunu["tarih"] if plan_gunu else f"{datetime.now():%Y-%m-%d}"
    return _paketle(urun, gorsel_yollari, gorseller, dikey, taslak, yon, tema, aci, revizyon, on_ek,
                    (plan_gunu or {}).get("tarih"), baslangic, ekip, tur=tur)


def _gorseller(urun, R):
    """Urun fotograflarini indirir, Rotuscu'dan gecirir. Doner: (yollar, PIL gorseller, dikey_yollar)"""
    from ofis import gorsel, urun_cekici
    gorsel_yollari = []
    if urun.get("proje"):       # gercek proje fotograflari: yerel, AI ile degistirilmez
        from pathlib import Path as _P
        yollar = [g for g in urun["gorseller"][:10] if _P(g).exists()]
        return yollar, [gorsel.ac(y) for y in yollar], []
    for g in urun["gorseller"][:3]:
        try:
            from pathlib import Path as _P
            if not str(g).startswith(("http://", "https://")) and _P(g).exists():   # stok / yapay zeka: yerelde hazir
                gorsel.ac(g)
                gorsel_yollari.append(g)
                continue
            yol = urun_cekici.gorsel_indir(g, VERI / "gorsel_onbellek", hashlib.md5(g.encode()).hexdigest() + ".img")
            gorsel.ac(yol)
            gorsel_yollari.append(yol)
        except Exception as e:
            print(f"  ! gorsel indirilemedi: {g} ({e})")
    if not gorsel_yollari:
        return [], [], []
    # Rotuscu: kucuk fotolari netlestirir, yatay fotolari AI ile dikeye tamamlar (urune dokunmaz)
    gorsel_yollari, dikey = R.hazirla(urun, gorsel_yollari)
    return gorsel_yollari, [gorsel.ac(y) for y in gorsel_yollari], dikey


def _metin_dongusu(M, K, urun, aci, ilk_notlar=None):
    """Metin yazari <-> Kalite kontrol dongusu. Doner: (taslak, revizyon_sayisi)"""
    Y = tum_ekip_cache["Yonetici"]
    geri, revizyon = (list(ilk_notlar) if ilk_notlar else None), 0
    while True:
        taslak = M.yaz(urun, aci, geri)
        onay, notlar = K.kontrol(urun, taslak)
        if onay:
            M.bitir("Metnim onaylandi ✅")
            return taslak, revizyon
        geri = list(ilk_notlar or []) + notlar   # patronun notu her turda korunur
        revizyon += 1
        if revizyon > AYAR.get("max_revizyon", 2):
            Y.soyle("Herkes", "Revizyon hakki doldu; son taslakla devam, insan onayinda dikkat!", "uyari")
            M.bitir("Son taslak teslim edildi")
            K.bitir("Uyarilarla gecti ⚠️")
            taslak["_kk_notlar"] = notlar      # otomatik yayina girmez; kullanicinin bakmasini bekler
            return taslak, revizyon


def _paketle(urun, gorsel_yollari, gorseller, dikey, taslak, yon, tema, aci, revizyon, on_ek, plan_tarihi,
             baslangic, ekip, ek_meta=None, muzik_id=None, muzik_haric=None, ek="", tur=None):
    """Post/story/Reels'i cizer, caption + rapor + meta yazar, 'bekliyor' isaretler. Doner: klasor"""
    import json as _json
    from ofis import analiz, yayin
    T, V = ekip["Tasarimci"], ekip["VideoEditoru"]
    kk_notlar = taslak.pop("_kk_notlar", None)
    yon_adi = yon["isim"] if isinstance(yon, dict) else yon
    klasor = CIKTI / (f"{on_ek}_{datetime.now():%H%M}_{''.join(c for c in urun['ad'] if c.isalnum())[:30]}"
                              f"{'_' + tur if tur else ''}{ek}")
    klasor.mkdir(parents=True, exist_ok=True)
    T.ciz(urun, gorsel_yollari, gorseller, taslak, klasor, yon, dikey, tur=tur)
    if tur in (None, "reels"):
        V.kurgula(urun, gorseller, taslak, klasor, gorsel_yollari, yon, dikey, muzik_id=muzik_id, muzik_haric=muzik_haric)

    atif = ""
    if (klasor / "muzik.json").exists():   # CC BY muzik -> lisans geregi sanatci adi caption'a
        atif = _json.loads((klasor / "muzik.json").read_text(encoding="utf-8")).get("atif", "")
    # Platform uzmanlari: ayni icerik her platformda kendi diliyle (Instagram, Facebook, TikTok, LinkedIn)
    from ofis import platformlar
    try:
        pl = platformlar.uret(urun, aci, taslak, tur)
    except Exception as e:
        print("  ! platform metinleri uretilemedi:", e)
        pl = {}
    if atif:
        for v in pl.values():
            v["caption"] = v["caption"] + "\n\n" + atif
    platformlar.kaydet(klasor, pl)
    ig = pl.get("instagram") or {"caption": taslak["caption"] + (("\n\n" + atif) if atif else ""),
                                 "hashtags": taslak.get("hashtags", [])}
    (klasor / "caption.txt").write_text(ig["caption"] + "\n\n" + " ".join(ig.get("hashtags", [])), encoding="utf-8")
    (klasor / "taslak.json").write_text(_json.dumps(taslak, ensure_ascii=False, indent=2), encoding="utf-8")
    rapor = [f"# Gunluk rapor — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"- Tema: {tema}", f"- Urun: {urun['ad']} — {urun['fiyat_metni']}", f"- Aci: {aci}",
             f"- Tasarim: {yon_adi}", f"- Revizyon: {revizyon}", f"- Kaynak: {urun['url']}", "", "## Ofis konusmalari", ""]
    rapor += [f"- **{m['gonderen']} → {m['alici']}**: {m['icerik']}" for m in pano.son_mesajlar(300, sonra_id=baslangic)]
    (klasor / "rapor.md").write_text("\n".join(rapor), encoding="utf-8")
    pano.hazirlandi_isaretle(urun["url"], urun["ad"], klasor)
    m = analiz.meta_yaz(klasor, urun, yon, tema, taslak, plan_tarihi)
    m.update(ek_meta or {})
    m["aci"] = aci
    if tur:
        m["format"] = tur
        m.setdefault("ozellikler", {})["format"] = tur
    if urun.get("proje"):
        m["proje"] = urun.get("proje_klasor")
        m.setdefault("ozellikler", {})["icerik_turu"] = "proje"
    if kk_notlar:
        m["kk_uyari"] = [str(n)[:200] for n in kk_notlar][:6]
    if (klasor / "kurgu.json").exists():   # hangi Reels formati kullanildi -> performans analizi ogrenir
        rf = _json.loads((klasor / "kurgu.json").read_text(encoding="utf-8")).get("reels_format")
        if rf:
            m["reels_format"] = rf
            m.setdefault("ozellikler", {})["reels_format"] = rf
    (klasor / "meta.json").write_text(_json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    yayin.bekliyor_isaretle(klasor.name, plan_tarihi, tur)   # sadece "bekliyor"; onay kullanicida
    return klasor


tum_ekip_cache = {}


def _ekip():
    tum_ekip_cache.clear()
    tum_ekip_cache.update(tum_ekip())
    return tum_ekip_cache


def _urun_bul(url):
    from ofis import fiyat, urun_cekici
    havuz = list(urun_cekici.tum_onbellekten() or []) + list(urun_cekici.onbellekten() or [])
    u = next((x for x in havuz if x.get("url") == url), None)
    if not u:
        from ofis.demo import demo_urunler
        u = next((x for x in demo_urunler() if x.get("url") == url), None)
    return fiyat.hazirla(u) if u else None


def revize(klasor_adi):
    """Onay kartindan istenen revizyonu uretir. Eski icerik 'revize_edildi' olur, yeni versiyon onay bekler."""
    import json as _json
    from ofis import plan, sanat, yayin
    pano.kur()
    eski_k = CIKTI / klasor_adi
    y = yayin.oku(klasor_adi)
    istek = y.get("revize") or {}
    if y.get("durum") != "revize_isteniyor":
        print("Bu icerik icin bekleyen revizyon istegi yok.")
        return 1
    try:
        baslangic = pano.son_id()
        ekip = _ekip()
        Y, M, K, S, R = (ekip[a] for a in ["Yonetici", "MetinYazari", "KaliteKontrol", "SanatYonetmeni", "Rotuscu"])
        meta = _json.loads((eski_k / "meta.json").read_text(encoding="utf-8"))
        secenekler, not_metni = istek.get("secenekler") or [], istek.get("not") or ""
        ad_listesi = ", ".join(S.SECENEKLER.get(s, s) for s in secenekler)
        Y.soyle("SanatYonetmeni", f"Patron '{meta['urun']['ad']}' icin revizyon istedi: "
                + (ad_listesi or "") + (f" — Not: \"{not_metni}\"" if not_metni else ""), "revizyon")

        urun = _urun_bul(meta["urun"]["url"])
        if not urun:
            raise RuntimeError("Urun artik sitede/onbellekte bulunamadi")
        gorsel_yollari, gorseller, dikey = _gorseller(urun, R)
        if not gorseller:
            raise RuntimeError("Urun gorseli indirilemedi")

        eski_tarif = meta.get("tarif") if isinstance(meta.get("tarif"), dict) and meta["tarif"].get("duzen") \
            else sanat.rastgele_tarif(urun, sanat.baglam())
        tarif, metin_notlari, secenekler = S.revize_et(eski_tarif, secenekler, not_metni, urun, gorsel_yollari,
                                                      tarih=meta.get("plan_gunu"))
        if "foto" in secenekler and len(gorsel_yollari) > 1:   # ana fotografi degistir
            gorsel_yollari = gorsel_yollari[1:] + gorsel_yollari[:1]
            gorseller = gorseller[1:] + gorseller[:1]
            dikey = (dikey[1:] + dikey[:1]) if len(dikey) > 1 else dikey
            S.soyle("Tasarimci", "Ana fotograf olarak siradaki fotografi kullan.")
        elif "foto" in secenekler:
            S.soyle("Yonetici", "Bu urunun sitede tek fotografi var; fotograf degistirilemedi.", "uyari")

        aci = meta.get("aci") or meta.get("tema") or ""
        taslak_yol = eski_k / "taslak.json"
        if metin_notlari or not taslak_yol.exists():
            taslak, rev = _metin_dongusu(M, K, urun, aci, metin_notlari or None)
        else:
            taslak, rev = _json.loads(taslak_yol.read_text(encoding="utf-8")), 0
            M.soyle("Tasarimci", "Metin ayni kaliyor, onceki onaylı metni kullanıyoruz.")
            M.bitir()

        eski_muzik = {}
        if (eski_k / "muzik.json").exists():
            eski_muzik = _json.loads((eski_k / "muzik.json").read_text(encoding="utf-8"))
        muzik_id = None if "muzik" in secenekler else eski_muzik.get("id")
        muzik_haric = {eski_muzik.get("id")} if "muzik" in secenekler and eski_muzik.get("id") else None

        surum = int(meta.get("surum") or 1) + 1
        on_ek = meta.get("plan_gunu") or f"{datetime.now():%Y-%m-%d}"
        klasor = _paketle(urun, gorsel_yollari, gorseller, dikey, taslak, tarif, meta.get("tema", ""), aci, rev,
                          on_ek, meta.get("plan_gunu"), baslangic, ekip, ek=f"_v{surum}",
                          ek_meta={"surum": surum, "onceki_versiyon": klasor_adi,
                                   "revize": {"secenekler": secenekler, "not": not_metni}},
                          muzik_id=muzik_id, muzik_haric=muzik_haric, tur=meta.get("format"))
        yayin.revize_tamam(klasor_adi, klasor.name)
        if meta.get("plan_gunu"):
            pg = plan.gun(meta["plan_gunu"]) or {}
            for t, ic in pg.get("icerikler", {}).items():
                if ic.get("klasor") == klasor_adi:
                    plan.icerik_guncelle(meta["plan_gunu"], t, klasor=klasor.name)
            if pg.get("klasor") == klasor_adi:
                plan.guncelle(meta["plan_gunu"], klasor=klasor.name)
        Y.soyle("Kullanici", f"Revizyon hazir (v{surum}) ✅ Onay sekmesinde yeni versiyon seni bekliyor.", "rapor")
        Y.bitir("Revizyon tamam")
        print(f"\nYeni versiyon: {klasor}")
        return 0
    except Exception as e:
        yayin.revize_hata(klasor_adi, f"{type(e).__name__}: {e}")
        pano.yaz("Yonetici", "Kullanici", f"Revizyon yapilamadi: {type(e).__name__}: {e}", "hata")
        raise


def hafta():
    from ofis import plan
    kalan = [g for g in plan.oku().get("gunler", []) if g.get("durum") == "onayli"
             and not all(g["icerikler"].get(t, {}).get("klasor") for t in plan.FORMATLAR)]
    if not kalan:
        print("Uretilecek onayli gun yok. Ofis ekranindaki Plan sekmesinden gunleri onaylayin.")
        return 0
    for g in kalan:
        print(f"\n===== {g['tarih']} {g['gun']}: " + " | ".join(f"{t}: {ic['urun']['ad']}" for t, ic in g["icerikler"].items() if ic.get("urun")) + " =====")
        try:
            main(g["tarih"])
        except Exception as e:
            pano.yaz("Sistem", "Yonetici", f"{g['tarih']} uretilemedi: {type(e).__name__}: {e}", "hata")
    return 0


def otomatik_plan():
    """Onumuzde planli gun kalmadiysa (ya da pazar gunu son 1 gun kaldiysa) gelecek haftayi kendiligindan planla."""
    import subprocess
    from ofis import fikir_kaynagi
    if fikir_kaynagi.veri_yok_mu() and "--demo" not in sys.argv:
        return                    # urun listesi olmayan isletme: icerik her gun fikirlerden uretilir, urun plani yok
    from datetime import timedelta
    from ofis import plan
    yarin = (date.today() + timedelta(days=1)).isoformat()
    ileri = [g for g in plan.oku().get("gunler", []) if g["tarih"] >= yarin]
    if not ileri or (date.today().weekday() == 6 and len(ileri) <= 1):
        bas = (date.fromisoformat(ileri[-1]["tarih"]) + timedelta(days=1)).isoformat() if ileri else yarin
        print(f"\nGelecek hafta icin plan hazirlaniyor ({bas})...")
        subprocess.run([sys.executable, str(KOK / "planla.py"), "--baslangic", bas]
                       + (["--demo"] if "--demo" in sys.argv else []), cwd=str(KOK))


if __name__ == "__main__":
    if "--revize" in sys.argv:
        sys.exit(revize(_arg("--revize")))
    if "--hafta" in sys.argv:
        sys.exit(hafta())
    sonuc = main()
    if "--gun" not in sys.argv and "--plansiz" not in sys.argv:
        otomatik_plan()
    sys.exit(sonuc)
