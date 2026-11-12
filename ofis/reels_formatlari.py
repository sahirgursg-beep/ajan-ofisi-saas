"""Instagram'da tutan Reels formatlarinin bizim urun fotograflarimiza uyarlanmis halleri.

Her format bir "senaryo" uretir: cekim listesi (hangi foto, hangi kadraj, nasil gecis), ekrandaki yazilar,
fiyat acilisi, geri sayim ve kapanis karti. Senaryoyu sablonlar/reels_format.html oynatir.
"luks" formati eski sablonlar/reels.html kurgusudur (dokunulmadi).

Kurallar (2026 Reels arastirmasi): kanca ilk 1.5 sn'de ekranda, her 2-4 sn'de goruntu degisir, 15 sn.
Format secimi donusumludur; son kullanilan 2 format tekrar edilmez, performans analizi
("reels_format" ozelligi) iyi gidenlerin agirligini artirir.
"""
import json
import random
from pathlib import Path

FORMATLAR = {
    "luks":          "Lüks tanıtım (yavaş kamera, zarif geçişler)",
    "fiyat_tahmini": "Fiyatı tahmin et (geri sayım + fiyat açılışı)",
    "uc_sebep":      "3 sebep (numaralı liste)",
    "detay_zoom":    "Detaylar (yakın çekim zoom + büyük açılış)",
    "ritim_kesim":   "Ritim kesim (hızlı kurgu, kelime kelime)",
    "pov":           "POV (hikâye anlatımı, yavaş pan)",
}
SURE = 15.0


def _temiz(liste):
    liste = [liste] if isinstance(liste, str) else (liste or [])
    return [str(x).strip().rstrip(".") for x in liste if str(x).strip()]


def _satirlar(taslak, adet):
    """Format yazilari icin kisa satirlar: carousel_lines > reels_lines > carousel_points > yedek."""
    s = []
    for alan in ("carousel_lines", "reels_lines", "carousel_points"):
        for x in _temiz(taslak.get(alan)):
            if x.lower() not in [y.lower() for y in s] and len(x.split()) <= 9:
                s.append(x)
    from . import musteri
    s += [x for x in musteri.faydalar() if x not in s]
    return s[:adet]


