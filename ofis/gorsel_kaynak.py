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

from . import fal_ai
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
    if os.environ.get("AJAN_GORSEL_URET", "1") == "0":
        return False
    return fal_ai.hazir() or bool(os.environ.get("AJAN_YZ_ANAHTAR", "").strip())


def _indir(http, adres):
    """Onbellekli indirme. Pixabay/Pexels 429 (cok istek) verirse kisa bekleyip tekrar dener."""
    import time
    yol = _yol(adres, ".jpg")
    if not yol.exists():
        for deneme in range(4):
            g = http.get(adres, timeout=60)
            if g.status_code == 429 and deneme < 3:
                time.sleep(2 + 3 * deneme)
                continue
            g.raise_for_status()
            break
        yol.write_bytes(g.content)
        time.sleep(0.15)                    # saniyede ~6 istegi gecmeyelim (Pixabay siniri dakikada 100)
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


def stok_adaylar(sorgu, adet=8, yon="portrait", haric=(), oturum=None):
    """Indirmeden aday listesi (secici kucuk onizlemelere bakip en iyisini secer).
    -> [{"id", "onizleme", "buyuk", "bilgi"}]"""
    http = oturum or requests
    out = []
    try:
        if _anahtar("PIXABAY_API_KEY"):
            r = http.get(PIXABAY, timeout=30, params={
                "key": _anahtar("PIXABAY_API_KEY"), "q": sorgu[:100], "image_type": "photo", "safesearch": "true",
                "orientation": "vertical" if yon == "portrait" else "horizontal" if yon == "landscape" else "all",
                "per_page": max(3, min(adet * 2, 40)), "order": "popular"})
            r.raise_for_status()
            for f in r.json().get("hits", []):
                if str(f.get("id")) in haric or not f.get("largeImageURL") or not f.get("webformatURL"):
                    continue
                out.append({"id": f"pixabay:{f['id']}", "onizleme": f["webformatURL"], "buyuk": f["largeImageURL"],
                            "bilgi": {"kaynak": "pixabay", "id": str(f.get("id")), "fotografci": f.get("user"),
                                      "link": f.get("pageURL")}})
    except Exception as e:
        print(f"  ! Pixabay aramasi: {str(e)[:100]}")
    if len(out) < adet and _anahtar("PEXELS_API_KEY"):
        try:
            r = http.get(PEXELS, params={"query": sorgu, "per_page": adet * 2, "orientation": yon},
                         headers={"Authorization": _anahtar("PEXELS_API_KEY")}, timeout=30)
            r.raise_for_status()
            for f in r.json().get("photos", []):
                src = f.get("src") or {}
                if str(f.get("id")) in haric or not src.get("medium"):
                    continue
                out.append({"id": f"pexels:{f['id']}", "onizleme": src["medium"],
                            "buyuk": src.get("large2x") or src.get("original"),
                            "bilgi": {"kaynak": "pexels", "id": str(f.get("id")), "fotografci": f.get("photographer"),
                                      "link": f.get("url")}})
        except Exception as e:
            print(f"  ! Pexels aramasi: {str(e)[:100]}")
    return out[:adet]


def indir(adres, oturum=None):
    return _indir(oturum or requests, adres)


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
    w, h = (int(x) for x in boyut.split("x"))
    if fal_ai.hazir():
        im = fal_ai.uret(istem, w, h, oturum=http)
        if im is None:
            return None
        yol = _yol(istem + "fal" + boyut, ".jpg")
        im.save(yol, quality=93)
        return str(yol)
    if not fal_ai.butce_var(0.07):
        return None
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
    fal_ai.harca(0.07, "gorsel_uretim_do")
    return str(yol)
