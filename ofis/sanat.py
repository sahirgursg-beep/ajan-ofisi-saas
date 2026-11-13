"""Sanat Yonetmeni'nin beyni: gunun trendlerine gore "tasarim tarifi" uretir, dogrular, kutuphaneye kaydeder.

Tarif ornegi:
{"isim": "Black Friday Gold", "duzen": "kemer", "fontlar": "zarif", "motif": "kose_susleri",
 "fiyat_stili": "rozet", "efekt": "sicak", "banner": "BLACK FRIDAY",
 "palet": {"zemin": "#0E0E0E", "vurgu": "#C9A24B", "panel": "#141414"}, "neden": "..."}
"""
import json
import random
import re
from datetime import date, datetime
from pathlib import Path

from .ayarlar import AYAR, KOK, MUSTERI_KOK, PAYLASIK, VERI
from . import kurallar, musteri

TUM_DUZENLER = ["tam_ekran", "ust_foto_alt_panel", "cerceveli", "kemer", "yan_panel", "diyagonal"]
# config.json "haric_duzenler" ile istenmeyen duzenler kapatilir (or. kemer/kubbe)
DUZENLER = [d for d in TUM_DUZENLER if d not in AYAR.get("haric_duzenler", [])] or ["tam_ekran"]
from . import fontlar as _fontlar
FONTLAR = list(_fontlar.CIFTLER)
MOTIFLER = ["yok", "altin_cizgi", "cift_cerceve", "kose_susleri", "daireler", "grain"]
FIYAT_STILLERI = ["rozet", "serit", "sade", "etiket_kart"]
EFEKTLER = ["yok", "sicak", "dramatik", "serin"]
KUTUPHANE = VERI / "sablon_kutuphane"

ACIKLAMA = {
    "duzen": {
        "tam_ekran": "full-bleed photo, text over dark gradient at bottom",
        "ust_foto_alt_panel": "photo on top 64%, solid color panel below with text",
        "cerceveli": "solid background, photo inset with thin accent frame, centered text below",
        "kemer": "solid background, photo inside an elegant arch window shape, centered text",
        "yan_panel": "color panel on the left 40% with text, photo on the right 60%",
        "diyagonal": "full photo with a diagonal color band at the bottom holding the text",
    },
    "fontlar": _fontlar.aciklama(),
    "motif": {
        "yok": "no ornament", "altin_cizgi": "short accent line above text",
        "cift_cerceve": "double thin frame around the whole image (echoes our logo)",
        "kose_susleri": "accent L-shaped corner ornaments", "daireler": "large soft accent circles",
        "grain": "subtle film grain texture",
    },
    "fiyat_stili": {
        "rozet": "round discount badge", "serit": "diagonal corner ribbon with % OFF",
        "sade": "just old/new price, no badge", "etiket_kart": "price on a white tag card",
    },
    "efekt": {"yok": "no photo filter", "sicak": "slightly warm", "dramatik": "slightly more contrast",
              "serin": "slightly cool"},
}


# ---------------- trend baglami ----------------
def _trend_dosyasi():
    """Once musterinin kendi trendler.json'u, sonra ulkesinin takvimi, o da yoksa kuresel takvim (GLOBAL.json)."""
    kod = (musteri.bilgi().get("ulke_kodu") or "").upper()
    for yol in (MUSTERI_KOK / "trendler.json", PAYLASIK / "takvimler" / f"{kod}.json",
                PAYLASIK / "takvimler" / "GLOBAL.json"):
        try:
            return json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {"etkinlikler": [], "mevsimler": [], "tasarim_trendleri": []}


def _aralikta(bugun, bas, bit):
    b = (int(bas[:2]), int(bas[3:]))
    e = (int(bit[:2]), int(bit[3:]))
    g = (bugun.month, bugun.day)
    return b <= g <= e if b <= e else (g >= b or g <= e)  # yil donumunu gecen aralik


def baglam(bugun=None):
    bugun = bugun or date.today()
    t = _trend_dosyasi()
    etkinlikler = [e for e in t.get("etkinlikler", []) if _aralikta(bugun, e["baslangic"], e["bitis"])]
    mevsim = [m for m in t.get("mevsimler", []) if bugun.month in m.get("aylar", [])]
    # yaklasan etkinlik (14 gun icinde)
    yaklasan = []
    for e in t.get("etkinlikler", []):
        try:
            d = date(bugun.year, int(e["baslangic"][:2]), int(e["baslangic"][3:]))
            if d < bugun:
                d = date(bugun.year + 1, d.month, d.day)
            if 0 < (d - bugun).days <= 14:
                yaklasan.append(f'{e["ad"]} in {(d - bugun).days} days')
        except ValueError:
            pass
    return {"tarih": bugun.isoformat(), "gun": bugun.strftime("%A"), "etkinlikler": etkinlikler,
            "mevsim": mevsim, "yaklasan": yaklasan, "trendler": t.get("tasarim_trendleri", [])}


# ---------------- renk yardimcilari ----------------
def _hex(s, varsayilan):
    s = (s or "").strip()
    return s.upper() if re.fullmatch(r"#[0-9a-fA-F]{6}", s) else varsayilan


