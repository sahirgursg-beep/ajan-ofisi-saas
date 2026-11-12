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
            veri = r.json()
            _maliyet_yaz(veri.get("usage") or {})
            metin = (veri["choices"][0]["message"].get("content") or "").strip()
            return json_coz(metin) if json_mod else metin
        except Exception as e:
            print(f"  ! Yapay zeka hatasi: {str(e)[:200]}")
            _hazir, _bakildi = False, time.time()
            durum_metni = f"Yapay zeka isteği başarısız: {str(e)[:120]}"
            return None
    return None


_gorme_yok = False


def _veri_uri(yol, kenar=896):
    import base64
    import io
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
    im.thumbnail((kenar, kenar))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def gor(sistem, mesaj, gorsel_yollari, json_mod=True, oturum=None):
    """Gorsel + metin (OpenAI 'image_url' bicimi). Model gorsel kabul etmiyorsa None ve bir daha denemez.
    AJAN_YZ_GORME_MODEL ile ayri bir gorsel model secilebilir (varsayilan: metin modeli)."""
    global _gorme_yok
    if _gorme_yok or not hazir():
        return None
    http = oturum or requests
    icerik = [{"type": "text", "text": mesaj}]
    for y in list(gorsel_yollari)[:4]:
        try:
            icerik.append({"type": "image_url", "image_url": {"url": _veri_uri(y)}})
        except Exception as e:
            print(f"  ! gorsel okunamadi {y}: {e}")
    govde = {"model": os.environ.get("AJAN_YZ_GORME_MODEL") or model_adi(), "temperature": 0.2,
             "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": icerik}]}
    if json_mod and _json_destek:
        govde["response_format"] = {"type": "json_object"}
    try:
        r = http.post(_url() + "/chat/completions", json=govde, timeout=180,
                      headers={"Authorization": f"Bearer {_anahtar()}"})
        if r.status_code == 400 and "response_format" in govde:
            govde.pop("response_format")
            r = http.post(_url() + "/chat/completions", json=govde, timeout=180,
                          headers={"Authorization": f"Bearer {_anahtar()}"})
        if r.status_code in (400, 404, 415, 422):
            _gorme_yok = True
            print(f"  ! Model gorsel kabul etmiyor (HTTP {r.status_code}); gorsel inceleme kapali.")
            return None
        r.raise_for_status()
        veri = r.json()
        _maliyet_yaz(veri.get("usage") or {})
        metin = (veri["choices"][0]["message"].get("content") or "").strip()
        return json_coz(metin) if json_mod else metin
    except Exception as e:
        print(f"  ! Gorsel inceleme hatasi: {str(e)[:160]}")
        return None


def _maliyet_yaz(kullanim):
    """Token kullanimini aylik yapay zeka harcamasina ekler (fiyatlar USD / 1M token, ortamdan degistirilebilir)."""
    try:
        g = float(os.environ.get("AJAN_YZ_FIYAT_GIRDI", "0.25"))
        c = float(os.environ.get("AJAN_YZ_FIYAT_CIKTI", "0.87"))
        tutar = (kullanim.get("prompt_tokens", 0) * g + kullanim.get("completion_tokens", 0) * c) / 1_000_000
        if tutar > 0:
            from . import fal_ai
            fal_ai.harca(tutar, "metin_yz")
    except Exception:
        pass


def sifirla():
    global _hazir
    _hazir = None


def durum():
    return durum_metni
