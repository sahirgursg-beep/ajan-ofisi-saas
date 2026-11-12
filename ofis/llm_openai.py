"""OpenAI uyumlu yapay zeka saglayicisi (DigitalOcean Serverless Inference, Groq, OpenRouter, OpenAI...).

Ortam degiskenleri (anahtar dosyaya yazilmaz):
  AJAN_YZ_URL     varsayilan https://inference.do-ai.run/v1   (DigitalOcean)
  AJAN_YZ_ANAHTAR model erisim anahtari
  AJAN_YZ_MODEL   varsayilan llama-4-maverick (model kaldirilirsa /models'tan otomatik yedek secilir)
"""
import os
import time

import requests

from .ayarlar import AYAR
from .llm_ortak import json_coz

_hazir = None
_bakildi = 0
_json_destek = True
_yedek_model = None          # yapilandirilan model servisten kalkmissa otomatik secilen model
durum_metni = ""
# Model kaldirilirsa (404) sirayla denenecek modeller (DigitalOcean katalog kimlikleri)
TERCIH = ("llama-4-maverick", "openai-gpt-oss-120b", "deepseek-4-flash", "qwen3.5-397b-a17b",
          "anthropic-claude-haiku-4.5", "openai-gpt-oss-20b")


def _url():
    return (os.environ.get("AJAN_YZ_URL") or (AYAR.get("yz") or {}).get("openai_url")
            or "https://inference.do-ai.run/v1").rstrip("/")


def _anahtar():
    return os.environ.get("AJAN_YZ_ANAHTAR", "").strip()


def model_adi():
    return _yedek_model or os.environ.get("AJAN_YZ_MODEL") or (AYAR.get("yz") or {}).get("openai_model") \
        or "llama-4-maverick"


def _model_bul(http):
    """GET /models -> tercih listesinden ilk mevcut model (yoksa listedeki ilk sohbet modeli)."""
    try:
        r = http.get(_url() + "/models", timeout=30, headers={"Authorization": f"Bearer {_anahtar()}"})
        r.raise_for_status()
        mevcut = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")]
    except Exception as e:
        print(f"  ! Model listesi alinamadi: {str(e)[:120]}")
        return None
    for m in TERCIH:
        if m in mevcut:
            return m
    sohbet = [m for m in mevcut if not any(x in m for x in ("image", "embed", "whisper", "tts", "rerank"))]
    return sohbet[0] if sohbet else None


def hazir():
    global _hazir, durum_metni
    if _hazir is False and time.time() - _bakildi < 60:
        return False
    if not _anahtar():
        _hazir, durum_metni = False, "Yapay zeka anahtarı yok (AJAN_YZ_ANAHTAR tanımlı değil)"
        return False
    _hazir, durum_metni = True, model_adi()
    return True


def sor(sistem, mesaj, json_mod=False, sicaklik=0.7, oturum=None):
    """Basarisizsa None (ajanlar sablon metne duser). 429/5xx'te bir kez bekleyip dener."""
    global _hazir, _bakildi, _json_destek, durum_metni, _yedek_model
    if not hazir():
        return None
    http = oturum or requests
    govde = {"model": model_adi(), "temperature": sicaklik,
             "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": mesaj}]}
    if json_mod and _json_destek:
        govde["response_format"] = {"type": "json_object"}
    zaman = (AYAR.get("yz") or {}).get("zaman_asimi_sn", 300)
    for deneme in range(3):
        try:
            r = http.post(_url() + "/chat/completions", json=govde, timeout=zaman,
                          headers={"Authorization": f"Bearer {_anahtar()}"})
            if r.status_code == 404 and not _yedek_model:
                yeni = _model_bul(http)
                if yeni and yeni != govde["model"]:
                    print(f"  ! Model '{govde['model']}' artik yok; '{yeni}' kullaniliyor (AJAN_YZ_MODEL'i guncelleyin)")
                    _yedek_model = yeni
                    govde["model"] = yeni
                    continue
            if r.status_code == 400 and "response_format" in govde:
                _json_destek = False            # bu model JSON bicimini desteklemiyor: istemle yetin
                govde.pop("response_format")
                continue
            if r.status_code in (429, 500, 502, 503, 504) and deneme < 2:
                time.sleep(2 * (deneme + 1))
                continue
            r.raise_for_status()
            metin = (r.json()["choices"][0]["message"].get("content") or "").strip()
            return json_coz(metin) if json_mod else metin
        except Exception as e:
            print(f"  ! Yapay zeka hatasi: {str(e)[:200]}")
            _hazir, _bakildi = False, time.time()
            durum_metni = f"Yapay zeka isteği başarısız: {str(e)[:120]}"
            return None
    return None


def sifirla():
    global _hazir
    _hazir = None


def durum():
    return durum_metni
