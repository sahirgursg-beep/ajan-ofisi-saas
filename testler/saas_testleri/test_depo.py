"""Yerel depo: icerik surumleri, is kuyrugu (musteri basina tek is), pano, imzali dosya adresleri."""
import time

import pytest

from saas.depo import Cakisma


def _musteri(d, mid="m1"):
    return d.musteri_ekle({"id": mid, "ad": mid, "profil": {"isletme": {}}, "durum": "deneme"})


def test_musteri_ve_uyelik(d):
    _musteri(d)
    with pytest.raises(Cakisma):
        _musteri(d)
    d.uyelik_ekle("u1", "m1", "sahip", "a@b.c")
    assert d.uye_mi("u1", "m1") and not d.uye_mi("u2", "m1")
    assert not d.uye_mi("u1", "m1", ("editor",))
    assert d.musteri_guncelle("m1", durum="aktif")["durum"] == "aktif"


def test_icerik_iyimser_kilit(d):
    _musteri(d)
    assert d.icerik_yaz("m1", {"klasor": "k1", "yayin": {"durum": "bekliyor"}}) == 1
    assert d.icerik_yaz("m1", {"klasor": "k1", "yayin": {"durum": "onaylandi"}}, beklenen_surum=1) == 2
    with pytest.raises(Cakisma):
        d.icerik_yaz("m1", {"klasor": "k1", "yayin": {"durum": "x"}}, beklenen_surum=1)
    assert d.icerik_al("m1", "k1")["yayin"] == {"durum": "onaylandi"}


def test_ayni_musteride_ayni_anda_tek_is(d):
    _musteri(d, "m1"), _musteri(d, "m2")
    a = d.is_ekle("m1", "uret")
    d.is_ekle("m1", "yayin_turu")
    c = d.is_ekle("m2", "uret")
    assert d.is_al("i1")["id"] == a["id"]
    assert d.is_al("i2")["id"] == c["id"]          # m1 mesgul, m2 alinir
    assert d.is_al("i3") is None                    # m1'in ikinci isi m1 bitmeden alinmaz
    d.is_bitir(a["id"], "bitti", "ok")
    assert d.is_al("i3")["tur"] == "yayin_turu"


def test_coken_iscinin_isi_yeniden_kuyruga(d):
    _musteri(d)
    a = d.is_ekle("m1", "uret")
    d.is_al("i1")
    with d._baglan() as c:
        c.execute("UPDATE isler SET baslama='2000-01-01T00:00:00+00:00' WHERE id=?", (a["id"],))
    assert d.is_al("i2", zaman_asimi_dk=60)["id"] == a["id"]


def test_bilinmeyen_is_turu(d):
    _musteri(d)
    with pytest.raises(ValueError):
        d.is_ekle("m1", "rm -rf")


def test_pano_sirali(d):
    _musteri(d)
    d.pano_ekle("m1", [{"gonderen": "A", "alici": "B", "icerik": str(i)} for i in range(5)])
    son = d.pano_son("m1", 3)
    assert [m["icerik"] for m in son] == ["2", "3", "4"]
    assert d.pano_son("m1", 10, sonra=son[-1]["id"]) == []


def test_imzali_dosya_adresi(d, tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    d.dosya_yukle("m1/cikti/k/a.jpg", f)
    adres = d.dosya_adresi("m1/cikti/k/a.jpg", 60)
    son = int(adres.split("son=")[1].split("&")[0])
    imza = adres.split("imza=")[1]
    assert d.imzali_oku("m1/cikti/k/a.jpg", son, imza)
    assert d.imzali_oku("m1/cikti/k/a.jpg", son, "0" * 32) is None
    assert d.imzali_oku("m1/cikti/k/a.jpg", int(time.time()) - 1, imza) is None
    with pytest.raises(ValueError):
        d.dosya_yukle("../disari.jpg", f)
