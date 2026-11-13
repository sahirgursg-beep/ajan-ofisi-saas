"""Doviz kurlari (USD bazli): paket fiyatlarinin ziyaretcinin para birimindeki yaklasik karsiligi icin.

Kaynak: open.er-api.com (ucretsiz, anahtarsiz; gunde bir kez guncellenir). 12 saat bellekte tutulur.
Servis cevap vermezse son bilinen kurlar, o da yoksa yalnizca USD gosterilir (fiyatlar hicbir zaman uydurulmaz).
Faturalama USD'dir; yerel tutarlar "yaklasik" olarak gosterilir.
"""
import math
import threading
import time

import requests

KAYNAK = "https://open.er-api.com/v6/latest/USD"
SURE = 12 * 3600
_kilit = threading.Lock()
_onbellek = {"zaman": 0, "kurlar": {}, "tarih": ""}


def kurlar(oturum=None):
    with _kilit:
        if _onbellek["kurlar"] and time.time() - _onbellek["zaman"] < SURE:
            return _onbellek["kurlar"], _onbellek["tarih"]
    try:
        r = (oturum or requests).get(KAYNAK, timeout=8)
        r.raise_for_status()
        j = r.json()
        if j.get("result") == "success" and isinstance(j.get("rates"), dict):
            with _kilit:
                _onbellek.update({"zaman": time.time(), "kurlar": {k: float(v) for k, v in j["rates"].items()},
                                  "tarih": j.get("time_last_update_utc", "")})
    except Exception as e:
        print(f"kur servisi: {type(e).__name__}", flush=True)
    return _onbellek["kurlar"], _onbellek["tarih"]


def guzel_yuvarla(tutar):
    """Fiyat etiketine yakisan yuvarlama: 9.4 -> 9.5, 15480 -> 15500, 1534000 -> 1530000"""
    if tutar <= 0:
        return 0
    if tutar < 20:
        return round(tutar * 2) / 2
    basamak = 10 ** max(0, int(math.log10(tutar)) - 1)
    return round(tutar / basamak) * basamak


def cevir(usd, para, oturum=None):
    """-> (yerel tutar ya da None, kur tarihi)"""
    para = (para or "USD").upper()
    if para == "USD":
        return usd, ""
    k, tarih = kurlar(oturum)
    if para not in k:
        return None, tarih
    return guzel_yuvarla(usd * k[para]), tarih
