"""Meta (Facebook Login) ile hesap baglama. Tek Meta uygulamasi; her musteri kendi sayfasini baglar.

Akis: panel -> /api/musteri/<id>/meta/baglan -> Facebook izin ekrani -> /meta/geri?code&state
      -> kod uzun omurlu kullanici anahtarina cevrilir -> yonetilen sayfalar (+ bagli Instagram) listelenir
      -> musteri panelde sayfayi secer -> sayfa anahtari SIFRELI saklanir.
Uzun omurlu kullanici anahtarindan alinan sayfa anahtarlarinin suresi dolmaz (sifre degisimi / izin
geri alinmasi haric); isci her iste sifresini cozup yalnizca o musterinin gecici klasorune yazar.
"""
from urllib.parse import urlencode

import requests

from . import ayar, guvenlik


class MetaBaglantiHatasi(Exception):
    pass


def donus_adresi():
    return f"{ayar.GENEL_ADRES}/meta/geri"


def izin_adresi(mid, kullanici_id):
    if not ayar.META_APP_ID:
        raise MetaBaglantiHatasi("META_APP_ID tanimli degil")
    state = guvenlik.imzala({"mid": mid, "uid": kullanici_id})
    return f"{ayar.META_DIALOG}/{ayar.META_VERSIYON}/dialog/oauth?" + urlencode({
        "client_id": ayar.META_APP_ID, "redirect_uri": donus_adresi(), "state": state,
        "scope": ayar.META_IZINLER, "response_type": "code"})


def _get(yol, http=None, **p):
    r = (http or requests).get(f"{ayar.META_GRAPH}/{ayar.META_VERSIYON}/{yol}", params=p, timeout=30)
    try:
        j = r.json()
    except ValueError:
        raise MetaBaglantiHatasi(f"Meta HTTP {r.status_code}")
    if r.status_code >= 400 or "error" in j:
        e = j.get("error") or {}
        raise MetaBaglantiHatasi(f"{e.get('message', 'Meta hatasi')} (kod {e.get('code')})")
    return j


def kodu_coz(code, http=None):
    """Izin kodu -> uzun omurlu kullanici anahtari -> sayfa listesi (anahtarlariyla)."""
    kisa = _get("oauth/access_token", http, client_id=ayar.META_APP_ID, client_secret=ayar.META_APP_SECRET,
                redirect_uri=donus_adresi(), code=code)["access_token"]
    uzun = _get("oauth/access_token", http, grant_type="fb_exchange_token", client_id=ayar.META_APP_ID,
                client_secret=ayar.META_APP_SECRET, fb_exchange_token=kisa)["access_token"]
    sayfalar = _get("me/accounts", http, access_token=uzun, limit=100,
                    fields="id,name,access_token,tasks,instagram_business_account{id,username}").get("data", [])
    out = []
    for s in sayfalar:
        if s.get("tasks") and not ({"CREATE_CONTENT", "MANAGE"} & set(s["tasks"])):
            continue          # paylasim yetkisi olmayan sayfa
        ig = s.get("instagram_business_account") or {}
        out.append({"page_id": s["id"], "page_ad": s.get("name"), "page_token": s["access_token"],
                    "ig_id": ig.get("id"), "ig_kullanici": ig.get("username")})
    if not out:
        raise MetaBaglantiHatasi("Paylasim yetkiniz olan bir Facebook sayfasi bulunamadi")
    return out


def herkese_acik(s):
    """Panelde gosterilecek kisim: anahtar YOK."""
    return {"page_id": s["page_id"], "page_ad": s.get("page_ad"), "ig_id": s.get("ig_id"),
            "ig_kullanici": s.get("ig_kullanici")}
