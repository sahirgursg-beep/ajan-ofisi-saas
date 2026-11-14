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
YENILEME_GUN = 30
EN_COK_DENEME = 2      # tutmayan sablon tipi en fazla bu kadar gun yeniden denenir (maliyet)
GECME = 6.0            # hakem puani: bu ve ustu dogrudan kabul
KABUL = 5.0            # iki turdan sonra, olcumu temiz en iyi surum en az bu puandaysa kabul

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


def _suresi_doldu(s):
    try:
        return datetime.fromisoformat(s["tarih"]) < datetime.now() - timedelta(days=YENILEME_GUN)
    except (KeyError, ValueError):
        return True


def _eksikler(s):
    """Sistemde olmayan sablon tipleri: gunde bir, toplamda EN_COK_DENEME kez yeniden denenir."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    d = s.get("denendi") or {}
    out = []
    for t in _tipler():
        if t in s.get("sablonlar", {}):
            continue
        k = d.get(t)
        k = {"gun": k, "kez": 1} if isinstance(k, str) else (k or {})
        if k.get("gun") != bugun and k.get("kez", 0) < EN_COK_DENEME:
            out.append(t)
    return out


def _tipler():
    """Paketin urettigi formatlara gereken sablonlar (yalniz post ureten pakette carousel/Reels sablonu kurulmaz)."""
    try:
        from . import paketler
        f = set(paketler.aktif().get("formatlar") or [])
    except Exception:
        f = set()
    if not f or f >= {"post", "carousel", "reels"}:
        return list(TIPLER)
    return [t for t in TIPLER if t.startswith(("post", "story")) or (t.startswith(("slayt", "liste")) and "carousel" in f)
            or (t == "son" and "reels" in f)]


def eski_mi():
    """Kurulum/yenileme gerekli mi: hic yok, suresi dolmus ya da eksik sablonu var (gunde en fazla bir deneme)."""
    s = _oku()
    return not s.get("dil") or _suresi_doldu(s) or bool(_eksikler(s))


# ---------------------------------------------------------------- metin sigdirma
def _boy(metin, tip, alan):
    """Baslik/satir boyu metin uzunlugundan (sablon var(--h) / var(--l) kullanir)."""
    n = len(metin or "")
    taban = {"HEADLINE": 124, "LINE": 96, "HOOK": 110}.get(alan, 96)
    if tip in ("slayt_tip",):
        taban += 16
    k = 1 if n <= 16 else .86 if n <= 28 else .74 if n <= 42 else .62 if n <= 60 else .52
    return int(taban * k)


IZINLI = {"post": ("HEADLINE", "HOOK", "PRICE", "OLD_PRICE", "CTA", "WEB"),
          "story": ("HEADLINE", "HOOK", "PRICE", "OLD_PRICE", "CTA", "WEB"),
          "slayt": ("LINE", "NO"), "liste": ("POINT1", "POINT2", "POINT3", "PRICE", "CTA", "WEB"), "son": ("CTA", "WEB")}


def izinli(tip):
    return IZINLI.get(tip.split("_")[0], YER_TUTUCULAR)


BOS = '<i data-bos></i>'
TEMIZLE_JS = ("<script>document.querySelectorAll('[data-bos]').forEach(function(b){"
              "var e=b.closest('[data-alan]')||b.closest('[data-metin]')||b.parentElement;"
              "while(e&&!e.classList.contains('tuval')){var p=e.parentElement;e.remove();"
              "if(!p||p.classList.contains('tuval')||p.textContent.trim()||p.querySelector('img'))break;e=p;}});</script>")


def doldur(sablon, tip, metin, varliklar):
    """Yer tutuculari doldurur. Bu tuval tipinin almadigi ya da bos kalan her alanin ogesi (ve onunla bosalan
    kapsayicisi: 'No.' rozeti, ikon cipi...) sayfadan kaldirilir; yarim etiket kalmaz."""
    h, bos_var = sablon, False
    for k in YER_TUTUCULAR:
        deger = str(metin.get(k, "") or "").strip() if k in izinli(tip) else ""
        if not deger and "{{" + k + "}}" in h:
            bos_var = True
        h = h.replace("{{" + k + "}}", uretken.html_kac(deger) if deger else BOS)
    for k, v in varliklar.items():
        h = h.replace("{{" + k + "}}", v)
    h = re.sub(r"\{\{[A-Z0-9_]+\}\}", "", h)
    stil = (f"--h:{_boy(metin.get('HEADLINE') or metin.get('HOOK'), tip, 'HEADLINE')}px;"
            f"--l:{_boy(metin.get('LINE'), tip, 'LINE')}px;")
    h = h.replace('class="tuval"', f'class="tuval" style="{stil}"', 1)
    return h + (TEMIZLE_JS if bos_var else "")


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
        "PLACEHOLDERS (write them literally, the system fills them). This template may use ONLY these text "
        f"placeholders: {' '.join('{{' + k + '}}' for k in izinli(tip))}. Use each at most once; write NO other words "
        "of your own (no labels like 'No.', 'Step', 'Tip', no invented taglines, no icon-only chips); "
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


def ornekler(urun, taslak):
    """Sablon denemesi icin metinler: 'gercek' = bugunun gercek metni (hakem bunu gorur; konuyla uyumlu),
    'uzun' = ayni alanlarin uzatilmis hali (yalniz olculur, tasma testi). Sabit, konusuz ornek yok."""
    m = AYAR["marka"]
    satirlar = [str(x).strip() for x in (taslak.get("carousel_lines") or []) if str(x).strip()]
    maddeler = [str(x).strip() for x in (taslak.get("carousel_points") or []) if str(x).strip()] \
        or list(musteri.carousel_maddeleri())[:3]
    baslik = taslak.get("headline") or urun["ad"]
    fiyatli = not (urun.get("ngn") == 0 or urun.get("fiyat") == 0)
    gercek = {"HEADLINE": baslik, "LINE": satirlar[0] if satirlar else baslik,
              "PRICE": (urun.get("fiyat_metni") or "") if fiyatli else "",
              "OLD_PRICE": (urun.get("eski_fiyat_metni") or "") if fiyatli else "", "CTA": m.get("cta") or "Learn more",
              "HOOK": taslak.get("hook") or baslik, "NO": "1",
              "POINT1": maddeler[0] if maddeler else "", "POINT2": maddeler[1] if len(maddeler) > 1 else "",
              "POINT3": maddeler[2] if len(maddeler) > 2 else ""}
    uzun = dict(ORNEK["uzun"])
    for k in ("HEADLINE", "LINE", "HOOK", "POINT1", "POINT2", "POINT3"):     # gunden gune degisen alanlar
        if gercek.get(k):
            uzun[k] = (gercek[k] + " " + gercek[k])[:60] if len(gercek[k]) < 40 else gercek[k][:70]
    uzun["CTA"] = gercek["CTA"]                 # CTA markanin sabit metni: oldugu gibi denenir
    if not gercek["PRICE"]:
        uzun["PRICE"] = uzun["OLD_PRICE"] = ""
    return {"kisa": gercek, "uzun": uzun}


def _olc(tip, html_, dil, varliklar, klasor, orn):
    """Gercek ve uzun metinle cizip olcer (tarayici: ana is parcaciginda). -> (sert_sorunlar, gercek_metinli_jpg|None)"""
    (W, H), rol = TIPLER[tip]
    sorunlar, kisa_yol = [], None
    for ad, ornek in orn.items():
        m = dict(ornek, WEB=AYAR["marka"].get("web") or "example.com")
        tuval = {"ad": tip, "boyut": (W, H), "rol": rol,
                 "metin": {k.lower(): m[k] for k in ("HEADLINE", "LINE") if m.get(k) and "{{" + k + "}}" in html_}}
        yol = klasor / f"_sistem_{tip}_{ad}.jpg"
        try:
            olc = uretken._ciz_ve_olc(uretken._sayfa(doldur(html_, tip, m, varliklar), tuval, dil, varliklar), tuval, yol)
        except Exception as e:
            olc = {"sert": [f"render error: {str(e)[:80]}"], "yumusak": []}
        sorunlar += [f"[{'long' if ad == 'uzun' else 'real'} text] {x}" for x in olc.get("sert", [])]
        if ad == "kisa":
            kisa_yol = yol
        else:
            yol.unlink(missing_ok=True)
    return sorunlar, kisa_yol


def kur(urun, gorsel_yollari, taslak, gunluk=print, zorla=False):
    """Tasarim sistemini kurar, yeniler ya da eksik sablonlarini tamamlar. -> sistem dict ya da None (model yok).

    Hiz icin: sablonlar paralel yazilir, tarayicida sirayla olculur, hakem puanlari paralel alinir; tutmayanlar
    bir kez (yine paralel) duzeltilir. Sonuc her durumda kaydedilir: tutanlar kalir, tutmayan tip ertesi gune
    kadar yeniden denenmez (her uretimde dakikalarca beklenmesin)."""
    import time
    s = _oku()
    if not llm.hazir():
        return s or None
    tam = zorla or not s.get("dil") or _suresi_doldu(s)
    if tam:
        eski = s.get("sablonlar") or {}
        dil = uretken.dil_sec(urun, taslak, None) or uretken._varsayilan_dil()
        dil["palet"] = modern_duzen.palet_onar(dil.get("palet"))
        s = {"tarih": datetime.now().isoformat(timespec="minutes"), "dil": dil, "sablonlar": {}, "kullanim": {},
             "denendi": {}}
        hedefler = _tipler()
    else:
        eski, dil, hedefler = {}, s["dil"], _eksikler(s)
    if not hedefler:
        return s
    from . import arastirma
    t0 = time.time()
    gunluk(f"Tasarim sistemi {'kuruluyor' if tam else 'tamamlaniyor'}: '{dil['stil']}', {len(hedefler)} sablon")
    varliklar = _varliklar(gorsel_yollari)
    klasor = VERI / "_sistem_tmp"
    klasor.mkdir(parents=True, exist_ok=True)
    ozet, orn = arastirma.istem_ozeti(), ornekler(urun, taslak)

    def yaz(tip, ek=""):
        try:
            return uretken._temizle(llm.tasarim_sor(uretken.SISTEM, _istem(tip, dil, ozet) + ek, sicaklik=0.8))
        except Exception as e:
            gunluk(f"[TASARIM] sistem {tip}: yazilamadi ({type(e).__name__})")
            return None

    def puanla(is_):
        tip, yol = is_
        return uretken._gorsel_puan(yol, {"ad": tip, "rol": TIPLER[tip][1]})

    with ThreadPoolExecutor(max_workers=5) as h:
        html_ = dict(zip(hedefler, h.map(yaz, hedefler)))
        bekleyen, en_iyi = list(hedefler), {}                       # en_iyi[tip] = (puan, html) olcumu temiz surum
        for tur_no in range(2):
            olcum = {}
            for tip in bekleyen:                                    # tarayici tek is parcaciginda
                if not html_.get(tip) or ".tuval" not in html_[tip]:
                    olcum[tip] = (["no valid HTML returned"], None)
                else:
                    olcum[tip] = _olc(tip, html_[tip], dil, varliklar, klasor, orn)
            temiz = [(t, y) for t, (sert, y) in olcum.items() if not sert and y]
            puanlar = dict(zip([t for t, _ in temiz], h.map(puanla, temiz)))
            kalan = {}
            for tip in bekleyen:
                sert, yol = olcum[tip]
                puan, notlar = puanlar.get(tip, (None, []))
                if yol:
                    Path(yol).unlink(missing_ok=True)
                if not sert:
                    p = puan if puan is not None else GECME
                    if tip not in en_iyi or p > en_iyi[tip][0]:
                        en_iyi[tip] = (p, html_[tip])
                    if p >= GECME:
                        gunluk(f"[TASARIM] sistem {tip}: kabul (tur {tur_no + 1}, puan {puan})")
                        continue
                kalan[tip] = sert + ([] if sert else (notlar or ["make it more modern and striking"]))
                gunluk(f"[TASARIM] sistem {tip}: tur {tur_no + 1}, puan {puan}, sorun: {'; '.join(kalan[tip][:2])}")
            bekleyen = list(kalan)
            if not bekleyen or tur_no == 1:
                break
            ekler = ["\n\nA first version had these problems; write a better one that fixes ALL of them:\n- "
                     + "\n- ".join(kalan[t][:8]) + "\n\nFirst version:\n" + (html_.get(t) or "")[:6000] for t in bekleyen]
            html_.update(zip(bekleyen, h.map(yaz, bekleyen, ekler)))
    bugun = datetime.now().strftime("%Y-%m-%d")
    for tip in hedefler:
        if tip in en_iyi and en_iyi[tip][0] >= KABUL:
            s["sablonlar"][tip] = {"html": en_iyi[tip][1], "puan": en_iyi[tip][0]}
        else:
            onceki = (s.get("denendi") or {}).get(tip)
            kez = 1 if not isinstance(onceki, dict) else onceki.get("kez", 0) + 1
            s.setdefault("denendi", {})[tip] = {"gun": bugun, "kez": kez if not isinstance(onceki, str) else 2}
            if tip in eski:                                         # yenisi tutmadi: calisan eski surum kalsin
                s["sablonlar"][tip] = eski[tip]
    s["model"] = llm.tasarim_modeli_adi()
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    gunluk(f"Tasarim sistemi: {len(s['sablonlar'])}/{len(_tipler())} sablon hazir ({', '.join(s['sablonlar']) or 'yok'}), "
           f"{int(time.time() - t0)} sn. Eksik tuvaller modern duzenlerle cizilir.")
    return s


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
def _ciz(s, tip, metin, varliklar, hedef, rol_ad):
    (W, H), rol = TIPLER[tip]
    sab = s["sablonlar"][tip]["html"]
    tuval = {"ad": rol_ad, "boyut": (W, H), "rol": rol,
             "metin": {k.lower(): metin.get(k) for k in ("HEADLINE", "LINE", "PRICE")
                       if metin.get(k) and "{{" + k + "}}" in sab}}
    sayfa = uretken._sayfa(doldur(s["sablonlar"][tip]["html"], tip, metin, varliklar), tuval, s["dil"], varliklar)
    olc = uretken._ciz_ve_olc(sayfa, tuval, hedef)
    return not olc.get("sert"), olc


def _son_kontrol(yol):
    """Yayindan once kapaga son bakis (gorme modeli): bos rozet/cip, ust uste binen ya da okunmayan yazi var mi?
    -> sorun metni ya da None (sorun yok / model yok)."""
    try:
        c = llm.gor("You are the final quality check before a social media image is published. Answer ONLY with valid JSON.",
                    "Look for DEFECTS only (not taste): empty badges or chips, placeholder fragments like 'No.' with "
                    "nothing after, icons with no label, texts overlapping each other, text cut off, unreadable text, "
                    "a headline covering a face. "
                    'Return JSON: {"ok": true|false, "problem": "<the defect in max 10 words, empty if ok>"}', [yol])
    except Exception:
        return None
    if isinstance(c, dict) and c.get("ok") is False:
        return str(c.get("problem") or "defect")[:80]
    return None


def ciz_set(urun, gorsel_yollari, taslak, klasor, tur=None, gunluk=print):
    """Gunun icerigini cizer: once markanin sistem sablonlari (en az kullanilan), tutmayan/eksik her tuval icin
    modern duzen kutuphanesi. Yapay zeka cagrisi yok -> saniyeler surer, eski sablonlara donulmez.
    -> {"dil", "dosyalar", ...} ya da None (tarayici yok / post hic cizilemedi)."""
    import shutil
    s = _oku()
    dil = s.get("dil") or uretken._varsayilan_dil()
    dil["palet"] = modern_duzen.palet_onar(dil.get("palet"))
    sablonlar, kullanim = s.get("sablonlar") or {}, s.setdefault("kullanim", {})
    m = AYAR["marka"]
    v = _varliklar(gorsel_yollari)
    foto_sayisi = len({str(g) for g in gorsel_yollari})
    fiyatli = not (urun.get("ngn") == 0 or urun.get("fiyat") == 0)     # fiyatsiz icerikte "0" etiketi olmasin
    temel = {"HEADLINE": taslak.get("headline") or urun["ad"], "PRICE": (urun.get("fiyat_metni") or "") if fiyatli else "",
             "OLD_PRICE": (urun.get("eski_fiyat_metni") or "") if fiyatli else "", "CTA": m.get("cta") or "",
             "WEB": m.get("web") or "", "HOOK": taslak.get("hook") or ""}
    kucuk = lambda mt: {"headline": mt.get("HEADLINE"), "line": mt.get("LINE"), "price": mt.get("PRICE"),
                        "old_price": mt.get("OLD_PRICE"), "cta": mt.get("CTA"), "hook": mt.get("HOOK"),
                        "small": mt.get("WEB")}
    dosyalar, kullanilan_duzen = [], set()
    kontrol = {"kalan": 2}                      # kapak icin en fazla 2 son kontrol cagrisi

    def bir(onekler, metin, hedef, rol_ad, boyut, varlik=None, maddeler=None):
        vv = varlik or v
        for onek in onekler:                                        # 1) markanin sistem sablonlari
            for tip in sorted((k for k in sablonlar if k.startswith(onek)),
                              key=lambda a: (kullanim.get(a, 0), random.random())):
                try:
                    ok, olc = _ciz(s, tip, metin, vv, hedef, rol_ad)
                except Exception as e:
                    ok, olc = False, {"sert": [f"{type(e).__name__}: {str(e)[:60]}"]}
                if ok and rol_ad == "post" and kontrol["kalan"] > 0:
                    kontrol["kalan"] -= 1
                    sorun = _son_kontrol(hedef)
                    if sorun:
                        gunluk(f"[TASARIM] post: {tip} son kontrolden gecemedi ({sorun}), siradaki")
                        continue
                if ok:
                    kullanim[tip] = kullanim.get(tip, 0) + 1
                    gunluk(f"[TASARIM] {rol_ad}: sistem sablonu {tip}")
                    return True
                gunluk(f"[TASARIM] {rol_ad}: {tip} bu metne sigmadi ({'; '.join(olc['sert'][:2])})")
        mt = {k: x for k, x in kucuk(metin).items() if x}           # 2) modern duzen kutuphanesi
        if maddeler is not None:
            mt = {"points": maddeler, "price": metin.get("PRICE"), "cta": metin.get("CTA")}
        elif metin.get("LINE"):
            mt = {"line": metin["LINE"], "no": metin.get("NO")}
        tuval = {"ad": rol_ad, "boyut": boyut, "rol": "", "metin": mt, "fotosuz": not vv.get("FOTO1")}
        for ad in modern_duzen.adaylar(tuval, 4, haric=kullanilan_duzen) + modern_duzen.adaylar(dict(tuval, fotosuz=False), 4):
            try:
                olc = uretken._ciz_ve_olc(uretken._sayfa(modern_duzen.ciz(ad, tuval, dil, vv), tuval, dil, vv), tuval, hedef)
            except Exception as e:
                olc = {"sert": [f"{type(e).__name__}: {str(e)[:60]}"]}
            if not olc.get("sert"):
                kullanilan_duzen.add(ad)
                gunluk(f"[TASARIM] {rol_ad}: modern duzen {ad}")
                return True
        Path(hedef).unlink(missing_ok=True)
        gunluk(f"[TASARIM] {rol_ad}: cizilemedi")
        return False

    post = klasor / "post_1080x1350.jpg"
    if not bir(("post",), temel, post, "post", (1080, 1350)):
        return None
    dosyalar.append(post)
    if tur in (None, "post") and bir(("story",), temel, klasor / "story_1080x1920.jpg", "story", (1080, 1920)):
        dosyalar.append(klasor / "story_1080x1920.jpg")
    if tur in (None, "carousel"):
        satirlar = [str(x).strip() for x in (taslak.get("carousel_lines") or []) if str(x).strip()][:4] \
            or [taslak.get("headline") or urun["ad"]]
        maddeler = ([str(x).strip() for x in (taslak.get("carousel_points") or []) if str(x).strip()]
                    or list(musteri.carousel_maddeleri()))[:3]
        shutil.copyfile(post, klasor / "carousel_1.jpg")
        dosyalar.append(klasor / "carousel_1.jpg")
        no = 2
        for i, satir in enumerate(satirlar):
            foto_var = i + 2 <= foto_sayisi                         # kapak 1. fotoyu kullandi; kartlar siradakini
            v2 = dict(v, FOTO1=v.get(f"FOTO{i + 2}", v["FOTO1"])) if foto_var else dict(v, FOTO1="")
            sira = ("slayt_foto", "slayt_tip") if foto_var and i % 2 == 0 else ("slayt_tip", "slayt_foto") if foto_var \
                else ("slayt_tip",)
            hedef = klasor / f"carousel_{no}.jpg"
            if bir(sira, dict(temel, LINE=satir, NO=str(i + 1)), hedef, f"carousel_{no}", (1080, 1350), v2):
                dosyalar.append(hedef)
                no += 1
        hedef = klasor / f"carousel_{no}.jpg"
        if maddeler and bir(("liste",), dict(temel, **{f"POINT{j}": x for j, x in enumerate(maddeler, 1)}), hedef,
                            f"carousel_{no}", (1080, 1350), maddeler=maddeler):
            dosyalar.append(hedef)
    if s.get("dil"):
        try:
            DOSYA.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
    return {"dil": dil, "dosyalar": dosyalar, "puanlar": {}, "sistem": bool(sablonlar)}


def son_kart(gorsel_yollari, hedef, gunluk=print):
    """Reels kapanis karti: sistemdeki 'son' sablonu; yoksa sade modern kart (logo merkezde)."""
    s = _oku()
    v = _varliklar(gorsel_yollari)
    m = AYAR["marka"]
    metin = {"CTA": m.get("cta") or "", "WEB": m.get("web") or "", "MARKA": musteri.ad()}
    if (s.get("sablonlar") or {}).get("son"):
        try:
            ok, olc = _ciz(s, "son", metin, v, hedef, "reels_son")
        except Exception:
            ok = False
        if ok:
            gunluk("[TASARIM] reels kapanis: sistem sablonu")
            return hedef
    dil = s.get("dil") or uretken._varsayilan_dil()
    tuval = {"ad": "reels_son", "boyut": (1080, 1920), "rol": "", "metin": {}}
    sayfa = uretken._sayfa(modern_duzen.kapanis(1080, 1920, metin, dil, v), tuval, dil, v)
    olc = uretken._ciz_ve_olc(sayfa, tuval, hedef)
    gunluk("[TASARIM] reels kapanis: sade modern kart" + (f" (sorun: {olc['sert'][:1]})" if olc.get("sert") else ""))
    return hedef if not olc.get("sert") else None
