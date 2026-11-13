"""Panel yuklemeleri: fotograf/belge/logo, yalitim, isci birlestirmesi, sektor onerileri."""
import io
import json

import requests
from PIL import Image

from saas import isci, yukleme

from .conftest import FORM, oturum


def _kur(sunucu, eposta="sahip@a.test"):
    H = oturum(sunucu, eposta)
    m = requests.post(sunucu + "/api/musteri", headers=H, json=FORM).json()
    return H, m["id"]


def _jpg(w=640, h=480, renk=(200, 30, 30), exif_gps=False):
    b = io.BytesIO()
    im = Image.new("RGB", (w, h), renk)
    if exif_gps:
        ex = Image.Exif()
        ex[0x010F] = "PhoneMaker"       # meta veri: yeniden kodlamada atilmali
        im.save(b, "JPEG", exif=ex)
    else:
        im.save(b, "JPEG")
    return b.getvalue()


def test_fotograf_ve_belge_yukleme_listeleme_silme(sunucu, d):
    H, mid = _kur(sunucu)
    r = requests.post(f"{sunucu}/api/musteri/{mid}/yukle", headers=H, data={"not": "new sofa set"},
                      files=[("dosya", ("sofa.jpg", _jpg(exif_gps=True), "image/jpeg")),
                             ("dosya", ("menu.pdf", b"%PDF-1.4 test", "application/pdf"))])
    assert r.status_code == 200, r.text
    dosyalar = r.json()["dosyalar"]
    assert {x["tur"] for x in dosyalar} == {"gorsel", "belge"} and all(x["not"] == "new sofa set" for x in dosyalar)
    foto = next(x for x in dosyalar if x["tur"] == "gorsel")
    assert foto["adres"] and not foto["incelendi"]
    kayit = json.loads((d.dosyalar / mid / "yuklemeler" / "index.json").read_text())
    saklanan = d.dosyalar / mid / "yuklemeler" / next(k["dosya"] for k in kayit if k["tur"] == "gorsel")
    assert not Image.open(saklanan).getexif()             # telefon meta verisi silindi
    assert requests.post(f"{sunucu}/api/musteri/{mid}/yukleme/{foto['id']}/sil", headers=H).status_code == 200
    assert not saklanan.exists()
    assert len(requests.get(f"{sunucu}/api/musteri/{mid}/yuklemeler", headers=H).json()["dosyalar"]) == 1


def test_yanlis_tur_ve_yabanci_reddedilir(sunucu, d):
    H, mid = _kur(sunucu)
    r = requests.post(f"{sunucu}/api/musteri/{mid}/yukle", headers=H, files=[("dosya", ("x.exe", b"MZ", "x"))])
    assert r.status_code == 400 and "JPG" in r.json()["hata"]
    r = requests.post(f"{sunucu}/api/musteri/{mid}/yukle", headers=H, files=[("dosya", ("fake.jpg", b"nope", "image/jpeg"))])
    assert r.status_code == 400
    yabanci = oturum(sunucu, "yabanci@b.test")
    r = requests.post(f"{sunucu}/api/musteri/{mid}/yukle", headers=yabanci, files=[("dosya", ("a.jpg", _jpg(), "image/jpeg"))])
    assert r.status_code == 404
    assert requests.get(f"{sunucu}/api/musteri/{mid}/yuklemeler", headers=yabanci).status_code == 404


def test_logo_yukleme_renkleri_ve_profili_gunceller(sunucu, d):
    H, mid = _kur(sunucu)
    im = Image.new("RGBA", (300, 120), (0, 0, 0, 0))
    for x in range(20, 280):
        for y in range(20, 100):
            im.putpixel((x, y), (20, 60, 160, 255) if x < 150 else (230, 120, 20, 255))
    b = io.BytesIO()
    im.save(b, "PNG")
    r = requests.post(f"{sunucu}/api/musteri/{mid}/logo", headers=H, files=[("dosya", ("logo.png", b.getvalue(), "image/png"))])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["logo"] and j["renkler"]["renk_altin"] != "#C9A24B"
    m = d.musteri_al(mid)
    assert m["profil"]["marka"]["logo_yuklendi"] and m["profil"]["marka"]["logo"] == "marka/logo.png"
    assert (d.dosyalar / mid / "yuklemeler" / "logo.png").exists()
    assert requests.get(f"{sunucu}/api/musteri/{mid}/logo", headers=H).json()["logo"]


