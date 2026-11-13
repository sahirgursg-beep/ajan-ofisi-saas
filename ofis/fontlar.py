"""Sanat Yonetmeni'nin yazi tipi kutuphanesi: reklam ajansi tarzinda genis bir secim.

Her cift: baslik (display) + govde fontu ve tipografik davranis:
  bw  baslik kalinligi        bt  buyuk/kucuk harf (none | uppercase)
  bls harf araligi            bo  boyut carpani (dar/genis fontlari esitler)
  his ajansin dilinde ne anlatir (Sanat Yonetmeni bunu okuyup secer)
  uygun hangi sektor/ruh haline yakisir (oneri, kural degil)
Tum fontlar Google Fonts'tan (ucretsiz, ticari kullanima acik). Sablonlardaki .f-<anahtar> siniflari
buradan uretilir; yeni cift eklemek icin yalnizca bu tabloya satir eklemek yeterli.
"""
import hashlib
import json
import os
from pathlib import Path

YEDEK_SERIF = 'Georgia,"DejaVu Serif",serif'
YEDEK_SANS = '"Segoe UI","DejaVu Sans",sans-serif'
YEDEK_DAR = 'Impact,"Arial Narrow","DejaVu Sans Condensed",sans-serif'


YEDEK_ARAP = '"Noto Sans Arabic","DejaVu Sans",sans-serif'


def C(bf, bf_yedek, gf, bw, bt, bls, bo, his, uygun, alfabe=("latin",)):
    return {"bf": bf, "bf_yedek": bf_yedek, "gf": gf, "bw": bw, "bt": bt, "bls": bls, "bo": bo, "his": his,
            "uygun": uygun, "alfabe": list(alfabe)}


CIFTLER = {
    # ---- klasik / luks ----
    "klasik": C("Cormorant Garamond", YEDEK_SERIF, "Montserrat", 600, "none", "0", 1, "classic luxury serif", "furniture, hotels, jewellery, weddings", ("latin", "cyrillic", "vietnamese")),
    "modern": C("Playfair Display", YEDEK_SERIF, "Inter", 700, "none", "-.01em", 1, "modern editorial serif", "fashion, interiors, real estate", ("latin", "cyrillic", "vietnamese")),
    "zarif": C("Marcellus", YEDEK_SERIF, "Jost", 400, "uppercase", ".06em", .82, "refined spaced capitals", "spa, beauty, premium services"),
    "editoryal": C("DM Serif Display", YEDEK_SERIF, "DM Sans", 400, "none", "-.01em", 1.05, "magazine headline", "lifestyle, food, culture"),
    "moda_luks": C("Bodoni Moda", YEDEK_SERIF, "Manrope", 700, "none", "-.02em", 1.02, "high-fashion Didone, Vogue-like contrast", "fashion, beauty, luxury retail"),
    "antik": C("Cinzel", YEDEK_SERIF, "Raleway", 600, "uppercase", ".08em", .8, "carved Roman capitals, heritage and trust", "law, finance, faith, heritage brands"),
    "dergi": C("Abril Fatface", YEDEK_SERIF, "Lato", 400, "none", "0", 1.05, "fat-face magazine cover drama", "events, culture, food, fashion"),
    "sicak_serif": C("Fraunces", YEDEK_SERIF, "Work Sans", 800, "none", "-.02em", 1, "warm soft serif with personality", "cafes, bakeries, crafts, family brands"),
    # ---- kampanya / afis ----
    "cesur": C("Bebas Neue", YEDEK_DAR, "Montserrat", 400, "uppercase", ".02em", 1.25, "bold campaign capitals", "sales, sports, events"),
    "afis": C("Anton", YEDEK_DAR, "Inter", 400, "uppercase", ".01em", 1.2, "tall condensed poster type, billboard energy", "promotions, gyms, launches, nightlife"),
    "brutal": C("Archivo Black", YEDEK_SANS, "Archivo", 400, "uppercase", "-.01em", .95, "heavy brutalist grotesk, loud and confident", "streetwear, tech launches, bold offers"),
    "sokak": C("Bowlby One", YEDEK_SANS, "Rubik", 400, "uppercase", "0", .9, "chunky street-poster type", "food trucks, barbers, youth brands"),
    # ---- cagdas / teknoloji ----
    "cagdas": C("Bricolage Grotesque", YEDEK_SANS, "Figtree", 800, "none", "-.03em", 1.05, "contemporary characterful grotesk", "startups, agencies, modern services"),
    "teknoloji": C("Space Grotesk", YEDEK_SANS, "IBM Plex Sans", 700, "none", "-.02em", 1, "technical, precise, future-facing", "software, electronics, fintech, solar"),
    "sanatsal": C("Syne", YEDEK_SANS, "Manrope", 800, "none", "-.02em", 1, "art-gallery avant-garde", "studios, photography, design, music"),
    "kurumsal": C("Sora", YEDEK_SANS, "Source Sans 3", 600, "none", "-.01em", 1, "clean corporate confidence", "consulting, B2B, logistics, health"),
    # ---- samimi / eglenceli ----
    "samimi": C("Nunito", YEDEK_SANS, "Nunito", 800, "none", "-.01em", 1.05, "rounded and friendly", "clinics, schools, cleaning, pets"),
    "oyuncu": C("Fredoka", YEDEK_SANS, "Nunito", 600, "none", "0", 1.08, "playful bubbly rounded", "kids, toys, sweets, family events"),
    "retro": C("Shrikhand", YEDEK_SERIF, "DM Sans", 400, "none", "0", .95, "70s retro display with swagger", "restaurants, drinks, lounges, music"),
    "diner": C("Righteous", YEDEK_SANS, "Poppins", 400, "uppercase", ".02em", 1, "diner/retro-futurist signage", "fast food, grills, car culture"),
    "el_yazisi": C("Permanent Marker", YEDEK_SANS, "Nunito", 400, "none", "0", 1, "hand-written marker, human and spontaneous", "small shops, crafts, community, tips"),
    # ---- Arap alfabesi (Arapca, Farsca, Urduca icerikler) ----
    "arap_modern": C("Cairo", YEDEK_ARAP, "Tajawal", 800, "none", "0", 1, "bold modern Arabic sans, clean and confident", "retail, tech, services, offers", ("arabic", "latin")),
    "arap_klasik": C("Amiri", YEDEK_ARAP, "Noto Naskh Arabic", 700, "none", "0", 1.05, "classic Naskh calligraphic elegance", "luxury, perfume, hospitality, heritage", ("arabic",)),
}

