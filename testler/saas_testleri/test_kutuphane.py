"""Ortak kutuphane: tepkilerden ogrenim, depoya kalicilik, haftalik Kutuphaneci zamanlamasi."""
import json
from datetime import datetime, timezone

from saas import kutuphane


def _musteri(d, mid, sektor="bakery", dil="fr"):
    d.musteri_ekle({"id": mid, "ad": mid, "durum": "aktif",
                    "profil": {"isletme": {"sektor": sektor, "dil": dil}}})


def _icerik(d, mid, klasor, durum, font, muzik_id=None, kaynak=None):
    yayin = {"durum": durum}
    if kaynak:
        yayin["onay"] = {"kaynak": kaynak}
    d.icerik_yaz(mid, {"klasor": klasor, "tur": "post", "meta": {"ozellikler": {"fontlar": font, "duzen": "kemer"}},
                       "yayin": yayin, "caption": "x", "ekler": {"muzik.json": json.dumps({"id": muzik_id})} if muzik_id else {},
                       "dosyalar": []})


def test_tepkilerden_ortak_ogrenim(d):
    _musteri(d, "musteri-alfa"), _musteri(d, "musteri-beta", sektor="gym", dil="ar")
    _icerik(d, "musteri-alfa", "1_post", "yayinlandi", "klasik", "m1")
    _icerik(d, "musteri-alfa", "2_post", "reddedildi", "afis", "m2")
    _icerik(d, "musteri-beta", "3_post", "onaylandi", "klasik", kaynak="panel")
    _icerik(d, "musteri-beta", "4_post", "bekliyor", "afis")                      # tepki yok: sayilmaz
    o = kutuphane.ogrenim_topla(d)
    assert o["ozellik"]["fontlar"]["klasik"] == {"skor": 1.0, "n": 2}
    assert o["ozellik"]["fontlar"]["afis"] == {"skor": -2.0, "n": 1}
    assert o["sektor"]["bakery"]["fontlar"]["afis"]["skor"] == -2.0
    assert o["muzik"]["m1"]["skor"] == 1.0 and o["muzik"]["m2"]["skor"] == -2.0
    assert o["platform"] == {"sektorler": {"bakery": 1, "gym": 1}, "diller": {"fr": 1, "ar": 1}}
    assert "musteri-" not in json.dumps(o)                                # musteri kimligi yazilmaz


def test_kutuphane_depoda_kalici_ve_degisenler_yuklenir(d, tmp_path):
    kok = tmp_path / "paylasilan"
    (kok / "muzik" / "otomatik").mkdir(parents=True)
    (kok / "muzik" / "otomatik" / "a.mp3").write_bytes(b"1" * 500)
    (kok / "muzik" / "otomatik" / "kutuphane.json").write_text("[]")
    (kok / "takvimler").mkdir()
    (kok / "takvimler" / "GLOBAL.json").write_text("{}")                 # repodan gelir, depoya yazilmaz
    assert kutuphane.yukle(kok, d) == (2, 0)
    assert kutuphane.yukle(kok, d) == (0, 0)                              # degisiklik yok: yukleme yok
    (kok / "muzik" / "otomatik" / "a.mp3").unlink()                       # emekli parca
    assert kutuphane.yukle(kok, d) == (0, 1)
    yeni = tmp_path / "yeni_isci"
    assert kutuphane.indir(yeni, d) == 1 and (yeni / "muzik" / "otomatik" / "kutuphane.json").exists()
    assert not (yeni / "takvimler").exists()


def test_kutuphaneci_haftada_bir_sessiz_saatte_ya_da_zorla(d, tmp_path, monkeypatch):
    calisti = []
    monkeypatch.setattr(kutuphane, "kutuphaneci_calistir", lambda kok: calisti.append(1) or True)
    kok = tmp_path / "p"
    gunduz = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)
    assert kutuphane.gerekirse(kok, d, gunduz) == ["ogrenim"]            # ogrenim gunluk, buyuk is gece
    assert (kok / "ogrenim" / "ortak.json").exists()
    gece = datetime(2026, 11, 14, 2, 0, tzinfo=timezone.utc)
    assert kutuphane.gerekirse(kok, d, gece) == ["kutuphaneci"]             # ogrenim 12 saat once yapildi
    assert kutuphane.gerekirse(kok, d, datetime(2026, 11, 16, 2, 0, tzinfo=timezone.utc)) == ["ogrenim"]
    kutuphane.zorla(d)
    assert kutuphane.gerekirse(kok, d, datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)) == ["ogrenim", "kutuphaneci"]
    assert len(calisti) == 2 and not (d.json_oku(kutuphane.DURUM, {}) or {}).get("zorla")
    assert kutuphane.yonetim_ozeti(d)["durum"]["son_sonuc"] == "ok"


def test_yonetim_kutuphane_sadece_yoneticiye(sunucu, d):
    import requests
    from .conftest import oturum
    H = oturum(sunucu, "sahip@a.test")
    assert requests.get(sunucu + "/api/yonetim/kutuphane", headers=H).status_code == 404
    assert requests.post(sunucu + "/api/yonetim/kutuphane", headers=H, json={}).status_code == 404
    P = oturum(sunucu, "patron@feedzync.test")
    assert requests.get(sunucu + "/api/yonetim/kutuphane", headers=P).json()["durum"] == {}
    assert requests.post(sunucu + "/api/yonetim/kutuphane", headers=P, json={}).json()["durum"] == "ok"
    assert d.json_oku(kutuphane.DURUM)["zorla"] is True
