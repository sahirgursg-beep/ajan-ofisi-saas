"""Ajan ekibi v2: sektor bilgisi, platform uzmanlari, arastirma, verisiz (fikir) mod, gorsel kaynaklari, bulut rotus."""
import base64
import io
import json

import pytest
from PIL import Image

from ofis import (arastirma, ayarlar, fal_ai, fikir_kaynagi, gorsel_kaynak, llm, musteri, platformlar, rotus_bulut, sektor,
                  sektor_bilgi)


@pytest.fixture(autouse=True)
def yapay_zeka_yok(monkeypatch):
    monkeypatch.setattr(llm, "hazir", lambda: False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    for y in (sektor.YOL, arastirma.RAPOR, fal_ai.HARCAMA):
        y.unlink(missing_ok=True)
    yield
    for y in (sektor.YOL, arastirma.RAPOR, fal_ai.HARCAMA):
        y.unlink(missing_ok=True)


@pytest.fixture
def isletme(monkeypatch):
    def kur(**alanlar):
        yeni = {**ayarlar.AYAR["isletme"], **alanlar}
        monkeypatch.setitem(ayarlar.AYAR, "isletme", yeni)
        return yeni
    return kur


class Yanit:
    def __init__(self, veri=None, durum=200, icerik=b""):
        self._veri, self.status_code, self.content, self.text = veri, durum, icerik, json.dumps(veri or {})

    def json(self):
        return self._veri

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _png_b64(w, h, renk=(200, 50, 50)):
    b = io.BytesIO()
    Image.new("RGB", (w, h), renk).save(b, "PNG")
    return base64.b64encode(b.getvalue()).decode()


# ---------------- sektor bilgisi ----------------
def test_her_sektor_tam_ve_platform_agirliklari_gecerli():
    zorunlu = {"ad", "kelimeler", "kitle", "ton", "sutunlar", "fikirler", "kancalar", "gorsel", "stok", "hashtag",
               "platform"}
    assert len(sektor_bilgi.SEKTORLER) >= 25 and "genel" in sektor_bilgi.SEKTORLER
    for k, s in sektor_bilgi.SEKTORLER.items():
        assert zorunlu <= set(s), k
        assert s["sutunlar"] and s["fikirler"] and s["stok"], k
        assert set(s["platform"]) == set(platformlar.SIRA), k
        assert all(0 <= v <= 3 for v in s["platform"].values()), k


@pytest.mark.parametrize("cumle,beklenen", [
    ("family restaurant in Lekki serving jollof and small chops", "restoran"),
    ("we are a law firm helping startups", "hukuk"),
    ("hair salon and barber shop", "guzellik"),
    ("fumigation and pest control services", "temizlik"),
    ("", "genel"),
    ("something nobody has heard of", "genel"),
])
def test_tek_cumleden_sektor_bulunur(cumle, beklenen):
    assert sektor.kelime_ile_bul(cumle) == beklenen


def test_sektor_profili_yapay_zekasiz_ve_onbellekli(isletme):
    isletme(tanim="hair salon and barber shop", sektor="", sehirler=["Abuja"])
    p = sektor.profil()
    assert p["anahtar"] == "guzellik" and p["kaynak"] == "kelime"
    assert json.loads(sektor.YOL.read_text())["_imza"] == p["_imza"]
    assert "Abuja" in sektor.doldur("Best cuts in {city}")
    assert "Sector:" in sektor.istem_ozeti()
    isletme(tanim="restaurant and cafe")                     # tanim degisince profil yenilenir
    assert sektor.profil()["anahtar"] == "restoran"


def test_yapay_zeka_profili_tabanin_ustune_yazar(isletme, monkeypatch):
    isletme(tanim="bakery selling cakes", sektor="")
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", lambda *a, **k: {"sektor": "restoran", "alt_sektor": "Bakery", "ton": "warm",
                                                      "fikirler": ["Fresh bread at 7am in {city}"], "b2b": False})
    p = sektor.profil(yenile=True)
    assert p["anahtar"] == "restoran" and p["alt_sektor"] == "Bakery" and p["ton"] == "warm"
    assert p["fikirler"][0] == "Fresh bread at 7am in {city}" and len(p["fikirler"]) > 1
    assert p["kaynak"] == "yapay_zeka"


