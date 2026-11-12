"""Fiyat hesabi kodla yapilir; LLM'e birakilmaz. Para birimi musteriden gelir."""
import re

import pytest

from ofis import ayarlar, fiyat


def test_usd_yerel_paraya_cevrilir_ve_yuvarlanir():
    assert fiyat.yerel_fiyat(199.99, "USD") == 300000          # 199.99 * 1500 = 299985 -> 300,000
    assert fiyat.yerel_fiyat(1, "USD") == 2000                  # 1500 -> en yakin 1000 (2000, banker's yok)


def test_yerel_para_biriminde_kur_uygulanmaz():
    assert fiyat.yerel_fiyat(350000, "NGN") == 350000
    assert fiyat.yerel_fiyat(350000, "₦") == 350000


def test_kuru_tanimsiz_para_birimi_acik_hata_verir():
    with pytest.raises(ValueError):
        fiyat.yerel_fiyat(10, "EUR")


def test_indirim_ve_metin():
    u = fiyat.hazirla({"fiyat": 600, "eski_fiyat": 1000, "para_birimi": "USD"})
    assert u["fiyat_metni"] == "₦900,000"
    assert u["eski_fiyat_metni"] == "₦1,500,000"
    assert u["indirim_yuzde"] == 40
    assert u["tutar"] == u["ngn"] == 900000


def test_fiyat_gosterimi_kapaliysa_eski_fiyat_yok(monkeypatch):
    monkeypatch.setitem(ayarlar.AYAR, "fiyat_gosterimi", "normal")
    u = fiyat.hazirla({"fiyat": 600, "eski_fiyat": 1000, "para_birimi": "USD"})
    assert u["eski_fiyat_metni"] == "" and u["indirim_yuzde"] == 0


@pytest.mark.parametrize("metin,beklenen", [("Now ₦250,000!", "250,000"), ("only NGN 250,000", "250,000"),
                                            ("N250,000 only", "250,000")])
def test_fiyat_deseni_tum_yazimlari_yakalar(metin, beklenen):
    assert re.findall(fiyat.fiyat_deseni(), metin) == [beklenen]


def test_baska_para_birimli_musteri(monkeypatch):
    for k, v in {"para_birimi": "GHS", "para_sembolu": "GH₵", "site_para_birimi": "GHS",
                 "yuvarlama": 10, "ek_fiyat_isaretleri": []}.items():
        monkeypatch.setitem(ayarlar.AYAR, k, v)
    u = fiyat.hazirla({"fiyat": 1234})
    assert u["fiyat_metni"] == "GH₵1,230"
    assert re.findall(fiyat.fiyat_deseni(), "Price GH₵1,230") == ["1,230"]
