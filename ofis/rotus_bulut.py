"""Bulutta Rotuscu: GPU olmadan urun fotografi iyilestirme.

  netlestir(yol)        -> kucuk/bulanik fotolari yerelde buyutur ve keskinlestirir (Pillow, ucretsiz, hizli)
  dikey_genislet(yol)   -> yatay fotoyu 9:16'ya tamamlar: urun ortada SABIT kalir, yalnizca bos ust/alt alani
                           yapay zeka doldurur (OpenAI uyumlu /images/edits + maske). Servis desteklemiyorsa
                           None doner ve tasarim bulanik arka planla kirpar.
Urunun kendisine yapay zeka dokunmaz: maske urun alanini korur, sonucta urun alani orijinalden geri yapistirilir.
"""
import base64
import io
import os
from pathlib import Path

import requests
from PIL import Image, ImageFilter

from .ayarlar import VERI

KLASOR = VERI / "rotus"
_desteklenmiyor = False


def hazir():
    return bool(os.environ.get("AJAN_YZ_ANAHTAR", "").strip()) and os.environ.get("AJAN_ROTUS_BULUT", "1") != "0"


def netlestir(yol, hedef_kisa_kenar=1080):
    """Kisa kenari 1080'den kucukse buyutur + hafif keskinlestirir. Degismezse ayni yolu doner."""
    im = Image.open(yol)
    kisa = min(im.size)
    if kisa >= hedef_kisa_kenar * 0.9:
        return str(yol)
    oran = hedef_kisa_kenar / kisa
    yeni = im.convert("RGB").resize((round(im.width * oran), round(im.height * oran)), Image.LANCZOS)
    yeni = yeni.filter(ImageFilter.UnsharpMask(radius=1.6, percent=80, threshold=2))
    KLASOR.mkdir(parents=True, exist_ok=True)
    cikti = KLASOR / f"net_{Path(yol).stem}.jpg"
    yeni.save(cikti, quality=93)
    return str(cikti)


def _png(im):
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def dikey_genislet(yol, kutu=None, ipucu="", oturum=None):
    """-> 1024x1536 dikey gorselin yolu ya da None (servis yok / desteklenmiyor / hata)."""
    global _desteklenmiyor
    if _desteklenmiyor or not hazir():
        return None
    kaynak = Image.open(yol).convert("RGB")
    if kaynak.height >= kaynak.width * 1.2:
        return None                                  # zaten dikey
    W, H = 1024, 1536
    olcek = W / kaynak.width
    ic = kaynak.resize((W, round(kaynak.height * olcek)), Image.LANCZOS)
    y0 = (H - ic.height) // 2
    tuval = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tuval.paste(ic.convert("RGBA"), (0, y0))
    maske = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # seffaf = doldurulacak alan
    maske.paste(Image.new("RGBA", ic.size, (0, 0, 0, 255)), (0, y0))
    http = oturum or requests
    url = (os.environ.get("AJAN_GORSEL_URL") or os.environ.get("AJAN_YZ_URL") or "https://inference.do-ai.run/v1").rstrip("/")
    model = os.environ.get("AJAN_GORSEL_MODEL", "openai-gpt-image-1")
    istem = ("Extend the photo naturally upward and downward to a vertical frame: continue the same room, floor, "
             "wall, lighting and perspective. Do not change, move or add to the main subject. No text, no logos."
             + (f" Context: {ipucu}." if ipucu else ""))
    try:
        r = http.post(url + "/images/edits", timeout=240,
                      headers={"Authorization": f"Bearer {os.environ['AJAN_YZ_ANAHTAR'].strip()}"},
                      data={"model": model, "prompt": istem, "size": f"{W}x{H}", "n": "1"},
                      files={"image": ("image.png", _png(tuval), "image/png"),
                             "mask": ("mask.png", _png(maske), "image/png")})
        if r.status_code in (400, 404, 405, 422, 501):
            _desteklenmiyor = True                   # bu servis/model duzenlemeyi desteklemiyor: bu calismada bir daha deneme
            print(f"  ! bulut rotus desteklenmiyor (HTTP {r.status_code}): {r.text[:160]}")
            return None
        r.raise_for_status()
        d = (r.json().get("data") or [{}])[0]
        if d.get("b64_json"):
            sonuc = Image.open(io.BytesIO(base64.b64decode(d["b64_json"]))).convert("RGB")
        elif d.get("url"):
            sonuc = Image.open(io.BytesIO(http.get(d["url"], timeout=120).content)).convert("RGB")
        else:
            return None
    except Exception as e:
        print(f"  ! bulut rotus hatasi: {str(e)[:160]}")
        return None
    sonuc = sonuc.resize((W, H), Image.LANCZOS)
    sonuc.paste(ic, (0, y0))                         # urun alani birebir orijinal
    KLASOR.mkdir(parents=True, exist_ok=True)
    cikti = KLASOR / f"dikey_{Path(yol).stem}.jpg"
    sonuc.save(cikti, quality=93)
    return str(cikti)
