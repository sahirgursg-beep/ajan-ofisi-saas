"""Isletme ozeti (brief): tum ajanlarin uzerine konustugu GERCEKLER.

Kaynaklar: musterinin tek cumlelik tanimi + (varsa) web sitesinin ana sayfasi ve 'hakkimizda/hizmetler'
sayfalari. Yapay zeka bunlardan kisa bir ozet cikarir:
  ne_yapar, sunulanlar (hizmet/urun), kime, farki, kanitlanmis_bilgiler (sitede gecen somut bilgiler),
  gorsel_dunyasi (fotograflarda ne gorunmeli), gorselde_olmamali, yasaklar.
Ozet VERI/marka_ozeti.json'da tutulur; tanim/site degisince ya da 30 gunde bir yenilenir.
Amac: ajanlarin uydurmamasi (sahte musteri hikayesi, istatistik) ve gorsellerin isletmenin kendi dunyasini
gostermesi (or. sosyal medya ajansi icin moda butigi fotografi DEGIL).
"""
import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests

from . import llm, musteri
from .ayarlar import AYAR, VERI

YOL = VERI / "marka_ozeti.json"
YENILEME_GUN = 30
ALT_SAYFA = re.compile(r"about|hakkimizda|hakkında|services|hizmet|what-we-do|pricing|features|menu|products|who-we-are",
                       re.I)


def _site():
    s = (AYAR.get("site") or "").strip()
    return "" if not s or "example.com" in s else s


def _imza():
    i = musteri.bilgi()
    return hashlib.sha1(f"{i.get('ad')}|{i.get('tanim')}|{_site()}|v1".encode()).hexdigest()[:12]


def _metin(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "iframe"]):
        t.decompose()
    baslik = (soup.title.string or "").strip() if soup.title else ""
    aciklama = (soup.find("meta", attrs={"name": "description"}) or {}).get("content", "") if soup else ""
    govde = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return soup, f"{baslik}\n{aciklama}\n{govde}"


def site_metni(oturum=None, en_fazla=9000):
    """Ana sayfa + en fazla 2 alt sayfanin duz metni ('' = site yok/okunamadi)."""
    site = _site()
    if not site:
        return ""
    http = oturum or requests
    basliklar = {"User-Agent": "Mozilla/5.0 (FeedZync content assistant)"}
    try:
        r = http.get(site, timeout=20, headers=basliklar)
        r.raise_for_status()
        soup, metin = _metin(r.text)
    except Exception as e:
        print(f"  ! Site okunamadi ({type(e).__name__}): {str(e)[:100]}")
        return ""
    parcalar = [metin[:5000]]
    alan = urlparse(site).netloc
    linkler = []
    for a in soup.find_all("a", href=True):
        u = urljoin(site, a["href"])
        if urlparse(u).netloc == alan and ALT_SAYFA.search(u + " " + a.get_text(" ")) and u not in linkler:
            linkler.append(u)
    for u in linkler[:2]:
        try:
            r = http.get(u, timeout=20, headers=basliklar)
            r.raise_for_status()
            parcalar.append(_metin(r.text)[1][:2500])
        except Exception:
            pass
    return "\n---\n".join(parcalar)[:en_fazla]


