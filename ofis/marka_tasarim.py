"""Marka Tasarim Sistemi: her musteriye ozel, guclu modelle (Claude) tasarlanan sablon seti.

Neden: her gun her gonderiyi sifirdan tasarlatmak hem pahali hem tutarsiz (bir gun iyi, bir gun kotu). Iyi markalar
bunun yerine bir TASARIM SISTEMI kullanir: kendi renkleri, yazi tipleri ve 10-12 duzeniyle tutarli ama cesitli bir
akis. Burada o sistemi sanat yonetmeni + guclu tasarim modeli bir kez kurar, iki haftada bir (ya da puanlar
dusunce) yeniler. Gunluk icerik bu duzenlere oturtulur: hizli, ucuz, her zaman okunakli.

Her sablon iki ornek metinle (kisa ve uzun) cizilip olculur ve gorme modeline puanlatilir; gecemeyen sisteme girmez.
"""
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from . import llm, marka, modern_duzen, musteri, tasarim, uretken
from .ayarlar import AYAR, VERI

DOSYA = VERI / "tasarim_sistemi.json"
YENILEME_GUN = 14
GECME = 6.0

TIPLER = {
    "post_a": ((1080, 1350), "feed post, PHOTO-LED: full-bleed photo, bold headline overlaid on a scrim or a solid shape; price and one CTA"),
    "post_b": ((1080, 1350), "feed post, TYPE-LED: oversized headline is the hero, photo as a strong secondary element (cutout window, rounded frame or tilted card)"),
    "post_c": ((1080, 1350), "feed post, CARD/STICKER: full-bleed photo with a floating card or sticker-style labels carrying headline, price, CTA"),
    "post_d": ((1080, 1350), "feed post, a bold idea of your own that fits this brand (not a split-screen, not a newspaper layout)"),
    "story_a": ((1080, 1920), "Instagram story, photo-led full-bleed; keep top 220px and bottom 340px free of text"),
    "story_b": ((1080, 1920), "Instagram story, color-led: brand color background, big headline, photo in a rounded frame; keep top 220px and bottom 340px free of text"),
    "slayt_foto": ((1080, 1350), "carousel slide with a photo and ONE short line ({{LINE}}) as the message"),
    "slayt_tip": ((1080, 1350), "carousel slide WITHOUT any photo: typography only - a big step number ({{NO}}) and the line ({{LINE}}); bold brand colours"),
    "liste": ((1080, 1350), "last carousel slide: three points ({{POINT1}}, {{POINT2}}, {{POINT3}}) as a clean checklist or stacked cards, then price and the CTA - a slide people save"),
    "son": ((1080, 1920), "Reels end card: the LOGO is the hero (240-420px wide, deliberately placed, on a background that contrasts with it - use {{LOGO_ACIK}} on dark, {{LOGO_KOYU}} on light), then the CTA as one bold element and the website small. No photo needed. Keep top 220px and bottom 340px free"),
}
ORNEK = {
    "kisa": {"HEADLINE": "Fresh every morning", "LINE": "Baked at dawn", "PRICE": "$24", "OLD_PRICE": "$32",
             "CTA": "Order now", "HOOK": "Still warm", "NO": "1", "POINT1": "Free delivery", "POINT2": "Made daily",
             "POINT3": "Local flour"},
    "uzun": {"HEADLINE": "Everything you need to launch your first campaign this week",
             "LINE": "Connect your accounts and pick a ready-made plan", "PRICE": "₦1,875,000", "OLD_PRICE": "₦3,000,000",
             "CTA": "Visit our showroom or send us a DM", "HOOK": "Stop scrolling, start growing", "NO": "3",
             "POINT1": "Delivery anywhere in the city within 48 hours", "POINT2": "Solid hardwood frame",
             "POINT3": "Five-year warranty on every piece"},
}
YER_TUTUCULAR = ("HEADLINE", "LINE", "PRICE", "OLD_PRICE", "CTA", "WEB", "HOOK", "NO", "POINT1", "POINT2", "POINT3")


def _oku():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def sistem():
    return _oku()


