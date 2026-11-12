"""Yayin planlama, otomatik onay, yayinlama, geri cekme ve Meta hata durumlari.
Meta'ya hic istek gitmez: ofis.meta fonksiyonlari sahteleriyle degistirilir."""
import json
from datetime import datetime

import pytest

from ofis import meta, yayin
from ofis.ayarlar import CIKTI

SABIT_AN = datetime(2026, 11, 12, 10, 0, tzinfo=yayin.YEREL)      # Persembe 10:00 yerel saat


@pytest.fixture(autouse=True)
def ortam(cikti_temiz, monkeypatch):
    monkeypatch.setattr(yayin, "simdi", lambda: SABIT_AN)
    yayin.ayar_kaydet({"otomatik": True, "fb_meta_planla": True})


def icerik(ad="2026-11-12_1200_Urun_post", tur="post", kk_uyari=False, carousel=0, dosyalar=True, yayin_json=None):
    k = CIKTI / ad
    k.mkdir(parents=True)
    (k / "meta.json").write_text(json.dumps({"format": tur, "kk_uyari": kk_uyari}), encoding="utf-8")
    (k / "caption.txt").write_text("Hello #test", encoding="utf-8")
    if dosyalar:
        for f in ("post_1080x1350.jpg", "story_1080x1920.jpg", "reels_1080x1920.mp4"):
            (k / f).write_bytes(b"x")
    for i in range(1, carousel + 1):
        (k / f"carousel_{i}.jpg").write_bytes(b"x")
    if yayin_json is not None:
        (k / "yayin.json").write_text(json.dumps(yayin_json), encoding="utf-8")
    return ad


class SahteMeta:
    """Cagrilari kaydeden sahte Meta. hata={'ig_post': 'mesaj'} ile istenen hedef hata verir."""
    def __init__(self, monkeypatch, hata=None, sil_hata=None, ig=True):
        self.cagri, self.silinen, self.hata, self.sil_hata = [], [], hata or {}, sil_hata
        self._sayac = 0
        monkeypatch.setattr(meta, "bagli", lambda: True)
        monkeypatch.setattr(meta, "ayar", lambda: {"page_token": "t", "page_id": "p", "ig_id": "ig" if ig else None})
        for ad in ("ig_post", "ig_story", "ig_reels", "ig_carousel", "fb_post", "fb_story", "fb_reels", "fb_carousel"):
            monkeypatch.setattr(meta, ad, self._islem(ad))
        monkeypatch.setattr(meta, "sil", self._sil)

    def _islem(self, ad):
        def f(*a, **k):
            self.cagri.append((ad, a, k))
            if ad in self.hata:
                raise meta.MetaHata(self.hata[ad])
            self._sayac += 1
            return {"id": f"{ad}-{self._sayac}"}
        return f

    def _sil(self, nesne_id):
        if self.sil_hata:
            raise meta.MetaHata(self.sil_hata)
        self.silinen.append(nesne_id)
        return True


# ---------------- planlama ----------------
def test_onerilen_zaman_formatin_saati_ve_gecmisse_bos():
    assert yayin.onerilen_zaman("2026-11-12", "post") == "2026-11-12T12:00"
    assert yayin.onerilen_zaman("2026-11-12", "reels") == "2026-11-12T18:30"
    assert yayin.onerilen_zaman("2026-11-11", "post") == ""          # dun -> hemen


def test_uretim_sonu_asla_onaylamaz():
    k = icerik()
    y = yayin.bekliyor_isaretle(k, "2026-11-12", "post")
    assert y["durum"] == "bekliyor" and "onay" not in y
    assert y["hedefler"] == ["ig_post", "fb_post", "ig_story"]


def test_carousel_hazirsa_post_yerine_carousel():
    k = icerik(carousel=3)
    assert "ig_carousel" in yayin.varsayilan_hedefler(k) and "ig_post" not in yayin.varsayilan_hedefler(k)


def test_mesai_saatleri():
    assert yayin.mesai_icinde(SABIT_AN.replace(hour=8, minute=0))
    assert not yayin.mesai_icinde(SABIT_AN.replace(hour=7, minute=59))
    assert not yayin.mesai_icinde(SABIT_AN.replace(hour=19, minute=0))


def test_mesai_disina_dusen_otomatik_icerik_mesaiye_cekilir():
    k = icerik(tur="reels", yayin_json={"durum": "bekliyor", "zaman": "2026-11-12T19:00", "format": "reels",
                                         "hedefler": ["ig_reels"]})
    assert yayin.mesaiye_uydur(gunluk=lambda *_: None) == [k]
    assert yayin.oku(k)["zaman"] == "2026-11-12T18:30"


def test_elle_verilen_saate_dokunulmaz():
    k = icerik(yayin_json={"durum": "onaylandi", "zaman": "2026-11-12T19:30", "hedefler": ["ig_post"],
                           "onay": {"zaman": "x", "kaynak": "ofis_ekrani"}})
    assert yayin.mesaiye_uydur(gunluk=lambda *_: None) == []
    assert yayin.oku(k)["zaman"] == "2026-11-12T19:30"


