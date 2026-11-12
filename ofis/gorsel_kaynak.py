"""Gorsel kaynaklari: urun fotografi olmayan isletmeler icin.

  stok        -> Pixabay (PIXABAY_API_KEY, ucretsiz, atif gerekmez) ya da Pexels (PEXELS_API_KEY, eski anahtarlar)
  yapay_zeka  -> OpenAI uyumlu gorsel uretimi (varsayilan DigitalOcean Serverless Inference, openai-gpt-image-1)
Indirilen/uretilen gorseller veri/gorsel_onbellek'e yazilir, yerel dosya yolu doner.
Insan yuzu gerektirmeyen, markaya ozel kompozisyonlar yapay zekayla; gercekci mekan/insan sahneleri stoktan.
"""
import base64
import hashlib
import os

import requests

from .ayarlar import VERI

ONBELLEK = VERI / "gorsel_onbellek"
PEXELS = "https://api.pexels.com/v1/search"
PIXABAY = "https://pixabay.com/api/"


def _yol(anahtar, uzanti):
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    return ONBELLEK / (hashlib.md5(anahtar.encode()).hexdigest() + uzanti)


def _anahtar(ad):
    return os.environ.get(ad, "").strip()


def stok_hazir():
    return bool(_anahtar("PIXABAY_API_KEY") or _anahtar("PEXELS_API_KEY"))


def yz_hazir():
    return bool(os.environ.get("AJAN_YZ_ANAHTAR", "").strip()) and os.environ.get("AJAN_GORSEL_URET", "1") != "0"


def _indir(http, adres):
    yol = _yol(adres, ".jpg")
    if not yol.exists():
        g = http.get(adres, timeout=60)
        g.raise_for_status()
        yol.write_bytes(g.content)
    return str(yol)


def _pixabay(sorgu, adet, yon, haric, http):
    r = http.get(PIXABAY, timeout=30, params={
        "key": _anahtar("PIXABAY_API_KEY"), "q": sorgu[:100], "image_type": "photo", "safesearch": "true",
        "orientation": "vertical" if yon == "portrait" else "horizontal" if yon == "landscape" else "all",
        "per_page": 20, "order": "popular"})
    r.raise_for_status()
    out = []
    for f in r.json().get("hits", []):
        if str(f.get("id")) in haric or not f.get("largeImageURL"):
            continue
        out.append((_indir(http, f["largeImageURL"]), {"kaynak": "pixabay", "id": str(f.get("id")),
                                                       "fotografci": f.get("user"), "link": f.get("pageURL")}))
        if len(out) >= adet:
            break
    return out


def _pexels(sorgu, adet, yon, haric, http):
    r = http.get(PEXELS, params={"query": sorgu, "per_page": 15, "orientation": yon},
                 headers={"Authorization": _anahtar("PEXELS_API_KEY")}, timeout=30)
    r.raise_for_status()
    out = []
    for f in r.json().get("photos", []):
        if str(f.get("id")) in haric:
            continue
        adres = (f.get("src") or {}).get("large2x") or (f.get("src") or {}).get("original")
        if not adres:
            continue
        out.append((_indir(http, adres), {"kaynak": "pexels", "id": str(f.get("id")),
                                          "fotografci": f.get("photographer"), "link": f.get("url")}))
        if len(out) >= adet:
            break
    return out


def stok_ara(sorgu, adet=3, yon="portrait", haric=(), oturum=None):
    """Ucretsiz stok fotograf indirir (once Pixabay, sonra Pexels). -> [(yerel_yol, kaynak_bilgisi)]
    Pixabay kosullari: sonuclar indirilip kendi sunucumuzdan kullanilir (kalici hotlink yok), arama onbellegi var."""
    http = oturum or requests
    out = []
    if _anahtar("PIXABAY_API_KEY"):
        out = _pixabay(sorgu, adet, yon, haric, http)
    if len(out) < adet and _anahtar("PEXELS_API_KEY"):
        out += _pexels(sorgu, adet - len(out), yon, set(haric), http)
    return out


def yz_uret(istem, boyut="1024x1536", oturum=None):
    """Yapay zekayla gorsel uretir. -> yerel yol ya da None"""
    if not yz_hazir():
        return None
    http = oturum or requests
    url = (os.environ.get("AJAN_GORSEL_URL") or os.environ.get("AJAN_YZ_URL") or "https://inference.do-ai.run/v1").rstrip("/")
    model = os.environ.get("AJAN_GORSEL_MODEL", "openai-gpt-image-1")
    r = http.post(url + "/images/generations", timeout=240,
                  headers={"Authorization": f"Bearer {os.environ['AJAN_YZ_ANAHTAR'].strip()}"},
                  json={"model": model, "prompt": istem[:3800], "size": boyut, "n": 1})
    r.raise_for_status()
    d = (r.json().get("data") or [{}])[0]
    yol = _yol(istem + model + boyut, ".png")
    if d.get("b64_json"):
        yol.write_bytes(base64.b64decode(d["b64_json"]))
    elif d.get("url"):
        g = http.get(d["url"], timeout=120)
        g.raise_for_status()
        yol.write_bytes(g.content)
    else:
        return None
    return str(yol)
