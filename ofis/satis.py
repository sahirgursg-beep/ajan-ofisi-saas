"""Satis baglantisi: satis ekibi telefondan "sosyal medyadan gelen musteri" kaydi girer.
Boylece hangi paylasimin gercekten musteri/satis getirdigi gorunur; ajanlar begeniye degil satisa gore ogrenir.

veri/satislar.json: [{"id","zaman","satici","kaynak","urun","urun_url","kategori","durum","tutar","not","klasor"}]
durum: "soru" (bilgi istedi) | "ilgili" (showroom'a geldi / teklif) | "satildi"
"""
import json
import re
import uuid
from datetime import datetime, timedelta

from .ayarlar import KOK, VERI, CIKTI

YOL = VERI / "satislar.json"
KAYNAKLAR = {"instagram": "Instagram", "facebook": "Facebook", "whatsapp": "WhatsApp (sosyal medyadan)",
             "telefon": "Telefon (gönderiyi görüp)", "ziyaret": "Showroom ziyareti (gönderiyi görüp)"}
DURUMLAR = {"soru": "Bilgi istedi", "ilgili": "Showroom'a geldi / teklif", "satildi": "Satıldı"}


def _oku():
    try:
        return json.loads(YOL.read_text(encoding="utf-8"))
    except Exception:
        return []


def _yaz(d):
    YOL.parent.mkdir(parents=True, exist_ok=True)
    YOL.write_text(json.dumps(d[-3000:], ensure_ascii=False, indent=2), encoding="utf-8")


def _katalog():
    out = {}
    for dosya in ("urunler.json", "tum_urunler.json"):
        try:
            for u in json.loads((VERI / dosya).read_text(encoding="utf-8")):
                if u.get("ad") and u.get("url"):
                    out.setdefault(u["url"], u)
        except Exception:
            continue
    return list(out.values())


def son_paylasilanlar(gun=30):
    """Formda ilk sirada gosterilecek: son paylasilan urunler (yeniden eskiye)."""
    from . import yayin
    sinir = (datetime.now() - timedelta(days=gun)).strftime("%Y-%m-%d")
    out, gorulen = [], set()
    for x in yayin.liste(120):
        m = x["meta"]
        if x["yayin"].get("durum") not in ("yayinlandi", "kismen", "onaylandi"):
            continue
        if (m.get("plan_gunu") or m.get("tarih", ""))[:10] < sinir:
            continue
        u = m["urun"]
        if u.get("url") in gorulen:
            continue
        gorulen.add(u.get("url"))
        out.append({"ad": u["ad"], "url": u.get("url"), "kategori": (u.get("kategori") or "").split(">")[-1].strip(),
                    "klasor": x["klasor"], "gorsel": f"/cikti/{x['klasor']}/post_1080x1350.jpg"})
    return out[:24]


def ara(sorgu, limit=15):
    q = [w for w in re.findall(r"\w+", str(sorgu).lower()) if len(w) >= 2]
    if not q:
        return []
    out = []
    for u in _katalog():
        ad = u["ad"].lower()
        if all(w in ad for w in q):
            out.append({"ad": u["ad"], "url": u["url"], "kategori": (u.get("kategori") or "").split(">")[-1].strip()})
            if len(out) >= limit:
                break
    return out


def _icerik_bul(url, ad):
    """Bu urunun son 45 gundeki yayinlanmis icerigi (satisi o icerige baglamak icin)."""
    from . import yayin
    sinir = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    for x in yayin.liste(150):
        u = x["meta"]["urun"]
        if (url and u.get("url") == url) or (ad and u.get("ad", "").lower() == str(ad).lower()):
            if x["yayin"].get("durum") in ("yayinlandi", "kismen") and \
                    (x["meta"].get("plan_gunu") or x["meta"].get("tarih", ""))[:10] >= sinir:
                return x["klasor"]
    return None


