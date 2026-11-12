"""Tamamlanan projeler (gercek musteri isleri) -> haftalik "Proje gunu" icerigi.

Kullanim: proje klasorune (projeler/) her proje icin bir alt klasor acin, fotograflari icine atin.
  projeler/2026-11 Lekki Villa Kitchen/foto1.jpg ...
  projeler/2026-11 Lekki Villa Kitchen/bilgi.txt   (istege bagli)
      1. satir: baslik           (ornek: Modern kitchen for a family home)
      2. satir: konum            (ornek: Lekki, Lagos)
      sonraki satirlar: kisa aciklama (ne yapildi, hangi malzeme...)
  Kapak olmasini istediginiz fotografin adina "kapak" yazin (ornek: kapak.jpg).

Her hafta proje gunu (varsayilan cumartesi) YENI bir proje varsa o gunun 3 icerigi (post, carousel, Reels) o projeden
uretilir. Kullanilan proje bir daha paylasilmaz; yeni proje eklenmediyse o gun normal urun icerigi cikar.
Proje fotograflari gercek oldugu icin yapay zeka ile DEGISTIRILMEZ (genisletme/rotus yok); sadece kadraj ve tasarim.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from .ayarlar import KOK, VERI, PROJELER

KLASOR = PROJELER
KAYIT = VERI / "proje_kullanim.json"
ONBELLEK = VERI / "proje_onbellek"
UZANTI = {".jpg", ".jpeg", ".png", ".webp"}
BENIOKU = """Tamamlanan projelerinizin fotograflari icin klasor.

1) Her proje icin bir alt klasor acin:  ornek  "2026-11 Lekki Villa Kitchen"
2) Fotograflari icine atin (jpg / png). Kapak olmasini istediginizin adina "kapak" yazin.
3) Istege bagli bilgi.txt:
     1. satir: baslik        (Modern kitchen for a family home)
     2. satir: konum         (Lekki, Lagos)
     sonrasi : kisa aciklama (ne yapildi, malzemeler...)

Her hafta proje gununde (varsayilan cumartesi) en eski kullanilmamis proje paylasilir:
12:00 post, 15:00 carousel (tum fotolar), 18:30 Reels. Ayni proje bir daha paylasilmaz.
Yeni proje yoksa o gun normal urun icerigi cikar.
Musterinin adini, ev numarasini, yuz/aile fotolarini KOYMAYIN.
"""


def hazirla():
    KLASOR.mkdir(parents=True, exist_ok=True)
    oku_beni = KLASOR / "BENIOKU.txt"
    if not oku_beni.exists():
        oku_beni.write_text(BENIOKU, encoding="utf-8")


def _kayit():
    try:
        return json.loads(KAYIT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _kayit_yaz(d):
    KAYIT.parent.mkdir(parents=True, exist_ok=True)
    KAYIT.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _fotolar(k):
    fotolar = sorted([p for p in k.iterdir() if p.suffix.lower() in UZANTI and p.is_file()], key=lambda p: p.name.lower())
    kapak = [p for p in fotolar if "kapak" in p.stem.lower() or "cover" in p.stem.lower()]
    return kapak + [p for p in fotolar if p not in kapak]


def _bilgi(k):
    ad = re.sub(r"^\d{4}[-_. ]\d{1,2}[-_. ]*", "", k.name).strip(" -_") or k.name
    b = {"baslik": ad, "konum": "", "aciklama": ""}
    f = k / "bilgi.txt"
    if f.exists():
        satirlar = [s.strip() for s in f.read_text(encoding="utf-8", errors="ignore").splitlines() if s.strip()]
        if satirlar:
            b["baslik"] = satirlar[0][:80]
        if len(satirlar) > 1:
            b["konum"] = satirlar[1][:60]
        if len(satirlar) > 2:
            b["aciklama"] = " ".join(satirlar[2:])[:500]
    return b


def liste():
    hazirla()
    kayit = _kayit()
    out = []
    for k in sorted([d for d in KLASOR.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime):
        fotolar = _fotolar(k)
        out.append({"klasor": k.name, "foto_sayisi": len(fotolar), **_bilgi(k),
                    "kullanildi": kayit.get(k.name, {}).get("tarih"), "icerikler": kayit.get(k.name, {}).get("icerikler", {}),
                    "eklenme": datetime.fromtimestamp(k.stat().st_mtime).strftime("%Y-%m-%d")})
    return out


def siradaki():
    """Kullanilmamis, en az 2 fotografi olan en eski proje (yoksa None)."""
    for p in liste():
        if not p["kullanildi"] and p["foto_sayisi"] >= 2:
            return p
    return None


def _hazir_foto(yol):
    """Telefon fotografi: yonunu duzelt (EXIF), 2000 px'e kucult, onbellege jpg olarak koy."""
    from PIL import Image, ImageOps
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    hedef = ONBELLEK / (re.sub(r"[^\w]+", "_", f"{yol.parent.name}_{yol.stem}")[:90] + ".jpg")
    if hedef.exists() and hedef.stat().st_mtime >= yol.stat().st_mtime:
        return hedef
    im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
    im.thumbnail((2000, 2000))
    im.save(hedef, "JPEG", quality=92)
    return hedef


def urun_benzeri(p):
    """Uretim hattinin bekledigi 'urun' sozlugu (fiyatsiz). gorseller: yerel, hazirlanmis dosyalar."""
    k = KLASOR / p["klasor"]
    fotolar = []
    for f in _fotolar(k)[:12]:
        try:
            fotolar.append(str(_hazir_foto(f)))
        except Exception:
            continue
    ad = p["baslik"]
    return {"id": "proje:" + p["klasor"], "ad": ad, "url": "proje://" + p["klasor"], "proje": True,
            "proje_klasor": p["klasor"], "kategori": "Our Projects > " + (p["konum"] or "Completed project"),
            "aciklama": p["aciklama"], "konum": p["konum"], "fiyat_metni": "", "eski_fiyat_metni": "",
            "indirim_yuzde": 0, "gorseller": fotolar}


def kullanildi_isaretle(p, tur, klasor):
    d = _kayit()
    x = d.setdefault(p["klasor"], {"tarih": datetime.now().strftime("%Y-%m-%d"), "icerikler": {}})
    x["icerikler"][tur] = Path(klasor).name
    _kayit_yaz(d)


def tekrar_kullan(klasor_adi):
    """Kullanicinin istegiyle bir projeyi tekrar siraya alir."""
    d = _kayit()
    d.pop(klasor_adi, None)
    _kayit_yaz(d)
