"""Urun sitesi / verisi olmayan isletmeler icin icerik kaynagi ("bizden veri").

Sektor profili + haftalik arastirma raporu + yapay zeka -> gunun icerik fikirleri. Her fikir, uretim hattinin
bekledigi 'urun' bicimine cevrilir (fiyatsiz): baslik, sutun (kategori), aciklama, gorseller.
Gorseller: isletmenin yukledigi fotograflar (projeler gibi) varsa onlar; yoksa stok (Pexels) + yapay zeka.
Ayni fikir 60 gun icinde tekrar kullanilmaz (pano.hazirlananlar).
"""
import hashlib
import json
import os
import random

from . import arastirma, gorsel_kaynak, llm, marka_ozeti, musteri, pano, sektor
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
    from . import yuklemeler
    havuz = [sektor.doldur(f) for f in yuklemeler.belge_fikirleri() + (r.get("fikirler") or []) + p.get("fikirler", [])]
    kullanilan = pano.son_hazirlananlar(TEKRAR_GUN)
    o = marka_ozeti.ozet()
    cevap = None
    if llm.hazir():
        cevap = llm.sor(
            f"You are the content strategist for {musteri.ad()}, {musteri.tanim()}. You plan honest, useful "
            "posts that make people want to work with or buy from THIS business. Answer ONLY with valid JSON.",
            f"{marka_ozeti.istem_ozeti()}{sektor.istem_ozeti()}{arastirma.istem_ozeti()}\nIdea bank:\n- "
            + "\n- ".join(havuz[:20])
            + f"\n\nWrite {adet} DIFFERENT post ideas for today. Mix pillars (education/tips, behind the scenes, "
              "how it works, invitation/offer, community). Each idea must be about THIS business and its own "
              "offer, written for its customers. No invented customers, case studies, statistics or results. "
              "Never propose an idea that needs photos of specific real people or places we do not have - the "
              "team, founders, engineers, staff, the office, customers, events ('meet the team', 'behind the "
              "scenes with our engineers'): a stock or AI photo of strangers would mislead. Build ideas around "
              "the product, its benefits, how it works, tips and the customer's everyday situation instead. "
              "The photo must show the business's own world (see VISUALS above) - e.g. a social media agency is "
              "shown with phones, laptops, planning boards and content creation, never as a clothing shop. "
              'Return JSON: {"ideas": [{"title": "<short title>", "pillar": "<content pillar>", '
              '"angle": "<one sentence>", "details": "<2-3 sentences of what the post says>", '
              '"stock_queries": ["<3 DIFFERENT concrete stock photo searches, 2-4 words each, nouns a camera can '
              'see (people/objects/place/action), e.g. \'barista pouring latte art\', never abstract words like '
              'success or growth>"], "must_show": "<what the photo must show, one sentence>", '
              '"avoid": "<what would be wrong for this business, a few words>", '
              '"ai_image_prompt": "<photorealistic scene of the business\'s own world, no text, no logos, '
              'no recognisable faces>"}]}', json_mod=True, sicaklik=0.7)
    fikirler = [_duzle(f) for f in (cevap or {}).get("ideas", []) if isinstance(f, dict) and f.get("title")]
    if len(fikirler) < adet:     # yapay zeka yoksa / az verdiyse: bilgi bankasindan
        stok = o.get("stok_terimleri") or p.get("stok") or ["small business"]
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


def _metin(x):
    if isinstance(x, (list, tuple)):
        return " ".join(_metin(y) for y in x if y)
    if isinstance(x, dict):
        return " ".join(_metin(y) for y in x.values() if y)
    return str(x or "").strip()


def _duzle(f):
    """Yapay zeka bazen alanlari liste/sozluk dondurur: hepsi duz metne."""
    d = {k: _metin(f.get(k)) for k in ("title", "pillar", "angle", "details", "stock_query", "ai_image_prompt",
                                       "must_show", "avoid")}
    q = f.get("stock_queries")
    d["stock_queries"] = [_metin(x) for x in (q if isinstance(q, list) else [q] if q else []) if _metin(x)][:4]
    if d["stock_query"] and d["stock_query"] not in d["stock_queries"]:
        d["stock_queries"].append(d["stock_query"])
    return d


