"""Marka Kurallari: kullanicinin KALICI kurallari. Her uretimde tum ajanlar okur.

veri/marka_kurallari.json
{
  "yasak": {"duzen": ["diyagonal"], "fontlar": [], "motif": ["grain"], "fiyat_stili": [], "efekt": []},
  "yasak_kelimeler": ["cheap", "bargain"],          # caption/baslikta asla gecmez (kod kontrol eder)
  "banner": "serbest" | "kapali",                  # kapali -> gorsellerde banner yazisi hic olmaz
  "kurallar": [{"id": "k1", "metin": "Kirmizi kullanma", "kapsam": "gorsel"|"metin"|"hepsi", "aktif": true}]
}
Yapisal kurallar (yasaklar, banner, yasak kelimeler) KODLA uygulanir -> kesin.
Serbest metin kurallar ilgili ajanlarin LLM istemine eklenir -> yonlendirici.
"""
import json
import re
import uuid
from datetime import datetime

from .ayarlar import KOK, VERI

DOSYA = VERI / "marka_kurallari.json"
ALANLAR = ("duzen", "fontlar", "motif", "fiyat_stili", "efekt")
BOS = {"yasak": {a: [] for a in ALANLAR}, "yasak_kelimeler": [], "banner": "serbest", "kurallar": []}


def oku():
    try:
        d = json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    out = json.loads(json.dumps(BOS))
    out.update({k: v for k, v in d.items() if k in BOS})
    out["yasak"] = {a: list((d.get("yasak") or {}).get(a, [])) for a in ALANLAR}
    return out


def kaydet(veri):
    """Ofis ekranindan gelen veriyi temizleyip kaydeder."""
    from . import sanat
    gecerli = {"duzen": sanat.TUM_DUZENLER, "fontlar": sanat.FONTLAR, "motif": sanat.MOTIFLER,
               "fiyat_stili": sanat.FIYAT_STILLERI, "efekt": sanat.EFEKTLER}
    yasak = {}
    for a in ALANLAR:
        secili = [x for x in (veri.get("yasak") or {}).get(a, []) if x in gecerli[a]]
        if len(secili) >= len(gecerli[a]):   # hepsi yasaklanamaz; en az bir secenek kalmali
            secili = secili[:-1]
        yasak[a] = secili
    kelimeler = []
    for k in veri.get("yasak_kelimeler") or []:
        k = re.sub(r"\s+", " ", str(k)).strip()[:40]
        if k and k.lower() not in (x.lower() for x in kelimeler):
            kelimeler.append(k)
    kurallar = []
    for k in veri.get("kurallar") or []:
        metin = re.sub(r"\s+", " ", str(k.get("metin", ""))).strip()[:200]
        if not metin:
            continue
        kurallar.append({"id": k.get("id") or uuid.uuid4().hex[:8], "metin": metin,
                         "kapsam": k.get("kapsam") if k.get("kapsam") in ("gorsel", "metin", "hepsi") else "hepsi",
                         "aktif": bool(k.get("aktif", True)), "tarih": k.get("tarih") or datetime.now().strftime("%Y-%m-%d")})
    d = {"yasak": yasak, "yasak_kelimeler": kelimeler[:50],
         "banner": "kapali" if veri.get("banner") == "kapali" else "serbest", "kurallar": kurallar[:40]}
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def izinli(alan, liste):
    """liste'den yasaklananlari cikarir (bos kalirsa orijinali dondurur)."""
    y = set(oku()["yasak"].get(alan, []))
    return [x for x in liste if x not in y] or list(liste)


def serbest(kapsam):
    """'gorsel' veya 'metin' icin aktif serbest kurallar (hepsi dahil)."""
    return [k["metin"] for k in oku()["kurallar"] if k.get("aktif") and k.get("kapsam") in (kapsam, "hepsi")]


def istem(kapsam):
    """LLM istemine eklenecek blok. Kural yoksa bos."""
    d = oku()
    satirlar = serbest(kapsam)
    if kapsam == "metin" and d["yasak_kelimeler"]:
        satirlar.append("Never use these words: " + ", ".join(d["yasak_kelimeler"]))
    if kapsam == "gorsel" and d["banner"] == "kapali":
        satirlar.append("Never use a banner (banner must be empty).")
    if not satirlar:
        return ""
    return ("\nBRAND RULES from the business owner (always follow, they override everything else; "
            "rules may be written in Turkish):\n- " + "\n- ".join(satirlar) + "\n")


def yasak_kelime_bul(metin):
    m = (metin or "").lower()
    return [k for k in oku()["yasak_kelimeler"] if re.search(r"(?<!\w)" + re.escape(k.lower()) + r"(?!\w)", m)]
