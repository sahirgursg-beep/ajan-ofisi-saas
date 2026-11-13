"""Isletmenin icerik dili: ajan talimati ve tasarimlardaki sabit etiketler (NEW IN, % OFF...).

Dil profil.isletme.dil'den gelir (ISO kodu); yoksa ulkenin varsayilan dili, o da yoksa Ingilizce.
Yapay zekanin yazdigi metinler dogrudan bu dilde istenir; burada yalnizca kodun yazdigi kisa etiketler var.
"""
from . import ulkeler

ETIKET = {
    "yeni": {"en": "NEW IN", "fr": "NOUVEAU", "es": "NOVEDAD", "pt": "NOVIDADE", "de": "NEU", "it": "NOVITÀ",
             "tr": "YENİ", "ar": "جديد", "nl": "NIEUW", "id": "BARU", "sw": "MPYA"},
    "indirim": {"en": "OFF", "fr": "DE RÉDUC", "es": "DTO", "pt": "OFF", "de": "RABATT", "it": "SCONTO",
                "tr": "İNDİRİM", "ar": "خصم", "nl": "KORTING", "id": "DISKON", "sw": "PUNGUZO"},
    "fiyat_tahmin": {"en": "Guess the price? 👀", "fr": "Devinez le prix ? 👀", "es": "¿Adivinas el precio? 👀",
                     "pt": "Adivinha o preço? 👀", "de": "Errätst du den Preis? 👀", "it": "Indovina il prezzo? 👀",
                     "tr": "Fiyatı tahmin et 👀", "ar": "خمّن السعر 👀", "nl": "Raad de prijs? 👀",
                     "id": "Tebak harganya? 👀", "sw": "Kisia bei? 👀"},
    "uc_sebep": {"en": "3 reasons you'll love this", "fr": "3 raisons de l'adorer", "es": "3 razones para amarlo",
                 "pt": "3 motivos para amar", "de": "3 Gründe, es zu lieben", "it": "3 motivi per amarlo",
                 "tr": "Seveceğin 3 neden", "ar": "3 أسباب ستحبها", "nl": "3 redenen om het te zien",
                 "id": "3 alasan kamu suka", "sw": "Sababu 3 utaipenda"},
    "detaylar": {"en": "THE DETAILS", "fr": "LES DÉTAILS", "es": "LOS DETALLES", "pt": "OS DETALHES",
                 "de": "DIE DETAILS", "it": "I DETTAGLI", "tr": "DETAYLAR", "ar": "التفاصيل", "nl": "DE DETAILS",
                 "id": "DETAILNYA", "sw": "MAELEZO"},
    "kanca": {"en": "Made for you", "fr": "Fait pour vous", "es": "Hecho para ti", "pt": "Feito para você",
              "de": "Für dich gemacht", "it": "Fatto per te", "tr": "Senin için", "ar": "صُنع لك",
              "nl": "Voor jou gemaakt", "id": "Dibuat untukmu", "sw": "Kwa ajili yako"},
}


SAGDAN_SOLA = {"ar", "fa", "ur", "he", "ps"}


def html_isareti(metin):
    """Sablon HTML'ine icerik dilini ve yazi yonunu ekler: Arapca/Farsca gibi dillerde satirlar sagdan sola akar,
    noktalama ve sayilar dogru yere duser; tarayici o dilin harflerine uygun yedek fontu secer."""
    k = kod()
    yon = ' dir="rtl"' if k in SAGDAN_SOLA else ""
    metin = metin.replace("<html>", f'<html lang="{k}"{yon}>', 1)
    if yon:   # sayilar, fiyatlar ve "2 / 4" sayaci sagdan sola satirda ters donmesin
        metin = metin.replace("</head>", "<style>[dir=rtl] :is(.sayac,.eski,.yeni,.fiyat2,.rozet b,.rozet:not(:has(b)),.serit)"
                              "{direction:ltr;unicode-bidi:isolate}</style></head>", 1)
    return metin


def kod():
    from .ayarlar import AYAR
    i = AYAR.get("isletme") or {}
    if i.get("dil"):
        return str(i["dil"]).split("-")[0].lower()
    u = ulkeler.al(i.get("ulke_kodu"))
    return u["dil"] if u else "en"


def adi():
    return ulkeler.dil_adi(kod())


def etiket(anahtar):
    d = ETIKET.get(anahtar, {})
    return d.get(kod()) or d.get("en", anahtar)


def talimat():
    """Musteriye gorunen her metin icin ajanlara eklenen dil kurali."""
    d = adi()
    if d == "English":
        return "\nLANGUAGE: write every customer-facing text (captions, headlines, on-image text) in English.\n"
    return (f"\nLANGUAGE: write every customer-facing text (captions, hooks, headlines, on-image lines, carousel "
            f"text, titles) in {d}, natural and native for {d}-speaking customers - not translated-sounding. "
            f"Hashtags may mix {d} and English. JSON keys stay in English.\n")