# ---------------- otomatik onay ----------------
def test_otomatik_aday_kurallari():
    temiz = icerik("a_post", yayin_json={"durum": "bekliyor", "zaman": "2026-11-12T12:00", "hedefler": ["ig_post"]})
    icerik("b_post", kk_uyari=True, yayin_json={"durum": "bekliyor", "zaman": "2026-11-12T12:00", "hedefler": ["ig_post"]})
    icerik("c_post", yayin_json={"durum": "bekliyor", "zaman": "2026-11-12T09:00", "hedefler": ["ig_post"]})
    icerik("d_post", yayin_json={"durum": "bekliyor", "zaman": "2026-11-12T12:00", "hedefler": ["ig_post"],
                                 "otomatik_kapali": True})
    assert yayin.otomatik_adaylar() == [temiz]


def test_otomatik_yayin_kapaliysa_aday_yok():
    icerik(yayin_json={"durum": "bekliyor", "zaman": "2026-11-12T12:00", "hedefler": ["ig_post"]})
    yayin.ayar_kaydet({"otomatik": False})
    assert yayin.otomatik_adaylar() == []


def test_otomatik_onay_kaynagi_kaydedilir():
    k = icerik(yayin_json={"durum": "bekliyor", "zaman": "2026-11-12T12:00", "hedefler": ["ig_post"]})
    y = yayin.otomatik_onayla(k)
    assert y["durum"] == "onaylandi" and y["onay"]["kaynak"] == "otomatik" and y["caption"] == "Hello #test"


# ---------------- yayinlama ----------------
def test_onaysiz_icerik_yayinlanmaz(monkeypatch):
    m = SahteMeta(monkeypatch)
    k = icerik(yayin_json={"durum": "bekliyor", "hedefler": ["ig_post"]})
    with pytest.raises(PermissionError):
        yayin.yayinla(k, gunluk=lambda *_: None)
    assert m.cagri == []


def test_basarili_yayin(monkeypatch):
    m = SahteMeta(monkeypatch)
    k = icerik()
    yayin.onayla(k, ["ig_post", "fb_post", "ig_story"], "", "Metin #a")
    y = yayin.yayinla(k, gunluk=lambda *_: None)
    assert y["durum"] == "yayinlandi"
    assert [c[0] for c in m.cagri] == ["ig_post", "fb_post", "ig_story"]
    assert all(y["sonuc"][h]["id"] for h in y["hedefler"])


def test_kismi_hata_kismen_olarak_isaretlenir_ve_tekrar_denemede_basarili_atlanir(monkeypatch):
    m = SahteMeta(monkeypatch, hata={"fb_post": "Temporary error (kod 2)"})
    k = icerik()
    yayin.onayla(k, ["ig_post", "fb_post"], "", "Metin")
    y = yayin.yayinla(k, gunluk=lambda *_: None)
    assert y["durum"] == "kismen" and "hata" in y["sonuc"]["fb_post"]
    m.hata.clear()
    assert yayin.tekrar_dene(k)["durum"] == "onaylandi"         # kullanici "Tekrar dene" dedi
    y = yayin.yayinla(k, gunluk=lambda *_: None)
    assert y["durum"] == "yayinlandi"
    assert [c[0] for c in m.cagri].count("ig_post") == 1        # ayni yere iki kez paylasilmaz


def test_dosya_eksikse_hata_meta_cagrilmaz(monkeypatch):
    m = SahteMeta(monkeypatch)
    k = icerik(dosyalar=False)
    yayin.onayla(k, ["ig_post"], "", "x")
    y = yayin.yayinla(k, gunluk=lambda *_: None)
    assert y["durum"] == "hata" and "bulunamadi" in y["sonuc"]["ig_post"]["hata"] and m.cagri == []


def test_instagram_hesabi_bagli_degilse_ig_hedefi_atlanir(monkeypatch):
    m = SahteMeta(monkeypatch, ig=False)
    k = icerik()
    yayin.onayla(k, ["ig_post", "fb_post"], "", "x")
    y = yayin.yayinla(k, gunluk=lambda *_: None)
    assert y["durum"] == "kismen" and [c[0] for c in m.cagri] == ["fb_post"]


def test_meta_baglantisi_yoksa_yayinlanmaz(monkeypatch):
    monkeypatch.setattr(meta, "bagli", lambda: False)
    k = icerik()
    yayin.onayla(k, ["ig_post"], "", "x")
    with pytest.raises(RuntimeError):
        yayin.yayinla(k, gunluk=lambda *_: None)


def test_hashtag_siniri_30():
    metin = " ".join(f"#h{i}" for i in range(40))
    assert yayin._hashtag_siniri(metin).count("#") == 30


