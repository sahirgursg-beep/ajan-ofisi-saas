"""Gorsel Secici: cok aday -> temas sayfasi -> gorme modeli puani -> yalnizca 7+ secilir; model yoksa eski yol."""
from PIL import Image

from ofis import gorsel_kaynak, gorsel_secici, llm


def _sahte_kaynak(tmp_path, monkeypatch, n=10):
    def adaylar(q, adet=6, haric=(), **k):
        out = []
        for i in range(adet):
            kimlik = f"{q}:{i}"
            if kimlik in haric:
                continue
            y = tmp_path / f"{abs(hash(kimlik))}.jpg"
            Image.new("RGB", (64, 80), (i * 20 % 255, 90, 120)).save(y)
            out.append({"id": kimlik, "onizleme": str(y), "buyuk": str(y), "bilgi": {"kaynak": "test", "id": kimlik}})
        return out
    monkeypatch.setattr(gorsel_kaynak, "stok_adaylar", adaylar)
    monkeypatch.setattr(gorsel_kaynak, "indir", lambda adres, oturum=None: adres)


def test_yalnizca_konuya_uyan_fotograflar_secilir(tmp_path, monkeypatch):
    _sahte_kaynak(tmp_path, monkeypatch)
    gorulen = {}

    def gor(sistem, mesaj, yollar, **k):
        gorulen["mesaj"], gorulen["yol"] = mesaj, yollar[0]
        return {"scores": [{"no": 3, "score": 9}, {"no": 7, "score": 8}, {"no": 1, "score": 4}, {"no": 12, "score": 7},
                           {"no": 99, "score": 10}]}
    monkeypatch.setattr(llm, "gor", gor)
    secilen, rapor = gorsel_secici.sec(["barista latte art", "coffee shop counter"], "Our new latte", "Luna Cafe",
                                       adet=3, kacin="office", gunluk=lambda m: None)
    assert [p for _, _, p in secilen] == [9, 8, 7]                 # 4 puanli secilmedi, olmayan 99 yok sayildi
    assert rapor["aday"] == 12 and "Avoid: office" in gorulen["mesaj"]
    assert Image.open(gorulen["yol"]).size == (4 * 300, 3 * 375)      # 12 aday -> 4x3 numarali sayfa


def test_gorme_modeli_yoksa_eski_davranis(tmp_path, monkeypatch):
    _sahte_kaynak(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, "gor", lambda *a, **k: None)
    secilen, rapor = gorsel_secici.sec(["a"], "konu", "isletme", adet=2, gunluk=lambda m: None)
    assert len(secilen) == 2 and rapor["gorme"] is False


def test_gorme_modeli_katalogdan_bulunur_ve_hatirlanir(tmp_path, monkeypatch):
    from ofis import llm_openai
    monkeypatch.setenv("AJAN_YZ_ANAHTAR", "k")
    monkeypatch.delenv("AJAN_YZ_GORME_MODEL", raising=False)
    for ad, v in (("_gorme_yok", False), ("_gorme_model", None), ("_gorme_kotu", set()), ("_hazir", None)):
        monkeypatch.setattr(llm_openai, ad, v)
    y = tmp_path / "a.jpg"
    Image.new("RGB", (20, 20)).save(y)
    istekler = []

    class R:
        def __init__(self, kod, veri):
            self.status_code, self._v = kod, veri
        def json(self):
            return self._v
        def raise_for_status(self):
            pass

    class Http:
        def get(self, url, **k):
            return R(200, {"data": [{"id": "openai-gpt-oss-120b"}, {"id": "kimi-k2.6"}, {"id": "openai-gpt-image-1"}]})
        def post(self, url, json=None, **k):
            istekler.append(json["model"])
            return R(200, {"choices": [{"message": {"content": '{"ok": 1}'}}]}) if json["model"] == "kimi-k2.6" else R(400, {})
    assert llm_openai.gor("s", "m", [y], oturum=Http()) == {"ok": 1}
    assert istekler[0] == "kimi-k2.6" and llm_openai.gorme_modeli() == "kimi-k2.6"
    llm_openai.gor("s", "m", [y], oturum=Http())
    assert istekler == ["kimi-k2.6", "kimi-k2.6"]                  # ikinci seferde katalog taranmaz
