"""Sanat Yonetmeni'ne 3 farkli YENI sablon tasarlatir (gercek urunlerle, post + story).
    python sanat_ornek.py          -> feed'den 3 urun
    python sanat_ornek.py --demo   -> ornek urunlerle
Sonuc: cikti/sanat_ornekleri/  (tarifler sablonlar/kutuphane/ klasorune de kaydedilir)
"""
import hashlib
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw  # noqa: E402

from ofis import fiyat, gorsel, llm, pano, tasarim, urun_cekici  # noqa: E402
from ofis.ajanlar import SanatYonetmeni  # noqa: E402
from ofis.ayarlar import AYAR, KOK, VERI, CIKTI  # noqa: E402

BASLIKLAR = ["Quiet luxury for everyday living", "Where family evenings begin", "Made for slow Sunday mornings"]


def main():
    hedef = CIKTI / "sanat_ornekleri"
    hedef.mkdir(parents=True, exist_ok=True)
    pano.kur()
    sy = SanatYonetmeni(7)
    print("LLM:", AYAR["model"] if llm.hazir() else "YOK (sablon modu - rastgele kombinasyonlar)")
    if "--demo" in sys.argv:
        from ofis.demo import demo_urunler
        urunler = demo_urunler()
    else:
        urunler = urun_cekici.urunleri_cek(print)
    urunler = [u for u in urunler if u.get("gorseller")]
    random.shuffle(urunler)
    secilen, kat = [], set()
    for u in urunler:
        k = u.get("kategori", "").split(">")[-1].strip()
        if k not in kat:
            secilen.append(u)
            kat.add(k)
        if len(secilen) == 3:
            break
    onceki, ozet = [], []
    for i, u in enumerate(secilen, 1):
        fiyat.hazirla(u)
        yollar = []
        for g in u["gorseller"][:3]:
            try:
                yollar.append(urun_cekici.gorsel_indir(g, VERI / "gorsel_onbellek",
                                                       hashlib.md5(g.encode()).hexdigest() + ".img"))
            except Exception as e:
                print("  ! gorsel indirilemedi:", e)
        if not yollar:
            continue
        kisit = ("These must be clearly DIFFERENT from the designs you already made in this batch "
                 f"(use another layout, font pair and palette): {onceki}") if onceki else ""
        tarif = sy.tarif_uret(u, yollar, kisit)
        onceki.append({k: tarif[k] for k in ("duzen", "fontlar", "motif", "palet")})
        v = tasarim.veri_hazirla(u, yollar, {"headline": BASLIKLAR[(i - 1) % 3]}, tarif)
        post, story = hedef / f"{i}_post.jpg", hedef / f"{i}_story.jpg"
        tasarim.ciz("dinamik.html", v, post)
        tasarim.ciz("dinamik.html", v, story, (1080, 1920))
        (hedef / f"{i}_tarif.json").write_text(json.dumps(tarif, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{i}] {tarif['isim']}: {tarif['duzen']} / {tarif['fontlar']} / {tarif['motif']} / {tarif['palet']}")
        print(f"    {tarif.get('neden', '')}")
        ozet.append((tarif["isim"], Image.open(post), Image.open(story)))
        if i == 1:
            print("    Bu sablonla reklam Reels'i hazirlaniyor (~1 dk)...")
            from ofis import reklam
            reklam.reklam_yap(u, yollar, {"hook": BASLIKLAR[0]}, tarif, hedef / "1_reels.mp4")
    tasarim.kapat()
    if ozet:  # tek sayfada karsilastirma
        k = Image.new("RGB", (len(ozet) * 2220 + 20, 1920 + 100), (24, 20, 17))
        c = ImageDraw.Draw(k)
        for j, (isim, p, s) in enumerate(ozet):
            x = 20 + j * 2220
            c.text((x, 24), f"{j + 1}. {isim}", font=gorsel.font("kalin", 44), fill=(230, 204, 138))
            k.paste(p, (x, 100))
            k.paste(s, (x + 1100, 100))
        k.thumbnail((3600, 3600))
        k.save(hedef / "karsilastirma.jpg", quality=88)
    print(f"\nHazir: {hedef}")
    if os.name == "nt":
        os.startfile(hedef)


if __name__ == "__main__":
    main()
