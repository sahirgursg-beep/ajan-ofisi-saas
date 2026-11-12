"""Web API: giris, musteri yalitimi, kayit, kararlar, Meta OAuth (sahte Graph ile), zamanlayici."""
import requests

from saas import ayar, guvenlik

from .conftest import FORM, oturum


def _kur(sunucu, eposta="sahip@a.test"):
    H = oturum(sunucu, eposta)
    m = requests.post(sunucu + "/api/musteri", headers=H, json=FORM).json()
    return H, m["id"]


def test_saglik_ve_yapilandirma(sunucu):
    assert requests.get(sunucu + "/saglik").json()["durum"] == "ok"
    y = requests.get(sunucu + "/api/yapilandirma").json()
    assert y["yerel_giris"] is True and "supabase_anon" in y and "SERVICE" not in str(y)
    r = requests.get(sunucu + "/")
    assert r.status_code == 200 and "Agent Office" in r.text and r.headers["X-Frame-Options"] == "DENY"


def test_girissiz_ve_yabanci_erisemez(sunucu, d):
    H, mid = _kur(sunucu)
    assert requests.get(f"{sunucu}/api/musteri/{mid}/icerikler").status_code == 401
    yabanci = oturum(sunucu, "yabanci@b.test")
    for yol in ("icerikler", "profil", "isler", "pano", "meta/baglan"):
        assert requests.get(f"{sunucu}/api/musteri/{mid}/{yol}", headers=yabanci).status_code == 404, yol
    assert requests.post(f"{sunucu}/api/musteri/{mid}/uret", headers=yabanci, json={}).status_code == 404
    assert requests.get(sunucu + "/api/ben", headers=yabanci).json()["musteriler"] == []


def test_izleyici_karar_veremez(sunucu, d):
    H, mid = _kur(sunucu)
    izleyici = oturum(sunucu, "izle@a.test")
    uid = guvenlik.kullanici_dogrula(izleyici["Authorization"])["id"]
    d.uyelik_ekle(uid, mid, "izleyici")
    assert requests.get(f"{sunucu}/api/musteri/{mid}/icerikler", headers=izleyici).status_code == 200
    assert requests.post(f"{sunucu}/api/musteri/{mid}/uret", headers=izleyici, json={}).status_code == 404


def test_kayit_hatali_form_ve_deneme_suresi(sunucu):
    H = oturum(sunucu)
    r = requests.post(sunucu + "/api/musteri", headers=H, json={"isletme_adi": "X", "renk_koyu": "mavi"})
    assert r.status_code == 422 and "renk_koyu" in r.json()["alanlar"]
    m = requests.post(sunucu + "/api/musteri", headers=H, json=FORM).json()
    assert m["durum"] == "deneme" and m["deneme_bitis"] and m["yayin_ayar"]["otomatik"] is True
    ikinci = requests.post(sunucu + "/api/musteri", headers=H, json=FORM).json()
    assert ikinci["id"] == m["id"] + "-2"


def test_karar_akisi_ve_surum_kontrolu(sunucu, d):
    H, mid = _kur(sunucu)
    d.icerik_yaz(mid, {"klasor": "2026-11-12_1200_X_post", "tur": "post", "caption": "Hi",
                       "yayin": {"durum": "bekliyor", "hedefler": ["ig_post"]}, "dosyalar": ["post_1080x1350.jpg"]})
    yol = f"{sunucu}/api/musteri/{mid}/icerik/2026-11-12_1200_X_post"
    r = requests.post(yol + "/onayla", headers=H, json={"surum": 1, "hedefler": ["ig_post", "fb_post"],
                                                         "zaman": "2026-11-13T12:00", "metin": "Yeni"})
    assert r.status_code == 200 and r.json()["yayin"]["durum"] == "onaylandi" and r.json()["is"] is None
    assert requests.post(yol + "/onayla", headers=H, json={"surum": 1, "hedefler": ["ig_post"]}).status_code == 409
    r = requests.post(yol + "/geri_al", headers=H, json={})
    assert r.json()["yayin"]["durum"] == "bekliyor"
    r = requests.post(yol + "/onayla", headers=H, json={"hedefler": ["ig_post"], "metin": "Simdi"})
    assert r.json()["is"]["tur"] == "yayin_turu"          # saatsiz onay -> hemen yayin turu
    assert requests.post(yol + "/bilinmeyen", headers=H, json={}).status_code == 404
    assert requests.post(f"{sunucu}/api/musteri/{mid}/icerik/..%2Fx/onayla", headers=H, json={}).status_code in (400, 404)
    v = requests.get(f"{sunucu}/api/musteri/{mid}/icerikler", headers=H).json()
    assert v["icerikler"][0]["dosyalar"]["post_1080x1350.jpg"].startswith("/yerel-dosya/")