GOOGLE = {   # Google Fonts css2 aile ifadeleri (yalnizca var olan agirliklar: tek bir hata tum istegi bozar)
    "Cormorant Garamond": "Cormorant+Garamond:ital,wght@0,500;0,600;1,500", "Montserrat": "Montserrat:wght@400;500;600;700;800",
    "Playfair Display": "Playfair+Display:ital,wght@0,700;1,500", "Inter": "Inter:wght@400;600;700", "Bebas Neue": "Bebas+Neue",
    "Marcellus": "Marcellus", "Jost": "Jost:wght@400;600", "DM Serif Display": "DM+Serif+Display:ital@0;1",
    "DM Sans": "DM+Sans:wght@400;600;700", "Bodoni Moda": "Bodoni+Moda:ital,wght@0,500;0,700;1,500", "Manrope": "Manrope:wght@400;600;800",
    "Cinzel": "Cinzel:wght@600;700", "Raleway": "Raleway:wght@400;600", "Abril Fatface": "Abril+Fatface", "Lato": "Lato:wght@400;700",
    "Fraunces": "Fraunces:wght@600;800", "Work Sans": "Work+Sans:wght@400;600", "Anton": "Anton", "Archivo Black": "Archivo+Black",
    "Archivo": "Archivo:wght@400;600", "Bowlby One": "Bowlby+One", "Rubik": "Rubik:wght@400;600",
    "Bricolage Grotesque": "Bricolage+Grotesque:wght@700;800", "Figtree": "Figtree:wght@400;600",
    "Space Grotesk": "Space+Grotesk:wght@500;700", "IBM Plex Sans": "IBM+Plex+Sans:wght@400;600", "Syne": "Syne:wght@700;800",
    "Sora": "Sora:wght@400;600", "Source Sans 3": "Source+Sans+3:wght@400;600", "Nunito": "Nunito:wght@400;600;800",
    "Fredoka": "Fredoka:wght@400;600", "Shrikhand": "Shrikhand", "Righteous": "Righteous", "Poppins": "Poppins:wght@400;600",
    "Permanent Marker": "Permanent+Marker",
    "Cairo": "Cairo:wght@400;700;800", "Tajawal": "Tajawal:wght@400;700", "Amiri": "Amiri:wght@400;700",
    "Noto Naskh Arabic": "Noto+Naskh+Arabic:wght@400;600",
}

