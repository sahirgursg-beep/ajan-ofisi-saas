"""Uretim hatti: metin -> kalite kontrol (LLM yokken, sablon modunda) ve gorsel hazirlik.
Tam gorsel/Reels cizimi icin: AJAN_TAM_TEST=1 ile tarayici + ffmpeg kullanan uctan uca demo testi calisir."""
import json
import os
import subprocess
import sys

import pytest

from ofis import ajanlar, ayarlar, fiyat, llm, tasarim


@pytest.fixture(autouse=True)
def llm_kapali(monkeypatch):
    monkeypatch.setattr(llm, "sor", lambda *a, **k: None)
    monkeypatch.setattr(llm, "hazir", lambda: False)


@pytest.fixture
def urun():
    return fiyat.hazirla({"ad": "Milano Sofa", "fiyat": 1250, "eski_fiyat": 2000, "para_birimi": "USD",
                          "kategori": "Living Room > Sofas", "aciklama": "Solid frame.", "gorseller": []})


def _ekip():
    from ofis import pano
    pano.kur()
    return ajanlar.tum_ekip()


def test_sablon_metni_musteri_bilgisiyle_yazilir_ve_kontrolden_gecer(urun):
    e = _ekip()
    taslak = e["MetinYazari"].yaz(urun, "Comfort")
    assert urun["fiyat_metni"] in taslak["caption"]
    assert ayarlar.AYAR["marka"]["cta"] in taslak["caption"]
    assert taslak["hashtags"][0] == "#OakAndEmberLiving"
    ok, notlar = e["KaliteKontrol"].kontrol(urun, taslak)
    assert ok, notlar


def test_kalite_kontrol_yanlis_fiyati_yakalar(urun):
    e = _ekip()
    taslak = e["MetinYazari"].yaz(urun, "Comfort")
    taslak["caption"] = taslak["caption"].replace(urun["fiyat_metni"], "₦1,000,000")
    ok, notlar = e["KaliteKontrol"].kontrol(urun, taslak)
    assert not ok and any("exact price" in n or "Wrong price" in n for n in notlar)


def test_kalite_kontrol_online_satis_ifadesini_yakalar(urun):
    e = _ekip()
    taslak = e["MetinYazari"].yaz(urun, "Comfort")
    taslak["caption"] += "\nBuy online today!"
    ok, notlar = e["KaliteKontrol"].kontrol(urun, taslak)
    assert not ok and any("buy online" in n for n in notlar)


def test_marka_renkleri_sablona_islenir_ve_gecersiz_renk_atlanir(monkeypatch):
    css = tasarim.marka_css()
    assert f"--koyu:{ayarlar.AYAR['marka']['renk_koyu']};" in css
    monkeypatch.setitem(ayarlar.AYAR["marka"], "renk_koyu", "red;}body{display:none")
    assert "--koyu" not in tasarim.marka_css()


def test_logo_yoksa_sablon_logosuz_cizer():
    from ofis import marka
    assert marka.logolar() == {"altin": None, "krem": None, "koyu": None}


def test_seffaf_logo_uc_renkte_uretilir(monkeypatch):
    from PIL import Image, ImageDraw
    from ofis import marka
    yol = ayarlar.MUSTERI_KOK / "marka" / "logo.png"
    yol.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([40, 20, 160, 80], fill=(200, 120, 40, 255))
    im.save(yol)
    try:
        r = marka.logolar()
        assert all(p and p.exists() for p in r.values())
        assert Image.open(r["altin"]).size == (121, 61)          # seffaf kenarlar kirpildi
    finally:
        for p in (ayarlar.VERI / "marka").glob("*.png"):
            p.unlink()
        yol.unlink()


@pytest.mark.skipif(os.environ.get("AJAN_TAM_TEST") != "1", reason="tarayici + ffmpeg gerekir: AJAN_TAM_TEST=1")
def test_uctan_uca_demo_gunu(tmp_path):
    """Gercek uretim: 3 icerik (post, carousel, Reels) yeni bir musteri klasorunde uretilir, hicbiri onaylanmaz."""
    m = tmp_path / "musteriler" / "uctan-uca"
    m.mkdir(parents=True)
    (m / "profil.json").write_text((ayarlar.KOK / "musteriler" / "ornek-mobilya" / "profil.json")
                                   .read_text(encoding="utf-8"), encoding="utf-8")
    ortam = {**os.environ, "AJAN_MUSTERILER_KOK": str(tmp_path / "musteriler"), "AJAN_MUSTERI": "uctan-uca"}
    r = subprocess.run([sys.executable, str(ayarlar.KOK / "calistir.py"), "--demo", "--plansiz"],
                       cwd=ayarlar.KOK, env=ortam, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    klasorler = sorted(d for d in (m / "cikti").iterdir() if d.is_dir() and (d / "meta.json").exists())
    assert {d.name.rsplit("_", 1)[1] for d in klasorler} == {"post", "carousel", "reels"}
    for d in klasorler:
        assert (d / "post_1080x1350.jpg").stat().st_size > 10_000
        assert json.loads((d / "yayin.json").read_text(encoding="utf-8"))["durum"] == "bekliyor"
    reels = next(d for d in klasorler if d.name.endswith("_reels"))
    assert (reels / "reels_1080x1920.mp4").stat().st_size > 100_000
    assert len(list(next(d for d in klasorler if d.name.endswith("_carousel")).glob("carousel_*.jpg"))) >= 3
