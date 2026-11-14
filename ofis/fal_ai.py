"""fal.ai baglantisi: bulut rotus (dikey genisletme) ve yapay zeka gorsel uretimi.

Anahtar: FAL_KEY (fal.ai > Dashboard > API Keys). Modeller ortam degiskeniyle degistirilebilir:
  AJAN_FAL_GENISLET  (varsayilan fal-ai/flux-2-pro/outpaint, ~$0.06 / dikey gorsel)
  AJAN_FAL_URET      (varsayilan fal-ai/flux-2-pro, ~$0.045 / dikey gorsel; hata verirse flux-2/flash)
Aylik harcama tavani (musteri basina, USD): AJAN_YZ_AYLIK_TAVAN (varsayilan 10). Tavan dolunca ucretli cagri
yapilmaz; rotus bedava netlestirmeye, gorseller stok fotograflara doner.
"""
import base64
import io
import json
import math
import os
from datetime import date

import requests
from PIL import Image

from .ayarlar import VERI

TABAN = "https://fal.run/"
HARCAMA = VERI / "yz_harcama.json"


def _anahtar():
    return os.environ.get("FAL_KEY", "").strip()


def hazir():
    return bool(_anahtar())


# ---------------- harcama tavani ----------------
def _ay():
    return date.today().strftime("%Y-%m")


def _harcamalar():
    try:
        return json.loads(HARCAMA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def tavan():
    """Aylik ucretli yapay zeka butcesi: paketin tavani; ortam degiskeni ust sinir koyar."""
    try:
        ust = float(os.environ.get("AJAN_YZ_AYLIK_TAVAN", "100"))
    except ValueError:
        ust = 100.0
    try:
        from . import paketler
        return min(float(paketler.aktif()["ai_tavan_usd"]), ust)
    except Exception:
        return min(10.0, ust)


def bu_ay():
    return float(_harcamalar().get(_ay(), 0.0))


def gorsel_hakki():
    """Paketin aylik yapay zeka gorsel hakki (adet). Musterinin kendi fotograflari hakki harcamaz."""
    try:
        from . import paketler
        return int(paketler.aktif().get("ai_gorsel") or 0)
    except Exception:
        return 0


def gorsel_kullanilan():
    k = ((_harcamalar().get("_kalemler") or {}).get(_ay()) or {}).get("gorsel_uretim") or {}
    return int(k.get("adet") or 0)


def gorsel_kalan():
    hak = gorsel_hakki()
    return max(0, hak - gorsel_kullanilan()) if hak else 10 ** 6


def butce_var(tahmini=0.0):
    return bu_ay() + tahmini <= tavan()


_harca_kilit = __import__("threading").Lock()


def harca(tutar, ne=""):
    """Paralel is parcaciklari ayni dosyaya yazar: kilit + atomik yazim (aksi halde sayac sifirlaniyordu)."""
    with _harca_kilit:
        h = _harcamalar()
        h[_ay()] = round(float(h.get(_ay(), 0.0)) + tutar, 4)
        kalem = h.setdefault("_kalemler", {}).setdefault(_ay(), {})
        k = kalem.setdefault(ne or "diger", {"adet": 0, "usd": 0.0})
        k["adet"] += 1
        k["usd"] = round(k["usd"] + tutar, 5)
        HARCAMA.parent.mkdir(parents=True, exist_ok=True)
        gecici = HARCAMA.with_suffix(".tmp")
        gecici.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(gecici, HARCAMA)


def _mp(w, h):
    return math.ceil(w * h / 1_048_576)        # fal: 1 MP = 1024x1024


def genisletme_fiyati(giris_wh, cikis_wh):
    """FLUX.2 Pro: ilk cikis MP $0.03, sonraki her giris+cikis MP $0.015 (yukari yuvarlanir)."""
    return 0.03 + 0.015 * (_mp(*cikis_wh) - 1 + _mp(*giris_wh))


# ---------------- cagrilar ----------------
def _veri_uri(im, bicim="JPEG"):
    b = io.BytesIO()
    im.convert("RGB").save(b, bicim, quality=92)
    return f"data:image/{bicim.lower()};base64," + base64.b64encode(b.getvalue()).decode()


def _cagir(model, girdi, http, sure=240):
    r = http.post(TABAN + model, json=girdi, timeout=sure,
                  headers={"Authorization": f"Key {_anahtar()}", "Content-Type": "application/json"})
    r.raise_for_status()
    gorsel = ((r.json() or {}).get("images") or [{}])[0].get("url")
    if not gorsel:
        raise RuntimeError("fal.ai bos sonuc dondu")
    if gorsel.startswith("data:"):
        return Image.open(io.BytesIO(base64.b64decode(gorsel.split(",", 1)[1])))
    g = http.get(gorsel, timeout=120)
    g.raise_for_status()
    return Image.open(io.BytesIO(g.content))


def genislet(ic, ust, alt, oturum=None):
    """PIL gorseli (genislik 1024) yukari/asagi genisletir. -> PIL gorsel ya da None (anahtar/butce yok)."""
    cikis = (ic.width, ic.height + ust + alt)
    fiyat = genisletme_fiyati(ic.size, cikis)
    if not hazir() or not butce_var(fiyat):
        return None
    model = os.environ.get("AJAN_FAL_GENISLET", "fal-ai/flux-2-pro/outpaint")
    sonuc = _cagir(model, {"image_url": _veri_uri(ic), "expand_top": int(ust), "expand_bottom": int(alt),
                           "mode": "high", "output_format": "jpeg"}, oturum or requests)
    harca(fiyat, "rotus_genisletme")
    return sonuc.convert("RGB")


def uret(istem, w=1024, h=1536, oturum=None):
    """Metinden gorsel. -> PIL gorsel ya da None."""
    # Varsayilan FLUX.2 Pro: flash'a gore cok daha az bozuk el/anlamsiz yazi (~$0.03/MP). Hata verirse flash.
    # Butcenin ilk yarisinda FLUX.2 Pro (kalite), ikinci yarisinda flash (6 kat ucuz): ay sonu stoksuz kalinmasin
    model = os.environ.get("AJAN_FAL_URET") or ("fal-ai/flux-2-pro" if bu_ay() < 0.5 * tavan() else "fal-ai/flux-2/flash")
    fiyat = (0.005 if "flash" in model else 0.03) * max(1, _mp(w, h))
    if not hazir() or not butce_var(fiyat) or gorsel_kalan() <= 0:
        return None
    girdi = {"prompt": istem[:3000], "image_size": {"width": w, "height": h}, "output_format": "jpeg"}
    try:
        sonuc = _cagir(model, girdi, oturum or requests, sure=180)
    except Exception as e:
        if "flash" in model:
            raise
        print(f"  ! {model} kullanilamadi ({str(e)[:80]}), flux-2/flash deneniyor")
        model, fiyat = "fal-ai/flux-2/flash", 0.005 * max(1, _mp(w, h))
        sonuc = _cagir(model, girdi, oturum or requests, sure=180)
    harca(fiyat, "gorsel_uretim")
    return sonuc.convert("RGB")
