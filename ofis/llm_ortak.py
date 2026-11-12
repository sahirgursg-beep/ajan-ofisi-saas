"""Saglayicilarin ortak yardimcilari."""
import json
import re


def json_coz(metin):
    """Modelin cevabindan JSON nesnesini cikarir (kod bloklari ve oncesindeki/sonrasindaki metin temizlenir)."""
    if metin is None:
        return None
    try:
        return json.loads(metin)
    except Exception:
        m = re.search(r"\{.*\}", metin, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None
