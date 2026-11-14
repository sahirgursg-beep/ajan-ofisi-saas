"""Modern duzen kutuphanesi: uretken tasarim tutmadiginda devreye giren saglam, guncel duzenler.

Eski 'dinamik.html' sablonlarinin (serif, ince altin cizgiler, gazete gorunumu) yerine gecer. Her duzen o gunun
gorsel dilini (palet + font cifti) kullanir, metin uzunluguna gore boyutlanir ve ayni olcum/hakemden gecer.
Sabit sablon degil, parametrik: palet, font, foto, metin ve tuval boyutu her seferinde degisir.
"""
import html
import random

GUVENLI = 64


def _p(h):
    h = (h or "#000000").lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _yazi(zemin):
    return "#111111" if _p(zemin) > 0.55 else "#FFFFFF"


def _boy(metin, buyuk=124):
    n = len(metin or "")
    return buyuk if n <= 18 else int(buyuk * .88) if n <= 30 else int(buyuk * .76) if n <= 46 else int(buyuk * .64) if n <= 70 else int(buyuk * .54)


E = lambda s: html.escape(str(s or ""))


def _ortak(W, H, dil):
    pl = dil["palet"]
    return (f"<style>.tuval{{--a1:{pl['accent']};--a2:{pl['accent2']};width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{pl['bg']};"
            f"font-family:var(--gf);color:{pl['ink']}}}"
            ".tuval *{box-sizing:border-box}.h{font-family:var(--bf);font-weight:var(--bw,700);letter-spacing:-.035em;"
            "line-height:.98;text-wrap:balance;hyphens:none;margin:0}"
            ".pill{display:inline-flex;align-items:center;gap:14px;border-radius:999px;padding:22px 34px;"
            "font-weight:700;font-size:30px;white-space:nowrap}"
            ".chip{display:inline-block;border-radius:18px;padding:14px 22px;font-weight:800;font-size:44px;white-space:nowrap;"
            "font-family:var(--bf)}.eski{font-size:28px;text-decoration:line-through;opacity:.7;white-space:nowrap}"
            ".logo{height:64px;width:auto;object-fit:contain}.foto{object-fit:cover;display:block}"
            ".ok::after{content:'';display:inline-block;width:14px;height:14px;border-top:4px solid currentColor;"
            "border-right:4px solid currentColor;transform:rotate(45deg);margin-left:4px}")


def _logo(v, koyu_zemin):
    src = v.get("LOGO_ACIK") if koyu_zemin else v.get("LOGO_KOYU")
    return f'<img class="logo" src="{src}" alt="">' if src else ""


def _fiyat(m, renk_zemin, yazi):
    if not m.get("price"):
        return ""
    eski = f'<div class="eski" data-metin>{E(m["old_price"])}</div>' if m.get("old_price") else ""
    return (f'<div style="display:flex;flex-direction:column;gap:6px">{eski}'
            f'<div class="chip" data-metin style="background:{renk_zemin};color:{yazi}">{E(m["price"])}</div></div>')


def _img(v, stil):
    """Fotograf yoksa (yalnizca tipografi) bos kutu yerine palet degradesi."""
    if v.get("FOTO1"):
        return f'<img class="foto" src="{v["FOTO1"]}" style="{stil}">'
    return f'<div style="{stil};background:linear-gradient(135deg,var(--a1,#ddd),var(--a2,#999))"></div>'


def _ana_metin(m):
    return m.get("line") or m.get("headline") or ""


# ------------------------------------------------------------------ duzenler
def tam_foto(W, H, m, dil, v):
    pl, ust, alt = dil["palet"], (220 if H > 1500 else GUVENLI), (360 if H > 1500 else GUVENLI)
    b = _boy(_ana_metin(m), 128)
    return (_ortak(W, H, dil) + f"""
.scrim{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 34%,rgba(0,0,0,.78) 100%)}}
.alt{{position:absolute;left:{GUVENLI}px;right:{GUVENLI}px;bottom:{alt}px;display:flex;flex-direction:column;gap:30px;color:#fff}}
.satir{{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}}
</style><div class="tuval">{_img(v, "position:absolute;inset:0;width:100%;height:100%")}
<div class="scrim"></div><div style="position:absolute;left:{GUVENLI}px;top:{ust}px">{_logo(v, True)}</div>
<div class="alt"><h1 class="h" data-metin style="font-size:{b}px;color:#fff">{E(_ana_metin(m))}</h1>
<div class="satir">{_fiyat(m, pl['accent'], _yazi(pl['accent']))}
{f'<div class="pill" data-metin style="background:#fff;color:#111">{E(m["cta"])}<span class="ok"></span></div>' if m.get('cta') else ''}</div></div></div>""")


