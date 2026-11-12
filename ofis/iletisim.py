"""Iletisim Analisti'nin veri isleri: yorumlari ve DM'leri OKUR, raporlar. Hicbir mesaja/yoruma CEVAP YAZMAZ
(cevaplari gercek satis ekibi ve Meta Business Agent verir).

Cikti: veri/iletisim/rapor.json (son rapor) + veri/iletisim/gecmis.json (gunluk ozet satirlari)
Kullanici adlari kaydedilmez; ornek olarak yalnizca kisa, kisaltilmis mesaj parcalari tutulur.
"""
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .ayarlar import KOK, VERI

KLASOR = VERI / "iletisim"
KONULAR = {
    "fiyat": r"\b(price|how much|hw much|hm+\b|cost|pp\b|pls price|amount|naira|₦|discount|promo)",
    "konum": r"\b(where|location|address|showroom|shop|store|located|visit)",
    "teslimat": r"\b(deliver|delivery|shipping|ship|transport|send to)",
    "odeme": r"\b(installment|instalment|pay small|payment plan|transfer|account number|pos\b|pay)",
    "stok_olcu": r"\b(available|in stock|colou?r|size|dimension|measure|seater|cm\b|inch|other colou?r)",
    "sikayet": r"\b(bad|late|complain|refund|broken|damaged|not happy|disappoint|scam|fake)",
    "begeni": r"(beautiful|nice|love|wow|lovely|gorgeous|amazing|❤|😍|🔥|👏)",
}
ADLAR = {"fiyat": "fiyat sorusu", "konum": "adres / showroom", "teslimat": "teslimat", "odeme": "ödeme / taksit",
         "stok_olcu": "stok / renk / ölçü", "sikayet": "şikâyet", "begeni": "beğeni / iltifat"}


def konular(metin):
    m = (metin or "").lower()
    return [k for k, desen in KONULAR.items() if re.search(desen, m)]


def _kisa(metin, n=110):
    m = re.sub(r"\s+", " ", metin or "").strip()
    m = re.sub(r"\+?\d[\d\s-]{7,}\d", "[numara]", m)        # telefon numaralarini rapora yazma
    return m[:n] + ("…" if len(m) > n else "")


def _zaman(z):
    try:
        return datetime.fromisoformat(str(z).replace("Z", "+00:00").replace("+0000", "+00:00"))
    except Exception:
        return None


def _urun_adlari():
    adlar = []
    for dosya in ("tum_urunler.json", "urunler.json"):
        try:
            for u in json.loads((VERI / dosya).read_text(encoding="utf-8")):
                if u.get("ad"):
                    adlar.append(u["ad"])
        except Exception:
            continue
    return list(dict.fromkeys(adlar))


GENEL = {"sofa", "seater", "chair", "table", "set", "with", "fabric", "leather", "velvet", "bed", "frame", "the",
         "and", "for", "wood", "wooden", "piece", "pcs", "cabinet", "unit", "corner", "dining", "living", "room"}


def _urun_bul(metin, adlar):
    """Mesajda gecen urun: model adi + en az bir kelime daha eslesirse tam urun; sadece model adi -> 'X serisi'."""
    m = set(re.findall(r"[a-z0-9]+", (metin or "").lower()))
    if not m:
        return None
    en_iyi, puan = None, 0
    for ad in adlar:
        kelimeler = [w for w in re.findall(r"[a-z0-9]+", ad.lower()) if len(w) >= 3]
        if not kelimeler or kelimeler[0] in GENEL or len(kelimeler[0]) < 4 or kelimeler[0] not in m:
            continue
        p = 1 + sum(1 for w in kelimeler[1:] if w in m)
        if p > puan:
            en_iyi, puan = ad, p
    if not en_iyi:
        return None
    return en_iyi if puan >= 2 else en_iyi.split(" ")[0] + " serisi"


