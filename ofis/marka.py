"""Marka varliklari: musteri logosundan seffaf logolar, fontlarin indirilmesi."""
import hashlib
import re
from pathlib import Path

from PIL import Image, ImageFilter

from .ayarlar import AYAR, KOK, PAYLASIK, VERI

MARKA_KLASOR = VERI / "marka"
FONT_KLASOR = PAYLASIK / "fontlar"
GOOGLE_FONTS = ("https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500"
                "&family=Montserrat:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,700;1,500"
                "&family=Inter:wght@400;600;700&family=Bebas+Neue&family=Marcellus&family=Jost:wght@400;600"
                "&family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@400;600;700&display=swap")


def _hex(h, varsayilan):
    try:
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    except Exception:
        return varsayilan


def _alfa_genel(im):
    """Seffaf olmayan logo: kose rengini zemin sayar, zemine uzakligi alfa yapar (beyaz/duz zeminli logolar)."""
    from PIL import ImageChops
    im = im.convert("RGB")
    w, h = im.size
    koseler = [im.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    zemin = tuple(sorted(c[i] for c in koseler)[1] for i in range(3))
    fark = ImageChops.difference(im, Image.new("RGB", im.size, zemin)).convert("L")
    return fark.point(lambda v: 0 if v < 18 else min(255, int((v - 18) * 4)))


def _alfa_altin_monogram(im, cerceve):
    """Koyu deri zemin uzerinde altin monogram (ilk musteride kullanilan logo turu)."""
    from PIL import ImageChops
    r, g, b = im.split()
    lum = im.convert("L")
    kirp = lambda x: max(0.0, min(1.0, x))
    a1 = lum.point(lambda v: int(kirp((v - 80) / 50) * 255))
    a2 = ImageChops.subtract(r, b).point(lambda v: int(kirp((v - 25) / 35) * 255))
    parlak = lum.point(lambda v: int(kirp((v - 165) / 40) * 255))
    A = ImageChops.lighter(ImageChops.multiply(a1, a2), parlak)
    return A.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))


def logolar():
    """Musterinin logosundan uc renkte seffaf PNG uretir (altin = logonun kendi renkleri, krem/koyu = tek renk).
    profil.json -> marka.logo (musteri klasorune gore yol), marka.logo_isleme:
      "seffaf"        : PNG zaten seffaf (onerilen)          "duz_zemin": duz renkli zemini temizle
      "altin_monogram": koyu zemin + altin logo               (bos)      : otomatik (alfa varsa seffaf, yoksa duz_zemin)
    Logo yoksa None doner; sablonlar logosuz cizer."""
    from .ayarlar import dosya_yolu
    MARKA_KLASOR.mkdir(parents=True, exist_ok=True)
    m = AYAR["marka"]
    cerceve = m.get("logo_cerceve", True)
    e = "_c" if cerceve else ""
    altin, krem, koyu = (MARKA_KLASOR / f"logo_altin{e}.png", MARKA_KLASOR / f"logo_krem{e}.png",
                         MARKA_KLASOR / f"logo_koyu{e}.png")
    kaynak = dosya_yolu(m.get("logo"))
    if not kaynak or not kaynak.exists():
        return {"altin": None, "krem": None, "koyu": None}
    if (altin.exists() and krem.exists() and koyu.exists()
            and altin.stat().st_mtime >= kaynak.stat().st_mtime):
        return {"altin": altin, "krem": krem, "koyu": koyu}
    ham = Image.open(kaynak)
    isleme = m.get("logo_isleme") or ("seffaf" if ham.mode in ("RGBA", "LA", "P") and "A" in ham.convert("RGBA").getbands()
                                      and ham.convert("RGBA").getchannel("A").getextrema()[0] < 250 else "duz_zemin")
    im = ham.convert("RGB")
    if isleme == "seffaf":
        A = ham.convert("RGBA").getchannel("A")
    elif isleme == "altin_monogram":
        A = _alfa_altin_monogram(im, cerceve)
    else:
        A = _alfa_genel(im)
    rgba = im.copy()
    rgba.putalpha(A)
    kutu = A.point(lambda v: 255 if v > 90 else 0).getbbox() or (0, 0, *im.size)
    mono = rgba.crop(kutu)
    if isleme == "altin_monogram" and not cerceve:     # cercevesiz: ortadaki monogram + yazi
        s = im.width / 900
        mono = rgba.crop((int(135 * s), int(265 * s), int(770 * s), int(695 * s)))
        mono = mono.crop(mono.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox() or (0, 0, *mono.size))
    mono.save(altin)
    krem_img = Image.new("RGBA", mono.size, _hex(m.get("renk_acik"), (244, 239, 230, 255)))
    krem_img.putalpha(mono.getchannel("A"))
    krem_img.save(krem)
    koyu_img = Image.new("RGBA", mono.size, _hex(m.get("renk_koyu"), (28, 22, 18, 255)))
    koyu_img.putalpha(mono.getchannel("A"))
    koyu_img.save(koyu)
    return {"altin": altin, "krem": krem, "koyu": koyu}


YEDEK_VURGULAR = ["#B5562F", "#1F6F5C", "#155E75", "#C9962B", "#7A2335", "#3F5A3A"]


