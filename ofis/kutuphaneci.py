"""Kutuphaneci: platformun ortak yaratici kutuphanesini her hafta kendi kendine buyutur ve ayiklar.

Tum musteriler ayni kutuphaneyi kullanir; isci her calismadan sonra degisenleri depoya yazar (saas/kutuphane.py).
  * Muzik : her ruh haline yeni lisansli (CC0 / CC BY) parcalar, musterilerin sektorlerine gore yeni arama
            sorgulari; begenilmeyen ve tavani asan parcalar emekliye ayrilir.
  * Font  : Google Fonts katalogundan yeni baslik+govde ciftleri (Sanat Yonetmeni'nin kelime haznesi); musterilerin
            yazdigi her alfabe (Arapca, Kiril...) icin yeterli cift; kotu sonuc veren eklenmis ciftler emekli.
  * Ogrenim: saas tarafi tum musterilerin tepkilerini ogrenim/ortak.json'a derler; ajanlar secimlerini buna gore
            agirliklandirir (analiz.ozellik_agirligi, muzik.sec).
Kullanim: python -m ofis.kutuphaneci   (AJAN_PAYLASIK_KOK ortak klasoru gosterir)
"""
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

from .ayarlar import PAYLASIK
from . import fontlar, llm, muzik

RAPOR = PAYLASIK / "kutuphane_rapor.json"
KATALOG_URL = "https://fonts.google.com/metadata/fonts"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
HAFTALIK_FONT = 3          # haftada en fazla yeni cift
ALFABE_EN_AZ = 3           # musterilerin kullandigi her alfabe icin en az bu kadar cift


def _oku(yol, varsayilan):
    try:
        return json.loads(Path(yol).read_text(encoding="utf-8"))
    except Exception:
        return varsayilan


def _yaz(yol, veri):
    Path(yol).parent.mkdir(parents=True, exist_ok=True)
    Path(yol).write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def platform_ozeti():
    """saas tarafinin ortak.json'a yazdigi: hangi sektorler, diller var (musteri kimligi yok)."""
    return (_oku(muzik.ORTAK_OGRENIM, {}) or {}).get("platform") or {}


# ---------------------------------------------------------------- muzik
def muzik_buyut(gunluk=print, yeni_ek=3):
    p = platform_ozeti()
    yeni_sorgu = {}
    if llm.hazir():
        mevcut = muzik.sorgular()
        cevap = llm.sor(
            "You curate royalty-free background music for short social media videos (Reels/TikTok) of small "
            "businesses. Answer ONLY with valid JSON.",
            f"Businesses on the platform by sector: {p.get('sektorler') or 'mixed'}. Content languages: "
            f"{p.get('diller') or 'mixed'}.\nCurrent search queries per mood: {json.dumps(mevcut, ensure_ascii=False)}\n"
            "Suggest 2 NEW short search queries (2-3 words, English, genre/instrument/mood words that work on a "
            "Creative Commons music search) for EACH mood, adding variety the current list lacks, fitting these "
            "businesses and regions. No artist or song names.\n"
            'Return JSON: {"sakin": ["..",".."], "enerjik": ["..",".."], "festival": ["..",".."]}',
            json_mod=True, sicaklik=0.9)
        if isinstance(cevap, dict):
            for ruh in mevcut:
                for q in (cevap.get(ruh) or [])[:2]:
                    q = re.sub(r"[^a-z0-9 &-]", "", str(q).lower()).strip()[:40]
                    if q and q not in mevcut[ruh] and len(q.split()) <= 4:
                        try:
                            if sum(1 for r in muzik._ara(q) if muzik._lisans_uygun(r)) >= 3:   # gercekten sonuc var mi
                                yeni_sorgu.setdefault(ruh, []).append(q)
                        except Exception:
                            pass
    if yeni_sorgu:
        kayit = _oku(muzik.SORGU_DOSYA, {})
        for ruh, qs in yeni_sorgu.items():
            kayit[ruh] = (kayit.get(ruh, []) + qs)[-40:]
        _yaz(muzik.SORGU_DOSYA, kayit)
        gunluk(f"Yeni muzik sorgulari: {yeni_sorgu}")
    eklenen = muzik.guncelle(gunluk=gunluk, yeni_ek=yeni_ek)
    cikan = muzik.emekliye_ayir(gunluk=gunluk)
    aktif = [k for k in muzik.kutuphane() if not k.get("emekli")]
    return {"eklenen": eklenen, "emekli": cikan, "toplam": len(aktif), "yeni_sorgu": yeni_sorgu,
            "ruh": {r: sum(1 for k in aktif if k["ruh"] == r) for r in muzik.sorgular()}}


# ---------------------------------------------------------------- fontlar
def katalog():
    r = requests.get(KATALOG_URL, headers=UA, timeout=60)
    r.raise_for_status()
    metin = r.text[r.text.index("{"):]                   # basta ")]}'" korumasi var
    return {f["family"]: f for f in json.loads(metin).get("familyMetadataList", [])}


