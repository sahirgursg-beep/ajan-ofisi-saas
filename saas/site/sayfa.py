"""Tanitim sitesi: sunucuda uretilen, hizli ve arama motoru dostu sayfalar (framework yok).

Adresler:  /<dil>/  /<dil>/pricing  /<dil>/faq   /en/industries  /en/industries/<sektor>
           /legal/privacy  /legal/terms  /legal/data-deletion   /sitemap.xml  /robots.txt
SEO: her sayfada title/description, canonical, hreflang (+x-default), Open Graph, JSON-LD (Organization, WebSite,
SoftwareApplication + fiyat, FAQPage, BreadcrumbList).
"""
import html
import json
import re
from urllib.parse import quote

from ofis import paketler, sektor_bilgi, sektor_isleri

from . import metin
from .metin import DILLER, t

E = html.escape
SAYFALAR = ("", "pricing", "faq")       # her dilde var olan sayfalar


def slug(anahtar):
    ad = sektor_bilgi.SEKTORLER[anahtar]["ad"].lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", ad).strip("-")


SLUG = {slug(k): k for k in sektor_bilgi.SEKTORLER if k != "genel"}


def _yol(dil, sayfa=""):
    return f"/{dil}/" + (sayfa + "" if sayfa else "")


def _kok(site, dil, sayfa=""):
    return site.rstrip("/") + _yol(dil, sayfa)


def _jsonld(*nesneler):
    return "".join(f'<script type="application/ld+json">{json.dumps(n, ensure_ascii=False)}</script>' for n in nesneler)


def _organizasyon(site):
    return {"@context": "https://schema.org", "@type": "Organization", "name": "FeedZync", "url": site,
            "logo": site.rstrip("/") + "/panel/varliklar/feedzync-ikon.png"}


def _uygulama(site, dil):
    return {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "FeedZync",
            "applicationCategory": "BusinessApplication", "operatingSystem": "Web", "inLanguage": dil,
            "description": t(dil, "aciklama"), "url": _kok(site, dil),
            "offers": {"@type": "AggregateOffer", "priceCurrency": "USD", "lowPrice": "10", "highPrice": "60",
                       "offerCount": "3"}}


def _sss_ld(dil):
    return {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": dil,
            "mainEntity": [{"@type": "Question", "name": s, "acceptedAnswer": {"@type": "Answer", "text": c}}
                           for s, c in t(dil, "sss")]}


