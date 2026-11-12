"""Performans Analisti'nin beyni.

Her gunun ciktisi icin cikti/<klasor>/meta.json yazilir (urun, kategori, tasarim tarifi, tema...).
Kullanici ofis ekranindan puan (1-5 yildiz: post/story/reels) ve/veya gercek rakamlar
(goruntulenme, begeni, kaydetme, mesaj) girer -> cikti/<klasor>/performans.json
Analist bunlardan "kitlemiz neyi seviyor" ogrenimlerini cikarir -> veri/ogrenimler.json
Meta (Instagram) baglandiginda rakamlar otomatik dolacak; analiz ayni kalir.
"""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .ayarlar import KOK, VERI, CIKTI

CIKTI = CIKTI
OGRENIM = VERI / "ogrenimler.json"
ADLAR = {"duzen": "düzen", "fontlar": "font", "motif": "motif", "fiyat_stili": "fiyat stili", "banner": "banner",
         "palet_ton": "renk tonu", "ana_kategori": "kategori", "alt_kategori": "alt kategori", "tema": "tema",
         "kanca_boyu": "kanca uzunluğu", "indirim": "indirim",
         "format": "içerik formatı", "reels_format": "Reels formatı"}


# ---------------- kayit ----------------
def meta_yaz(klasor, urun, tarif, tema, taslak, plan_gunu=None):
    from .sanat import _parlaklik
    t = tarif if isinstance(tarif, dict) else {"isim": str(tarif)}
    kat = [p.strip() for p in urun.get("kategori", "").split(">") if p.strip()]
    meta = {
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "plan_gunu": plan_gunu,
        "urun": {"ad": urun["ad"], "url": urun.get("url"), "kategori": urun.get("kategori"),
                 "fiyat_metni": urun.get("fiyat_metni"), "indirim_yuzde": urun.get("indirim_yuzde") or 0},
        "tema": tema, "kanca": taslak.get("hook", ""), "baslik": taslak.get("headline", ""),
        "tarif": t,
        "ozellikler": {
            "duzen": t.get("duzen"), "fontlar": t.get("fontlar"), "motif": t.get("motif"),
            "fiyat_stili": t.get("fiyat_stili"), "banner": "var" if t.get("banner") else "yok",
            "palet_ton": ("koyu" if _parlaklik(t["palet"]["zemin"]) < 0.5 else "acik") if t.get("palet") else None,
            "ana_kategori": kat[0] if kat else None, "alt_kategori": kat[-1] if kat else None,
            "tema": tema, "kanca_boyu": "kisa" if len(taslak.get("hook", "").split()) <= 4 else "uzun",
            "indirim": "var" if (urun.get("indirim_yuzde") or 0) >= 5 else "yok",
        },
    }
    (Path(klasor) / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def performans_kaydet(klasor_adi, veri):
    """veri: {"post": 1-5, "story": 1-5, "reels": 1-5, "goruntulenme": n, "begeni": n, "kaydetme": n, "mesaj": n, "not": ""}"""
    k = CIKTI / Path(klasor_adi).name
    if not k.is_dir():
        raise FileNotFoundError(klasor_adi)
    yol = k / "performans.json"
    eski = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    for a, v in veri.items():
        if a in ("post", "story", "reels"):
            eski[a] = max(1, min(5, int(v))) if v not in (None, "", 0, "0") else eski.pop(a, None) and None
        elif a in ("goruntulenme", "begeni", "kaydetme", "mesaj", "paylasim", "yorum", "soru", "lead", "satis"):
            eski[a] = int(v) if str(v).strip().isdigit() else eski.get(a)
        elif a == "not":
            eski[a] = str(v)[:300]
    eski = {a: v for a, v in eski.items() if v is not None}
    eski["guncelleme"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    yol.write_text(json.dumps(eski, ensure_ascii=False, indent=2), encoding="utf-8")
    return eski


def ciktilar(n=40):
    if not CIKTI.exists():
        return []
    out = []
    for k in sorted([d for d in CIKTI.iterdir() if d.is_dir() and (d / "meta.json").exists()], reverse=True)[:n]:
        meta = json.loads((k / "meta.json").read_text(encoding="utf-8"))
        perf = json.loads((k / "performans.json").read_text(encoding="utf-8")) if (k / "performans.json").exists() else {}
        out.append({"klasor": k.name, "meta": meta, "performans": perf,
                    "dosyalar": sorted(f.name for f in k.iterdir() if f.suffix in (".jpg", ".mp4"))})
    return out


# ---------------- analiz ----------------
def _skorla(kayitlar):
    """Her kayda 1-5 arasi tek bir skor verir. Yildizlar + (varsa) etkilesim orani."""
    oranlar = []
    for k in kayitlar:
        p = k["performans"]
        if p.get("goruntulenme"):
            er = (p.get("begeni", 0) + 2 * p.get("kaydetme", 0) + 3 * p.get("mesaj", 0) + 2 * p.get("paylasim", 0)
                  + 2 * p.get("yorum", 0) + 3 * p.get("soru", 0) + 15 * p.get("lead", 0) + 60 * p.get("satis", 0)) \
                 / max(1, p["goruntulenme"]) * 100
            k["_er"] = er
            oranlar.append(er)
    oranlar.sort()
    for k in kayitlar:
        p, parcalar = k["performans"], []
        yildiz = [p[a] for a in ("post", "story", "reels") if p.get(a)]
        if yildiz:
            parcalar.append(sum(yildiz) / len(yildiz))
        if "_er" in k and len(oranlar) >= 2:   # gercek rakamlar: kendi icinde siralamaya gore 1-5
            sira = oranlar.index(k["_er"]) / (len(oranlar) - 1)
            parcalar.append(1 + 4 * sira)
            parcalar.append(1 + 4 * sira)        # gercek veri yildizdan daha agir basar
        k["_skor"] = sum(parcalar) / len(parcalar) if parcalar else None
    return [k for k in kayitlar if k["_skor"] is not None]


def analiz_et():
    kayitlar = _skorla(ciktilar(200))
    sonuc = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "n": len(kayitlar),
             "tercih": [], "kacin": [], "kategori_puan": {}, "reels_ort": None, "en_iyi": None, "en_zayif": None}
    if not kayitlar:
        return sonuc
    genel = sum(k["_skor"] for k in kayitlar) / len(kayitlar)
    sonuc["genel_ort"] = round(genel, 2)
    gruplar = defaultdict(list)
    for k in kayitlar:
        for alan, deger in (k["meta"].get("ozellikler") or {}).items():
            if deger:
                gruplar[(alan, deger)].append(k["_skor"])
    satirlar = []
    for (alan, deger), skorlar in gruplar.items():
        if len(skorlar) >= 2:
            fark = sum(skorlar) / len(skorlar) - genel
            satirlar.append({"alan": alan, "deger": deger, "n": len(skorlar), "ort": round(sum(skorlar) / len(skorlar), 2),
                             "fark": round(fark, 2)})
    satirlar.sort(key=lambda s: s["fark"], reverse=True)
    sonuc["tercih"] = [s for s in satirlar if s["fark"] >= 0.3][:6]
    sonuc["kacin"] = [s for s in reversed(satirlar) if s["fark"] <= -0.3][:6]
    sonuc["kategori_puan"] = {s["deger"]: s["ort"] for s in satirlar if s["alan"] in ("ana_kategori", "alt_kategori")}
    reels = [k["performans"]["reels"] for k in kayitlar if k["performans"].get("reels")]
    sonuc["reels_ort"] = round(sum(reels) / len(reels), 2) if reels else None
    en = max(kayitlar, key=lambda k: k["_skor"])
    ez = min(kayitlar, key=lambda k: k["_skor"])
    sonuc["en_iyi"] = {"klasor": en["klasor"], "urun": en["meta"]["urun"]["ad"], "skor": round(en["_skor"], 2),
                       "tarif": en["meta"]["tarif"].get("isim")}
    sonuc["en_zayif"] = {"klasor": ez["klasor"], "urun": ez["meta"]["urun"]["ad"], "skor": round(ez["_skor"], 2),
                         "tarif": ez["meta"]["tarif"].get("isim")}
    OGRENIM.parent.mkdir(parents=True, exist_ok=True)
    OGRENIM.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
    return sonuc


def ogrenimler():
    try:
        return json.loads(OGRENIM.read_text(encoding="utf-8"))
    except Exception:
        return {}


def istem_ozeti():
    """Diger ajanlarin istemine eklenecek kisa ingilizce ozet (yoksa bos)."""
    o = ogrenimler()
    if not o.get("n"):
        return ""
    f = lambda xs: ", ".join(f"{s['alan']}={s['deger']}" for s in xs) or "none yet"
    return (f"Audience performance learnings from {o['n']} rated posts: PREFER {f(o.get('tercih', []))}; "
            f"AVOID {f(o.get('kacin', []))}.")


def ozellik_agirligi(alan, deger):
    """Ogrenimlere gore 0.5 (kacin) - 2.0 (tercih) arasi agirlik."""
    o = ogrenimler()
    for s in o.get("tercih", []):
        if s["alan"] == alan and s["deger"] == deger:
            return 1 + min(1.0, s["fark"])
    for s in o.get("kacin", []):
        if s["alan"] == alan and s["deger"] == deger:
            return max(0.5, 1 + s["fark"] / 2)
    return 1.0
