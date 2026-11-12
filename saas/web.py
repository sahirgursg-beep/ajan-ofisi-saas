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
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import ayar, guvenlik, kuyruk, meta_oauth, profil, yayin_durum, zamanlayici
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


def musteri_yetki(request, roller=("sahip", "editor", "izleyici")):
    k = kullanici(request)
    mid = request.path_params["mid"]
    if not depo().uye_mi(k["id"], mid, roller):
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


def musteri_ozeti(m, rol=None):
    i = (m.get("profil") or {}).get("isletme") or {}
    return {"id": m["id"], "ad": m["ad"], "durum": m["durum"], "deneme_bitis": m.get("deneme_bitis"), "rol": rol,
            "meta": m.get("meta_bilgi") or {}, "meta_bagli": bool(m.get("meta_token")),
            "meta_secim_bekliyor": bool(m.get("meta_aday")), "saat_dilimi": i.get("saat_dilimi"),
            "saat_kisaltma": i.get("saat_kisaltma"), "para": (m.get("profil") or {}).get("para_sembolu"),
            "yayin_ayar": m.get("yayin_ayar") or {}, "son_uretim": m.get("son_uretim")}


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
SURUM = "2026-11-12.fal"


async def saglik(request):
    var = lambda ad: bool(os.environ.get(ad, "").strip().lower() not in ayar.BOS)
    return JSONResponse({"durum": "ok", "ortam": ayar.ORTAM, "depo": ayar.DEPO, "eksik": ayar.kontrol(),
                         "surum": SURUM,
                         "servisler": {"yapay_zeka": var("AJAN_YZ_ANAHTAR"), "fal": var("FAL_KEY"),
                                       "pixabay": var("PIXABAY_API_KEY"), "pexels": var("PEXELS_API_KEY")}})


async def yapilandirma(request):
    """Panelin giris icin ihtiyaci (gizli degil)."""
    return JSONResponse({"supabase_url": ayar.SUPABASE_URL, "supabase_anon": ayar.SUPABASE_ANON_ANAHTARI,
                         "yerel_giris": ayar.YEREL_GIRIS and ayar.ORTAM != "bulut",
                         "meta_hazir": bool(ayar.META_APP_ID)})


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
    return JSONResponse({"kullanici": k, "musteriler": out})


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


async def panel(request):
    return FileResponse(PANEL / "index.html", headers={"Cache-Control": "no-cache"})


async def http_hatasi(request, exc):
    return JSONResponse({"hata": exc.detail}, status_code=exc.status_code)


async def guvenlik_basliklari(request, call_next):
    r = await call_next(request)
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    r.headers.setdefault("X-Frame-Options", "DENY")
    return r


M = "/api/musteri/{mid}"
routes = [
    Route("/", panel), Route("/saglik", saglik),
    Route("/api/yapilandirma", yapilandirma), Route("/api/yerel-giris", yerel_giris, methods=["POST"]),
    Route("/api/ben", ben), Route("/api/musteri", musteri_olustur, methods=["POST"]),
    Route(M + "/profil", profil_al), Route(M + "/profil", profil_guncelle, methods=["PUT"]),
    Route(M + "/yayin-ayar", yayin_ayari, methods=["PUT"]),
    Route(M + "/icerikler", icerik_listesi),
    Route(M + "/icerik/{klasor}/{islem}", icerik_karar, methods=["POST"]),
    Route(M + "/uret", uret, methods=["POST"]), Route(M + "/isler", is_listesi), Route(M + "/pano", pano),
    Route(M + "/meta/baglan", meta_baglan), Route(M + "/meta/adaylar", meta_adaylar),
    Route(M + "/meta/sec", meta_sec, methods=["POST"]), Route(M + "/meta/kes", meta_kes, methods=["POST"]),
    Route("/meta/geri", meta_geri),
    Route("/ic/zamanlayici", zamanlayici_ucu, methods=["POST"]),
    Route("/yerel-dosya/{anahtar:path}", yerel_dosya),
    Mount("/panel", StaticFiles(directory=str(PANEL)), name="panel"),
]

app = Starlette(routes=routes, exception_handlers={HTTPException: http_hatasi},
                middleware=[Middleware(BaseHTTPMiddleware, dispatch=guvenlik_basliklari)])
