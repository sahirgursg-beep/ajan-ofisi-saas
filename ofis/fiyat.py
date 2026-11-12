"""Fiyat hesabi - KASITLI OLARAK LLM KULLANMAZ. Sayi isi kodla yapilir.

Musterinin para birimi profil.json'dan gelir:
  "para_birimi": "NGN", "para_sembolu": "₦", "site_para_birimi": "USD",
  "doviz_kurlari": {"USD": 1500}, "yuvarlama": 1000
Site fiyati zaten yerel para birimindeyse kur uygulanmaz.
Not: urun sozlugundeki "ngn" alani tarihsel addir; anlami "yerel para birimindeki tutar"dir ("tutar" ile ayni).
"""
import re

from .ayarlar import AYAR


def _kod(pb):
    pb = (pb or "").upper().strip()
    return {"$": "USD", "US$": "USD", "€": "EUR", "£": "GBP", "₦": "NGN"}.get(pb, pb)


def yerel_para():
    return _kod(AYAR.get("para_birimi") or "NGN")


def kur(kaynak):
    """1 birim 'kaynak' kac birim yerel para eder."""
    kaynak = _kod(kaynak)
    if kaynak == yerel_para():
        return 1.0
    kurlar = {_kod(k): float(v) for k, v in (AYAR.get("doviz_kurlari") or {}).items()}
    if kaynak not in kurlar:
        raise ValueError(f"{kaynak}->{yerel_para()} kuru profilde yok (doviz_kurlari)")
    return kurlar[kaynak]


def yerel_fiyat(fiyat, para_birimi=None):
    """Sitedeki fiyati musterinin para birimine cevirir ve yuvarlar. Sayi (int) doner."""
    if fiyat is None:
        return None
    pb = para_birimi or AYAR.get("site_para_birimi") or yerel_para()
    deger = float(fiyat) * kur(pb)
    adim = AYAR.get("yuvarlama", 1) or 1
    return int(round(deger / adim) * adim)


naira = yerel_fiyat      # eski ad


def bicimle(tutar):
    if tutar is None:
        return ""
    return f"{AYAR.get('para_sembolu') or yerel_para() + ' '}{tutar:,.0f}"


def fiyat_deseni():
    """Metindeki fiyatlari yakalayan desen: sembol ya da kod + sayi (or. '₦250,000', 'NGN 250,000')."""
    isaretler = {re.escape(AYAR.get("para_sembolu", "").strip()), re.escape(yerel_para())}
    isaretler |= {re.escape(x) for x in AYAR.get("ek_fiyat_isaretleri", [])}   # or. Nijerya'da "N250,000"
    isaretler -= {""}
    return r"(?:" + "|".join(sorted(isaretler, key=len, reverse=True)) + r")\s?([\d,]{4,})"


def hazirla(u):
    """Urune ngn/tutar, fiyat_metni, eski_fiyat_metni, indirim_yuzde alanlarini ekler."""
    u["ngn"] = u["tutar"] = yerel_fiyat(u["fiyat"], u.get("para_birimi"))
    u["fiyat_metni"] = bicimle(u["ngn"])
    eski = u.get("eski_fiyat")
    if eski and AYAR.get("fiyat_gosterimi", "indirimli") == "indirimli":
        u["eski_ngn"] = yerel_fiyat(eski, u.get("para_birimi"))
        u["eski_fiyat_metni"] = bicimle(u["eski_ngn"])
        u["indirim_yuzde"] = round(100 * (1 - u["fiyat"] / eski))
    else:
        u["eski_ngn"] = None
        u["eski_fiyat_metni"] = ""
        u["indirim_yuzde"] = 0
    return u
