"""Cloud Scheduler her 10 dakikada bir /ic/zamanlayici'yi cagirir. Burada her aktif musteri icin:
  - deneme suresi bittiyse ve odeme yoksa hesap duraklatilir
  - mesai icindeyse bir 'yayin_turu' isi (saati gelen icerik, Meta planlama, rakamlar, yorum raporu)
  - gunun uretim saati geldiyse ve bugun uretilmediyse bir 'uret' isi
Sonra isci bir kez uyandirilir. Her sey musterinin kendi saat diliminde hesaplanir."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import kuyruk
from .depo import depo


def _tz(m):
    i = (m.get("profil") or {}).get("isletme") or {}
    try:
        return ZoneInfo(i.get("saat_dilimi") or "UTC")
    except Exception:
        return timezone.utc


def _dk(hhmm):
    h, d = str(hhmm).split(":")
    return int(h) * 60 + int(d)


def tur(an_utc=None, tetikle=True):
    d = depo()
    an_utc = an_utc or datetime.now(timezone.utc)
    rapor = {"duraklatilan": [], "yayin_turu": [], "uret": []}
    for m in d.musteriler(["deneme", "aktif"]):
        if m["durum"] == "deneme" and m.get("deneme_bitis") and \
                datetime.fromisoformat(str(m["deneme_bitis"]).replace("Z", "+00:00")) < an_utc:
            d.musteri_guncelle(m["id"], durum="duraklatildi")
            rapor["duraklatilan"].append(m["id"])
            continue
        if not m.get("meta_token") and not (m.get("yayin_ayar") or {}).get("baglantisiz_uret"):
            continue                    # Meta baglanmadan ne yayin ne uretim (bos yere maliyet olmasin)
        yerel = an_utc.astimezone(_tz(m))
        i = (m.get("profil") or {}).get("isletme") or {}
        ya = m.get("yayin_ayar") or {}
        bas, bit = _dk(ya.get("mesai_bas") or i.get("mesai_bas") or "08:00"), \
            _dk(ya.get("mesai_bit") or i.get("mesai_bit") or "19:00")
        simdi = yerel.hour * 60 + yerel.minute
        if bas <= simdi < bit:
            kuyruk.is_ekle(m["id"], "yayin_turu", {}, tetikle=False)
            rapor["yayin_turu"].append(m["id"])
        uretim = _dk(ya.get("uretim_saati") or "08:00")
        bugun_hata = sum(1 for x in d.isler(m["id"], 30) if x["tur"] == "uret" and x["durum"] == "hata"
                         and str(x.get("olusturma", ""))[:10] == an_utc.date().isoformat())
        if simdi >= uretim and simdi < bit and str(m.get("son_uretim") or "") != yerel.date().isoformat() \
                and bugun_hata < 2:          # iki kez basarisizsa gun boyu tekrar deneyip maliyet cikarmasin
            kuyruk.is_ekle(m["id"], "uret", {"plansiz": False}, tetikle=False)
            rapor["uret"].append(m["id"])
    if tetikle and (rapor["yayin_turu"] or rapor["uret"]):
        rapor["isci"] = kuyruk.isciyi_uyandir()
    return rapor