def iskelet(site, uygulama, dil, sayfa, baslik, aciklama, govde, diller=None, ld="", canonical=None):
    """Ortak sayfa iskeleti. diller: bu sayfanin var oldugu diller (hreflang icin)."""
    diller = diller or list(DILLER)
    canonical = canonical or (site.rstrip("/") + (_yol(dil, sayfa) if sayfa is not None else "/"))
    cok = sayfa is not None and len(diller) > 1
    alternatif = "".join(f'<link rel="alternate" hreflang="{d}" href="{_kok(site, d, sayfa)}">' for d in diller) if cok else ""
    alternatif += f'<link rel="alternate" hreflang="x-default" href="{_kok(site, "en", sayfa)}">' if cok else ""
    yon = (DILLER.get(dil) or metin.EN)["yon"]
    nav = (f'<a href="{_yol(dil)}#nasil">{E(t(dil, "nav_nasil"))}</a><a href="{_yol(dil, "pricing")}">{E(t(dil, "nav_fiyat"))}</a>'
           f'<a href="/en/industries">{E(t(dil, "nav_sektor"))}</a><a href="{_yol(dil, "faq")}">{E(t(dil, "nav_sss"))}</a>')
    dil_sec = "".join(f'<option value="{d}" {"selected" if d == dil else ""}>{E(DILLER[d]["ad"])}</option>' for d in DILLER)
    return f"""<!doctype html>
<html lang="{dil}" dir="{yon}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(baslik)}</title><meta name="description" content="{E(aciklama)}">
<link rel="canonical" href="{E(canonical)}">{alternatif}
<meta property="og:type" content="website"><meta property="og:site_name" content="FeedZync">
<meta property="og:title" content="{E(baslik)}"><meta property="og:description" content="{E(aciklama)}">
<meta property="og:url" content="{E(canonical)}"><meta property="og:image" content="{site.rstrip('/')}/panel/varliklar/og.png">
<meta property="og:locale" content="{dil}"><meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#127F56">
<link rel="icon" type="image/png" href="/panel/varliklar/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap" rel="stylesheet">{'<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap" rel="stylesheet">' if yon == "rtl" else ""}
<link rel="stylesheet" href="/site.css?v=4">
{ld}
</head>
<body>
<header class="sar ust"><a class="logo" href="{_yol(dil)}" aria-label="FeedZync"><img src="/panel/varliklar/feedzync-logo.png" alt="FeedZync" width="171" height="32"></a>
<nav aria-label="Main">{nav}</nav><span class="bosluk"></span>
<a class="giris-link" href="{E(uygulama)}/">{E(t(dil, "giris"))}</a><a class="dugme" href="{E(uygulama)}/?kayit=1&amp;dil={dil}">{E(t(dil, "basla"))}</a></header>
<main>{govde}</main>
<div class="yapiskan" aria-hidden="true"><a class="dugme" tabindex="-1" href="{E(uygulama)}/?kayit=1&amp;dil={dil}">{E(t(dil, "kutu_btn"))}</a></div>
<footer><div class="sar"><span>© 2026 FeedZync</span><a href="/legal/privacy">{E(t(dil, "gizlilik"))}</a><a href="/legal/terms">{E(t(dil, "kosullar"))}</a>
<a href="/legal/data-deletion">{E(t(dil, "veri_silme"))}</a><span style="flex:1"></span>
<label>{E(t(dil, "dil"))} <select onchange="location.href='/'+this.value+'/{(sayfa or '') if cok else ''}'" aria-label="{E(t(dil, 'dil'))}">{dil_sec}</select></label></div></footer>
<script>
(() => {{ const y = document.querySelector('.yapiskan'), f = document.querySelector('.basla-form, .son');
  if (!y || !('IntersectionObserver' in window)) return;
  // telefonda: baslatma formu ekrandan cikinca alta tek tus gelir; form ya da son cagri gorununce kaybolur
  new IntersectionObserver(([e]) => y.classList.toggle('gorunur', !e.isIntersecting && scrollY > 200)).observe(f || document.body);
}})();
document.querySelectorAll('form.basla-form').forEach(f => f.addEventListener('submit', e => {{
  e.preventDefault(); const ad = f.querySelector('input').value.trim();
  location.href = f.action + (f.action.includes('?') ? '&' : '?') + 'ad=' + encodeURIComponent(ad);
}}));
</script>
</body></html>"""


def _basla_formu(uygulama, dil):
    return (f'<form class="kutu basla-form" action="{E(uygulama)}/?kayit=1&amp;dil={dil}" method="get">'
            f'<label class="ekran-okuyucu" for="ad-{dil}">{E(t(dil, "kutu"))}</label>'
            f'<input id="ad-{dil}" name="ad" placeholder="{E(t(dil, "kutu"))}" autocomplete="organization" maxlength="80">'
            f'<button class="dugme" type="submit">{E(t(dil, "kutu_btn"))}</button></form>'
            f'<p class="kutu-not">{E(t(dil, "kutu_not"))}</p>')


