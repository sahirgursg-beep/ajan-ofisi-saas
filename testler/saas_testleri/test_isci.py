"""Isci: indir -> ajanlari calistir -> geri yaz. Birlestirme kurali birim testi + sahte Meta ile uctan uca."""
import os
from pathlib import Path

import pytest

from saas import guvenlik, isci, profil, yayin_durum
from saas.depo import Cakisma

from .conftest import FORM


def test_birlestir_meta_kimlikleri_kaybolmaz_kullanici_karari_kazanir():
    db = {"durum": "kaldiriliyor", "caption": "kullanici", "sonuc": {"fb_post": {"id": "eski"}}}
    isci_y = {"durum": "yayinlandi", "caption": "isci", "sonuc": {"ig_post": {"id": "yeni"}, "fb_post": {"hata": "x"}}}
    y = isci.birlestir(db, isci_y)
    assert y["durum"] == "kaldiriliyor" and y["caption"] == "kullanici"
    assert y["sonuc"]["ig_post"]["id"] == "yeni" and y["sonuc"]["fb_post"]["id"] == "eski"
    y = isci.birlestir({"durum": "onaylandi"}, {"durum": "yayinlandi", "yayin_zamani": "t", "sonuc": {}})
    assert y["durum"] == "yayinlandi" and y["yayin_zamani"] == "t"


def test_komutlar_iptal_once_gelir(tmp_path):
    (tmp_path / "cikti" / "k").mkdir(parents=True)
    (tmp_path / "cikti" / "k" / "yayin.json").write_text('{"bekleyen_iptal": ["p1"]}')
    a = isci.komutlar("kaldir", {"klasor": "k"}, tmp_path)
    assert a[0][-1] == "iptaller" and a[1][-2:] == ["kaldir", "k"]


def test_ajan_sureci_platform_sirlarini_gormez(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "COK-GIZLI")
    monkeypatch.setenv("SAAS_SIFRELEME_ANAHTARI", "COK-GIZLI")
    import sys
    ok, kayit = isci.calistir("m", tmp_path, tmp_path, [[sys.executable, "-c",
                              "import os;print('SIZINTI' if any('COK-GIZLI'==v for v in os.environ.values()) else 'TEMIZ')"]], 60)
    assert ok and "TEMIZ" in kayit