def topla(gun=14, gunluk=print):
    """Son 'gun' gunde yayinlanan iceriklerin yorumlari + son 24 saatin DM'leri. Doner: rapor (dict)."""
    from . import meta, yayin
    if not meta.bagli():
        raise RuntimeError("Meta bagli degil")
    simdi = datetime.now().astimezone()
    adlar = _urun_adlari()
    rapor = {"tarih": simdi.strftime("%Y-%m-%d %H:%M"), "icerikler": [], "yorum": {}, "dm": {}, "izin_eksik": [],
             "izin_hata": {}}
    konu_say, urun_ilgi, ornek = Counter(), Counter(), {}

    # ---- yorumlar (icerik bazinda) ----
    toplam_y, cevapsiz_y, son24_y = 0, 0, 0
    for x in yayin.liste(120):
        y = x["yayin"]
        if not y.get("sonuc"):
            continue
        z = _zaman(y.get("yayin_zamani") or y.get("zaman") or "")
        if z and z.tzinfo is None:
            z = z.replace(tzinfo=yayin.YEREL)
        if not z or z < simdi - timedelta(days=gun):
            continue
        satir = {"klasor": x["klasor"], "urun": x["meta"]["urun"]["ad"], "format": x["meta"].get("format"),
                 "yorum": 0, "cevapsiz": 0, "soru": 0, "konular": Counter()}
        for h, r in y["sonuc"].items():
            if not r.get("id") or r.get("planli") or r.get("kaldirildi") or h.endswith("story"):
                continue
            try:
                liste = meta.ig_yorumlar(r["id"]) if h.startswith("ig_") else meta.fb_yorumlar(r["id"])
            except Exception as e:
                rapor["izin_eksik"].append("yorumlar")
                rapor["izin_hata"]["yorumlar"] = str(e)[:240]
                gunluk(f"{x['klasor']} {h} yorumlar okunamadi: {e}")
                continue
            for c in liste:
                if c.get("kendimiz"):
                    continue
                satir["yorum"] += 1
                toplam_y += 1
                cz = _zaman(c.get("zaman"))
                if cz and cz > simdi - timedelta(hours=24):
                    son24_y += 1
                if not c.get("cevaplandi"):
                    satir["cevapsiz"] += 1
                    cevapsiz_y += 1
                ks = konular(c.get("metin"))
                for k in ks:
                    satir["konular"][k] += 1
                    konu_say[k] += 1
                    ornek.setdefault(k, [])
                    if len(ornek[k]) < 3:
                        ornek[k].append(_kisa(c.get("metin")))
                if set(ks) & {"fiyat", "konum", "teslimat", "odeme", "stok_olcu"}:
                    satir["soru"] += 1
                    urun_ilgi[satir["urun"]] += 1
        satir["konular"] = dict(satir["konular"])
        rapor["icerikler"].append(satir)
    rapor["yorum"] = {"toplam": toplam_y, "son_24_saat": son24_y, "cevapsiz": cevapsiz_y}

    # ---- DM'ler (Instagram + Messenger), son 24 saat ----
    dm_say, dm_cevapsiz, sureler, dm_konu = 0, 0, [], Counter()
    for platform in ("instagram", "messenger"):
        try:
            konusmalar = meta.konusmalar(platform)
        except Exception as e:
            rapor["izin_eksik"].append(f"dm_{platform}")
            rapor["izin_hata"][f"dm_{platform}"] = str(e)[:240]
            gunluk(f"{platform} mesajlari okunamadi (izin gerekebilir): {e}")
            continue
        for k in konusmalar:
            mesajlar = sorted(k["mesajlar"], key=lambda m: m.get("zaman") or "")
            yeni = [m for m in mesajlar if not m["biz"] and (_zaman(m.get("zaman")) or simdi) > simdi - timedelta(hours=24)]
            if not yeni:
                continue
            dm_say += 1
            if mesajlar and not mesajlar[-1]["biz"]:
                dm_cevapsiz += 1
            for m in yeni:
                for kn in konular(m.get("metin")):
                    dm_konu[kn] += 1
                    konu_say[kn] += 1
                    ornek.setdefault(kn, [])
                    if len(ornek[kn]) < 3:
                        ornek[kn].append(_kisa(m.get("metin")))
                u = _urun_bul(m.get("metin"), adlar)
                if u:
                    urun_ilgi[u] += 1
            # ilk musteri mesajindan sonraki ilk cevabimiza kadar gecen sure
            for i, m in enumerate(mesajlar):
                if not m["biz"]:
                    cevap = next((n for n in mesajlar[i + 1:] if n["biz"]), None)
                    a, b = _zaman(m.get("zaman")), _zaman((cevap or {}).get("zaman"))
                    if a and b:
                        sureler.append((b - a).total_seconds() / 60)
                    break
    sureler.sort()
    rapor["dm"] = {"konusma_24s": dm_say, "cevap_bekleyen": dm_cevapsiz, "konular": dict(dm_konu),
                   "ortanca_cevap_dk": round(sureler[len(sureler) // 2]) if sureler else None}
    rapor["konular"] = dict(konu_say.most_common())
    rapor["ornekler"] = ornek
    rapor["urun_ilgisi"] = urun_ilgi.most_common(8)
    rapor["izin_eksik"] = sorted(set(rapor["izin_eksik"]))
    kaydet(rapor)
    return rapor


def kaydet(rapor):
    KLASOR.mkdir(parents=True, exist_ok=True)
    (KLASOR / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        g = json.loads((KLASOR / "gecmis.json").read_text(encoding="utf-8"))
    except Exception:
        g = {}
    g[rapor["tarih"][:10]] = {"yorum_24s": rapor["yorum"].get("son_24_saat"), "cevapsiz_yorum": rapor["yorum"].get("cevapsiz"),
                              "dm_24s": rapor["dm"].get("konusma_24s"), "dm_bekleyen": rapor["dm"].get("cevap_bekleyen"),
                              "ortanca_cevap_dk": rapor["dm"].get("ortanca_cevap_dk"), "konular": rapor.get("konular")}
    g = dict(sorted(g.items())[-90:])
    (KLASOR / "gecmis.json").write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    # yorumlardaki satin alma sorulari icerigin performansina "soru" olarak islenir (analiz bunu ogrenir)
    from . import analiz
    for s in rapor["icerikler"]:
        if s["yorum"]:
            try:
                analiz.performans_kaydet(s["klasor"], {"soru": str(s["soru"])})
            except Exception:
                pass


def son_rapor():
    try:
        r = json.loads((KLASOR / "rapor.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    try:
        r["gecmis"] = json.loads((KLASOR / "gecmis.json").read_text(encoding="utf-8"))
    except Exception:
        r["gecmis"] = {}
    return r


def ozet_satirlari(r):
    """Insan okunur kisa ozet (Turkce)."""
    s = [f"Son 24 saatte {r['yorum'].get('son_24_saat', 0)} yeni yorum, {r['dm'].get('konusma_24s', 0)} DM konuşması."]
    if r["yorum"].get("cevapsiz"):
        s.append(f"Cevaplanmamış yorum: {r['yorum']['cevapsiz']} (son 14 gün).")
    if r["dm"].get("cevap_bekleyen"):
        s.append(f"Son mesajı müşteriden olan (cevap bekleyen) DM: {r['dm']['cevap_bekleyen']}.")
    if r["dm"].get("ortanca_cevap_dk") is not None:
        s.append(f"DM'lere ortanca ilk cevap süresi: {r['dm']['ortanca_cevap_dk']} dk.")
    if r.get("konular"):
        s.append("En çok konuşulanlar: " + ", ".join(f"{ADLAR.get(k, k)} ({n})" for k, n in list(r["konular"].items())[:4]) + ".")
    if r.get("urun_ilgisi"):
        s.append("En çok sorulan ürünler: " + ", ".join(f"{u} ({n})" for u, n in r["urun_ilgisi"][:4]) + ".")
    ad = {"yorumlar": "yorumlar", "dm_instagram": "Instagram DM", "dm_messenger": "Messenger"}
    for k in r.get("izin_eksik") or []:
        s.append(f"Okunamadı — {ad.get(k, k)}: Meta'nın cevabı “{(r.get('izin_hata') or {}).get(k, 'izin eksik olabilir')}”.")
    return s
