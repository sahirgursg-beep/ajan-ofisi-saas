"""Kayit formu dogrulama, giris belirteci, sifreleme ve imzali OAuth state."""
import time

import jwt
import pytest

from saas import guvenlik, profil

from .conftest import FORM


def test_formdan_profil():
    p = profil.formdan({**FORM, "sehirler": "Lagos, Abuja", "hashtagler": "oak, #home decor", "renk_koyu": "#112233"})
    assert p["isletme"]["ad"] == "Oak & Ember Living" and p["marka"]["ad"] == "OAK & EMBER LIVING"
    assert p["isletme"]["saat_kisaltma"] == "WAT" and p["isletme"]["utc_ofset_saat"] == 1
    assert p["isletme"]["hashtagler"] == ["#oak", "#homedecor"]
    assert p["doviz_kurlari"] == {"USD": 1500.0} and p["marka"]["renk_koyu"] == "#112233"


def test_formdaki_hatalar_alan_alan_doner():
    with pytest.raises(profil.ProfilHatasi) as e:
        profil.formdan({"isletme_adi": "", "renk_koyu": "kirmizi", "site": "ftp://x", "saat_dilimi": "Mars/Base",
                        "para_birimi": "naira", "site_para_birimi": "USD"})
    assert {"isletme_adi", "renk_koyu", "site", "saat_dilimi", "para_birimi"} <= set(e.value.alanlar)


def test_ayni_para_biriminde_kur_gerekmez():
    p = profil.formdan({**FORM, "site_para_birimi": "NGN", "kur": ""})
    assert p["doviz_kurlari"] == {}


def test_kimlik_uretimi_benzersiz():
    assert profil.kimlik_uret("Oak & Ember Living") == "oak-ember-living"
    assert profil.kimlik_uret("Çiçek Mobilya", {"cicek-mobilya"}) == "cicek-mobilya-2"


def test_yerel_belirtec_dogrulanir_ve_sahtesi_reddedilir():
    b = guvenlik.yerel_belirtec("A@b.co")
    k = guvenlik.kullanici_dogrula("Bearer " + b)
    assert k["eposta"] == "A@b.co" and k["id"] == guvenlik.kullanici_dogrula("Bearer " + guvenlik.yerel_belirtec("a@B.co"))["id"]
    sahte = jwt.encode({"sub": "x", "aud": "authenticated"}, "baska-sir", algorithm="HS256")
    with pytest.raises(guvenlik.YetkiHatasi):
        guvenlik.kullanici_dogrula("Bearer " + sahte)
    with pytest.raises(guvenlik.YetkiHatasi):
        guvenlik.kullanici_dogrula(None)


def test_sifreleme_ve_state():
    s = guvenlik.sifrele({"page_token": "GIZLI"})
    assert "GIZLI" not in s and guvenlik.coz(s) == {"page_token": "GIZLI"}
    st = guvenlik.imzala({"mid": "m1"}, 60)
    assert guvenlik.imza_coz(st)["mid"] == "m1"
    govde, imza = st.rsplit(".", 1)
    with pytest.raises(guvenlik.YetkiHatasi):
        guvenlik.imza_coz(govde[:-2] + "xx." + imza)
    with pytest.raises(guvenlik.YetkiHatasi):
        guvenlik.imza_coz(guvenlik.imzala({"mid": "m1"}, -1))