def _gorseller(f, gunluk):
    """Birden fazla aramadan adaylar -> gorme modeli konuya uyanlari secer (gorsel_secici). Iyi aday yetmezse
    yapay zeka gorseli tamamlar."""
    yollar, kaynaklar = [], []
    try:
        from . import gorsel_secici
        secilen, _ = gorsel_secici.sec(f.get("stock_queries") or [f.get("stock_query") or f["title"]],
                                       f"{f['title']}. {f.get('must_show') or f.get('angle') or ''}",
                                       f"{musteri.ad()}, {musteri.tanim()}", adet=3, kacin=f.get("avoid", ""),
                                       gunluk=gunluk)
        for y, k, _ in secilen:
            yollar.append(y)
            kaynaklar.append(k)
    except Exception as e:
        gunluk(f"Stok fotograf alinamadi ({type(e).__name__}): {str(e)[:80]}")
    if len(yollar) < 3:
        # Carousel her kartta farkli gorsel ister: eksik kalan her yer icin farkli acidan bir yapay zeka gorseli
        try:
            from . import gorsel_secici
            p = sektor.profil()
            taban = (f"{f.get('ai_image_prompt') or f['title']}. Style: {p.get('gorsel', '')}. "
                     "Photorealistic, professional social media photo, vertical composition, no text, no letters, "
                     "no watermark, no logos, no recognisable faces, no screens or monitors showing text or UI, "
                     "no close-up hands.")
            acilar = ("", " Different shot: a close-up detail of the key object.",
                      " Different shot: a wide environmental view with soft natural light.")
            uretim = 0                                   # fikir basina en fazla 2 uretim (aylik gorsel hakki)
            for aci in acilar[:3 - len(yollar)]:
                istem = taban + aci
                for deneme in range(2):
                    if uretim >= 2:
                        break
                    y = gorsel_kaynak.yz_uret(istem)
                    if not y:
                        break
                    uretim += 1
                    # Yapay zeka gorseli de ayni hakemden gecer: anlamsiz yazi/bozuk el varsa kullanilmaz
                    puan = gorsel_secici.puanla([y], f["title"], f"{musteri.ad()}, {musteri.tanim()}",
                                                "any visible text or letters, garbled writing, distorted hands")
                    skor = (puan or {}).get(0) if puan is not None else None
                    gunluk(f"[GORSEL] yapay zeka gorseli puani: {skor}")
                    if skor is None or skor >= 6:
                        (yollar.insert(0, y), kaynaklar.insert(0, {"kaynak": "yapay_zeka"})) if not yollar or aci == "" \
                            else (yollar.append(y), kaynaklar.append({"kaynak": "yapay_zeka"}))
                        break
                    istem += " Absolutely no writing of any kind anywhere in the image."
        except Exception as e:
            gunluk(f"Yapay zeka gorseli uretilemedi ({type(e).__name__}): {str(e)[:80]}")
    return yollar, kaynaklar


def fikir_urunleri(adet=3, gunluk=print):
    """Uretim hattina 'urun' gibi verilecek fikir icerikleri (gorselleri hazir)."""
    out = []
    if os.environ.get("AJAN_ONIZLEME"):
        adet = 1
    fikirler = _fikir_listesi(adet + 2)
    # Ilk fikirlerin gorselleri ayni anda toplanir (ag + gorme modeli beklemesi); yedekler gerekirse sirayla
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as h:
        hazir = dict(zip(range(adet), h.map(lambda f: _gorseller(f, gunluk), fikirler[:adet])))
    for i, f in enumerate(fikirler):
        yollar, kaynaklar = hazir[i] if i in hazir else _gorseller(f, gunluk)
        if not yollar:
            continue
        out.append({"ad": f["title"][:80], "url": _adres(f["title"]), "fiyat": None, "eski_fiyat": None,
                    "kategori": f.get("pillar") or "", "aciklama": f.get("details") or f.get("angle") or "",
                    "aci": f.get("angle") or "", "gorseller": yollar, "gorsel_kaynaklari": kaynaklar,
                    "fikir": True, "fiyat_metni": "", "eski_fiyat_metni": "", "indirim_yuzde": 0, "ngn": None})
        if len(out) >= adet:
            break
    if not out:
        gunluk("Gorsel kaynagi yok: PIXABAY_API_KEY ya da yapay zeka gorsel uretimi gerekli.")
    return out


def kaynak_notu(urun):
    """Pexels fotograflari icin metin sonuna eklenecek kisa kaynak notu (Pexels kosullari geregi nazik atif)."""
    ks = [k for k in urun.get("gorsel_kaynaklari") or [] if k.get("kaynak") == "pexels" and k.get("fotografci")]
    return ("Photo: " + ", ".join(sorted({k["fotografci"] for k in ks})) + " / Pexels") if ks else ""


def json_ozet(urun):
    return json.dumps({k: urun.get(k) for k in ("ad", "kategori", "aci", "gorsel_kaynaklari")}, ensure_ascii=False)