# ---------------- geri cekme / kaldirma ----------------
def test_kaldir_yayindakileri_meta_dan_siler(monkeypatch):
    m = SahteMeta(monkeypatch)
    k = icerik()
    yayin.onayla(k, ["ig_post", "fb_post"], "", "x")
    yayin.yayinla(k, gunluk=lambda *_: None)
    y = yayin.kaldir(k)
    assert y["durum"] == "kaldirildi" and y["otomatik_kapali"] is True
    assert sorted(m.silinen) == sorted(r["id"] for r in y["sonuc"].values())


def test_kaldirma_hatasi_kaydedilir_ve_bildirilir(monkeypatch):
    m = SahteMeta(monkeypatch)
    k = icerik()
    yayin.onayla(k, ["ig_post"], "", "x")
    yayin.yayinla(k, gunluk=lambda *_: None)
    m.sil_hata = "Unsupported delete request (kod 100)"
    with pytest.raises(RuntimeError):
        yayin.kaldir(k)
    y = yayin.oku(k)
    assert y["durum"] == "kaldirma_hatasi" and "kaldir_hata" in y["sonuc"]["ig_post"]


def test_geri_al_facebook_planini_iptal_eder(monkeypatch):
    m = SahteMeta(monkeypatch)
    k = icerik(yayin_json={"durum": "onaylandi", "zaman": "2026-11-12T12:00", "hedefler": ["fb_post"],
                           "onay": {"zaman": "x", "kaynak": "otomatik"},
                           "sonuc": {"fb_post": {"id": "plan-1", "planli": True}}})
    y = yayin.geri_al(k)
    assert y["durum"] == "bekliyor" and y["otomatik_kapali"] and m.silinen == ["plan-1"] and y["sonuc"] == {}


def test_yayinlanmis_icerik_tekrar_onaylanamaz(monkeypatch):
    SahteMeta(monkeypatch)
    k = icerik()
    yayin.onayla(k, ["ig_post"], "", "x")
    yayin.yayinla(k, gunluk=lambda *_: None)
    with pytest.raises(ValueError):
        yayin.onayla(k, ["ig_post"], "", "x")


# ---------------- Meta planlayici ve engel durumlari ----------------
def test_facebook_meta_planlayicisina_gonderilir(monkeypatch):
    m = SahteMeta(monkeypatch)
    k = icerik(yayin_json={"durum": "onaylandi", "zaman": "2026-11-12T12:00", "hedefler": ["fb_post", "ig_post"],
                           "onay": {"zaman": "x", "kaynak": "otomatik"}})
    assert yayin.meta_planlanacaklar() == [k]
    y = yayin.meta_planla(k, gunluk=lambda *_: None)
    assert y["sonuc"]["fb_post"]["planli"] is True
    ad, args, _ = m.cagri[0]
    assert ad == "fb_post" and args[2] == SABIT_AN.replace(hour=12).timestamp()   # yerel saatle unix
    assert "ig_post" not in y["sonuc"]           # Instagram saatinde buradan yayinlanir


def test_planlanamayan_hedef_engel_degilse_tekrar_denenmez(monkeypatch):
    SahteMeta(monkeypatch, hata={"fb_post": "Invalid parameter (kod 100)"})
    k = icerik(yayin_json={"durum": "onaylandi", "zaman": "2026-11-12T12:00", "hedefler": ["fb_post"],
                           "onay": {"zaman": "x", "kaynak": "otomatik"}})
    yayin.meta_planla(k, gunluk=lambda *_: None)
    assert "plan_hata" in yayin.oku(k)["sonuc"]["fb_post"]
    assert yayin.meta_planlanacaklar() == []


def test_engel_kalkinca_otomatik_icerik_tekrar_kuyruga(monkeypatch):
    k = icerik(yayin_json={"durum": "hata", "zaman": "2026-11-12T09:30", "hedefler": ["ig_post"],
                           "onay": {"zaman": "x", "kaynak": "otomatik"},
                           "sonuc": {"ig_post": {"hata": "MetaHata: API access blocked. (kod 200)"}}})
    yayin.engel_sonrasi_tekrar()
    y = yayin.oku(k)
    assert y["durum"] == "onaylandi" and y["sonuc"] == {}


def test_cok_gecikmis_otomatik_icerik_kacirildi_olur():
    k = icerik(yayin_json={"durum": "onaylandi", "zaman": "2026-11-12T07:00", "hedefler": ["ig_post"],
                           "onay": {"zaman": "x", "kaynak": "otomatik"}})
    assert yayin.kacirilanlari_isaretle() == [k]
    assert yayin.oku(k)["durum"] == "kacirildi"


# ---------------- saat dilimi ----------------
def test_pasifik_farki_yerel_saat_dilimine_gore():
    from datetime import date
    assert yayin.pasifik_wat_farki(date(2026, 7, 1)) == 8      # Lagos UTC+1, PDT UTC-7
    assert yayin.pasifik_wat_farki(date(2026, 12, 1)) == 9     # PST UTC-8