def _fiyat_bolumu(uygulama, dil, baslik_seviyesi="h2"):
    paket = paketler.liste()
    kartlar = []
    for p in paket:
        ozellik = (t(dil, "paket_ozellik") or {}).get(p["kod"]) or p["ozellikler"]
        kartlar.append(
            f'<div class="paket {"one" if p.get("one_cikan") else ""}" data-paket="{p["kod"]}">'
            + (f'<span class="rozet">{E(t(dil, "populer"))}</span>' if p.get("one_cikan") else "")
            + f'<h3>{E(p["ad"])}</h3><div class="fiyat">${p["usd"]}<small>{E(t(dil, "ay"))}</small></div>'
            f'<div class="yerel soluk" data-usd="{p["usd"]}"></div>'
            f'<ul>{"".join(f"<li>{E(o)}</li>" for o in ozellik)}</ul>'
            f'<a class="dugme" href="{E(uygulama)}/?kayit=1&amp;dil={dil}&amp;paket={p["kod"]}">{E(t(dil, "fiyat_sec"))}</a></div>')
    return f"""<section class="bolum" id="fiyat"><div class="sar">
<div class="bolum-bas"><div><{baslik_seviyesi} style="font-size:clamp(30px,4.2vw,48px)">{E(t(dil, "fiyat_h"))}</{baslik_seviyesi}><p class="soluk" style="margin-top:12px">{E(t(dil, "fiyat_p"))}</p></div>
<label class="para-sec">{E(t(dil, "para_goster"))} <select id="para"><option>USD</option></select></label></div>
<div class="paketler">{"".join(kartlar)}</div><p class="fatura soluk">{E(t(dil, "fatura"))}</p></div></section>
<script>
(async () => {{
  const sec = document.getElementById('para'), ay = {json.dumps(t(dil, "ay"))};
  const ulkeler = (await (await fetch('/api/ulkeler')).json()).ulkeler;
  const tahmin = () => {{ for (const l of navigator.languages || [navigator.language]) {{ const r = (l.split('-')[1] || '').toUpperCase();
      const u = ulkeler.find(x => x.kod === r); if (u) return u.para; }}
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone; return (ulkeler.find(x => x.saat_dilimi === tz) || {{}}).para || 'USD'; }};
  async function goster(para) {{
    const f = await (await fetch('/api/fiyatlar?para=' + para)).json();
    sec.innerHTML = f.paralar.map(p => `<option ${{p === f.para ? 'selected' : ''}}>${{p}}</option>`).join('');
    document.querySelectorAll('.yerel').forEach((el, i) => {{ const p = f.paketler[i];
      el.textContent = f.para !== 'USD' && p.yerel != null ? '≈ ' + f.sembol + Number(p.yerel).toLocaleString() + ' ' + ay : ''; }});
  }}
  sec.onchange = () => {{ localStorage.setItem('fz_para', sec.value); goster(sec.value); }};
  goster(localStorage.getItem('fz_para') || tahmin()).catch(() => {{}});
}})();
</script>"""


def _sss_bolumu(dil, baslik_seviyesi="h2"):
    return (f'<section class="bolum sss" id="sss"><div class="sar" style="max-width:860px">'
            f'<{baslik_seviyesi} style="font-size:clamp(30px,4.2vw,48px);margin-bottom:24px">{E(t(dil, "sss_h"))}</{baslik_seviyesi}>'
            + "".join(f"<details><summary>{E(s)}</summary><p>{E(c)}</p></details>" for s, c in t(dil, "sss"))
            + "</div></section>")


def _son(uygulama, dil):
    return (f'<section class="bolum"><div class="sar"><div class="son"><h2>{E(t(dil, "son_h"))}</h2>'
            f'<a class="dugme" href="{E(uygulama)}/?kayit=1&amp;dil={dil}">{E(t(dil, "son_btn"))}</a></div></div></section>')


ONE_CIKAN = ("restoran", "guzellik", "moda", "emlak", "spor", "saglik", "eticaret", "otel", "egitim", "mobilya")


