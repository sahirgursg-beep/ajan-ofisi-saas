"""Tanitim sitesi: cok dilli sayfalar, SEO etiketleri, site haritasi, robots, alan adina gore yonlendirme."""
import json
import re

import requests

from saas.site import metin, sayfa

SITE = {"Host": "feedzync.com"}


def test_her_dilde_ana_fiyat_sss_sayfalari(sunucu):
    for dil in metin.DILLER:
        for yol in ("", "pricing", "faq"):
            r = requests.get(f"{sunucu}/{dil}/{yol}", headers=SITE)
            assert r.status_code == 200, (dil, yol)
            h = r.text
            assert f'<html lang="{dil}"' in h and 'rel="canonical"' in h and 'hreflang="x-default"' in h
            assert h.count('rel="alternate" hreflang=') == len(metin.DILLER) + 1
            assert "og:image" in h and "application/ld+json" in h
            for blok in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h):
                json.loads(blok)
    ar = requests.get(f"{sunucu}/ar/", headers=SITE).text
    assert 'dir="rtl"' in ar and "ابدأ مجاناً" in ar
    assert requests.get(f"{sunucu}/xx/", headers=SITE).status_code == 404


def test_tum_dillerde_ayni_anahtarlar():
    for dil, d in metin.DILLER.items():
        eksik = [k for k in ("h1", "alt", "kutu", "ekip", "adimlar", "gun", "sss", "paket_ozellik", "fiyat_h") if k not in d]
        assert not eksik, (dil, eksik)
        assert len(d["sss"]) == len(metin.EN["sss"]) and set(d["paket_ozellik"]) == {"starter", "growth", "pro"}


def test_ana_sayfa_kayit_ve_fiyat(sunucu):
    h = requests.get(f"{sunucu}/en/", headers=SITE).text
    assert "?kayit=1&amp;dil=en" in h and "$10" in h and "$30" in h and "$60" in h and "Most popular" in h
    assert '"lowPrice": "10"' in h and '"FAQPage"' in h


def test_sektor_ve_yasal_sayfalar(sunucu):
    assert "restaurants-cafes-and-food" in sayfa.SLUG
    r = requests.get(f"{sunucu}/en/industries/restaurants-cafes-and-food", headers=SITE)
    assert r.status_code == 200 and "AI social media manager for restaurants" in r.text and "BreadcrumbList" in r.text
    assert "{city}" not in r.text
    assert requests.get(f"{sunucu}/en/industries", headers=SITE).status_code == 200
    assert requests.get(f"{sunucu}/en/industries/nope", headers=SITE).status_code == 404
    for ad in ("privacy", "terms", "data-deletion"):
        assert requests.get(f"{sunucu}/legal/{ad}", headers=SITE).status_code == 200


def test_site_haritasi_ve_robots(sunucu):
    x = requests.get(f"{sunucu}/sitemap.xml", headers=SITE).text
    assert x.count("<url>") == len(metin.DILLER) * 3 + 1 + len(sayfa.SLUG) + 3 and "xhtml:link" in x
    assert "Sitemap: https://feedzync.com/sitemap.xml" in requests.get(f"{sunucu}/robots.txt", headers=SITE).text
    assert "Disallow: /\n" in requests.get(f"{sunucu}/robots.txt").text                 # uygulama alani


def test_alan_adina_gore_davranis(sunucu):
    r = requests.get(sunucu + "/", headers={**SITE, "Accept-Language": "fr-FR,fr;q=0.9"}, allow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/fr/"
    r = requests.get(sunucu + "/", headers={**SITE, "Accept-Language": "ja"}, allow_redirects=False)
    assert r.headers["location"] == "/en/"
    assert "X-Robots-Tag" not in requests.get(sunucu + "/en/", headers=SITE).headers
    app = requests.get(sunucu + "/")
    assert app.status_code == 200 and "FeedZync" in app.text and app.headers["X-Robots-Tag"] == "noindex"
