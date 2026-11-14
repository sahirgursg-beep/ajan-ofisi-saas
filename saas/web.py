"""Web servisi (Cloud Run): panel, giris, musteri API'si, Meta baglantisi, zamanlayici ucu.
Calistirma: uvicorn saas.web:app --host 0.0.0.0 --port 8800

Her /api/musteri/<id>/... istegi: gecerli oturum + o musteriye uyelik sarttir (yazma icin sahip/editor).
Bu surec ofis/ paketini ice aktarmaz; ajan isleri kuyruga yazilir, isci yapar.
"""
import json
import os
import re
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import ayar, guvenlik, kuyruk, meta_oauth, profil, yayin_durum, yukleme, zamanlayici
from .depo import Cakisma, depo

PANEL = ayar.KOK / "saas" / "panel"
KLASOR_DESENI = re.compile(r"^[\w.-]{1,120}$")
YAZAN = ("sahip", "editor")


# ---------------------------------------------------------------- yardimcilar
def hata(mesaj, kod=400, **ek):
    return JSONResponse({"hata": mesaj, **ek}, status_code=kod)


async def govde(request):
    try:
        g = await request.json()
        return g if isinstance(g, dict) else {}
    except Exception:
        return {}


def kullanici(request):
    try:
        return guvenlik.kullanici_dogrula(request.headers.get("authorization"))
    except guvenlik.YetkiHatasi as e:
        raise HTTPException(401, str(e))


def yonetici_mi(k):
    return bool(k.get("eposta")) and k["eposta"].lower() in ayar.YONETICILER


def yonetici(request):
    k = kullanici(request)
    if not yonetici_mi(k):
        raise HTTPException(404, "Not found")
    return k


def musteri_yetki(request, roller=("sahip", "editor", "izleyici")):
    k = kullanici(request)
    mid = request.path_params["mid"]
    if not yonetici_mi(k) and not depo().uye_mi(k["id"], mid, roller):    # yonetici destek icin her musteriyi acar
        raise HTTPException(404, "Not found")          # baska musteri var mi yok mu bile soylenmez
    m = depo().musteri_al(mid)
    if not m:
        raise HTTPException(404, "Not found")
    return k, m


def tz(m):
    try:
        return ZoneInfo(((m.get("profil") or {}).get("isletme") or {}).get("saat_dilimi") or "UTC")
    except Exception:
        return timezone.utc


def _paket(m):
    from ofis import paketler
    kod = paketler.kod_of((m.get("profil") or {}).get("abonelik"))
    return {"kod": kod, "ad": paketler.al(kod)["ad"], "usd": paketler.al(kod)["usd"], "deneme": m.get("durum") == "deneme"}


def musteri_ozeti(m, rol=None):
    i = (m.get("profil") or {}).get("isletme") or {}
    return {"id": m["id"], "ad": m["ad"], "durum": m["durum"], "deneme_bitis": m.get("deneme_bitis"), "rol": rol,
            "meta": m.get("meta_bilgi") or {}, "meta_bagli": bool(m.get("meta_token")),
            "meta_secim_bekliyor": bool(m.get("meta_aday")), "saat_dilimi": i.get("saat_dilimi"),
            "saat_kisaltma": i.get("saat_kisaltma"), "para": (m.get("profil") or {}).get("para_sembolu"),
            "yayin_ayar": m.get("yayin_ayar") or {}, "son_uretim": m.get("son_uretim"),
            "logo_yuklendi": bool(((m.get("profil") or {}).get("marka") or {}).get("logo_yuklendi")),
            "paket": _paket(m),
            "site": (m.get("profil") or {}).get("site") or ""}


def icerik_gorunumu(mid, ic, adresler):
    y = ic.get("yayin") or {}
    try:
        platformlar = json.loads((ic.get("ekler") or {}).get("platformlar.json") or "{}")
    except ValueError:
        platformlar = {}
    return {"klasor": ic["klasor"], "tur": ic.get("tur"), "meta": ic.get("meta") or {}, "yayin": y,
            "platformlar": platformlar,
            "caption": y.get("caption") or ic.get("caption") or "", "surum": ic["surum"],
            "dosyalar": {ad: adresler.get(f"{mid}/cikti/{ic['klasor']}/{ad}") for ad in ic.get("dosyalar") or []}}


def klasor_dogrula(k):
    if not KLASOR_DESENI.match(k or ""):
        raise HTTPException(400, "Invalid content")
    return k


