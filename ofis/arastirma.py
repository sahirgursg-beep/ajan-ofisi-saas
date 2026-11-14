"""Sektor arastirma ajani: her hafta isletmenin sektorunde neyin ise yaradigini arastirir ve Sanat Yonetmeni,
Pazarlama Uzmani ve Fikir Uretici'ye bir rapor verir.

Kaynaklar (yalnizca okuma, resmi API):
  1) Ornek hesaplar: musterinin rakipleri + yapay zekanin onerdigi aday hesaplar. Her aday Instagram Business
     Discovery ile DOGRULANIR (gercekten var mi, isletme hesabi mi, kac takipci); dogrulanamayan atilir.
     Dogrulanan hesaplar veri/arastirma_hesaplar.json'da birikir (sektorun ornek hesap kutuphanesi).
  2) Hashtag trendleri: sektor hashtaglerinin en cok etkilesim alan gonderileri (Instagram hashtag aramasi;
     Instagram haftada 30 farkli hashtag'e izin verir, biz 3 kullaniriz).
  3) Sektor bilgi bankasi + isletmeye ozel sektor profili.
Ciktisi veri/sektor_raporu.json. Meta bagli degilse yalnizca 3. kaynakla (yapay zeka) rapor yazilir.
"""
import json
from collections import Counter
from datetime import datetime, timedelta

from . import llm, musteri, sektor
from .ayarlar import VERI

RAPOR = VERI / "sektor_raporu.json"
HESAPLAR = VERI / "arastirma_hesaplar.json"
YENILEME_GUN = 7
EN_FAZLA_ADAY = 8


def _oku(yol, varsayilan):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return varsayilan


def rapor():
    return _oku(RAPOR, {})


def eski_mi():
    r = rapor()
    if not r.get("tarih"):
        return True
    try:
        return datetime.fromisoformat(r["tarih"]) < datetime.now() - timedelta(days=YENILEME_GUN)
    except ValueError:
        return True


def _aday_hesaplar(p):
    """Yapay zekadan sektor + ulke icin ornek Instagram isletme hesabi adaylari (dogrulanmamis)."""
    if not llm.hazir():
        return []
    i = musteri.bilgi()
    cevap = llm.sor(
        "You are a social media researcher. Answer ONLY with valid JSON. Only suggest accounts you are confident "
        "exist; they will be verified and unverifiable ones discarded.",
        f"Business: {i.get('ad')} — {p['ad']}" + (f" / {p.get('alt_sektor')}" if p.get("alt_sektor") else "")
        + f"\nCountry/cities: {i.get('ulke') or '-'} / {musteri.sehirler_metni()}\n"
        "List up to 12 public Instagram BUSINESS or CREATOR accounts that are strong examples of social media in this "
        "niche: local leaders first, then regional/global benchmarks with great creative. "
        'Return JSON: {"accounts": ["<username without @>"]}', json_mod=True, sicaklik=0.3)
    return [str(x).strip().lstrip("@").lower() for x in (cevap or {}).get("accounts", []) if str(x).strip()][:12]


def _dogrula(adaylar, gunluk):
    from . import rakip
    out = []
    for k in adaylar:
        try:
            h = rakip._hesap(k)
            if h.get("takipci"):
                out.append(h)
        except Exception as e:
            gunluk(f"@{k} dogrulanamadi: {str(e)[:80]}")
    return out


def _hashtag_trendleri(p, gunluk):
    from . import meta
    a = meta.ayar()
    out = []
    for h in [x.lower().replace(" ", "") for x in p.get("hashtag", [])][:3]:
        try:
            hid = (meta.get("ig_hashtag_search", a["page_token"], user_id=a["ig_id"], q=h).get("data") or [{}])[0].get("id")
            if not hid:
                continue
            medya = meta.get(f"{hid}/top_media", a["page_token"], user_id=a["ig_id"], limit=25,
                             fields="caption,media_type,like_count,comments_count,timestamp").get("data", [])
            for m in medya:
                m["hashtag"] = h
            out += medya
        except Exception as e:
            gunluk(f"#{h} okunamadi: {str(e)[:80]}")
    return out


