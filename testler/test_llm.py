"""Yapay zeka katmani saglayicidan bagimsiz: ana -> yedek -> sablon modu."""
import pytest

from ofis import ayarlar, llm, llm_gemini
from ofis.llm_ortak import json_coz


class Sahte:
    def __init__(self, ad, hazir=True, cevap="tamam"):
        self.ad, self._hazir, self.cevap, self.cagri = ad, hazir, cevap, []

    def hazir(self):
        return self._hazir

    def model_adi(self):
        return f"{self.ad}-model"

    def sor(self, sistem, mesaj, json_mod=False, sicaklik=0.7):
        self.cagri.append((sistem, mesaj, json_mod))
        return self.cevap

    def sifirla(self):
        pass

    def durum(self):
        return "sahte"


@pytest.fixture
def saglayicilar(monkeypatch):
    def kur(ana, yedek=None, **ozel):
        monkeypatch.setitem(ayarlar.AYAR, "yz", {**ayarlar.AYAR.get("yz", {}), "saglayici": ana,
                                                  "yedek_saglayici": yedek or ""})
        monkeypatch.setattr(llm, "_ozel", dict(ozel))
    return kur


def test_ana_saglayici_kullanilir(saglayicilar):
    a, b = Sahte("a"), Sahte("b")
    saglayicilar("a", "b", a=a, b=b)
    assert llm.sor("s", "m") == "tamam"
    assert a.cagri and not b.cagri
    assert llm.saglayici_adi() == "a" and llm.model_adi() == "a-model"


def test_ana_hazir_degilse_yedege_gecer(saglayicilar):
    a, b = Sahte("a", hazir=False), Sahte("b", cevap="yedekten")
    saglayicilar("a", "b", a=a, b=b)
    assert llm.sor("s", "m") == "yedekten"
    assert llm.saglayici_adi() == "b"


def test_ana_hata_verirse_yedege_gecer(saglayicilar):
    a, b = Sahte("a", cevap=None), Sahte("b", cevap="yedekten")
    saglayicilar("a", "b", a=a, b=b)
    assert llm.sor("s", "m") == "yedekten"
    assert a.cagri and b.cagri


def test_hicbiri_yoksa_none_ve_sablon_modu(saglayicilar):
    saglayicilar("a", "b", a=Sahte("a", hazir=False), b=Sahte("b", hazir=False))
    assert llm.hazir() is False
    assert llm.sor("s", "m") is None


def test_bilinmeyen_saglayici_acik_hata(saglayicilar):
    saglayicilar("yok")
    with pytest.raises(ValueError):
        llm.hazir()


def test_json_coz_kod_blogu_ve_bozuk_metin():
    assert json_coz('```json\n{"a": 1}\n```') == {"a": 1}
    assert json_coz('Here: {"a": [1, 2]} thanks') == {"a": [1, 2]}
    assert json_coz("json degil") is None
    assert json_coz(None) is None


# ---------------- Gemini (ag yok: sahte HTTP oturumu) ----------------
class SahteCevap:
    def __init__(self, kod, govde):
        self.status_code, self._g = kod, govde

    def json(self):
        return self._g

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class SahteOturum:
    def __init__(self, *cevaplar):
        self.cevaplar, self.istekler = list(cevaplar), []

    def post(self, url, json=None, headers=None, timeout=None):
        self.istekler.append({"url": url, "json": json, "headers": headers})
        return self.cevaplar.pop(0)


def _gemini_cevap(metin):
    return {"candidates": [{"content": {"parts": [{"text": metin}]}}]}


@pytest.fixture
def gemini_anahtar(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-anahtar")
    llm_gemini.sifirla()
    yield
    llm_gemini.sifirla()


def test_gemini_anahtar_yoksa_hazir_degil(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    llm_gemini.sifirla()
    assert llm_gemini.hazir() is False
    assert "anahtar" in llm_gemini.durum().lower()


def test_gemini_istek_bicimi_ve_json_cevap(gemini_anahtar):
    o = SahteOturum(SahteCevap(200, _gemini_cevap('{"index": 2}')))
    assert llm_gemini.sor("sistem metni", "soru", json_mod=True, sicaklik=0.3, oturum=o) == {"index": 2}
    istek = o.istekler[0]
    assert istek["headers"]["x-goog-api-key"] == "test-anahtar"
    assert "key=" not in istek["url"]                      # anahtar URL'de (loglarda) gorunmez
    assert istek["json"]["systemInstruction"]["parts"][0]["text"] == "sistem metni"
    assert istek["json"]["generationConfig"] == {"temperature": 0.3, "responseMimeType": "application/json"}


def test_gemini_gecici_hatada_bir_kez_yeniden_dener(gemini_anahtar, monkeypatch):
    monkeypatch.setattr(llm_gemini.time, "sleep", lambda s: None)
    o = SahteOturum(SahteCevap(429, {}), SahteCevap(200, _gemini_cevap("merhaba")))
    assert llm_gemini.sor("s", "m", oturum=o) == "merhaba"
    assert len(o.istekler) == 2


def test_gemini_kalici_hatada_none_ve_bir_sure_hazir_degil(gemini_anahtar):
    o = SahteOturum(SahteCevap(400, {"error": {"message": "bad"}}))
    assert llm_gemini.sor("s", "m", oturum=o) is None
    assert llm_gemini.hazir() is False