def kaydet(veri):
    kaynak = veri.get("kaynak") if veri.get("kaynak") in KAYNAKLAR else "instagram"
    durum = veri.get("durum") if veri.get("durum") in DURUMLAR else "soru"
    urun = re.sub(r"\s+", " ", str(veri.get("urun") or "")).strip()[:120]
    if not urun:
        raise ValueError("Ürün adı gerekli")
    url = str(veri.get("urun_url") or "")[:300]
    kat = str(veri.get("kategori") or "")[:80]
    if not kat:
        u = next((u for u in _katalog() if u["url"] == url or u["ad"].lower() == urun.lower()), None)
        kat = (u.get("kategori") or "").split(">")[-1].strip() if u else ""
    tutar = re.sub(r"[^\d]", "", str(veri.get("tutar") or ""))
    k = {"id": uuid.uuid4().hex[:8], "zaman": datetime.now().strftime("%Y-%m-%d %H:%M"),
         "satici": re.sub(r"\s+", " ", str(veri.get("satici") or "")).strip()[:40], "kaynak": kaynak,
         "urun": urun, "urun_url": url, "kategori": kat, "durum": durum, "tutar": int(tutar) if tutar else None,
         "not": re.sub(r"\s+", " ", str(veri.get("not") or "")).strip()[:300], "klasor": _icerik_bul(url, urun)}
    if not k["kategori"] and k["klasor"]:
        try:
            m = json.loads((CIKTI / k["klasor"] / "meta.json").read_text(encoding="utf-8"))
            k["kategori"] = (m["urun"].get("kategori") or "").split(">")[-1].strip()
        except Exception:
            pass
    d = _oku()
    d.append(k)
    _yaz(d)
    if k["satici"]:
        from . import ofis_ayar
        s = ofis_ayar.oku().get("saticilar") or []
        if k["satici"] not in s:
            ofis_ayar.guncelle(saticilar=(s + [k["satici"]])[-20:])
    if k["klasor"]:
        _icerige_isle(k["klasor"])
    return k


def sil(kid):
    d = _oku()
    k = next((x for x in d if x["id"] == kid), None)
    d = [x for x in d if x["id"] != kid]
    _yaz(d)
    if k and k.get("klasor"):
        _icerige_isle(k["klasor"])
    return {"ok": True}


def _icerige_isle(klasor):
    """Icerigin performans.json'ina 'lead' ve 'satis' sayilarini yazar (analiz bunlari agir sayar)."""
    from . import analiz
    ilgili = [x for x in _oku() if x.get("klasor") == klasor]
    try:
        analiz.performans_kaydet(klasor, {"lead": str(len(ilgili)),
                                          "satis": str(sum(1 for x in ilgili if x["durum"] == "satildi"))})
    except Exception:
        pass


def son(n=50):
    return list(reversed(_oku()))[:n]


def ozet(gun=30):
    sinir = (datetime.now() - timedelta(days=gun)).strftime("%Y-%m-%d")
    d = [x for x in _oku() if x["zaman"] >= sinir]
    say = lambda f: sorted(_sayac(f(x) for x in d if f(x)).items(), key=lambda t: -t[1])
    sat = [x for x in d if x["durum"] == "satildi"]
    return {"gun": gun, "toplam": len(d), "satis": len(sat), "ilgili": sum(1 for x in d if x["durum"] == "ilgili"),
            "ciro": sum(x.get("tutar") or 0 for x in sat), "icerik_kaynakli": sum(1 for x in d if x.get("klasor")),
            "kaynaklar": say(lambda x: KAYNAKLAR.get(x["kaynak"], x["kaynak"])),
            "urunler": say(lambda x: x["urun"])[:8],
            "kategori_satis": sorted(_sayac(x["kategori"] for x in sat if x.get("kategori")).items(), key=lambda t: -t[1]),
            "saticilar": say(lambda x: x.get("satici"))[:8]}


def _sayac(it):
    out = {}
    for v in it:
        out[v] = out.get(v, 0) + 1
    return out


def kategori_agirligi(kategoriler):
    """Son 60 gunde satilan kategoriler planda biraz one cikar (en fazla x1.5)."""
    kat = {k.lower() for k in kategoriler}
    sinir = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    n = sum(1 for x in _oku() if x["durum"] == "satildi" and x["zaman"] >= sinir and (x.get("kategori") or "").lower() in kat)
    return 1.0 + min(0.5, 0.15 * n)


def lan_adresi(port):
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return f"http://{ip}:{port}/"
