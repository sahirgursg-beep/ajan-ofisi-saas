"""Urun sitesi / verisi olmayan isletmeler icin icerik kaynagi ("bizden veri").

Sektor profili + haftalik arastirma raporu + yapay zeka -> gunun icerik fikirleri. Her fikir, uretim hattinin
bekledigi 'urun' bicimine cevrilir (fiyatsiz): baslik, sutun (kategori), aciklama, gorseller.
Gorseller: isletmenin yukledigi fotograflar (projeler gibi) varsa onlar; yoksa stok (Pexels) + yapay zeka.
Ayni fikir 60 gun icinde tekrar kullanilmaz (pano.hazirlananlar).
"""
import hashlib
import json
import random

from . import arastirma, gorsel_kaynak, llm, musteri, pano, sektor
from .ayarlar import AYAR

TEKRAR_GUN = 60


def veri_yok_mu():
    """Urun kaynagi tanimli degil mi? (site/feed yok ya da profil bunu acikca istiyor)"""
    if AYAR.get("urun_kaynagi") == "fikir":
        return True
    site = (AYAR.get("site") or "").strip()
    return not AYAR.get("feed_url") and (not site or "example.com" in site)


def _adres(baslik):
    return "fikir://" + hashlib.sha1(baslik.lower().encode()).hexdigest()[:16]


def _fikir_listesi(adet):
    p = sektor.profil()
    r = arastirma.rapor()
    havuz = [sektor.doldur(f) for f in (r.get("fikirler") or []) + p.get("fikirler", [])]
    kullanilan = pano.son_hazirlananlar(TEKRAR_GUN)
    cevap = None
    if llm.hazir():
        cevap = llm.sor(
            f"You are the content strategist for {musteri.ad()}, {musteri.tanim()}. Answer ONLY with valid JSON.",
            f"{sektor.istem_ozeti()}{arastirma.istem_ozeti()}\nIdea bank:\n- " + "\n- ".join(havuz[:20])
            + f"\n\nPick or write {adet} DIFFERENT post ideas for today that this business can publish without new "
              "photos from the owner (we will use stock or AI imagery). Mix pillars; avoid ideas that need prices, "
              "real customer names or specific facts we don't know. "
              'Return JSON: {"ideas": [{"title": "<short title>", "pillar": "<content pillar>", '
              '"angle": "<one sentence>", "details": "<2-3 sentences of what the post says>", '
              '"stock_query": "<3-5 word Pexels search>", "ai_image_prompt": "<photorealistic scene, no text, '
              'no logos, no recognisable people>"}]}', json_mod=True, sicaklik=0.8)
    fikirler = [f for f in (cevap or {}).get("ideas", []) if isinstance(f, dict) and f.get("title")]
    if len(fikirler) < adet:     # yapay zeka yoksa / az verdiyse: bilgi bankasindan
        stok = p.get("stok") or ["small business"]
        for b in random.sample(havuz, len(havuz)):
            fikirler.append({"title": b, "pillar": random.choice(p["sutunlar"]), "angle": b, "details": b,
                             "stock_query": random.choice(stok),
                             "ai_image_prompt": f"Photorealistic {random.choice(stok)}, {p.get('gorsel', '')}, "
                                                "natural light, no text, no logos"})
    out = []
    for f in fikirler:
        if _adres(f["title"]) not in kullanilan and f["title"] not in [x["title"] for x in out]:
            out.append(f)
        if len(out) >= adet:
            break
    return out


def _gorseller(f, gunluk):
    yollar, kaynaklar, haric = [], [], set()
    try:
        for y, k in gorsel_kaynak.stok_ara(f.get("stock_query") or f["title"], adet=3, haric=haric):
            yollar.append(y)
            kaynaklar.append(k)
    except Exception as e:
        gunluk(f"Stok fotograf alinamadi ({type(e).__name__}): {str(e)[:80]}")
    if len(yollar) < 3:
        try:
            p = sektor.profil()
            y = gorsel_kaynak.yz_uret(
                f"{f.get('ai_image_prompt') or f['title']}. Style: {p.get('gorsel', '')}. "
                "Photorealistic, professional social media photo, vertical composition, no text, no watermark, "
                "no logos, no recognisable faces.")
            if y:
                yollar.insert(0, y)
                kaynaklar.insert(0, {"kaynak": "yapay_zeka"})
        except Exception as e:
            gunluk(f"Yapay zeka gorseli uretilemedi ({type(e).__name__}): {str(e)[:80]}")
    return yollar, kaynaklar


def fikir_urunleri(adet=3, gunluk=print):
    """Uretim hattina 'urun' gibi verilecek fikir icerikleri (gorselleri hazir)."""
    out = []
    for f in _fikir_listesi(adet + 2):
        yollar, kaynaklar = _gorseller(f, gunluk)
        if not yollar:
            continue
        out.append({"ad": f["title"][:80], "url": _adres(f["title"]), "fiyat": None, "eski_fiyat": None,
                    "kategori": f.get("pillar") or "", "aciklama": f.get("details") or f.get("angle") or "",
                    "aci": f.get("angle") or "", "gorseller": yollar, "gorsel_kaynaklari": kaynaklar,
                    "fikir": True, "fiyat_metni": "", "eski_fiyat_metni": "", "indirim_yuzde": 0, "ngn": None})
        if len(out) >= adet:
            break
    if not out:
        gunluk("Gorsel kaynagi yok: PEXELS_API_KEY ya da yapay zeka gorsel uretimi gerekli.")
    return out


def kaynak_notu(urun):
    """Pexels fotograflari icin metin sonuna eklenecek kisa kaynak notu (Pexels kosullari geregi nazik atif)."""
    ks = [k for k in urun.get("gorsel_kaynaklari") or [] if k.get("kaynak") == "pexels" and k.get("fotografci")]
    return ("Photo: " + ", ".join(sorted({k["fotografci"] for k in ks})) + " / Pexels") if ks else ""


def json_ozet(urun):
    return json.dumps({k: urun.get(k) for k in ("ad", "kategori", "aci", "gorsel_kaynaklari")}, ensure_ascii=False)
