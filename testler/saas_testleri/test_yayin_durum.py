"""Panel kararlari: ofis/yayin.py kurallariyla ayni; Meta isleri isciye birakilir."""
from datetime import timezone

import pytest

from saas import yayin_durum as yd

TZ = timezone.utc


def test_onayla_ve_bos_hedef():
    y = yd.onayla({"durum": "bekliyor"}, ["ig_post", "x"], "2026-11-13T12:00", "Metin", TZ)
    assert y["durum"] == "onaylandi" and y["hedefler"] == ["ig_post"] and y["onay"]["kaynak"] == "panel"
    with pytest.raises(yd.KararHatasi):
        yd.onayla({"durum": "bekliyor"}, [], "", "Metin", TZ)
    with pytest.raises(yd.KararHatasi):
        yd.onayla({"durum": "bekliyor"}, ["ig_post"], "yarin", "Metin", TZ)


def test_yayindaki_icerik_tekrar_onaylanamaz():
    with pytest.raises(yd.KararHatasi):
        yd.onayla({"durum": "yayinlandi"}, ["ig_post"], "", "m", TZ)
    with pytest.raises(yd.KararHatasi):
        yd.onayla({"durum": "kismen", "sonuc": {"ig_post": {"id": "1"}}}, ["ig_post"], "", "m", TZ)


def test_planli_facebook_iptal_listesine_alinir():
    y = {"durum": "onaylandi", "onay": {}, "sonuc": {"fb_post": {"id": "p1", "planli": True}}}
    g = yd.geri_al(y, TZ)
    assert g["durum"] == "bekliyor" and g["otomatik_kapali"] and g["bekleyen_iptal"] == ["p1"] and g["sonuc"] == {}
    o = yd.onayla({"durum": "onaylandi", "sonuc": {"fb_post": {"id": "p2", "planli": True}}}, ["fb_post"], "", "m", TZ)
    assert o["bekleyen_iptal"] == ["p2"]


def test_kaldir_metada_bir_sey_yoksa_yerinde():
    y, gerek = yd.kaldir_istegi({"durum": "onaylandi", "onay": {}}, TZ)
    assert y["durum"] == "kaldirildi" and not gerek
    y, gerek = yd.kaldir_istegi({"durum": "yayinlandi", "sonuc": {"ig_post": {"id": "1"}}}, TZ)
    assert y["durum"] == "kaldiriliyor" and gerek


def test_revize_ve_tekrar():
    with pytest.raises(yd.KararHatasi):
        yd.revize_iste({"durum": "onaylandi"}, [], "x", TZ)
    with pytest.raises(yd.KararHatasi):
        yd.revize_iste({"durum": "bekliyor"}, [], "", TZ)
    assert yd.revize_iste({"durum": "bekliyor"}, ["acik"], "", TZ)["durum"] == "revize_isteniyor"
    assert yd.tekrar_dene({"durum": "kismen", "onay": {"z": 1}}) [1] == "yayin_turu"
    assert yd.tekrar_dene({"durum": "kaldirma_hatasi"})[1] == "kaldir"
    assert yd.tekrar_dene({"durum": "bekliyor"})[1] is None