# ---------------------------------------------------------------- genel
SURUM = "2026-11-14.reels-yazi-maliyet"


async def saglik(request):
    var = lambda ad: bool(os.environ.get(ad, "").strip().lower() not in ayar.BOS)
    return JSONResponse({"durum": "ok", "ortam": ayar.ORTAM, "depo": ayar.DEPO, "eksik": ayar.kontrol(),
                         "surum": SURUM,
                         "servisler": {"yapay_zeka": var("AJAN_YZ_ANAHTAR"), "fal": var("FAL_KEY"),
                                       "pixabay": var("PIXABAY_API_KEY"), "pexels": var("PEXELS_API_KEY")}})


# ---------------------------------------------------------------- yuklemeler / logo / site kontrolu
async def _form_dosyalari(request, en_fazla=20):
    form = await request.form(max_files=en_fazla, max_fields=10, max_part_size=21 * 1024 * 1024)
    dosyalar = []
    for f in form.getlist("dosya"):
        if hasattr(f, "read"):
            dosyalar.append((f.filename or "dosya", await f.read()))
    return form, dosyalar


async def yukle(request):
    _, m = musteri_yetki(request, YAZAN)
    try:
        form, dosyalar = await _form_dosyalari(request)
    except Exception:
        return hata("Upload at most 20 files at once (photos under 15 MB, documents under 20 MB)")
    if not dosyalar:
        return hata("Choose at least one file")
    try:
        yeni = await run_in_threadpool(yukleme.ekle, depo(), m["id"], dosyalar, str(form.get("not") or ""))
    except yukleme.YuklemeHatasi as e:
        return hata(str(e))
    return JSONResponse({"eklenen": len(yeni), "dosyalar": await run_in_threadpool(yukleme.gorunum, depo(), m["id"])})


async def yuklemeler(request):
    _, m = musteri_yetki(request)
    return JSONResponse({"dosyalar": await run_in_threadpool(yukleme.gorunum, depo(), m["id"])})


async def yukleme_sil(request):
    _, m = musteri_yetki(request, YAZAN)
    ok = await run_in_threadpool(yukleme.sil, depo(), m["id"], request.path_params["kimlik"])
    if not ok:
        return hata("Not found", 404)
    return JSONResponse({"dosyalar": await run_in_threadpool(yukleme.gorunum, depo(), m["id"])})


async def logo_yukle(request):
    _, m = musteri_yetki(request, YAZAN)
    try:
        _, dosyalar = await _form_dosyalari(request, 1)
        if not dosyalar:
            return hata("Choose your logo file")
        palet = await run_in_threadpool(yukleme.logo_kaydet, depo(), m["id"], dosyalar[0][1])
    except yukleme.YuklemeHatasi as e:
        return hata(str(e))
    except Exception:
        return hata("Upload your logo as PNG or JPG (under 8 MB)")
    p = dict(m["profil"])
    marka = dict(p.get("marka") or {})
    sablon = profil.sablon().get("marka", {})
    if palet and all(marka.get(k) in (None, "", sablon.get(k)) for k in palet):   # renkleri kendisi secmediyse
        marka.update(palet)
    marka.update({"logo": "marka/logo.png", "logo_yuklendi": True, "logo_isleme": ""})
    p["marka"] = marka
    m = depo().musteri_guncelle(m["id"], profil=p)
    adres = depo().dosya_adresi(f"{m['id']}/yuklemeler/logo.png")
    return JSONResponse({"logo": adres, "renkler": {k: marka.get(k) for k in ("renk_koyu", "renk_altin", "renk_acik")},
                         "ozet": musteri_ozeti(m)})


async def logo_al(request):
    _, m = musteri_yetki(request)
    if not ((m.get("profil") or {}).get("marka") or {}).get("logo_yuklendi"):
        return JSONResponse({"logo": None})
    return JSONResponse({"logo": depo().dosya_adresi(f"{m['id']}/yuklemeler/logo.png")})


async def site_kontrol(request):
    kullanici(request)                      # yalnizca giris yapmis kullanicilar (acik vekil olmasin)
    g = await govde(request)
    from ofis import entegrasyon
    return JSONResponse(await run_in_threadpool(entegrasyon.site_bilgisi, str(g.get("site") or "")[:200]))


# ---------------------------------------------------------------- yonetim paneli (platform sahibi)
DURUMLAR = ("deneme", "aktif", "duraklatildi", "kapali")


