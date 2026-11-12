"""Musterinin panelden yukledigi dosyalar: fotograflar ve belgeler (menu, brosur, fiyat listesi...).

Klasor: musteriler/<id>/yuklemeler/  (isci depodan indirir)  +  index.json (panel ve isci ortak kaydi):
  [{"id", "dosya", "ad", "tur": "gorsel"|"belge", "not": "<sahibin notu>", "tarih", "analiz": {...},
    "kullanim": [{"tarih", "klasor"}]}]
1) incele(): analiz edilmemis dosyalar yapay zekayla incelenir
     gorsel -> ne gorunuyor, hangi tur (urun, hizmet ani, mekan, ekip, proje, once/sonra, menu...), paylasilabilir mi
     belge  -> metni cikarilir; ozet, somut bilgiler, icerik fikirleri
2) kaynak_urunleri(): paylasilmamis fotograflardan uretim hattinin bekledigi 'urun' bicimi (fiyatsiz, gercek
   foto). Sahibin yukledigi fotograflar her zaman once kullanilir.
3) belge_gercekleri()/belge_fikirleri(): isletme ozetine ve fikir havuzuna eklenir.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from . import llm, musteri
from .ayarlar import MUSTERI_KOK, VERI

KLASOR = MUSTERI_KOK / "yuklemeler"
INDEX = KLASOR / "index.json"
ONBELLEK = VERI / "yukleme_onbellek"
GORSEL = {".jpg", ".jpeg", ".png", ".webp"}
BELGE = {".pdf", ".txt", ".md", ".csv"}
PAYLASILIR = {"urun", "hizmet_ani", "mekan", "ekip", "proje", "once_sonra", "menu", "etkinlik", "diger"}


def oku():
    try:
        d = json.loads(INDEX.read_text(encoding="utf-8"))
        return [x for x in d if isinstance(x, dict) and x.get("dosya")] if isinstance(d, list) else []
    except Exception:
        return []


def yaz(kayitlar):
    KLASOR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(kayitlar, ensure_ascii=False, indent=1), encoding="utf-8")


def _yol(k):
    return KLASOR / Path(k["dosya"]).name


def _belge_metni(yol, sinir=12000):
    uz = yol.suffix.lower()
    if uz == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print("  ! pypdf kurulu degil; PDF okunamadi")
            return ""
        try:
            r = PdfReader(str(yol))
            return "\n".join((s.extract_text() or "") for s in r.pages[:15])[:sinir]
        except Exception as e:
            print(f"  ! PDF okunamadi: {e}")
            return ""
    try:
        return yol.read_text(encoding="utf-8", errors="replace")[:sinir]
    except Exception:
        return ""


def _gorsel_incele(k):
    yol = _yol(k)
    i = musteri.bilgi()
    cevap = llm.gor(
        "You look at photos a small business uploaded for its social media and describe them factually. "
        "Answer ONLY with valid JSON.",
        f"Business: {musteri.ad()} - {musteri.tanim()}. Offers: {', '.join(i.get('hizmetler') or []) or '-'}\n"
        f"Owner's note for this photo: {k.get('not') or '-'}\n"
        'Return JSON: {"baslik": "<short post title, max 8 words>", '
        '"tur": "<one of: urun, hizmet_ani, mekan, ekip, proje, once_sonra, menu, etkinlik, belge, diger>", '
        '"aciklama": "<what is visible, factual, 1-2 sentences, no guesses about prices or brands>", '
        '"icerik_fikri": "<one sentence: how to use it in a post>", '
        '"grup": "<2-4 word key: same product/project/event photos share the same key>", '
        '"uygun": <true if it is a real photo good enough to post (not blurry, not a screenshot, no documents '
        'with personal data, no children\'s faces)>}', [yol])
    if not isinstance(cevap, dict) or not cevap.get("baslik"):
        not_ = (k.get("not") or "").strip()
        return {"baslik": (not_ or f"From {musteri.ad()}")[:60], "tur": "diger", "aciklama": not_,
                "icerik_fikri": not_, "grup": k["id"], "uygun": True, "kaynak": "not"}
    tur = str(cevap.get("tur") or "diger").strip().lower()
    return {"baslik": str(cevap.get("baslik"))[:80], "tur": tur if tur in PAYLASILIR | {"belge"} else "diger",
            "aciklama": str(cevap.get("aciklama") or "")[:400], "icerik_fikri": str(cevap.get("icerik_fikri") or "")[:300],
            "grup": re.sub(r"\s+", " ", str(cevap.get("grup") or k["id"]).lower())[:40],
            "uygun": cevap.get("uygun") is not False, "kaynak": "yapay_zeka"}


def _belge_incele(k):
    metin = _belge_metni(_yol(k))
    if not metin.strip():
        return {"ozet": k.get("not") or "", "gercekler": [], "fikirler": [], "kaynak": "bos"}
    if not llm.hazir():
        return {"ozet": metin[:300], "gercekler": [], "fikirler": [], "kaynak": "metin"}
    cevap = llm.sor(
        "You read a document a small business uploaded (menu, price list, brochure, company profile) and extract "
        "what its social media team can use. Never invent. Answer ONLY with valid JSON.",
        f"Business: {musteri.ad()} - {musteri.tanim()}\nOwner's note: {k.get('not') or '-'}\n"
        f"Document text:\n{metin}\n\n"
        '{"ozet": "<what this document is, 1 sentence>", '
        '"gercekler": ["<up to 12 concrete facts: products/services with prices if written, opening hours, '
        'locations, offers, years, certifications>"], '
        '"fikirler": ["<up to 6 post ideas based only on this document>"]}', json_mod=True, sicaklik=0.2)
    if not isinstance(cevap, dict):
        return {"ozet": metin[:300], "gercekler": [], "fikirler": [], "kaynak": "metin"}
    duz = lambda xs: [str(x)[:200] for x in (xs or []) if str(x).strip()]
    return {"ozet": str(cevap.get("ozet") or "")[:300], "gercekler": duz(cevap.get("gercekler"))[:12],
            "fikirler": duz(cevap.get("fikirler"))[:6], "kaynak": "yapay_zeka"}


def incele(gunluk=print):
    """Analizi olmayan yuklemeleri inceler, index.json'a yazar. -> incelenen sayisi"""
    kayitlar, n = oku(), 0
    for k in kayitlar:
        if k.get("analiz") or not _yol(k).exists():
            continue
        try:
            k["analiz"] = _gorsel_incele(k) if k.get("tur") == "gorsel" else _belge_incele(k)
            n += 1
        except Exception as e:
            gunluk(f"Yukleme incelenemedi ({k.get('ad')}): {type(e).__name__}")
    if n:
        yaz(kayitlar)
        gunluk(f"{n} yeni dosya incelendi.")
    return n


