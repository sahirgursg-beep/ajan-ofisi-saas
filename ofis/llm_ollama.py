"""Yerel yapay zeka saglayicisi: Ollama. Ollama yoksa hazir() False doner; ust katman yedege ya da sablon moduna gecer."""
import json
import os
import re
import shutil
import subprocess
import time

import requests

from .ayarlar import AYAR
from .llm_ortak import json_coz

_hazir = None
_model = None
_bakildi = 0              # son kontrol zamani: "kapali" sonucu kalici sayilmaz
_baslatma_denendi = 0
durum_metni = ""          # saglik kontrolu icin insan okunur durum
YEDEK_TERCIH = ("qwen2.5", "qwen3", "qwen", "llama3.1", "llama3.2", "llama3", "gemma", "mistral", "phi")


def _url():
    """Windows'ta 'localhost' once IPv6 dener ve saniyelerce bekletir; Ollama IPv4 dinler. Dogrudan 127.0.0.1."""
    return AYAR["ollama_url"].rstrip("/").replace("//localhost", "//127.0.0.1")


def _etiketler(deneme=3, sure=6):
    son = None
    for i in range(deneme):
        try:
            r = requests.get(_url() + "/api/tags", timeout=sure)
            return [m.get("name", "") for m in r.json().get("models", [])]
        except Exception as e:
            son = e
            time.sleep(1.5)
    raise son


def _ollama_baslat():
    """Ollama kapaliysa arka planda acmayi dener (10 dakikada en fazla bir kez). Acildiysa True."""
    global _baslatma_denendi
    if time.time() - _baslatma_denendi < 600:
        return False
    _baslatma_denendi = time.time()
    exe = shutil.which("ollama")
    if not exe:
        aday = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
        exe = aday if os.path.exists(aday) else None
    if not exe:
        return False
    try:
        bayrak = 0x00000008 | 0x08000000 if os.name == "nt" else 0     # DETACHED_PROCESS | CREATE_NO_WINDOW
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, creationflags=bayrak)
    except Exception:
        return False
    print("  Ollama kapaliydi; arka planda baslatiliyor...")
    for _ in range(20):
        time.sleep(1.5)
        try:
            requests.get(_url() + "/api/tags", timeout=3)
            return True
        except Exception:
            pass
    return False


def hazir():
    """Ollama acik mi ve kullanilabilir bir model var mi? Kapaliysa acmayi dener; ayardaki model yoksa
    yuklu baska bir modelle devam eder. 'Hazir degil' sonucu 60 sn sonra yeniden sinanir."""
    global _hazir, _model, durum_metni, _bakildi
    if _hazir is False and time.time() - _bakildi > 60:
        _hazir = None
    if _hazir is None:
        _bakildi = time.time()
        try:
            try:
                modeller = _etiketler()
            except Exception:
                if not _ollama_baslat():
                    raise
                modeller = _etiketler()
            istenen = AYAR["model"]
            tam = [m for m in modeller if m == istenen or m == istenen + ":latest"]
            aile = [m for m in modeller if m.split(":")[0] == istenen.split(":")[0]]
            if tam or aile:
                _model, _hazir, durum_metni = (tam or aile)[0], True, (tam or aile)[0]
            else:
                yedek = next((m for t in YEDEK_TERCIH for m in modeller if m.startswith(t) and "embed" not in m), None)
                if yedek:
                    _model, _hazir = yedek, True
                    durum_metni = f"'{istenen}' yok, yüklü '{yedek}' kullanılıyor (MODEL_YUKLE.bat ile asıl model yüklenebilir)"
                    print(f"  ! '{istenen}' modeli yok; yuklu '{yedek}' modeliyle devam ediliyor.")
                else:
                    _hazir = False
                    durum_metni = f"Ollama açık ama '{istenen}' modeli yüklü değil — MODEL_YUKLE.bat'ı çalıştırın"
                    print(f"  ! Ollama calisiyor ama '{istenen}' modeli yok. Yuklemek icin MODEL_YUKLE.bat "
                          f"(ya da: ollama pull {istenen})")
        except Exception:
            _hazir = False
            durum_metni = "Ollama açılamadı — Başlat menüsünden Ollama'yı açın"
    return _hazir


def model_adi():
    hazir()
    return _model or AYAR["model"]


def sor(sistem, mesaj, json_mod=False, sicaklik=0.7):
    """LLM'e sorar. Basarisizsa None doner."""
    if not hazir():
        return None
    govde = {
        "model": model_adi(),
        "stream": False,
        "messages": [
            {"role": "system", "content": sistem},
            {"role": "user", "content": mesaj},
        ],
        "options": {"temperature": sicaklik},
    }
    if json_mod:
        govde["format"] = "json"
    try:
        r = requests.post(_url() + "/api/chat", json=govde, timeout=(AYAR.get("yz") or {}).get("zaman_asimi_sn", 300))
        r.raise_for_status()
        metin = r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"  ! LLM hatasi: {e}")
        return None
    if json_mod:
        return json_coz(metin)
    return metin




def sifirla():
    global _hazir
    _hazir = None


def durum():
    return durum_metni
