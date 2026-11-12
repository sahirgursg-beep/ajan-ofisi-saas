"""Musteri ayarlari: profil birlesmesi, klasor ayrimi ve musteriye ozel metinler."""
import json

import pytest

from ofis import ayarlar, musteri


def test_profil_platform_ayarinin_ustune_yazilir():
    assert ayarlar.AYAR["musteri_id"] == "test-musteri"
    assert ayarlar.AYAR["isletme"]["ad"] == "Test Living"          # profilden
    assert ayarlar.AYAR["model"]                                     # config.json'dan
    assert ayarlar.AYAR["marka"]["renk_koyu"].startswith("#")


def test_derin_birlestirme_alt_anahtarlari_korur():
    taban = {"marka": {"ad": "A", "renk": "#000"}, "x": 1}
    ust = {"marka": {"ad": "B"}}
    assert ayarlar._derin_birlestir(taban, ust) == {"marka": {"ad": "B", "renk": "#000"}, "x": 1}


def test_veri_ve_cikti_musteri_klasorunde():
    for yol in (ayarlar.VERI, ayarlar.CIKTI, ayarlar.PROJELER):
        assert ayarlar.MUSTERI_KOK in yol.parents
        assert yol.exists()


@pytest.mark.parametrize("kotu", ["../fr", "FR", "a b", "x/y", "-x"])
def test_gecersiz_musteri_kimligi_reddedilir(monkeypatch, kotu):
    monkeypatch.setenv("AJAN_MUSTERI", kotu)
    with pytest.raises(ValueError):
        ayarlar.aktif_musteri()


def test_profili_olmayan_musteri_acik_hata_verir():
    with pytest.raises(FileNotFoundError):
        ayarlar.yukle("olmayan-musteri")


def test_sablon_profil_gecerli_json_ve_zorunlu_alanlar():
    for ad in ("_sablon", "ornek-mobilya"):
        p = json.loads((ayarlar.KOK / "musteriler" / ad / "profil.json").read_text(encoding="utf-8"))
        for alan in ("isletme", "marka", "para_birimi", "kategoriler", "haftalik_tema"):
            assert alan in p, (ad, alan)


def test_istem_metinleri_musteriden_gelir():
    assert musteri.ad() == "Test Living"
    assert musteri.tanim() == "a premium furniture showroom in Nigeria"
    assert "Lagos" in musteri.sehirler_metni()


def test_online_satan_musteride_yasak_ifade_yok(monkeypatch):
    assert "buy online" in musteri.yasak_ifadeler()
    monkeypatch.setitem(ayarlar.AYAR["isletme"], "online_satis", True)
    assert musteri.yasak_ifadeler() == []


def test_proje_hashtagleri_yoksa_genel_hashtaglere_duser(monkeypatch):
    monkeypatch.setitem(ayarlar.AYAR["isletme"], "proje_hashtagler", [])
    assert musteri.hashtagler(proje=True) == musteri.hashtagler()


def test_kodda_ilk_musteriye_ozel_ifade_kalmadi():
    """Furniture Republic'e ozel ad, sehir, logo ve rakip bilgisi kodda sabit olarak gecmemeli."""
    yasak = ("Furniture Republic", "FURNITURE REPUBLIC", "furniturerepublic", "areamobilya", "FR LOGO",
             "FR monogram", "Abuja saat", "Lagos/Abuja")
    for dosya in list((ayarlar.KOK / "ofis").glob("*.py")) + list(ayarlar.KOK.glob("*.py")) \
            + list((ayarlar.KOK / "sablonlar").glob("*.html")):
        metin = dosya.read_text(encoding="utf-8")
        for y in yasak:
            assert y not in metin, f"{dosya.name}: '{y}'"
