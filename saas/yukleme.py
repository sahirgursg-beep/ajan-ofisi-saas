"""Panel yuklemeleri: fotograflar, belgeler ve logo (web servisi tarafi).

Depo duzeni:  <musteri>/yuklemeler/index.json   (kayit listesi; isci analiz ve kullanim bilgisini ekler)
              <musteri>/yuklemeler/<id>.<uzanti>
              <musteri>/yuklemeler/logo.png
Fotograflar sunucuda yeniden kodlanir (EXIF yonu duzeltilir, konum gibi meta veriler atilir, en fazla 2400 px).
"""
import io
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

GORSEL = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
BELGE = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/plain", ".csv": "text/csv"}
GORSEL_SINIR = 15 * 1024 * 1024
BELGE_SINIR = 20 * 1024 * 1024
EN_FAZLA_KAYIT = 300
Image.MAX_IMAGE_PIXELS = 60_000_000


class YuklemeHatasi(ValueError):
    pass


def dizin_anahtari(mid):
    return f"{mid}/yuklemeler/index.json"


def dizin(d, mid):
    v = d.json_oku(dizin_anahtari(mid), [])
    return v if isinstance(v, list) else []


def _gorsel_temizle(veri):
    try:
        im = Image.open(io.BytesIO(veri))
        im.load()
    except Exception:
        raise YuklemeHatasi("This file is not a readable image")
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((2400, 2400))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=90)          # meta veriler (GPS vb.) yeni dosyaya tasinmaz
    return b.getvalue()


def ekle(d, mid, dosyalar, notu=""):
    """dosyalar: [(ad, bayt)] -> eklenen kayitlar"""
    kayitlar = dizin(d, mid)
    if len(kayitlar) + len(dosyalar) > EN_FAZLA_KAYIT:
        raise YuklemeHatasi(f"Library is full ({EN_FAZLA_KAYIT} files). Delete some old files first.")
    yeni = []
    for ad, veri in dosyalar:
        uz = Path(ad or "").suffix.lower()
        if uz in GORSEL:
            if len(veri) > GORSEL_SINIR:
                raise YuklemeHatasi(f"{ad}: images must be under 15 MB")
            veri, uz, tur, tip = _gorsel_temizle(veri), ".jpg", "gorsel", "image/jpeg"
        elif uz in BELGE:
            if len(veri) > BELGE_SINIR:
                raise YuklemeHatasi(f"{ad}: documents must be under 20 MB")
            if uz == ".pdf" and not veri.startswith(b"%PDF"):
                raise YuklemeHatasi(f"{ad}: not a valid PDF")
            tur, tip = "belge", BELGE[uz]
        else:
            raise YuklemeHatasi(f"{ad}: use JPG, PNG, WEBP photos or PDF/TXT/CSV documents")
        kimlik = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)
        with tempfile.TemporaryDirectory() as t:
            yol = Path(t) / (kimlik + uz)
            yol.write_bytes(veri)
            d.dosya_yukle(f"{mid}/yuklemeler/{kimlik}{uz}", yol, tip)
        yeni.append({"id": kimlik, "dosya": kimlik + uz, "ad": Path(ad).name[:120], "tur": tur,
                     "not": (notu or "")[:300], "boyut": len(veri),
                     "tarih": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    d.json_yaz(dizin_anahtari(mid), dizin(d, mid) + yeni)     # arada baska yukleme olduysa kaybolmasin
    return yeni


def sil(d, mid, kimlik):
    kayitlar = dizin(d, mid)
    k = next((x for x in kayitlar if x.get("id") == kimlik), None)
    if not k:
        return False
    d.dosya_sil(f"{mid}/yuklemeler/{k['dosya']}")
    d.json_yaz(dizin_anahtari(mid), [x for x in kayitlar if x.get("id") != kimlik])
    return True


def gorunum(d, mid):
    kayitlar = sorted(dizin(d, mid), key=lambda x: x.get("tarih", ""), reverse=True)
    adresler = d.dosya_adresleri([f"{mid}/yuklemeler/{k['dosya']}" for k in kayitlar if k.get("tur") == "gorsel"])
    out = []
    for k in kayitlar:
        a = k.get("analiz") or {}
        out.append({"id": k["id"], "ad": k.get("ad"), "tur": k.get("tur"), "not": k.get("not", ""),
                    "tarih": k.get("tarih"), "adres": adresler.get(f"{mid}/yuklemeler/{k['dosya']}"),
                    "baslik": a.get("baslik") or a.get("ozet") or "", "incelendi": bool(a),
                    "uygun": a.get("uygun", True), "kullanildi": bool(k.get("kullanim"))})
    return out


# ---------------------------------------------------------------- logo
def _palet(im):
    """Logodan marka renkleri: koyu, vurgu (en doygun), acik. Seffaf ve beyaza yakin pikseller sayilmaz."""
    rgba = im.convert("RGBA")
    rgba.thumbnail((200, 200))
    pikseller = [p[:3] for p in (rgba.get_flattened_data() if hasattr(rgba, 'get_flattened_data') else rgba.getdata())
                 if p[3] > 200 and sum(p[:3]) < 720]
    if len(pikseller) < 20:
        return {}
    kucuk = Image.new("RGB", (len(pikseller), 1))
    kucuk.putdata(pikseller)
    renkler = [c for _, c in sorted(kucuk.quantize(6).convert("RGB").getcolors(64) or [], reverse=True)]
    if not renkler:
        return {}
    import colorsys
    hx = lambda c: "#%02X%02X%02X" % c
    parlaklik = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    doygunluk = lambda c: colorsys.rgb_to_hsv(*(x / 255 for x in c))[1]
    koyu = min(renkler, key=parlaklik)
    vurgu = max(renkler, key=lambda c: (doygunluk(c), -abs(parlaklik(c) - 140)))
    if parlaklik(koyu) > 90:                     # logo hep acik renkliyse koyu zemin: vurgunun koyu tonu
        koyu = tuple(int(x * 0.25) for x in vurgu)
    return {"renk_koyu": hx(koyu), "renk_altin": hx(vurgu), "renk_acik": "#F6F2EC"}


def logo_kaydet(d, mid, veri):
    """-> (logo PNG baytlari, onerilen palet)"""
    if len(veri) > 8 * 1024 * 1024:
        raise YuklemeHatasi("Logo must be under 8 MB")
    try:
        im = Image.open(io.BytesIO(veri))
        im.load()
    except Exception:
        raise YuklemeHatasi("Upload your logo as PNG or JPG")
    im = ImageOps.exif_transpose(im)
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    im.thumbnail((1200, 1200))
    b = io.BytesIO()
    im.save(b, "PNG")
    with tempfile.TemporaryDirectory() as t:
        yol = Path(t) / "logo.png"
        yol.write_bytes(b.getvalue())
        d.dosya_yukle(f"{mid}/yuklemeler/logo.png", yol, "image/png")
    return _palet(im)
