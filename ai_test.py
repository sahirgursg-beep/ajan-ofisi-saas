"""Ekran karti AI testini yapar: 2 gercek urun fotografini netlestirir ve dikeye tamamlar.
Sonuc: cikti/ai_test/  (once_sonra_*.jpg: solda orijinal, sagda AI ile tamamlanmis 9:16)
"""
import hashlib
import os
import random
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw  # noqa: E402

from ofis import ai_gorsel, algila, gorsel, marka, urun_cekici  # noqa: E402
from ofis.ayarlar import KOK, VERI, CIKTI  # noqa: E402


def main():
    hazir, aciklama = ai_gorsel.durum()
    print("Ekran karti:", aciklama)
    if not hazir:
        print("AI hazir degil. Once AI_KURULUM.bat calistirin.")
        return 1
    hedef = CIKTI / "ai_test"
    hedef.mkdir(parents=True, exist_ok=True)
    urunler = urun_cekici.onbellekten() or urun_cekici.urunleri_cek(print)
    urunler = [u for u in urunler if u.get("gorseller")]
    random.shuffle(urunler)
    for i, u in enumerate(urunler[:2], 1):
        g = u["gorseller"][0]
        print(f"\n[{i}/2] {u['ad']}")
        yol = urun_cekici.gorsel_indir(g, VERI / "gorsel_onbellek", hashlib.md5(g.encode()).hexdigest() + ".img")
        t = time.time()
        net = ai_gorsel.netlestir(yol)
        print(f"   netlestirme: {'yapildi' if net != yol else 'gerek yok (foto zaten buyuk)'} ({time.time() - t:.0f} sn)")
        kaynak = marka.gorsel_hazirla(net)
        kutu = algila.urun_kutusu(kaynak)
        print(f"   urun algilama ({kutu['yontem']}): x {kutu['x0']:.2f}-{kutu['x1']:.2f}, y {kutu['y0']:.2f}-{kutu['y1']:.2f}")
        t = time.time()
        dikey = ai_gorsel.dikey_genislet(kaynak, kutu, u.get("kategori", ""))
        print(f"   dikeye tamamlama: {time.time() - t:.0f} sn")
        # once / sonra
        once = gorsel.ac(kaynak)
        once.thumbnail((1080, 1920))
        sonra = Image.open(dikey).convert("RGB")
        k = Image.new("RGB", (1080 * 2 + 60, 1920 + 120), (24, 20, 17))
        c = ImageDraw.Draw(k)
        k.paste(once, (20, 120 + (1920 - once.height) // 2))
        k.paste(sonra, (1120, 120))
        c.text((20, 30), "ONCE (orijinal)", font=gorsel.font("kalin", 48), fill=(230, 204, 138))
        c.text((1120, 30), "SONRA (AI ile 9:16)", font=gorsel.font("kalin", 48), fill=(230, 204, 138))
        k.save(hedef / f"once_sonra_{i}.jpg", quality=90)
        sonra.save(hedef / f"dikey_{i}.jpg", quality=95)
    ai_gorsel.bosalt()
    print(f"\nHazir: {hedef}")
    if os.name == "nt":
        os.startfile(hedef)
    return 0


if __name__ == "__main__":
    sys.exit(main())