def ozet(yenile=False, oturum=None):
    """-> dict (bos dict = olusturulamadi; ajanlar yalnizca tanimla devam eder)."""
    imza = _imza()
    try:
        d = json.loads(YOL.read_text(encoding="utf-8"))
        taze = datetime.fromisoformat(d.get("tarih", "2000-01-01")) > datetime.now() - timedelta(days=YENILEME_GUN)
        if d.get("_imza") == imza and taze and not yenile:
            return d
    except Exception:
        d = {}
    if not llm.hazir():
        return d if d.get("_imza") == imza else {}
    i = musteri.bilgi()
    kaynak = site_metni(oturum)
    cevap = llm.sor(
        "You are a brand strategist. You read what a business says about itself and write a factual brief "
        "for its social media team. Never invent anything. Answer ONLY with valid JSON.",
        f"Business name: {i.get('ad')}\nOwner's one-line description: {i.get('tanim') or '-'}\n"
        f"Location: {musteri.sehirler_metni()}, {i.get('ulke') or ''}\nSales channel: {musteri.satis_kanali()}\n"
        f"Website text (may be empty):\n{kaynak or '(no website text)'}\n\n"
        "Write the brief in English:\n"
        '{"ne_yapar": "<what the business does, 1 sentence, concrete>", '
        '"sunulanlar": ["<up to 8 products/services they actually offer>"], '
        '"kime": "<who the customers are>", '
        '"farki": "<what makes them different, ONLY if stated; else empty>", '
        '"kanitlanmis_bilgiler": ["<up to 8 concrete facts stated in the text: features, locations, years, '
        'opening hours, offers. Never numbers or results that are not written there>"], '
        '"gorsel_dunyasi": "<what photos for THIS business should show: their own product/service, their '
        'workplace, the moment of using it; 1-2 sentences>", '
        '"stok_terimleri": ["<6 stock-photo search terms (2-4 words) that show THIS business\'s own world>"], '
        '"gorselde_olmamali": "<what must not be shown (e.g. a software agency must not show clothes or food '
        'as if it sold them)>", '
        '"b2b": <true if they mainly sell to other businesses>}',
        json_mod=True, sicaklik=0.2)
    if not isinstance(cevap, dict) or not cevap.get("ne_yapar"):
        return d if d.get("_imza") == imza else {}
    temiz = {}
    for k in ("ne_yapar", "kime", "farki", "gorsel_dunyasi", "gorselde_olmamali"):
        temiz[k] = _str(cevap.get(k))[:400]
    for k in ("sunulanlar", "kanitlanmis_bilgiler", "stok_terimleri"):
        temiz[k] = [_str(x)[:120] for x in (cevap.get(k) or []) if _str(x)][:8]
    temiz["b2b"] = bool(cevap.get("b2b"))
    temiz.update({"_imza": imza, "tarih": datetime.now().isoformat(timespec="seconds"), "site_okundu": bool(kaynak)})
    YOL.parent.mkdir(parents=True, exist_ok=True)
    YOL.write_text(json.dumps(temiz, ensure_ascii=False, indent=2), encoding="utf-8")
    return temiz


def _str(x):
    if isinstance(x, list):
        return "; ".join(_str(y) for y in x if y)
    return str(x or "").strip()


def istem_ozeti():
    """Tum ajan istemlerine eklenen gercekler + uydurma yasagi."""
    o = ozet()
    satirlar = ["\nBUSINESS FACTS (the only facts you may state about this business):",
                f"- What it does: {o.get('ne_yapar') or musteri.tanim()}"]
    if o.get("sunulanlar"):
        satirlar.append(f"- Offers: {', '.join(o['sunulanlar'])}")
    if o.get("kime"):
        satirlar.append(f"- Customers: {o['kime']}")
    if o.get("farki"):
        satirlar.append(f"- Difference: {o['farki']}")
    if o.get("kanitlanmis_bilgiler"):
        satirlar.append(f"- Verified facts: {'; '.join(o['kanitlanmis_bilgiler'])}")
    satirlar.append("HONESTY RULES: never invent customers, case studies, testimonials, reviews, statistics, "
                    "percentages, follower counts, awards, prices or results. If a post needs an example, make it "
                    "clearly hypothetical ('Imagine a bakery that...') or give a practical tip instead.")
    if o.get("gorsel_dunyasi"):
        satirlar.append(f"VISUALS must show: {o['gorsel_dunyasi']}")
    if o.get("gorselde_olmamali"):
        satirlar.append(f"VISUALS must NOT show: {o['gorselde_olmamali']}")
    return "\n".join(satirlar) + "\n"
