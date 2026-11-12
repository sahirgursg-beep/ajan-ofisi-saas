"""Panelden gelen yayin kararlari (onayla, reddet, geri al, kaldir, revize, tekrar dene).

Kurallar ofis/yayin.py ile aynidir; tek fark, web sureci Meta'ya istek ATMAZ:
- Facebook'ta planli bir gonderinin iptali gerekiyorsa kimligi 'bekleyen_iptal' listesine yazilir;
  isci bir sonraki turda Meta'dan siler.
- Yayindaki icerigi kaldirmak isci isidir ('kaldir' isi).
Boylece panel tiklamasi aninda cevap verir, Meta hatalari iscide yakalanir ve kayda gecer.
"""
from datetime import datetime

HEDEFLER = {"ig_post": "Instagram Post", "ig_carousel": "Instagram Carousel", "ig_story": "Instagram Story",
            "ig_reels": "Instagram Reels", "fb_post": "Facebook Post", "fb_carousel": "Facebook Carousel",
            "fb_story": "Facebook Story", "fb_reels": "Facebook Reels"}
YAYINDA = ("yayinlaniyor", "yayinlandi", "kaldiriliyor")


class KararHatasi(ValueError):
    pass


def _simdi(tz):
    return datetime.now(tz).isoformat(timespec="seconds")


def _planlilari_iptale_al(y):
    iptal = list(y.get("bekleyen_iptal") or [])
    for h, r in list((y.get("sonuc") or {}).items()):
        if r.get("planli") and r.get("id"):
            iptal.append(r["id"])
            y["sonuc"].pop(h)
    if iptal:
        y["bekleyen_iptal"] = sorted(set(iptal))
    return bool(iptal)


def onayla(yayin, hedefler, zaman, metin, tz, kaynak="panel"):
    y = dict(yayin or {})
    if y.get("durum") in YAYINDA:
        raise KararHatasi("This content is already published or publishing")
    y["sonuc"] = {h: r for h, r in (y.get("sonuc") or {}).items() if not r.get("kaldirildi") and r.get("id")}
    if any(r.get("id") and not r.get("planli") for r in y["sonuc"].values()):
        raise KararHatasi("Part of this content is already live; use Remove or Retry first")
    _planlilari_iptale_al(y)
    hedefler = [h for h in (hedefler or []) if h in HEDEFLER]
    if not hedefler:
        raise KararHatasi("Choose at least one destination")
    if zaman:
        try:
            datetime.fromisoformat(zaman)
        except ValueError:
            raise KararHatasi("Time must be YYYY-MM-DDTHH:MM")
    if not str(metin or "").strip():
        raise KararHatasi("Caption cannot be empty")
    y.update({"durum": "onaylandi", "hedefler": hedefler, "zaman": zaman or "", "caption": str(metin)[:2200],
              "onay": {"zaman": _simdi(tz), "kaynak": kaynak}})
    y.pop("otomatik_kapali", None)
    return y


def reddet(yayin, tz):
    y = dict(yayin or {})
    if y.get("durum") in ("yayinlaniyor", "yayinlandi"):
        raise KararHatasi("Published content cannot be rejected")
    _planlilari_iptale_al(y)
    y.update({"durum": "reddedildi", "red_zamani": _simdi(tz)})
    y.pop("onay", None)
    return y


def geri_al(yayin, tz):
    y = dict(yayin or {})
    if y.get("durum") == "onaylandi":
        _planlilari_iptale_al(y)
        y.update({"durum": "bekliyor", "otomatik_kapali": True})
        y.pop("onay", None)
    return y


def kaldir_istegi(yayin, tz):
    """Yayindaki/planli icerigi kaldirma istegi: durum 'kaldiriliyor', isi isci yapar."""
    y = dict(yayin or {})
    if not any(r.get("id") and not r.get("kaldirildi") for r in (y.get("sonuc") or {}).values()):
        # Meta'da hicbir sey yok: yerinde iptal
        y.update({"durum": "kaldirildi", "otomatik_kapali": True, "kaldirma_zamani": _simdi(tz)})
        y.pop("onay", None)
        return y, False
    y.update({"durum": "kaldiriliyor", "otomatik_kapali": True})
    y.pop("onay", None)
    return y, True


def revize_iste(yayin, secenekler, not_metni, tz):
    y = dict(yayin or {})
    if y.get("durum") == "onaylandi":
        raise KararHatasi("Put it on hold first, then request changes")
    if y.get("durum") not in ("bekliyor", "reddedildi", "hata", None):
        raise KararHatasi(f"This content cannot be revised ({y.get('durum')})")
    not_metni = str(not_metni or "").strip()[:500]
    if not secenekler and not not_metni:
        raise KararHatasi("Tick an option or write a note")
    y.pop("onay", None)
    y.update({"durum": "revize_isteniyor", "onceki_durum": y.get("durum") or "bekliyor",
              "revize": {"secenekler": list(secenekler or [])[:8], "not": not_metni, "zaman": _simdi(tz)}})
    return y


def tekrar_dene(yayin):
    """-> (yeni yayin, gereken is turu ya da None)"""
    y = dict(yayin or {})
    if y.get("durum") == "kaldirma_hatasi":
        y["durum"] = "kaldiriliyor"
        return y, "kaldir"
    if y.get("durum") in ("kismen", "hata", "kacirildi") and y.get("onay"):
        y.update({"durum": "onaylandi", "zaman": ""})
        return y, "yayin_turu"
    return y, None