def _harcama(d, mid):
    h = d.json_oku(f"{mid}/harcama.json", {}) or {}
    ay = datetime.now(timezone.utc).strftime("%Y-%m")
    kalem = ((h.get("_kalemler") or {}).get(ay)) or {}
    return {"bu_ay": round(float(h.get(ay, 0) or 0), 4), "kalemler": kalem}


def _yonetim_satiri(d, m, son_is=None):
    uyeler = d.uyeler(m["id"])
    i = (m.get("profil") or {}).get("isletme") or {}
    return {**musteri_ozeti(m), "sektor": i.get("sektor") or "", "sehir": ", ".join(i.get("sehirler") or []),
            "olusturma": m.get("olusturma"), "site": (m.get("profil") or {}).get("site") or "",
            "sahipler": [u.get("eposta") for u in uyeler if u.get("rol") == "sahip" and u.get("eposta")],
            "son_is": {k: (son_is or {}).get(k) for k in ("tur", "durum", "olusturma", "bitis")} if son_is else None}


async def yonetim_ozet(request):
    yonetici(request)
    d = depo()

    def topla():
        musteriler = d.musteriler()
        isler = d.son_isler(300)
        son = {}
        for i in isler:
            son.setdefault(i["musteri_id"], i)
        simdi = datetime.now(timezone.utc)
        satirlar = [_yonetim_satiri(d, m, son.get(m["id"])) for m in musteriler]
        for x in satirlar:
            x["harcama"] = _harcama(d, x["id"])
        bitiyor = [x["id"] for x in satirlar if x["durum"] == "deneme" and x.get("deneme_bitis")
                   and datetime.fromisoformat(x["deneme_bitis"]) - simdi < timedelta(days=3)]
        gun = simdi - timedelta(hours=24)
        son24 = [i for i in isler if i.get("olusturma") and datetime.fromisoformat(i["olusturma"]) > gun]
        return {
            "sayilar": {dr: sum(1 for m in musteriler if m["durum"] == dr) for dr in DURUMLAR} | {"toplam": len(musteriler)},
            "meta_bagli": sum(1 for x in satirlar if x["meta_bagli"]),
            "deneme_bitiyor": bitiyor,
            "isler_24s": {dr: sum(1 for i in son24 if i["durum"] == dr) for dr in ("bitti", "hata", "calisiyor", "bekliyor")},
            "kuyruk": sum(1 for i in isler if i["durum"] == "bekliyor"),
            "harcama_bu_ay": round(sum(x["harcama"]["bu_ay"] for x in satirlar), 2),
            "sabit_aylik": float(ayar.al("SAAS_SABIT_AYLIK_USD", "62") or 62),
            "musteriler": satirlar,
            "servisler": {a: bool((os.environ.get(a) or "").strip()) for a in
                          ("AJAN_YZ_ANAHTAR", "FAL_KEY", "PIXABAY_API_KEY", "META_APP_ID", "RESEND_API_KEY")},
            "surum": SURUM}
    return JSONResponse(await run_in_threadpool(topla))


async def yonetim_isler(request):
    yonetici(request)
    durum = request.query_params.get("durum") or None
    isler = await run_in_threadpool(depo().son_isler, 100, durum)
    return JSONResponse({"isler": isler})


async def yonetim_kutuphane(request):
    yonetici(request)
    from . import kutuphane
    if request.method == "POST":
        await run_in_threadpool(kutuphane.zorla)
        return JSONResponse({"durum": "ok"})
    return JSONResponse(await run_in_threadpool(kutuphane.yonetim_ozeti))


async def yonetim_musteri(request):
    yonetici(request)
    mid = request.path_params["mid"]
    d = depo()
    m = d.musteri_al(mid)
    if not m:
        return hata("Not found", 404)

    def topla():
        isler = d.isler(mid, 15)
        return {**_yonetim_satiri(d, m, isler[0] if isler else None), "harcama": _harcama(d, mid),
                "isler": isler, "pano": d.pano_son(mid, 40), "yayin_ayar": m.get("yayin_ayar") or {},
                "profil": profil.form_gorunumu(m["profil"])}
    return JSONResponse(await run_in_threadpool(topla))


