"""Uyelik oncesi ornek post: e-posta sarti, gunluk sinirlar, gecici isletme, sonucun yalnizca kimlikle gorulmesi."""
import requests

from ofis import entegrasyon
from saas import web

SITE = {"tamam": True, "site": "https://lunabakery.example", "platform": "genel", "baslik": "Luna Bakery | Fresh bread",
        "aciklama": "Family bakery known for sourdough and birthday cakes", "gorsel": "", "ikon": "", "dil": "en"}


def _baslat(sunucu, eposta="a@b.co", site="lunabakery.example", ip="1.1.1.1"):
    return requests.post(sunucu + "/api/onizleme", json={"site": site, "eposta": eposta, "dil": "en"},
                         headers={"X-Forwarded-For": ip})


def test_ornek_post_akisi_ve_sinirlar(sunucu, d, monkeypatch):
    monkeypatch.setattr(entegrasyon, "site_bilgisi", lambda site, oturum=None: dict(SITE))
    monkeypatch.setattr(web, "ONIZLEME_GUNLUK", 2)
    assert _baslat(sunucu, eposta="bozuk").json()["neden"] == "gecersiz"
    r = _baslat(sunucu)
    assert r.status_code == 202
    mid = r.json()["id"]
    m = d.musteri_al(mid)
    assert mid.startswith("onz-") and m["durum"] == "duraklatildi" and m["profil"]["onizleme"] and m["ad"] == "Luna Bakery"
    is_ = d.isler(mid, 1)[0]
    assert is_["tur"] == "uret" and is_["parametre"]["onizleme"] is True
    assert "a@b.co" not in str(m)                                      # e-posta isletme kaydina yazilmaz
    assert d.json_oku("_onizleme/kayitlar.json")[0]["eposta"] == "a@b.co"
    assert _baslat(sunucu).json()["id"] == mid                         # ayni kisi + site: ayni ornek, yeni is yok
    assert _baslat(sunucu, eposta="c@d.co").json()["neden"] == "sinir"        # ayni IP: gunde 1
    assert _baslat(sunucu, eposta="e@f.co", ip="2.2.2.2").status_code == 202
    assert _baslat(sunucu, eposta="g@h.co", ip="3.3.3.3").json()["neden"] == "sinir"   # toplam gunluk sinir
    assert requests.get(f"{sunucu}/api/onizleme/{mid}").json() == {"durum": "hazirlaniyor"}
    assert requests.get(f"{sunucu}/api/onizleme/onz-{'0' * 20}").status_code == 404


def test_normal_isletme_onizleme_ucundan_okunamaz_ve_yonetimde_gorunmez(sunucu, d, monkeypatch):
    from .conftest import FORM, oturum
    H = oturum(sunucu, "sahip@a.test")
    gercek = requests.post(sunucu + "/api/musteri", headers=H, json=FORM).json()["id"]
    assert requests.get(f"{sunucu}/api/onizleme/{gercek}").status_code == 404
    monkeypatch.setattr(entegrasyon, "site_bilgisi", lambda site, oturum=None: dict(SITE))
    mid = _baslat(sunucu).json()["id"]
    yon = requests.get(sunucu + "/api/yonetim/ozet", headers=oturum(sunucu, "patron@feedzync.test")).json()
    assert mid not in str(yon) and gercek in str(yon)
