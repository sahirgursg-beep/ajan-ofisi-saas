"""Uretken tasarim: sabit sablon yok. Sanat Yonetmeni her icerik icin once bir gorsel dil (stil, palet, font,
fikir) secer, sonra her tuval (post, story, carousel kartlari) icin HTML/CSS'i sifirdan yazar.

Kalite kapisi (sirayla):
  1. Guvenlik temizligi: script, olay ozellikleri, dis adresler atilir; yalnizca verdigimiz fotograf/logo/font.
  2. Olcum (tarayicida): her yazi tuvalin icinde mi, tasiyor mu, ust uste biniyor mu, en kucuk punto, zorunlu
     metinler (baslik, fiyat) gercekten sayfada mi, fotograflar yuklendi mi.
  3. Gorme modeli puanlar: modern mi, okunuyor mu, fotograf one cikiyor mu (1-10).
Sorun varsa tasarimci ayni tuvali sorun listesiyle bir kez daha yazar; yine olmazsa o tuval eski sablona duser.
Boylece her gun farkli ama her zaman okunakli tasarimlar cikar.
"""
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import fontlar, llm, marka, modern_duzen, musteri, tasarim
from .ayarlar import AYAR, VERI

GECMIS = VERI / "uretken_gecmis.json"
GUVENLI_KENAR = 48

# Stil sozlugu: kalip degil, yon. Sanat Yonetmeni bunlari karistirabilir ya da yenisini uretebilir.
STILLER = {
    "bento": "rounded tiles of different sizes in a grid (photo tile, big-claim tile, small tag tiles), 16-24px gaps, soft shadows",
    "poster_tipografi": "oversized headline (150-260px) with tight leading as the hero, photo smaller or cut by the type, very bold contrast",
    "sticker_pop": "full-bleed photo with rotated sticker labels, pill tags, a hand-drawn SVG arrow or circle pointing at the subject",
    "renk_blok": "two or three flat color blocks on a strict Swiss grid, photo in one block, left-aligned type, generous whitespace",
    "cam_kart": "blurred and darkened photo as background with a sharp crop of it on top and a frosted-glass card (backdrop-filter) for text",
    "gradient_mesh": "soft multi-color gradient blobs (radial-gradients) behind a crisp photo card, modern app aesthetic",
    "dev_rakam": "one giant number or price as the visual anchor (300px+) with a tiny context line and the photo beside it",
    "polaroid_kolaj": "two or three photos as tilted polaroid/print cards with tape strips, playful and personal",
    "outline_type": "huge outlined (-webkit-text-stroke) words behind the photo subject, layered depth",
    "bolunmus": "split screen: photo on one half, solid color with type on the other, a thin divider or overlapping badge",
    "minimal_lux": "lots of negative space, one small elegant photo, refined sans headline, tiny caps details - premium and calm",
}
KART_TIPLERI = (
    "big statement: the line huge across the slide, small photo crop as accent",
    "photo-led: full-bleed or large photo with the line on a bold sticker or pill",
    "number/step: a giant step number or icon-like shape plus the line",
    "split: half photo, half solid color with the line",
    "quote card: the line large inside one clean card over a blurred photo",
    "detail zoom: a tight crop of the photo in a rounded window with the line beside it",
)
YASAK = ("newspaper columns", "body text paragraphs on the image", "thin hairline rules everywhere",
         "gold frames", "centered serif headline over a gradient as the only idea", "clip-art", "emoji walls")


def _oku(yol, vars_):
    try:
        return json.loads(Path(yol).read_text(encoding="utf-8"))
    except Exception:
        return vars_


def gecmis(n=8):
    return _oku(GECMIS, [])[-n:]


