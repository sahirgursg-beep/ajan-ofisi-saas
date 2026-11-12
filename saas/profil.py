"""Kayit formundan musteri profili (ajanlarin profil.json'u) uretir ve dogrular.
Taban: musteriler/_sablon/profil.json. Musteriye donuk metinler Ingilizce."""
import copy
import json
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .ayar import KOK

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")
PARA = re.compile(r"^[A-Z]{3}$")
SAAT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ProfilHatasi(ValueError):
    def __init__(self, alanlar):
        self.alanlar = alanlar
        super().__init__("; ".join(f"{k}: {v}" for k, v in alanlar.items()))


def sablon():
    return json.loads((KOK / "musteriler" / "_sablon" / "profil.json").read_text(encoding="utf-8"))


def kimlik_uret(ad, mevcut=()):
    """'Oak & Ember Living' -> 'oak-ember-living' (cakisirsa -2, -3...)."""
    s = unicodedata.normalize("NFKD", ad).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "musteri"
    if s[0] in "-_":
        s = "m" + s
    aday, i = s, 2
    while aday in mevcut:
        aday, i = f"{s}-{i}", i + 1
    return aday


def _liste(v, en_fazla=20):
    if isinstance(v, str):
        v = [x for x in re.split(r"[,\n]", v)]
    return [str(x).strip() for x in (v or []) if str(x).strip()][:en_fazla]


def _saat_dilimi(ad):
    try:
        tz = ZoneInfo(ad)
    except (ZoneInfoNotFoundError, ValueError):
        raise ProfilHatasi({"saat_dilimi": "Gecersiz saat dilimi (or. Africa/Lagos)"})
    an = datetime.now(tz)
    return {"saat_dilimi": ad, "utc_ofset_saat": an.utcoffset().total_seconds() / 3600,
            "saat_kisaltma": an.tzname() if an.tzname() and not an.tzname()[0] in "+-" else ad.split("/")[-1]}


