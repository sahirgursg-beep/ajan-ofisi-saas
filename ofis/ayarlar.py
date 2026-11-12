"""Ayarlar ve klasorler.

Iki katman vardir:
  1) config.json                         -> platformun varsayilanlari (her musteride ayni)
  2) musteriler/<musteri>/profil.json    -> o musteriye ozel her sey (isletme, marka, para, saat, urun kaynagi...)
Profil, config'in ustune derinlemesine yazilir; kod her zaman birlesmis AYAR'i okur.

Hangi musteri? Sirayla: AJAN_MUSTERI ortam degiskeni -> aktif_musteri.txt -> "ornek-mobilya".
Faz 0'da bir surec = bir musteri. Faz 1'de bu dosyalar veritabanina tasinacak; kodun geri kalani
yalnizca AYAR ve asagidaki klasor sabitlerini kullandigi icin degismeyecek.
"""
import json
import os
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
PAYLASIK = Path(os.environ.get("AJAN_PAYLASIK_KOK") or KOK / "paylasilan")   # tum musterilerin ortak varliklari: fontlar, muzik, yapay zeka modelleri
MUSTERILER = Path(os.environ.get("AJAN_MUSTERILER_KOK") or KOK / "musteriler")   # testler gecici klasor verir
VARSAYILAN_MUSTERI = "ornek-mobilya"


def _derin_birlestir(taban, ust):
    out = dict(taban)
    for k, v in (ust or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _derin_birlestir(out[k], v)
        else:
            out[k] = v
    return out


def aktif_musteri():
    m = os.environ.get("AJAN_MUSTERI", "").strip()
    if not m:
        dosya = KOK / "aktif_musteri.txt"
        if dosya.exists():
            m = dosya.read_text(encoding="utf-8").strip()
    m = m or VARSAYILAN_MUSTERI
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", m):
        raise ValueError(f"Gecersiz musteri kimligi: {m!r} (kucuk harf, rakam, - ve _ kullanin)")
    return m


def yukle(musteri=None):
    musteri = musteri or aktif_musteri()
    taban = json.loads((KOK / "config.json").read_text(encoding="utf-8"))
    profil_yol = MUSTERILER / musteri / "profil.json"
    if not profil_yol.exists():
        raise FileNotFoundError(f"Musteri profili yok: {profil_yol}. "
                                f"musteriler/_sablon klasorunu kopyalayip doldurun.")
    profil = json.loads(profil_yol.read_text(encoding="utf-8"))
    ayar = _derin_birlestir(taban, profil)
    ayar["musteri_id"] = musteri
    # Bulut ortami ayarlari ortam degiskeniyle ezer (Cloud Run'da GPU yok, yapay zeka bulut API'si)
    if os.environ.get("AJAN_YZ_SAGLAYICI"):
        ayar.setdefault("yz", {})["saglayici"] = os.environ["AJAN_YZ_SAGLAYICI"]
    if os.environ.get("AJAN_YZ_YEDEK") is not None and "AJAN_YZ_YEDEK" in os.environ:
        ayar.setdefault("yz", {})["yedek_saglayici"] = os.environ["AJAN_YZ_YEDEK"]
    if os.environ.get("AJAN_AI_GORSEL") == "0":
        ayar.setdefault("ai_gorsel", {})["aktif"] = False
    # Eski anahtarla uyum: usd_ngn_kur -> doviz_kurlari
    if "usd_ngn_kur" in ayar and "USD" not in (ayar.get("doviz_kurlari") or {}):
        ayar.setdefault("doviz_kurlari", {})["USD"] = ayar["usd_ngn_kur"]
    return ayar


MUSTERI = aktif_musteri()
AYAR = yukle(MUSTERI)

MUSTERI_KOK = MUSTERILER / MUSTERI
VERI = MUSTERI_KOK / "veri"            # pano, urun onbellegi, yayin durumu, Meta baglantisi
CIKTI = MUSTERI_KOK / "cikti"          # uretilen post / carousel / Reels
PROJELER = MUSTERI_KOK / "projeler"    # tamamlanan gercek proje fotograflari
MUZIK = PAYLASIK / "muzik"
for _k in (VERI, CIKTI, PROJELER):
    _k.mkdir(parents=True, exist_ok=True)


def dosya_yolu(ad):
    """Profilde verilen goreli dosya yolunu (logo vb.) musteri klasorune gore cozer."""
    if not ad:
        return None
    p = Path(ad)
    return p if p.is_absolute() else MUSTERI_KOK / p