def _gecmise_yaz(kayit):
    g = _oku(GECMIS, [])
    GECMIS.parent.mkdir(parents=True, exist_ok=True)
    GECMIS.write_text(json.dumps((g + [kayit])[-40:], ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 1. gorsel dil
def dil_sec(urun, taslak, tur):
    from . import analiz
    son = gecmis()
    fontlar_ = fontlar.aciklama(fontlar.uygun_ciftler())
    cevap = llm.sor(
        "You are the creative director of a top social media agency in 2026. Your feeds look like the best "
        "Instagram accounts right now: bold, modern, thumb-stopping, never like a newspaper or a template. "
        "Answer ONLY with valid JSON.",
        f"Brand: {musteri.ad()} - {musteri.tanim()}. Brand colors: {AYAR['marka'].get('renk_koyu')}, "
        f"{AYAR['marka'].get('renk_altin')}.\n"
        f"Today's content ({tur}): {urun['ad']} | {taslak.get('headline', '')} | {urun.get('aciklama', '')[:200]}\n"
        f"{analiz.istem_ozeti()}\n"
        f"Style directions you can use, mix or go beyond:\n" + "\n".join(f"- {k}: {v}" for k, v in STILLER.items())
        + f"\nRecently used (do NOT repeat style+palette): {[(g.get('stil'), g.get('palet', {}).get('bg')) for g in son]}\n"
        f"Font pairs (headline + body; choose by key): " + "; ".join(f"{k} = {v}" for k, v in fontlar_.items())
        + "\nPrefer clean modern sans or bold display pairs; use a serif pair only for clearly luxury/heritage brands.\n"
        + f"Never: {', '.join(YASAK)}.\n"
        'Return JSON: {"stil": "<style key or a new short name>", "fikir": "<the one creative idea of this design, '
        'one sentence>", "font": "<font pair key>", "palet": {"bg": "#hex", "ink": "#hex", "accent": "#hex", '
        '"accent2": "#hex"}, "dokular": "<shapes/textures/details to use, one sentence>", '
        '"neden": "<one short Turkish sentence for the team: why this look for this post>"}',
        json_mod=True, sicaklik=0.95)
    if not isinstance(cevap, dict):
        return None
    hex_ = lambda h, v: h if isinstance(h, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", h) else v
    p = cevap.get("palet") if isinstance(cevap.get("palet"), dict) else {}
    font = cevap.get("font") if cevap.get("font") in fontlar_ else random.choice(list(fontlar_))
    return {"stil": str(cevap.get("stil") or random.choice(list(STILLER)))[:40],
            "fikir": str(cevap.get("fikir") or "")[:200], "font": font,
            "palet": {"bg": hex_(p.get("bg"), "#F4F1EC"), "ink": hex_(p.get("ink"), "#151515"),
                      "accent": hex_(p.get("accent"), "#FF5A36"), "accent2": hex_(p.get("accent2"), "#2D5BFF")},
            "dokular": str(cevap.get("dokular") or "")[:200], "neden": str(cevap.get("neden") or "")[:200]}


PALETLER = ({"bg": "#F4F1EA", "ink": "#121212", "accent": "#FF5A36", "accent2": "#2D5BFF"},
            {"bg": "#0F1115", "ink": "#0F1115", "accent": "#C6F432", "accent2": "#7C5CFF"},
            {"bg": "#EEF3F8", "ink": "#0B2545", "accent": "#FFB703", "accent2": "#13315C"},
            {"bg": "#FFF4EC", "ink": "#2B1A12", "accent": "#E4572E", "accent2": "#17BEBB"})


def _varsayilan_dil():
    modern = [k for k in fontlar.uygun_ciftler() if k in ("cagdas", "teknoloji", "kurumsal", "sanatsal", "brutal", "afis")] \
        or fontlar.uygun_ciftler()
    return {"stil": "modern", "fikir": "", "font": random.choice(modern), "palet": random.choice(PALETLER),
            "dokular": "", "neden": "varsayilan modern dil"}


# ---------------------------------------------------------------- 2. tuvaller
def tuvaller(urun, taslak, tur, foto_sayisi):
    """Her tuval: ad, boyut, rol aciklamasi, uzerinde OLMASI gereken metinler (birebir)."""
    fiyat = urun.get("fiyat_metni") or ""
    eski = urun.get("eski_fiyat_metni") or ""
    cta = AYAR["marka"].get("cta") or ""
    web = AYAR["marka"].get("web") or ""
    temel = {"headline": taslak.get("headline") or urun["ad"], "price": fiyat, "old_price": eski, "cta": cta}
    liste = [{"ad": "post", "boyut": (1080, 1350), "rol": "Instagram/Facebook feed post (4:5). Must stop the scroll.",
              "metin": {**temel, "small": web}}]
    if tur in (None, "post"):
        liste.append({"ad": "story", "boyut": (1080, 1920),
                      "rol": "Instagram story (9:16). Keep top 220px and bottom 340px free of text (app UI).",
                      "metin": {**temel, "hook": taslak.get("hook") or ""}})
    if tur in (None, "carousel"):
        satir = [str(s).strip() for s in (taslak.get("carousel_lines") or []) if str(s).strip()][:4]
        madde = [str(s).strip() for s in (taslak.get("carousel_points") or []) if str(s).strip()][:3] \
            or musteri.carousel_maddeleri()
        # Her kart ayni gorsel dilde ama FARKLI bir duzende: carousel'i kaydirtan sey cesitlilik
        tipler = random.sample(KART_TIPLERI, len(KART_TIPLERI))
        for i, s in enumerate(satir or [taslak.get("headline") or urun["ad"]], 2):
            tip = tipler[(i - 2) % len(tipler)]
            liste.append({"ad": f"carousel_{i}", "boyut": (1080, 1350), "foto": min(i - 1, foto_sayisi),
                          "rol": f"Carousel slide {i} (swipe content). Layout for THIS slide: {tip}. Same palette and "
                                 "fonts as the cover but a different composition from the other slides. No page counter "
                                 "(Instagram shows its own dots).", "metin": {"line": s}})
        son_no = 2 + len(satir or [1])
        liste.append({"ad": f"carousel_{son_no}", "boyut": (1080, 1350), "son": True,
                      "rol": "Last carousel slide: the takeaway and the call to action, as a checklist or stacked "
                             "cards - make people save the post.", "metin": {"points": madde, "price": fiyat, "cta": cta}})
    return liste


def _istem(dil, tuval, foto_bilgi, logo_var, ornek=None):
    W, H = tuval["boyut"]
    metinler = {k: v for k, v in tuval["metin"].items() if v}
    return (
        f"Design ONE {W}x{H}px social media image as HTML+CSS.\nRole: {tuval['rol']}\n"
        f"Visual language (keep it): style '{dil['stil']}' - {STILLER.get(dil['stil'], dil['stil'])}. "
        f"Idea: {dil['fikir']}. Details: {dil['dokular']}. Palette: {json.dumps(dil['palet'])}.\n"
        f"Exact texts to place (use them VERBATIM, nothing else except tiny decorative labels of 1-3 words): "
        f"{json.dumps(metinler, ensure_ascii=False)}\n"
        f"Photos available: {foto_bilgi}. Use them as <img src=\"{{{{FOTO1}}}}\"> etc. with object-fit:cover and "
        "a deliberate object-position. The photo must stay clearly visible (at least 40% of the canvas) unless the "
        "style is pure typography.\n"
        + (f"Main photo of this slide: FOTO{tuval['foto']} (so the slides do not repeat the same image).\n"
           if tuval.get("foto") else "")
        + ("Logo: <img src=\"{{LOGO_KOYU}}\"> on light areas or <img src=\"{{LOGO_ACIK}}\"> on dark areas, "
           "height 56-80px, in a corner.\n" if logo_var else "No logo.\n")
        + "Fonts: headline font-family: var(--bf); body font-family: var(--gf). Headline weight var(--bw).\n"
        "RULES:\n"
        f"- Root element: <div class=\"tuval\"> exactly {W}px x {H}px, position:relative, overflow:hidden.\n"
        f"- Keep every text at least {GUVENLI_KENAR}px from the edges. Headline 64px or larger; nothing under 26px.\n"
        "- Put data-metin on EVERY element that contains text.\n"
        "- Text must never cover the main subject of the photo and must have strong contrast (use a solid panel, "
        "a scrim or a card behind text on photos).\n"
        "- Use modern CSS freely: grid, flex, border-radius, box-shadow, gradients, backdrop-filter, transforms, "
        "clip-path, mix-blend-mode, inline SVG shapes.\n"
        "CRAFT: one dominant element; at most 4 text blocks; headline at most 3 lines - size it from its length "
        "(about 1080px / (characters per line x 0.55)); one consistent corner radius; align everything to a clear grid; "
        "grid/flex children get min-width:0 so long words never push the layout; prices on one line "
        "(white-space:nowrap) and sized to fit.\n"
        "AVOID what reviewers reject: more than ONE call-to-action element; invented UI/screens with tiny fake text "
        "(use real large text only); boxy split-card layouts that read like a dated template; hyphenated or awkwardly "
        "broken headlines (use text-wrap:balance, no hyphens); cropping through a person's face.\n"
        "- No <script>, no external URLs, no web fonts other than the variables, no emoji.\n"
        + (f"The cover (slide 1) uses this CSS - reuse its colors, fonts, radius and details, not its layout:\n"
           f"{ornek[:3000]}\n" if ornek else "")
        + "Return ONLY the HTML: one <style> block followed by the <div class=\"tuval\">...</div>."
    )


SISTEM = ("You are a senior digital designer who writes production HTML/CSS for social media creatives. Your work "
          "looks like 2026's best brand accounts: bold hierarchy, confident color, modern layouts, perfect "
          "alignment, generous spacing. Output only code.")


def _temizle(html_):
    h = re.sub(r"```(?:html)?", "", str(html_ or ""), flags=re.I)
    h = re.sub(r"<\s*script[\s\S]*?<\s*/\s*script\s*>", "", h, flags=re.I)
    h = re.sub(r"<\s*(link|meta|iframe|object|embed|base)[^>]*>", "", h, flags=re.I)
    h = re.sub(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", h, flags=re.I)
    h = re.sub(r"@import[^;]+;", "", h, flags=re.I)
    h = re.sub(r"(?i)(src|href)\s*=\s*([\"'])(?!\{\{)[^\"']*\2", r'\1=""', h)
    h = re.sub(r"url\(\s*['\"]?(?:https?:|//|file:)[^)]*\)", "none", h, flags=re.I)
    h = h.replace("javascript:", "")
    bas = h.find("<style")
    return h[bas:] if bas >= 0 else h


def _sayfa(govde, tuval, dil, varliklar):
    W, H = tuval["boyut"]
    for k, v in varliklar.items():
        govde = govde.replace("{{" + k + "}}", v)
    govde = re.sub(r"\{\{[A-Z0-9_]+\}\}", "", govde)
    from . import dil as dil_
    css = marka.fontlar_css()
    return dil_.html_isareti(
        f"<html><head><meta charset=\"utf-8\">"
        + (f"<link rel=\"stylesheet\" href=\"{tasarim._uri(css)}\">" if css else "")
        + f"<style>{fontlar.css_siniflari()}\nhtml,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;"
        f"background:{dil['palet']['bg']}}} *{{box-sizing:border-box}} img{{display:block}}"
        f".tuval{{width:{W}px!important;height:{H}px!important;overflow:hidden!important}}</style></head>"
        f"<body class=\"f-{dil['font']}\">{govde}</body></html>")


OLC = r"""([W, H, kenar, zorunlu]) => {
  // sert = yayinlanamaz (kesik/tuval disi yazi, eksik zorunlu metin, yuklenmeyen gorsel); yumusak = iyilestirilebilir
  const sert = [], yumusak = [], kutular = [];
  if (!document.querySelector('.tuval')) return {sert: ['root .tuval missing'], yumusak: []};
  document.querySelectorAll('.tuval img').forEach((i) => { if (!i.complete || !i.naturalWidth) sert.push('an image did not load (use only the given placeholders)'); });
  const metinli = [...document.querySelectorAll('.tuval *')].filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
  for (const e of metinli) {
    const s = getComputedStyle(e); if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity < 0.05) continue;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const ad = e.textContent.trim().slice(0, 40), boy = parseFloat(s.fontSize);
    if (r.left < -2 || r.top < -2 || r.right > W + 2 || r.bottom > H + 2) sert.push(`text "${ad}" goes outside the canvas`);
    else if (r.left < kenar - 16 || r.top < kenar - 16 || r.right > W - kenar + 16 || r.bottom > H - kenar + 16) yumusak.push(`text "${ad}" is too close to the edge`);
    if (s.overflow !== 'visible' && (e.scrollWidth > e.clientWidth + 4 || e.scrollHeight > e.clientHeight + 4)) sert.push(`text "${ad}" is cut off by its box`);
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {   // ust kutu kirpiyor mu
      const ps = getComputedStyle(p); if (ps.overflow === 'visible' && ps.overflowX === 'visible' && ps.clipPath === 'none') continue;
      const pr = p.getBoundingClientRect();
      if (r.left < pr.left - 3 || r.right > pr.right + 3 || r.top < pr.top - 3 || r.bottom > pr.bottom + 3) { sert.push(`text "${ad}" is clipped by its container`); break; }
    }
    if (boy < 18) sert.push(`text "${ad}" is unreadable (${boy}px)`); else if (boy < 24) yumusak.push(`text "${ad}" is small (${boy}px)`);
    if (s.transform === 'none' && boy >= 24) kutular.push([ad, r]);
  }
  for (let i = 0; i < kutular.length; i++) for (let j = i + 1; j < kutular.length; j++) {
    const [a, r1] = kutular[i], [b, r2] = kutular[j];
    const ic = (p, q) => p.left <= q.left + 1 && p.right >= q.right - 1 && p.top <= q.top + 1 && p.bottom >= q.bottom - 1;
    const x = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left)), y = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));
    if (!ic(r1, r2) && !ic(r2, r1) && x * y > 0.35 * Math.min(r1.width * r1.height, r2.width * r2.height)) yumusak.push(`texts "${a}" and "${b}" overlap`);
  }
  const yazi = (document.querySelector('.tuval').innerText || '').toLowerCase();
  const kelimeler = (t) => (t.toLowerCase().match(/[\p{L}\p{N}]+/gu) || []);
  const mevcut = new Set(kelimeler(yazi));
  for (const z of zorunlu) {
    const k = kelimeler(z); if (!k.length) continue;
    const bulunan = k.filter((w) => mevcut.has(w)).length;
    if (bulunan / k.length < 0.8) sert.push(`required text missing or changed: "${z}"`);
  }
  return {sert: [...new Set(sert)].slice(0, 8), yumusak: [...new Set(yumusak)].slice(0, 8)};
}"""


def _ciz_ve_olc(html_, tuval, hedef):
    W, H = tuval["boyut"]
    gecici = tasarim.SABLON / f"_uretken_{AYAR['musteri_id']}_{tuval['ad']}.html"
    gecici.write_text(html_, encoding="utf-8")
    sayfa = tasarim._tarayici_al().new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    try:
        sayfa.goto(gecici.as_uri(), wait_until="load")
        sayfa.evaluate("document.fonts.ready")
        sayfa.wait_for_timeout(200)
        m = tuval["metin"]
        zorunlu = [m.get(k) for k in ("headline", "price", "line") if m.get(k)]
        sorunlar = sayfa.evaluate(OLC, [W, H, GUVENLI_KENAR, zorunlu])
        sayfa.screenshot(path=str(hedef), type="jpeg", quality=93, clip={"x": 0, "y": 0, "width": W, "height": H})
        return sorunlar
    finally:
        sayfa.close()
        gecici.unlink(missing_ok=True)


def _gorsel_puan(yol, tuval):
    cevap = llm.gor(
        "You are a strict art director reviewing social media creatives before they are published. Answer ONLY with valid JSON.",
        f"This is a {tuval['ad']} for {musteri.ad()}. Score it 1-10 as a 2026 Instagram creative: modern and "
        "thumb-stopping (not like a newspaper or a dated template), every text easy to read on a phone, clear "
        "hierarchy, the photo/subject well presented, nothing cut off or overlapping.\n"
        'Return JSON: {"score": 1-10, "problems": ["<concrete fix, max 12 words>"]}', [yol])
    if not isinstance(cevap, dict):
        return None, []
    try:
        return float(cevap.get("score")), [str(p)[:120] for p in (cevap.get("problems") or [])][:5]
    except (TypeError, ValueError):
        return None, []


# ---------------------------------------------------------------- 3. hepsi
def tasarla(urun, gorsel_yollari, taslak, klasor, tur=None, gunluk=print, sablon_ciz=None):
    """Uretken tasarim seti. -> {"dil": ..., "dosyalar": [..], "puanlar": {..}} ya da None (eski sablona dus)."""
    if not llm.hazir() or AYAR.get("uretken_tasarim") is False:
        return None
    dil = dil_sec(urun, taslak, tur) or _varsayilan_dil()
    _gecmise_yaz({"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "stil": dil["stil"], "palet": dil["palet"],
                  "font": dil["font"], "deneme": True})          # tutmasa da tekrar secilmesin
    gunluk(f"Gorsel dil: {dil['stil']} — {dil['fikir']}")
    logo = marka.logolar()
    fotolar = [marka.gorsel_hazirla(Path(g)) for g in gorsel_yollari[:4]]
    varliklar = {f"FOTO{i}": tasarim._uri(f) for i, f in enumerate(fotolar, 1)}
    for i in range(len(fotolar) + 1, 5):
        varliklar[f"FOTO{i}"] = varliklar.get("FOTO1", "")
    varliklar["LOGO_KOYU"] = tasarim._uri(logo.get("koyu")) if logo.get("koyu") else ""
    varliklar["LOGO_ACIK"] = tasarim._uri(logo.get("krem")) if logo.get("krem") else ""
    from PIL import Image
    foto_bilgi = ", ".join(
        f"FOTO{i} ({'portrait' if im.height > im.width * 1.1 else 'landscape' if im.width > im.height * 1.1 else 'square'})"
        for i, im in ((i, Image.open(f)) for i, f in enumerate(fotolar, 1))) or "none"
    liste = tuvaller(urun, taslak, tur, len(fotolar))

    def yaz(tuval, ek="", ornek=None):
        mesaj = _istem(dil, tuval, foto_bilgi, bool(varliklar["LOGO_KOYU"]), ornek) + ek
        return _temizle(llm.tasarim_sor(SISTEM, mesaj, sicaklik=0.8))

    sonuc = {"dil": dil, "dosyalar": [], "puanlar": {}}
    kullanilan_duzen = set()          # ayni setteki kartlar ayni yedek duzeni tekrarlamasin
    taslaklar = {}
    with ThreadPoolExecutor(max_workers=4) as h:           # once ana post (diger tuvaller onun dilini izler)
        ana = h.submit(yaz, liste[0]).result()
        taslaklar[liste[0]["ad"]] = ana
        stil_ornek = (ana or "")[:(ana or "").find("</style>") + 8] if ana and "</style>" in ana else (ana or "")[:2500]
        isler = {t["ad"]: h.submit(yaz, t, "", stil_ornek if t["ad"].startswith("carousel") else None) for t in liste[1:]}
        taslaklar.update({k: f.result() for k, f in isler.items()})
    for tuval in liste:
        hedef = klasor / (f"{tuval['ad']}_{tuval['boyut'][0]}x{tuval['boyut'][1]}.jpg"
                          if tuval["ad"] in ("post", "story") else f"{tuval['ad']}.jpg")
        govde, iyi, en_iyi = taslaklar.get(tuval["ad"]), False, None       # en_iyi: (puan, html) sert sorunu olmayan
        for deneme in range(3):
            if not govde or ".tuval" not in govde:
                gunluk(f"{tuval['ad']}: tasarimci gecerli HTML vermedi, tekrar yaziliyor")
                govde = yaz(tuval)
                continue
            sayfa_html = _sayfa(govde, tuval, dil, varliklar)
            try:
                olcum = _ciz_ve_olc(sayfa_html, tuval, hedef)
            except Exception as e:
                olcum = {"sert": [f"render error: {str(e)[:80]}"], "yumusak": []}
            sert, yumusak = olcum.get("sert", []), olcum.get("yumusak", [])
            puan, notlar = None, []
            if not sert:
                puan, notlar = _gorsel_puan(hedef, tuval)
                p = (puan if puan is not None else 7) - 0.5 * len(yumusak)
                if en_iyi is None or p > en_iyi[0]:
                    en_iyi = (p, sayfa_html, puan)
                if (puan is None or puan >= 7) and len(yumusak) <= 1:
                    iyi = True
                    break
            sorunlar = sert + yumusak + notlar
            gunluk(f"{tuval['ad']}: deneme {deneme + 1} - sert {len(sert)}, yumusak {len(yumusak)}, puan {puan}: "
                   f"{'; '.join(sorunlar[:3])}")
            if deneme < 2:
                govde = _temizle(llm.tasarim_sor(SISTEM, _istem(dil, tuval, foto_bilgi, bool(varliklar["LOGO_KOYU"]))
                                         + "\n\nYour previous version had these problems, fix ALL of them and keep "
                                           "the idea:\n- " + "\n- ".join(sorunlar or ["make it more modern"])
                                         + "\n\nPrevious version:\n" + govde[:6000], sicaklik=0.6)) or govde
        dongude_iyi = iyi
        if not iyi:
            # Uretken tasarim esigi gecemedi: modern duzen kutuphanesinden adaylar + en iyi deneme ayni hakemle
            # yarisir; en yuksek puan yayinlanir. Eski (gazete gorunumlu) sablonlara artik donulmez.
            adaylar = []
            if en_iyi:
                adaylar.append((en_iyi[2] if en_iyi[2] is not None else 6.5, "uretken", en_iyi[1]))
            v2 = dict(varliklar)
            if tuval.get("foto"):
                v2["FOTO1"] = varliklar.get(f"FOTO{tuval['foto']}") or varliklar.get("FOTO1", "")
            for ad in modern_duzen.adaylar(tuval, 2, haric=kullanilan_duzen):
                h = _sayfa(modern_duzen.ciz(ad, tuval, dil, v2), tuval, dil, varliklar)
                aday_yol = klasor / f"_aday_{tuval['ad']}_{ad}.jpg"
                try:
                    olc = _ciz_ve_olc(h, tuval, aday_yol)
                    if olc.get("sert"):
                        gunluk(f"{tuval['ad']}: duzen {ad} sert sorun: {olc['sert'][:2]}")
                        continue
                    pn, _ = _gorsel_puan(aday_yol, tuval)
                    adaylar.append((pn if pn is not None else 6.0, ad, h))
                except Exception as e:
                    gunluk(f"{tuval['ad']}: duzen {ad} cizilemedi: {e}")
                finally:
                    aday_yol.unlink(missing_ok=True)
            if adaylar:
                puan_, ad_, h_ = max(adaylar, key=lambda a: a[0])
                gunluk(f"{tuval['ad']}: adaylar {[(a[1], a[0]) for a in adaylar]} -> {ad_}")
                _ciz_ve_olc(h_, tuval, hedef)
                if ad_ != "uretken":
                    kullanilan_duzen.add(ad_)
                en_iyi = (puan_, h_, puan_)
                iyi = dongude_iyi = True
        if iyi and not dongude_iyi:
            _ciz_ve_olc(en_iyi[1], tuval, hedef)            # sert sorunu olmayan en iyi deneme yayinlanir
        if iyi:
            sonuc["puanlar"][tuval["ad"]] = (en_iyi or (None, None, None))[2]
            sonuc["dosyalar"].append(hedef)
        elif tuval["ad"] == "post":
            return None                                     # hicbir aday cizilemediyse (tarayici yok vb.)
        else:
            Path(hedef).unlink(missing_ok=True)
    if tur in (None, "carousel"):
        # Tutan kartlar sirayla numaralanir (kartta sayac yok); hic kart tutmadiysa eski carousel devralir
        kartlar = [t for t in liste if t["ad"].startswith("carousel_")]
        tutan = [klasor / f"{t['ad']}.jpg" for t in kartlar if (klasor / f"{t['ad']}.jpg").exists()]
        if tutan:
            import shutil
            gecici = []
            for i, y in enumerate(tutan, 2):
                g = klasor / f"_kart_{i}.jpg"
                y.rename(g)
                gecici.append(g)
            for i, g in enumerate(gecici, 2):
                g.rename(klasor / f"carousel_{i}.jpg")
            shutil.copyfile(klasor / "post_1080x1350.jpg", klasor / "carousel_1.jpg")
            sonuc["dosyalar"] = [d for d in sonuc["dosyalar"] if not Path(d).name.startswith("carousel_")] + \
                [klasor / f"carousel_{i}.jpg" for i in range(1, len(tutan) + 2)]
        else:
            sonuc["carousel_eksik"] = True
    gunluk(f"Sonuc: {len(sonuc['dosyalar'])} tuval, puanlar {sonuc['puanlar']}"
           + (" (carousel eski sablona dustu)" if sonuc.get("carousel_eksik") else ""))
    _gecmise_yaz({"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "stil": dil["stil"], "palet": dil["palet"],
                  "font": dil["font"], "puanlar": sonuc["puanlar"]})
    return sonuc


# ---------------------------------------------------------------- Reels kapanis karti
def son_kart(urun, gorsel_yollari, taslak, dil, hedef, gunluk=print):
    """Reels'in son sahnesi (1080x1920): logo, harekete gecirme ve adres; icerigin gorsel diliyle, yerlesimi ve
    renkleri tasarimci secer. Olcum + hakemden gecmezse None (sablonun kendi kapanisi kalir)."""
    if not llm.hazir() or not dil:
        return None
    logo = marka.logolar()
    fotolar = [marka.gorsel_hazirla(Path(g)) for g in gorsel_yollari[:2]]
    varliklar = {f"FOTO{i}": tasarim._uri(f) for i, f in enumerate(fotolar, 1)}
    varliklar.setdefault("FOTO1", "")
    varliklar.setdefault("FOTO2", varliklar["FOTO1"])
    varliklar["LOGO_KOYU"] = tasarim._uri(logo.get("koyu")) if logo.get("koyu") else ""
    varliklar["LOGO_ACIK"] = tasarim._uri(logo.get("krem")) if logo.get("krem") else ""
    m = AYAR["marka"]
    tuval = {"ad": "reels_son", "boyut": (1080, 1920),
             "rol": "Final scene (end card) of a 15-second Instagram Reel. The brand closes the video: the LOGO is the "
                    "hero (large, 240-420px wide, perfectly centred or on a deliberate grid line, on a background "
                    "colour that makes it contrast clearly - choose the light or dark logo variant accordingly), then "
                    "the call to action as one bold button-like element, then the website small. Calm, premium, "
                    "uncluttered; a photo may appear only as a subtle background or small accent. Keep top 220px and "
                    "bottom 340px free of text.",
             "metin": {"cta": m.get("cta") or "", "small": m.get("web") or ""}}
    foto_bilgi = ", ".join(f"FOTO{i}" for i in range(1, len(fotolar) + 1)) or "none"
    govde = _temizle(llm.tasarim_sor(SISTEM, _istem(dil, tuval, foto_bilgi, bool(varliklar["LOGO_KOYU"])), sicaklik=0.7))
    en_iyi = None
    for deneme in range(3):
        if not govde or ".tuval" not in govde:
            break
        sayfa_html = _sayfa(govde, tuval, dil, varliklar)
        try:
            olcum = _ciz_ve_olc(sayfa_html, tuval, hedef)
        except Exception as e:
            olcum = {"sert": [f"render error: {str(e)[:80]}"], "yumusak": []}
        sert = olcum.get("sert", [])
        puan, notlar = (None, [])
        logo_yok = varliklar["LOGO_KOYU"] and "{{LOGO" not in govde and "LOGO_" not in govde
        if logo_yok:
            sert = sert + ["the logo is missing - place the logo image as the hero"]
        if not sert:
            puan, notlar = _gorsel_puan(hedef, tuval)
            if en_iyi is None or (puan or 0) > (en_iyi[0] or 0):
                en_iyi = (puan, sayfa_html)
            if puan is None or puan >= 7:
                gunluk(f"Reels kapanis karti hazir (puan {puan})")
                return hedef
        gunluk(f"reels_son: deneme {deneme + 1} - {'; '.join((sert + notlar)[:3])}, puan {puan}")
        if deneme < 2:
            govde = _temizle(llm.tasarim_sor(SISTEM, _istem(dil, tuval, foto_bilgi, bool(varliklar["LOGO_KOYU"]))
                                     + "\n\nYour previous version had these problems, fix ALL of them:\n- "
                                     + "\n- ".join(sert + notlar or ["make the logo clearer"]) + "\n\nPrevious version:\n"
                                     + govde[:6000], sicaklik=0.5)) or govde
    if en_iyi and (en_iyi[0] is None or en_iyi[0] >= 5):
        _ciz_ve_olc(en_iyi[1], tuval, hedef)
        return hedef
    Path(hedef).unlink(missing_ok=True)
    return None