def gorsel_analiz(hesaplar, gunluk=print):
    """Ornek hesaplarin en cok etkilesim alan paylasimlarina GERCEKTEN bakar (gorme modeli): hangi duzenler,
    tipografi, renkler ve duzenleme tarzi tutuyor. Sanat Yonetmeni gorsel dili secerken bunu kullanir."""
    from . import gorsel_kaynak, gorsel_secici
    adresler = []
    for h in sorted(hesaplar, key=lambda h: -(h.get("ort_begeni") or 0)):
        adresler += [e["gorsel"] for e in h.get("en_iyi", []) if e.get("gorsel")][:2]
    yollar = []
    for a in adresler[:16]:
        try:
            yollar.append(gorsel_kaynak.indir(a))
        except Exception:
            continue
    if len(yollar) < 4:
        return None
    sayfa = gorsel_secici.temas_sayfasi(yollar, VERI / "_ilham.jpg")
    cevap = llm.gor(
        "You are a design researcher at a social media agency. Describe only what you actually see. Answer ONLY with valid JSON.",
        f"These are the best-performing recent posts of leading Instagram accounts in this niche: {sektor.profil().get('ad')}.\n"
        "Extract the concrete, reusable design patterns. Return JSON: "
        '{"duzenler": ["<4 layout patterns, concrete>"], "tipografi": ["<3 typography patterns>"], '
        '"renkler": ["<3 colour approaches with example hex>"], "duzenleme": ["<3 photo/editing styles>"], '
        '"ozet": "<2 sentences: what makes these posts work visually>"}', [sayfa])
    if isinstance(cevap, dict):
        gunluk(f"Ornek hesaplarin {len(yollar)} paylasimi gorsel olarak incelendi")
        return {k: cevap.get(k) for k in ("duzenler", "tipografi", "renkler", "duzenleme", "ozet")}
    return None


def _istatistik(hesaplar, trend):
    tur = Counter()
    for h in hesaplar:
        tur.update(h.get("tur_dagilimi") or {})
    tur.update({"Carousel" if m.get("media_type") == "CAROUSEL_ALBUM" else
                "Reels/Video" if m.get("media_type") == "VIDEO" else "Görsel": 1 for m in trend})
    etk = lambda m: (m.get("like_count") or 0) + 3 * (m.get("comments_count") or 0)
    kancalar = [str(m.get("caption") or "").split("\n")[0][:120] for m in sorted(trend, key=etk, reverse=True)[:12]
                if m.get("caption")]
    for h in hesaplar:
        kancalar += [e["metin"].split("\n")[0][:120] for e in h.get("en_iyi", []) if e.get("metin")]
    return {"format_dagilimi": dict(tur.most_common()), "ornek_kancalar": kancalar[:20],
            "hesap_sayisi": len(hesaplar), "trend_gonderi": len(trend)}


