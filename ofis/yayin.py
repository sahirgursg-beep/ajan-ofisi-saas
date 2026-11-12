"""Yayin akisi.

OTOMATIK YAYIN (kullanicinin karari, veri/yayin_ayar.json "otomatik"; ofis ekranindan kapatilabilir):
  uretim -> "bekliyor"
  -> otomatik_onayla(): kalite kontrolden TEMIZ gecmis ve saati ileride olan icerik "onaylandi" (kaynak: otomatik)
  -> meta_planla(): Facebook hedefleri Meta'nin kendi planlayicisina gonderilir (Business Suite'te gorunur);
     Instagram'in API'sinde planlama yok, saatinde bu bilgisayardan yayinlanir.
  -> saatinde yayinla() -> "yayinlandi" / "kismen" / "hata"
  Kullanici istediginde kaldir(): planli Facebook gonderileri iptal, yayinlanmis olanlar Meta'dan silinir.
Kalite kontrol uyarisiyla gecen icerik, onayi geri alinan icerik ve saati gecmis icerik otomatik yayina GIRMEZ;
kullanicinin "Onayla"sini bekler. Otomatik yayin kapaliysa eski kural gecerli: onay olmadan yayin yok.
Zamanlar musterinin yerel saatidir (profil.json -> isletme.saat_dilimi).
"""
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import musteri
from .ayarlar import AYAR, KOK, VERI, CIKTI

CIKTI = CIKTI
YEREL = musteri.YEREL
WAT = YEREL          # eski ad; yeni kod YEREL kullansin
HEDEFLER = {"ig_post": "Instagram Post", "ig_carousel": "Instagram Carousel", "ig_story": "Instagram Story",
            "ig_reels": "Instagram Reels", "fb_post": "Facebook Post", "fb_carousel": "Facebook Carousel",
            "fb_story": "Facebook Story", "fb_reels": "Facebook Reels"}
VARSAYILAN_HEDEF = AYAR.get("yayin_hedefleri", ["ig_post", "ig_story", "ig_reels", "fb_post", "fb_reels"])


AYAR_YOL = VERI / "yayin_ayar.json"
VARSAYILAN_AYAR = {"otomatik": True, "gecikme_siniri_dk": 120, "fb_meta_planla": True,
                   # Mesai musterinin yerel saatiyle; profil.json -> isletme.mesai ile degistirilir.
                   "mesai_bas": musteri.bilgi().get("mesai_bas", "08:00"),
                   "mesai_bit": musteri.bilgi().get("mesai_bit", "19:00"),
                   "saatler": {"post": "12:00", "carousel": "15:00", "reels": "18:30"},
                   "rapor_saati": "18:00"}
FB_PLANLANIR = ("fb_post", "fb_carousel", "fb_reels")   # Facebook'un kendi planlayicisina gidebilenler


def simdi():
    return datetime.now(YEREL)


def ayar_oku():
    try:
        return {**VARSAYILAN_AYAR, **json.loads(AYAR_YOL.read_text(encoding="utf-8"))}
    except Exception:
        return dict(VARSAYILAN_AYAR)


def ayar_kaydet(degisen):
    a = ayar_oku()
    a.update({k: v for k, v in degisen.items() if k in VARSAYILAN_AYAR})
    AYAR_YOL.parent.mkdir(parents=True, exist_ok=True)
    AYAR_YOL.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    return a