def eski_mi():
    s = _oku()
    if not s.get("sablonlar") or not any(k.startswith("post") for k in s["sablonlar"]):
        return True
    try:
        return datetime.fromisoformat(s["tarih"]) < datetime.now() - timedelta(days=YENILEME_GUN)
    except (KeyError, ValueError):
        return True


# ---------------------------------------------------------------- metin sigdirma
def _boy(metin, tip, alan):
    """Baslik/satir boyu metin uzunlugundan (sablon var(--h) / var(--l) kullanir)."""
    n = len(metin or "")
    taban = {"HEADLINE": 124, "LINE": 96, "HOOK": 110}.get(alan, 96)
    if tip in ("slayt_tip",):
        taban += 16
    k = 1 if n <= 16 else .86 if n <= 28 else .74 if n <= 42 else .62 if n <= 60 else .52
    return int(taban * k)


def doldur(sablon, tip, metin, varliklar):
    """Yer tutuculari doldurur; bos alanli ogeler (data-alan) sayfadaki kucuk betikle kaldirilir."""
    h = sablon
    for k in YER_TUTUCULAR:
        h = h.replace("{{" + k + "}}", uretken.html_kac(metin.get(k, "")))
    for k, v in varliklar.items():
        h = h.replace("{{" + k + "}}", v)
    h = re.sub(r"\{\{[A-Z0-9_]+\}\}", "", h)
    stil = (f"--h:{_boy(metin.get('HEADLINE') or metin.get('HOOK'), tip, 'HEADLINE')}px;"
            f"--l:{_boy(metin.get('LINE'), tip, 'LINE')}px;")
    h = h.replace('class="tuval"', f'class="tuval" style="{stil}"', 1)
    bos = [k for k in YER_TUTUCULAR if not str(metin.get(k, "")).strip()]
    if bos:
        h += ("<script>for(const a of " + json.dumps(bos) + ")document.querySelectorAll('[data-alan=\"'+a+'\"]')"
              ".forEach(e=>e.remove());</script>")
    return h


# ---------------------------------------------------------------- kurulum
def _istem(tip, dil, arastirma_ozeti):
    (W, H), rol = TIPLER[tip]
    return (
        f"Design ONE reusable {W}x{H}px template for the brand's social media design system.\n"
        f"Brand: {musteri.ad()} - {musteri.tanim()}.\n"
        f"Visual language of the brand (keep it across all templates): style '{dil['stil']}'. "
        f"Palette {json.dumps(dil['palet'])}. Details: {dil.get('dokular', '')}.\n"
        f"{arastirma_ozeti}\n"
        f"This template: {rol}.\n"
        "PLACEHOLDERS (write them literally, the system fills them): text {{HEADLINE}} {{LINE}} {{HOOK}} {{PRICE}} "
        "{{OLD_PRICE}} {{CTA}} {{WEB}} {{NO}} {{POINT1}} {{POINT2}} {{POINT3}} (use only the ones this template needs); "
        "images <img src=\"{{FOTO1}}\"> (and {{FOTO2}} optionally) with object-fit:cover, logo <img src=\"{{LOGO_KOYU}}\"> "
        "or <img src=\"{{LOGO_ACIK}}\"> (height 56-90px unless the logo is the hero).\n"
        "TEXT SIZE: the system sets CSS variables on .tuval: use font-size:var(--h) for {{HEADLINE}}/{{HOOK}} and "
        "font-size:var(--l) for {{LINE}}; they are sized to the text length. Other texts 26-44px.\n"
        "Optional parts: give the element that holds {{PRICE}} data-alan=\"PRICE\", {{OLD_PRICE}} data-alan=\"OLD_PRICE\", "
        "{{CTA}} data-alan=\"CTA\", {{WEB}} data-alan=\"WEB\" - they are removed when the business has no value.\n"
        "Texts will range from 2 words to about 60 characters: the layout must hold both (flex/grid with min-width:0, "
        "text-wrap:balance, white-space:nowrap only on prices).\n"
        f"RULES: root <div class=\"tuval\"> exactly {W}x{H}px, position:relative, overflow:hidden; every text at least "
        "56px from the edges; put data-metin on every text element; strong contrast for every text (scrim, solid "
        "panel or card on photos); ONE call-to-action only; no fake UI, no tiny decorative text, no newspaper "
        "columns, no thin gold frames, no split-screen 50/50 boxes; headline font-family:var(--bf), weight var(--bw); "
        "body font-family:var(--gf). Modern CSS welcome (grid, gradients, border-radius, shadows, backdrop-filter, "
        "transforms, clip-path, inline SVG). No <script>, no external URLs, no emoji.\n"
        "Return ONLY the HTML: one <style> block then the <div class=\"tuval\">...</div>."
    )