# Kutuphaneci'nin her hafta ekledigi ciftler (ortak kutuphane, tum musteriler). Elle yazilmis ciftleri ezmez.
EK_DOSYA = Path(os.environ.get("AJAN_PAYLASIK_KOK") or Path(__file__).resolve().parent.parent / "paylasilan") / "fontlar" / "ek_ciftler.json"


def _ek_yukle():
    try:
        ek = json.loads(EK_DOSYA.read_text(encoding="utf-8"))
    except Exception:
        return
    for k, c in (ek.get("ciftler") or {}).items():
        if k not in CIFTLER and not c.get("emekli") and all(a in (ek.get("google") or {}) or a in GOOGLE for a in (c["bf"], c["gf"])):
            CIFTLER[k] = {**C(c["bf"], c.get("bf_yedek") or YEDEK_SANS, c["gf"], c["bw"], c["bt"], c["bls"], c["bo"],
                              c["his"], c["uygun"], c.get("alfabe") or ["latin"]), "ek": True}
    for a, spec in (ek.get("google") or {}).items():
        GOOGLE.setdefault(a, spec)


_ek_yukle()

# Icerik dili -> gereken alfabe (Google Fonts "subset" adlari)
ALFABE = {"ar": "arabic", "fa": "arabic", "ur": "arabic", "ps": "arabic", "ru": "cyrillic", "uk": "cyrillic",
          "bg": "cyrillic", "sr": "cyrillic", "mk": "cyrillic", "kk": "cyrillic", "el": "greek", "he": "hebrew",
          "hi": "devanagari", "mr": "devanagari", "ne": "devanagari", "th": "thai", "vi": "vietnamese",
          "bn": "bengali", "ta": "tamil", "ko": "korean", "ja": "japanese", "zh": "chinese-simplified"}


def alfabe(dil_kodu):
    return ALFABE.get((dil_kodu or "en").split("-")[0].lower(), "latin")


def uygun_ciftler(dil_kodu=None):
    """Icerik dilinin harflerini gercekten iceren ciftler. Hic yoksa (yeni alfabe) hepsi: sistem yedek fontu devralir."""
    if dil_kodu is None:
        try:
            from . import dil
            dil_kodu = dil.kod()
        except Exception:
            dil_kodu = "en"
    a = alfabe(dil_kodu)
    return [k for k, c in CIFTLER.items() if a in c.get("alfabe", ["latin"])] or list(CIFTLER)


def aileler():
    return sorted({c["bf"] for c in CIFTLER.values()} | {c["gf"] for c in CIFTLER.values()})


def imza():
    """Font kutuphanesi degisince yerel onbellek yenilensin."""
    return hashlib.sha1("|".join(GOOGLE[a] for a in aileler()).encode()).hexdigest()[:8]


def css_siniflari():
    """Sablonlara eklenen .f-<anahtar> siniflari (sablondaki eski tanimlarin ustune yazar)."""
    satirlar = []
    for k, c in CIFTLER.items():
        satirlar.append(f'.f-{k} {{ --bf:"{c["bf"]}",{c["bf_yedek"]}; --gf:"{c["gf"]}",{YEDEK_SANS}; '
                        f'--bw:{c["bw"]}; --bt:{c["bt"]}; --bls:{c["bls"]}; --bo:{c["bo"]}; }}')
    return "\n".join(satirlar)


def aciklama(anahtarlar=None):
    """Sanat Yonetmeni istemi icin: anahtar -> 'Baslik + Govde (his; uygun)'"""
    return {k: f'{c["bf"]} + {c["gf"]} ({c["his"]}; suits {c["uygun"]})' for k, c in CIFTLER.items()
            if anahtarlar is None or k in anahtarlar}


def uygunluk(anahtar, sektor_metni):
    """Sablon modunda (yapay zekasiz) sektore yakisan fontlari daha sik secmek icin agirlik (1 ya da 3)."""
    kelimeler = {w[:5] for w in __import__("re").findall(r"[a-z]{4,}", (sektor_metni or "").lower())}
    uygun = {w[:5] for w in __import__("re").findall(r"[a-z]{4,}", CIFTLER.get(anahtar, {}).get("uygun", "").lower())}
    return 3 if kelimeler & uygun else 1