def vurgu_rengi(yol, tohum=0):
    """Fotograftaki en canli baskin rengi bulur -> (vurgu, vurgu_koyu, yazi_rengi)."""
    import colorsys
    im = Image.open(yol).convert("RGB")
    im.thumbnail((200, 200))
    q = im.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    sayilar = sorted(q.getcolors(), reverse=True)
    toplam = sum(c for c, _ in sayilar)
    en_iyi, puan = None, 0
    for c, i in sayilar:
        r, g, b = pal[i * 3:i * 3 + 3]
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if s < 0.35 or not 0.18 < l < 0.8:
            continue  # gri/beyaz/siyah tonlar vurgu olamaz
        p = s * (c / toplam) ** 0.5
        if p > puan:
            en_iyi, puan = (h, l, s), p
    if en_iyi is None or puan < 0.12:
        # fotografta belirgin renk yok -> markaya uygun toprak tonlarindan biri (oldugu gibi)
        hexr = YEDEK_VURGULAR[tohum % len(YEDEK_VURGULAR)]
        r, g, b = (int(hexr[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
    else:
        h, l, s = en_iyi
        s = min(max(s, 0.45), 0.68)   # canli ama "neon" degil
        l = min(max(l, 0.36), 0.5)
    hx = lambda rgb: "#" + "".join(f"{int(v * 255):02X}" for v in rgb)
    vurgu = colorsys.hls_to_rgb(h, l, s)
    koyu = colorsys.hls_to_rgb(h, l * 0.55, s)
    parlaklik = 0.299 * vurgu[0] + 0.587 * vurgu[1] + 0.114 * vurgu[2]
    yazi = "#1C1612" if parlaklik > 0.5 else "#FFFFFF"
    return hx(vurgu), hx(koyu), yazi


def _aile_css(aile, spec, requests):
    """Tek ailenin CSS'i + woff2 dosyalari, aile basina onbellek: kutuphaneye yeni font eklenince yalnizca o indirilir.
    CJK dilimleri (/* [12] */ gibi, yuzlerce dosya) atlanir."""
    anahtar = hashlib.sha1(spec.encode()).hexdigest()[:10]
    yol = FONT_KLASOR / "aileler" / f"{anahtar}.css"
    if yol.exists():
        return yol.read_text(encoding="utf-8")
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
    r = requests.get("https://fonts.googleapis.com/css2?family=" + spec + "&display=swap", headers=ua, timeout=20)
    r.raise_for_status()
    bloklar = re.findall(r"(/\*[^*]*\*/\s*@font-face\s*\{[^}]*\})", r.text) or [r.text]
    bloklar = [b for b in bloklar if not re.match(r"/\*\s*\[\d+\]", b)]
    css = "\n".join(bloklar)
    yol.parent.mkdir(parents=True, exist_ok=True)
    for i, url in enumerate(dict.fromkeys(re.findall(r"url\((https://[^)]+\.woff2)\)", css))):
        ad = f"{anahtar}_{i}.woff2"
        (yol.parent / ad).write_bytes(requests.get(url, timeout=30).content)
        css = css.replace(url, "aileler/" + ad)
    yol.write_text(css, encoding="utf-8")
    return css


def fontlar_css():
    """Google Fonts'u bir kez indirip yerelde saklar (sonra internetsiz calisir). Her aile ayri istenir ve ayri
    saklanir: biri basarisiz olursa digerleri yine gelir. Hicbiri gelmezse None; sablonlar yedek fontlara duser."""
    from . import fontlar
    css_yolu = FONT_KLASOR / f"fonts_{fontlar.imza()}.css"
    if css_yolu.exists():
        return css_yolu
    try:
        import requests
    except ImportError:
        return None
    FONT_KLASOR.mkdir(parents=True, exist_ok=True)
    parcalar = []
    for aile in fontlar.aileler():
        try:
            parcalar.append(_aile_css(aile, fontlar.GOOGLE[aile], requests))
        except Exception as e:
            print(f"  ! Font indirilemedi: {aile} ({type(e).__name__})")
    if not parcalar:
        eski = sorted(FONT_KLASOR.glob("fonts_*.css"))
        return eski[-1] if eski else None
    css_yolu.write_text("\n".join(parcalar), encoding="utf-8")
    return css_yolu


def srgb_yap(im):
    """Fotograf baska bir renk profiliyle (Adobe RGB, Display P3...) kaydedildiyse sRGB'ye cevirir.
    Profil yok sayilirsa urun renkleri soluk ya da kaymis gorunur."""
    icc = im.info.get("icc_profile")
    if not icc:
        return im
    try:
        import io
        from PIL import ImageCms
        kaynak = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        if "srgb" in (ImageCms.getProfileDescription(kaynak) or "").lower():
            return im
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.mode else "RGB")
        return ImageCms.profileToProfile(im, kaynak, ImageCms.createProfile("sRGB"),
                                         renderingIntent=0, outputMode=im.mode)
    except Exception:
        return im


def gorsel_hazirla(yol: Path, max_kenar=2800) -> Path:
    """Dev urun fotograflarini (6000px'e kadar) sablon icin makul boyuta indirir."""
    if yol.stem.endswith(("_srgb", "_dikey")):   # zaten hazirlanmis (AI ciktisi dahil) -> oldugu gibi kullan
        return yol
    hedef = yol.with_name(yol.stem + f"_{max_kenar}_srgb.jpg")
    if not hedef.exists():
        from PIL import ImageOps
        im = srgb_yap(ImageOps.exif_transpose(Image.open(yol)))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            zemin = Image.new("RGB", im.size, "white")
            zemin.paste(im, mask=im.getchannel("A"))
            im = zemin
        im = im.convert("RGB")
        im.thumbnail((max_kenar, max_kenar), Image.LANCZOS)
        im.save(hedef, quality=94, subsampling=0)  # 4:4:4 - kirmizi/bordo kenarlarda renk tasmasi olmasin
    return hedef
