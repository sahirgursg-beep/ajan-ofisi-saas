"""Ofisin kendi kendine (kullanici onayiyla) degistirebildigi ayarlar: veri/ofis_ayar.json
config.json'a dokunulmaz; oneri kutusundan onaylanan degisiklikler buraya yazilir."""
import json

from .ayarlar import AYAR, KOK, VERI

YOL = VERI / "ofis_ayar.json"
VARSAYILAN = {
    "reels_kapali": [],                 # kapatilan Reels formatlari
    "oncelikli_kategoriler": {},        # {"Bedroom Sets": 1.5} plan seciminde carpan
    "rakipler": list(AYAR.get("rakipler", [])),   # Instagram kullanici adlari (rakip/ilham takibi), profil.json
    "deneme_reels": "yeni_formatlar",   # "kapali" | "yeni_formatlar" | "hepsi"  (Instagram Trial Reels)
    "proje_gunu": 5,                    # tamamlanan projeler hangi gun paylasilsin (0=Pzt ... 6=Paz, -1 = kapali)
}


def oku():
    try:
        d = json.loads(YOL.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    out = {**json.loads(json.dumps(VARSAYILAN)), **d}
    return out


def kaydet(d):
    YOL.parent.mkdir(parents=True, exist_ok=True)
    YOL.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def guncelle(**alanlar):
    d = oku()
    d.update({k: v for k, v in alanlar.items() if k in VARSAYILAN})
    return kaydet(d)
