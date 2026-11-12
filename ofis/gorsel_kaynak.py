"""Gorsel kaynaklari: urun fotografi olmayan isletmeler icin.

  stok        -> Pexels (ucretsiz, ticari kullanima acik; PEXELS_API_KEY ortam degiskeni)
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


def _yol(anahtar, uzanti):
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    return ONBELLEK / (hashlib.md5(anahtar.encode()).hexdigest() + uzanti)


def stok_hazir():
    return bool(os.environ.get("PEXELS_API_KEY", "").strip())


def yz_hazir():
    return bool(os.environ.get("AJAN_YZ_ANAHTAR", "").strip()) and os.environ.get("AJAN_GORSEL_URET", "1") != "0"


def stok_ara(sorgu, adet=3, yon="portrait", haric=(), oturum=None):
    """Pexels'ten fotograf indirir. -> [(yerel_yol, kaynak_bilgisi)]"""
    if not stok_hazir():
        return []
    http = oturum or requests
    r = http.get(PEXELS, params={"query": sorgu, "per_page": 15, "orientation": yon},
                 headers={"Authorization": os.environ["PEXELS_API_KEY"].strip()}, timeout=30)
    r.raise_for_status()
    out = []
    for f in r.json().get("photos", []):
        if str(f.get("id")) in haric:
            continue
        adres = (f.get("src") or {}).get("large2x") or (f.get("src") or {}).get("original")
        if not adres:
            continue
        yol = _yol(adres, ".jpg")
        if not yol.exists():
            g = http.get(adres, timeout=60)
            g.raise_for_status()
            yol.write_bytes(g.content)
        out.append((str(yol), {"kaynak": "pexels", "id": str(f.get("id")), "fotografci": f.get("photographer"),
                                "link": f.get("url")}))
        if len(out) >= adet:
            break
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
