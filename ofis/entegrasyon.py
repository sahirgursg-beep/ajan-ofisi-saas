"""Web sitesi entegrasyonlari: musterinin sitesinden urun ve icerik verisini anahtarsiz ceker.

Desteklenenler (hepsi acik/genel uc noktalar, musteriden sifre ya da API anahtari istenmez):
  shopify      -> /products.json                      (tum Shopify magazalarinda acik)
  woocommerce  -> /wp-json/wc/store/v1/products       (WooCommerce Store API, acik)
  wordpress    -> /wp-json/wp/v2/posts                (blog yazilari: hizmet isletmeleri icin icerik kaynagi)
  xml          -> Google/Facebook urun feed'i (urun_cekici.feed_oku)
  ticimax      -> XML feed (urun_cekici)
  genel        -> sitemap + urun sayfalari (JSON-LD); o da olmazsa gercek tarayiciyla (Playwright) tarama
Bu modul saf: ayarlar'i ice aktarmaz (web servisi de site kontrolunde kullanir).
Urun bicimi: {ad, url, fiyat, para_birimi, kategori, aciklama, gorseller}
"""
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASLIK = {"User-Agent": "Mozilla/5.0 (compatible; FeedZync/1.0; +https://feedzync.com)",
          "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}


# ---------------------------------------------------------------- guvenlik
def guvenli_adres(url):
    """Yalnizca http(s) ve genel internet adresleri (ic ag / sunucunun kendisi degil)."""
    try:
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return False
        for bilgi in socket.getaddrinfo(u.hostname, None):
            ip = ipaddress.ip_address(bilgi[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def normallestir(site):
    site = (site or "").strip()
    if not site:
        return ""
    if not re.match(r"^https?://", site, re.I):
        site = "https://" + site
    u = urlparse(site)
    return f"{u.scheme}://{u.netloc}".lower()


def _metin(html, sinir=500):
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)[:sinir]


def _json(http, url, timeout=20):
    r = http.get(url, headers=BASLIK, timeout=timeout)
    if r.status_code != 200 or "json" not in (r.headers.get("content-type") or "").lower():
        return None
    try:
        return r.json()
    except ValueError:
        return None


# ---------------------------------------------------------------- algilama
def platform_bul(site, oturum=None, html=None):
    """-> 'shopify' | 'woocommerce' | 'wordpress' | 'ticimax' | 'genel' | '' (site yok/acilmiyor)"""
    http = oturum or requests
    site = normallestir(site)
    if not site:
        return ""
    try:
        if html is None:
            html = http.get(site, headers=BASLIK, timeout=20).text
    except Exception:
        html = ""
    h = (html or "").lower()
    if "cdn.shopify.com" in h or "shopify.theme" in h:
        return "shopify"
    if "ticimax" in h:
        return "ticimax"
    try:
        d = _json(http, urljoin(site, "/products.json?limit=1"))
        if isinstance(d, dict) and isinstance(d.get("products"), list):
            return "shopify"
    except Exception:
        pass
    if "wp-content" in h or "wp-json" in h or "woocommerce" in h:
        try:
            d = _json(http, urljoin(site, "/wp-json/wc/store/v1/products?per_page=1"))
            if isinstance(d, list):
                return "woocommerce"
        except Exception:
            pass
        return "wordpress"
    return "genel" if html else ""


def site_bilgisi(site, oturum=None):
    """Kayit ekrani icin hizli kontrol: platform + sitenin kendi baslik/aciklamasi + logo adayi."""
    http = oturum or requests
    site = normallestir(site)
    if not site or not guvenli_adres(site):
        return {"tamam": False, "hata": "Enter a valid public website address"}
    try:
        r = http.get(site, headers=BASLIK, timeout=15)
        r.raise_for_status()
        if getattr(r, "url", site) and not guvenli_adres(str(getattr(r, "url", site))):
            return {"tamam": False, "hata": "Enter a valid public website address"}
    except Exception as e:
        return {"tamam": False, "site": site, "hata": f"We could not open this website ({type(e).__name__})"}
    soup = BeautifulSoup(r.text, "html.parser")
    meta = lambda *ad: next((m.get("content") for a in ad for m in [soup.find("meta", attrs={"property": a})
                                                                     or soup.find("meta", attrs={"name": a})] if m and m.get("content")), "")
    ikon = soup.find("link", rel=lambda v: v and any("icon" in x.lower() for x in (v if isinstance(v, list) else [v])))
    return {"tamam": True, "site": site, "platform": platform_bul(site, http, r.text),
            "baslik": (meta("og:site_name") or (soup.title.string if soup.title else "") or "").strip()[:80],
            "aciklama": (meta("og:description", "description") or "").strip()[:240],
            "gorsel": urljoin(site, meta("og:image")) if meta("og:image") else "",
            "ikon": urljoin(site, ikon["href"]) if ikon and ikon.get("href") else ""}


# ---------------------------------------------------------------- shopify
def shopify_urunleri(site, oturum=None, en_fazla=120):
    http = oturum or requests
    site = normallestir(site)
    out = []
    for sayfa in range(1, 4):
        d = _json(http, urljoin(site, f"/products.json?limit=250&page={sayfa}"), 30)
        urunler = (d or {}).get("products") or []
        for p in urunler:
            varyant = (p.get("variants") or [{}])[0]
            gorseller = [g.get("src") for g in p.get("images") or [] if g.get("src")]
            if not gorseller:
                continue
            fiyat = _sayi(varyant.get("price"))
            eski = _sayi(varyant.get("compare_at_price"))
            etiket = p.get("tags") or []
            etiket = ", ".join(etiket) if isinstance(etiket, list) else str(etiket)
            out.append({"ad": p.get("title", "").strip(), "url": urljoin(site, f"/products/{p.get('handle')}"),
                        "fiyat": fiyat, "eski_fiyat": eski if eski and fiyat and eski > fiyat else None,
                        "para_birimi": None, "kategori": (p.get("product_type") or etiket)[:80],
                        "aciklama": _metin(p.get("body_html")), "gorseller": gorseller[:6],
                        "stokta": any(v.get("available", True) for v in p.get("variants") or [{}])})
            if len(out) >= en_fazla:
                return out
        if len(urunler) < 250:
            break
    return out


# ---------------------------------------------------------------- woocommerce
def woocommerce_urunleri(site, oturum=None, en_fazla=120):
    http = oturum or requests
    site = normallestir(site)
    out = []
    for sayfa in range(1, 4):
        d = _json(http, urljoin(site, f"/wp-json/wc/store/v1/products?per_page=100&page={sayfa}"), 30)
        if not isinstance(d, list) or not d:
            break
        for p in d:
            fiyatlar = p.get("prices") or {}
            birim = int(fiyatlar.get("currency_minor_unit") or 0)
            bol = lambda v: (_sayi(v) / (10 ** birim)) if _sayi(v) is not None else None
            fiyat, normal = bol(fiyatlar.get("sale_price") or fiyatlar.get("price")), bol(fiyatlar.get("regular_price"))
            gorseller = [g.get("src") for g in p.get("images") or [] if g.get("src")]
            if not gorseller:
                continue
            out.append({"ad": _metin(p.get("name"), 120), "url": p.get("permalink") or site,
                        "fiyat": fiyat, "eski_fiyat": normal if normal and fiyat and normal > fiyat else None,
                        "para_birimi": fiyatlar.get("currency_code"),
                        "kategori": ", ".join(c.get("name", "") for c in p.get("categories") or []),
                        "aciklama": _metin(p.get("short_description") or p.get("description")),
                        "gorseller": gorseller[:6], "stokta": p.get("is_in_stock", True)})
            if len(out) >= en_fazla:
                return out
        if len(d) < 100:
            break
    return out


# ---------------------------------------------------------------- wordpress (blog)
def wordpress_yazilari(site, oturum=None, adet=12):
    """Son blog yazilari: {baslik, ozet, url, gorsel} - hizmet isletmeleri icin gercek icerik kaynagi."""
    http = oturum or requests
    site = normallestir(site)
    d = _json(http, urljoin(site, f"/wp-json/wp/v2/posts?per_page={adet}&_embed=1"), 30)
    out = []
    for p in d if isinstance(d, list) else []:
        medya = ((p.get("_embedded") or {}).get("wp:featuredmedia") or [{}])[0]
        out.append({"baslik": _metin((p.get("title") or {}).get("rendered"), 140),
                    "ozet": _metin((p.get("excerpt") or {}).get("rendered"), 400),
                    "url": p.get("link"), "gorsel": medya.get("source_url") if isinstance(medya, dict) else None})
    return [y for y in out if y["baslik"]]


# ---------------------------------------------------------------- gercek tarayici (yedek)
def tarayici_ile_tara(site, urun_oku, en_fazla=40, sayfa_sinir=60, gunluk=print):
    """JavaScript ile acilan siteler: Playwright ile ana sayfa + ayni alandaki linkleri gezer,
    her sayfanin HTML'ini urun_oku(html, url) ile cozer. Playwright yoksa bos liste."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        gunluk("Gercek tarayici (Playwright) kurulu degil; tarayici taramasi atlandi.")
        return []
    site = normallestir(site)
    alan = urlparse(site).netloc
    urunler, gezilen = [], set()
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            s = b.new_page(user_agent=BASLIK["User-Agent"])
            s.goto(site, wait_until="networkidle", timeout=60000)
            linkler = s.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            linkler = [u.split("#")[0] for u in dict.fromkeys(linkler) if urlparse(u).netloc == alan]
            linkler.sort(key=lambda u: 0 if re.search(r"product|urun|shop|item|/p/|catalog|menu", u, re.I) else 1)
            gunluk(f"Tarayici: {len(linkler)} link bulundu, urun sayfalari inceleniyor...")
            for u in linkler[:sayfa_sinir]:
                if u in gezilen or len(urunler) >= en_fazla:
                    continue
                gezilen.add(u)
                try:
                    s.goto(u, wait_until="domcontentloaded", timeout=30000)
                    s.wait_for_timeout(800)
                    urun = urun_oku(s.content(), u)
                except Exception:
                    urun = None
                if urun and urun.get("gorseller"):
                    urunler.append(urun)
        finally:
            b.close()
    return urunler


def _sayi(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        m = re.search(r"[\d.]+", str(v).replace(",", ""))
        return float(m.group(0)) if m else None