def _dene(tip, html_, dil, varliklar, klasor):
    """Iki ornek metinle cizip olcer, kisa ornegi puanlar. -> (puan|None, sorunlar)"""
    (W, H), _ = TIPLER[tip]
    tuval = {"ad": tip, "boyut": (W, H), "rol": TIPLER[tip][1], "metin": {}}
    sorunlar, puan = [], None
    for ad, ornek in ORNEK.items():
        m = dict(ornek, WEB=AYAR["marka"].get("web") or "example.com")
        sayfa = uretken._sayfa(doldur(html_, tip, m, varliklar), tuval, dil, varliklar)
        yol = klasor / f"_sistem_{tip}_{ad}.jpg"
        tuval["metin"] = {"headline": m["HEADLINE"]} if "{{HEADLINE}}" in html_ else {"line": m["LINE"]} if "{{LINE}}" in html_ else {}
        try:
            olc = uretken._ciz_ve_olc(sayfa, tuval, yol)
        except Exception as e:
            olc = {"sert": [f"render error: {str(e)[:80]}"], "yumusak": []}
        sorunlar += [f"[{ad} text] {x}" for x in olc.get("sert", [])]
        if ad == "kisa" and not olc.get("sert"):
            puan, notlar = uretken._gorsel_puan(yol, tuval)
            if puan is not None and puan < GECME:
                sorunlar += notlar or ["make it more modern and striking"]
        yol.unlink(missing_ok=True)
    return puan, sorunlar


def kur(urun, gorsel_yollari, taslak, gunluk=print, zorla=False):
    """Tasarim sistemini kurar/yeniler. -> sistem dict ya da None (model yok)."""
    if not zorla and not eski_mi():
        return _oku()
    if not llm.hazir():
        return None
    from . import arastirma
    dil = uretken.dil_sec(urun, taslak, None) or uretken._varsayilan_dil()
    gunluk(f"Tasarim sistemi kuruluyor: '{dil['stil']}' — model {llm.tasarim_modeli_adi()}")
    varliklar = _varliklar(gorsel_yollari)
    klasor = VERI / "_sistem_tmp"
    klasor.mkdir(parents=True, exist_ok=True)
    ozet = arastirma.istem_ozeti()
    yaz = lambda tip, ek="": uretken._temizle(llm.tasarim_sor(uretken.SISTEM, _istem(tip, dil, ozet) + ek, sicaklik=0.8))
    with ThreadPoolExecutor(max_workers=4) as h:
        taslaklar = dict(zip(TIPLER, h.map(yaz, TIPLER)))
    sablonlar = {}
    for tip, html_ in taslaklar.items():
        for deneme in range(2):
            if not html_ or ".tuval" not in html_:
                html_ = yaz(tip)
                continue
            puan, sorunlar = _dene(tip, html_, dil, varliklar, klasor)
            gunluk(f"[TASARIM] sistem {tip}: deneme {deneme + 1}, puan {puan}, sorun {len(sorunlar)}"
                   + (f": {'; '.join(sorunlar[:2])}" if sorunlar else ""))
            if not sorunlar:
                sablonlar[tip] = {"html": html_, "puan": puan}
                break
            if deneme == 0:
                html_ = yaz(tip, "\n\nA first version had these problems; write a better one that fixes ALL of them:\n- "
                            + "\n- ".join(sorunlar[:8]) + "\n\nFirst version:\n" + html_[:6000])
    s = {"tarih": datetime.now().isoformat(timespec="minutes"), "dil": dil, "sablonlar": sablonlar,
         "model": llm.tasarim_modeli_adi(), "kullanim": {}}
    if any(k.startswith("post") for k in sablonlar):
        DOSYA.parent.mkdir(parents=True, exist_ok=True)
        DOSYA.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        gunluk(f"Tasarim sistemi hazir: {len(sablonlar)}/{len(TIPLER)} sablon ({', '.join(sablonlar)})")
        return s
    gunluk("Tasarim sistemi kurulamadi (hicbir post sablonu gecemedi); modern duzenler kullanilacak")
    return None


