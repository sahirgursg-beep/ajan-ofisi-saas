"""Carousel (kaydirmali) post: kapak + 2-3 detay karti + fiyat/CTA karti, hepsi 1080x1350.

Kapak = gunun postu (ayni gorunum). Detay kartlari urunun diger fotograflari; urunun tek fotografi varsa
ayni fotograftan yakin plan kirpimlar kullanilir (urune dokunulmaz, sadece kadraj). Metinler Metin Yazari'nin
carousel_lines / carousel_points alanlarindan gelir; fiyat KOD ile yazilir.
"""
import shutil
from pathlib import Path

from PIL import Image

from . import marka, musteri, tasarim

EN_FAZLA = 5


def _kirpimlar(ana_yol, klasor, adet):
    """Tek fotografli urunler icin: urun kutusunun iki farkli bolgesinden 4:5 yakin plan."""
    from . import algila
    yol = marka.gorsel_hazirla(Path(ana_yol))
    im = Image.open(yol).convert("RGB")
    W, H = im.size
    try:
        k = algila.urun_kutusu(yol) or {}
    except Exception:
        k = {}
    x0, x1 = k.get("x0", .15) * W, k.get("x1", .85) * W
    y0, y1 = k.get("y0", .3) * H, k.get("y1", .9) * H
    bw, bh = x1 - x0, y1 - y0
    cikti = []
    # urunun sol ve sag tarafindan, tam yukseklikte 4:5 yakin planlar (cozunurluk korunur)
    h = min(H, max(bh * 1.05, H * 0.62))
    w = min(W, h * 0.8)
    h = w / 0.8
    for i, fx in enumerate([0.28, 0.74, 0.5][:adet]):
        cx, cy = x0 + bw * fx, y0 + bh * 0.5
        l = min(max(cx - w / 2, 0), W - w)
        t = min(max(cy - h / 2, 0), H - h)
        kirp = im.crop((int(l), int(t), int(l + w), int(t + h)))
        if kirp.width < 700:   # cok kucukse kirpma yapma (bulaniklasir)
            continue
        hedef = klasor / f"_kirp_{i}.jpg"
        kirp.save(hedef, quality=95)
        cikti.append(hedef)
    return cikti


def _noktalar(sira, toplam):
    return "".join(f'<i class="{"aktif" if i == sira else ""}"></i>' for i in range(1, toplam + 1))


def _varsayilan_degiskenler(v):
    """Sanat Yonetmeni tarifi yoksa (sabit mod) marka renkleri."""
    v.setdefault("siniflar", "f-klasik")
    v.setdefault("t_zemin", "#1C1612")
    v.setdefault("t_yazi", "#F4EFE6")
    v.setdefault("t_vurgu", "#C9A24B")
    v.setdefault("t_vurgu_yazi", "#1C1612")
    v.setdefault("t_panel", "#F4EFE6")
    v.setdefault("t_panel_yazi", "#1C1612")
    return v


def _parlak(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def uret(urun, gorsel_yollari, taslak, tarif, klasor, gunluk=print):
    """carousel_1.jpg ... carousel_N.jpg uretir. Donus: dosya listesi."""
    klasor = Path(klasor)
    kapak = klasor / "post_1080x1350.jpg"
    if not kapak.exists():
        raise FileNotFoundError("Once post cizilmeli (kapak karti)")
    for eski in klasor.glob("carousel_*.jpg"):
        eski.unlink()
    proje = bool(urun.get("proje"))
    detay_fotolar = list(gorsel_yollari[1:9 if proje else 4])
    gecici = []
    if len(detay_fotolar) < 2 and gorsel_yollari:
        gecici = _kirpimlar(gorsel_yollari[0], klasor, 2 - len(detay_fotolar))
        detay_fotolar += gecici
    satirlar = [str(s).strip() for s in (taslak.get("carousel_lines") or []) if str(s).strip()]
    satirlar += [str(s) for s in (taslak.get("reels_lines") or [])] + [taslak.get("headline", "")]
    maddeler = [str(s).strip() for s in (taslak.get("carousel_points") or []) if str(s).strip()][:3]
    if len(maddeler) < 2:
        maddeler = musteri.carousel_maddeleri(proje=proje)
    toplam = 1 + len(detay_fotolar) + 1
    toplam = min(toplam, 10 if proje else EN_FAZLA)
    detay_fotolar = detay_fotolar[:toplam - 2]
    logo = marka.logolar()
    dosyalar = [klasor / "carousel_1.jpg"]
    shutil.copyfile(kapak, dosyalar[0])
    try:
        for i, foto in enumerate(detay_fotolar, 2):
            v = _varsayilan_degiskenler(tasarim.veri_hazirla(urun, [foto], taslak, tarif))
            v.update({"kart_tipi": "s-detay", "sayac": f"{i} / {toplam}", "t_noktalar": _noktalar(i, toplam),
                      "detay": satirlar[(i - 2) % len(satirlar)] if satirlar else taslak.get("headline", ""),
                      "logo_kart": tasarim._uri(logo["krem"] or logo["altin"]),
                      "madde1": "", "madde2": "", "madde3": "", "madde3_gizle": "gizli"})
            hedef = klasor / f"carousel_{i}.jpg"
            tasarim.ciz("carousel.html", v, hedef)
            dosyalar.append(hedef)
            gunluk(f"Carousel karti {i}/{toplam} hazir")
        v = _varsayilan_degiskenler(tasarim.veri_hazirla(urun, gorsel_yollari[:1], taslak, tarif))
        panel_koyu = _parlak(v["t_panel"]) < 0.5
        v.update({"kart_tipi": "s-son" + (" kisa" if any(len(m) > 34 for m in maddeler) else ""),
                  "sayac": f"{toplam} / {toplam}", "t_noktalar": _noktalar(toplam, toplam), "detay": "",
                  "logo_kart": tasarim._uri((logo["altin"] if panel_koyu else logo["koyu"]) or logo["altin"]),
                  "madde1": maddeler[0], "madde2": maddeler[1],
                  "madde3": maddeler[2] if len(maddeler) > 2 else "", "madde3_gizle": "" if len(maddeler) > 2 else "gizli"})
        hedef = klasor / f"carousel_{toplam}.jpg"
        tasarim.ciz("carousel.html", v, hedef)
        dosyalar.append(hedef)
    finally:
        for g in gecici:
            Path(g).unlink(missing_ok=True)
    return dosyalar
