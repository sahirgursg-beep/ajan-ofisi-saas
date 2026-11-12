"""Siteden urun cekme araci (Ticimax uyumlu, genel yaklasim).

Sira:
 1) config'te feed_url varsa XML urun feed'i (Google/Facebook katalog formati)
 2) yoksa sitemap.xml -> urun sayfalari
 3) o da olmazsa ana sayfa + kategori sayfalarindaki linkler
Her urun sayfasindan JSON-LD, og: etiketleri ve Ticimax gorsel yollari okunur.
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .ayarlar import AYAR, KOK, VERI

BASLIK = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FR-Ajan-Ofisi/1.0"}
ONBELLEK = VERI / "urunler.json"
TUM_ONBELLEK = VERI / "tum_urunler.json"   # kategori filtresinden once (plan icin kategori secimi)


def _get(url, timeout=20):
    r = requests.get(url, headers=BASLIK, timeout=timeout)
    r.raise_for_status()
    return r


def _yerel(etiket):
    return etiket.rsplit("}", 1)[-1].split(":")[-1].lower()


def _sayi(s):
    if s is None:
        return None
    s = str(s)
    m = re.search(r"[\d.,]+", s)
    if not m:
        return None
    t = m.group(0)
    # 1.234,56 / 1,234.56 / 1234
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", "") if len(t.split(",")[-1]) == 3 else t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# ---------- 1) XML feed ----------
def _feed_indir(url):
    """Once normal istek; site Cloudflare korumasi verirse gercek tarayici (Playwright) ile dener."""
    try:
        r = requests.get(url, headers={**BASLIK, "Accept": "application/xml,text/xml,*/*"}, timeout=90)
        if r.status_code == 200 and (b"<Urun" in r.content[:5000] or b"<item" in r.content[:5000]):
            return r.content
    except Exception:
        pass
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        sayfa = b.new_page()
        site = AYAR["site"]
        sayfa.goto(site, wait_until="domcontentloaded", timeout=60000)
        sayfa.wait_for_timeout(6000)  # Cloudflare kontrolunun bitmesini bekle
        metin = sayfa.evaluate("async u => await (await fetch(u)).text()", url)
        b.close()
    return metin.encode("utf-8")


BUYUK_KAL = {"TV", "LED", "XL", "XXL", "MDF", "L", "U", "II", "III", "IV"}


def guzel_ad(ad):
    """'CHERRY 210 TV WALL UNIT' -> 'Cherry 210 TV Wall Unit'"""
    kelimeler = []
    for k in ad.split():
        temiz = re.sub(r"[^A-Za-z]", "", k).upper()
        kelimeler.append(k.upper() if temiz in BUYUK_KAL or any(c.isdigit() for c in k) else "-".join(x.capitalize() for x in k.split("-")))
    return " ".join(kelimeler)


def ticimax_feed(kok):
    """Ticimax XML formati: Root/Urunler/Urun"""
    urunler = []
    for u in kok.iter("Urun"):
        g = lambda n: (u.findtext(n) or "").strip()
        kat_ham = g("KategoriTree").replace("DININGROOM", "DINING ROOM").replace("LIVINGROOM", "LIVING ROOM")
        secenekler = u.findall(".//Secenek")
        satis = indirimli = pb = None
        if secenekler:
            s = min(secenekler, key=lambda s: _sayi(s.findtext("IndirimliFiyat")) or _sayi(s.findtext("SatisFiyati")) or 1e12)
            satis = _sayi(s.findtext("SatisFiyati"))
            indirimli = _sayi(s.findtext("IndirimliFiyat"))
            pb = (s.findtext("ParaBirimi") or "").strip() or None
        if indirimli is not None and satis is not None and not (0 < indirimli < satis):
            indirimli = None
        urunler.append({
            "id": g("UrunKartiID"),
            "ad": guzel_ad(g("UrunAdi")),
            "url": g("UrunUrl"),
            "fiyat": indirimli or satis,  # musterinin odeyecegi fiyat
            "eski_fiyat": satis if indirimli else None,
            "para_birimi": pb,
            "kategori": " > ".join(guzel_ad(p) for p in kat_ham.split("/")),
            "aciklama": BeautifulSoup(g("Aciklama"), "html.parser").get_text(" ", strip=True)[:500],
            "gorseller": [r.text.strip() for r in u.iter("Resim") if r.text and r.text.strip()],
        })
    return [x for x in urunler if x["ad"] and x["gorseller"] and x["fiyat"]]


def feed_oku(url):
    kok = ET.fromstring(_feed_indir(url))
    if kok.find(".//Urun") is not None:
        return ticimax_feed(kok)
    urunler = []
    for item in kok.iter():
        if _yerel(item.tag) not in ("item", "entry", "product", "urun"):
            continue
        alan = {}
        gorseller = []
        for c in item:
            ad = _yerel(c.tag)
            deger = (c.text or "").strip() or c.attrib.get("href", "")
            if ad in ("image_link", "additional_image_link", "image", "resim"):
                gorseller.append(deger)
            else:
                alan.setdefault(ad, deger)
        fiyat_metni = alan.get("sale_price") or alan.get("price") or alan.get("fiyat")
        pb = None
        if fiyat_metni:
            m = re.search(r"[A-Z]{3}", fiyat_metni)
            pb = m.group(0) if m else None
        urunler.append({
            "ad": alan.get("title") or alan.get("name") or alan.get("urunadi", ""),
            "url": alan.get("link") or alan.get("url", ""),
            "fiyat": _sayi(fiyat_metni),
            "para_birimi": pb,
            "kategori": alan.get("product_type") or alan.get("google_product_category") or alan.get("kategori", ""),
            "aciklama": BeautifulSoup(alan.get("description", ""), "html.parser").get_text(" ", strip=True)[:500],
            "gorseller": [g for g in gorseller if g],
        })
    return [u for u in urunler if u["ad"] and u["gorseller"]]


# ---------- 2) sitemap ----------
def sitemap_linkleri(site):
    adaylar = [urljoin(site, "/sitemap.xml"), urljoin(site, "/sitemap_index.xml")]
    try:
        robots = _get(urljoin(site, "/robots.txt"), 10).text
        adaylar = re.findall(r"(?im)^sitemap:\s*(\S+)", robots) + adaylar
    except Exception:
        pass
    linkler, gezilen = [], set()

    def gez(url, derinlik=0):
        if url in gezilen or derinlik > 2:
            return
        gezilen.add(url)
        try:
            kok = ET.fromstring(_get(url, 30).content)
        except Exception:
            return
        alt, sayfa = [], []
        for e in kok.iter():
            if _yerel(e.tag) == "loc" and e.text:
                (alt if e.text.strip().lower().endswith(".xml") else sayfa).append(e.text.strip())
        # urun sitemap'leri once
        alt.sort(key=lambda u: 0 if re.search(r"urun|product", u, re.I) else 1)
        for a in alt:
            gez(a, derinlik + 1)
        linkler.extend(sayfa)

    for a in adaylar:
        gez(a)
        if linkler:
            break
    return list(dict.fromkeys(linkler))


# ---------- 3) sayfa linkleri ----------
def sayfa_linkleri(site):
    linkler = []
    for sayfa in [site] + AYAR.get("kategori_sayfalari", []):
        try:
            soup = BeautifulSoup(_get(sayfa).text, "html.parser")
        except Exception:
            continue
        host = urlparse(site).netloc
        for a in soup.find_all("a", href=True):
            u = urljoin(sayfa, a["href"]).split("#")[0]
            if urlparse(u).netloc == host:
                linkler.append(u)
    return list(dict.fromkeys(linkler))


# ---------- urun sayfasi ----------
def _jsonld(soup):
    sonuc = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            veri = json.loads(s.string or "")
        except Exception:
            continue
        yigin = veri if isinstance(veri, list) else [veri]
        while yigin:
            d = yigin.pop()
            if isinstance(d, dict):
                sonuc.append(d)
                if "@graph" in d:
                    yigin.extend(d["@graph"])
    return sonuc


def urun_sayfasi_oku(url):
    soup = BeautifulSoup(_get(url).text, "html.parser")
    ld = _jsonld(soup)
    urun = next((d for d in ld if "product" in str(d.get("@type", "")).lower()), None)
    meta = lambda p: (soup.find("meta", property=p) or soup.find("meta", attrs={"name": p}) or {}).get("content")

    ad = fiyat = pb = None
    gorseller, aciklama, kategori = [], "", ""
    if urun:
        ad = urun.get("name")
        aciklama = urun.get("description", "")
        img = urun.get("image")
        gorseller += img if isinstance(img, list) else [img] if img else []
        teklif = urun.get("offers") or {}
        if isinstance(teklif, list):
            teklif = teklif[0] if teklif else {}
        fiyat = _sayi(teklif.get("price") or teklif.get("lowPrice"))
        pb = teklif.get("priceCurrency")
        kategori = urun.get("category", "") or ""
    fiyat = fiyat or _sayi(meta("product:price:amount") or meta("og:price:amount"))
    pb = pb or meta("product:price:currency")
    if fiyat is None:
        el = soup.find(attrs={"itemprop": "price"})
        if el:
            fiyat = _sayi(el.get("content") or el.get_text())
    if not ad and (meta("og:type") or "").lower().startswith("product"):
        ad = meta("og:title")
    if not ad or fiyat is None:
        return None  # urun sayfasi degil

    # Breadcrumb -> kategori
    for d in ld:
        if "breadcrumb" in str(d.get("@type", "")).lower():
            kategori += " > " + " > ".join(
                str((i.get("item") or {}).get("name") if isinstance(i.get("item"), dict) else i.get("name", ""))
                for i in d.get("itemListElement", []))
    bc = soup.find(class_=re.compile("breadcrumb", re.I))
    if bc:
        kategori += " > " + bc.get_text(" > ", strip=True)

    # Ticimax gorselleri (UrunResim klasoru), og:image
    if meta("og:image"):
        gorseller.append(meta("og:image"))
    for img in soup.find_all("img"):
        src = img.get("data-original") or img.get("data-src") or img.get("src") or ""
        if "urunresim" in src.lower():
            gorseller.append(urljoin(url, src))
    gorseller = [urljoin(url, g) for g in gorseller if isinstance(g, str) and g]
    # buyuk boyutlu olanlari one al, tekrarlari at
    gorseller = sorted(dict.fromkeys(gorseller), key=lambda g: 0 if re.search(r"buyuk|large|big", g, re.I) else 1)

    return {
        "ad": ad.strip(), "url": url, "fiyat": fiyat, "para_birimi": pb,
        "kategori": kategori.strip(" >"),
        "aciklama": BeautifulSoup(aciklama, "html.parser").get_text(" ", strip=True)[:500],
        "gorseller": gorseller[:6],
    }


def _sade(s):
    return re.sub(r"[^a-z]", "", s.lower())


def kategori_uygun(urun):
    anahtarlar = [_sade(k) for k in AYAR.get("kategoriler", [])]
    haric = [_sade(k) for k in AYAR.get("haric_kategoriler", [])]
    metin = _sade(urun.get("kategori", "") + " " + urun.get("url", ""))
    if any(h and h in metin for h in haric):
        return False
    return not anahtarlar or any(k in metin for k in anahtarlar)


def urunleri_cek(gunluk=print):
    site = AYAR["site"]
    urunler = []
    if AYAR.get("feed_url"):
        gunluk("XML feed okunuyor...")
        urunler = feed_oku(AYAR["feed_url"])
    else:
        gunluk("sitemap.xml aranıyor...")
        linkler = sitemap_linkleri(site)
        if not linkler:
            gunluk("sitemap yok, sayfa linkleri taranıyor...")
            linkler = sayfa_linkleri(site)
        # kategori kelimesi gecen linkleri one al
        linkler.sort(key=lambda u: 0 if kategori_uygun({"url": u}) else 1)
        gunluk(f"{len(linkler)} link bulundu, urun sayfalari okunuyor...")
        for u in linkler:
            if len(urunler) >= AYAR.get("max_urun_tarama", 60):
                break
            try:
                p = urun_sayfasi_oku(u)
            except Exception:
                p = None
            if p and p["gorseller"]:
                urunler.append(p)
    TUM_ONBELLEK.parent.mkdir(parents=True, exist_ok=True)
    TUM_ONBELLEK.write_text(json.dumps(urunler, ensure_ascii=False), encoding="utf-8")
    uygun = [u for u in urunler if kategori_uygun(u)]
    if urunler and not uygun:
        gunluk("! Kategori filtresi hic urun birakmadi, tum urunler kullaniliyor.")
        uygun = urunler
    ONBELLEK.parent.mkdir(parents=True, exist_ok=True)
    ONBELLEK.write_text(json.dumps(uygun, ensure_ascii=False, indent=2), encoding="utf-8")
    return uygun


def tum_onbellekten():
    if TUM_ONBELLEK.exists():
        return json.loads(TUM_ONBELLEK.read_text(encoding="utf-8"))
    return []


def onbellekten():
    if ONBELLEK.exists():
        return json.loads(ONBELLEK.read_text(encoding="utf-8"))
    return []


def gorsel_indir(url, klasor: Path, ad):
    klasor.mkdir(parents=True, exist_ok=True)
    if not url.lower().startswith("http"):
        return Path(url.replace("file://", ""))  # yerel dosya (demo)
    hedef = klasor / ad
    if not hedef.exists():
        hedef.write_bytes(_get(url, 30).content)
    return hedef
