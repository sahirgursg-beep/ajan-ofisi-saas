"""Ortak yaratici kutuphane (muzik, fontlar, ortak ogrenim) - isci tarafi.

* Kalicilik: isci yeniden baslasa da kutuphane kaybolmaz. Dosyalar depoda _paylasilan/ altinda tek tek tutulur;
  manifest.json hangi dosyanin hangi surumde oldugunu bilir. Isci acilista indirir, her isten sonra yalnizca
  degisenleri yukler (Reels uretirken eklenen muzik dahil).
* Ortak ogrenim: tum musterilerin icerik tepkilerinden (yayinlandi / reddedildi / silindi / degisiklik istendi)
  tasarim ozelliklerine ve muzik parcalarina puan; musteri kimligi veya metni yazilmaz, yalnizca sayilar.
* Kutuphaneci: haftada bir (ya da yonetici "simdi" derse) ofis.kutuphaneci alt sureci kutuphaneyi buyutur.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ayar
from .depo import depo

ONEK = "_paylasilan/kutuphane/"
MANIFEST = "_paylasilan/kutuphane/manifest.json"
DURUM = "_paylasilan/kutuphane/durum.json"
KAPSAM = ("muzik/otomatik", "fontlar/aileler", "fontlar/ek_ciftler.json", "ogrenim", "kutuphane_rapor.json")
HAFTA = timedelta(days=7)
GUN = timedelta(days=1)

SINYAL = {"yayinlandi": 1.0, "kismi": 0.5, "reddedildi": -2.0, "kaldirildi": -2.0, "kaldiriliyor": -2.0,
          "revize_isteniyor": -1.0, "revize_edildi": -1.0}


def gunluk(m):
    print(f"{datetime.now():%H:%M:%S} [kutuphane] {m}", flush=True)


# ---------------------------------------------------------------- kalicilik
def _yerel_dosyalar(kok):
    for k in KAPSAM:
        y = kok / k
        if y.is_file():
            yield y
        elif y.is_dir():
            yield from (f for f in y.rglob("*") if f.is_file())


def _ozet(yol):
    h = hashlib.sha1()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()[:16]


def indir(kok, d=None):
    """Acilista: depodaki kutuphaneyi ortak klasore indirir. -> indirilen dosya sayisi"""
    d = d or depo()
    man = d.json_oku(MANIFEST, {}) or {}
    n = 0
    for rel, bilgi in man.items():
        hedef = kok / rel
        if hedef.exists() and hedef.stat().st_size == bilgi.get("b"):
            continue
        try:
            if d.dosya_indir(ONEK + rel, hedef):
                n += 1
        except Exception as e:
            gunluk(f"indirilemedi {rel}: {e}")
    return n


def yukle(kok, d=None):
    """Degisen/yeni dosyalari yukler, kutuphaneden cikanlari depodan siler. -> (yuklenen, silinen)"""
    d = d or depo()
    man = d.json_oku(MANIFEST, {}) or {}
    yeni, yuklenen = {}, 0
    for f in _yerel_dosyalar(kok):
        rel = f.relative_to(kok).as_posix()
        b = f.stat().st_size
        eski = man.get(rel)
        if eski and eski.get("b") == b and eski.get("t") == int(f.stat().st_mtime):
            yeni[rel] = eski
            continue
        h = _ozet(f)
        if not eski or eski.get("h") != h:
            d.dosya_yukle(ONEK + rel, f)
            yuklenen += 1
        yeni[rel] = {"b": b, "h": h, "t": int(f.stat().st_mtime)}
    silinen = 0
    for rel in set(man) - set(yeni):
        try:
            d.dosya_sil(ONEK + rel)
            silinen += 1
        except Exception:
            pass
    if yuklenen or silinen or yeni != man:
        d.json_yaz(MANIFEST, yeni)
    return yuklenen, silinen


# ---------------------------------------------------------------- ortak ogrenim
def _muzik_id(icerik):
    try:
        return json.loads((icerik.get("ekler") or {}).get("muzik.json") or "{}").get("id")
    except Exception:
        return None


def ogrenim_topla(d=None, icerik_sayisi=200):
    """Tum musterilerin tepkilerinden ozellik ve muzik puanlari. Musteri kimligi/metni yazilmaz."""
    d = d or depo()
    genel = defaultdict(lambda: defaultdict(list))
    sektorel = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    muzik = defaultdict(list)
    sektorler, diller = defaultdict(int), defaultdict(int)
    for m in d.musteriler(["deneme", "aktif", "duraklatildi"]):
        i = ((m.get("profil") or {}).get("isletme") or {})
        sektor = i.get("sektor") or ""
        if sektor:
            sektorler[sektor] += 1
        dil = (i.get("dil") or "").split("-")[0]
        if not dil and i.get("ulke_kodu"):
            try:
                from ofis import ulkeler
                dil = (ulkeler.al(i["ulke_kodu"]) or {}).get("dil") or ""
            except Exception:
                dil = ""
        diller[dil or "en"] += 1
        try:
            icerikler = d.icerikler(m["id"], icerik_sayisi)
        except Exception:
            continue
        for ic in icerikler:
            y = ic.get("yayin") or {}
            s = SINYAL.get(y.get("durum"))
            if s is None and y.get("durum") == "onaylandi" and (y.get("onay") or {}).get("kaynak") == "panel":
                s = 1.0                                   # sahibi panelden bizzat onayladi
            if s is None:
                continue
            for alan, deger in ((ic.get("meta") or {}).get("ozellikler") or {}).items():
                if deger and alan not in ("tema", "ana_kategori", "alt_kategori"):
                    genel[alan][str(deger)].append(s)
                    if sektor:
                        sektorel[sektor][alan][str(deger)].append(s)
            mid = _muzik_id(ic)
            if mid:
                muzik[mid].append(s)
    ozet = lambda xs: {"skor": round(sum(xs) / len(xs), 2), "n": len(xs)}
    return {
        "tarih": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "ozellik": {a: {v: ozet(x) for v, x in d_.items()} for a, d_ in genel.items()},
        "sektor": {s: {a: {v: ozet(x) for v, x in d_.items()} for a, d_ in al.items()} for s, al in sektorel.items()},
        "muzik": {k: ozet(x) for k, x in muzik.items()},
        "platform": {"sektorler": dict(sektorler), "diller": dict(diller)},
    }


def ogrenim_yaz(kok, d=None):
    o = ogrenim_topla(d)
    yol = kok / "ogrenim" / "ortak.json"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    return o


# ---------------------------------------------------------------- kutuphaneci
def kutuphaneci_calistir(kok, sure_sn=1500):
    """ofis.kutuphaneci'yi ortak klasor uzerinde ayri surecte calistirir (yapay zeka + indirmeler)."""
    with tempfile.TemporaryDirectory(prefix="kutuphaneci_") as t:
        musteriler = Path(t) / "musteriler"
        shutil.copytree(ayar.KOK / "musteriler" / "_sablon", musteriler / "kutuphaneci")
        ortam = {**os.environ, "AJAN_MUSTERI": "kutuphaneci", "AJAN_MUSTERILER_KOK": str(musteriler),
                 "AJAN_PAYLASIK_KOK": str(kok), "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        for sir in [k for k in ortam if k.startswith(("SUPABASE_", "SAAS_SIFRELEME", "SAAS_IMZA", "SAAS_ZAMANLAYICI",
                                                      "META_APP_SECRET"))]:
            ortam.pop(sir)
        try:
            p = subprocess.run([sys.executable, "-m", "ofis.kutuphaneci"], cwd=str(ayar.KOK), env=ortam,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=sure_sn)
        except subprocess.TimeoutExpired:
            gunluk("Kutuphaneci zaman asimi")
            return None
        for satir in (p.stdout + p.stderr).splitlines()[-40:]:
            gunluk(satir[:300])
        return p.returncode == 0