def formdan(form, taban=None):
    """Panel formu -> tam profil. Eksik alanlar sablondan gelir. Hatali alanlar ProfilHatasi ile doner."""
    p = copy.deepcopy(taban or sablon())
    p.pop("_aciklama", None)
    hata = {}
    f = {k: (v.strip() if isinstance(v, str) else v) for k, v in (form or {}).items()}
    i, m = p["isletme"], p["marka"]

    ad = f.get("isletme_adi") or i.get("ad")
    if not ad or ad == "Brand Name" or len(ad) > 80:
        hata["isletme_adi"] = "Isletme adi gerekli (en fazla 80 karakter)"
    else:
        i["ad"], m["ad"] = ad, f.get("marka_adi") or ad.upper()
    if f.get("tanim"):
        i["tanim"] = f["tanim"][:120]
    for k in ("sektor", "urun_turu", "ulke"):
        if f.get(k):
            i[k] = str(f[k])[:60]
    if f.get("ulke_kodu"):
        if not re.fullmatch(r"[A-Za-z]{2}", f["ulke_kodu"]):
            hata["ulke_kodu"] = "Iki harfli ulke kodu (NG, GH, KE...)"
        else:
            i["ulke_kodu"] = f["ulke_kodu"].upper()
    if "sehirler" in f:
        i["sehirler"] = _liste(f["sehirler"], 6)
    if "online_satis" in f:
        i["online_satis"] = bool(f["online_satis"])
    if f.get("satis_kanali"):
        i["satis_kanali"] = f["satis_kanali"][:200]
    elif "online_satis" in f:
        i["satis_kanali"] = ("Customers can order online or by phone/DM." if i["online_satis"] else
                             "Sales only happen in the store or by phone/DM, never tell people to buy online.")
    if f.get("cta"):
        m["cta"] = f["cta"][:80]
        i["yonlendirme"] = f["cta"][:80].rstrip(".").lower()
    for k in ("hashtagler", "proje_hashtagler", "carousel_maddeleri", "faydalar"):
        if k in f:
            i[k] = _liste(f[k], 15)
    if "hashtagler" in f:
        i["hashtagler"] = [("#" + h.lstrip("#")).replace(" ", "") for h in i["hashtagler"]]
    if f.get("saat_dilimi"):
        try:
            i.update(_saat_dilimi(f["saat_dilimi"]))
        except ProfilHatasi as e:
            hata.update(e.alanlar)
    for k in ("mesai_bas", "mesai_bit"):
        if f.get(k):
            if SAAT.match(f[k]):
                i[k] = f[k]
            else:
                hata[k] = "SS:DD bicimi (08:00)"

    for k in ("renk_koyu", "renk_kahve", "renk_altin", "renk_altin_acik", "renk_acik"):
        if f.get(k):
            if HEX.match(f[k]):
                m[k] = f[k].upper()
            else:
                hata[k] = "#RRGGBB bicimi"
    if f.get("web"):
        m["web"] = re.sub(r"^https?://", "", f["web"]).strip("/")[:80]
    if f.get("marka_tarif"):
        m["tarif"] = f["marka_tarif"][:160]

    for k in ("site", "feed_url"):
        if f.get(k):
            if URL.match(f[k]):
                p[k] = f[k]
            else:
                hata[k] = "http(s):// ile baslayan adres"
    if "kategoriler" in f:
        p["kategoriler"] = [x.lower() for x in _liste(f["kategoriler"], 20)]
    if "haric_kategoriler" in f:
        p["haric_kategoriler"] = [x.lower() for x in _liste(f["haric_kategoriler"], 20)]
    for k in ("para_birimi", "site_para_birimi"):
        if f.get(k):
            if PARA.match(f[k].upper()):
                p[k] = f[k].upper()
            else:
                hata[k] = "Uc harfli para kodu (NGN, USD...)"
    if f.get("para_sembolu"):
        p["para_sembolu"] = f["para_sembolu"][:4]
    if f.get("kur"):
        try:
            kur = float(f["kur"])
            assert kur > 0
            p["doviz_kurlari"] = {p.get("site_para_birimi", "USD"): kur}
        except (ValueError, AssertionError):
            hata["kur"] = "Pozitif sayi"
    if f.get("yuvarlama"):
        try:
            p["yuvarlama"] = max(1, int(f["yuvarlama"]))
        except ValueError:
            hata["yuvarlama"] = "Tam sayi"
    if "rakipler" in f:
        p["rakipler"] = [x.lstrip("@").lower() for x in _liste(f["rakipler"], 10)]

    if p.get("site_para_birimi") == p.get("para_birimi"):
        p["doviz_kurlari"] = {}
    elif p.get("site_para_birimi") not in (p.get("doviz_kurlari") or {}):
        hata.setdefault("kur", f"{p.get('site_para_birimi')} -> {p.get('para_birimi')} kuru gerekli")
    if not (p.get("feed_url") or (p.get("site") and p["site"] != "https://example.com")):
        hata.setdefault("site", "Urunlerin cekilecegi site ya da XML katalog adresi gerekli")
    if hata:
        raise ProfilHatasi(hata)
    return p


def form_gorunumu(p):
    """Profil -> panel formunun alanlari (duzenleme ekrani icin)."""
    i, m = p.get("isletme", {}), p.get("marka", {})
    return {
        "isletme_adi": i.get("ad"), "marka_adi": m.get("ad"), "tanim": i.get("tanim"), "sektor": i.get("sektor"),
        "ulke": i.get("ulke"), "ulke_kodu": i.get("ulke_kodu"), "sehirler": ", ".join(i.get("sehirler", [])),
        "online_satis": i.get("online_satis", False), "satis_kanali": i.get("satis_kanali"), "cta": m.get("cta"),
        "hashtagler": ", ".join(i.get("hashtagler", [])), "carousel_maddeleri": "\n".join(i.get("carousel_maddeleri", [])),
        "saat_dilimi": i.get("saat_dilimi"), "mesai_bas": i.get("mesai_bas"), "mesai_bit": i.get("mesai_bit"),
        "renk_koyu": m.get("renk_koyu"), "renk_altin": m.get("renk_altin"), "renk_acik": m.get("renk_acik"),
        "web": m.get("web"), "site": p.get("site"), "feed_url": p.get("feed_url"),
        "kategoriler": ", ".join(p.get("kategoriler", [])), "para_birimi": p.get("para_birimi"),
        "para_sembolu": p.get("para_sembolu"), "site_para_birimi": p.get("site_para_birimi"),
        "kur": next(iter((p.get("doviz_kurlari") or {}).values()), ""), "yuvarlama": p.get("yuvarlama"),
        "rakipler": ", ".join(p.get("rakipler", [])),
    }
