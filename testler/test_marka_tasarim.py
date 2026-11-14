"""Marka tasarim sistemi + tasarim modeli zinciri + Reels kapanis karti."""
import json
import os

import pytest

from ofis import fiyat, llm, llm_openai, marka_tasarim, modern_duzen, uretken

TARAYICI = pytest.mark.skipif(os.environ.get("AJAN_TAM_TEST") != "1", reason="tarayici gerekir (AJAN_TAM_TEST=1)")

SABLON = """<style>.tuval{width:1080px;height:1350px;position:relative;overflow:hidden;background:#111;color:#fff}
.b{position:absolute;left:72px;right:72px;bottom:260px;font:800 var(--h)/1 var(--bf);text-wrap:balance}
.p{position:absolute;left:72px;bottom:120px;font:700 48px var(--gf);white-space:nowrap}
.c{position:absolute;right:72px;bottom:120px;font:700 36px var(--gf);white-space:nowrap}</style>
<div class="tuval"><img src="{{FOTO1}}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.5">
<h1 class="b" data-metin>{{HEADLINE}}</h1><div class="p" data-metin data-alan="PRICE">{{PRICE}}</div>
<div class="c" data-metin data-alan="CTA">{{CTA}}</div></div>"""


class _Yanit:
    def __init__(self, kod, veri):
        self.status_code, self._veri, self.text = kod, veri, json.dumps(veri)

    def json(self):
        return self._veri

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Http:
    """DO: /models iki Claude listeler; ilki 403, ikincisi calisir."""
    def __init__(self):
        self.denenen = []

    def get(self, url, **k):
        return _Yanit(200, {"data": [{"id": "anthropic-claude-4.5-sonnet"}, {"id": "anthropic-claude-4.6-sonnet"},
                                     {"id": "openai-gpt-oss-120b"}]})

    def post(self, url, json=None, **k):
        self.denenen.append(json["model"])
        if json["model"] == "anthropic-claude-4.6-sonnet":
            return _Yanit(403, {"error": "model not in key scope"})
        return _Yanit(200, {"choices": [{"message": {"content": "<div class='tuval'></div>"}}], "usage": {}})


