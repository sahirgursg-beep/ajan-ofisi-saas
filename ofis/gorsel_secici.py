"""Gorsel Secici: stok fotograflar arasindan konuya gercekten uyanlari secer.

Eski yol: ilk arama sonucunun ilk 3 fotografi -> isabet ~%50. Yeni yol:
  1. Birden fazla somut aramadan 12-16 aday toplanir (yalnizca kucuk onizlemeler indirilir).
  2. Adaylar numarali tek bir temas sayfasina dizilir; gorme modeli her birini konuya, isletmenin dunyasina,
     kaliteye ve yasaklara (yazi/filigran, alakasiz sahne, yapay poz) gore 0-10 puanlar.
  3. 7 ve ustu alanlar secilir (en iyiler once); yetmezse yapay zeka gorseli tamamlar (cagiran taraf).
Gorme modeli yoksa aday sirasi korunur (eski davranis) ve bu durum kayda yazilir.
"""
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import gorsel_kaynak, llm
from .ayarlar import VERI

ESIK = 7
HUCRE = (300, 375)
KAYIT = VERI / "gorsel_secim.json"


def _font(boyut):
    for ad in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(ad, boyut)
        except Exception:
            continue
    return ImageFont.load_default()


def temas_sayfasi(yollar, hedef):
    """Numarali izgara (4 sutun). Gorme modeli tek istekte hepsini gorur."""
    sutun = 4
    satir = (len(yollar) + sutun - 1) // sutun
    W, H = HUCRE
    sayfa = Image.new("RGB", (sutun * W, satir * H), "white")
    ciz = ImageDraw.Draw(sayfa)
    f = _font(34)
    for i, y in enumerate(yollar):
        try:
            im = Image.open(y).convert("RGB")
        except Exception:
            continue
        im = _kapla(im, W - 8, H - 8)
        x, yy = (i % sutun) * W + 4, (i // sutun) * H + 4
        sayfa.paste(im, (x, yy))
        ciz.rectangle((x, yy, x + 58, yy + 50), fill="black")
        ciz.text((x + 10, yy + 6), str(i + 1), fill="white", font=f)
    sayfa.save(hedef, "JPEG", quality=82)
    return hedef


def _kapla(im, w, h):
    oran = max(w / im.width, h / im.height)
    im = im.resize((max(1, int(im.width * oran)), max(1, int(im.height * oran))))
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def puanla(yollar, konu, isletme, kacin=""):
    """-> {sira(0'dan): puan} ya da None (gorme modeli yok)."""
    if not yollar:
        return {}
    sayfa = temas_sayfasi(yollar, VERI / "_temas.jpg")
    cevap = llm.gor(
        "You are the photo editor of a social media agency. You pick photos that a real customer of this business "
        "would instantly connect with. Answer ONLY with valid JSON.",
        f"Business: {isletme}\nThis post is about: {konu}\n"
        + (f"Avoid: {kacin}\n" if kacin else "")
        + f"The sheet shows {len(yollar)} numbered candidate photos. Score EVERY photo 0-10:\n"
        "10 = clearly shows this exact topic in this business's real world, natural, high quality, room for text;\n"
        "7 = good fit, a customer would find it relevant;\n"
        "4 = generic or only loosely related;\n"
        "0 = wrong subject, wrong industry, visible text/watermark/logo, cheesy staged stock pose, low quality.\n"
        'Return JSON: {"scores": [{"no": 1, "score": 0-10, "why": "<5 words>"}]}',
        [sayfa])
    if not isinstance(cevap, dict):
        return None
    out = {}
    for s in cevap.get("scores") or []:
        try:
            no, puan = int(s.get("no")) - 1, float(s.get("score"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= no < len(yollar):
            out[no] = max(0.0, min(10.0, puan))
    return out


def sec(sorgular, konu, isletme, adet=3, kacin="", haric=(), gunluk=print):
    """-> (secilenler [(yerel_yol, kaynak_bilgisi, puan)], rapor). Secilen buyuk fotograf indirilir."""
    adaylar, gorulen = [], set(haric)
    for q in [q for q in sorgular if q][:4]:
        for a in gorsel_kaynak.stok_adaylar(q, adet=6, haric=gorulen):
            if a["id"] not in gorulen:
                gorulen.add(a["id"])
                adaylar.append(a)
        if len(adaylar) >= 16:
            break
    adaylar = adaylar[:16]
    def _kucuk(a):
        try:
            return gorsel_kaynak.indir(a["onizleme"])
        except Exception:
            return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as h:
        inen = list(h.map(_kucuk, adaylar))
    kucukler = [y for y in inen if y]
    gecerli = [a for a, y in zip(adaylar, inen) if y]
    puanlar = puanla(kucukler, konu, isletme, kacin) if gecerli else {}
    rapor = {"aday": len(gecerli), "gorme": puanlar is not None}
    if puanlar is None:                        # gorme modeli yok: eski davranis (aday sirasi)
        sira = list(range(len(gecerli)))[:adet]
        rapor["not"] = "gorme modeli yok, ilk adaylar alindi"
    else:
        sira = [i for i, _ in sorted(puanlar.items(), key=lambda x: -x[1]) if puanlar[i] >= ESIK][:adet]
        rapor["puanlar"] = sorted((round(p, 1) for p in puanlar.values()), reverse=True)
    secilen = []
    for i in sira:
        try:
            secilen.append((gorsel_kaynak.indir(gecerli[i]["buyuk"]), gecerli[i]["bilgi"],
                            (puanlar or {}).get(i)))
        except Exception as e:
            gunluk(f"Fotograf indirilemedi: {str(e)[:80]}")
    rapor["secilen"] = [p for _, _, p in secilen]
    gunluk(f"[GORSEL] '{konu[:50]}': {rapor['aday']} aday, secilen puanlar {rapor['secilen']}"
           + ("" if rapor["gorme"] else " (gorme modeli yok)"))
    try:
        gecmis = json.loads(KAYIT.read_text(encoding="utf-8")) if KAYIT.exists() else []
        KAYIT.write_text(json.dumps((gecmis + [{"konu": konu[:80], **rapor}])[-200:], ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return secilen, rapor
