"""Isletmenin sektorunu bulur ve o isletmeye ozel sektor profilini hazirlar.

Girdi: musterinin tek cumlelik tanimi (isletme.tanim), adi, sehri; varsa isletme.sektor anahtari.
1) Anahtar kelimelerle en yakin sektor (her zaman calisir)
2) Yapay zeka varsa: sektoru dogrular ve bu isletmeye ozel bir profil uretir (kitle, ton, icerik sutunlari,
   fikirler, kancalar, gorsel stil, stok arama terimleri) -> taban sektor bilgisinin ustune yazilir.
Sonuc veri/sektor_profili.json'da saklanir; tanim degisince yeniden uretilir.
"""
import hashlib
import json
import re

from . import llm, musteri, sektor_bilgi
from .ayarlar import AYAR, VERI

YOL = VERI / "sektor_profili.json"
LISTE_ALANLARI = ("sutunlar", "fikirler", "kancalar", "stok", "hashtag")


def _tanim_metni():
    i = musteri.bilgi()
    return " | ".join(x for x in (i.get("ad"), i.get("tanim"), i.get("urun_turu"), i.get("sektor"),
                                  " ".join(AYAR.get("kategoriler") or [])) if x)


def _imza():
    return hashlib.sha1((_tanim_metni() + "|v2").encode()).hexdigest()[:12]


def kelime_ile_bul(metin):
    """En cok anahtar kelime eslesen sektor; yoksa 'genel'."""
    m = (metin or "").lower()
    en_iyi, puan = "genel", 0
    for k, s in sektor_bilgi.SEKTORLER.items():
        p = sum(len(w) for w in s["kelimeler"] if re.search(r"(?<![a-z])" + re.escape(w.lower()) + r"(?![a-z])", m))
        if p > puan:
            en_iyi, puan = k, p
    return en_iyi


def _yz_profil(taban_anahtar):
    liste = "\n".join(f"- {k}: {v}" for k, v in sektor_bilgi.liste().items())
    i = musteri.bilgi()
    cevap = llm.sor(
        "You are a senior social media strategist who has run accounts for every kind of business. "
        "Answer ONLY with valid JSON.",
        f"Business: {i.get('ad')}\nDescription from the owner: {i.get('tanim') or '-'}\n"
        f"Location: {musteri.sehirler_metni()}, {i.get('ulke') or ''}\n"
        f"Sales channel: {musteri.satis_kanali()}\n\nKnown sector keys:\n{liste}\n\n"
        f"Keyword guess: {taban_anahtar}.\n"
        "1) Pick the closest sector key (or 'genel' if none fits).\n"
        "2) Write a profile tailored to THIS business (not generic), in English:\n"
        '{"sektor": "<key>", "alt_sektor": "<short niche name>", "kitle": "<target audience>", '
        '"ton": "<brand voice, 3-5 words>", "sutunlar": ["<5-6 content pillars>"], '
        '"fikirler": ["<10 concrete post ideas for this business, may use {city}>"], '
        '"kancalar": ["<5 scroll-stopping hooks>"], "gorsel": "<visual style direction>", '
        '"stok": ["<6 stock photo search terms that fit this business>"], '
        '"hashtag": ["<6 hashtag roots without #>"], "dikkat": "<legal/ethical cautions for this niche or empty>", '
        '"urun_odakli": <true if they sell physical products>, "b2b": <true if mainly selling to businesses>}',
        json_mod=True, sicaklik=0.4)
    return cevap if isinstance(cevap, dict) else None


def profil(yenile=False):
    """Bu isletmenin sektor profili (taban + isletmeye ozel)."""
    imza = _imza()
    if not yenile:
        try:
            d = json.loads(YOL.read_text(encoding="utf-8"))
            if d.get("_imza") == imza:
                return d
        except Exception:
            pass
    i = musteri.bilgi()
    anahtar = i.get("sektor") if i.get("sektor") in sektor_bilgi.SEKTORLER else kelime_ile_bul(_tanim_metni())
    p = json.loads(json.dumps(sektor_bilgi.al(anahtar)))
    p["anahtar"], p["kaynak"] = anahtar, "kelime"
    ozel = _yz_profil(anahtar) if llm.hazir() else None
    if ozel:
        if ozel.get("sektor") in sektor_bilgi.SEKTORLER and ozel["sektor"] != anahtar:
            anahtar = ozel["sektor"]
            p = {**json.loads(json.dumps(sektor_bilgi.al(anahtar))), "anahtar": anahtar}
        for k in ("kitle", "ton", "gorsel", "dikkat", "alt_sektor"):
            if isinstance(ozel.get(k), str) and ozel[k].strip():
                p[k] = ozel[k].strip()[:400]
        for k in LISTE_ALANLARI:
            v = [str(x).strip() for x in (ozel.get(k) or []) if str(x).strip()]
            if v:
                p[k] = (v + [x for x in p.get(k, []) if x not in v])[:12]
        for k in ("urun_odakli", "b2b"):
            if isinstance(ozel.get(k), bool):
                p[k] = ozel[k]
        p["kaynak"] = "yapay_zeka"
    p["_imza"] = imza
    YOL.parent.mkdir(parents=True, exist_ok=True)
    YOL.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def doldur(metin):
    i = musteri.bilgi()
    return (str(metin).replace("{city}", (i.get("sehirler") or [i.get("ulke") or "your city"])[0])
            .replace("{business}", musteri.ad()).replace("{product_type}", i.get("urun_turu") or "piece"))


def istem_ozeti():
    """Ajan istemlerine eklenen kisa sektor bilgisi."""
    p = profil()
    satirlar = [f"\nSector: {p['ad']}" + (f" / {p['alt_sektor']}" if p.get("alt_sektor") else ""),
                f"Audience: {p['kitle']}", f"Brand voice: {p['ton']}",
                f"Content pillars: {', '.join(p['sutunlar'][:6])}", f"Visual direction: {p['gorsel']}"]
    if p.get("dikkat"):
        satirlar.append(f"Cautions: {p['dikkat']}")
    return "\n".join(satirlar) + "\n"