@pytest.mark.skipif(os.environ.get("AJAN_TAM_TEST") != "1", reason="tarayici + ffmpeg: AJAN_TAM_TEST=1")
def test_uctan_uca_uret_onayla_yayinla_kaldir(d, graph, monkeypatch, tmp_path):
    monkeypatch.setenv("AJAN_GRAPH_URL", graph.adres)
    monkeypatch.setenv("AJAN_YZ_SAGLAYICI", "gemini")         # anahtar yok -> hazir degil -> sablon metinler
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    mid = "oak"
    d.musteri_ekle({"id": mid, "ad": "Oak", "durum": "deneme",
                    "profil": profil.formdan({**FORM, "mesai_bas": "00:00", "mesai_bit": "23:59"}),  # saatten bagimsiz
                    "yayin_ayar": {"otomatik": False},
                    "meta_token": guvenlik.sifrele({"page_id": "111", "page_token": "SAYFA111", "ig_id": "ig111",
                                                    "page_ad": "Oak Page", "ig_kullanici": "oakember"})})
    paylasik = isci.paylasik_hazirla(tmp_path / "paylasilan")

    # 1) uretim
    d.is_ekle(mid, "uret", {"demo": True, "plansiz": True})
    isci.bir_is("test", paylasik)
    i = d.isler(mid)[0]
    assert i["durum"] == "bitti", i["kayit"][-1500:]
    ic = {x["tur"]: x for x in d.icerikler(mid)}
    assert set(ic) == {"post", "carousel", "reels"}
    assert all(x["yayin"]["durum"] == "bekliyor" for x in ic.values())       # hicbiri kendiliginden onaylanmadi
    assert "reels_1080x1920.mp4" in ic["reels"]["dosyalar"]
    assert d.pano_son(mid, 5)

    # 2) post'u hemen yayinla (panel karari + yayin turu)
    post = ic["post"]
    y = yayin_durum.onayla(post["yayin"], ["ig_post", "fb_post"], "", "Hello Lagos ₦1,875,000",
                           __import__("datetime").timezone.utc)
    d.icerik_yaz(mid, {"klasor": post["klasor"], "yayin": y, "caption": y["caption"]}, beklenen_surum=post["surum"])
    d.is_ekle(mid, "yayin_turu")
    isci.bir_is("test", paylasik)
    assert d.isler(mid)[0]["durum"] == "bitti", d.isler(mid)[0]["kayit"][-1500:]
    p = d.icerik_al(mid, post["klasor"])
    assert p["yayin"]["durum"] == "yayinlandi", p["yayin"]
    assert p["yayin"]["sonuc"]["ig_post"]["id"] and p["yayin"]["sonuc"]["fb_post"]["id"]
    assert any(y.endswith("/111/photos") for y in graph.yollar("POST"))
    assert any(y.endswith("/ig111/media_publish") for y in graph.yollar("POST"))

    # 3) kaldir
    y, gerek = yayin_durum.kaldir_istegi(p["yayin"], __import__("datetime").timezone.utc)
    assert gerek
    d.icerik_yaz(mid, {"klasor": post["klasor"], "yayin": y}, beklenen_surum=p["surum"])
    d.is_ekle(mid, "kaldir", {"klasor": post["klasor"]})
    isci.bir_is("test", paylasik)
    p = d.icerik_al(mid, post["klasor"])
    assert p["yayin"]["durum"] == "kaldirildi" and len(graph.silinen) == 2

    # 4) veri paketi Meta anahtarini icermez; ikinci uretim onceki urunleri hatirlar
    paket = tmp_path / "v.tgz"
    assert d.dosya_indir(f"{mid}/veri.tar.gz", paket)
    import tarfile
    with tarfile.open(paket) as t:
        adlar = t.getnames()
    assert "meta.json" not in adlar and "pano.db" in adlar
    d.is_ekle(mid, "uret", {"demo": True, "plansiz": True})
    isci.bir_is("test", paylasik)
    yeni = [x for x in d.icerikler(mid) if x["klasor"] not in {v["klasor"] for v in ic.values()}]
    assert len(yeni) == 3
    onceki_urunler = {v["meta"]["urun"]["ad"] for v in ic.values()}
    assert len({x["meta"]["urun"]["ad"] for x in yeni} - onceki_urunler) >= 1     # 4 demo urunden tekrar etmeyen


def test_biten_icerik_is_bitmeden_yuklenir(d, tmp_path):
    import json as _j
    import threading
    kok = tmp_path / "kok"
    k = kok / "cikti" / "2026-11-13_1200_post"
    k.mkdir(parents=True)
    (k / "meta.json").write_text(_j.dumps({"format": "post"}))
    (k / "post_1080x1350.jpg").write_bytes(b"jpg")
    goruntu = {"icerik": {}}
    dur = threading.Event()
    t = threading.Thread(target=isci._erken_yayinla, args=(d, "m1", kok, goruntu, dur, 0.05), daemon=True)
    t.start()
    import time
    time.sleep(0.2)
    assert d.icerik_al("m1", k.name) is None                   # .hazir yok: henuz yuklenmez
    (k / ".hazir").write_text("1")
    for _ in range(40):
        if d.icerik_al("m1", k.name):
            break
        time.sleep(0.05)
    dur.set(); t.join(5)
    ic = d.icerik_al("m1", k.name)
    assert ic and ic["dosyalar"] == ["post_1080x1350.jpg"] and goruntu["erken"] == 1
    assert goruntu["icerik"][k.name]["surum"] == ic["surum"] and ".hazir" not in ic["ekler"]


def test_kapanis_sinyalinde_uretim_hemen_birakilir():
    import sys, time
    from saas import isci
    isci.KAPANIS.set()
    try:
        t = time.time()
        kod, _ = isci._akit([sys.executable, "-c", "import time; time.sleep(60)"], None, 600, "m1")
        assert kod is None and time.time() - t < 10
    finally:
        isci.KAPANIS.clear()
