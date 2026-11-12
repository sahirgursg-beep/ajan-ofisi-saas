"""Reels icin otomatik, telifsiz muzik.

Kaynak: Openverse (api.openverse.org) - WordPress'in acik lisansli medya arama servisi; Jamendo, ccMixter,
Freesound ve Wikimedia'daki parcalari lisans bilgisiyle listeler.

LISANS KURALI (degistirilemez):
  * Sadece CC0 (tamamen serbest) ve CC BY (ticari kullanim serbest, atif sart) indirilir.
  * NC (ticari degil), ND (degistirilemez), SA (ayni lisans zorunlu) parcalar ASLA kullanilmaz.
  * CC BY parcalarda sanatci/parca adi caption'a otomatik eklenir.
  * Her parcanin kaynagi ve lisansi muzik/otomatik/kutuphane.json'a kaydedilir.
Kullanicinin muzik/ klasorune kendi koydugu mp3'ler de havuza katilir.
"""
import json
import os
import random
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .ayarlar import AYAR, KOK, MUZIK, VERI

KLASOR = MUZIK / "otomatik"
KUTUPHANE = KLASOR / "kutuphane.json"
KULLANIM = VERI / "muzik_kullanim.json"   # tekrar sayaci musteri basina
API = os.environ.get("AJAN_OPENVERSE_URL", "https://api.openverse.org") + "/v1/audio/"
IZINLI = {"cc0", "by"}
BASLIK = {"User-Agent": "AjanOfisi/1.0 (social media reels; uses Openverse API)"}

VARSAYILAN_SORGULAR = {
    "sakin": ["piano lounge", "ambient chill", "smooth jazz", "acoustic calm", "lofi relaxing"],
    "enerjik": ["upbeat corporate", "upbeat pop", "funk groove", "electronic upbeat", "happy energetic"],
    "festival": ["afrobeat", "celebration party", "christmas upbeat", "festive dance", "african groove"],
}


def ayar(anahtar, varsayilan=None):
    return (AYAR.get("muzik") or {}).get(anahtar, varsayilan)


def _oku(yol, varsayilan):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return varsayilan


def _yaz(yol, veri):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def kutuphane():
    return _oku(KUTUPHANE, [])


def ruh_hali(tarif=None, etkinlik=""):
    """Tasarim tarifinden muzik ruh hali: festival / enerjik / sakin."""
    e = (etkinlik or "").lower() + " " + str((tarif or {}).get("banner", "")).lower()
    if any(k in e for k in ("detty", "christmas", "new year", "independence", "celebrat", "festive")):
        return "festival"
    if isinstance(tarif, dict) and (tarif.get("fiyat_stili") in ("rozet", "serit") or tarif.get("banner")):
        return "enerjik"
    return "sakin"


# ---------------- indirme ----------------
def _lisans_uygun(r):
    lisans = (r.get("license") or "").lower()
    return lisans in IZINLI


def _ara(sorgu, sayfa=1):
    p = {"q": sorgu, "license": "cc0,by", "license_type": "commercial,modification", "category": "music",
         "page_size": 20, "page": sayfa}
    r = requests.get(API, params=p, headers=BASLIK, timeout=30)
    if r.status_code == 400:            # filtre degeri desteklenmiyorsa: filtresiz ara, lisansi biz suzelim
        p.pop("license_type", None)
        r = requests.get(API, params=p, headers=BASLIK, timeout=30)
    r.raise_for_status()
    return [x for x in r.json().get("results", []) if _lisans_uygun(x)]


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _sure_sn(dosya):
    """ffmpeg ile gercek sureyi olcer (dosya bozuksa None)."""
    try:
        r = subprocess.run([_ffmpeg(), "-i", str(dosya), "-f", "null", "-"], capture_output=True, text=True,
                           timeout=120)
        m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
        if not m:
            return None
        h, d, s = m[-1]
        return int(h) * 3600 + int(d) * 60 + float(s)
    except Exception:
        return None


