"""Testler gercek musteri verisine ASLA dokunmaz: her oturum gecici bir musteri klasoru kurar.
Ortam degiskenleri ofis paketi ilk kez ice aktarilmadan ONCE ayarlanmalidir (bu dosya bunu yapar)."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
GECICI = Path(tempfile.mkdtemp(prefix="ajan_test_"))
MUSTERI = "test-musteri"

_profil = json.loads((KOK / "musteriler" / "ornek-mobilya" / "profil.json").read_text(encoding="utf-8"))
_profil["isletme"]["ad"] = "Test Living"
_profil["marka"]["ad"] = "TEST LIVING"
_profil["site_para_birimi"] = "USD"
(GECICI / "musteriler" / MUSTERI).mkdir(parents=True)
(GECICI / "musteriler" / MUSTERI / "profil.json").write_text(json.dumps(_profil, ensure_ascii=False), encoding="utf-8")
shutil.copytree(KOK / "paylasilan" / "takvimler", GECICI / "paylasilan" / "takvimler")

os.environ["AJAN_MUSTERILER_KOK"] = str(GECICI / "musteriler")
os.environ["AJAN_PAYLASIK_KOK"] = str(GECICI / "paylasilan")
os.environ["AJAN_MUSTERI"] = MUSTERI
os.environ["AJAN_GRAPH_URL"] = "http://127.0.0.1:9"        # yanlislikla gercek Meta'ya istek gitmesin
os.environ.pop("GEMINI_API_KEY", None)
sys.path.insert(0, str(KOK))

from ofis import ayarlar  # noqa: E402

assert ayarlar.MUSTERI_KOK == GECICI / "musteriler" / MUSTERI, "Testler gecici musteri klasorunde calismali"


@pytest.fixture
def cikti_temiz():
    """Her yayin testi bos bir cikti klasoruyla baslar."""
    for d in ayarlar.CIKTI.iterdir():
        shutil.rmtree(d) if d.is_dir() else d.unlink()
    for ad in ("yayin_ayar.json", "meta.json"):
        (ayarlar.VERI / ad).unlink(missing_ok=True)
    yield ayarlar.CIKTI


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(GECICI, ignore_errors=True)