def renk_poster(W, H, m, dil, v):
    pl = dil["palet"]
    zemin, yazi = pl["accent"], _yazi(pl["accent"])
    ust, alt = (220 if H > 1500 else GUVENLI), (360 if H > 1500 else GUVENLI)
    b = _boy(_ana_metin(m), 136)
    foto_h = int(H * (0.5 if H > 1500 else 0.46))
    return (_ortak(W, H, dil) + f"""
.tuval{{background:{zemin};color:{yazi}}}
.cer{{position:absolute;right:{GUVENLI}px;bottom:{alt}px;width:{int(W * .62)}px;height:{foto_h}px;border-radius:44px;overflow:hidden;
transform:rotate(-2.5deg);box-shadow:0 30px 60px rgba(0,0,0,.28)}}
</style><div class="tuval"><div style="position:absolute;left:{GUVENLI}px;right:{GUVENLI}px;top:{ust}px;display:flex;justify-content:space-between;align-items:flex-start;gap:30px">
<h1 class="h" data-metin style="font-size:{b}px;max-width:{W - 2 * GUVENLI - 40}px">{E(_ana_metin(m))}</h1></div>
<div style="position:absolute;right:{GUVENLI}px;top:{ust}px">{_logo(v, _p(zemin) < .55)}</div>
<div class="cer">{_img(v, "width:100%;height:100%")}</div>
<div style="position:absolute;left:{GUVENLI}px;bottom:{alt}px;display:flex;flex-direction:column;gap:22px;align-items:flex-start;max-width:{int(W * .3)}px">
{_fiyat(m, pl['ink'], _yazi(pl['ink']))}
{f'<div class="pill" data-metin style="background:{pl["ink"]};color:{_yazi(pl["ink"])};font-size:26px;padding:18px 26px">{E(m["cta"])}</div>' if m.get('cta') else ''}</div></div>""")


def kart_alt(W, H, m, dil, v):
    pl = dil["palet"]
    alt = 360 if H > 1500 else GUVENLI
    b = _boy(_ana_metin(m), 96)
    return (_ortak(W, H, dil) + f"""
.kart{{position:absolute;left:{GUVENLI - 16}px;right:{GUVENLI - 16}px;bottom:{alt - 16}px;background:#fff;color:#111;border-radius:44px;
padding:48px;display:flex;flex-direction:column;gap:28px;box-shadow:0 24px 70px rgba(0,0,0,.25)}}
</style><div class="tuval">{_img(v, "position:absolute;inset:0;width:100%;height:100%")}
<div style="position:absolute;left:{GUVENLI}px;top:{220 if H > 1500 else GUVENLI}px">{_logo(v, True)}</div>
<div class="kart"><h1 class="h" data-metin style="font-size:{b}px">{E(_ana_metin(m))}</h1>
<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap">{_fiyat(m, pl['accent'], _yazi(pl['accent']))}
{f'<div class="pill" data-metin style="background:{pl["ink"] if _p(pl["ink"]) < .5 else "#111"};color:#fff">{E(m["cta"])}<span class="ok"></span></div>' if m.get('cta') else ''}</div></div></div>""")


def dikey_bolunmus(W, H, m, dil, v):
    pl = dil["palet"]
    panel = pl["ink"] if _p(pl["ink"]) < .5 else pl["accent"]
    yazi = _yazi(panel)
    pw = int(W * .46)
    ust, alt = (220 if H > 1500 else GUVENLI), (360 if H > 1500 else GUVENLI)
    b = min(_boy(_ana_metin(m), 104), 96)
    return (_ortak(W, H, dil) + f"""
.panel{{position:absolute;left:0;top:0;bottom:0;width:{pw}px;background:{panel};color:{yazi};padding:{ust}px 48px {alt}px {GUVENLI}px;
display:flex;flex-direction:column;justify-content:space-between;gap:30px}}
</style><div class="tuval">{_img(v, "position:absolute;top:0;right:0;bottom:0;width:{W - pw}px;height:100%")}
<div class="panel"><div>{_logo(v, _p(panel) < .55)}</div>
<h1 class="h" data-metin style="font-size:{b}px">{E(_ana_metin(m))}</h1>
<div style="display:flex;flex-direction:column;gap:22px;align-items:flex-start">{_fiyat(m, pl['accent2'] if pl['accent2'] != panel else pl['accent'], _yazi(pl['accent2']))}
{f'<div class="pill" data-metin style="background:{yazi};color:{panel};font-size:26px;padding:18px 26px">{E(m["cta"])}</div>' if m.get('cta') else ''}</div></div></div>""")