def ana(site, uygulama, dil):
    ekip = "".join(f"<li>{E(x)}</li>" for x in t(dil, "ekip"))
    adimlar = "".join(f"<li><h3>{E(a)}</h3><p>{E(b)}</p></li>" for a, b in t(dil, "adimlar"))
    ikonlar = ("post", "car", "reel", "diger")
    gun = "".join(f'<div><span class="ikon {ikonlar[i]}" aria-hidden="true"></span><h3>{E(a)}</h3><p>{E(b)}</p></div>'
                  for i, (a, b) in enumerate(t(dil, "gun")))
    tum = [f'<a href="/en/industries/{s}">{E(sektor_bilgi.SEKTORLER[k]["ad"])}</a>'
           for s, k in sorted(SLUG.items(), key=lambda x: (x[1] not in ONE_CIKAN, sektor_bilgi.SEKTORLER[x[1]]["ad"]))]
    ilk = len([k for k in SLUG.values() if k in ONE_CIKAN]) or 10
    sektorler = ("".join(tum[:ilk]) + f'<details class="hepsi"><summary>{E(t(dil, "sektor_hepsi").replace("{n}", str(len(tum))))}</summary>'
                 + "".join(tum[ilk:]) + "</details>")
    govde = f"""
<section class="sar kahraman"><div><h1>{E(t(dil, "h1"))}</h1><p class="alt">{E(t(dil, "alt"))}</p>{_basla_formu(uygulama, dil)}</div>
<aside class="ekip" aria-label="{E(t(dil, "ekip_h"))}"><h3>{E(t(dil, "ekip_h"))}</h3><ol>{ekip}</ol>
<div class="saatler"><span>12:00 · Post</span><span>15:00 · Carousel</span><span>18:30 · Reel</span></div></aside></section>
<section class="bolum beyaz" id="nasil"><div class="sar"><div class="bolum-bas"><h2>{E(t(dil, "nasil_h"))}</h2></div><ol class="adimlar">{adimlar}</ol></div></section>
<section class="bolum"><div class="sar"><div class="bolum-bas"><h2>{E(t(dil, "gun_h"))}</h2></div><div class="dortlu">{gun}</div></div></section>
<section class="bolum beyaz"><div class="sar durust"><p class="vurgu">{E(t(dil, "durust_h"))}</p><p style="font-size:19px">{E(t(dil, "durust_p"))}</p></div></section>
<section class="bolum"><div class="sar"><div class="bolum-bas"><h2>{E(t(dil, "sektor_h"))}</h2><p class="soluk">{E(t(dil, "sektor_p"))}</p></div><div class="sektorler">{sektorler}</div></div></section>
{_fiyat_bolumu(uygulama, dil)}{_sss_bolumu(dil)}{_son(uygulama, dil)}"""
    ld = _jsonld(_organizasyon(site), {"@context": "https://schema.org", "@type": "WebSite", "name": "FeedZync",
                                       "url": site, "inLanguage": dil}, _uygulama(site, dil), _sss_ld(dil))
    return iskelet(site, uygulama, dil, "", t(dil, "baslik"), t(dil, "aciklama"), govde, ld=ld)


def fiyat(site, uygulama, dil):
    govde = (f'<div class="sar ic" style="padding-bottom:0"><h1>{E(t(dil, "fiyat_h"))}</h1></div>'
             + _fiyat_bolumu(uygulama, dil, "h2") + _sss_bolumu(dil) + _son(uygulama, dil))
    return iskelet(site, uygulama, dil, "pricing", t(dil, "fiyat_sayfa_baslik"), t(dil, "fiyat_p") + " " + t(dil, "aciklama"),
                   govde, ld=_jsonld(_uygulama(site, dil), _sss_ld(dil)))


def sss(site, uygulama, dil):
    govde = (f'<div class="sar ic" style="padding-bottom:0"><h1>{E(t(dil, "sss_h"))}</h1></div>'
             + _sss_bolumu(dil, "h2") + _son(uygulama, dil))
    return iskelet(site, uygulama, dil, "faq", t(dil, "sss_baslik"), t(dil, "aciklama"), govde, ld=_jsonld(_sss_ld(dil)))


def _doldur(x):
    return (str(x).replace("{city}", "your city").replace("{business}", "your business")
            .replace("{product_type}", "product"))


