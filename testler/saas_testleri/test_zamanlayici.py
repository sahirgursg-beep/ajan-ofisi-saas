"""Zamanlayici: her musterinin kendi saat diliminde mesai, gunluk uretim ve deneme suresi."""
from datetime import datetime, timezone

from saas import guvenlik, profil, zamanlayici

from .conftest import FORM


def _m(d, mid, tzad="Africa/Lagos", **ek):
    p = profil.formdan({**FORM, "saat_dilimi": tzad})
    return d.musteri_ekle({"id": mid, "ad": mid, "profil": p, "durum": "deneme",
                           "meta_token": guvenlik.sifrele({"page_id": "1"}), **ek})


def test_yerel_saate_gore_isler(d):
    _m(d, "lagos")                                   # UTC+1
    _m(d, "nairobi", "Africa/Nairobi")              # UTC+3
    an = datetime(2026, 11, 12, 6, 30, tzinfo=timezone.utc)   # Lagos 07:30 (mesai disi), Nairobi 09:30
    r = zamanlayici.tur(an, tetikle=False)
    assert r["yayin_turu"] == ["nairobi"] and r["uret"] == ["nairobi"]
    an = datetime(2026, 11, 12, 7, 30, tzinfo=timezone.utc)   # Lagos 08:30
    r = zamanlayici.tur(an, tetikle=False)
    assert set(r["yayin_turu"]) == {"lagos", "nairobi"} and set(r["uret"]) == {"lagos", "nairobi"}
    assert sum(1 for i in d.isler("nairobi") if i["tur"] == "uret") == 1     # bekleyen is varken ikincisi acilmaz


def test_bugun_uretildiyse_tekrar_uretmez(d):
    _m(d, "lagos", son_uretim="2026-11-12")
    r = zamanlayici.tur(datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc), tetikle=False)
    assert r["uret"] == [] and r["yayin_turu"] == ["lagos"]


def test_meta_bagli_degilse_hicbir_is_yok(d):
    d.musteri_ekle({"id": "bos", "ad": "bos", "profil": profil.formdan(FORM), "durum": "deneme"})
    r = zamanlayici.tur(datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc), tetikle=False)
    assert r == {"duraklatilan": [], "yayin_turu": [], "uret": []}


def test_deneme_bitince_duraklatilir_aktif_etkilenmez(d):
    _m(d, "biten", deneme_bitis="2026-11-01T00:00:00+00:00")
    _m(d, "odeyen", deneme_bitis="2026-11-01T00:00:00+00:00")
    d.musteri_guncelle("odeyen", durum="aktif")
    r = zamanlayici.tur(datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc), tetikle=False)
    assert r["duraklatilan"] == ["biten"] and d.musteri_al("biten")["durum"] == "duraklatildi"
    assert "odeyen" in r["yayin_turu"]


def test_iki_kez_basarisiz_uretim_gun_boyu_tekrarlanmaz(d):
    _m(d, "lagos")
    for _ in range(2):
        i = d.is_ekle("lagos", "uret")
        d.is_al("x")
        d.is_bitir(i["id"], "hata", "patladi")
    r = zamanlayici.tur(datetime.now(timezone.utc).replace(hour=9), tetikle=False)
    assert r["uret"] == []