def _hazir(yol):
    from PIL import Image, ImageOps
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    hedef = ONBELLEK / (yol.stem + ".jpg")
    if not hedef.exists():
        im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
        im.thumbnail((2000, 2000))
        im.save(hedef, "JPEG", quality=92)
    return str(hedef)


def kaynak_urunleri(adet=3, en_az_foto=1):
    """Paylasilmamis, paylasilabilir fotograflar -> 'urun' sozlukleri (ayni grup tek icerik, en fazla 8 foto)."""
    gruplar = {}
    for k in oku():
        a = k.get("analiz") or {}
        if k.get("tur") != "gorsel" or k.get("kullanim") or not a.get("uygun", True) or not _yol(k).exists():
            continue
        if a.get("tur") == "belge":
            continue
        gruplar.setdefault(a.get("grup") or k["id"], []).append(k)
    out = []
    for anahtar, ks in sorted(gruplar.items(), key=lambda kv: min(x.get("tarih", "") for x in kv[1])):
        if len(ks) < en_az_foto:
            continue
        a = ks[0].get("analiz") or {}
        yollar = []
        for k in ks[:8]:
            try:
                yollar.append(_hazir(_yol(k)))
            except Exception as e:
                print(f"  ! yukleme hazirlanamadi {k.get('ad')}: {e}")
        if not yollar:
            continue
        notlar = " ".join(x.get("not", "") for x in ks if x.get("not"))
        out.append({"ad": a.get("baslik") or f"From {musteri.ad()}", "url": "yukleme://" + anahtar,
                    "yukleme": True, "yukleme_idler": [k["id"] for k in ks], "fikir": True, "fiyat": None,
                    "eski_fiyat": None, "kategori": a.get("tur") or "",
                    "aciklama": " ".join(x for x in (a.get("aciklama"), notlar) if x)[:500],
                    "aci": a.get("icerik_fikri") or "", "gorseller": yollar, "fiyat_metni": "",
                    "eski_fiyat_metni": "", "indirim_yuzde": 0, "ngn": None,
                    "gorsel_kaynaklari": [{"kaynak": "musteri"}]})
        if len(out) >= adet:
            break
    return out


def kullanildi(urun, klasor):
    if not urun.get("yukleme"):
        return
    kayitlar = oku()
    idler = set(urun.get("yukleme_idler") or [])
    for k in kayitlar:
        if k["id"] in idler:
            k.setdefault("kullanim", []).append({"tarih": datetime.now().strftime("%Y-%m-%d"),
                                                 "klasor": Path(klasor).name})
    yaz(kayitlar)


def belge_gercekleri():
    return [g for k in oku() if k.get("tur") == "belge" for g in (k.get("analiz") or {}).get("gercekler", [])][:20]


def belge_fikirleri():
    return [f for k in oku() if k.get("tur") == "belge" for f in (k.get("analiz") or {}).get("fikirler", [])][:12]