def sektorler_sayfasi(site, uygulama):
    dil = "en"
    liste = "".join(f'<a href="/en/industries/{s}">{E(sektor_bilgi.SEKTORLER[k]["ad"])}</a>'
                    for s, k in sorted(SLUG.items(), key=lambda x: sektor_bilgi.SEKTORLER[x[1]]["ad"]))
    govde = (f'<div class="sar ic"><h1>{E(t(dil, "sektor_h"))}</h1><p class="soluk">{E(t(dil, "sektor_p"))}</p>'
             f'<div class="sektorler" style="margin-top:24px">{liste}</div></div>' + _son(uygulama, dil))
    return iskelet(site, uygulama, dil, "industries", t(dil, "sektor_liste_baslik"),
                   "FeedZync creates daily social media content for more than 30 kinds of business.", govde, diller=["en"])


def sektor_sayfasi(site, uygulama, sl):
    k = SLUG.get(sl)
    if not k:
        return None
    dil, s = "en", sektor_bilgi.SEKTORLER[k]
    ad = s["ad"]
    baslik = t(dil, "sektor_sayfa_h").format(s=ad.lower())
    aciklama = t(dil, "sektor_sayfa_p").format(s=ad.lower())
    isler = "".join(f"<li>{E(x)}</li>" for x in sektor_isleri.ISLER.get(k, [])[:10])
    fikirler = "".join(f"<li>{E(_doldur(x))}</li>" for x in s["fikirler"][:8])
    sutunlar = ", ".join(s["sutunlar"][:6])
    yol = f"industries/{sl}"
    govde = f"""<div class="sar ic"><p class="kirinti"><a href="/en/">FeedZync</a> › <a href="/en/industries">{E(t(dil, "sektor_tum"))}</a></p>
<h1>{E(baslik)}</h1><p style="font-size:20px">{E(aciklama)}</p>
{_basla_formu(uygulama, dil)}
<h2>Who your posts speak to</h2><p>{E(s["kitle"])}. Tone of voice: {E(s["ton"])}.</p>
<h2>{E(t(dil, "sektor_sunulan"))}</h2><ul>{isler}</ul>
<h2>{E(t(dil, "sektor_fikir"))}</h2><ul>{fikirler}</ul>
<h2>Content mix</h2><p>{E(sutunlar)}. Every week the team studies leading accounts in your sector and adapts what works to your brand.</p>
{('<h2>Handled with care</h2><p>' + E(s["dikkat"]) + '</p>') if s.get("dikkat") else ""}
</div>{_fiyat_bolumu(uygulama, dil)}{_son(uygulama, dil)}"""
    kirinti = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "FeedZync", "item": _kok(site, "en")},
        {"@type": "ListItem", "position": 2, "name": "Industries", "item": _kok(site, "en", "industries")},
        {"@type": "ListItem", "position": 3, "name": ad, "item": _kok(site, "en", yol)}]}
    return iskelet(site, uygulama, dil, yol, f"{baslik} — FeedZync", aciklama, govde, diller=["en"],
                   ld=_jsonld(kirinti, _uygulama(site, "en")))


