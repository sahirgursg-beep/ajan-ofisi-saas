"""OpenAI uyumlu yapay zeka saglayicisi (DigitalOcean Serverless Inference, Groq, OpenRouter, OpenAI...).

Ortam degiskenleri (anahtar dosyaya yazilmaz):
  AJAN_YZ_URL     varsayilan https://inference.do-ai.run/v1   (DigitalOcean)
  AJAN_YZ_ANAHTAR model erisim anahtari
  AJAN_YZ_MODEL   varsayilan openai-gpt-oss-120b (model kaldirilirsa /models'tan otomatik yedek secilir)
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
TERCIH = ("openai-gpt-oss-120b", "llama-4-maverick", "deepseek-4-flash", "qwen3.5-397b-a17b",
          "anthropic-claude-haiku-4.5", "openai-gpt-oss-20b")


def _url():
    return (os.environ.get("AJAN_YZ_URL") or (AYAR.get("yz") or {}).get("openai_url")
            or "https://inference.do-ai.run/v1").rstrip("/")


def _anahtar():
    return os.environ.get("AJAN_YZ_ANAHTAR", "").strip()


def model_adi():
    return _yedek_model or os.environ.get("AJAN_YZ_MODEL") or (AYAR.get("yz") or {}).get("openai_model") \
        or "openai-gpt-oss-120b"


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


# Gorsel gorebilen modeller (DigitalOcean katalogu degisir): sirayla aranir; metin modeli gorse o da denenir.
GORME_TERCIH = ("kimi-k2.6", "kimi-k3", "kimi", "glm-5.3", "glm", "nemotron-3.5-super-vl", "vl",
                "deepseek-v4.1-flash", "anthropic-claude-haiku-4.5", "llama-4-maverick", "qwen3.5")
_gorme_model = None
_gorme_kotu = set()


def _gorme_adaylari(http):
    """Ortam degiskeni > katalogdaki gorme modelleri (tercih sirasiyla) > metin modeli."""
    adaylar = []
    if os.environ.get("AJAN_YZ_GORME_MODEL"):
        adaylar.append(os.environ["AJAN_YZ_GORME_MODEL"])
    try:
        r = http.get(_url() + "/models", timeout=30, headers={"Authorization": f"Bearer {_anahtar()}"})
        mevcut = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")] if r.status_code == 200 else []
    except Exception:
        mevcut = []
    for parca in GORME_TERCIH:
        adaylar += [m for m in mevcut if parca in m.lower() and m not in adaylar
                    and not any(x in m for x in ("image", "embed", "tts", "whisper"))]
    adaylar.append(model_adi())
    return [m for m in dict.fromkeys(adaylar) if m not in _gorme_kotu]


def gorme_modeli():
    return _gorme_model


def gor(sistem, mesaj, gorsel_yollari, json_mod=True, oturum=None):
    """Gorsel + metin (OpenAI 'image_url' bicimi). Calisan ilk gorme modelini bulur ve hatirlar; resim
    kabul etmeyen model bir daha denenmez. Hicbiri yoksa None (cagiran taraf gorsel incelemesiz devam eder)."""
    global _gorme_yok, _gorme_model
    if _gorme_yok or not hazir():
        return None
    http = oturum or requests
    icerik = [{"type": "text", "text": mesaj}]
    for y in list(gorsel_yollari)[:4]:
        try:
            icerik.append({"type": "image_url", "image_url": {"url": _veri_uri(y)}})
        except Exception as e:
            print(f"  ! gorsel okunamadi {y}: {e}")
    modeller = [_gorme_model] if _gorme_model else _gorme_adaylari(http)
    for model in modeller:
        govde = {"model": model, "temperature": 0.2,
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
                _gorme_kotu.add(model)
                if _gorme_model == model:
                    _gorme_model = None
                print(f"  ! '{model}' gorsel kabul etmiyor (HTTP {r.status_code}), siradaki deneniyor.")
                continue
            r.raise_for_status()
            veri = r.json()
            _maliyet_yaz(veri.get("usage") or {}, model)
            metin = (veri["choices"][0]["message"].get("content") or "").strip()
            if _gorme_model != model:
                _gorme_model = model
                print(f"  Gorsel inceleme modeli: {model}")
            return json_coz(metin) if json_mod else metin
        except Exception as e:
            print(f"  ! Gorsel inceleme hatasi ({model}): {str(e)[:160]}")
            return None
    _gorme_yok = True
    print("  ! Hicbir model gorsel kabul etmedi; gorsel inceleme kapali (AJAN_YZ_GORME_MODEL ile belirtilebilir).")
    return None


FIYATLAR = (("opus", 5.0, 25.0), ("sonnet", 3.0, 15.0), ("haiku", 1.0, 5.0), ("kimi", 0.6, 2.5), ("glm", 0.6, 2.2))


def _maliyet_yaz(kullanim, model=None):
    """Token kullanimini aylik yapay zeka harcamasina ekler (fiyatlar USD / 1M token, ortamdan degistirilebilir)."""
    try:
        g = float(os.environ.get("AJAN_YZ_FIYAT_GIRDI", "0.25"))
        c = float(os.environ.get("AJAN_YZ_FIYAT_CIKTI", "0.87"))
        for parca, fg, fc in FIYATLAR:
            if model and parca in model.lower():
                g, c = fg, fc
                break
        tutar = (kullanim.get("prompt_tokens", 0) * g + kullanim.get("completion_tokens", 0) * c) / 1_000_000
        if tutar > 0:
            from . import fal_ai
            fal_ai.harca(tutar, "tasarim_yz" if model and model != model_adi() else "metin_yz")
    except Exception:
        pass


def sifirla():
    global _hazir
    _hazir = None


def durum():
    return durum_metni


# ---------------------------------------------------------------- tasarim modeli
# Tasarim (HTML/CSS) ve marka tasarim sistemi icin guclu model. Sira: DigitalOcean'daki Claude modelleri (yeniden
# eskiye) -> fal.ai uzerinden OpenRouter Claude (FAL_KEY varsa) -> metin modeli.
TASARIM_TERCIH = ("anthropic-claude-sonnet-5", "anthropic-claude-4.6-sonnet", "anthropic-claude-sonnet-4.6",
                  "anthropic-claude-4.5-sonnet", "anthropic-claude-opus-4.6", "anthropic-claude-haiku-4.5", "claude")
FAL_TASARIM = os.environ.get("AJAN_FAL_TASARIM_MODEL", "anthropic/claude-sonnet-4.6")
_tasarim_adaylari = None
_tasarim_kotu = set()
_kilit = __import__("threading").RLock()


def _do_tasarim_adaylari(http):
    env = os.environ.get("AJAN_YZ_TASARIM_MODEL", "").strip()
    if env:
        return [] if env in ("metin", "fal") else [env]
    try:
        r = http.get(_url() + "/models", timeout=30, headers={"Authorization": f"Bearer {_anahtar()}"})
        mevcut = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")] if r.status_code == 200 else []
    except Exception:
        mevcut = []
    out = []
    for parca in TASARIM_TERCIH:
        out += [m for m in mevcut if parca in m and m not in out and "image" not in m]
    return out


def tasarim_modeli(http=None):
    """Kullanilacak ilk tasarim modelinin adi (kayit icin)."""
    global _tasarim_adaylari
    with _kilit:                                   # paralel isler ayni anda sorarsa /models bir kez cagrilsin
        if _tasarim_adaylari is None:
            _tasarim_adaylari = _do_tasarim_adaylari(http or requests)
    for m in _tasarim_adaylari:
        if m not in _tasarim_kotu:
            return m
    if os.environ.get("FAL_KEY") and os.environ.get("AJAN_YZ_TASARIM_MODEL", "") != "metin" and "fal" not in _tasarim_kotu:
        return "fal:" + FAL_TASARIM
    return model_adi()


def _fal_sor(sistem, mesaj, sicaklik, http):
    r = http.post("https://fal.run/openrouter/router", timeout=300,
                  headers={"Authorization": f"Key {os.environ['FAL_KEY']}", "Content-Type": "application/json"},
                  json={"model": FAL_TASARIM, "system_prompt": sistem, "prompt": mesaj, "temperature": sicaklik,
                        "max_tokens": 6000})
    if r.status_code in (400, 401, 403, 404, 422):
        raise PermissionError(f"HTTP {r.status_code}: {r.text[:120]}")
    r.raise_for_status()
    veri = r.json()
    u = veri.get("usage") or {}
    try:
        from . import fal_ai
        tutar = float(u.get("cost") or 0) or (u.get("prompt_tokens", 0) * 3 + u.get("completion_tokens", 0) * 15) / 1e6
        fal_ai.harca(tutar, "tasarim_yz")
    except Exception:
        pass
    return (veri.get("output") or "").strip()


def tasarim_sor(sistem, mesaj, sicaklik=0.7, oturum=None):
    """Tasarim modeline sorar; erisilemeyen model (403/404...) isaretlenir, siradaki denenir; en son metin modeli."""
    if not hazir():
        return None
    http = oturum or requests
    for _ in range(8):
        model = tasarim_modeli(http)
        if model == model_adi():
            return sor(sistem, mesaj, json_mod=False, sicaklik=sicaklik, oturum=oturum)
        try:
            if model.startswith("fal:"):
                cevap = _fal_sor(sistem, mesaj, sicaklik, http)
                if model not in _bildirilen:
                    _bildirilen.add(model)
                    print(f"  Tasarim modeli: {model} (fal.ai uzerinden)")
                return cevap
            govde = {"model": model, "temperature": sicaklik, "max_tokens": 6000,
                     "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": mesaj}]}
            r = http.post(_url() + "/chat/completions", json=govde, timeout=300,
                          headers={"Authorization": f"Bearer {_anahtar()}"})
            if r.status_code in (400, 401, 403, 404, 422):
                raise PermissionError(f"HTTP {r.status_code}: {r.text[:160]}")
            r.raise_for_status()
            veri = r.json()
            _maliyet_yaz(veri.get("usage") or {}, model)
            print(f"  Tasarim modeli: {model}") if model not in _bildirilen else None
            _bildirilen.add(model)
            return (veri["choices"][0]["message"].get("content") or "").strip()
        except PermissionError as e:
            with _kilit:
                if model.startswith("fal:"):
                    _tasarim_kotu.add("fal")
                elif "anthropic" in model and str(e).startswith("HTTP 403"):
                    # 403 hesap duzeyinde: DO'daki tum Claude modelleri ayni yaniti verir, hepsini atla
                    _tasarim_kotu.update(m for m in (_tasarim_adaylari or []) if "anthropic" in m)
                else:
                    _tasarim_kotu.add(model)
                if model not in _bildirilen_hata:
                    _bildirilen_hata.add(model)
                    print(f"  ! Tasarim modeli '{model}' kullanilamadi ({e}); siradaki deneniyor")
        except Exception as e:
            print(f"  ! Tasarim modeli hatasi ({model}): {str(e)[:160]}")
            return sor(sistem, mesaj, json_mod=False, sicaklik=sicaklik, oturum=oturum)
    return sor(sistem, mesaj, json_mod=False, sicaklik=sicaklik, oturum=oturum)


_bildirilen = set()
_bildirilen_hata = set()
