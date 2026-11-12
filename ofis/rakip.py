"""Rakip / ilham takibi: Instagram'in resmi Business Discovery ozelligiyle diger ISLETME hesaplarinin herkese acik
paylasimlarini ve rakamlarini okur (sadece okuma; hicbir etkilesim yapmaz).
Sonuc: veri/rakip.json (son) + kisa ozet Sanat Yonetmeni ve Pazarlama Uzmani'na."""
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from .ayarlar import KOK, VERI

YOL = VERI / "rakip.json"
TUR = {"IMAGE": "Görsel", "VIDEO": "Reels/Video", "CAROUSEL_ALBUM": "Carousel"}


def _hesap(kullanici):
    from . import meta
    a = meta.ayar()
    alan = (f"business_discovery.username({kullanici})"
            "{username,name,followers_count,media_count,"
            "media.limit(18){caption,like_count,comments_count,media_type,media_product_type,timestamp,permalink,media_url,thumbnail_url}}")
    d = meta.get(a["ig_id"], a["page_token"], fields=alan).get("business_discovery") or {}
    medya = (d.get("media") or {}).get("data", [])
    simdi = datetime.now(timezone.utc)
    son30 = [m for m in medya if m.get("timestamp") and
             datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) > simdi - timedelta(days=30)]
    etk = lambda m: (m.get("like_count") or 0) + 2 * (m.get("comments_count") or 0)
    en_iyi = sorted(medya, key=etk, reverse=True)[:3]
    tur = Counter(("REELS" if m.get("media_product_type") == "REELS" else m.get("media_type")) for m in son30)
    saatler = Counter((datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")).hour + 1) % 24 for m in son30)
    return {"kullanici": d.get("username", kullanici), "ad": d.get("name"), "takipci": d.get("followers_count"),
            "gonderi": d.get("media_count"), "son30_gonderi": len(son30),
            "ort_begeni": round(sum(m.get("like_count") or 0 for m in medya) / max(1, len(medya))),
            "ort_yorum": round(sum(m.get("comments_count") or 0 for m in medya) / max(1, len(medya)), 1),
            "tur_dagilimi": {({"REELS": "Reels"}.get(k) or TUR.get(k, k)): n for k, n in tur.items()},
            "sik_saatler_wat": [h for h, _ in saatler.most_common(3)],
            "en_iyi": [{"link": m.get("permalink"), "begeni": m.get("like_count"), "yorum": m.get("comments_count"),
                        "tur": "Reels" if m.get("media_product_type") == "REELS" else TUR.get(m.get("media_type"), ""),
                        "gorsel": m.get("thumbnail_url") or m.get("media_url"),
                        "metin": (m.get("caption") or "")[:160]} for m in en_iyi]}


def guncelle(gunluk=print):
    from . import meta, ofis_ayar
    if not meta.bagli():
        raise RuntimeError("Meta bağlı değil")
    out = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "hesaplar": [], "hatalar": {}}
    hedefler = list(ofis_ayar.oku().get("rakipler") or [])
    biz = meta.ayar().get("ig_kullanici")
    if biz and biz not in hedefler:
        hedefler = [biz] + hedefler          # kendimizi de ayni olcuyle karsilastir
    for k in hedefler:
        try:
            h = _hesap(k)
            h["biz"] = k == biz
            out["hesaplar"].append(h)
        except Exception as e:
            out["hatalar"][k] = str(e)[:200]
            gunluk(f"@{k} okunamadi: {e}")
    YOL.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def son():
    try:
        return json.loads(YOL.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ozet_satirlari(r):
    s = []
    for h in r.get("hesaplar", []):
        tur = ", ".join(f"{k} {n}" for k, n in sorted(h["tur_dagilimi"].items(), key=lambda t: -t[1]))
        tk = f"{h['takipci']:,}".replace(",", ".") if h.get("takipci") else "-"
        s.append(f"@{h['kullanici']}{' (biz)' if h.get('biz') else ''}: {tk} takipçi, son 30 günde "
                 f"{h['son30_gonderi']} gönderi ({tur or '-'}), ort. {h['ort_begeni']} beğeni")
    return s