def _agirliklar(aile):
    return sorted({int(k) for k in (aile.get("fonts") or {}) if k.isdigit()}) or [400]


def google_spec(aile, istenen):
    """Ailede gercekten olan agirliklardan css2 ifadesi (olmayan agirlik tum istegi bozar)."""
    var = _agirliklar(aile)
    sec = sorted({min(var, key=lambda w: abs(w - x)) for x in (400, 600, istenen)})
    ad = aile["family"].replace(" ", "+")
    return ad if sec == [400] and len(var) == 1 else f"{ad}:wght@{';'.join(map(str, sec))}"


def _css_calisiyor(spec):
    try:
        r = requests.get("https://fonts.googleapis.com/css2?family=" + spec + "&display=swap", headers=UA, timeout=20)
        return r.status_code == 200 and "@font-face" in r.text
    except Exception:
        return False


def _gecerli_cift(c, kat, kullanilan_anahtar):
    try:
        bf, gf = kat[str(c["bf"])], kat[str(c["gf"])]
    except KeyError:
        return None
    if bf["family"] == gf["family"] and bf.get("category") == "Display":
        return None
    anahtar = re.sub(r"[^a-z0-9_]", "", str(c.get("anahtar") or bf["family"]).lower().replace(" ", "_"))[:24]
    while not anahtar or anahtar in kullanilan_anahtar:
        anahtar = (anahtar or "cift") + str(random.randint(2, 99))
    bw = min(_agirliklar(bf), key=lambda w: abs(w - int(c.get("bw") or 700)))
    bt = "uppercase" if str(c.get("bt")) == "uppercase" else "none"
    bls = str(c.get("bls") or "0")
    bls = bls if re.fullmatch(r"-?\.?\d*\.?\d+(em)?", bls) else "0"
    try:
        bo = max(0.75, min(1.3, float(c.get("bo") or 1)))
    except (TypeError, ValueError):
        bo = 1
    alfabe = sorted(set(bf.get("subsets") or ["latin"]) & set(gf.get("subsets") or ["latin"]) - {"menu"}) or ["latin"]
    yedek = fontlar.YEDEK_SERIF if bf.get("category") == "Serif" else fontlar.YEDEK_SANS
    return anahtar, {"bf": bf["family"], "bf_yedek": yedek, "gf": gf["family"], "bw": bw, "bt": bt, "bls": bls,
                     "bo": bo, "his": str(c.get("his") or "")[:80], "uygun": str(c.get("uygun") or "")[:90],
                     "alfabe": alfabe, "eklendi": datetime.now().strftime("%Y-%m-%d")}


def _alfabe_icin_cift(alf, kat, kullanilan):
    """Yapay zekasiz yedek: o alfabeyi destekleyen en populer baslik + govde ailesi."""
    uygun = sorted([f for f in kat.values() if alf in (f.get("subsets") or [])], key=lambda f: f.get("popularity", 9999))
    baslik = [f for f in uygun if f.get("category") in ("Display", "Serif", "Sans Serif") and f["family"] not in kullanilan]
    govde = [f for f in uygun if f.get("category") == "Sans Serif"]
    if not baslik or not govde:
        return None
    b = baslik[0]
    g = next((f for f in govde if f["family"] != b["family"]), govde[0])
    return {"anahtar": f"{alf}_{b['family']}", "bf": b["family"], "gf": g["family"], "bw": 700, "bt": "none",
            "bls": "0", "bo": 1, "his": f"popular {b.get('category', '').lower()} for {alf} script", "uygun": "all sectors"}