def gerekirse(kok, d=None, simdi=None):
    """Isci dongusunden cagrilir: gunde bir ortak ogrenim, haftada bir (ya da zorla) Kutuphaneci."""
    d = d or depo()
    simdi = simdi or datetime.now(timezone.utc)
    durum = d.json_oku(DURUM, {}) or {}
    oku = lambda k: datetime.fromisoformat(durum[k]) if durum.get(k) else None
    yapilan = []
    if not oku("ogrenim") or simdi - oku("ogrenim") >= GUN or durum.get("zorla"):
        ogrenim_yaz(kok, d)
        durum["ogrenim"] = simdi.isoformat(timespec="minutes")
        yapilan.append("ogrenim")
    sessiz_saat = 1 <= simdi.hour < 5            # buyuk isi musterilerin uretim saatlerinden uzak tut
    if durum.get("zorla") or ((not oku("kutuphaneci") or simdi - oku("kutuphaneci") >= HAFTA) and sessiz_saat):
        t = time.time()
        sonuc = kutuphaneci_calistir(kok)
        durum["kutuphaneci"] = simdi.isoformat(timespec="minutes")
        durum["son_sonuc"] = "ok" if sonuc else "hata"
        durum["sure_sn"] = int(time.time() - t)
        yapilan.append("kutuphaneci")
    if yapilan:
        durum.pop("zorla", None)
        d.json_yaz(DURUM, durum)
        y, s = yukle(kok, d)
        gunluk(f"{', '.join(yapilan)} tamam; depoya {y} dosya yuklendi, {s} silindi")
    return yapilan


def yonetim_ozeti(d=None):
    """Yonetim paneli icin: son Kutuphaneci raporu ve durum."""
    d = d or depo()
    durum = d.json_oku(DURUM, {}) or {}
    try:
        with tempfile.TemporaryDirectory() as t:
            yol = Path(t) / "r.json"
            rapor = json.loads(yol.read_text(encoding="utf-8")) if d.dosya_indir(ONEK + "kutuphane_rapor.json", yol) else {}
    except Exception:
        rapor = {}
    return {"durum": durum, "rapor": {k: v for k, v in rapor.items() if k != "gecmis"},
            "gecmis": [{"tarih": g.get("tarih"), "muzik_eklenen": (g.get("muzik") or {}).get("eklenen"),
                        "font_eklenen": len((g.get("font") or {}).get("eklenen") or [])} for g in rapor.get("gecmis", [])]}


def zorla(d=None):
    d = d or depo()
    durum = d.json_oku(DURUM, {}) or {}
    durum["zorla"] = True
    d.json_yaz(DURUM, durum)
