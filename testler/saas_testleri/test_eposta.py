"""Sahip e-postalari: anahtar yoksa sessiz; pazartesi ozeti haftada bir; deneme hatirlatmasi bir kez; dil."""
from datetime import datetime, timezone

from saas import eposta


class Http:
    def __init__(self):
        self.giden = []

    def post(self, url, **k):
        self.giden.append(k["json"])
        return type("R", (), {"status_code": 200})()


def _kur(d, dil="tr", durum="deneme", bitis="2026-11-18T07:00:00+00:00"):
    d.musteri_ekle({"id": "m1", "ad": "Luna Fırın", "durum": durum, "deneme_bitis": bitis,
                    "profil": {"isletme": {"dil": dil, "saat_dilimi": "Europe/Istanbul"}}})
    with d._baglan() as c:
        c.execute("INSERT INTO uyelikler (kullanici_id, musteri_id, rol, eposta) VALUES ('u1','m1','sahip','sahip@luna.test')")
        c.execute("INSERT INTO uyelikler (kullanici_id, musteri_id, rol, eposta) VALUES ('u2','m1','izleyici','izleyici@luna.test')")


def test_anahtar_yoksa_hic_gondermez(d, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    _kur(d)
    assert eposta.tur(d, datetime(2026, 11, 16, 7, 30, tzinfo=timezone.utc)) == {"ozet": [], "deneme": []}


def test_pazartesi_ozeti_ve_deneme_hatirlatmasi_bir_kez(d, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    http = Http()
    monkeypatch.setattr(eposta, "requests", http)
    _kur(d)
    d.icerik_yaz("m1", {"klasor": "2026-11-17_1100_A_post", "tur": "post", "meta": {"kk_uyari": ["x"]},
                        "yayin": {"durum": "bekliyor"}, "caption": "", "ekler": {}, "dosyalar": []})
    pazartesi = datetime(2026, 11, 16, 7, 30, tzinfo=timezone.utc)      # Istanbul 10:30
    assert eposta.tur(d, pazartesi) == {"ozet": ["m1"], "deneme": ["m1"]}
    ozet, deneme = http.giden
    assert ozet["to"] == ["sahip@luna.test"] and ozet["subject"] == "Sosyal medyada haftanız"
    assert "Kısa bakış gereken" in ozet["html"] and "Luna Fırın" in ozet["html"]
    assert deneme["subject"] == "Ücretsiz denemeniz 2 gün sonra bitiyor"
    assert eposta.tur(d, pazartesi.replace(minute=50)) == {"ozet": [], "deneme": []}   # ayni hafta tekrar yok
    assert len(http.giden) == 2


def test_arapca_e_posta_sagdan_sola(d, monkeypatch):
    _kur(d, dil="ar", durum="aktif")
    konu, govde = eposta.haftalik_ozet(d, d.musteri_al("m1"), datetime(2026, 11, 16, 9, tzinfo=timezone.utc))
    assert 'dir="rtl"' in govde and konu == "أسبوعك على السوشيال ميديا"
