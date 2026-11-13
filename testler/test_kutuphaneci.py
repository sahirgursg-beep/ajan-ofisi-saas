"""Kendi kendine buyuyen kutuphane: font ciftleri (alfabe duyarli), muzik puanlari/emeklilik, ortak ogrenim."""
import json

from ofis import analiz, fontlar, kutuphaneci, llm, muzik
from ofis.ayarlar import PAYLASIK


def _katalog():
    f = lambda ad, kat, subsets, pop, w=("400", "700"): {"family": ad, "category": kat, "subsets": ["menu", *subsets],
                                                         "popularity": pop, "fonts": {x: {} for x in w}}
    return {x["family"]: x for x in (
        f("Rubik Mono One", "Display", ["latin", "cyrillic"], 50, ("400",)),
        f("Noto Kufi Arabic", "Sans Serif", ["arabic", "latin"], 30, ("400", "600", "800")),
        f("Readex Pro", "Sans Serif", ["arabic", "latin"], 40),
        f("Lato", "Sans Serif", ["latin"], 5), f("Inter", "Sans Serif", ["latin", "cyrillic"], 3),
    )}


def test_icerik_dili_alfabesine_uygun_font_ciftleri():
    assert set(fontlar.uygun_ciftler("ar")) == {"arap_modern", "arap_klasik"}
    assert "afis" in fontlar.uygun_ciftler("en") and "afis" not in fontlar.uygun_ciftler("ru")
    assert fontlar.uygun_ciftler("ja") == list(fontlar.CIFTLER)         # hic yoksa sistem yedegi
    assert fontlar.alfabe("ar-EG") == "arabic" and fontlar.alfabe("fr") == "latin"


def test_kutuphaneci_yeni_font_cifti_ekler_ve_dogrular(monkeypatch):
    kat = _katalog()
    monkeypatch.setattr(kutuphaneci, "_css_calisiyor", lambda spec: "Bozuk" not in spec)
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", lambda *a, **k: {"ciftler": [
        {"anahtar": "mono poster", "bf": "Rubik Mono One", "gf": "Lato", "bw": 900, "bt": "uppercase", "bls": ".04em",
         "bo": 3, "his": "wide mono poster", "uygun": "gyms"},
        {"anahtar": "uydurma", "bf": "Var Olmayan Font", "gf": "Lato", "bw": 700},          # katalogda yok: atlanir
    ]})
    (muzik.ORTAK_OGRENIM).parent.mkdir(parents=True, exist_ok=True)
    muzik.ORTAK_OGRENIM.write_text(json.dumps({"platform": {"diller": {"en": 3, "fa": 1}}}))
    try:
        r = kutuphaneci.font_buyut(gunluk=lambda m: None, kat=kat)
        ek = json.loads(fontlar.EK_DOSYA.read_text())
        assert any(e.startswith("mono_poster: Rubik Mono One + Lato") for e in r["eklenen"])
        c = ek["ciftler"]["mono_poster"]
        assert c["bw"] == 400 and c["bt"] == "uppercase" and c["bo"] == 1.3 and c["alfabe"] == ["latin"]
        assert ek["google"]["Rubik Mono One"] == "Rubik+Mono+One"                 # tek agirlik: duz ad
        assert "uydurma" not in ek["ciftler"]
        # Farsca musteri var, Arap alfabeli cift 2 < 3: en populer Arapca aile eklendi
        assert any("arabic" in v["alfabe"] for k, v in ek["ciftler"].items())
        fontlar._ek_yukle()
        assert "mono_poster" in fontlar.CIFTLER and fontlar.GOOGLE["Rubik Mono One"]
        assert "mono_poster" in fontlar.css_siniflari()
    finally:
        fontlar.EK_DOSYA.unlink(missing_ok=True)
        muzik.ORTAK_OGRENIM.unlink(missing_ok=True)
        for k in [k for k, v in fontlar.CIFTLER.items() if v.get("ek")]:
            fontlar.CIFTLER.pop(k)