# ---------------- platform uzmanlari ----------------
TABAN = {"hook": "Your Sunday table, sorted", "headline": "Sunday table",
         "caption": "Our oak dining table seats six. Visit us. Price ₦450,000.",
         "hashtags": ["#oak", "#lagosliving", "#diningroom", "#homedecor", "#furniture", "#lagos", "#naija",
                      "#interiors", "#homestyle", "#design", "#wood", "#table"], "reels_lines": ["Seats six", "Solid oak"]}


def test_platform_surumleri_kurallara_uyar(isletme):
    isletme(tanim="furniture showroom", sektor="mobilya", platformlar=[])
    out = platformlar.uret({"ad": "Oak table", "fiyat_metni": "₦450,000"}, "family dinners", TABAN, "post")
    assert set(out) <= set(platformlar.SIRA) and {"instagram", "facebook"} <= set(out)
    for p, v in out.items():
        k = platformlar.KURALLAR[p]
        assert v["mod"] == k["mod"]
        assert len(v["caption"]) <= k["metin_siniri"] and len(v["hashtags"]) <= k["hashtag"][1]
    assert out["instagram"]["mod"] == "otomatik"
    if "tiktok" in out:
        assert out["tiktok"]["mod"] == "manuel" and out["tiktok"]["baslik"]
        assert out["tiktok"]["ekran_yazilari"] == ["Seats six", "Solid oak"]
    assert "comments" in out["facebook"]["caption"]


def test_sektor_agirligi_sifir_olan_platform_atlanir_ama_secim_kazanir(isletme):
    isletme(tanim="hair salon", sektor="guzellik", platformlar=[])
    assert "linkedin" not in platformlar.aktif_platformlar()
    isletme(platformlar=["linkedin", "instagram"])
    assert platformlar.aktif_platformlar() == ["instagram", "linkedin"]


def test_yapay_zeka_fiyati_bozarsa_onayli_metne_donulur(isletme, monkeypatch):
    isletme(tanim="furniture showroom", sektor="mobilya", platformlar=["instagram", "linkedin"])
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", lambda *a, **k: {"hook": "x", "caption": "Now only ₦99,000!", "hashtags": ["a"]})
    out = platformlar.uret({"ad": "Oak table", "fiyat_metni": "₦450,000"}, "", TABAN, "post")
    assert "₦450,000" in out["instagram"]["caption"] and "99,000" not in out["instagram"]["caption"]
    assert out["linkedin"]["mod"] == "manuel" and "₦450,000" in out["linkedin"]["caption"]


def test_platform_metni_kaydedilir_ve_okunur(tmp_path):
    platformlar.kaydet(tmp_path, {"facebook": {"caption": "Hello", "hashtags": ["#a", "#b"], "mod": "otomatik"}})
    assert platformlar.metin(tmp_path, "facebook") == "Hello\n\n#a #b"
    assert platformlar.metin(tmp_path, "tiktok") is None
    assert platformlar.oku(tmp_path / "yok") == {}


# ---------------- arastirma ----------------
def test_arastirma_raporu_isteme_eklenir_ve_tazelik_kontrolu():
    assert arastirma.eski_mi() and arastirma.istem_ozeti() == ""
    from datetime import datetime, timedelta
    arastirma.RAPOR.parent.mkdir(parents=True, exist_ok=True)
    arastirma.RAPOR.write_text(json.dumps({
        "tarih": datetime.now().isoformat(), "ozet": "Warm minimal interiors win.",
        "gorsel_trendler": ["soft daylight"], "renk_paletleri": [{"ad": "Clay", "renkler": ["#C2703D", "#F3EDE4"]}],
        "kacin": ["stock-looking collages"]}))
    s = arastirma.istem_ozeti()
    assert not arastirma.eski_mi()
    assert "Warm minimal" in s and "soft daylight" in s and "#C2703D" in s and "stock-looking" in s
    arastirma.RAPOR.write_text(json.dumps({"tarih": (datetime.now() - timedelta(days=9)).isoformat(), "ozet": "x"}))
    assert arastirma.eski_mi()