async def yonetim_islem(request):
    """POST /api/yonetim/musteri/<id>/<islem>: durum | deneme_uzat | uret | otomatik"""
    k = yonetici(request)
    mid, islem = request.path_params["mid"], request.path_params["islem"]
    d = depo()
    m = d.musteri_al(mid)
    if not m:
        return hata("Not found", 404)
    g = await govde(request)
    if islem == "durum":
        if g.get("durum") not in DURUMLAR:
            return hata("Unknown status")
        m = d.musteri_guncelle(mid, durum=g["durum"])
    elif islem == "deneme_uzat":
        gun = int(g.get("gun") or 7)
        if not 1 <= gun <= 90:
            return hata("1-90 days")
        taban = max(datetime.now(timezone.utc), datetime.fromisoformat(m["deneme_bitis"]) if m.get("deneme_bitis")
                    else datetime.now(timezone.utc))
        m = d.musteri_guncelle(mid, deneme_bitis=(taban + timedelta(days=gun)).isoformat(timespec="seconds"),
                               durum="deneme" if m["durum"] in ("duraklatildi", "kapali", "deneme") else m["durum"])
    elif islem == "uret":
        if not kuyruk.is_ekle(mid, "uret", {"demo": False, "plansiz": True}):
            return hata("A production job is already waiting")
    elif islem == "plan":
        from ofis import paketler
        if g.get("plan") not in paketler.PAKETLER:
            return hata("Unknown plan")
        p = dict(m["profil"])
        p["abonelik"] = {**(p.get("abonelik") or {}), "plan": g["plan"]}
        m = d.musteri_guncelle(mid, profil=p)
    elif islem == "otomatik":
        ya = dict(m.get("yayin_ayar") or {})
        ya["otomatik"] = bool(g.get("otomatik"))
        m = d.musteri_guncelle(mid, yayin_ayar=ya)
    else:
        return hata("Unknown action", 404)
    print(f"YONETIM {k.get('eposta')} {mid} {islem} {g}", flush=True)
    return JSONResponse({"tamam": True, "musteri": _yonetim_satiri(d, d.musteri_al(mid))})


async def yonetim_sayfasi(request):
    return FileResponse(PANEL / "yonetim.html", headers={"Cache-Control": "no-cache"})


async def sektorler(request):
    """Kayit formu icin sektorler ve her sektorde sunulan isler (oneri cipleri)."""
    from ofis import sektor_isleri
    return JSONResponse({"sektorler": sektor_isleri.liste()}, headers={"Cache-Control": "public, max-age=3600"})


async def fiyatlar(request):
    """Paketler: USD + istenen para biriminde yaklasik karsiligi. ?para=EUR (yoksa ?ulke=DE'den bulunur)."""
    from ofis import paketler, ulkeler
    from . import kur
    para = (request.query_params.get("para") or "").upper()[:3]
    if not para:
        u = ulkeler.al(request.query_params.get("ulke"))
        para = u["para"] if u else "USD"
    sembol = next((u["sembol"] for u in ulkeler.ULKELER.values() if u["para"] == para), para)
    out, tarih = [], ""
    for p in paketler.liste():
        yerel, tarih = await run_in_threadpool(kur.cevir, p["usd"], para)
        out.append({**p, "yerel": yerel})
    kurlar, _ = await run_in_threadpool(kur.kurlar)
    paralar = sorted({u["para"] for u in ulkeler.ULKELER.values()} | {"USD", "EUR", "GBP"})
    return JSONResponse({"para": para if out[0]["yerel"] is not None else "USD", "sembol": sembol, "kur_tarihi": tarih,
                         "deneme_gun": ayar.DENEME_GUN, "paketler": out,
                         "paralar": [x for x in paralar if x == "USD" or x in kurlar]},
                        headers={"Cache-Control": "public, max-age=3600"})


async def ulkeler_ucu(request):
    from ofis import ulkeler
    return JSONResponse({"ulkeler": ulkeler.liste(), "diller": ulkeler.DILLER},
                        headers={"Cache-Control": "public, max-age=86400"})


async def sektor_tahmin(request):
    from ofis import sektor_isleri
    return JSONResponse({"sektor": sektor_isleri.tahmin(request.query_params.get("metin", "")[:300])})


async def yapilandirma(request):
    """Panelin giris icin ihtiyaci (gizli degil)."""
    return JSONResponse({"supabase_url": ayar.SUPABASE_URL, "supabase_anon": ayar.SUPABASE_ANON_ANAHTARI,
                         "yerel_giris": ayar.YEREL_GIRIS and ayar.ORTAM != "bulut",
                         "meta_hazir": bool(ayar.META_APP_ID), "destek": ayar.al("SAAS_DESTEK_EPOSTA") or ""})


