"""Site entegrasyonlari (Shopify, WooCommerce, WordPress, tarama sirasi) ve yuklenen dosyalarin kullanimi."""
import json

import pytest
from PIL import Image

from ofis import ayarlar, entegrasyon, llm, urun_cekici, yuklemeler


class Y:
    def __init__(self, veri=None, durum=200, metin="", tip="application/json"):
        self._v, self.status_code, self.text, self.headers = veri, durum, metin, {"content-type": tip}
        self.url = ""

    def json(self):
        return self._v

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Http:
    def __init__(self, yollar):
        self.yollar, self.istekler = yollar, []

    def get(self, url, **k):
        self.istekler.append(url)
        for parca, y in self.yollar.items():
            if parca in url:
                return y
        return Y(None, 404, "", "text/html")


SHOPIFY = {"products": [
    {"title": "Velvet Sofa", "handle": "velvet-sofa", "product_type": "Sofas", "body_html": "<p>Soft <b>velvet</b></p>",
     "variants": [{"price": "450000.00", "compare_at_price": "520000.00", "available": True}],
     "images": [{"src": "https://cdn.shopify.com/a.jpg"}]},
    {"title": "No Photo", "handle": "x", "variants": [{"price": "1"}], "images": []}]}


def test_shopify_algilanir_ve_urunler_okunur():
    http = Http({"/products.json?limit=1": Y(SHOPIFY), "/products.json?limit=250&page=1": Y(SHOPIFY),
                 "shop.example": Y(None, 200, "<html><script src='https://cdn.shopify.com/s.js'></script></html>", "text/html")})
    assert entegrasyon.platform_bul("shop.example", http) == "shopify"
    u = entegrasyon.shopify_urunleri("https://shop.example/some/page", http)
    assert len(u) == 1 and u[0]["ad"] == "Velvet Sofa" and u[0]["fiyat"] == 450000.0 and u[0]["eski_fiyat"] == 520000.0
    assert u[0]["url"] == "https://shop.example/products/velvet-sofa" and u[0]["aciklama"] == "Soft velvet"


def test_woocommerce_fiyat_birimi_ve_wordpress_yazilari():
    woo = [{"name": "Jollof Pack", "permalink": "https://w.example/p/jollof", "is_in_stock": True,
            "prices": {"price": "350000", "regular_price": "400000", "sale_price": "350000",
                       "currency_code": "NGN", "currency_minor_unit": 2},
            "categories": [{"name": "Food"}], "images": [{"src": "https://w.example/j.jpg"}],
            "short_description": "<p>Party jollof</p>"}]
    yazi = [{"title": {"rendered": "5 tips"}, "excerpt": {"rendered": "<p>Clean your sofa</p>"}, "link": "https://w.example/5",
             "_embedded": {"wp:featuredmedia": [{"source_url": "https://w.example/i.jpg"}]}}]
    http = Http({"wc/store/v1/products?per_page=1": Y(woo), "wc/store/v1/products?per_page=100&page=1": Y(woo),
                 "wp/v2/posts": Y(yazi), "w.example": Y(None, 200, "<link href='/wp-content/x.css'>", "text/html")})
    assert entegrasyon.platform_bul("https://w.example", http) == "woocommerce"
    u = entegrasyon.woocommerce_urunleri("https://w.example", http)[0]
    assert u["fiyat"] == 3500.0 and u["eski_fiyat"] == 4000.0 and u["para_birimi"] == "NGN" and u["kategori"] == "Food"
    y = entegrasyon.wordpress_yazilari("https://w.example", http)
    assert y == [{"baslik": "5 tips", "ozet": "Clean your sofa", "url": "https://w.example/5", "gorsel": "https://w.example/i.jpg"}]


def test_guvenli_adres_ic_agi_reddeder():
    assert not entegrasyon.guvenli_adres("http://127.0.0.1/")
    assert not entegrasyon.guvenli_adres("file:///etc/passwd")
    assert entegrasyon.normallestir("Shop.Example/abc") == "https://shop.example"


def test_tarama_sirasi_shopify_once_sonra_tarayici(monkeypatch):
    monkeypatch.setitem(ayarlar.AYAR, "site", "https://shop.example")
    monkeypatch.setitem(ayarlar.AYAR, "feed_url", "")
    monkeypatch.setitem(ayarlar.AYAR, "kategoriler", [])
    urun_cekici.PLATFORM.unlink(missing_ok=True)
    monkeypatch.setattr(entegrasyon, "platform_bul", lambda *a, **k: "shopify")
    monkeypatch.setattr(entegrasyon, "shopify_urunleri", lambda *a, **k: [
        {"ad": "A", "url": "u", "fiyat": 1, "gorseller": ["g"], "kategori": ""}])
    assert [u["ad"] for u in urun_cekici.urunleri_cek(lambda *_: None)] == ["A"]
    assert json.loads(urun_cekici.PLATFORM.read_text())["yontem"] == "shopify"
    # JavaScript sitesi: klasik tarama bos -> gercek tarayici
    urun_cekici.PLATFORM.unlink()
    monkeypatch.setattr(entegrasyon, "platform_bul", lambda *a, **k: "genel")
    monkeypatch.setattr(urun_cekici, "_site_taramasi", lambda *a: [])
    monkeypatch.setattr(entegrasyon, "tarayici_ile_tara", lambda *a, **k: [
        {"ad": "B", "url": "v", "fiyat": 2, "gorseller": ["g"], "kategori": ""}])
    assert [u["ad"] for u in urun_cekici.urunleri_cek(lambda *_: None)] == ["B"]
    # urun cikmayan site bir hafta yeniden taranmaz
    urun_cekici.PLATFORM.unlink()
    monkeypatch.setattr(entegrasyon, "tarayici_ile_tara", lambda *a, **k: [])
    assert urun_cekici.urunleri_cek(lambda *_: None) == []
    monkeypatch.setattr(entegrasyon, "platform_bul", lambda *a, **k: pytest.fail("yeniden taradi"))
    assert urun_cekici.urunleri_cek(lambda *_: None) == []
    urun_cekici.PLATFORM.unlink()