# ---------------------------------------------------------------- yasal (Ingilizce)
YASAL = {
    "privacy": ("Privacy Policy", """
<p>This policy explains what FeedZync ("we") collects and how we use it. Last updated: November 2026.</p>
<h2>What we collect</h2><ul>
<li>Account data: your email address and sign-in details.</li>
<li>Business data you give us: business name, description, country, website address, logo, photos and documents you upload.</li>
<li>Public information from your website, used to understand what you offer.</li>
<li>If you connect Instagram and Facebook: page and account identifiers and an access token, stored encrypted, used only to publish your content and read basic engagement (comments, messages, insights) for your reports. We never reply to anyone on your behalf.</li>
<li>Usage data needed to run the service (job logs, error reports).</li></ul>
<h2>How we use it</h2><p>Only to create, schedule and publish social media content for your business and to run, secure and improve the service. We do not sell your data and do not use it for advertising.</p>
<h2>Processors</h2><p>We use trusted providers to run the service: cloud hosting and database (DigitalOcean, Supabase), AI providers that generate text and images from your business information, and free stock photo services. They process data only on our instructions.</p>
<h2>Photos you upload</h2><p>We remove hidden metadata such as location from photos when you upload them. Please do not upload photos of people without their permission.</p>
<h2>Retention and deletion</h2><p>We keep your data while your account is active. You can delete files at any time and ask us to delete your account and all data; see <a href="/legal/data-deletion">Data deletion</a>.</p>
<h2>Your rights</h2><p>You can access, correct, export or delete your data. Contact us through the email address shown in your account.</p>"""),
    "terms": ("Terms of Service", """
<p>By using FeedZync you agree to these terms. Last updated: November 2026.</p>
<h2>The service</h2><p>FeedZync uses AI to prepare and publish social media content for your business based on the information you provide. You remain responsible for your business information and for content published on your accounts. You can change, stop or delete any post at any time.</p>
<h2>Free trial and plans</h2><p>New accounts get a 7-day free trial without a card. Paid plans are billed monthly in US dollars; local currency amounts shown on the site are approximate. You can cancel at any time; access continues until the end of the paid period.</p>
<h2>Acceptable use</h2><p>Do not use FeedZync for unlawful, misleading or harmful content, or to publish content you do not have the rights to. We may suspend accounts that break these rules or the rules of the social platforms.</p>
<h2>Your content</h2><p>You keep all rights to your content, logo and photos. You give us permission to use them only to provide the service.</p>
<h2>Availability</h2><p>We work to keep the service running but cannot guarantee uninterrupted availability or that every post will be published (for example if a platform rejects it).</p>
<h2>Liability</h2><p>To the extent allowed by law, our liability is limited to the amount you paid in the last 3 months.</p>"""),
    "data-deletion": ("Data deletion", """
<p>You can delete your data at any time.</p>
<h2>Delete files and posts</h2><p>In the app, open <b>Photos &amp; files</b> to delete uploaded files, and open any post to delete it from Instagram and Facebook.</p>
<h2>Disconnect Instagram and Facebook</h2><p>In the app, open <b>Business → Accounts → Disconnect</b>. This removes our access token immediately. You can also remove FeedZync in Facebook under Settings → Business integrations.</p>
<h2>Delete your account and all data</h2><p>Email us from the address you signed up with and ask for account deletion. We delete your business data, files, content and connection tokens within 30 days and confirm by email.</p>"""),
}


def yasal(site, uygulama, ad):
    if ad not in YASAL:
        return None
    baslik, icerik = YASAL[ad]
    govde = f'<div class="sar ic"><h1>{E(baslik)}</h1>{icerik}</div>'
    return iskelet(site, uygulama, "en", None, f"{baslik} — FeedZync", f"FeedZync {baslik.lower()}.", govde,
                   diller=["en"], canonical=site.rstrip("/") + f"/legal/{ad}")


def site_haritasi(site):
    from datetime import date
    bugun = date.today().isoformat()
    satir = []

    def ekle(yol, diller):
        alt = "".join(f'<xhtml:link rel="alternate" hreflang="{d}" href="{_kok(site, d, yol)}"/>' for d in diller) \
            if len(diller) > 1 else ""
        for d in diller:
            satir.append(f"<url><loc>{_kok(site, d, yol)}</loc><lastmod>{bugun}</lastmod>{alt}</url>")
    for s in SAYFALAR:
        ekle(s, list(DILLER))
    ekle("industries", ["en"])
    for sl in SLUG:
        ekle(f"industries/{sl}", ["en"])
    for ad in YASAL:
        satir.append(f"<url><loc>{site.rstrip('/')}/legal/{ad}</loc></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + "".join(satir) + "</urlset>")


def dil_sec(kabul):
    """Accept-Language basligindan desteklenen en iyi dil."""
    for parca in (kabul or "").split(","):
        d = parca.split(";")[0].strip().lower().split("-")[0]
        if d in DILLER:
            return d
    return metin.VARSAYILAN


def kayit_adresi(uygulama, dil, ad=""):
    return f"{uygulama}/?kayit=1&dil={dil}" + (f"&ad={quote(ad)}" if ad else "")
