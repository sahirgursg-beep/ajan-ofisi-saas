"""Yonetim paneli: yalnizca yoneticiler; ozet, musteri detayi, durum/deneme/otopilot/uretim islemleri."""
import json

import requests

from .conftest import FORM, oturum

PATRON = "patron@feedzync.test"


def _kur(sunucu, eposta="sahip@a.test"):
    H = oturum(sunucu, eposta)
    m = requests.post(sunucu + "/api/musteri", headers=H, json=FORM).json()
    return H, m["id"]


def test_yonetici_olmayan_goremez(sunucu, d):
    H, mid = _kur(sunucu)
    for yol in ("/api/yonetim/ozet", "/api/yonetim/isler", f"/api/yonetim/musteri/{mid}"):
        assert requests.get(sunucu + yol, headers=H).status_code == 404
        assert requests.get(sunucu + yol).status_code == 401
    assert requests.post(f"{sunucu}/api/yonetim/musteri/{mid}/durum", headers=H, json={"durum": "aktif"}).status_code == 404
    assert requests.get(sunucu + "/yonetim").status_code == 200          # sayfa acik, veri yetkiye bagli
    assert requests.get(sunucu + "/api/ben", headers=H).json()["kullanici"]["yonetici"] is False


def test_yonetici_ozet_ve_islemler(sunucu, d):
    H, mid = _kur(sunucu)
    d.dosyalar.joinpath(mid).mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    ay = datetime.now(timezone.utc).strftime("%Y-%m")
    (d.dosyalar / mid / "harcama.json").write_text(json.dumps({ay: 1.25, "_kalemler": {ay: {"metin_yz": {"adet": 40, "usd": 1.25}}}}))
    P = oturum(sunucu, PATRON)
    assert requests.get(sunucu + "/api/ben", headers=P).json()["kullanici"]["yonetici"] is True
    o = requests.get(sunucu + "/api/yonetim/ozet", headers=P).json()
    assert o["sayilar"]["toplam"] == 1 and o["sayilar"]["deneme"] == 1 and o["harcama_bu_ay"] == 1.25
    satir = o["musteriler"][0]
    assert satir["sahipler"] == ["sahip@a.test"] and satir["harcama"]["kalemler"]["metin_yz"]["adet"] == 40

    eski = d.musteri_al(mid)["deneme_bitis"]
    r = requests.post(f"{sunucu}/api/yonetim/musteri/{mid}/deneme_uzat", headers=P, json={"gun": 14})
    assert r.status_code == 200 and d.musteri_al(mid)["deneme_bitis"] > eski
    assert requests.post(f"{sunucu}/api/yonetim/musteri/{mid}/durum", headers=P, json={"durum": "aktif"}).status_code == 200
    assert d.musteri_al(mid)["durum"] == "aktif"
    assert requests.post(f"{sunucu}/api/yonetim/musteri/{mid}/durum", headers=P, json={"durum": "x"}).status_code == 400
    requests.post(f"{sunucu}/api/yonetim/musteri/{mid}/otomatik", headers=P, json={"otomatik": False})
    assert d.musteri_al(mid)["yayin_ayar"]["otomatik"] is False
    assert requests.post(f"{sunucu}/api/yonetim/musteri/{mid}/uret", headers=P, json={}).status_code == 200
    assert d.isler(mid)[0]["tur"] == "uret"
    detay = requests.get(f"{sunucu}/api/yonetim/musteri/{mid}", headers=P).json()
    assert detay["isler"] and detay["profil"]["isletme_adi"] == FORM["isletme_adi"]
    assert requests.get(sunucu + "/api/yonetim/isler?durum=bekliyor", headers=P).json()["isler"][0]["musteri_id"] == mid


def test_yonetici_musteri_panelini_destek_icin_acar(sunucu, d):
    H, mid = _kur(sunucu)
    P = oturum(sunucu, PATRON)
    ben = requests.get(sunucu + "/api/ben", headers=P, params={"musteri": mid}).json()
    assert ben["musteriler"][0]["id"] == mid and ben["musteriler"][0]["rol"] == "yonetici"
    assert requests.get(f"{sunucu}/api/musteri/{mid}/icerikler", headers=P).status_code == 200
    yabanci = oturum(sunucu, "yabanci@b.test")
    assert requests.get(sunucu + "/api/ben", headers=yabanci, params={"musteri": mid}).json()["musteriler"] == []