def test_arastirma_yapay_zekasiz_taban_bilgiyle_rapor_yazar(isletme):
    isletme(tanim="restaurant", sektor="restoran", sehirler=["Lagos"])
    r = arastirma.guncelle(gunluk=lambda *_: None, zorla=True)
    assert r["ozet"] and r["fikirler"] and "{city}" not in " ".join(r["fikirler"])


# ---------------- verisiz (fikir) mod ----------------
def test_fikir_modu_fiyatsiz_urun_uretir_ve_tekrar_etmez(isletme, monkeypatch, tmp_path):
    isletme(tanim="cleaning company", sektor="temizlik", sehirler=["Lagos"])
    monkeypatch.setitem(ayarlar.AYAR, "urun_kaynagi", "fikir")
    assert fikir_kaynagi.veri_yok_mu()
    foto = tmp_path / "f.jpg"
    Image.new("RGB", (800, 1000)).save(foto)
    monkeypatch.setattr(gorsel_kaynak, "stok_ara", lambda *a, **k: [(str(foto), {"kaynak": "pexels", "fotografci": "Ada"})])
    monkeypatch.setattr(gorsel_kaynak, "yz_uret", lambda *a, **k: None)
    kullanilan = set()
    monkeypatch.setattr(fikir_kaynagi.pano, "son_hazirlananlar", lambda gun: kullanilan)
    out = fikir_kaynagi.fikir_urunleri(3, gunluk=lambda *_: None)
    assert len(out) == 3 and len({u["url"] for u in out}) == 3
    for u in out:
        assert u["fikir"] and u["fiyat"] is None and u["fiyat_metni"] == "" and u["url"].startswith("fikir://")
        assert u["gorseller"] == [str(foto)]
    assert fikir_kaynagi.kaynak_notu(out[0]) == "Photo: Ada / Pexels"
    kullanilan.update(u["url"] for u in out)
    assert not {u["url"] for u in fikir_kaynagi.fikir_urunleri(3, gunluk=lambda *_: None)} & kullanilan


def test_gorsel_kaynagi_yoksa_fikir_uretilmez(isletme, monkeypatch):
    isletme(tanim="cleaning company", sektor="temizlik")
    monkeypatch.setattr(gorsel_kaynak, "stok_ara", lambda *a, **k: [])
    monkeypatch.setattr(gorsel_kaynak, "yz_uret", lambda *a, **k: None)
    monkeypatch.setattr(fikir_kaynagi.pano, "son_hazirlananlar", lambda gun: set())
    mesajlar = []
    assert fikir_kaynagi.fikir_urunleri(2, gunluk=mesajlar.append) == []
    assert any("PIXABAY_API_KEY" in m for m in mesajlar)


def test_site_varsa_veri_var(monkeypatch):
    monkeypatch.setitem(ayarlar.AYAR, "urun_kaynagi", None)
    monkeypatch.setitem(ayarlar.AYAR, "site", "https://shop.example.ng")
    assert not fikir_kaynagi.veri_yok_mu()
    monkeypatch.setitem(ayarlar.AYAR, "site", "")
    monkeypatch.setitem(ayarlar.AYAR, "feed_url", "")
    assert fikir_kaynagi.veri_yok_mu()


# ---------------- gorsel kaynaklari ----------------
class SahteHttp:
    def __init__(self, cevaplar):
        self.cevaplar, self.istekler = cevaplar, []

    def _cevap(self, url):
        for parca, y in self.cevaplar.items():
            if parca in url:
                return y
        return Yanit({}, 404)

    def get(self, url, **k):
        self.istekler.append(("GET", url, k))
        return self._cevap(url)

    def post(self, url, **k):
        self.istekler.append(("POST", url, k))
        return self._cevap(url)