def guncelle(gunluk=print, zorla=False):
    if not zorla and not eski_mi():
        return rapor()
    from . import meta
    p = sektor.profil()
    kutuphane = _oku(HESAPLAR, {"hesaplar": {}})
    hesaplar, trend = [], []
    meta_var = False
    try:
        meta_var = meta.bagli() and bool(meta.ayar().get("ig_id"))
    except Exception:
        pass
    if meta_var:
        from . import ofis_ayar
        bilinen = list(kutuphane["hesaplar"])
        rakipler = [x.lower() for x in (ofis_ayar.oku().get("rakipler") or [])]
        yeni = [k for k in _aday_hesaplar(p) if k not in bilinen and k not in rakipler][:EN_FAZLA_ADAY]
        hedef = list(dict.fromkeys(rakipler + bilinen[:10] + yeni))
        hesaplar = _dogrula(hedef, gunluk)
        for h in hesaplar:
            kutuphane["hesaplar"][h["kullanici"].lower()] = {"takipci": h.get("takipci"), "son": datetime.now().isoformat()[:10]}
        HESAPLAR.write_text(json.dumps(kutuphane, ensure_ascii=False, indent=2), encoding="utf-8")
        trend = _hashtag_trendleri(p, gunluk)
    ist = _istatistik(hesaplar, trend)
    gorsel = None
    try:
        gorsel = gorsel_analiz(hesaplar, gunluk) if hesaplar else None
    except Exception as e:
        gunluk(f"Gorsel analiz yapilamadi: {str(e)[:80]}")
    sentez = None
    if llm.hazir():
        sentez = llm.sor(
            "You are the head of research in a social media agency. Turn data into concrete creative direction. "
            "Answer ONLY with valid JSON.",
            f"{sektor.istem_ozeti()}\nBusiness: {musteri.ad()} in {musteri.sehirler_metni()}\n"
            f"Verified example accounts (followers, format mix, best posts):\n"
            + json.dumps([{k: h.get(k) for k in ("kullanici", "takipci", "tur_dagilimi", "ort_begeni", "en_iyi")}
                          for h in hesaplar][:10], ensure_ascii=False)[:6000]
            + f"\nHashtag trend stats: {json.dumps(ist, ensure_ascii=False)[:3000]}\n"
            + (f"What the top posts of these accounts actually look like (visual analysis): "
               f"{json.dumps(gorsel, ensure_ascii=False)[:2000]}\n" if gorsel else "") + "\n"
            "Write this week's research brief for the art director and copywriter. If data is thin, rely on your "
            "expertise for this niche and say so in 'ozet'. Return JSON: "
            '{"ozet": "<3 sentences, English>", "tutan_formatlar": ["<formats that work now>"], '
            '"kancalar": ["<6 hook patterns that work in this niche>"], '
            '"gorsel_trendler": ["<5 visual/design trends to use: layouts, typography, colour, editing style>"], '
            '"renk_paletleri": [{"ad": "<name>", "renkler": ["#hex", "#hex", "#hex"]}], '
            '"fikirler": ["<10 fresh post ideas for this business this week>"], '
            '"kacin": ["<4 things to avoid>"], "en_iyi_saatler": ["<HH:MM local>"]}',
            json_mod=True, sicaklik=0.6)
    r = {"tarih": datetime.now().isoformat(timespec="minutes"), "sektor": p.get("anahtar"),
         "kaynak": "meta+yapay_zeka" if meta_var else ("yapay_zeka" if sentez else "bilgi_bankasi"),
         "istatistik": ist, "ornek_hesaplar": [h["kullanici"] for h in hesaplar], "gorsel_analiz": gorsel}
    if isinstance(sentez, dict):
        r.update({k: sentez.get(k) for k in ("ozet", "tutan_formatlar", "kancalar", "gorsel_trendler",
                                             "renk_paletleri", "fikirler", "kacin", "en_iyi_saatler")})
    else:
        r.update({"ozet": f"Base knowledge for {p['ad']}.", "kancalar": p.get("kancalar", []),
                  "gorsel_trendler": [p.get("gorsel", "")], "fikirler": [sektor.doldur(f) for f in p.get("fikirler", [])]})
    RAPOR.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    gunluk(f"Sektor raporu hazir ({r['kaynak']}, {len(hesaplar)} ornek hesap, {len(trend)} trend gonderi)")
    return r


def istem_ozeti():
    r = rapor()
    if not r.get("ozet"):
        return ""
    k = lambda a, n: "; ".join(str(x) for x in (r.get(a) or [])[:n])
    s = f"\nThis week's sector research: {r['ozet']}\n"
    if r.get("gorsel_trendler"):
        s += f"Visual trends to use: {k('gorsel_trendler', 5)}\n"
    if r.get("tutan_formatlar"):
        s += f"Formats working now: {k('tutan_formatlar', 4)}\n"
    if r.get("kancalar"):
        s += f"Hook patterns: {k('kancalar', 5)}\n"
    if r.get("kacin"):
        s += f"Avoid: {k('kacin', 4)}\n"
    g = r.get("gorsel_analiz") or {}
    if g.get("ozet"):
        s += (f"Observed in the top posts of leading accounts in this niche: {g['ozet']} Layouts: "
              + "; ".join(str(x) for x in (g.get("duzenler") or [])[:4]) + ". Typography: "
              + "; ".join(str(x) for x in (g.get("tipografi") or [])[:3]) + "\n")
    if r.get("renk_paletleri"):
        s += "Trending palettes: " + "; ".join(f"{p.get('ad')} {' '.join(p.get('renkler') or [])}"
                                               for p in r["renk_paletleri"][:3] if isinstance(p, dict)) + "\n"
    return s