def ust_tipografi(W, H, m, dil, v):
    pl = dil["palet"]
    ust, alt = (220 if H > 1500 else GUVENLI), (360 if H > 1500 else GUVENLI)
    b = _boy(_ana_metin(m), 132)
    return (_ortak(W, H, dil) + f"""
.cer{{position:absolute;left:{GUVENLI}px;right:{GUVENLI}px;bottom:{alt}px;top:{int(H * .42)}px;border-radius:48px;overflow:hidden}}
</style><div class="tuval"><div style="position:absolute;left:{GUVENLI}px;right:{GUVENLI}px;top:{ust}px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px">{_logo(v, _p(pl['bg']) < .55)}
{f'<div class="pill" data-metin style="background:{pl["accent"]};color:{_yazi(pl["accent"])};font-size:26px;padding:16px 26px">{E(m["price"])}</div>' if m.get('price') else ''}</div>
<h1 class="h" data-metin style="font-size:{b}px;color:{pl['ink']}">{E(_ana_metin(m))}</h1></div>
<div class="cer">{_img(v, "width:100%;height:100%")}</div>
{f'<div class="pill" data-metin style="position:absolute;left:{GUVENLI + 32}px;bottom:{alt + 32}px;background:#fff;color:#111">{E(m["cta"])}<span class="ok"></span></div>' if m.get('cta') else ''}</div>""")


def liste_karti(W, H, m, dil, v):
    """Carousel son karti: maddeler + fiyat + CTA (kaydedilecek ozet)."""
    pl = dil["palet"]
    maddeler = "".join(f'<div style="display:flex;gap:26px;align-items:center;background:#fff;color:#111;border-radius:30px;padding:30px 34px">'
                       f'<span style="flex:none;width:56px;height:56px;border-radius:50%;background:{pl["accent"]};color:{_yazi(pl["accent"])};'
                       f'display:grid;place-items:center;font-weight:800;font-size:28px">{i}</span>'
                       f'<span data-metin style="font-size:40px;font-weight:600;line-height:1.15">{E(x)}</span></div>'
                       for i, x in enumerate((m.get("points") or [])[:3], 1))
    return (_ortak(W, H, dil) + f"""</style><div class="tuval" style="background:{pl['ink'] if _p(pl['ink']) < .5 else '#151515'};color:#fff">
<div style="position:absolute;left:{GUVENLI}px;right:{GUVENLI}px;top:{GUVENLI}px;bottom:{GUVENLI}px;display:flex;flex-direction:column;gap:30px;justify-content:center">
<div>{_logo(v, True)}</div>{maddeler}
<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap;margin-top:10px">{_fiyat(m, pl['accent'], _yazi(pl['accent']))}
{f'<div class="pill" data-metin style="background:{pl["accent"]};color:{_yazi(pl["accent"])}">{E(m["cta"])}<span class="ok"></span></div>' if m.get('cta') else ''}</div></div></div>""")


DUZENLER = {"tam_foto": tam_foto, "renk_poster": renk_poster, "kart_alt": kart_alt,
            "dikey_bolunmus": dikey_bolunmus, "ust_tipografi": ust_tipografi}


def adaylar(tuval, adet=2, haric=()):
    """Bu tuval icin denenecek duzen adlari (son kart icin liste)."""
    if "points" in tuval["metin"]:
        return ["liste_karti"]
    havuz = [d for d in DUZENLER if d not in haric]
    if tuval["boyut"][1] > 1500:                  # story: yan yana bolunmus duzen dar kalir
        havuz = [d for d in havuz if d != "dikey_bolunmus"] or havuz
    return random.sample(havuz, min(adet, len(havuz)))


def ciz(ad, tuval, dil, varliklar):
    W, H = tuval["boyut"]
    f = liste_karti if ad == "liste_karti" else DUZENLER[ad]
    return f(W, H, tuval["metin"], dil, varliklar)
