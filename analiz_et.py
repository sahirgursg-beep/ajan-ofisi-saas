"""Performans Analisti'ni elle calistirir: python analiz_et.py"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from ofis import pano  # noqa: E402
from ofis.ajanlar import tum_ekip  # noqa: E402

pano.kur()
tum_ekip()["PerformansAnalisti"].analiz()
