"""Abonelik paketleri (saf veri: web, panel, site ve ajanlar ayni tabloyu kullanir).

Fiyatlar USD; sitede ve panelde ziyaretcinin para biriminde yaklasik karsiligi da gosterilir.
Deneme suresi boyunca isletme Growth paketinin ozellikleriyle calisir.
Uretimde uygulanan sinirlar: gunluk formatlar, platformlar, aylik ucretli yapay zeka butcesi.
"""

PAKETLER = {
    "starter": {
        "ad": "Starter", "usd": 10, "formatlar": ["post"], "platformlar": ["instagram", "facebook"],
        "ai_tavan_usd": 2, "isletme": 1,
        "ozellikler": ["1 designed post every day", "Instagram & Facebook auto-publishing",
                       "Captions and hashtags written for your business", "Your photos + free stock photos",
                       "Sector research every week"],
    },
    "growth": {
        "ad": "Growth", "usd": 30, "formatlar": ["post", "carousel", "reels"],
        "platformlar": ["instagram", "facebook", "tiktok", "linkedin"], "ai_tavan_usd": 6, "isletme": 1,
        "ozellikler": ["3 pieces every day: post, carousel and Reel", "Instagram & Facebook auto-publishing",
                       "Ready-to-post TikTok & LinkedIn versions", "AI photo retouching and AI images",
                       "Reads your website, menu and price lists", "Everything in Starter"],
        "one_cikan": True,
    },
    "pro": {
        "ad": "Pro", "usd": 60, "formatlar": ["post", "carousel", "reels"],
        "platformlar": ["instagram", "facebook", "tiktok", "linkedin"], "ai_tavan_usd": 15, "isletme": 3,
        "ozellikler": ["Up to 3 businesses or brands", "Higher AI image and retouching budget",
                       "Priority production every morning", "Monthly performance report", "Everything in Growth"],
    },
}
DENEME_PAKETI = "growth"
SIRA = ("starter", "growth", "pro")


def al(kod):
    return PAKETLER.get(kod) or PAKETLER[DENEME_PAKETI]


def kod_of(abonelik):
    k = (abonelik or {}).get("plan")
    return k if k in PAKETLER else DENEME_PAKETI


def aktif():
    """Ajan surecinde: bu isletmenin paketi (profil.abonelik.plan)."""
    from .ayarlar import AYAR
    return al(kod_of(AYAR.get("abonelik")))


def formatlar(tum):
    """Gunun formatlarindan paketin izin verdikleri (sira korunur)."""
    izin = set(aktif()["formatlar"])
    return [f for f in tum if f in izin] or list(tum)[:1]


def liste():
    return [{"kod": k, **{a: v for a, v in PAKETLER[k].items()}} for k in SIRA]