def test_pixabay_once_denenir_ve_indirilir(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "pk")
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    http = SahteHttp({
        "pixabay.com/api": Yanit({"hits": [
            {"id": 7, "user": "Kemi", "pageURL": "https://pixabay.com/p/7", "largeImageURL": "https://cdn/7.jpg"},
            {"id": 8, "user": "Tolu", "pageURL": "https://pixabay.com/p/8", "largeImageURL": "https://cdn/8.jpg"}]}),
        "https://cdn/": Yanit(icerik=b"pix")})
    out = gorsel_kaynak.stok_ara("bakery bread", adet=2, oturum=http)
    assert [k["kaynak"] for _, k in out] == ["pixabay", "pixabay"] and open(out[0][0], "rb").read() == b"pix"
    assert http.istekler[0][2]["params"]["key"] == "pk" and http.istekler[0][2]["params"]["orientation"] == "vertical"


def test_pexels_araması_indirir_ve_atif_bilgisi_doner(monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.setenv("PEXELS_API_KEY", "test")
    http = SahteHttp({
        "api.pexels.com": Yanit({"photos": [
            {"id": 1, "photographer": "Ada", "url": "https://pexels.com/p/1", "src": {"large2x": "https://img/1.jpg"}},
            {"id": 2, "photographer": "Bo", "url": "https://pexels.com/p/2", "src": {"large2x": "https://img/2.jpg"}}]}),
        "https://img/": Yanit(icerik=b"jpgbytes")})
    out = gorsel_kaynak.stok_ara("clean kitchen", adet=3, haric={"2"}, oturum=http)
    assert len(out) == 1 and out[0][1]["fotografci"] == "Ada"
    assert open(out[0][0], "rb").read() == b"jpgbytes"
    assert http.istekler[0][2]["headers"]["Authorization"] == "test"


def test_anahtar_yoksa_gorsel_kaynaklari_sessizce_bos(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.delenv("AJAN_YZ_ANAHTAR", raising=False)
    assert gorsel_kaynak.stok_ara("x") == [] and gorsel_kaynak.yz_uret("x") is None
    assert not rotus_bulut.hazir()


def test_yapay_zeka_gorseli_b64_kaydedilir(monkeypatch):
    monkeypatch.setenv("AJAN_YZ_ANAHTAR", "k")
    http = SahteHttp({"/images/generations": Yanit({"data": [{"b64_json": _png_b64(8, 12)}]})})
    yol = gorsel_kaynak.yz_uret("a bright clean kitchen", oturum=http)
    assert Image.open(yol).size == (8, 12)
    istek = http.istekler[0][2]
    assert istek["json"]["model"] == "openai-gpt-image-1" and istek["headers"]["Authorization"] == "Bearer k"


# ---------------- bulut rotus ----------------
def test_netlestir_kucuk_gorseli_buyutur(tmp_path):
    kucuk = tmp_path / "k.jpg"
    Image.new("RGB", (400, 500), (90, 90, 90)).save(kucuk)
    assert min(Image.open(rotus_bulut.netlestir(kucuk)).size) == 1080
    buyuk = tmp_path / "b.jpg"
    Image.new("RGB", (1080, 1350)).save(buyuk)
    assert rotus_bulut.netlestir(buyuk) == str(buyuk)


def test_dikey_genisletme_urunu_birebir_korur(tmp_path, monkeypatch):
    monkeypatch.setenv("AJAN_YZ_ANAHTAR", "k")
    monkeypatch.setattr(rotus_bulut, "_desteklenmiyor", False)
    yatay = tmp_path / "y.jpg"
    Image.new("RGB", (1200, 800), (10, 200, 10)).save(yatay)
    http = SahteHttp({"/images/edits": Yanit({"data": [{"b64_json": _png_b64(1024, 1536, (0, 0, 255))}]})})
    sonuc = Image.open(rotus_bulut.dikey_genislet(yatay, oturum=http))
    assert sonuc.size == (1024, 1536)
    assert sonuc.getpixel((512, 768))[1] > 150          # orta (urun) orijinal yesil
    assert sonuc.getpixel((512, 20))[2] > 150           # ust kenar yapay zeka dolgusu
    assert http.istekler[0][2]["files"]["mask"][0] == "mask.png"


def test_dikey_genisletme_desteklenmiyorsa_bir_daha_denemez(tmp_path, monkeypatch):
    monkeypatch.setenv("AJAN_YZ_ANAHTAR", "k")
    monkeypatch.setattr(rotus_bulut, "_desteklenmiyor", False)
    yatay = tmp_path / "y.jpg"
    Image.new("RGB", (1200, 800)).save(yatay)
    http = SahteHttp({"/images/edits": Yanit({"error": "unsupported"}, 404)})
    assert rotus_bulut.dikey_genislet(yatay, oturum=http) is None
    assert rotus_bulut.dikey_genislet(yatay, oturum=http) is None
    assert len(http.istekler) == 1
    dikey = tmp_path / "d.jpg"
    Image.new("RGB", (800, 1200)).save(dikey)
    monkeypatch.setattr(rotus_bulut, "_desteklenmiyor", False)
    assert rotus_bulut.dikey_genislet(dikey, oturum=http) is None and len(http.istekler) == 1


# ---------------- fal.ai ----------------
def _jpg_bytes(w, h, renk):
    b = io.BytesIO()
    Image.new("RGB", (w, h), renk).save(b, "JPEG")
    return b.getvalue()


def test_fal_genisletme_dogru_istek_harcama_ve_urun_korunur(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk")
    monkeypatch.delenv("AJAN_YZ_ANAHTAR", raising=False)
    yatay = tmp_path / "y.jpg"
    Image.new("RGB", (1200, 800), (10, 200, 10)).save(yatay)
    http = SahteHttp({"fal.run/fal-ai/flux-2-pro/outpaint": Yanit({"images": [{"url": "https://cdn.fal/x.jpg"}]}),
                      "cdn.fal": Yanit(icerik=_jpg_bytes(1024, 1536, (0, 0, 255)))})
    assert rotus_bulut.hazir()
    sonuc = Image.open(rotus_bulut.dikey_genislet(yatay, oturum=http))
    assert sonuc.size == (1024, 1536) and sonuc.getpixel((512, 768))[1] > 150 and sonuc.getpixel((512, 20))[2] > 150
    istek = http.istekler[0][2]
    assert istek["headers"]["Authorization"] == "Key fk"
    assert istek["json"]["image_url"].startswith("data:image/jpeg;base64,")
    assert istek["json"]["expand_top"] + istek["json"]["expand_bottom"] + 683 == 1536
    assert fal_ai.bu_ay() == pytest.approx(0.06)


def test_fal_aylik_tavan_dolunca_ucretli_cagri_yapilmaz(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk")
    monkeypatch.setenv("AJAN_YZ_AYLIK_TAVAN", "1")
    fal_ai.harca(0.995, "test")
    yatay = tmp_path / "y.jpg"
    Image.new("RGB", (1200, 800)).save(yatay)
    http = SahteHttp({})
    assert rotus_bulut.dikey_genislet(yatay, oturum=http) is None
    assert gorsel_kaynak.yz_uret("kitchen", oturum=http) is None
    assert http.istekler == []


def test_fal_gorsel_uretimi(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fk")
    http = SahteHttp({"fal.run/fal-ai/flux-2/flash": Yanit({"images": [{"url": "https://cdn.fal/g.jpg"}]}),
                      "cdn.fal": Yanit(icerik=_jpg_bytes(1024, 1536, (200, 200, 0)))})
    yol = gorsel_kaynak.yz_uret("a tidy bakery counter", oturum=http)
    assert Image.open(yol).size == (1024, 1536)
    assert http.istekler[0][2]["json"]["image_size"] == {"width": 1024, "height": 1536}
    assert fal_ai.bu_ay() == pytest.approx(0.01)


def test_genisletme_fiyati_belgeyle_uyumlu():
    assert fal_ai.genisletme_fiyati((1024, 1024), (1024, 1024)) == pytest.approx(0.045)
    assert fal_ai.genisletme_fiyati((1024, 683), (1024, 1536)) == pytest.approx(0.06)


# ---------------- sablon kalintilari / site urun vermiyor ----------------
def test_site_urun_vermezse_fikir_moduna_gecer(isletme, monkeypatch):
    from ofis import ajanlar, pano, urun_cekici
    pano.kur()
    isletme(tanim="AI social media manager", sektor="")
    monkeypatch.setitem(ayarlar.AYAR, "urun_kaynagi", None)
    monkeypatch.setitem(ayarlar.AYAR, "site", "https://www.feedzync.example")
    monkeypatch.setattr(urun_cekici, "urunleri_cek", lambda *a, **k: [])
    sahte = [{"ad": "Idea", "url": "fikir://1", "fikir": True, "gorseller": ["x.jpg"]}]
    monkeypatch.setattr(fikir_kaynagi, "fikir_urunleri", lambda *a, **k: sahte)
    U = ajanlar.tum_ekip()["UrunSorumlusu"]
    assert U.urunleri_getir() == sahte and U.tum_urunler == sahte


def test_sablon_temalari_ve_etiketleri_baska_sektore_tasinmaz(isletme, monkeypatch):
    from ofis import ajanlar
    sb = musteri.sablon()
    isletme(tanim="dental clinic", sektor="saglik", ad="Smile Dental",
            hashtagler=list(sb["isletme"]["hashtagler"]), proje_hashtagler=[])
    monkeypatch.setitem(ayarlar.AYAR, "haftalik_tema", sb["haftalik_tema"])
    assert ajanlar.bugunun_temasi() in sektor.profil()["sutunlar"]
    h = musteri.hashtagler()
    assert h[0] == "#SmileDental" and "#BrandName" not in h and len(h) > 1
    monkeypatch.setitem(ayarlar.AYAR, "haftalik_tema", {d: "Our own theme" for d in sb["haftalik_tema"]})
    assert ajanlar.bugunun_temasi() == "Our own theme"


def test_model_kaldirilinca_otomatik_yedek_model(monkeypatch):
    from ofis import llm_openai
    monkeypatch.setenv("AJAN_YZ_ANAHTAR", "k")
    monkeypatch.setenv("AJAN_YZ_MODEL", "llama3.3-70b-instruct")
    monkeypatch.setattr(llm_openai, "_yedek_model", None)
    monkeypatch.setattr(llm_openai, "_hazir", None)

    class Http(SahteHttp):
        def post(self, url, **k):
            self.istekler.append(("POST", url, k))
            if k["json"]["model"] == "llama3.3-70b-instruct":
                return Yanit({"error": "model not found"}, 404)
            return Yanit({"choices": [{"message": {"content": '{"ok": true}'}}]})
    http = Http({"/models": Yanit({"data": [{"id": "llama-4-maverick"}, {"id": "openai-gpt-oss-120b"}]})})
    assert llm_openai.sor("s", "m", json_mod=True, oturum=http) == {"ok": True}
    assert llm_openai.model_adi() == "openai-gpt-oss-120b"            # tercih sirasi, listedeki sira degil
    assert http.istekler[-1][2]["json"]["model"] == "openai-gpt-oss-120b"


def test_sektor_tanimdan_bulunur_sablon_kategorileri_yaniltmaz(isletme, monkeypatch):
    isletme(ad="FeedZYNC", tanim="AI AUTOMATED SOCIAL MEDIA MANAGER", sektor="")
    monkeypatch.setitem(ayarlar.AYAR, "kategoriler", ["living room", "dining room", "bedroom"])
    assert sektor.profil(yenile=True)["anahtar"] == "medya"


# ---------------- marka ozeti / durustluk ----------------
def test_marka_ozeti_siteden_gercekleri_cikarir_ve_ister(isletme, monkeypatch):
    from ofis import marka_ozeti
    marka_ozeti.YOL.unlink(missing_ok=True)
    isletme(ad="FeedZync", tanim="AI social media manager")
    monkeypatch.setitem(ayarlar.AYAR, "site", "https://feedzync.example")
    html = ('<html><title>FeedZync</title><body><h1>AI agents run your Instagram</h1>'
            '<a href="/services">Services</a><script>x()</script></body></html>')
    http = SahteHttp({"/services": Yanit(), "feedzync.example": Yanit()})
    http.cevaplar["/services"].text = "<html><body>Daily posts, Reels, captions</body></html>"
    http.cevaplar["feedzync.example"].text = html
    alinan = {}

    def sor(sistem, mesaj, **k):
        alinan["mesaj"] = mesaj
        return {"ne_yapar": "AI team that creates and posts social media content", "sunulanlar": ["Daily posts", "Reels"],
                "kanitlanmis_bilgiler": [["Daily posts"], "Reels"], "gorsel_dunyasi": "phones, laptops, content planning",
                "gorselde_olmamali": "clothing or food as if sold", "stok_terimleri": ["social media planning"]}
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", sor)
    o = marka_ozeti.ozet(oturum=http)
    assert "AI agents run your Instagram" in alinan["mesaj"] and "Daily posts, Reels" in alinan["mesaj"]
    assert "x()" not in alinan["mesaj"] and o["kanitlanmis_bilgiler"] == ["Daily posts", "Reels"]
    s = marka_ozeti.istem_ozeti()
    assert "never invent customers" in s and "VISUALS must NOT show: clothing" in s
    marka_ozeti.YOL.unlink(missing_ok=True)


def test_kalite_kontrol_uydurma_sonuc_ve_musteri_hikayesini_reddeder(isletme, monkeypatch):
    from ofis import ajanlar, marka_ozeti, pano
    pano.kur()
    monkeypatch.setattr(marka_ozeti, "ozet", lambda *a, **k: {"kanitlanmis_bilgiler": ["Founded 2025"]})
    KK = ajanlar.tum_ekip()["KaliteKontrol"]
    taslak = {"hook": "40% more followers", "headline": "Grow faster", "caption": "Customer spotlight: boutique grew.",
              "hashtags": ["#a"] * 8, "reels_lines": ["Real growth"], "carousel_lines": [], "carousel_points": []}
    ok, notlar = KK.kontrol({"ad": "Growth tips", "fikir": True}, taslak)
    assert not ok and any("invented number" in n for n in notlar) and any("case study" in n for n in notlar)


def test_taslak_alanlari_duzeltilir():
    from ofis.ajanlar import taslak_duzelt
    t = taslak_duzelt({"hook": ["Fast", "posts"], "caption": ["Line 1", "Line 2"], "hashtags": "#a, #b",
                       "reels_lines": "one\ntwo", "carousel_points": [{"t": "x"}]})
    assert t["hook"] == "Fast posts" and t["caption"] == "Line 1\nLine 2" and t["hashtags"] == ["#a", "#b"]
    assert t["reels_lines"] == ["one", "two"] and t["carousel_points"] == ["x"]



def test_buyuk_harf_cta_duzeltilir(monkeypatch):
    import json as _j
    from ofis import ayarlar as a
    yol = a.MUSTERILER / a.MUSTERI / "profil.json"
    eski = yol.read_text(encoding="utf-8")
    p = _j.loads(eski)
    p["marka"]["cta"] = "VISIT TO OUR WEBSITE"
    yol.write_text(_j.dumps(p), encoding="utf-8")
    try:
        assert a.yukle(a.MUSTERI)["marka"]["cta"] == "Visit to our website"
    finally:
        yol.write_text(eski, encoding="utf-8")


# ---------------- yazi tipi kutuphanesi ----------------
def test_font_kutuphanesi_tutarli_ve_genis():
    from ofis import fontlar, sanat
    assert len(fontlar.CIFTLER) >= 20 and set(sanat.FONTLAR) == set(fontlar.uygun_ciftler()) and "arap_klasik" not in sanat.FONTLAR
    assert all(a in fontlar.GOOGLE for a in fontlar.aileler())
    css = fontlar.css_siniflari()
    assert all(f".f-{k} " in css for k in fontlar.CIFTLER) and '"Anton"' in css
    assert set(sanat.ACIKLAMA["fontlar"]) == set(sanat.FONTLAR) and "suits" in sanat.ACIKLAMA["fontlar"]["afis"]
    assert fontlar.uygunluk("retro", "Restaurants, cafes & food") == 3 and fontlar.uygunluk("antik", "Restaurants") == 1


def test_sablon_modu_sektore_uygun_font_secer(isletme):
    from ofis import sanat, fontlar
    isletme(tanim="restaurant", sektor="restoran")
    secilen = [sanat.rastgele_tarif({"ad": "x", "indirim_yuzde": 0}, sanat.baglam(), tohum=i)["fontlar"] for i in range(200)]
    uygun = [f for f in fontlar.CIFTLER if fontlar.uygunluk(f, "Restaurants, cafes & food") == 3]
    assert len(set(secilen)) >= 8                                         # cesitlilik
    assert sum(f in uygun for f in secilen) / len(secilen) > len(uygun) / len(fontlar.CIFTLER)   # sektore yakisanlar one cikar


# ---------------- kuresel: ulke, dil, takvim ----------------
def test_ulke_tablosu_ve_dil_talimati(monkeypatch):
    from ofis import dil, ulkeler
    assert len(ulkeler.ULKELER) >= 60 and ulkeler.al("fr")["para"] == "EUR" and ulkeler.ada_gore("Japan")["dil"] == "ja"
    from zoneinfo import ZoneInfo
    for u in ulkeler.ULKELER.values():
        ZoneInfo(u["saat_dilimi"])                      # gecerli saat dilimleri
        assert u["dil"] in ulkeler.DILLER, u
    monkeypatch.setitem(ayarlar.AYAR, "isletme", {**ayarlar.AYAR["isletme"], "dil": "fr"})
    assert "French" in dil.talimat() and dil.etiket("yeni") == "NOUVEAU"
    monkeypatch.setitem(ayarlar.AYAR, "isletme", {**ayarlar.AYAR["isletme"], "dil": "", "ulke_kodu": "BR"})
    assert dil.kod() == "pt" and dil.etiket("detaylar") == "OS DETALHES"
    monkeypatch.setitem(ayarlar.AYAR, "isletme", {**ayarlar.AYAR["isletme"], "dil": "xx"})
    assert dil.etiket("indirim") == "OFF"                # bilinmeyen dil -> Ingilizce etiket


def test_ulkesi_takvimi_olmayan_isletme_kuresel_takvimi_kullanir(isletme):
    from datetime import date
    from ofis import sanat
    isletme(ulke_kodu="JP")
    b = sanat.baglam(date(2026, 11, 25))
    assert any(e["ad"] == "Black Friday" for e in b["etkinlikler"]) and b["trendler"]


# ---------------- paketler ----------------
def test_paket_sinirlari_uretime_uygulanir(isletme, monkeypatch):
    from ofis import paketler, plan
    monkeypatch.setitem(ayarlar.AYAR, "abonelik", {"plan": "starter"})
    assert paketler.formatlar(plan.FORMATLAR) == ["post"]
    isletme(tanim="law firm", sektor="hukuk", platformlar=[])
    assert platformlar.aktif_platformlar() == ["instagram", "facebook"]
    assert fal_ai.tavan() == 2
    monkeypatch.setitem(ayarlar.AYAR, "abonelik", {})            # deneme -> Growth
    assert paketler.formatlar(plan.FORMATLAR) == list(plan.FORMATLAR) and "linkedin" in platformlar.aktif_platformlar()
    assert [p["usd"] for p in paketler.liste()] == [10, 30, 60]