def test_google_spec_yalnizca_var_olan_agirliklar():
    kat = _katalog()
    assert kutuphaneci.google_spec(kat["Noto Kufi Arabic"], 900) == "Noto+Kufi+Arabic:wght@400;600;800"
    assert kutuphaneci.google_spec(kat["Lato"], 700) == "Lato:wght@400;700"


def test_muzik_puanlari_secimi_yonlendirir_ve_begenilmeyen_emekli_olur(monkeypatch):
    muzik.KLASOR.mkdir(parents=True, exist_ok=True)
    eski_kut = muzik.KUTUPHANE.read_text() if muzik.KUTUPHANE.exists() else None
    kayitlar = []
    for i in range(4):
        ad = f"sakin_t{i}.mp3"
        (muzik.KLASOR / ad).write_bytes(b"x")
        kayitlar.append({"id": f"t{i}", "dosya": ad, "ruh": "sakin", "baslik": f"T{i}", "lisans": "cc0"})
    muzik.KUTUPHANE.write_text(json.dumps(kayitlar))
    muzik.ORTAK_OGRENIM.parent.mkdir(parents=True, exist_ok=True)
    muzik.ORTAK_OGRENIM.write_text(json.dumps({"muzik": {"t0": {"skor": 1.5, "n": 4}, "t3": {"skor": -1.5, "n": 3}}}))
    monkeypatch.setattr(muzik, "_kullanici_parcalari", lambda: [])
    try:
        secilen = [muzik.sec("sakin")["id"] for _ in range(300)]
        assert secilen.count("t0") > secilen.count("t1") and secilen.count("t0") > secilen.count("t3")
        assert muzik.emekliye_ayir(gunluk=lambda m: None) == 1
        assert not (muzik.KLASOR / "sakin_t3.mp3").exists()
        assert {muzik.sec("sakin")["id"] for _ in range(100)} <= {"t0", "t1", "t2"}
        assert next(k for k in muzik.kutuphane() if k["id"] == "t3")["emekli"]   # lisans kaydi kalir
    finally:
        for i in range(4):
            (muzik.KLASOR / f"sakin_t{i}.mp3").unlink(missing_ok=True)
        muzik.KUTUPHANE.unlink() if eski_kut is None else muzik.KUTUPHANE.write_text(eski_kut)
        muzik.ORTAK_OGRENIM.unlink(missing_ok=True)


def test_kutuphaneci_sorgulari_dogrulanarak_eklenir(monkeypatch):
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", lambda *a, **k: {"sakin": ["bossa nova guitar", "<script>"], "enerjik": ["k-pop dance"]})
    monkeypatch.setattr(muzik, "_ara", lambda q, sayfa=1: [{"license": "cc0"}] * (5 if "bossa" in q else 0))
    monkeypatch.setattr(muzik, "guncelle", lambda **k: 2)
    monkeypatch.setattr(muzik, "emekliye_ayir", lambda **k: 0)
    try:
        r = kutuphaneci.muzik_buyut(gunluk=lambda m: None)
        assert r["yeni_sorgu"] == {"sakin": ["bossa nova guitar"]}             # sonuc vermeyen sorgu eklenmez
        assert "bossa nova guitar" in muzik.sorgular()["sakin"] and "piano lounge" in muzik.sorgular()["sakin"]
    finally:
        muzik.SORGU_DOSYA.unlink(missing_ok=True)


def test_ortak_ogrenim_yeni_musteriye_yon_verir():
    yol = PAYLASIK / "ogrenim" / "ortak.json"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"ozellik": {"fontlar": {"afis": {"skor": 1.6, "n": 9}, "retro": {"skor": -1.8, "n": 7},
                                                        "diner": {"skor": 2, "n": 1}}}}))
    try:
        assert analiz.ozellik_agirligi("fontlar", "afis") > 1.3
        assert analiz.ozellik_agirligi("fontlar", "retro") < 0.7
        assert analiz.ozellik_agirligi("fontlar", "diner") == 1.0            # az veri: etkisiz
        assert "afis" in analiz.ortak_ozet() and "retro" in analiz.ortak_ozet()
    finally:
        yol.unlink()