def test_ayni_is_iki_kez_acilmaz(sunucu, d):
    H, mid = _kur(sunucu)
    a = requests.post(f"{sunucu}/api/musteri/{mid}/uret", headers=H, json={}).json()["is"]
    b = requests.post(f"{sunucu}/api/musteri/{mid}/uret", headers=H, json={}).json()["is"]
    assert a["id"] == b["id"] and len(d.isler(mid)) == 1


def test_duraklatilmis_hesap_uretemez(sunucu, d):
    H, mid = _kur(sunucu)
    d.musteri_guncelle(mid, durum="duraklatildi")
    assert requests.post(f"{sunucu}/api/musteri/{mid}/uret", headers=H, json={}).status_code == 402


def test_meta_oauth_akisi(sunucu, d, graph, monkeypatch):
    monkeypatch.setattr(ayar, "META_GRAPH", graph.adres)
    H, mid = _kur(sunucu)
    adres = requests.get(f"{sunucu}/api/musteri/{mid}/meta/baglan", headers=H).json()["adres"]
    assert "client_id=uygulama1" in adres and "instagram_content_publish" in adres
    state = adres.split("state=")[1].split("&")[0]
    from urllib.parse import unquote
    state = unquote(state)
    r = requests.get(f"{sunucu}/meta/geri", params={"code": "KOD", "state": state}, allow_redirects=False)
    assert r.status_code == 302 and "meta=sec" in r.headers["location"]
    m = d.musteri_al(mid)
    assert m["meta_token"] is None and "SAYFA111" not in (m["meta_aday"] or "")       # sifreli
    aday = requests.get(f"{sunucu}/api/musteri/{mid}/meta/adaylar", headers=H).json()["sayfalar"]
    assert [s["page_ad"] for s in aday] == ["Oak Page", "Third Page"]                   # yetkisiz sayfa elendi
    assert "token" not in str(aday)
    oz = requests.post(f"{sunucu}/api/musteri/{mid}/meta/sec", headers=H, json={"page_id": "111"}).json()
    assert oz["meta_bagli"] and oz["meta"]["ig_kullanici"] == "oakember"
    assert guvenlik.coz(d.musteri_al(mid)["meta_token"])["page_token"] == "SAYFA111"
    # kurcalanmis state
    r = requests.get(f"{sunucu}/meta/geri", params={"code": "KOD", "state": state[:-3] + "abc"}, allow_redirects=False)
    assert "gecersiz" in r.headers["location"]
    # baska kullanicinin state'i baska musteriye baglayamaz
    yabanci_state = guvenlik.imzala({"mid": mid, "uid": "baska-kullanici"})
    r = requests.get(f"{sunucu}/meta/geri", params={"code": "KOD", "state": yabanci_state}, allow_redirects=False)
    assert "gecersiz" in r.headers["location"]


def test_zamanlayici_anahtar_ister(sunucu, monkeypatch):
    monkeypatch.setattr(ayar, "ZAMANLAYICI_ANAHTARI", "z-anahtar")
    assert requests.post(sunucu + "/ic/zamanlayici").status_code == 401
    assert requests.post(sunucu + "/ic/zamanlayici", headers={"X-Zamanlayici-Anahtari": "z-anahtar"}).status_code == 200
