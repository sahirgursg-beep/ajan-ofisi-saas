"""SaaS testleri: yerel depo (gecici klasor), sahte giris, isci tetikleme kapali, sahte Meta."""
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

_GECICI = Path(tempfile.mkdtemp(prefix="saas_test_"))
os.environ.update({"SAAS_ORTAM": "yerel", "SAAS_DEPO": "yerel", "SAAS_YEREL_KLASOR": str(_GECICI / "varsayilan"),
                   "SAAS_TETIK": "yok", "SAAS_YEREL_GIRIS": "1", "SAAS_GENEL_ADRES": "http://panel.test",
                   "META_APP_ID": "uygulama1", "META_APP_SECRET": "gizli1", "AJAN_ENV_DOSYA": str(_GECICI / "yok.env")})

from saas import depo as depo_paketi  # noqa: E402
from saas.depo.yerel import YerelDepo  # noqa: E402

from .sahte_graph import SahteGraph  # noqa: E402


@pytest.fixture
def d(tmp_path):
    dp = YerelDepo(tmp_path / "depo")
    depo_paketi.ayarla(dp)
    yield dp
    depo_paketi.ayarla(None)


@pytest.fixture
def graph():
    g = SahteGraph()
    yield g
    g.kapat()


@pytest.fixture
def sunucu(d):
    """Gercek uvicorn sunucusu (httpx yok -> TestClient yerine requests ile)."""
    import uvicorn
    from saas.web import app
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(5)


def oturum(adres, eposta="sahip@a.test"):
    import requests
    t = requests.post(adres + "/api/yerel-giris", json={"eposta": eposta}).json()["belirtec"]
    return {"Authorization": "Bearer " + t}


FORM = {"isletme_adi": "Oak & Ember Living", "tanim": "a premium furniture showroom",
        "site": "https://oakandember.example", "saat_dilimi": "Africa/Lagos", "para_birimi": "NGN",
        "site_para_birimi": "USD", "kur": "1500"}
