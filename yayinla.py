"""Yayinci (sosyal medya isleri). Ofis ekrani (sunucu.py) her dakika, Windows Gorev Zamanlayici her 10 dakikada
bir calistirir; ayni anda tek kopya calisir (kilit).
    python yayinla.py --otomatik     -> hepsi: otomatik planla, Meta'ya planla, saati geleni yayinla,
                                       kaldirma isteklerini isle, saatte bir istatistik, gunde bir iletisim raporu
    python yayinla.py --bekleyenler  -> sadece saati gelmis onayli icerikleri yayinla
    python yayinla.py --istatistik   -> sadece rakamlari cek
    python yayinla.py --iletisim     -> sadece yorum/DM raporu
    python yayinla.py --toplanti     -> haftalik ajan toplantisi (oneriler)
    python yayinla.py --rakip        -> rakip/ilham hesaplarini tara
    python yayinla.py --rapor        -> haftalik yonetici raporu
    python yayinla.py --saglik       -> saglik kontrolu
Yorum ve mesajlara CEVAP YAZILMAZ; sadece okunur ve raporlanir.
"""
import json
import sys
import time

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ofis import meta, pano, yayin  # noqa: E402
from ofis.ayarlar import KOK, VERI  # noqa: E402

DURUM = VERI / "yayinci_durum.json"