def test_tasarim_modeli_403_hesap_duzeyinde_tum_do_claude_atlanir(monkeypatch):
    monkeypatch.setenv("AJAN_YZ_ANAHTAR", "x")
    monkeypatch.delenv("AJAN_YZ_TASARIM_MODEL", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.setattr(llm_openai, "hazir", lambda: True)
    monkeypatch.setattr(llm_openai, "_tasarim_adaylari", None)
    monkeypatch.setattr(llm_openai, "_tasarim_kotu", set())
    http = _Http()
    cevap = llm_openai.tasarim_sor("s", "m", oturum=http)
    assert cevap == "<div class='tuval'></div>"
    assert http.denenen[0] == "anthropic-claude-4.6-sonnet"
    assert "anthropic-claude-4.5-sonnet" not in http.denenen          # 403 hesap duzeyinde: digerleri denenmez
    assert llm_openai.tasarim_modeli(http) == llm_openai.model_adi()


def test_do_claude_yoksa_fal_openrouter_kullanilir(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    monkeypatch.setattr(llm_openai, "hazir", lambda: True)
    monkeypatch.setattr(llm_openai, "_tasarim_adaylari", [])
    monkeypatch.setattr(llm_openai, "_tasarim_kotu", set())

    class Http:
        def post(self, url, json=None, headers=None, **k):
            assert url.endswith("openrouter/router") and headers["Authorization"] == "Key k"
            assert json["model"].startswith("anthropic/claude") and json["system_prompt"] == "s"
            return _Yanit(200, {"output": "<style></style><div class=\"tuval\"></div>", "usage": {"cost": 0.01}})
    assert "tuval" in llm_openai.tasarim_sor("s", "m", oturum=Http())


def test_sablon_doldurma_bos_alanlari_kaldirir_ve_boyu_metne_gore_ayarlar():
    h = marka_tasarim.doldur(SABLON, "post_a", {"HEADLINE": "A <b>", "PRICE": "", "CTA": "Shop"}, {"FOTO1": "data:x"})
    assert "A &lt;b&gt;" in h and "{{" not in h and "--h:124px" in h
    assert h.count("<i data-bos>") == 1 and "<script>" in h       # bos fiyat ogesi sayfada kaldirilir
    kart = marka_tasarim.doldur("<div class=\"tuval\"><b data-metin>No. {{NO}}</b><h1>{{HEADLINE}}</h1></div>", "post_c",
                                {"HEADLINE": "Hi", "NO": "3"}, {})
    assert "No. 3" not in kart and "data-bos" in kart             # post NO almaz: rozet kaldirilir
    uzun = marka_tasarim.doldur(SABLON, "post_a", {"HEADLINE": "x" * 58}, {})
    assert "--h:76px" in uzun


def test_kapanis_karti_logoyu_kontrast_zemine_koyar():
    dil = {"palet": {"bg": "#F4F4F0", "ink": "#111111", "accent": "#1B3D2F", "accent2": "#E8B04B"}, "font": "cagdas"}
    yalniz_acik = modern_duzen.kapanis(1080, 1920, {"CTA": "Book now", "WEB": "x.com"}, dil, {"LOGO_ACIK": "data:acik"})
    assert "background:#1B3D2F" in yalniz_acik and "data:acik" in yalniz_acik       # acik logo -> koyu zemin
    yalniz_koyu = modern_duzen.kapanis(1080, 1920, {"CTA": "Book now"}, dil, {"LOGO_KOYU": "data:koyu"})
    assert "background:#F4F4F0" in yalniz_koyu and "data:koyu" in yalniz_koyu


def test_sablon_ornek_metni_gunun_icerigiyle_ayni_konuda():
    urun = fiyat.hazirla({"ad": "AI captions", "fiyat": 0, "para_birimi": "USD", "gorseller": []})
    o = marka_tasarim.ornekler(urun, {"headline": "3 caption hacks", "carousel_lines": ["Hook first"]})
    assert o["kisa"]["HEADLINE"] == "3 caption hacks" and o["kisa"]["LINE"] == "Hook first"
    assert "caption" in o["uzun"]["HEADLINE"] and "Fresh" not in json.dumps(o)


def test_hakem_kapanis_kartinda_foto_ya_da_baslik_aramaz():
    assert "do not ask for a photo" in uretken._olcut({"ad": "reels_son"})
    assert "Instagram creative" in uretken._olcut({"ad": "post"})


@TARAYICI
def test_sistem_kurulur_ve_gunluk_set_sablonlardan_cizilir(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(marka_tasarim, "DOSYA", tmp_path / "sistem.json")
    fotolar = []
    for i, renk in enumerate(("#7a8c6e", "#8c6e7a", "#6e7a8c")):
        f = tmp_path / f"f{i}.jpg"
        Image.new("RGB", (900, 1200), renk).save(f)
        fotolar.append(str(f))
    urun = fiyat.hazirla({"ad": "Lamp", "fiyat": 50, "para_birimi": "USD", "gorseller": []})
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", lambda s, m, json_mod=False, sicaklik=0.7:
                        {"stil": "poster_tipografi", "fikir": "x", "font": "cagdas"} if json_mod else "")
    monkeypatch.setattr(llm, "tasarim_sor", lambda s, m, sicaklik=0.7:
                        SABLON.replace("{{HEADLINE}}", "{{LINE}}") if "carousel slide" in m else SABLON)
    monkeypatch.setattr(llm, "gor", lambda *a, **k: {"score": 8, "problems": []})
    s = marka_tasarim.kur(urun, fotolar, {"headline": "Glow"}, gunluk=lambda m: None, zorla=True)
    assert s and "post_a" in s["sablonlar"] and not marka_tasarim.eski_mi()
    r = marka_tasarim.ciz_set(urun, fotolar, {"headline": "Glow", "carousel_lines": ["One", "Two"]}, tmp_path,
                              "carousel", gunluk=lambda m: None)
    assert r and r["sistem"] and (tmp_path / "post_1080x1350.jpg").stat().st_size > 5000
    assert [p.name for p in r["dosyalar"]][:3] == ["post_1080x1350.jpg", "carousel_1.jpg", "carousel_2.jpg"]
    son = marka_tasarim.son_kart(fotolar, tmp_path / "son.jpg", gunluk=lambda m: None)
    assert son and son.stat().st_size > 3000


@TARAYICI
def test_sistem_kurulamasa_da_set_modern_duzenlerle_tam_cizilir_ve_her_uretimde_yeniden_denenmez(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(marka_tasarim, "DOSYA", tmp_path / "sistem.json")
    fotolar = []
    for i, renk in enumerate(("#7a8c6e", "#8c6e7a")):
        f = tmp_path / f"f{i}.jpg"
        Image.new("RGB", (900, 1200), renk).save(f)
        fotolar.append(str(f))
    urun = fiyat.hazirla({"ad": "Lamp", "fiyat": 50, "para_birimi": "USD", "gorseller": []})
    cagri = []
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", lambda s, m, json_mod=False, sicaklik=0.7:
                        {"stil": "bento", "fikir": "x", "font": "cagdas"} if json_mod else "")
    monkeypatch.setattr(llm, "tasarim_sor", lambda s, m, sicaklik=0.7: cagri.append(1) or SABLON)
    monkeypatch.setattr(llm, "gor", lambda *a, **k: {"score": 3, "problems": ["dated"]})
    s = marka_tasarim.kur(urun, fotolar, {"headline": "Glow"}, gunluk=lambda m: None)
    assert s is not None and s["sablonlar"] == {} and len(cagri) == 2 * len(marka_tasarim.TIPLER)
    assert not marka_tasarim.eski_mi()                               # bugun denendi: ayni gun tekrar kurulmaz
    r = marka_tasarim.ciz_set(urun, fotolar, {"headline": "Glow", "carousel_lines": ["One", "Two", "Three"],
                                              "carousel_points": ["A", "B", "C"]}, tmp_path, None, gunluk=lambda m: None)
    adlar = [p.name for p in r["dosyalar"]]
    assert adlar == ["post_1080x1350.jpg", "story_1080x1920.jpg", "carousel_1.jpg", "carousel_2.jpg", "carousel_3.jpg",
                     "carousel_4.jpg", "carousel_5.jpg"] and not r["sistem"]
    assert marka_tasarim.son_kart(fotolar, tmp_path / "son.jpg", gunluk=lambda m: None)


@TARAYICI
def test_bos_rozet_ve_ikon_cipi_goruntuden_kalkar(tmp_path):
    from ofis import tasarim
    sab = ("<style>.tuval{width:1080px;height:1350px;position:relative;background:#111;color:#fff;font-size:60px}</style>"
           "<div class=\"tuval\"><div id=\"r\" data-metin>No. {{NO}}</div><div id=\"c\"><span><svg width=\"20\" height=\"20\"></svg>"
           "<span data-metin>{{POINT1}}</span></span></div><h1 data-metin>{{HEADLINE}}</h1></div>")
    dil = uretken._varsayilan_dil()
    tuval = {"ad": "post", "boyut": (1080, 1350), "rol": "", "metin": {"headline": "Hello"}}
    f = tmp_path / "s.html"
    f.write_text(uretken._sayfa(marka_tasarim.doldur(sab, "post_c", {"HEADLINE": "Hello"}, {}), tuval, dil, {}), encoding="utf-8")
    sayfa = tasarim._tarayici_al().new_page()
    try:
        sayfa.goto(f.as_uri())
        assert sayfa.evaluate("[!!document.getElementById('r'), !!document.getElementById('c'), document.querySelector('h1').innerText]") \
            == [False, False, "Hello"]
    finally:
        sayfa.close()
        tasarim.kapat()


def test_gorsel_hakki_dolunca_yapay_zeka_gorseli_uretilmez(tmp_path, monkeypatch):
    from ofis import fal_ai, paketler
    monkeypatch.setattr(fal_ai, "HARCAMA", tmp_path / "h.json")
    monkeypatch.setenv("FAL_KEY", "k")
    monkeypatch.setattr(paketler, "aktif", lambda: {"ai_gorsel": 2, "ai_tavan_usd": 50})
    cagri = []
    from PIL import Image
    monkeypatch.setattr(fal_ai, "_cagir", lambda *a, **k: cagri.append(1) or Image.new("RGB", (8, 8)))
    assert fal_ai.gorsel_kalan() == 2
    assert fal_ai.uret("x") is not None and fal_ai.uret("x") is not None
    assert fal_ai.gorsel_kalan() == 0 and fal_ai.uret("x") is None and len(cagri) == 2


def test_pro_paket_tek_marka_ve_her_pakette_gorsel_hakki():
    from ofis import paketler
    assert [p["isletme"] for p in paketler.PAKETLER.values()] == [1, 1, 1]
    assert [p["ai_gorsel"] for p in paketler.PAKETLER.values()] == [10, 40, 120]
    from saas.site import metin
    assert "3" not in " ".join(str(x) for x in paketler.PAKETLER["pro"]["ozellikler"][:1])


def test_son_kontrol_kusurlu_kapagi_reddeder(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "gor", lambda *a, **k: {"ok": False, "problem": "empty badge"})
    assert marka_tasarim._son_kontrol(tmp_path / "x.jpg") == "empty badge"
    monkeypatch.setattr(llm, "gor", lambda *a, **k: {"score": 8})
    assert marka_tasarim._son_kontrol(tmp_path / "x.jpg") is None
