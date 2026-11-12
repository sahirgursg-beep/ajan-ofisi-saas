"""Bulut yapay zeka saglayicisi: Google Gemini (REST, ek paket gerektirmez).

Anahtar koda ya da dosyaya yazilmaz: ortam degiskeninden okunur (varsayilan GEMINI_API_KEY,
config.json -> yz.gemini_anahtar_ortam ile degistirilebilir). Bulutta Secret Manager bu degiskeni doldurur.
"""
import os
import time

import requests

from .ayarlar import AYAR
from .llm_ortak import json_coz

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_hazir = None
_bakildi = 0
durum_metni = ""


def _yz():
    return AYAR.get("yz") or {}


def _anahtar():
    return os.environ.get(_yz().get("gemini_anahtar_ortam", "GEMINI_API_KEY"), "").strip()


def model_adi():
    return _yz().get("gemini_model", "gemini-2.5-flash")


def hazir():
    """Anahtar tanimli mi? (Ag cagrisi yapmaz; gercek hata ilk istekte yakalanir ve 60 sn hazir degil sayilir.)"""
    global _hazir, durum_metni
    if _hazir is False and time.time() - _bakildi < 60:
        return False
    if not _anahtar():
        durum_metni = f"Gemini anahtarı yok ({_yz().get('gemini_anahtar_ortam', 'GEMINI_API_KEY')} tanımlı değil)"
        _hazir = False
        return False
    _hazir, durum_metni = True, model_adi()
    return True


def _govde(sistem, mesaj, json_mod, sicaklik):
    g = {
        "systemInstruction": {"parts": [{"text": sistem}]},
        "contents": [{"role": "user", "parts": [{"text": mesaj}]}],
        "generationConfig": {"temperature": sicaklik},
    }
    if json_mod:
        g["generationConfig"]["responseMimeType"] = "application/json"
    return g


def _metin(cevap):
    try:
        parcalar = cevap["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parcalar).strip()
    except (KeyError, IndexError, TypeError):
        return None


def sor(sistem, mesaj, json_mod=False, sicaklik=0.7, oturum=None):
    """Basarisizsa None doner (ajanlar sablon metne duser). 429/5xx'te bir kez bekleyip yeniden dener."""
    global _hazir, _bakildi, durum_metni
    if not hazir():
        return None
    http = oturum or requests
    for deneme in range(2):
        try:
            r = http.post(URL.format(model=model_adi()), json=_govde(sistem, mesaj, json_mod, sicaklik),
                          headers={"x-goog-api-key": _anahtar()}, timeout=_yz().get("zaman_asimi_sn", 300))
            if r.status_code in (429, 500, 502, 503, 504) and deneme == 0:
                time.sleep(2)
                continue
            r.raise_for_status()
            metin = _metin(r.json())
            break
        except Exception as e:
            print(f"  ! Gemini hatasi: {str(e)[:200]}")
            _hazir, _bakildi = False, time.time()
            durum_metni = f"Gemini isteği başarısız: {str(e)[:120]}"
            return None
    else:
        return None
    if metin is None:
        return None
    return json_coz(metin) if json_mod else metin


def sifirla():
    global _hazir
    _hazir = None


def durum():
    return durum_metni