def test_urun_html_oku_json_ld():
    html = ('<script type="application/ld+json">{"@type":"Product","name":"Oak Bed","image":"/b.jpg",'
            '"offers":{"price":"300000","priceCurrency":"NGN"}}</script>')
    u = urun_cekici.urun_html_oku(html, "https://s.example/p/oak")
    assert u["ad"] == "Oak Bed" and u["fiyat"] == 300000 and u["gorseller"][0] == "https://s.example/b.jpg"


# ---------------- yuklemeler (ofis tarafi) ----------------
@pytest.fixture
def kutuphane(monkeypatch):
    import shutil
    shutil.rmtree(yuklemeler.KLASOR, ignore_errors=True)
    shutil.rmtree(yuklemeler.ONBELLEK, ignore_errors=True)
    yuklemeler.KLASOR.mkdir(parents=True)
    kayit = []
    for i, (renk, grup) in enumerate([((200, 0, 0), "red sofa"), ((210, 0, 0), "red sofa"), ((0, 0, 200), "shop front")]):
        Image.new("RGB", (800, 1000), renk).save(yuklemeler.KLASOR / f"f{i}.jpg")
        kayit.append({"id": f"f{i}", "dosya": f"f{i}.jpg", "tur": "gorsel", "not": "new arrival" if i == 0 else "",
                      "tarih": f"2026-11-1{i}"})
    (yuklemeler.KLASOR / "menu.txt").write_text("Jollof rice 3500 NGN\nOpen 9am-9pm")
    kayit.append({"id": "m", "dosya": "menu.txt", "tur": "belge", "not": "our menu", "tarih": "2026-11-15"})
    yuklemeler.yaz(kayit)
    yield
    shutil.rmtree(yuklemeler.KLASOR, ignore_errors=True)


def test_yuklemeler_incelenir_gruplanir_ve_bir_kez_kullanilir(kutuphane, monkeypatch):
    monkeypatch.setattr(llm, "hazir", lambda: True)
    gruplar = {"f0.jpg": "red sofa", "f1.jpg": "red sofa", "f2.jpg": "shop front"}
    monkeypatch.setattr(llm, "gor", lambda s, m, yollar, **k: {
        "baslik": "Our " + gruplar[yollar[0].name], "tur": "urun", "aciklama": "visible", "icerik_fikri": "show it",
        "grup": gruplar[yollar[0].name], "uygun": True})
    monkeypatch.setattr(llm, "sor", lambda *a, **k: {"ozet": "Menu", "gercekler": ["Jollof rice 3500 NGN", "Open 9am-9pm"],
                                                     "fikirler": ["Lunch menu highlight"]})
    assert yuklemeler.incele(lambda *_: None) == 4 and yuklemeler.incele(lambda *_: None) == 0
    assert yuklemeler.belge_gercekleri() == ["Jollof rice 3500 NGN", "Open 9am-9pm"]
    assert yuklemeler.belge_fikirleri() == ["Lunch menu highlight"]
    u = yuklemeler.kaynak_urunleri(5)
    assert [x["ad"] for x in u] == ["Our red sofa", "Our shop front"] and len(u[0]["gorseller"]) == 2
    assert u[0]["yukleme"] and u[0]["fikir"] and u[0]["fiyat"] is None and "new arrival" in u[0]["aciklama"]
    yuklemeler.kullanildi(u[0], "2026-11-13_post")
    assert [x["ad"] for x in yuklemeler.kaynak_urunleri(5)] == ["Our shop front"]


def test_gorsel_model_yoksa_sahibin_notu_kullanilir(kutuphane, monkeypatch):
    monkeypatch.setattr(llm, "gor", lambda *a, **k: None)
    monkeypatch.setattr(llm, "hazir", lambda: False)
    yuklemeler.incele(lambda *_: None)
    k = {x["id"]: x for x in yuklemeler.oku()}
    assert k["f0"]["analiz"]["baslik"] == "new arrival" and k["f0"]["analiz"]["kaynak"] == "not"
    assert k["m"]["analiz"]["ozet"].startswith("Jollof")


def test_gorsel_istegi_bicimi_ve_desteklenmeyen_model(tmp_path, monkeypatch):
    from ofis import llm_openai
    monkeypatch.setenv("AJAN_YZ_ANAHTAR", "k")
    monkeypatch.setattr(llm_openai, "_gorme_yok", False)
    monkeypatch.setattr(llm_openai, "_hazir", None)
    foto = tmp_path / "a.jpg"
    Image.new("RGB", (3000, 2000)).save(foto)
    alinan = []

    class P:
        def __init__(self, durum, veri):
            self.status_code, self._v = durum, veri

        def json(self):
            return self._v

        def raise_for_status(self):
            pass

    class H:
        def __init__(self, durum):
            self.durum = durum

        def post(self, url, **k):
            alinan.append(k["json"])
            return P(self.durum, {"choices": [{"message": {"content": '{"baslik": "Sofa"}'}}]})
    assert llm_openai.gor("s", "m", [foto], oturum=H(200)) == {"baslik": "Sofa"}
    parca = alinan[0]["messages"][1]["content"]
    assert parca[0]["type"] == "text" and parca[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert llm_openai.gor("s", "m", [foto], oturum=H(422)) is None
    assert llm_openai._gorme_yok and llm_openai.gor("s", "m", [foto], oturum=H(200)) is None
