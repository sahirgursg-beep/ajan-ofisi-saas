"""Tasarimci ve Video Editoru'nun kullandigi cizim araclari (Pillow + FFmpeg)."""
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .ayarlar import AYAR, KOK, MUZIK

M = AYAR["marka"]
KOYU, ALTIN, ACIK = M["renk_koyu"], M["renk_altin"], M["renk_acik"]

_FONTLAR = {
    "serif": ["georgiab.ttf", "C:/Windows/Fonts/georgiab.ttf", "DejaVuSerif-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
    "kalin": ["segoeuib.ttf", "C:/Windows/Fonts/segoeuib.ttf", "arialbd.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "normal": ["segoeui.ttf", "C:/Windows/Fonts/segoeui.ttf", "arial.ttf",
               "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}
_onbellek = {}


def font(tur, boyut):
    anahtar = (tur, boyut)
    if anahtar not in _onbellek:
        for f in _FONTLAR[tur]:
            try:
                _onbellek[anahtar] = ImageFont.truetype(f, boyut)
                break
            except OSError:
                continue
        else:
            _onbellek[anahtar] = ImageFont.load_default(boyut)
    return _onbellek[anahtar]


def sar(ciz, metin, f, genislik, max_satir=3):
    kelimeler, satirlar, satir = metin.split(), [], ""
    for k in kelimeler:
        dene = (satir + " " + k).strip()
        if ciz.textlength(dene, font=f) <= genislik:
            satir = dene
        else:
            if satir:
                satirlar.append(satir)
            satir = k
    if satir:
        satirlar.append(satir)
    if len(satirlar) > max_satir:
        satirlar = satirlar[:max_satir]
        satirlar[-1] = satirlar[-1].rstrip(".,") + "…"
    return satirlar


def ortala_yaz(ciz, y, satirlar, f, renk, W, aralik=1.2):
    for s in satirlar:
        w = ciz.textlength(s, font=f)
        ciz.text(((W - w) / 2, y), s, font=f, fill=renk)
        y += int(f.size * aralik)
    return y


def fiyat_rozeti(ciz, merkez_x, y, metin, boyut=64):
    f = font("kalin", boyut)
    w = ciz.textlength(metin, font=f)
    px, py = 44, 22
    x0 = merkez_x - w / 2 - px
    ciz.rounded_rectangle([x0, y, x0 + w + 2 * px, y + boyut + 2 * py], radius=(boyut + 2 * py) // 2, fill=KOYU)
    ciz.text((x0 + px, y + py - boyut * 0.12), metin, font=f, fill=ALTIN)
    return y + boyut + 2 * py


def sigdir(img, kutu_w, kutu_h):
    img = img.copy()
    img.thumbnail((kutu_w, kutu_h), Image.LANCZOS)
    return img


def kapla(img, W, H):
    return ImageOps.fit(img, (W, H), Image.LANCZOS)


def ac(yol):
    from .marka import srgb_yap
    img = srgb_yap(ImageOps.exif_transpose(Image.open(yol)))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        zemin = Image.new("RGB", img.size, "white")
        zemin.paste(img, mask=img.split()[-1])
        return zemin
    return img.convert("RGB")


def _golge_kart(tuval, kart, x, y, r=28):
    W, H = kart.size
    golge = Image.new("RGBA", (W + 120, H + 120), (0, 0, 0, 0))
    ImageDraw.Draw(golge).rounded_rectangle([60, 70, W + 60, H + 70], radius=r, fill=(0, 0, 0, 70))
    golge = golge.filter(ImageFilter.GaussianBlur(28))
    tuval.paste(golge, (x - 60, y - 60), golge)
    maske = Image.new("L", kart.size, 0)
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, W, H], radius=r, fill=255)
    tuval.paste(kart, (x, y), maske)


def urun_karti(tuval, img, x, y, w, h):
    kart = Image.new("RGB", (w, h), "white")
    ic = sigdir(img, w - 60, h - 60)
    kart.paste(ic, ((w - ic.width) // 2, (h - ic.height) // 2))
    _golge_kart(tuval, kart, x, y)


# ---------------- POST (1080x1350) ----------------
def post_ciz(urun_img, ad, kategori, fiyat_metni, baslik, hedef: Path):
    W, H = 1080, 1350
    t = Image.new("RGB", (W, H), ACIK)
    c = ImageDraw.Draw(t)
    # ust: marka
    f = font("kalin", 30)
    ortala_yaz(c, 48, [" ".join(M["ad"])], f, KOYU, W)
    c.line([(W / 2 - 60, 96), (W / 2 + 60, 96)], fill=ALTIN, width=3)
    # baslik (metin yazarindan)
    y = ortala_yaz(c, 120, sar(c, baslik, font("normal", 38), 920, 2), font("normal", 38), KOYU, W)
    # urun karti
    urun_karti(t, urun_img, 70, y + 24, 940, 720)
    y = y + 24 + 720 + 36
    # kategori + ad
    if kategori:
        y = ortala_yaz(c, y, [kategori.upper()], font("kalin", 26), ALTIN, W)
    y = ortala_yaz(c, y + 4, sar(c, ad, font("serif", 52), 960, 2), font("serif", 52), KOYU, W, 1.15)
    # fiyat
    if fiyat_metni:
        fiyat_rozeti(c, W / 2, y + 14, fiyat_metni, 54)
    # alt bant
    c.rectangle([0, H - 70, W, H], fill=KOYU)
    ortala_yaz(c, H - 56, [f"{M['cta']}  •  {M['web']}"], font("normal", 28), ACIK, W)
    t.save(hedef, quality=95)
    return hedef


# ---------------- STORY (1080x1920) ----------------
def story_ciz(urun_img, ad, fiyat_metni, kanca, hedef: Path):
    W, H = 1080, 1920
    arka = kapla(urun_img, W, H).filter(ImageFilter.GaussianBlur(40))
    t = Image.blend(arka, Image.new("RGB", (W, H), KOYU), 0.55)
    c = ImageDraw.Draw(t)
    ortala_yaz(c, 120, [" ".join(M["ad"])], font("kalin", 34), ALTIN, W)
    y = ortala_yaz(c, 230, sar(c, kanca, font("serif", 76), 940, 3), font("serif", 76), ACIK, W, 1.15)
    urun_karti(t, urun_img, 80, max(y + 50, 560), 920, 860)
    y = max(y + 50, 560) + 860 + 60
    y = ortala_yaz(c, y, sar(c, ad, font("serif", 54), 960, 2), font("serif", 54), ACIK, W, 1.15)
    if fiyat_metni:
        y = fiyat_rozeti(c, W / 2, y + 20, fiyat_metni, 62)
    ortala_yaz(c, H - 150, [M["cta"]], font("normal", 36), ACIK, W)
    t.save(hedef, quality=95)
    return hedef


# ---------------- REELS (1080x1920, MP4) ----------------
def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _kolay(t):
    return t * t * (3 - 2 * t)


def reels_yap(gorseller, ad, fiyat_metni, kanca, hedef: Path, fps=30, eski_fiyat_metni=""):
    W, H = 1080, 1920
    toplam = AYAR.get("video_sure_sn", 15)
    gorseller = gorseller[:3]
    n = len(gorseller)
    s_kanca, s_fiyat, s_cta = 2.5, 3.0, 2.5
    s_gorsel = max(2.0, (toplam - s_kanca - s_fiyat - s_cta) / n)

    # hazir katmanlar
    karanlik = Image.new("RGB", (W, H), KOYU)
    from . import marka
    _l = marka.logolar().get("altin")
    logo_img = Image.open(_l).convert("RGBA") if _l else None

    def logo_bas(k, y, yukseklik):
        if logo_img is None:
            ortala_yaz(ImageDraw.Draw(k), y, [" ".join(M["ad"])], font("kalin", 34), ALTIN, W)
            return
        l = logo_img.resize((int(logo_img.width * yukseklik / logo_img.height), yukseklik), Image.LANCZOS)
        k.paste(l, ((W - l.width) // 2, y), l)

    def beyaz_zemin(g):
        k = g.resize((40, 40))
        kenar = [k.getpixel((x, y)) for x in range(40) for y in (0, 39)] + [k.getpixel((x, y)) for y in range(40) for x in (0, 39)]
        return sum(sum(p) / 3 > 235 for p in kenar) > len(kenar) * 0.7

    def kompozit(g):
        if not beyaz_zemin(g):
            # Oda fotografi: dikey kareyi doldur, kare boyunca yavasca yana kaydir
            olcek = (H * 1.06) / g.height
            return ("pan", g.resize((max(int(g.width * olcek), W + 2), int(H * 1.06)), Image.LANCZOS))
        # Urun asla kirpilmasin: bulanik arka plan + ortada tam urun
        BW, BH = int(W * 1.12), int(H * 1.12)
        arka = Image.blend(kapla(g, BW, BH).filter(ImageFilter.GaussianBlur(45)),
                           Image.new("RGB", (BW, BH), KOYU), 0.35)
        on = sigdir(g, int(BW * 0.98), int(BH * 0.62))
        arka.paste(on, ((BW - on.width) // 2, int(BH * 0.45 - on.height / 2)))
        return ("zoom", arka)

    buyuk = [kompozit(g) for g in gorseller]
    alt_gradyan = Image.new("L", (1, H))
    for yy in range(H):
        alt = max(0, (yy - H * 0.62) / (H * 0.38)) * 230
        ust = max(0, (H * 0.14 - yy) / (H * 0.14)) * 170
        alt_gradyan.putpixel((0, yy), int(max(alt, ust)))
    alt_gradyan = alt_gradyan.resize((W, H))

    def kanca_kare(t):
        k = karanlik.copy()
        c = ImageDraw.Draw(k)
        a = _kolay(min(1, t / 0.6))
        renk = tuple(int(int(KOYU[i:i + 2], 16) * (1 - a) + int(ACIK[i:i + 2], 16) * a) for i in (1, 3, 5))
        f = font("serif", 92)
        satirlar = sar(c, kanca, f, 940, 4)
        y = H / 2 - len(satirlar) * f.size * 0.6
        y = ortala_yaz(c, y - 30 * (1 - a), satirlar, f, renk, W, 1.15)
        c.line([(W / 2 - 90 * a, y + 30), (W / 2 + 90 * a, y + 30)], fill=ALTIN, width=5)
        logo_bas(k, 130, 110)
        return k

    def gorsel_kare(i, t):
        tur, g = buyuk[i]
        if tur == "pan":
            fazla = g.width - W
            orta = fazla / 2
            menzil = min(fazla / 2, W * 0.35)
            yon = 1 if i % 2 == 0 else -1
            ox = int(orta + yon * menzil * (_kolay(t) * 2 - 1))
            oy = (g.height - H) // 2
            k = g.crop((ox, oy, ox + W, oy + H))
        else:
            z = 1.0 + 0.08 * _kolay(t)  # yavas zoom
            cw, ch = int(g.width / z), int(g.height / z)
            ox, oy = (g.width - cw) // 2, (g.height - ch) // 2
            k = g.crop((ox, oy, ox + cw, oy + ch)).resize((W, H), Image.BILINEAR)
        k.paste(karanlik, (0, 0), alt_gradyan)
        c = ImageDraw.Draw(k)
        ortala_yaz(c, H - 300, sar(c, ad, font("serif", 64), 960, 2), font("serif", 64), ACIK, W, 1.15)
        logo_bas(k, 120, 90)
        return k

    fiyat_zemin = Image.blend(kapla(gorseller[0], W, H).filter(ImageFilter.GaussianBlur(40)), karanlik, 0.6)

    def fiyat_kare(t):
        k = fiyat_zemin.copy()
        urun_karti(k, gorseller[0], 90, 360, 900, 820)
        c = ImageDraw.Draw(k)
        y = ortala_yaz(c, 1240, sar(c, ad, font("serif", 58), 960, 2), font("serif", 58), ACIK, W, 1.15)
        if eski_fiyat_metni:
            f = font("normal", 40)
            w = c.textlength(eski_fiyat_metni, font=f)
            c.text(((W - w) / 2, y + 20), eski_fiyat_metni, font=f, fill=(190, 180, 170))
            c.line([((W - w) / 2 - 6, y + 46), ((W + w) / 2 + 6, y + 38)], fill=(190, 180, 170), width=3)
            y += 70
        if fiyat_metni:
            olcek = 0.8 + 0.2 * _kolay(min(1, t / 0.5))
            fiyat_rozeti(c, W / 2, y + 30, fiyat_metni, int(70 * olcek))
        return k

    def cta_kare(t):
        k = karanlik.copy()
        c = ImageDraw.Draw(k)
        logo_bas(k, 520, 230)
        y = 800
        c.line([(W / 2 - 120, y + 20), (W / 2 + 120, y + 20)], fill=ALTIN, width=4)
        y = ortala_yaz(c, y + 70, sar(c, M["cta"], font("serif", 64), 900, 3), font("serif", 64), ACIK, W, 1.2)
        ortala_yaz(c, y + 40, [M["web"]], font("normal", 40), ACIK, W)
        return k

    bolumler = [(s_kanca, kanca_kare)]
    bolumler += [(s_gorsel, (lambda i: lambda t: gorsel_kare(i, t))(i)) for i in range(n)]
    bolumler += [(s_fiyat, fiyat_kare), (s_cta, cta_kare)]

    komut = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    muzikler = list((MUZIK).glob("*.mp3")) if (MUZIK).exists() else []
    sure = sum(b[0] for b in bolumler)
    if muzikler:
        komut += ["-i", str(random.choice(muzikler)), "-af", f"afade=t=out:st={sure - 1.5}:d=1.5",
                  "-c:a", "aac", "-b:a", "160k", "-shortest"]
    komut += ["-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264",
              "-preset", "veryfast", "-crf", "20", "-colorspace", "bt709", "-color_primaries", "bt709",
              "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", str(hedef)]
    p = subprocess.Popen(komut, stdin=subprocess.PIPE)
    for s, fn in bolumler:
        kare_sayisi = int(s * fps)
        for f in range(kare_sayisi):
            t = f / max(1, kare_sayisi - 1)
            k = fn(t)
            gecis = f / (0.3 * fps)
            if gecis < 1:  # bolum basinda siyahtan acilis
                k = Image.blend(Image.new("RGB", (W, H), "black"), k, gecis)
            p.stdin.write(k.tobytes())
    p.stdin.close()
    p.wait()
    if p.returncode != 0:
        raise RuntimeError("FFmpeg video olusturamadi")
    return hedef
