"""Tasarim yonlerini gercek urunlerle karsilastirmak icin onizleme uretir.
    python onizleme.py         -> feed'den 4 rastgele urun, her biri A/B/C
Sonuc: cikti/onizleme/ klasoru (karsilastirma_*.jpg + tek tek postlar + ornek reels)
"""
import hashlib
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw  # noqa: E402

from ofis import fiyat, gorsel, tasarim, urun_cekici  # noqa: E402
from ofis.ayarlar import KOK, VERI, CIKTI  # noqa: E402

YONLER = {"A": ("A_editoryal_post.html", "A · Editoryal"),
          "B": ("B_altin_cerceve_post.html", "B · Altin Cerceve"),
          "C": ("C_showroom_firsati_post.html", "C · Showroom Firsati"),
          "D": ("D_kolaj_post.html", "D · Kolaj"),
          "E": ("E_canli_post.html", "E · Canli")}
ORNEK_METIN = ["Quiet luxury for everyday living", "Where family evenings begin",
               "Made for slow mornings", "Elegance you can live in"]


def main():
    hedef = CIKTI / "onizleme"
    hedef.mkdir(parents=True, exist_ok=True)
    print("Urunler feed'den okunuyor...")
    urunler = urun_cekici.urunleri_cek(print)
    print(f"{len(urunler)} uygun urun bulundu.")
    if not urunler:
        print("Urun yok! config.json'daki feed_url'i kontrol edin.")
        return 1
    # farkli alt kategorilerden, en cok fotografi olan 4 urun
    random.shuffle(urunler)
    secilen, gorulen = [], set()
    for u in sorted(urunler, key=lambda u: -min(len(u["gorseller"]), 3)):
        kat = u["kategori"].split(">")[-1].strip()
        if kat not in gorulen:
            secilen.append(u)
            gorulen.add(kat)
        if len(secilen) == 4:
            break
    for i, u in enumerate(secilen):
        fiyat.hazirla(u)
        print(f"[{i + 1}/4] {u['ad']} — {u['fiyat_metni']}")
        yollar = []
        for g in u["gorseller"][:3]:
            try:
                yollar.append(urun_cekici.gorsel_indir(g, VERI / "gorsel_onbellek",
                                                       hashlib.md5(g.encode()).hexdigest() + ".img"))
            except Exception as e:
                print("   ! gorsel indirilemedi:", e)
        if not yollar:
            continue
        v = tasarim.veri_hazirla(u, yollar, {"headline": ORNEK_METIN[i % 4]})
        kareler = []
        for harf, (sablon, etiket) in YONLER.items():
            dosya = hedef / f"{i + 1}_{harf}_post.jpg"
            tasarim.ciz(sablon, v, dosya)
            tasarim.ciz(sablon, v, hedef / f"{i + 1}_{harf}_story.jpg", (1080, 1920))
            kareler.append((etiket, Image.open(dosya)))
        # yan yana karsilastirma (5 yon)
        k = Image.new("RGB", (1100 * len(kareler) + 20, 1350 + 90), (24, 20, 17))
        c = ImageDraw.Draw(k)
        for j, (etiket, im) in enumerate(kareler):
            x = 20 + j * 1100
            k.paste(im, (x, 70))
            c.text((x + 10, 18), etiket, font=gorsel.font("kalin", 38), fill=(230, 204, 138))
        k.thumbnail((3000, 3000))
        k.save(hedef / f"karsilastirma_{i + 1}.jpg", quality=88)
        if i == 0:
            print("   Ornek reklam Reels hazirlaniyor (~1 dk)...")
            from ofis import reklam
            reklam.reklam_yap(u, yollar, {"hook": "Quiet luxury, everyday comfort"}, None, hedef / "ornek_reels.mp4")
    tasarim.kapat()
    print(f"\nHazir! Klasor: {hedef}")
    if os.name == "nt":
        os.startfile(hedef)
    return 0


if __name__ == "__main__":
    sys.exit(main())