def _durum():
    try:
        return json.loads(DURUM.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _durum_yaz(d):
    DURUM.parent.mkdir(parents=True, exist_ok=True)
    DURUM.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


_ekip = {}


def ekip():
    if not _ekip:
        from ofis.ajanlar import tum_ekip
        pano.kur()
        _ekip.update(tum_ekip())
    return _ekip


def _sm():
    return ekip()["SosyalMedya"]


def kaldirmalar():
    for x in yayin.liste(80):
        if x["yayin"].get("durum") == "kaldiriliyor":
            sm = _sm()
            try:
                yayin.kaldir(x["klasor"])
                sm.soyle("Yonetici", f"Istediginiz icerik yayindan kaldirildi: {x['meta']['urun']['ad']}", "rapor")
            except Exception as e:
                sm.soyle("Yonetici", f"Kaldirma tamamlanamadi: {e}", "hata")


def otomatik_onaylar():
    adaylar = yayin.otomatik_adaylar()
    for k in adaylar:
        y = yayin.otomatik_onayla(k)
        _sm().soyle("Yonetici", f"Otomatik yayina alindi 📅 {k} → {y.get('zaman', '').replace('T', ' ')} {yayin.musteri.KISALTMA} "
                    f"({', '.join(yayin.HEDEFLER[h] for h in y.get('hedefler', []))}). Istemezseniz Yayin sekmesinden 'Kaldir'.")
    for k in yayin.kacirilanlari_isaretle():
        _sm().soyle("Yonetici", f"Bilgisayar kapali kaldigi icin {k} saatinde yayinlanamadi; gec saatte otomatik "
                    "paylasmadim. Yayin sekmesinden 'Simdi yayinla' diyebilirsiniz.", "uyari")


def meta_planlari():
    for k in yayin.meta_planlanacaklar():
        sm = _sm()
        sm.calis(f"Facebook gonderileri Meta'da planlaniyor: {k}")
        y = yayin.meta_planla(k, gunluk=lambda m: pano.durum(sm.ad, "calisiyor", m))
        planli = [yayin.HEDEFLER[h] for h, r in (y.get("sonuc") or {}).items() if r.get("planli")]
        hatali = [yayin.HEDEFLER[h] for h, r in (y.get("sonuc") or {}).items() if r.get("plan_hata")]
        _ENGEL.extend(r["plan_hata"] for r in (y.get("sonuc") or {}).values() if r.get("plan_hata"))
        if any(meta.engel_mi(e) for e in _ENGEL):
            sm.bitir()
            return
        if planli:
            sm.soyle("Yonetici", f"Meta planlayicisina eklendi: {', '.join(planli)} ({y.get('zaman', '').replace('T', ' ')} {yayin.musteri.KISALTMA}). "
                     "Business Suite'te gorebilirsiniz.")
        if hatali and not any(meta.engel_mi(e) for e in _ENGEL):
            sm.soyle("Yonetici", f"{', '.join(hatali)} Meta'da planlanamadi; saatinde buradan yayinlayacagim.", "uyari")
        sm.bitir()


def bekleyenler():
    for k in yayin.zamani_gelenler():
        sm = _sm()
        y = yayin.oku(k)
        sm.calis(f"Yayinlaniyor: {k}")
        try:
            sonuc = yayin.yayinla(k, gunluk=lambda m: pano.durum(sm.ad, "calisiyor", m))
            ok = [yayin.HEDEFLER[h] for h, r in sonuc.get("sonuc", {}).items() if r.get("id") and not r.get("planli")]
            hata = [f"{yayin.HEDEFLER[h]}: {r['hata']}" for h, r in sonuc.get("sonuc", {}).items() if r.get("hata")]
            _ENGEL.extend(r["hata"] for r in sonuc.get("sonuc", {}).values() if r.get("hata"))
            if ok:
                sm.soyle("Herkes", f"Yayinlandi ✅ {', '.join(ok)} — {y.get('caption', '')[:60]}...", "rapor")
            if hata:
                sm.soyle("Yonetici", "Yayin hatasi: " + " | ".join(hata)[:400], "hata")
        except PermissionError as e:
            sm.soyle("Yonetici", f"Guvenlik: {e}", "hata")
        except Exception as e:
            _ENGEL.append(str(e))
            sm.soyle("Yonetici", f"Yayin yapilamadi ({type(e).__name__}: {e})", "hata")
        sm.bitir()
        if any(meta.engel_mi(e) for e in _ENGEL):
            break


def istatistik():
    sm = _sm()
    sm.calis("Instagram + Facebook rakamlarini cekiyorum...")
    n = yayin.istatistikleri_guncelle(gunluk=lambda m: pano.durum(sm.ad, "calisiyor", m))
    if n:
        sm.soyle("PerformansAnalisti", f"{n} icerigin rakamlari guncellendi (izlenme, begeni, kaydetme, paylasim, yorum).")
    sm.bitir()
    return n


def iletisim():
    return ekip()["IletisimAnalisti"].rapor()


def saglik_kontrol():
    from ofis import saglik
    r = saglik.kontrol()
    sorunlar = [f"{k['ad']}: {k['mesaj']}" for k in r["kontroller"] if k["durum"] != "ok"]
    if sorunlar:
        ekip()["Yonetici"].soyle("Herkes", "Sabah kontrolu: " + " | ".join(sorunlar)[:500],
                                 "hata" if r["durum"] == "hata" else "uyari")
    return r


def rakip_tara():
    from ofis import rakip
    sm = ekip()["PazarlamaUzmani"]
    sm.calis("Rakip ve ilham hesaplarini tariyorum (sadece okuma)...")
    try:
        r = rakip.guncelle(gunluk=lambda m: pano.durum(sm.ad, "calisiyor", m))
        satir = rakip.ozet_satirlari(r)
        if satir:
            sm.soyle("SanatYonetmeni", "Rakip/ilham ozeti: " + " | ".join(satir)[:550])
    except Exception as e:
        sm.soyle("Yonetici", f"Rakip taramasi yapilamadi: {e}", "uyari")
    sm.bitir()


def toplanti():
    from ofis import oneriler
    y = ekip()["Yonetici"]
    y.calis("Haftalik toplanti: gecen haftayi tartisiyoruz...")
    r = oneriler.toplanti()
    y.bitir(f"Toplanti bitti: {len(r['oneriler'])} oneri onayda")
    return r


def rapor():
    from ofis import haftalik_rapor
    yol = haftalik_rapor.olustur()
    ekip()["Yonetici"].soyle("Kullanici", f"Haftalik yonetici raporu hazir: Performans sayfasindaki 'Raporlar' bolumunden "
                             f"acabilirsiniz ({yol.name}).", "rapor")
    return yol


def haftalik_isler(d, simdi):
    """Pazartesi 09:00'dan sonra bir kez: rakip taramasi -> toplanti -> rapor -> yedek."""
    from ofis import saglik
    an = yayin.simdi()
    hafta = an.strftime("%G-W%V")
    if an.weekday() != 0 or an.hour < 9 or d.get("haftalik") == hafta:
        return
    d["haftalik"] = hafta
    _durum_yaz(d)
    if meta.bagli():
        rakip_tara()
    toplanti()
    try:
        rapor()
    except Exception as e:
        print("rapor:", e)
    try:
        saglik.yedekle()
    except Exception as e:
        print("yedek:", e)


def otomatik():
    """Tek tur. Mesai (musterinin yerel saatiyle) disinda Meta'ya istek atilmaz; nadir isler zaman damgasiyla seyreltilir."""
    d = _durum()
    simdi = time.time()
    if yayin.mesai_icinde() and d.get("saglik_gun") != yayin.simdi().date().isoformat() and yayin.simdi().hour >= 8:
        d["saglik_gun"] = yayin.simdi().date().isoformat()
        d["saglik_zaman"] = simdi
        _durum_yaz(d)
        try:
            saglik_kontrol()
        except Exception as e:
            print("saglik:", e)
    elif yayin.mesai_icinde() and simdi - d.get("saglik_zaman", 0) > 600:
        from ofis import saglik      # sorun varsa 10 dakikada bir sessizce yeniden bak (duzeltildiyse uyari kalksin)
        if saglik.son().get("durum") not in (None, "ok"):
            d["saglik_zaman"] = simdi
            _durum_yaz(d)
            try:
                saglik.kontrol()
            except Exception as e:
                print("saglik:", e)
    if yayin.mesai_icinde() and simdi - d.get("arastirma_zaman", 0) > 6 * 3600:
        d["arastirma_zaman"] = simdi    # haftalik sektor arastirmasi (eskiyse); 6 saatte bir kontrol edilir
        _durum_yaz(d)
        try:
            from ofis import arastirma
            if arastirma.eski_mi():
                arastirma.guncelle(gunluk=lambda m: pano.yaz("SektorArastirmaci", "SanatYonetmeni", m, "rapor"))
        except Exception as e:
            print("arastirma:", e)
    if simdi < d.get("meta_bekle", 0):
        return                        # Meta engeli: bekleme suresi dolmadi
    yayin.mesaiye_uydur(gunluk=print)
    kaldirmalar()
    if not meta.bagli():
        otomatik_onaylar()            # onay kaydi yine tutulur; baglanti kurulunca yayinlanir
        return
    otomatik_onaylar()
    if not yayin.mesai_icinde():
        return
    hata_once = d.get("son_engel_mesaji", 0)
    try:
        yayin.engel_sonrasi_tekrar()
        meta_planlari()
        bekleyenler()
        kaldirmalar()
    finally:
        engel = _son_engel()
        if engel:
            d["meta_bekle"] = simdi + 3600
            if simdi - hata_once > 6 * 3600:
                d["son_engel_mesaji"] = simdi
                _sm().soyle("Yonetici", "Meta isteklerimizi reddediyor (" + engel[:160] + "). Hesabi korumak icin 1 saat "
                            "hic deneme yapmiyorum. Yayin sekmesindeki '🔍 Baglantiyi test et' ile sebebini gorebilirsiniz.", "hata")
            _durum_yaz(d)
            return
    a = yayin.ayar_oku()
    haftalik_isler(d, simdi)
    if simdi - d.get("istatistik", 0) > 3 * 3600:
        d["istatistik"] = simdi
        _durum_yaz(d)
        istatistik()
    if simdi - d.get("iletisim", 0) > 20 * 3600 and yayin.simdi().strftime("%H:%M") >= a.get("rapor_saati", "18:00"):
        d["iletisim"] = simdi          # mesai bitmeden (18:00) gunluk yorum/DM raporu + performans analizi
        _durum_yaz(d)
        iletisim()
        try:
            ekip()["PerformansAnalisti"].analiz()
        except Exception as e:
            print("analiz:", e)


_ENGEL = []


def _son_engel():
    """Bu turda alinan hatalardan biri hesap capinda engel mi?"""
    return next((h for h in _ENGEL if meta.engel_mi(h)), "")


def main():
    tek = {"--toplanti": toplanti, "--rakip": rakip_tara, "--rapor": rapor, "--saglik": saglik_kontrol}
    for bayrak, f in tek.items():          # yayin yapmayan, elle baslatilan isler: kilit beklemez
        if bayrak in sys.argv:
            try:
                f()
            except Exception:
                import traceback
                with open(VERI / "yayinci_hata.log", "a", encoding="utf-8") as fh:
                    fh.write(time.strftime("%Y-%m-%d %H:%M ") + traceback.format_exc() + "\n")
                return 1
            return 0
    try:
        with yayin.kilit():
            if "--istatistik" in sys.argv:
                if meta.bagli():
                    istatistik()
            elif "--iletisim" in sys.argv:
                iletisim()
            elif "--tani" in sys.argv:
                meta.tani()
            elif "--bekleyenler" in sys.argv:
                if meta.bagli():
                    bekleyenler()
            else:
                otomatik()
    except TimeoutError:
        return 0       # baska bir kopya calisiyor
    except Exception:
        import traceback
        with open(VERI / "yayinci_hata.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M ") + traceback.format_exc() + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
