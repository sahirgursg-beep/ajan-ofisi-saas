"""Siteye baglanmadan sistemi denemek icin ornek urunler ve cizilmis gorseller."""
from PIL import Image, ImageDraw

from .ayarlar import KOK, PAYLASIK

KLASOR = PAYLASIK / "demo_gorseller"


def _koltuk(yol, renk, aci=0):
    W, H = 1200, 1200
    img = Image.new("RGB", (W, H), (236, 232, 225))
    c = ImageDraw.Draw(img)
    c.rectangle([0, 820, W, H], fill=(205, 196, 182))  # zemin
    c.ellipse([180, 860, 1020, 940], fill=(185, 175, 160))  # golge
    x = 160 + aci
    c.rounded_rectangle([x, 420, x + 880, 640], 60, fill=renk)  # arkalik
    koyu = tuple(int(v * 0.8) for v in renk)
    c.rounded_rectangle([x - 40, 560, x + 920, 820], 50, fill=koyu)  # oturak
    for i in range(3):
        c.rounded_rectangle([x + 20 + i * 290, 600, x + 280 + i * 290, 700], 30, fill=renk)  # minder
    c.rounded_rectangle([x - 80, 500, x + 40, 820], 40, fill=koyu)  # kol
    c.rounded_rectangle([x + 840, 500, x + 960, 820], 40, fill=koyu)
    for px in (x - 30, x + 900):
        c.rectangle([px, 820, px + 22, 880], fill=(90, 70, 50))  # ayak
    img.save(yol, quality=92)


def demo_urunler():
    KLASOR.mkdir(parents=True, exist_ok=True)
    tanimlar = [
        ("Milano 3-Seater Fabric Sofa", "Living Room > Sofas", 1250, (120, 135, 120)),
        ("Verona L-Shaped Sectional", "Living Room > Sectionals", 2380, (150, 120, 95)),
        ("Oslo Velvet Armchair Set", "Living Room > Armchairs", 860, (90, 110, 150)),
        ("Royal Upholstered Bed Bench", "Bedroom > Benches", 640, (170, 150, 130)),
    ]
    urunler = []
    for i, (ad, kat, usd, renk) in enumerate(tanimlar):
        yollar = []
        for j in range(3):
            y = KLASOR / f"urun{i}_{j}.jpg"
            if not y.exists():
                _koltuk(y, tuple(min(255, v + j * 12) for v in renk), aci=j * 30)
            yollar.append(str(y))
        urunler.append({"ad": ad, "url": f"demo://urun{i}", "fiyat": usd, "para_birimi": "USD",
                        "eski_fiyat": round(usd / 0.6, 2) if i % 2 == 0 else None,
                        "kategori": kat, "aciklama": "Solid hardwood frame, high-density foam cushions.",
                        "gorseller": yollar})
    return urunler