@contextmanager
def kilit(bekle=0):
    """Ayni anda tek yayinci (ofis ekrani + Gorev Zamanlayici ayni icerigi iki kez yayinlamasin)."""
    yol = VERI / "yayin.kilit"
    yol.parent.mkdir(parents=True, exist_ok=True)
    bas = time.time()
    while True:
        try:
            fd = os.open(str(yol), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - yol.stat().st_mtime > 45 * 60:   # coken surecten kalmis eski kilit
                    yol.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.time() - bas >= bekle:
                raise TimeoutError("Baska bir yayin islemi suruyor")
            time.sleep(2)
    try:
        yield
    finally:
        try:
            yol.unlink()
        except FileNotFoundError:
            pass


def _yol(klasor):
    k = CIKTI / Path(klasor).name
    if not (k / "meta.json").exists():
        raise FileNotFoundError(klasor)
    return k


def oku(klasor):
    k = _yol(klasor)
    y = k / "yayin.json"
    try:
        return json.loads(y.read_text(encoding="utf-8"))
    except Exception:
        return {"durum": "bekliyor"}


def _yaz(klasor, veri):
    (_yol(klasor) / "yayin.json").write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return veri


def caption(klasor):
    y = oku(klasor)
    if y.get("caption"):
        return y["caption"]
    c = _yol(klasor) / "caption.txt"
    return c.read_text(encoding="utf-8") if c.exists() else ""


FORMAT_SAATI = VARSAYILAN_AYAR["saatler"]
FORMAT_HEDEF = {"post": ["ig_post", "fb_post", "ig_story"], "carousel": ["ig_carousel", "fb_carousel"],
                "reels": ["ig_reels", "fb_reels"]}


def onerilen_zaman(plan_gunu=None, tur=None):
    """Plan gunu varsa o gun, yoksa bugun; formatin saati (config 'yayin_saatleri', WAT). Gecmisse bos (= hemen)."""
    saat = (AYAR.get("yayin_saatleri") or ayar_oku().get("saatler") or FORMAT_SAATI).get(tur) if tur else None
    saat = saat or AYAR.get("yayin_saati", "18:00")
    gun = plan_gunu or simdi().date().isoformat()
    z = f"{gun}T{saat}"
    return z if datetime.fromisoformat(z).replace(tzinfo=YEREL) > simdi() else ""


def carousel_dosyalari(klasor):
    return sorted(_yol(klasor).glob("carousel_*.jpg"), key=lambda p: int(p.stem.split("_")[1]))


def varsayilan_hedefler(klasor):
    """Carousel hazirsa tek gorselli post yerine carousel paylasilir (kapak karti = post gorseli)."""
    h = list(VARSAYILAN_HEDEF)
    if len(carousel_dosyalari(klasor)) >= 2:
        h = [{"ig_post": "ig_carousel", "fb_post": "fb_carousel"}.get(x, x) for x in h]
    return h


def bekliyor_isaretle(klasor, plan_gunu=None, tur=None):
    """Uretim sonunda cagrilir. Sadece 'bekliyor' yazar - ASLA onaylamaz."""
    hedef = AYAR.get("format_hedefleri", FORMAT_HEDEF).get(tur) if tur else None
    return _yaz(klasor, {"durum": "bekliyor", "hedefler": hedef or varsayilan_hedefler(klasor),
                         "zaman": onerilen_zaman(plan_gunu, tur), "format": tur,
                         "olusturma": simdi().isoformat(timespec="minutes")})


def _planlilari_geri_cek(klasor, y):
    """Facebook'ta planlanmis (henuz yayinlanmamis) gonderileri iptal eder; sonuc kaydindan dusurur."""
    from . import meta
    for h, r in list((y.get("sonuc") or {}).items()):
        if r.get("planli") and r.get("id"):
            meta.sil(r["id"])
            y["sonuc"].pop(h)
    return y


def onayla(klasor, hedefler, zaman, metin, kaynak="ofis_ekrani"):
    """Kullanicinin ofis ekranindaki tiklamasiyla (sunucu.py) cagrilir. Planlanmis icerigi duzenlemek icin de
    kullanilir: Facebook'ta planli olanlar iptal edilip yeni saat/metinle tekrar planlanir."""
    y = oku(klasor)
    if y.get("durum") in ("yayinlaniyor", "yayinlandi", "kaldiriliyor"):
        raise ValueError("Bu icerik zaten yayinlandi/yayinlaniyor")
    y["sonuc"] = {h: r for h, r in (y.get("sonuc") or {}).items() if not r.get("kaldirildi") and r.get("id")}
    if any(r.get("id") and not r.get("planli") for r in y["sonuc"].values()):
        raise ValueError("Bu icerigin bir kismi zaten yayinda; once 'Kaldir' ya da 'Tekrar dene' kullanin")
    _planlilari_geri_cek(klasor, y)
    hedefler = [h for h in hedefler if h in HEDEFLER]
    if not hedefler:
        raise ValueError("En az bir yayin yeri secin")
    if zaman:
        datetime.fromisoformat(zaman)   # bicim kontrolu
    y.update({"durum": "onaylandi", "hedefler": hedefler, "zaman": zaman or "", "caption": metin,
              "onay": {"zaman": simdi().isoformat(timespec="seconds"), "kaynak": kaynak}})
    return _yaz(klasor, y)


def reddet(klasor):
    y = oku(klasor)
    if y.get("durum") in ("yayinlaniyor", "yayinlandi"):
        raise ValueError("Yayinlanmis icerik reddedilemez")
    y.update({"durum": "reddedildi", "red_zamani": simdi().isoformat(timespec="minutes")})
    y.pop("onay", None)
    return _yaz(klasor, y)


def geri_al(klasor):
    """Onaylanmis/planlanmis ama henuz yayinlanmamis icerigi tekrar 'bekliyor'a ceker (Facebook planlari iptal).
    Bir daha otomatik yayina girmez; kullanici isterse elle onaylar."""
    y = oku(klasor)
    if y.get("durum") == "onaylandi":
        _planlilari_geri_cek(klasor, y)
        y["durum"] = "bekliyor"
        y["otomatik_kapali"] = True
        y.pop("onay", None)
        _yaz(klasor, y)
    return y


# ---------------- otomatik yayin ----------------
def _dk(hhmm):
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


def mesai_icinde(an=None):
    a, an = ayar_oku(), an or simdi()
    return _dk(a["mesai_bas"]) <= an.hour * 60 + an.minute < _dk(a["mesai_bit"])


def mesaiye_uydur(gunluk=print):
    """Mesai bitimine 15 dk'dan yakin ya da sonrasina dusen (eski 19:00 Reels gibi) yayinlanmamis icerikleri
    formatin mesai icindeki saatine ceker. Facebook'ta planliysa iptal edilip yeni saatle tekrar planlanir."""
    a = ayar_oku()
    sinir = _dk(a["mesai_bit"]) - 15
    degisen = []
    for x in liste(80):
        y = x["yayin"]
        if y.get("durum") not in ("bekliyor", "onaylandi") or not y.get("zaman"):
            continue
        if y.get("durum") == "onaylandi" and (y.get("onay") or {}).get("kaynak") != "otomatik":
            continue      # elle verilen saate dokunma
        gun, saat = y["zaman"].split("T")
        if _dk(saat) < sinir and _dk(saat) >= _dk(a["mesai_bas"]):
            continue
        if any(r.get("id") and not r.get("planli") for r in (y.get("sonuc") or {}).values()):
            continue      # bir kismi yayinda
        yeni_saat = a["saatler"].get(y.get("format") or x["meta"].get("format") or "", "")
        if not yeni_saat or _dk(yeni_saat) >= sinir:
            yeni_saat = f"{(_dk(a['mesai_bit']) - 30) // 60:02d}:{(_dk(a['mesai_bit']) - 30) % 60:02d}"
        _planlilari_geri_cek(x["klasor"], y)
        y["sonuc"] = {h: r for h, r in (y.get("sonuc") or {}).items() if r.get("id")}
        y["zaman"] = f"{gun}T{yeni_saat}"
        _yaz(x["klasor"], y)
        degisen.append(x["klasor"])
        gunluk(f"{x['klasor']} mesai icine alindi: {saat} -> {yeni_saat}")
    return degisen


def otomatik_adaylar():
    """Otomatik onaylanabilecek icerikler: bekliyor + kalite kontrol temiz + saati ileride + elle durdurulmamis."""
    if not ayar_oku().get("otomatik"):
        return []
    out = []
    for x in liste(60):
        y, m = x["yayin"], x["meta"]
        if (y.get("durum") or "bekliyor") != "bekliyor" or y.get("otomatik_kapali") or m.get("kk_uyari"):
            continue
        z = y.get("zaman")
        if not z or datetime.fromisoformat(z).replace(tzinfo=YEREL) <= simdi():
            continue
        out.append(x["klasor"])
    return out


def otomatik_onayla(klasor):
    y = oku(klasor)
    if y.get("durum", "bekliyor") != "bekliyor":
        return y
    y.update({"durum": "onaylandi", "caption": caption(klasor),
              "onay": {"zaman": simdi().isoformat(timespec="seconds"), "kaynak": "otomatik"}})
    return _yaz(klasor, y)


def _denenebilir(plan_hata):
    """Hic denenmemis ya da hesap capinda gecici engel yuzunden planlanamamis (engel kalkinca tekrar denenir)."""
    from . import meta
    return not plan_hata or meta.engel_mi(plan_hata)


def engel_sonrasi_tekrar():
    """Meta engeli/gecersiz anahtar yuzunden yayinlanamayan OTOMATIK icerikler, saati cok gecmediyse tekrar kuyruga."""
    from . import meta
    sinir = timedelta(minutes=int(ayar_oku().get("gecikme_siniri_dk", 120)))
    for x in liste(60):
        y = x["yayin"]
        if y.get("durum") != "hata" or (y.get("onay") or {}).get("kaynak") != "otomatik" or not y.get("zaman"):
            continue
        hatalar = [r.get("hata") for r in (y.get("sonuc") or {}).values() if r.get("hata")]
        if hatalar and all(meta.engel_mi(h) for h in hatalar) and \
                datetime.fromisoformat(y["zaman"]).replace(tzinfo=YEREL) + sinir > simdi():
            y["durum"] = "onaylandi"
            y["sonuc"] = {h: r for h, r in y["sonuc"].items() if not r.get("hata")}
            _yaz(x["klasor"], y)


def meta_planlanacaklar():
    """Onayli, Facebook hedefi henuz Meta'ya planlanmamis ve saati en az 15 dk ileride olan icerikler."""
    if not ayar_oku().get("fb_meta_planla"):
        return []
    out = []
    for x in liste(60):
        y = x["yayin"]
        if y.get("durum") != "onaylandi" or not y.get("zaman"):
            continue
        if datetime.fromisoformat(y["zaman"]).replace(tzinfo=YEREL) < simdi() + timedelta(minutes=15):
            continue
        sonuc = y.get("sonuc") or {}
        # bir kez denenip planlanamayan hedef tekrar tekrar denenmez; saatinde buradan yayinlanir
        if any(h in FB_PLANLANIR and not (sonuc.get(h) or {}).get("id") and _denenebilir((sonuc.get(h) or {}).get("plan_hata"))
               for h in y.get("hedefler", [])):
            out.append(x["klasor"])
    return out


def meta_planla(klasor, gunluk=print):
    """Facebook hedeflerini Meta'nin planlayicisina gonderir. Hata olursa sorun degil: saatinde buradan yayinlanir."""
    from . import meta
    y = oku(klasor)
    if y.get("durum") != "onaylandi" or not y.get("zaman"):
        return y
    k = _yol(klasor)
    unix = datetime.fromisoformat(y["zaman"]).replace(tzinfo=YEREL).timestamp()
    metin = _hashtag_siniri(platform_metni(klasor, y, "facebook"))
    sonuc = y.setdefault("sonuc", {})
    kartlar = carousel_dosyalari(klasor)
    islem = {"fb_post": lambda: meta.fb_post(k / "post_1080x1350.jpg", metin, unix),
             "fb_carousel": lambda: meta.fb_carousel(kartlar, metin, unix),
             "fb_reels": lambda: meta.fb_reels(k / "reels_1080x1920.mp4", metin, unix)}
    for h in y.get("hedefler", []):
        if h not in FB_PLANLANIR or (sonuc.get(h) or {}).get("id") or not _denenebilir((sonuc.get(h) or {}).get("plan_hata")):
            continue
        try:
            gunluk(f"{HEDEFLER[h]} Meta'da planlaniyor ({y['zaman'].replace('T', ' ')} {musteri.KISALTMA})...")
            r = islem[h]()
            sonuc[h] = {**r, "planli": True, "plan_zamani": y["zaman"]}
        except Exception as e:
            sonuc[h] = {"plan_hata": f"{type(e).__name__}: {e}"[:300]}
            gunluk(f"{HEDEFLER[h]} planlanamadi, saatinde buradan yayinlanacak: {e}")
    guncel = oku(klasor)
    if guncel.get("durum") != "onaylandi":     # bu arada kullanici geri aldi/kaldirdi -> planlari geri cek
        y["durum"] = guncel.get("durum")
        _planlilari_geri_cek(klasor, y)
        return _yaz(klasor, {**guncel, "sonuc": y.get("sonuc", {})})
    return _yaz(klasor, y)


def kacirilanlari_isaretle():
    """Bilgisayar kapali kaldigi icin saati cok gecmis OTOMATIK icerikler yayinlanmaz; kullaniciya birakilir."""
    sinir = timedelta(minutes=int(ayar_oku().get("gecikme_siniri_dk", 120)))
    out = []
    for x in liste(60):
        y = x["yayin"]
        if y.get("durum") != "onaylandi" or (y.get("onay") or {}).get("kaynak") != "otomatik" or not y.get("zaman"):
            continue
        if datetime.fromisoformat(y["zaman"]).replace(tzinfo=YEREL) + sinir < simdi():
            bekleyen = [h for h in y["hedefler"] if not (y.get("sonuc", {}).get(h) or {}).get("id")]
            if bekleyen:
                y.update({"durum": "kacirildi", "kacirilan": bekleyen})
                _yaz(x["klasor"], y)
                out.append(x["klasor"])
    return out


def kaldir(klasor):
    """KULLANICI ISTEGI: icerigi yayindan kaldirir. Planli Facebook gonderileri iptal edilir, yayinlanmis
    Facebook/Instagram gonderileri Meta'dan silinir. Henuz hicbir yere gitmemisse sadece iptal edilir."""
    from . import meta
    y = oku(klasor)
    sonuc = y.get("sonuc") or {}
    hatalar = []
    for h, r in sonuc.items():
        if not r.get("id") or r.get("kaldirildi"):
            continue
        try:
            meta.sil(r["id"])
            r["kaldirildi"] = simdi().isoformat(timespec="minutes")
            r.pop("kaldir_hata", None)
        except Exception as e:
            r["kaldir_hata"] = f"{type(e).__name__}: {e}"[:300]
            hatalar.append(f"{HEDEFLER.get(h, h)}: {e}")
    y.pop("onay", None)
    y.update({"sonuc": sonuc, "otomatik_kapali": True, "kaldirma_zamani": simdi().isoformat(timespec="minutes"),
              "durum": "kaldirma_hatasi" if hatalar else "kaldirildi"})
    _yaz(klasor, y)
    if hatalar:
        raise RuntimeError("Bazi yerlerden kaldirilamadi: " + " | ".join(hatalar)[:400])
    return y


def revize_iste(klasor, secenekler, not_metni):
    """Kullanici Onay kartindan revizyon istedi. Icerik yayinlanmaz; ajanlar yeni bir versiyon uretir."""
    y = oku(klasor)
    if y.get("durum") == "onaylandi":
        raise ValueError("Önce onayı geri alın, sonra revize isteyin")
    if y.get("durum") not in ("bekliyor", "reddedildi", "hata", None):
        raise ValueError("Bu içerik revize edilemez (" + str(y.get("durum")) + ")")
    not_metni = str(not_metni or "").strip()[:500]
    if not secenekler and not not_metni:
        raise ValueError("Bir seçenek işaretleyin ya da not yazın")
    y.pop("onay", None)
    y.update({"durum": "revize_isteniyor", "onceki_durum": y.get("durum") or "bekliyor",
              "revize": {"secenekler": list(secenekler), "not": not_metni,
                         "zaman": simdi().isoformat(timespec="minutes")}})
    return _yaz(klasor, y)


def revize_tamam(eski, yeni):
    y = oku(eski)
    y.update({"durum": "revize_edildi", "yeni_versiyon": Path(yeni).name})
    _yaz(eski, y)


def revize_hata(eski, mesaj):
    y = oku(eski)
    y["durum"] = y.pop("onceki_durum", "bekliyor")
    y["revize_hata"] = str(mesaj)[:300]
    _yaz(eski, y)


def liste(n=30):
    if not CIKTI.exists():
        return []
    out = []
    for k in sorted([d for d in CIKTI.iterdir() if d.is_dir() and (d / "meta.json").exists()], reverse=True)[:n]:
        meta = json.loads((k / "meta.json").read_text(encoding="utf-8"))
        mz = json.loads((k / "muzik.json").read_text(encoding="utf-8")) if (k / "muzik.json").exists() else None
        out.append({"klasor": k.name, "meta": meta, "yayin": oku(k.name), "caption": caption(k.name), "muzik": mz,
                    "dosyalar": sorted(f.name for f in k.iterdir() if f.suffix in (".jpg", ".mp4"))})
    sira = {"revize_isteniyor": 0, "bekliyor": 0, "kacirildi": 0, "kaldirma_hatasi": 0, "onaylandi": 1,
            "yayinlaniyor": 1, "hata": 2, "kismen": 2, "yayinlandi": 3, "reddedildi": 4, "kaldirildi": 4,
            "revize_edildi": 5}
    return sorted(out, key=lambda x: sira.get(x["yayin"].get("durum"), 5))


def zamani_gelenler():
    out = []
    for x in liste(60):
        y = x["yayin"]
        if y.get("durum") == "onaylandi" and y.get("onay"):
            z = y.get("zaman")
            if not z or datetime.fromisoformat(z).replace(tzinfo=YEREL) <= simdi():
                out.append(x["klasor"])
    return out


def platform_metni(klasor, y, platform):
    """Facebook icin Facebook uzmaninin metni; kullanici panelde metni degistirdiyse onunki her yerde gecerli."""
    from . import platformlar
    taban = caption(klasor)
    kullanici = (y.get("caption") or "").strip()
    c_dosya = _yol(klasor) / "caption.txt"
    orijinal = c_dosya.read_text(encoding="utf-8").strip() if c_dosya.exists() else ""
    if kullanici and " ".join(kullanici.split()) != " ".join(orijinal.split()):
        return kullanici
    return platformlar.metin(_yol(klasor), platform) or taban


def _hashtag_siniri(metin, en_fazla=30):
    kelimeler, sayac = [], 0
    for k in metin.split(" "):
        if k.startswith("#"):
            sayac += 1
            if sayac > en_fazla:
                continue
        kelimeler.append(k)
    return " ".join(kelimeler)[:2200]


def yayinla(klasor, gunluk=print):
    """Onayli (elle ya da otomatik yayin ayariyla) icerigi secilen yerlere yayinlar. Onay yoksa REDDEDER.
    Facebook'ta zaten planlanmis hedefler atlanir (Meta saatinde kendisi yayinlar)."""
    from . import meta
    y = oku(klasor)
    if y.get("durum") != "onaylandi" or not (y.get("onay") or {}).get("zaman"):
        raise PermissionError("Bu icerik kullanici tarafindan onaylanmadi; yayinlanmayacak.")
    if not meta.bagli():
        raise RuntimeError("Meta baglantisi yok (Onay sekmesinden baglanin)")
    k = _yol(klasor)
    dosya = {"post": k / "post_1080x1350.jpg", "story": k / "story_1080x1920.jpg", "reels": k / "reels_1080x1920.mp4"}
    kartlar = carousel_dosyalari(klasor)
    metin = _hashtag_siniri(y.get("caption") or caption(klasor))
    fb_metin = _hashtag_siniri(platform_metni(klasor, y, "facebook"))
    y["durum"] = "yayinlaniyor"
    _yaz(klasor, y)
    sonuc = y.get("sonuc", {})
    islem = {"ig_post": lambda: meta.ig_post(dosya["post"], metin),
             "ig_story": lambda: meta.ig_story(dosya["story"]),
             "ig_reels": lambda: meta.ig_reels(dosya["reels"], metin, deneme=deneme_mi(klasor)),
             "fb_post": lambda: meta.fb_post(dosya["post"], fb_metin),
             "fb_story": lambda: meta.fb_story(dosya["story"]),
             "fb_reels": lambda: meta.fb_reels(dosya["reels"], fb_metin),
             "ig_carousel": lambda: meta.ig_carousel(kartlar, metin),
             "fb_carousel": lambda: meta.fb_carousel(kartlar, fb_metin)}
    for h in y["hedefler"]:
        if sonuc.get(h, {}).get("id"):
            continue    # daha once basariyla yayinlanmis / Facebook'ta planli
        if oku(klasor).get("durum") in ("kaldiriliyor", "kaldirildi", "bekliyor"):
            gunluk("Kullanici yayini durdurdu, kalan hedefler atlaniyor")
            break
        tur = h.split("_")[1]
        if tur == "carousel":
            if len(kartlar) < 2:
                sonuc[h] = {"hata": "Carousel kartlari bulunamadi"}
                continue
        elif not dosya[tur].exists():
            sonuc[h] = {"hata": f"{dosya[tur].name} bulunamadi"}
            continue
        if h.startswith("ig_") and not meta.ayar().get("ig_id"):
            sonuc[h] = {"hata": "Facebook sayfasina bagli Instagram Business hesabi yok"}
            continue
        try:
            gunluk(f"{HEDEFLER[h]} yayinlaniyor...")
            r = islem[h]()
            sonuc[h] = {**r, "zaman": simdi().isoformat(timespec="minutes")}
            if h == "ig_reels" and deneme_mi(klasor):
                sonuc[h]["deneme"] = True
            gunluk(f"{HEDEFLER[h]} yayinlandi ✅")
        except Exception as e:
            sonuc[h] = {"hata": f"{type(e).__name__}: {e}"}
            gunluk(f"{HEDEFLER[h]} HATA: {e}")
    basarili = [h for h in y["hedefler"] if sonuc.get(h, {}).get("id")]
    y["sonuc"] = sonuc
    guncel = oku(klasor)
    if guncel.get("durum") in ("kaldiriliyor", "kaldirildi", "bekliyor"):   # yayin sirasinda kullanici kaldir dedi
        y["durum"] = "kaldiriliyor"
        return _yaz(klasor, y)
    y["durum"] = "yayinlandi" if len(basarili) == len(y["hedefler"]) else ("kismen" if basarili else "hata")
    y["yayin_zamani"] = simdi().isoformat(timespec="minutes")
    return _yaz(klasor, y)


def deneme_mi(klasor):
    """Instagram Deneme Reels'i olarak mi paylasilsin? (ofis_ayar 'deneme_reels')
    yeni_formatlar: daha once 2'den az yayinlanmis bir Reels formatiysa deneme olarak paylas."""
    from . import ofis_ayar
    mod = ofis_ayar.oku().get("deneme_reels", "yeni_formatlar")
    if mod == "kapali":
        return False
    if mod == "hepsi":
        return True
    try:
        rf = json.loads((_yol(klasor) / "meta.json").read_text(encoding="utf-8")).get("reels_format")
    except Exception:
        return False
    if not rf:
        return False
    n = 0
    for p in CIKTI.glob("*/meta.json"):
        if p.parent.name == Path(klasor).name:
            continue
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("reels_format") == rf and \
                    json.loads((p.parent / "yayin.json").read_text(encoding="utf-8")).get("durum") in ("yayinlandi", "kismen"):
                n += 1
        except Exception:
            continue
    return n < 2


def tekrar_dene(klasor):
    """Kismen/hata/kacirildi durumundaki icerigi, ONCEKI onayi koruyarak tekrar kuyruga alir (kullanici tiklamasiyla)."""
    y = oku(klasor)
    if y.get("durum") == "kaldirma_hatasi":
        return kaldir(klasor)
    if y.get("durum") in ("kismen", "hata", "kacirildi") and y.get("onay"):
        y["durum"] = "onaylandi"
        y["zaman"] = ""
        _yaz(klasor, y)
    return y


IG_TUR = {"ig_post": "post", "ig_carousel": "post", "ig_reels": "reels", "ig_story": "story"}
FB_HEDEF = ("fb_post", "fb_carousel", "fb_reels")


def istatistikleri_guncelle(gun=21, gunluk=print):
    """Yayinlanmis iceriklerin Instagram + Facebook rakamlarini ceker -> performans.json (elle girilen
    yildizlara dokunmaz). Facebook'ta planli olup saati gecenlerin yayina girdigini de dogrular."""
    from . import analiz, meta
    if not meta.bagli():
        return 0
    say = 0
    for x in liste(120):
        y = x["yayin"]
        if y.get("durum") not in ("yayinlandi", "kismen", "onaylandi") or not y.get("sonuc"):
            continue
        z = y.get("yayin_zamani") or y.get("zaman")
        if z and datetime.fromisoformat(z).replace(tzinfo=YEREL) < simdi() - timedelta(days=gun):
            continue
        degisti = False
        for h, r in y["sonuc"].items():      # planli Facebook gonderisi saatinde yayina girdi mi?
            if r.get("planli") and r.get("id") and r.get("plan_zamani") and \
                    datetime.fromisoformat(r["plan_zamani"]).replace(tzinfo=YEREL) < simdi() - timedelta(minutes=5):
                if meta.yayinda_mi(r["id"]) is not False:
                    r["planli"] = False
                    r["zaman"] = r["plan_zamani"]
                    degisti = True
        if degisti:
            _yaz(x["klasor"], y)
        toplam, ham = {}, {}
        for h, r in y["sonuc"].items():
            mid = r.get("id")
            if not mid or r.get("planli") or r.get("kaldirildi"):
                continue
            try:
                if h in IG_TUR:
                    if h == "ig_story" and r.get("zaman") and \
                            datetime.fromisoformat(r["zaman"]).replace(tzinfo=YEREL) < simdi() - timedelta(hours=24):
                        continue    # story 24 saatte kaybolur; rakami o surede alinir
                    m = meta.ig_istatistik(mid, IG_TUR[h])
                elif h in FB_HEDEF:
                    m = meta.fb_ozet(mid)
                else:
                    continue
            except Exception as e:
                gunluk(f"{x['klasor']} {h} istatistik alinamadi: {e}")
                continue
            ham[h] = m
            for a, b in (("goruntulenme", "views"), ("begeni", "likes"), ("kaydetme", "saved"), ("paylasim", "shares"),
                         ("yorum", "comments")):
                deger = m.get(b) if b != "views" else (m.get("views") or m.get("reach"))
                if deger is not None:
                    toplam[a] = toplam.get(a, 0) + int(deger)
        if toplam:
            analiz.performans_kaydet(x["klasor"], {k: str(v) for k, v in toplam.items()})
            p = CIKTI / x["klasor"] / "performans.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            eski_ham = d.get("meta_ham") or {}
            d["meta_ham"] = {**eski_ham, **ham}      # kaybolan story rakami korunur
            d["meta_guncelleme"] = simdi().isoformat(timespec="minutes")
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            say += 1
    try:
        hesap_kaydet(meta.hesap_ozeti())
    except Exception as e:
        gunluk(f"Hesap ozeti alinamadi: {e}")
    return say


HESAP = VERI / "hesap_gecmisi.json"


def pasifik_wat_farki(gun=None):
    """Musterinin yerel saati ile ABD Pasifik saati arasindaki fark (saat). Pasifik: PDT (UTC-7, Mart 2. pazar -
    Kasim 1. pazar), PST (UTC-8). Ornek: Lagos (UTC+1) -> yazin 8, kisin 9."""
    from datetime import date, datetime as _dt
    g = gun or simdi().date()
    def pazar(yil, ay, kacinci):
        d = date(yil, ay, 1)
        ilk = d + timedelta(days=(6 - d.weekday()) % 7)
        return ilk + timedelta(weeks=kacinci - 1)
    pasifik = -7 if pazar(g.year, 3, 2) <= g < pazar(g.year, 11, 1) else -8
    yerel = musteri.ofset_saat(_dt(g.year, g.month, g.day, 12, tzinfo=YEREL))
    return int(round(yerel - pasifik))


def hesap_kaydet(o):
    """Gunde bir satir: takipci sayilari + IG gunluk erisim; son gun saatlik cevrimici takipci dagilimi."""
    if not o:
        return
    try:
        d = json.loads(HESAP.read_text(encoding="utf-8"))
    except Exception:
        d = {"gunler": {}}
    gun = simdi().date().isoformat()
    saatlik = o.pop("ig_cevrimici_saat", None)
    if saatlik:      # Meta bu metrigi Pasifik saatiyle (PST/PDT) verir -> musterinin yerel saatine cevir
        fark = pasifik_wat_farki()
        wat = {}
        for k, n in saatlik.items():
            h = (int(k) + fark) % 24
            wat[str(h)] = wat.get(str(h), 0) + n
        saatlik = wat
    d["gunler"][gun] = {**d["gunler"].get(gun, {}), **{k: v for k, v in o.items() if v is not None}}
    if saatlik:
        d["cevrimici_saat"] = saatlik
    d["gunler"] = dict(sorted(d["gunler"].items())[-120:])
    HESAP.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def hesap_gecmisi():
    try:
        return json.loads(HESAP.read_text(encoding="utf-8"))
    except Exception:
        return {"gunler": {}}