async def yerel_giris(request):
    if not (ayar.YEREL_GIRIS and ayar.ORTAM != "bulut"):
        return hata("Not available", 404)
    g = await govde(request)
    eposta = str(g.get("eposta") or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", eposta):
        return hata("Enter a valid email")
    return JSONResponse({"belirtec": guvenlik.yerel_belirtec(eposta)})


async def ben(request):
    k = kullanici(request)
    d = depo()
    out = []
    for u in d.uyelikler(k["id"]):
        m = d.musteri_al(u["musteri_id"])
        if m:
            out.append(musteri_ozeti(m, u["rol"]))
    hedef = request.query_params.get("musteri")
    if yonetici_mi(k) and hedef and not any(x["id"] == hedef for x in out):    # yonetici bir musterinin panelini acar
        m = d.musteri_al(hedef)
        if m:
            out.insert(0, musteri_ozeti(m, "yonetici"))
    return JSONResponse({"kullanici": {**k, "yonetici": yonetici_mi(k)}, "musteriler": out})


# ---------------------------------------------------------------- musteri olusturma / profil
async def musteri_olustur(request):
    k = kullanici(request)
    d = depo()
    if sum(1 for u in d.uyelikler(k["id"]) if u["rol"] == "sahip") >= 3:
        return hata("One account can create up to 3 businesses", 403)
    g = await govde(request)
    try:
        p = profil.formdan(g)
    except profil.ProfilHatasi as e:
        return hata("Some fields need attention", 422, alanlar=e.alanlar)
    mevcut = {m["id"] for m in d.musteriler()}
    mid = profil.kimlik_uret(p["isletme"]["ad"], mevcut)
    bitis = (datetime.now(timezone.utc) + timedelta(days=ayar.DENEME_GUN)).isoformat(timespec="seconds")
    for _ in range(3):
        try:
            m = d.musteri_ekle({"id": mid, "ad": p["isletme"]["ad"], "profil": p, "durum": "deneme",
                                "deneme_bitis": bitis, "yayin_ayar": {"otomatik": True}})   # az insan onayi: kalite kontrolden gecen kendiliginden yayinlanir
            break
        except Cakisma:
            mid = profil.kimlik_uret(p["isletme"]["ad"], mevcut | {mid})
    else:
        return hata("Could not create the business, please try again", 409)
    d.uyelik_ekle(k["id"], mid, "sahip", k.get("eposta"))
    return JSONResponse(musteri_ozeti(m, "sahip"), status_code=201)


async def profil_al(request):
    _, m = musteri_yetki(request)
    return JSONResponse({"form": profil.form_gorunumu(m["profil"]), "ozet": musteri_ozeti(m)})


async def profil_guncelle(request):
    _, m = musteri_yetki(request, YAZAN)
    g = await govde(request)
    try:
        p = profil.formdan(g, taban=m["profil"])
    except profil.ProfilHatasi as e:
        return hata("Some fields need attention", 422, alanlar=e.alanlar)
    m = depo().musteri_guncelle(m["id"], profil=p, ad=p["isletme"]["ad"])
    return JSONResponse({"form": profil.form_gorunumu(m["profil"]), "ozet": musteri_ozeti(m)})


async def yayin_ayari(request):
    _, m = musteri_yetki(request, YAZAN)
    g = await govde(request)
    ya = dict(m.get("yayin_ayar") or {})
    if "otomatik" in g:
        ya["otomatik"] = bool(g["otomatik"])
    for k in ("mesai_bas", "mesai_bit", "uretim_saati"):
        if k in g:
            if not profil.SAAT.match(str(g[k])):
                return hata(f"{k}: use HH:MM")
            ya[k] = g[k]
    if "saatler" in g and isinstance(g["saatler"], dict):
        s = {t: v for t, v in g["saatler"].items() if t in ("post", "carousel", "reels") and profil.SAAT.match(str(v))}
        ya["saatler"] = {**(ya.get("saatler") or {}), **s}
    m = depo().musteri_guncelle(m["id"], yayin_ayar=ya)
    return JSONResponse(musteri_ozeti(m))


# ---------------------------------------------------------------- icerikler
async def icerik_listesi(request):
    _, m = musteri_yetki(request)
    d = depo()
    ic = d.icerikler(m["id"], min(int(request.query_params.get("n", 30)), 80))
    anahtarlar = [f"{m['id']}/cikti/{x['klasor']}/{a}" for x in ic for a in x.get("dosyalar") or []]
    adresler = d.dosya_adresleri(anahtarlar, 3600)
    return JSONResponse({"icerikler": [icerik_gorunumu(m["id"], x, adresler) for x in ic],
                         "hedefler": yayin_durum.HEDEFLER,
                         "simdi": datetime.now(tz(m)).strftime("%Y-%m-%dT%H:%M")})


async def icerik_karar(request):
    """POST /api/musteri/<id>/icerik/<klasor>/<islem>: onayla | reddet | geri_al | kaldir | revize | tekrar"""
    k, m = musteri_yetki(request, YAZAN)
    klasor = klasor_dogrula(request.path_params["klasor"])
    islem = request.path_params["islem"]
    g = await govde(request)
    d = depo()
    ic = d.icerik_al(m["id"], klasor)
    if not ic:
        return hata("Content not found", 404)
    if "surum" in g and int(g["surum"]) != ic["surum"]:
        return hata("This content changed in the meantime; please refresh", 409)
    z, is_turu, is_param = tz(m), None, None
    try:
        y = ic.get("yayin") or {}
        if islem == "onayla":
            y = yayin_durum.onayla(y, g.get("hedefler"), g.get("zaman") or "", g.get("metin") or ic.get("caption"), z,
                                   kaynak=f"panel:{k.get('eposta') or k['id']}")
            if not y["zaman"] or y.get("bekleyen_iptal"):
                is_turu = "yayin_turu"
        elif islem == "reddet":
            y = yayin_durum.reddet(y, z)
            is_turu = "yayin_turu" if y.get("bekleyen_iptal") else None
        elif islem == "geri_al":
            y = yayin_durum.geri_al(y, z)
            is_turu = "yayin_turu" if y.get("bekleyen_iptal") else None
        elif islem == "kaldir":
            y, gerek = yayin_durum.kaldir_istegi(y, z)
            if gerek:
                is_turu, is_param = "kaldir", {"klasor": klasor}
        elif islem == "revize":
            y = yayin_durum.revize_iste(y, g.get("secenekler") or [], g.get("not"), z)
            is_turu, is_param = "revize", {"klasor": klasor}
        elif islem == "tekrar":
            y, is_turu = yayin_durum.tekrar_dene(y)
            is_param = {"klasor": klasor} if is_turu == "kaldir" else None
        else:
            return hata("Unknown action", 404)
    except yayin_durum.KararHatasi as e:
        return hata(str(e), 409)
    try:
        yeni = d.icerik_yaz(m["id"], {"klasor": klasor, "yayin": y,
                                      "caption": y.get("caption", ic.get("caption", ""))}, beklenen_surum=ic["surum"])
    except Cakisma:
        return hata("This content changed in the meantime; please refresh", 409)
    is_ = kuyruk.is_ekle(m["id"], is_turu, is_param or {}) if is_turu else None
    return JSONResponse({"yayin": y, "surum": yeni, "is": is_ and {"id": is_["id"], "tur": is_["tur"]}})


async def uret(request):
    _, m = musteri_yetki(request, YAZAN)
    if m["durum"] in ("duraklatildi", "kapali"):
        return hata("Your subscription is paused", 402)
    g = await govde(request)
    is_ = kuyruk.is_ekle(m["id"], "uret", {"demo": bool(g.get("demo")), "plansiz": bool(g.get("plansiz", True))})
    return JSONResponse({"is": is_}, status_code=202)


async def is_listesi(request):
    _, m = musteri_yetki(request)
    return JSONResponse({"isler": [{k: v for k, v in i.items() if k != "isci"} for i in depo().isler(m["id"], 20)]})


async def pano(request):
    _, m = musteri_yetki(request)
    return JSONResponse({"mesajlar": depo().pano_son(m["id"], 60, int(request.query_params.get("sonra", 0)))})


# ---------------------------------------------------------------- Meta baglantisi
async def meta_baglan(request):
    k, m = musteri_yetki(request, ("sahip",))
    try:
        return JSONResponse({"adres": meta_oauth.izin_adresi(m["id"], k["id"])})
    except meta_oauth.MetaBaglantiHatasi as e:
        return hata(str(e), 503)


async def meta_geri(request):
    q = request.query_params
    if q.get("error"):
        return RedirectResponse("/#meta=iptal", 302)
    try:
        st = guvenlik.imza_coz(q.get("state", ""))
    except guvenlik.YetkiHatasi:
        return RedirectResponse("/#meta=gecersiz", 302)
    d = depo()
    if not d.uye_mi(st["uid"], st["mid"], ("sahip",)):
        return RedirectResponse("/#meta=gecersiz", 302)
    try:
        sayfalar = meta_oauth.kodu_coz(q.get("code", ""))
    except meta_oauth.MetaBaglantiHatasi as e:
        return RedirectResponse(f"/#meta=hata&mesaj={quote(str(e)[:120])}", 302)
    if len(sayfalar) == 1:
        s = sayfalar[0]
        d.musteri_guncelle(st["mid"], meta_token=guvenlik.sifrele(s), meta_bilgi=meta_oauth.herkese_acik(s),
                           meta_aday=None)
        return RedirectResponse(f"/#musteri={st['mid']}&meta=bagli", 302)
    d.musteri_guncelle(st["mid"], meta_aday=guvenlik.sifrele(sayfalar))
    return RedirectResponse(f"/#musteri={st['mid']}&meta=sec", 302)


async def meta_adaylar(request):
    _, m = musteri_yetki(request, ("sahip",))
    return JSONResponse({"sayfalar": [meta_oauth.herkese_acik(s) for s in guvenlik.coz(m.get("meta_aday")) or []]})


async def meta_sec(request):
    _, m = musteri_yetki(request, ("sahip",))
    g = await govde(request)
    s = next((x for x in guvenlik.coz(m.get("meta_aday")) or [] if x["page_id"] == str(g.get("page_id"))), None)
    if not s:
        return hata("Page not found; please reconnect", 404)
    m = depo().musteri_guncelle(m["id"], meta_token=guvenlik.sifrele(s), meta_bilgi=meta_oauth.herkese_acik(s),
                                meta_aday=None)
    return JSONResponse(musteri_ozeti(m))


async def meta_kes(request):
    _, m = musteri_yetki(request, ("sahip",))
    m = depo().musteri_guncelle(m["id"], meta_token=None, meta_bilgi={}, meta_aday=None)
    return JSONResponse(musteri_ozeti(m))


# ---------------------------------------------------------------- ic uclar
async def zamanlayici_ucu(request):
    try:
        guvenlik.zamanlayici_dogrula(request.headers.get("x-zamanlayici-anahtari"))
    except guvenlik.YetkiHatasi:
        return hata("Unauthorized", 401)
    return JSONResponse(zamanlayici.tur())


async def yerel_dosya(request):
    """Yalnizca yerel depo: imzali, sureli dosya adresi (Supabase'de bunu Storage yapar)."""
    d = depo()
    if not hasattr(d, "imzali_oku"):
        return hata("Not found", 404)
    yol = d.imzali_oku(request.path_params["anahtar"], request.query_params.get("son", "0"),
                       request.query_params.get("imza", ""))
    return FileResponse(yol) if yol else hata("Not found", 404)


def site_alani_mi(request):
    from urllib.parse import urlparse
    host = (request.headers.get("host") or "").split(":")[0].lower()
    ana = urlparse(ayar.SITE_ADRES).hostname or ""
    return bool(ana) and host in (ana, "www." + ana.removeprefix("www."))


async def panel(request):
    if site_alani_mi(request):                 # feedzync.com -> ziyaretcinin dilindeki tanitim sitesi
        from .site import sayfa as site
        return RedirectResponse(f"/{site.dil_sec(request.headers.get('accept-language'))}/", 302)
    return FileResponse(PANEL / "index.html", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- tanitim sitesi
SITE_CSS = ayar.KOK / "saas" / "site" / "site.css"


def _site_cevap(icerik, request):
    if icerik is None:
        raise HTTPException(404, "Not found")
    return Response(icerik, media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=600"})


async def site_dil(request):
    from .site import metin, sayfa as site
    dil, alt = request.path_params["dil"], request.path_params.get("sayfa", "")
    if dil not in metin.DILLER:
        raise HTTPException(404, "Not found")
    u = ayar.GENEL_ADRES
    if alt == "":
        return _site_cevap(site.ana(ayar.SITE_ADRES, u, dil), request)
    if alt == "pricing":
        return _site_cevap(site.fiyat(ayar.SITE_ADRES, u, dil), request)
    if alt == "faq":
        return _site_cevap(site.sss(ayar.SITE_ADRES, u, dil), request)
    if alt == "industries" and dil == "en":
        return _site_cevap(site.sektorler_sayfasi(ayar.SITE_ADRES, u), request)
    raise HTTPException(404, "Not found")


async def site_sektor(request):
    from .site import sayfa as site
    return _site_cevap(site.sektor_sayfasi(ayar.SITE_ADRES, ayar.GENEL_ADRES, request.path_params["sl"]), request)


async def site_yasal(request):
    from .site import sayfa as site
    return _site_cevap(site.yasal(ayar.SITE_ADRES, ayar.GENEL_ADRES, request.path_params["ad"]), request)


async def site_haritasi(request):
    from .site import sayfa as site
    return Response(site.site_haritasi(ayar.SITE_ADRES), media_type="application/xml")


async def robots(request):
    if site_alani_mi(request):
        govde = f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /yonetim\nSitemap: {ayar.SITE_ADRES}/sitemap.xml\n"
    else:                                       # uygulama alani arama motorlarinda gorunmesin
        govde = "User-agent: *\nDisallow: /\n"
    return Response(govde, media_type="text/plain")


async def site_css(request):
    return FileResponse(SITE_CSS, headers={"Cache-Control": "public, max-age=86400"})


async def http_hatasi(request, exc):
    return JSONResponse({"hata": exc.detail}, status_code=exc.status_code)


async def guvenlik_basliklari(request, call_next):
    r = await call_next(request)
    if not site_alani_mi(request):
        r.headers.setdefault("X-Robots-Tag", "noindex")      # uygulama + onizleme: dizine eklenmez
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    r.headers.setdefault("X-Frame-Options", "DENY")
    return r


M = "/api/musteri/{mid}"
routes = [
    Route("/", panel), Route("/saglik", saglik),
    Route("/api/yapilandirma", yapilandirma), Route("/api/sektorler", sektorler),
    Route("/api/sektor-tahmin", sektor_tahmin), Route("/api/ulkeler", ulkeler_ucu), Route("/api/fiyatlar", fiyatlar), Route("/api/yerel-giris", yerel_giris, methods=["POST"]),
    Route("/api/ben", ben), Route("/api/musteri", musteri_olustur, methods=["POST"]),
    Route(M + "/profil", profil_al), Route(M + "/profil", profil_guncelle, methods=["PUT"]),
    Route(M + "/yayin-ayar", yayin_ayari, methods=["PUT"]),
    Route(M + "/icerikler", icerik_listesi),
    Route(M + "/yukle", yukle, methods=["POST"]), Route(M + "/yuklemeler", yuklemeler),
    Route(M + "/yukleme/{kimlik}/sil", yukleme_sil, methods=["POST"]),
    Route(M + "/logo", logo_yukle, methods=["POST"]), Route(M + "/logo", logo_al),
    Route("/api/site-kontrol", site_kontrol, methods=["POST"]),
    Route("/yonetim", yonetim_sayfasi), Route("/api/yonetim/ozet", yonetim_ozet),
    Route("/api/yonetim/isler", yonetim_isler), Route("/api/yonetim/kutuphane", yonetim_kutuphane, methods=["GET", "POST"]),
    Route("/api/yonetim/musteri/{mid}", yonetim_musteri),
    Route("/api/yonetim/musteri/{mid}/{islem}", yonetim_islem, methods=["POST"]),
    Route(M + "/icerik/{klasor}/{islem}", icerik_karar, methods=["POST"]),
    Route(M + "/uret", uret, methods=["POST"]), Route(M + "/isler", is_listesi), Route(M + "/pano", pano),
    Route(M + "/meta/baglan", meta_baglan), Route(M + "/meta/adaylar", meta_adaylar),
    Route(M + "/meta/sec", meta_sec, methods=["POST"]), Route(M + "/meta/kes", meta_kes, methods=["POST"]),
    Route("/meta/geri", meta_geri),
    Route("/ic/zamanlayici", zamanlayici_ucu, methods=["POST"]),
    Route("/yerel-dosya/{anahtar:path}", yerel_dosya),
    Mount("/panel", StaticFiles(directory=str(PANEL)), name="panel"),
    Route("/site.css", site_css), Route("/sitemap.xml", site_haritasi), Route("/robots.txt", robots),
    Route("/legal/{ad}", site_yasal), Route("/en/industries/{sl}", site_sektor),
    Route("/{dil}/", site_dil), Route("/{dil}/{sayfa}", site_dil),
]

app = Starlette(routes=routes, exception_handlers={HTTPException: http_hatasi},
                middleware=[Middleware(BaseHTTPMiddleware, dispatch=guvenlik_basliklari)])