def _kirpik(yol):
    """Logonun seffaf kenarlarini kirpar: bos pay logoyu merkezden kaydirmasin."""
    if not yol:
        return None
    from PIL import Image
    hedef = Path(yol).with_name(Path(yol).stem + "_k.png")
    try:
        if not hedef.exists() or hedef.stat().st_mtime < Path(yol).stat().st_mtime:
            im = Image.open(yol).convert("RGBA")
            kutu = im.getchannel("A").getbbox()
            (im.crop(kutu) if kutu else im).save(hedef)
        return hedef
    except Exception:
        return Path(yol)


def _varliklar(gorsel_yollari):
    logo = marka.logolar()
    tekil = list(dict.fromkeys(str(g) for g in gorsel_yollari))[:4]
    fotolar = [marka.gorsel_hazirla(Path(g)) for g in tekil]
    v = {f"FOTO{i}": tasarim._uri(f) for i, f in enumerate(fotolar, 1)}
    v.setdefault("FOTO1", "")
    v.setdefault("FOTO2", v["FOTO1"])
    v.setdefault("FOTO3", v["FOTO2"])
    v.setdefault("FOTO4", v["FOTO3"])
    v["LOGO_KOYU"] = tasarim._uri(_kirpik(logo.get("koyu"))) if logo.get("koyu") else ""
    v["LOGO_ACIK"] = tasarim._uri(_kirpik(logo.get("krem"))) if logo.get("krem") else ""
    return v


# ---------------------------------------------------------------- gunluk kullanim
def _sec(s, onek, haric=()):
    """Bu tipteki sablonlardan en az kullanilani (esitlikte rastgele)."""
    adaylar = [k for k in s["sablonlar"] if k.startswith(onek) and k not in haric]
    k = s.setdefault("kullanim", {})
    random.shuffle(adaylar)
    return sorted(adaylar, key=lambda a: k.get(a, 0))


def _ciz(s, tip, metin, varliklar, hedef, rol_ad):
    (W, H), rol = TIPLER[tip]
    sab = s["sablonlar"][tip]["html"]
    tuval = {"ad": rol_ad, "boyut": (W, H), "rol": rol,
             "metin": {k.lower(): metin.get(k) for k in ("HEADLINE", "LINE", "PRICE")
                       if metin.get(k) and "{{" + k + "}}" in sab}}
    sayfa = uretken._sayfa(doldur(s["sablonlar"][tip]["html"], tip, metin, varliklar), tuval, s["dil"], varliklar)
    olc = uretken._ciz_ve_olc(sayfa, tuval, hedef)
    return not olc.get("sert"), olc