def font_buyut(gunluk=print, kat=None):
    kat = kat or katalog()
    ek = _oku(fontlar.EK_DOSYA, {"ciftler": {}, "google": {}})
    ek.setdefault("ciftler", {}), ek.setdefault("google", {})
    p = platform_ozeti()
    kullanilan = {c["bf"] for c in fontlar.CIFTLER.values()} | {c["gf"] for c in fontlar.CIFTLER.values()}
    oneriler = []
    # 1) Musterilerin yazdigi her alfabe icin yeterli cift (Arapca musteri Latin font ile kalmasin)
    for kod in (p.get("diller") or {}):
        alf = fontlar.alfabe(kod)
        if len([k for k, c in fontlar.CIFTLER.items() if alf in c.get("alfabe", ["latin"])]) < ALFABE_EN_AZ:
            o = _alfabe_icin_cift(alf, kat, kullanilan)
            if o:
                oneriler.append(o)
    # 2) Sanat Yonetmeni'nin kelime haznesini genislet: yapay zeka katalogdan bosluklari dolduran ciftler secer
    if llm.hazir():
        adaylar = sorted([f for f in kat.values() if f["family"] not in kullanilan and f.get("category") != "Monospace"
                          and not any(s.startswith(("chinese", "japanese", "korean")) for s in f.get("subsets") or [])],
                         key=lambda f: f.get("popularity", 9999))[:160]
        liste = "; ".join(f'{f["family"]} ({f.get("category")}, {"/".join(s for s in f.get("subsets", []) if s not in ("menu", "latin-ext"))})'
                          for f in adaylar)
        cevap = llm.sor(
            "You are the type director of a top advertising agency building a font library for social media ads "
            "of small businesses worldwide. Answer ONLY with valid JSON.",
            f"Our current headline+body pairs:\n" + "\n".join(f"- {k}: {v}" for k, v in fontlar.aciklama().items())
            + f"\nBusinesses on the platform by sector: {p.get('sektorler') or 'mixed'}; languages: {p.get('diller') or 'mixed'}.\n"
            f"Available Google Fonts not used yet (family, category, scripts): {liste}\n\n"
            f"Propose {HAFTALIK_FONT} NEW pairs that fill gaps in our library (a mood, a sector or a script we cover "
            "poorly). Headline font from the list; body font from the list or a well-known readable Google sans. "
            "Each pair must feel distinctly different from the existing ones.\n"
            'Return JSON: {"ciftler": [{"anahtar": "<short_snake_case>", "bf": "<headline family>", "gf": "<body family>", '
            '"bw": <headline weight>, "bt": "none" or "uppercase", "bls": "<letter-spacing like .02em or 0>", '
            '"bo": <size factor 0.8-1.25, smaller for wide fonts>, "his": "<what it says, agency language>", '
            '"uygun": "<sectors/moods it suits>"}]}',
            json_mod=True, sicaklik=0.8)
        if isinstance(cevap, dict):
            oneriler += [c for c in (cevap.get("ciftler") or []) if isinstance(c, dict)][:HAFTALIK_FONT]
    eklenen = []
    anahtarlar = set(fontlar.CIFTLER) | set(ek["ciftler"])
    for o in oneriler:
        g = _gecerli_cift(o, kat, anahtarlar)
        if not g:
            continue
        anahtar, cift = g
        specler = {a: ek["google"].get(a) or fontlar.GOOGLE.get(a) or google_spec(kat[a], cift["bw"] if a == cift["bf"] else 600)
                   for a in (cift["bf"], cift["gf"])}
        if not all(_css_calisiyor(s) for s in specler.values()):
            gunluk(f"Font cifti atlandi (Google Fonts yanit vermedi): {cift['bf']} + {cift['gf']}")
            continue
        ek["ciftler"][anahtar] = cift
        for a, s in specler.items():
            if a not in fontlar.GOOGLE:
                ek["google"][a] = s
        anahtarlar.add(anahtar)
        eklenen.append(f"{anahtar}: {cift['bf']} + {cift['gf']} ({'/'.join(cift['alfabe'])})")
        gunluk(f"🔤 Yeni font cifti: {eklenen[-1]} — {cift['his']}")
    # 3) Eklenmis ciftlerden musterilerin surekli reddettikleri emekli olur (elle yazilmis cekirdek kalir)
    ozellik = ((_oku(muzik.ORTAK_OGRENIM, {}) or {}).get("ozellik") or {}).get("fontlar") or {}
    emekli = []
    for k, c in ek["ciftler"].items():
        q = ozellik.get(k) or {}
        if not c.get("emekli") and q.get("n", 0) >= 5 and q.get("skor", 0) < -0.5:
            c["emekli"] = datetime.now().strftime("%Y-%m-%d")
            emekli.append(k)
    _yaz(fontlar.EK_DOSYA, ek)
    return {"eklenen": eklenen, "emekli": emekli,
            "toplam": len(fontlar.CIFTLER) + len([k for k in ek["ciftler"] if k not in fontlar.CIFTLER and not ek["ciftler"][k].get("emekli")])}


# ---------------------------------------------------------------- hepsi
def calistir(gunluk=print):
    rapor = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M")}
    for ad, is_ in (("muzik", muzik_buyut), ("font", font_buyut)):
        try:
            rapor[ad] = is_(gunluk=gunluk)
        except Exception as e:
            rapor[ad] = {"hata": f"{type(e).__name__}: {str(e)[:160]}"}
            gunluk(f"Kutuphaneci {ad}: {rapor[ad]['hata']}")
    gecmis = _oku(RAPOR, {}).get("gecmis", [])
    rapor["gecmis"] = (gecmis + [{k: v for k, v in rapor.items() if k != "gecmis"}])[-12:]
    _yaz(RAPOR, rapor)
    return rapor


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = calistir()
    print("KUTUPHANECI " + json.dumps({k: v for k, v in r.items() if k != "gecmis"}, ensure_ascii=False))
