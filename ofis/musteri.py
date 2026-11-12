"""Musteriye (isletmeye) ozel metinler ve saat dilimi.

Ajanlarin istemlerine eskiden 'furniture showroom in Nigeria' gibi sabitler gomuluydu; artik hepsi
profil.json'daki "isletme" bolumunden uretilir. Yeni bir sektor = yeni bir profil, kod degismez.
"""
from datetime import datetime, timedelta, timezone

from .ayarlar import AYAR

VARSAYILAN = {
    "ad": "Your Brand",
    "sektor": "retail",
    "tanim": "a local business",              # "a premium furniture showroom" gibi, a/an ile
    "urun_turu": "products",
    "ulke": "",
    "sehirler": [],
    "online_satis": False,
    "satis_kanali": "Sales happen in the store or by phone/DM, never online.",
    "yonlendirme": "visit our store or send us a DM",
    "hashtagler": [],
    "proje_hashtagler": [],
    "carousel_maddeleri": ["See it in our store", "Order by phone or DM", "Friendly advice from our team"],
    "proje_carousel_maddeleri": ["Designed for this space", "Made by our team", "Visit our store"],
    "faydalar": ["Quality you can feel", "Made for everyday life", "See it in our store today"],
    "yasak_ifadeler": ["buy online", "order online", "add to cart", "checkout", "free delivery",
                       "shop now online", "click to buy"],
    "saat_dilimi": "UTC",
    "utc_ofset_saat": 0,
    "saat_kisaltma": "UTC",
}


def bilgi():
    return {**VARSAYILAN, **(AYAR.get("isletme") or {})}


def ad():
    return bilgi()["ad"] or AYAR.get("marka", {}).get("ad", "")


def yer():
    """'in Nigeria' / '' """
    u = bilgi()["ulke"]
    return f" in {u}" if u else ""


def tanim():
    """'a premium furniture showroom in Nigeria'"""
    return bilgi()["tanim"] + yer()


def sehirler_metni():
    s = bilgi()["sehirler"]
    return "/".join(s) if s else (bilgi()["ulke"] or "the local area")


def satis_kanali():
    return bilgi()["satis_kanali"]


def yasak_ifadeler():
    b = bilgi()
    return [] if b["online_satis"] else [x.lower() for x in b["yasak_ifadeler"]]


def hashtagler(proje=False):
    b = bilgi()
    return list((b["proje_hashtagler"] or b["hashtagler"]) if proje else b["hashtagler"])


def carousel_maddeleri(proje=False):
    b = bilgi()
    return list(b["proje_carousel_maddeleri"] if proje else b["carousel_maddeleri"])


def faydalar():
    return list(bilgi()["faydalar"])


# ---- saat dilimi --------------------------------------------------------
def _tz():
    b = bilgi()
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(b["saat_dilimi"])
    except Exception:
        # Windows'ta tzdata yoksa sabit ofsete duseriz (Nijerya gibi yaz saati olmayan yerlerde ayni sonuc).
        return timezone(timedelta(hours=float(b["utc_ofset_saat"])), b["saat_kisaltma"])


YEREL = _tz()
KISALTMA = bilgi()["saat_kisaltma"]


def simdi():
    return datetime.now(YEREL)


def ofset_saat(an=None):
    an = an or simdi()
    return (an.utcoffset() or timedelta()).total_seconds() / 3600
