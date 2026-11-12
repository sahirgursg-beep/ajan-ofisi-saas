"""Is kuyrugu: isi veritabanina yazar ve isciyi uyandirir.

Isci bir kez uyandiginda kuyruk bosalana kadar is alir (ayni musteride ayni anda tek is).
Bulutta uyandirma = Cloud Run Job calistirmasi; yerelde = arka planda bir alt surec.
"""
import subprocess
import sys
import threading
import time

import requests

from . import ayar
from .depo import depo

_son_tetik = 0.0
_kilit = threading.Lock()


def is_ekle(mid, tur, parametre=None, tekil=True, tetikle=True):
    """tekil: ayni tur+parametreyle bekleyen is varsa yenisini acmaz, onu doner."""
    d = depo()
    if tekil:
        var = d.bekleyen_is(mid, tur, parametre or {})
        if var:
            return var
    i = d.is_ekle(mid, tur, parametre or {})
    if tetikle:
        isciyi_uyandir()
    return i


def isciyi_uyandir():
    global _son_tetik
    with _kilit:
        if time.time() - _son_tetik < 15:      # art arda tiklamalarda tek calistirma yeter
            return "atlandi"
        _son_tetik = time.time()
    if ayar.TETIK == "yerel":
        subprocess.Popen([sys.executable, "-m", "saas.isci"], cwd=str(ayar.KOK),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return "yerel"
    if ayar.TETIK == "surekli":           # VPS: isci zaten acik ve kuyrugu yokluyor
        return "surekli"
    if ayar.TETIK == "cloudrun":
        return _cloud_run_calistir()
    return "yok"


def _metadata_token():
    r = requests.get("http://metadata.google.internal/computeMetadata/v1/instance/service-account/default/token",
                     headers={"Metadata-Flavor": "Google"}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def _cloud_run_calistir():
    adres = (f"https://run.googleapis.com/v2/projects/{ayar.GCP_PROJE}/locations/{ayar.GCP_BOLGE}"
             f"/jobs/{ayar.ISCI_IS_ADI}:run")
    r = requests.post(adres, headers={"Authorization": f"Bearer {_metadata_token()}"}, json={}, timeout=20)
    if r.status_code >= 300:
        raise RuntimeError(f"Isci baslatilamadi: HTTP {r.status_code} {r.text[:200]}")
    return "cloudrun"
