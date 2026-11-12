"""Supabase deposu: istek bicimleri (sahte HTTP oturumu; gercek Supabase'e baglanmaz)."""
import json

import pytest

from saas.depo import Cakisma
from saas.depo.supabase import SupabaseDepo


class Cevap:
    def __init__(self, kod=200, govde=None):
        self.status_code, self._g = kod, govde
        self.content = json.dumps(govde).encode() if govde is not None else b""
        self.text = self.content.decode()

    def json(self):
        return self._g


class Oturum:
    def __init__(self, *cevaplar):
        self.cevaplar, self.istekler = list(cevaplar), []

    def request(self, yontem, url, headers=None, params=None, data=None, timeout=None, **kw):
        self.istekler.append({"yontem": yontem, "url": url, "params": params or {}, "headers": headers,
                              "govde": json.loads(data) if isinstance(data, str) else None})
        return self.cevaplar.pop(0)


def _d(*c):
    o = Oturum(*c)
    return SupabaseDepo("https://p.supabase.co", "SERVIS", "kova", oturum=o), o


def test_servis_anahtari_basliklarda_ve_musteri_filtresi():
    d, o = _d(Cevap(200, [{"klasor": "k", "surum": 1}]))
    d.icerikler("m1", 5)
    i = o.istekler[0]
    assert i["url"] == "https://p.supabase.co/rest/v1/icerikler"
    assert i["params"]["musteri_id"] == "eq.m1" and i["params"]["limit"] == "5"
    assert i["headers"]["Authorization"] == "Bearer SERVIS" and i["headers"]["apikey"] == "SERVIS"


def test_surum_korumali_guncelleme_ve_cakisma():
    d, o = _d(Cevap(200, [{"surum": 4}]))
    assert d.icerik_yaz("m1", {"klasor": "k", "yayin": {"durum": "onaylandi"}}, beklenen_surum=3) == 4
    i = o.istekler[0]
    assert i["yontem"] == "PATCH" and i["params"]["surum"] == "eq.3" and i["govde"]["surum"] == 4
    d, o = _d(Cevap(200, []))
    with pytest.raises(Cakisma):
        d.icerik_yaz("m1", {"klasor": "k"}, beklenen_surum=3)


def test_is_alma_rpc():
    d, o = _d(Cevap(200, [{"id": "x", "tur": "uret"}]))
    assert d.is_al("isci-1", 70)["id"] == "x"
    assert o.istekler[0]["url"].endswith("/rest/v1/rpc/is_al")
    assert o.istekler[0]["govde"] == {"isci_adi": "isci-1", "zaman_asimi_dk": 70}


def test_toplu_imzali_adres_ve_gecersiz_anahtar():
    d, o = _d(Cevap(200, [{"path": "m1/cikti/k/a.jpg", "signedURL": "/object/sign/kova/m1/cikti/k/a.jpg?token=t"}]))
    r = d.dosya_adresleri(["m1/cikti/k/a.jpg"])
    assert r["m1/cikti/k/a.jpg"] == "https://p.supabase.co/storage/v1/object/sign/kova/m1/cikti/k/a.jpg?token=t"
    with pytest.raises(ValueError):
        d.dosya_adresleri(["../baska-musteri/x.jpg"])


def test_hata_mesaji_anahtari_icermez():
    from saas.depo.supabase import SupabaseHata
    d, o = _d(Cevap(500, {"message": "boom"}))
    with pytest.raises(SupabaseHata) as e:
        d.musteri_al("m1")
    assert "SERVIS" not in str(e.value)
