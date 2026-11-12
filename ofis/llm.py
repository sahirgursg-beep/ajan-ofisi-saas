"""Yapay zeka katmani: ajanlar yalnizca bu modulu cagirir, hangi saglayicinin calistigini bilmez.

config.json -> "yz": {"saglayici": "ollama" | "gemini" | "openai", "yedek_saglayici": ...}
("openai" = OpenAI uyumlu her servis; bulutta DigitalOcean Serverless Inference)
Siralama: ana saglayici hazirsa o; degilse yedek; ikisi de yoksa sor() None doner ve ajanlar
sablon metinlerle devam eder (sistem her durumda calisir).

Yeni saglayici eklemek: hazir(), model_adi(), sor(sistem, mesaj, json_mod, sicaklik), sifirla(), durum()
fonksiyonlarini saglayan bir modul yazip SAGLAYICILAR'a ekleyin.
"""
from importlib import import_module

from .ayarlar import AYAR
from .llm_ortak import json_coz  # noqa: F401  (eski kod llm.json_coz kullaniyor)

SAGLAYICILAR = {"ollama": "ofis.llm_ollama", "gemini": "ofis.llm_gemini", "openai": "ofis.llm_openai"}
_ozel = {}          # testler / ileride eklentiler icin: ad -> nesne


def kaydet(ad, saglayici):
    """Kod icinden saglayici tanimlar (testlerde sahte saglayici icin)."""
    _ozel[ad] = saglayici


def _yukle(ad):
    if not ad:
        return None
    if ad in _ozel:
        return _ozel[ad]
    if ad not in SAGLAYICILAR:
        raise ValueError(f"Bilinmeyen yapay zeka saglayicisi: {ad!r} ({', '.join(SAGLAYICILAR)})")
    return import_module(SAGLAYICILAR[ad])


def _adlar():
    yz = AYAR.get("yz") or {}
    ana = yz.get("saglayici", "ollama")
    yedek = yz.get("yedek_saglayici") or ""
    return [ana] + ([yedek] if yedek and yedek != ana else [])


def aktif():
    """Su an kullanilacak saglayici (ad, modul) ya da (None, None)."""
    for ad in _adlar():
        s = _yukle(ad)
        if s and s.hazir():
            return ad, s
    return None, None


def hazir():
    return aktif()[1] is not None


def saglayici_adi():
    return aktif()[0] or (_adlar()[0] if _adlar() else "")


def model_adi():
    ad, s = aktif()
    if s:
        return s.model_adi()
    return AYAR.get("model", "")


def sor(sistem, mesaj, json_mod=False, sicaklik=0.7):
    """LLM'e sorar. Ana saglayici hata verirse yedegi dener. Hepsi basarisizsa None."""
    for ad in _adlar():
        s = _yukle(ad)
        if not s or not s.hazir():
            continue
        cevap = s.sor(sistem, mesaj, json_mod=json_mod, sicaklik=sicaklik)
        if cevap is not None:
            return cevap
    return None


def sifirla():
    for ad in _adlar():
        s = _yukle(ad)
        if s and hasattr(s, "sifirla"):
            s.sifirla()


def durum():
    """Saglik kontrolu icin insan okunur durum."""
    parcalar = []
    for ad in _adlar():
        s = _yukle(ad)
        d = s.durum() if s and hasattr(s, "durum") else ""
        parcalar.append(f"{ad}: {d or ('hazır' if s and s.hazir() else 'hazır değil')}")
    return " · ".join(parcalar)