def test_sektor_onerileri_ve_tahmin(sunucu):
    s = requests.get(sunucu + "/api/sektorler").json()["sektorler"]
    restoran = next(x for x in s if x["anahtar"] == "restoran")
    assert "Finger food & catering" in restoran["isler"] and s[-1]["anahtar"] == "genel"
    assert requests.get(sunucu + "/api/sektor-tahmin", params={"metin": "we fix phones and laptops"}).json()["sektor"] == "elektronik"


def test_site_kontrolu_girisi_ister_ve_ic_agi_reddeder(sunucu):
    assert requests.post(sunucu + "/api/site-kontrol", json={"site": "example.com"}).status_code == 401
    H = oturum(sunucu)
    j = requests.post(sunucu + "/api/site-kontrol", headers=H, json={"site": "http://127.0.0.1:8800"}).json()
    assert j["tamam"] is False


def test_kayit_hizmet_secimiyle_tanim_olusur(sunucu):
    H = oturum(sunucu)
    r = requests.post(sunucu + "/api/musteri", headers=H, json={"isletme_adi": "Mama Put", "sektor": "restoran",
                                                                "hizmetler": ["Nigerian dishes", "Small chops & catering"]})
    assert r.status_code == 201, r.text
    p = requests.get(f"{sunucu}/api/musteri/{r.json()['id']}/profil", headers=H).json()["form"]
    assert p["hizmetler"] == ["Nigerian dishes", "Small chops & catering"] and "nigerian dishes" in p["tanim"]


def test_isci_yukleme_dizinini_guncel_dizinle_birlestirir(d, tmp_path):
    mid = "m1"
    d.json_yaz(f"{mid}/yuklemeler/index.json", [{"id": "a", "dosya": "a.jpg", "tur": "gorsel", "tarih": "1"}])
    (tmp_path / "x.jpg").write_bytes(_jpg())
    d.dosya_yukle(f"{mid}/yuklemeler/a.jpg", tmp_path / "x.jpg")
    kok = tmp_path / "kok"
    kok.mkdir()
    isci.yuklemeler_indir(d, mid, kok, "uret")
    assert (kok / "yuklemeler" / "a.jpg").exists()
    eski = isci._dizin_oku(kok)
    yerel = [dict(eski[0], analiz={"baslik": "Red sofa"}, kullanim=[{"tarih": "2026-11-13", "klasor": "k"}])]
    (kok / "yuklemeler" / "index.json").write_text(json.dumps(yerel))
    # is surerken panelden yeni bir dosya eklendi
    d.json_yaz(f"{mid}/yuklemeler/index.json", eski + [{"id": "b", "dosya": "b.jpg", "tur": "gorsel", "tarih": "2"}])
    isci.yuklemeler_geri_yaz(d, mid, kok, eski)
    son = d.json_oku(f"{mid}/yuklemeler/index.json")
    assert [k["id"] for k in son] == ["a", "b"] and son[0]["analiz"]["baslik"] == "Red sofa" and son[0]["kullanim"]


def test_logo_paleti():
    im = Image.new("RGB", (100, 100), (255, 255, 255))
    for x in range(10, 90):
        for y in range(10, 90):
            im.putpixel((x, y), (10, 10, 10) if x < 50 else (220, 30, 60))
    p = yukleme._palet(im)
    assert p["renk_koyu"] == "#0A0A0A" and p["renk_altin"].startswith("#D")
