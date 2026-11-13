"""HTML sablonlarini gercek tarayici motoruyla (Playwright/Chromium) gorsele cevirir."""
import html
import re
from pathlib import Path

from .ayarlar import AYAR, KOK
from . import marka

SABLON = KOK / "sablonlar"
_pw = _tarayici = None


def _tarayici_al():
    global _pw, _tarayici
    if _tarayici is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _tarayici = _pw.chromium.launch()
    return _tarayici


def kapat():
    global _pw, _tarayici
    if _tarayici:
        _tarayici.close()
        _pw.stop()
    _pw = _tarayici = None


def _uri(p):
    return Path(p).resolve().as_uri() if p else ""


def veri_hazirla(urun, gorseller, metin=None, tarif=None):
    """Sablona gidecek degiskenler. gorseller: yerel dosya yollari."""
    metin = metin or {}
    logo = marka.logolar()
    fontlar = marka.fontlar_css()
    kat = urun.get("kategori", "").split(">")[-1].strip()
    v = {
        "ortak": _uri(SABLON / "ortak.css"),
        "fontlar": _uri(fontlar) if fontlar else "",
        "logo_altin": _uri(logo["altin"]),
        "logo_krem": _uri(logo["krem"]),
        "ad": urun["ad"],
        "kategori": kat,
        "fiyat": urun.get("fiyat_metni", ""),
        "eski_fiyat": urun.get("eski_fiyat_metni", ""),
        "eski_gizle": "" if urun.get("eski_fiyat_metni") else "gizli",
        "indirim": str(urun.get("indirim_yuzde") or ""),
        "rozet_gizle": "" if (urun.get("indirim_yuzde") or 0) >= 5 else "gizli",
        "baslik": metin.get("headline", ""),
        "kanca": metin.get("hook", ""),
        "cta": AYAR["marka"]["cta"],
        "web": AYAR["marka"]["web"],
    }
    ind = urun.get("indirim_yuzde") or 0
    v["buyuk_baslik"] = metin.get("buyuk_baslik") or (f"{ind}% OFF" if ind >= 5 else "NEW IN")
    if gorseller:
        tohum = sum(map(ord, urun["ad"]))
        v["vurgu"], v["vurgu_koyu"], v["vurgu_yazi"] = marka.vurgu_rengi(marka.gorsel_hazirla(Path(gorseller[0])), tohum)
        v["logo_renk"] = _uri(logo["koyu"] if v["vurgu_yazi"] != "#FFFFFF" else logo["krem"])
    # Urun algilama: fotograf urunu merkeze alacak sekilde kirpilir, yazi/rozet urunun ustune binmez
    kutu = None
    if gorseller:
        from . import algila
        try:
            kutu = algila.urun_kutusu(marka.gorsel_hazirla(Path(gorseller[0])))
        except Exception:
            kutu = None
    k = kutu or {"cx": .5, "cy": .55, "x0": .15, "x1": .85, "y0": .35, "y1": .88}
    v["odak_stil"] = f"--ox:{k['cx'] * 100:.0f}%;--oy:{min(max(k['cy'], .3), .7) * 100:.0f}%"
    ek_sinif = []
    if tarif:
        from . import sanat
        tarif = dict(tarif)
        uzun = k["y0"] < 0.25 and k["y1"] > 0.7                       # urun fotografi bastan sona kapliyor
        if tarif.get("duzen") == "diyagonal" and (k["y1"] > 0.62 or uzun):
            tarif["duzen"] = "ust_foto_alt_panel"   # diyagonal bant urunun ustune biner -> foto ve yazi ayrilsin
        if tarif.get("duzen") == "tam_ekran":
            if uzun:
                tarif["duzen"] = "ust_foto_alt_panel"
            elif k["y1"] + 0.06 > 0.6:
                ek_sinif.append("yazi-ust")          # urun altta -> yazi ustte (rozet karsi kosede kalir)
        if "yazi-ust" not in ek_sinif and k["cx"] > 0.55:
            ek_sinif.append("rozet-sol")             # urun sagda -> rozet solda
        v.update(sanat.sablon_degiskenleri(tarif, logo, _uri))
        v["siniflar"] += " " + " ".join(ek_sinif)
    if not urun.get("fiyat_metni"):          # proje icerigi: fiyat alanlari tamamen gizlenir
        v["siniflar"] = (v.get("siniflar", "") + " fiyatsiz").strip()
        v["buyuk_baslik"] = metin.get("buyuk_baslik") or ("OUR PROJECT" if urun.get("proje") else v["buyuk_baslik"])
    for i, g in enumerate(gorseller[:4], 1):
        v[f"foto{i}"] = _uri(marka.gorsel_hazirla(Path(g)))
    for i in range(len(gorseller) + 1, 5):
        v[f"foto{i}"] = v.get("foto1", "")
    return v


def marka_css():
    """Musterinin marka renkleri -> ortak.css degiskenleri (varsayilanlarin ustune yazilir). Yalnizca gecerli hex."""
    m = AYAR["marka"]
    return "".join(f"--{css}:{m[k]};" for css, k in (("koyu", "renk_koyu"), ("kahve", "renk_kahve"),
                                                     ("altin", "renk_altin"), ("altin-acik", "renk_altin_acik"),
                                                     ("krem", "renk_acik"))
                   if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", str(m.get(k) or "")))


def ciz(sablon_adi, v, hedef, boyut=(1080, 1350)):
    metin = (SABLON / sablon_adi).read_text(encoding="utf-8")
    for k, deger in v.items():
        guvenli = deger if k in ("ortak", "fontlar") or k.startswith(("foto", "logo", "vurgu", "t_", "odak")) else html.escape(str(deger))
        metin = metin.replace("{{" + k + "}}", guvenli)
    if boyut[1] > boyut[0] * 1.5:
        metin = metin.replace("<body>", '<body class="story">', 1).replace('<body class="', '<body class="story ', 1)
    from . import fontlar as _fontlar
    metin = metin.replace("</head>", f"<style>:root{{--w:{boyut[0]}px;--h:{boyut[1]}px;{marka_css()}}}\n"
                          f"{_fontlar.css_siniflari()}</style></head>", 1)
    metin = metin.replace("<body", f'<body style="{v.get("odak_stil", "")}"', 1)
    gecici = SABLON / f"_render_{AYAR['musteri_id']}_{Path(hedef).stem}.html"   # sablon klasorunde: ortak.css goreli yolu calissin
    gecici.write_text(metin, encoding="utf-8")
    sayfa = _tarayici_al().new_page(viewport={"width": boyut[0], "height": boyut[1]}, device_scale_factor=1)
    try:
        sayfa.goto(gecici.as_uri(), wait_until="load")
        sayfa.evaluate("document.fonts.ready")
        sayfa.wait_for_timeout(150)
        sayfa.screenshot(path=str(hedef), type="jpeg", quality=93, clip={"x": 0, "y": 0, "width": boyut[0], "height": boyut[1]})
    finally:
        sayfa.close()
        gecici.unlink(missing_ok=True)
    return hedef