def ciz_set(urun, gorsel_yollari, taslak, klasor, tur=None, gunluk=print):
    """Gunun icerigini tasarim sistemiyle cizer. -> {"dil", "dosyalar"} ya da None (sistem yok)."""
    s = _oku()
    if not s.get("sablonlar"):
        return None
    m = AYAR["marka"]
    v = _varliklar(gorsel_yollari)
    foto_sayisi = len({str(g) for g in gorsel_yollari})
    temel = {"HEADLINE": taslak.get("headline") or urun["ad"], "PRICE": urun.get("fiyat_metni") or "",
             "OLD_PRICE": urun.get("eski_fiyat_metni") or "", "CTA": m.get("cta") or "", "WEB": m.get("web") or "",
             "HOOK": taslak.get("hook") or ""}
    dosyalar, kullanim = [], s.setdefault("kullanim", {})

    def bir(onek, metin, hedef, rol_ad, varlik=None):
        for tip in _sec(s, onek):
            ok, olc = _ciz(s, tip, metin, varlik or v, hedef, rol_ad)
            if ok:
                kullanim[tip] = kullanim.get(tip, 0) + 1
                gunluk(f"[TASARIM] {rol_ad}: sistem sablonu {tip}")
                return True
            gunluk(f"[TASARIM] {rol_ad}: {tip} bu metne sigmadi ({'; '.join(olc['sert'][:2])}), siradaki")
        return False

    post = klasor / "post_1080x1350.jpg"
    if not bir("post", temel, post, "post"):
        return None
    dosyalar.append(post)
    if tur in (None, "post") and bir("story", temel, klasor / "story_1080x1920.jpg", "story"):
        dosyalar.append(klasor / "story_1080x1920.jpg")
    if tur in (None, "carousel"):
        import shutil
        satirlar = [str(x).strip() for x in (taslak.get("carousel_lines") or []) if str(x).strip()][:4] \
            or [taslak.get("headline") or urun["ad"]]
        maddeler = ([str(x).strip() for x in (taslak.get("carousel_points") or []) if str(x).strip()]
                    or musteri.carousel_maddeleri())[:3]
        shutil.copyfile(post, klasor / "carousel_1.jpg")
        dosyalar.append(klasor / "carousel_1.jpg")
        no = 2
        for i, satir in enumerate(satirlar):
            foto_var = i + 2 <= foto_sayisi                    # 2. fotograftan itibaren her karta yeni foto
            onek = "slayt_foto" if foto_var and i % 2 == 0 else "slayt_tip"
            v2 = dict(v, FOTO1=v.get(f"FOTO{i + 2}", v["FOTO1"])) if foto_var else v
            hedef = klasor / f"carousel_{no}.jpg"
            if bir(onek, dict(temel, LINE=satir, NO=str(i + 1)), hedef, f"carousel_{no}", v2) or \
                    bir("slayt_tip" if onek == "slayt_foto" else "slayt_foto", dict(temel, LINE=satir, NO=str(i + 1)),
                        hedef, f"carousel_{no}", v2):
                dosyalar.append(hedef)
                no += 1
        hedef = klasor / f"carousel_{no}.jpg"
        if bir("liste", dict(temel, POINT1=maddeler[0] if maddeler else "", POINT2=maddeler[1] if len(maddeler) > 1 else "",
                              POINT3=maddeler[2] if len(maddeler) > 2 else ""), hedef, f"carousel_{no}"):
            dosyalar.append(hedef)
    DOSYA.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"dil": s["dil"], "dosyalar": dosyalar, "puanlar": {}, "sistem": True}


def son_kart(gorsel_yollari, hedef, gunluk=print):
    """Reels kapanis karti: sistemdeki 'son' sablonu; yoksa sade modern kart (logo merkezde)."""
    s = _oku()
    v = _varliklar(gorsel_yollari)
    m = AYAR["marka"]
    metin = {"CTA": m.get("cta") or "", "WEB": m.get("web") or "", "MARKA": musteri.ad()}
    if s.get("sablonlar", {}).get("son"):
        ok, olc = _ciz(s, "son", metin, v, hedef, "reels_son")
        if ok:
            gunluk("[TASARIM] reels kapanis: sistem sablonu")
            return hedef
    dil = s.get("dil") or uretken._varsayilan_dil()
    tuval = {"ad": "reels_son", "boyut": (1080, 1920), "rol": "", "metin": {}}
    sayfa = uretken._sayfa(modern_duzen.kapanis(1080, 1920, metin, dil, v), tuval, dil, v)
    olc = uretken._ciz_ve_olc(sayfa, tuval, hedef)
    gunluk("[TASARIM] reels kapanis: sade modern kart" + (f" (sorun: {olc['sert'][:1]})" if olc.get("sert") else ""))
    return hedef if not olc.get("sert") else None