def guncelle(hedef_her_ruh=None, gunluk=print):
    """Her ruh hali icin kutuphanede en az hedef_her_ruh parca olmasini saglar. Indirilen parca sayisini doner."""
    hedef_her_ruh = hedef_her_ruh or int(ayar("hedef_her_ruh", 6))
    sorgular = ayar("sorgular", VARSAYILAN_SORGULAR)
    kut = kutuphane()
    var_olan = {k["id"] for k in kut}
    indirilen = 0
    for ruh, liste in sorgular.items():
        mevcut = [k for k in kut if k["ruh"] == ruh and (KLASOR / k["dosya"]).exists()]
        eksik = hedef_her_ruh - len(mevcut)
        if eksik <= 0:
            continue
        for sorgu in random.sample(liste, len(liste)):
            if eksik <= 0:
                break
            try:
                sonuclar = _ara(sorgu, random.randint(1, 3))
            except Exception as e:
                gunluk(f"Muzik aramasi basarisiz ({sorgu}): {e}")
                continue
            # CC0 once (atif gerekmez), sonra CC BY
            sonuclar.sort(key=lambda r: 0 if (r.get("license") or "").lower() == "cc0" else 1)
            for r in sonuclar:
                if eksik <= 0:
                    break
                sure = (r.get("duration") or 0) / 1000
                if r.get("id") in var_olan or not _lisans_uygun(r) or not r.get("url"):
                    continue
                if sure and not (40 <= sure <= 600):
                    continue
                if r.get("mature"):
                    continue
                uzanti = (r.get("filetype") or r["url"].rsplit(".", 1)[-1] or "mp3").lower()[:4]
                if uzanti not in ("mp3", "ogg", "wav", "flac", "m4a", "oga"):
                    uzanti = "mp3"
                ad = f"{ruh}_{r['id'][:12]}.{uzanti}"
                try:
                    v = requests.get(r["url"], headers=BASLIK, timeout=120)
                    v.raise_for_status()
                    if len(v.content) < 100_000 or len(v.content) > 25_000_000:
                        continue
                    KLASOR.mkdir(parents=True, exist_ok=True)
                    (KLASOR / ad).write_bytes(v.content)
                except Exception:
                    continue
                gercek = _sure_sn(KLASOR / ad)
                if not gercek or gercek < 30:
                    (KLASOR / ad).unlink(missing_ok=True)
                    continue
                kayit = {"id": r["id"], "dosya": ad, "ruh": ruh, "sorgu": sorgu, "baslik": r.get("title") or "",
                         "sanatci": r.get("creator") or "", "lisans": r["license"].lower(),
                         "lisans_surum": r.get("license_version") or "", "lisans_url": r.get("license_url") or "",
                         "kaynak": r.get("source") or r.get("provider") or "",
                         "sayfa": r.get("foreign_landing_url") or "", "atif": r.get("attribution") or "",
                         "sure_sn": round(gercek, 1), "indirme": datetime.now().isoformat(timespec="minutes")}
                kut.append(kayit)
                var_olan.add(r["id"])
                eksik -= 1
                indirilen += 1
                gunluk(f"🎵 {ruh}: \"{kayit['baslik']}\" - {kayit['sanatci']} ({kayit['lisans'].upper()})")
    _yaz(KUTUPHANE, kut)
    return indirilen


# ---------------- secim ----------------
def _kullanici_parcalari():
    kok = MUZIK
    return [{"id": "kullanici:" + p.name, "dosya": str(p), "ruh": "hepsi", "baslik": p.stem, "sanatci": "",
             "lisans": "kullanici"} for p in kok.glob("*.mp3")] if kok.exists() else []


def _havuz():
    return [k for k in kutuphane() if (KLASOR / k["dosya"]).exists()] + _kullanici_parcalari()


def _yol_ekle(k):
    k = dict(k)
    k["yol"] = k["dosya"] if os.path.isabs(k["dosya"]) else str(KLASOR / k["dosya"])
    return k


def bul(parca_id):
    """Belirli bir parcayi (revizyonda ayni muzigi korumak icin) bulur."""
    if not parca_id:
        return None
    k = next((k for k in _havuz() if k["id"] == parca_id), None)
    return _yol_ekle(k) if k else None


def sec(ruh="sakin", haric=None):
    """Ruh haline uygun, son 7 gunde kullanilmamis bir parca secer. Doner: kayit dict (veya None)."""
    kullanim = _oku(KULLANIM, {})
    sinir = (datetime.now() - timedelta(days=int(ayar("tekrar_gun", 7)))).isoformat()
    havuz = [k for k in _havuz() if k["id"] not in (haric or ())] or _havuz()
    uygun = [k for k in havuz if k["ruh"] in (ruh, "hepsi")] or havuz
    if not uygun:
        return None
    taze = [k for k in uygun if kullanim.get(k["id"], "") < sinir] or uygun
    taze.sort(key=lambda k: (0 if k.get("lisans") == "cc0" else 1, kullanim.get(k["id"], "")))
    return _yol_ekle(random.choice(taze[:3]))


def kullanildi(kayit):
    kullanim = _oku(KULLANIM, {})
    kullanim[kayit["id"]] = datetime.now().isoformat(timespec="minutes")
    _yaz(KULLANIM, kullanim)


def en_canli_bolum(dosya, sure=15.0):
    """Parcanin girisi atlanarak en enerjik 'sure' saniyelik bolumunun baslangicini bulur."""
    try:
        r = subprocess.run([_ffmpeg(), "-v", "error", "-i", str(dosya), "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                           capture_output=True, timeout=180)
        import array
        ornek = array.array("h", r.stdout[: len(r.stdout) // 2 * 2])
        if len(ornek) < 4000 * (sure + 2):
            return 0.0
        pencere = 2000   # 0.5 sn
        enerji = []
        for i in range(0, len(ornek) - pencere, pencere):
            p = ornek[i:i + pencere]
            enerji.append((sum(x * x for x in p[::8]) / (len(p) / 8)) ** 0.5)
        n = int(sure * 2)
        toplam_sn = len(enerji) / 2
        bas_min = int(min(max(8, toplam_sn * 0.1), max(0, toplam_sn - sure - 1)) * 2)  # girisi atla
        en_iyi, en_iyi_i = -1, bas_min
        for i in range(bas_min, len(enerji) - n):
            s = sum(enerji[i:i + n])
            if s > en_iyi:
                en_iyi, en_iyi_i = s, i
        return round(en_iyi_i / 2, 1)
    except Exception:
        return 0.0


def atif_satiri(kayit):
    """CC BY icin zorunlu atif (caption'a eklenir). CC0/kullanici parcasi icin bos."""
    if not kayit or kayit.get("lisans") != "by":
        return ""
    surum = f" {kayit['lisans_surum']}" if kayit.get("lisans_surum") else ""
    sanatci = f" by {kayit['sanatci']}" if kayit.get("sanatci") else ""
    return f"🎵 Music: \"{kayit.get('baslik') or 'Untitled'}\"{sanatci} (CC BY{surum})"