def _parlaklik(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _yazi_rengi(zemin):
    return "#1C1612" if _parlaklik(zemin) > 0.55 else "#FFFFFF"


def _karart(h, oran=0.82):
    return "#" + "".join(f"{int(int(h[i:i + 2], 16) * oran):02X}" for i in (1, 3, 5))


# ---------------- dogrulama ----------------
def dogrula(tarif, urun, foto_vurgu=None):
    """LLM'den ne gelirse gelsin gecerli, okunakli bir tarif dondurur."""
    t = dict(tarif or {})
    # Marka Kurallari'ndaki yasaklar burada KODLA uygulanir (LLM ne derse desin)
    duz, fon, mot, fiy, efk = (kurallar.izinli("duzen", DUZENLER), kurallar.izinli("fontlar", FONTLAR),
                               kurallar.izinli("motif", MOTIFLER), kurallar.izinli("fiyat_stili", FIYAT_STILLERI),
                               kurallar.izinli("efekt", EFEKTLER))
    ilk = lambda liste, tercih: tercih if tercih in liste else liste[0]
    sec = lambda alan, liste, vars: t.get(alan) if t.get(alan) in liste else vars
    t["duzen"] = sec("duzen", duz, random.choice(duz))
    t["fontlar"] = sec("fontlar", fon, ilk(fon, "klasik"))
    t["motif"] = sec("motif", mot, ilk(mot, "yok"))
    t["fiyat_stili"] = sec("fiyat_stili", fiy, ilk(fiy, "rozet"))
    t["efekt"] = sec("efekt", efk, ilk(efk, "yok"))
    if (urun.get("indirim_yuzde") or 0) < 5 and t["fiyat_stili"] in ("rozet", "serit"):
        t["fiyat_stili"] = ilk([x for x in fiy if x not in ("rozet", "serit")] or ["sade"], "sade")
    banner = re.sub(r"[^A-Za-z0-9 %&'!,.-]", "", str(t.get("banner") or "")).strip().upper()
    t["banner"] = "" if kurallar.oku()["banner"] == "kapali" else banner[:26]

    palet = t.get("palet")
    if not isinstance(palet, dict) or palet == {}:
        fv = foto_vurgu or ("#2B211B", "#C9A24B")
        palet = {"zemin": fv[0], "vurgu": fv[1], "panel": fv[0]}
    zemin = _hex(palet.get("zemin"), "#1C1612")
    vurgu = _hex(palet.get("vurgu"), "#C9A24B")
    panel = _hex(palet.get("panel"), zemin)
    if abs(_parlaklik(vurgu) - _parlaklik(panel)) < 0.18:  # vurgu panelde kaybolmasin
        vurgu = "#C9A24B" if _parlaklik(panel) < 0.5 else "#1C1612"
    t["palet"] = {"zemin": zemin, "vurgu": vurgu, "panel": panel}
    t["isim"] = str(t.get("isim") or f"{t['duzen']}-{t['fontlar']}")[:40]
    return t


def sablon_degiskenleri(t, logolar, uri):
    p = t["palet"]
    # logonun oturdugu zemine gore renk sec
    logo_zemin = {"tam_ekran": "#000000", "diyagonal": "#000000", "ust_foto_alt_panel": "#000000",
                  "yan_panel": p["panel"], "cerceveli": p["zemin"], "kemer": p["zemin"]}[t["duzen"]]
    logo = logolar["altin"] if _parlaklik(logo_zemin) < 0.5 else logolar["koyu"]
    siniflar = [f"d-{t['duzen']}", f"f-{t['fontlar']}", f"m-{t['motif']}", f"p-{t['fiyat_stili']}", f"e-{t['efekt']}"]
    if t["banner"]:
        siniflar.append("banner-var")
    return {
        "siniflar": " ".join(siniflar),
        "t_zemin": p["zemin"], "t_yazi": _yazi_rengi(p["zemin"]),
        "t_vurgu": p["vurgu"], "t_vurgu_yazi": _yazi_rengi(p["vurgu"]),
        "t_panel": p["panel"], "t_panel_yazi": _yazi_rengi(p["panel"]),
        "t_logo": uri(logo), "t_banner": t["banner"], "banner_gizle": "" if t["banner"] else "gizli",
        "t_hiza": "merkez" if t["duzen"] in ("cerceveli", "kemer") else "",
    }


# ---------------- sablon modu (LLM yoksa) ----------------
def _sektor_metni():
    try:
        from . import sektor
        p = sektor.profil()
        return f"{p.get('ad', '')} {p.get('alt_sektor', '')}"
    except Exception:
        return ""


def rastgele_tarif(urun, bglm, tohum=None, foto_vurgu=None):
    from .analiz import ozellik_agirligi
    r = random.Random(tohum)
    # Performans Analisti'nin ogrenimlerine gore agirlikli secim (sevilen duzen/font daha sik gelir)
    agirlikli = lambda alan, liste: r.choices(liste, weights=[ozellik_agirligi(alan, x) for x in liste])[0]
    etk = bglm["etkinlikler"][0] if bglm["etkinlikler"] else None
    t = {
        "duzen": agirlikli("duzen", kurallar.izinli("duzen", DUZENLER)),
        "fontlar": r.choices(kurallar.izinli("fontlar", FONTLAR),
                             weights=[ozellik_agirligi("fontlar", f) * _fontlar.uygunluk(f, _sektor_metni())
                                      for f in kurallar.izinli("fontlar", FONTLAR)])[0],
        "motif": agirlikli("motif", kurallar.izinli("motif", MOTIFLER)),
        "fiyat_stili": agirlikli("fiyat_stili", kurallar.izinli("fiyat_stili", FIYAT_STILLERI)),
        "efekt": r.choice(kurallar.izinli("efekt", ["yok", "sicak", "dramatik"])),
        "banner": etk["banner"] if etk else "",
        "palet": etk["palet"] if etk and isinstance(etk.get("palet"), dict) else None,
        "isim": (etk["ad"] if etk else "Daily") + f" #{r.randint(100, 999)}",
        "neden": "(sablon modu) trend takvimine gore rastgele kombinasyon",
    }
    return dogrula(t, urun, foto_vurgu)


# ---------------- kutuphane ----------------
def kaydet(t):
    KUTUPHANE.mkdir(parents=True, exist_ok=True)
    ad = re.sub(r"[^a-z0-9]+", "-", t["isim"].lower()).strip("-")[:30]
    yol = KUTUPHANE / f"{datetime.now():%Y-%m-%d_%H%M%S}_{ad}.json"
    yol.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    return yol


def son_tarifler(n=6):
    if not KUTUPHANE.exists():
        return []
    out = []
    for y in sorted(KUTUPHANE.glob("*.json"))[-n:]:
        try:
            d = json.loads(y.read_text(encoding="utf-8"))
            out.append({k: d.get(k) for k in ("isim", "duzen", "fontlar", "motif", "fiyat_stili")})
        except Exception:
            pass
    return out


def _aktif_aciklama():
    d = {alan: dict(v) for alan, v in ACIKLAMA.items()}
    d["duzen"] = {k: v for k, v in ACIKLAMA["duzen"].items() if k in DUZENLER}
    for alan in d:   # Marka Kurallari'nda yasaklananlar LLM'e hic gosterilmez
        izin = kurallar.izinli(alan, list(d[alan]))
        d[alan] = {k: v for k, v in d[alan].items() if k in izin}
    return d


def llm_istemi(urun, bglm, gecmis, ek_kisit=""):
    etk = "; ".join(f'{e["ad"]} (banner idea: {e["banner"]}, mood: {e["ruh_hali"]}, palette: {e["palet"]})'
                    for e in bglm["etkinlikler"]) or "none"
    sozluk = "\n".join(f"- {alan}: " + ", ".join(f"{k} = {v}" for k, v in d.items()) for alan, d in _aktif_aciklama().items())
    return (
        f"Date: {bglm['tarih']} ({bglm['gun']}). Active events: {etk}. Upcoming: {bglm['yaklasan'] or 'none'}. "
        f"Season: {[m['ad'] + ': ' + m['ruh_hali'] for m in bglm['mevsim']] or 'none'}.\n"
        f"Current design trends to draw from: {bglm['trendler']}\n"
        f"Product: {urun['ad']} | {urun.get('kategori', '')} | discount {urun.get('indirim_yuzde') or 0}% | "
        f"photos: {len(urun.get('gorseller', []))}\n"
        f"Recently used designs (do NOT repeat the same layout+font combo): {gecmis}\n{ek_kisit}\n"
        f"{kurallar.istem('gorsel')}"
        f"{__import__('ofis.analiz', fromlist=['x']).istem_ozeti()}\n\n"
        f"Design vocabulary (use ONLY these keys):\n{sozluk}\n\n"
        "Think like the creative director of a top advertising agency: one strong idea per design, bold "
        "typographic choices, real contrast between headline and body, and a font family that fits THIS brand and "
        "today's message (see 'suits' in the vocabulary) - not the same safe serif every day. Recently used fonts "
        "should not repeat.\n"
        "You have studied the leading accounts of this sector (see the sector research above): build on their "
        "visual trends and trending palettes, adapt them to this brand, never copy one account.\n"
        + ("This post has NO price: never design around a price; let the photo and headline carry it.\n"
           if not urun.get("fiyat") else "")
        + f"Create today's NEW Instagram template for {musteri.tanim()} ({AYAR['marka'].get('tarif', 'use the brand colors')}). "
        "Palette: hex colors; use the event palette if one is active, "
        "otherwise invent a tasteful palette or use \"fotodan\" to take colors from the product photo. "
        "Banner: max 3 words, uppercase, only if it adds value (event, NEW IN, LIMITED OFFER) else empty.\n"
        'Return JSON: {"isim": "<creative template name>", "duzen": "...", "fontlar": "...", "motif": "...", '
        '"fiyat_stili": "...", "efekt": "...", "banner": "...", '
        '"palet": {"zemin": "#hex", "vurgu": "#hex", "panel": "#hex"} or "fotodan", '
        '"neden": "<one short Turkish sentence: which trend/event inspired it>"}'
    )