def senaryo(format_adi, taslak, urun, foto_sayisi):
    n = max(1, foto_sayisi)
    F = lambda i: i % n                       # elimizde kac foto varsa onun icinde don
    tek = n == 1
    kanca = (taslak.get("hook") or "Your home deserves this").strip()
    ad = urun["ad"]
    fiyatli = bool(urun.get("fiyat_metni"))
    S = {"cekimler": [], "yazilar": [], "sure": SURE, "logo_ust": 0}

    def cek(a, f, h="zoom_in", gir="kes", mod="orta", z0=1.04, z1=1.16, gs=.3):
        S["cekimler"].append({"a": a, "f": F(f), "h": h, "gir": gir, "mod": mod, "z0": z0, "z1": z1, "gs": gs})

    def yaz(a, b, metin, stil, konum="alt", efekt="kay", no=None):
        S["yazilar"].append({"a": a, "b": b, "metin": metin, "stil": stil, "konum": konum, "efekt": efekt, "no": no})

    if format_adi == "fiyat_tahmini":
        cek(0, 0, "zoom_in", z0=1.02, z1=1.12)
        yaz(.1, 2.4, "Guess the price? 👀", "soru", "orta", "pop")
        S["karart"] = [(0, 2.4, .35)]
        cek(2.4, 1, "punch", "flas", "sol" if tek else "orta", 1.2, 1.25)
        cek(4.2, 2, "pan_sag", "kaydir", "sag" if tek else "orta", 1.15, 1.2)
        cek(6.0, 0 if n < 4 else 3, "zoom_out", "zoom", "ust" if tek else "orta", 1.05, 1.3)
        yaz(2.6, 5.9, ad, "buyuk", "alt")
        yaz(6.1, 8.0, _satirlar(taslak, 1)[0], "alt", "alt")
        S["sayac"] = [8.0, 10.0]
        S["fiyat"] = [10.0, 12.8] if fiyatli else None
        S["son"] = 12.8 if fiyatli else 10.0

    elif format_adi == "uc_sebep":
        cek(0, 0, "zoom_in", z0=1.02, z1=1.12)
        yaz(.1, 2.3, "3 reasons you'll love this", "kanca", "orta", "pop")
        S["karart"] = [(0, 2.3, .3), (2.3, 11.3, .28)]
        mods = ["sol", "sag", "alt"] if tek else ["orta", "orta", "orta"]
        for i, (sat, gir) in enumerate(zip(_satirlar(taslak, 3), ["kaydir", "kaydir", "kaydir"])):
            a = 2.3 + i * 3
            cek(a, i + 1, ["pan_sol", "zoom_in", "pan_sag"][i], gir, mods[i], 1.12, 1.24)
            yaz(a + .15, a + 2.95, sat, "madde", "alt", "kay", no=str(i + 1))
        S["cubuk"] = [[2.3 + i * 3, 5.3 + i * 3] for i in range(3)]
        cek(11.3, 0, "zoom_out", "bulanik", z0=1.03, z1=1.15)
        S["fiyat"] = [11.3, 13.0] if fiyatli else None
        S["son"] = 13.0 if fiyatli else 11.4

    elif format_adi == "detay_zoom":
        cek(0, 0, "zoom_out", z0=1.02, z1=1.18)
        yaz(.1, 2.3, "THE DETAILS", "etiket", "ust", "pop")
        yaz(.2, 2.3, kanca, "buyuk", "alt")
        satir = _satirlar(taslak, 4)
        kadraj = [("ust", 1), ("sol", 2), ("sag", 0), ("alt", 3)]
        for i, (mod, f) in enumerate(kadraj):
            a = 2.4 + i * 2
            cek(a, f if not tek else 0, "zoom_in", "bulanik", mod, 1.55, 1.85, .35)
            yaz(a + .2, a + 1.95, satir[i], "alt", "alt")
        S["karart"] = [(2.4, 10.4, .2)]
        cek(10.4, 0, "zoom_out", "zoom", z0=1.0, z1=1.12)
        if fiyatli:
            S["fiyat"] = [10.7, 12.9]
            S["son"] = 12.9
        else:
            yaz(10.5, 11.9, ad, "buyuk", "alt", "pop")
            S["son"] = 11.9

    elif format_adi == "ritim_kesim":
        kelimeler = [w for w in kanca.replace(",", "").split()][:6]
        for x in _satirlar(taslak, 2):
            kelimeler += x.split()[:4]
        kelimeler = kelimeler[:14]
        mods = ["orta", "sol", "sag", "ust", "alt"]
        adim = .6
        for i in range(16):
            a = round(i * adim, 2)
            cek(a, i, "punch", "flas" if i % 2 else "kes", mods[i % 5] if (tek or i >= n) else "orta",
                1.08 + .1 * (i % 3), 1.18 + .1 * (i % 3))
            if i < len(kelimeler):
                yaz(a + .02, a + adim, kelimeler[i], "vurus", "orta", "pop")
        S["karart"] = [(0, 9.6, .25)]
        cek(9.6, 0, "zoom_out", "flas", z0=1.02, z1=1.15)
        if fiyatli:
            S["fiyat"] = [9.8, 12.5]
            S["son"] = 12.5
        else:
            yaz(9.7, 11.0, ad, "buyuk", "alt", "pop")
            S["son"] = 11.0

    elif format_adi == "pov":
        pov = (taslak.get("pov") or "you finally found the piece your room was missing").strip()
        pov = pov[4:].strip(" :") if pov.lower().startswith("pov") else pov
        cek(0, 0, "pan_sol", mod="sol" if tek else "orta", z0=1.14, z1=1.2)
        yaz(.1, 4.0, pov, "pov", "ust")
        cek(3.6, 1, "pan_sag", "bulanik", "sag" if tek else "orta", 1.14, 1.2, .5)
        cek(7.2, 2, "zoom_in", "bulanik", "orta", 1.05, 1.2, .5)
        satir = _satirlar(taslak, 2)
        yaz(4.2, 7.1, satir[0], "alt", "alt")
        yaz(7.4, 10.3, satir[1], "alt", "alt")
        S["karart"] = [(0, 4.0, .2)]
        S["fiyat"] = [10.5, 12.8] if fiyatli else None
        S["son"] = 12.8 if fiyatli else 10.6
    else:
        raise ValueError(f"Bilinmeyen Reels formati: {format_adi}")
    if not S.get("fiyat"):
        S.pop("fiyat", None)
        if S["son"] < 12.5:            # fiyatsiz (proje) icerik: kapanistan once urun/proje adiyla genis bir final cekimi
            bas = S["son"]
            cek(bas, 0, "zoom_out", "bulanik", z0=1.0, z1=1.14, gs=.4)
            if not any(y["metin"] == ad and y["a"] >= bas - 1.5 for y in S["yazilar"]):
                yaz(bas + .2, 12.7, ad, "buyuk", "alt", "pop")
            S["son"] = 12.8
    return S


# ---------------- secim ----------------
def son_kullanilanlar(adet=6):
    """cikti/ altindaki en yeni Reels'lerin formatlari (yeniden eskiye)."""
    from .ayarlar import KOK, CIKTI
    kayit = []
    for m in CIKTI.glob("*/meta.json"):
        try:
            d = json.loads(m.read_text(encoding="utf-8"))
        except Exception:
            continue
        f = (d.get("ozellikler") or {}).get("reels_format")
        if f:
            kayit.append((d.get("tarih", ""), f))
    return [f for _, f in sorted(kayit, reverse=True)[:adet]]


def sec(foto_sayisi=3, istenen=None, haric=None):
    """Donusumlu + ogrenen secim. Doner: format adi."""
    from .ayarlar import AYAR, CIKTI
    if istenen in FORMATLAR:
        return istenen
    from . import ofis_ayar
    kapali = set(ofis_ayar.oku().get("reels_kapali") or []) | set(haric or [])   # kapatilanlar + bu icerige uymayanlar
    acik = [f for f in (AYAR.get("reels_formatlari") or list(FORMATLAR)) if f in FORMATLAR and f not in kapali] \
        or list(FORMATLAR)
    son = son_kullanilanlar(2)
    adaylar = [f for f in acik if f not in son] or acik
    try:
        from . import analiz
        agirlik = [analiz.ozellik_agirligi("reels_format", f) for f in adaylar]
    except Exception:
        agirlik = [1.0] * len(adaylar)
    # hic kullanilmamis formatlara ufak oncelik: once hepsi denensin ki analiz ogrenebilsin
    hepsi = son_kullanilanlar(30)
    agirlik = [w * (1.5 if f not in hepsi else 1.0) for f, w in zip(adaylar, agirlik)]
    if foto_sayisi < 2:   # tek fotoda hizli kesim tekrar eder gibi durur
        agirlik = [w * (.5 if f == "ritim_kesim" else 1) for f, w in zip(adaylar, agirlik)]
    return random.choices(adaylar, weights=agirlik)[0]
