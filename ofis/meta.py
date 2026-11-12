"""Facebook Sayfasi + Instagram Business hesabi icin Meta Graph API istemcisi.

Erisim anahtari (token) yalnizca bu bilgisayarda, veri/meta.json icinde saklanir; hicbir yere gonderilmez
(Meta disinda). Bu modul YAYIN KARARI VERMEZ: ne zaman neyin yayinlanacagina yayin.py karar verir.
Mesajlara/yorumlara CEVAP YAZAN bir fonksiyon bilerek YOKTUR: ofis mesajlari sadece okur ve raporlar.
"""
import json
import os
import time
from pathlib import Path

import requests

from .ayarlar import AYAR, KOK, VERI

AYAR_DOSYA = VERI / "meta.json"
VERSIYON = AYAR.get("graph_versiyon", "v23.0")
TABAN = os.environ.get("AJAN_GRAPH_URL", "https://graph.facebook.com")   # test icin degistirilebilir


class MetaHata(Exception):
    pass


# ---------------- ayar ----------------
def ayar():
    try:
        return json.loads(AYAR_DOSYA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ayar_kaydet(a):
    AYAR_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    AYAR_DOSYA.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")


def bagli():
    a = ayar()
    return bool(a.get("page_token") and a.get("page_id"))


def durum():
    a = ayar()
    return {"bagli": bagli(), "sayfa": a.get("page_ad"), "instagram": a.get("ig_kullanici"),
            "ig_var": bool(a.get("ig_id"))}


# ---------------- istek ----------------
def _url(yol):
    return yol if yol.startswith("http") else f"{TABAN}/{VERSIYON}/{yol.lstrip('/')}"


def _cevap(r):
    try:
        j = r.json()
    except Exception:
        raise MetaHata(f"HTTP {r.status_code}: {r.text[:200]}")
    if isinstance(j, dict) and j.get("error"):
        e = j["error"]
        raise MetaHata(f"{e.get('message', 'Bilinmeyen hata')} (kod {e.get('code')}"
                       f"{', alt kod ' + str(e.get('error_subcode')) if e.get('error_subcode') else ''})")
    if r.status_code >= 400:
        raise MetaHata(f"HTTP {r.status_code}: {str(j)[:200]}")
    return j


def get(yol, token, **p):
    return _cevap(requests.get(_url(yol), params={**p, "access_token": token}, timeout=60))


def sil_istek(yol, token):
    return _cevap(requests.delete(_url(yol), params={"access_token": token}, timeout=60))


def post(yol, token, dosya=None, **p):
    files = {"source": (Path(dosya).name, open(dosya, "rb"))} if dosya else None
    try:
        return _cevap(requests.post(_url(yol), data={**p, "access_token": token}, files=files, timeout=300))
    finally:
        if files:
            files["source"][1].close()


# ---------------- baglanti ----------------
def sayfalari_bul(token):
    """Kullanici/sistem kullanicisi anahtari -> yonetilen sayfalar (+ bagli Instagram hesabi).
    Sayfa anahtari yapistirilmissa o sayfanin kendisi doner."""
    alanlar = "id,name,access_token,instagram_business_account{id,username}"
    try:
        sayfalar = get("me/accounts", token, fields=alanlar, limit=100).get("data", [])
    except MetaHata:
        sayfalar = []
    if not sayfalar:   # belki dogrudan bir SAYFA anahtari
        me = get("me", token, fields="id,name,instagram_business_account{id,username}")
        me["access_token"] = token
        sayfalar = [me]
    return [{"id": s["id"], "ad": s.get("name"), "token": s.get("access_token") or token,
             "ig_id": (s.get("instagram_business_account") or {}).get("id"),
             "ig_kullanici": (s.get("instagram_business_account") or {}).get("username")} for s in sayfalar]


def sayfa_sec(sayfa):
    a = ayar()
    a.update({"page_id": sayfa["id"], "page_ad": sayfa["ad"], "page_token": sayfa["token"],
              "ig_id": sayfa.get("ig_id"), "ig_kullanici": sayfa.get("ig_kullanici")})
    ayar_kaydet(a)
    return durum()


def baglantiyi_kes():
    if AYAR_DOSYA.exists():
        AYAR_DOSYA.unlink()


# ---------------- yardimcilar ----------------
def _gizli_foto_url(dosya):
    """Instagram gorseli herkese acik bir adresten ceker. Gorseli Facebook sayfasina YAYINLANMAMIS
    (gizli) foto olarak yukleyip Meta'nin kendi CDN adresini kullaniyoruz; sayfada gorunmez."""
    a = ayar()
    r = post(f"{a['page_id']}/photos", a["page_token"], dosya=dosya, published="false", temporary="true")
    foto = get(r["id"], a["page_token"], fields="images")
    resimler = sorted(foto.get("images", []), key=lambda x: -x.get("width", 0))
    if not resimler:
        raise MetaHata("Gorsel adresi alinamadi")
    return resimler[0]["source"], r["id"]


def _bekle_hazir(konteyner, token, sure=600):
    """Instagram medya kabinin islenmesini bekler (video icin dakikalar surebilir)."""
    bas = time.time()
    while time.time() - bas < sure:
        d = get(konteyner, token, fields="status_code,status")
        kod = d.get("status_code")
        if kod == "FINISHED":
            return True
        if kod in ("ERROR", "EXPIRED"):
            raise MetaHata(f"Instagram medyayi isleyemedi: {d.get('status')}")
        time.sleep(5 if kod == "IN_PROGRESS" else 3)
    raise MetaHata("Instagram isleme zaman asimi")


def _ig_yayinla(konteyner):
    a = ayar()
    _bekle_hazir(konteyner, a["page_token"])
    m = post(f"{a['ig_id']}/media_publish", a["page_token"], creation_id=konteyner)
    try:
        link = get(m["id"], a["page_token"], fields="permalink").get("permalink")
    except MetaHata:
        link = None
    return {"id": m["id"], "link": link}


def _rupload(adres, token, dosya):
    boyut = Path(dosya).stat().st_size
    with open(dosya, "rb") as f:
        r = requests.post(adres, data=f, timeout=900, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(boyut),
            "Content-Type": "application/octet-stream"})
    return _cevap(r)


# ---------------- Instagram ----------------
def ig_post(gorsel, metin):
    a = ayar()
    url, _ = _gizli_foto_url(gorsel)
    k = post(f"{a['ig_id']}/media", a["page_token"], image_url=url, caption=metin)
    return _ig_yayinla(k["id"])


def ig_story(gorsel):
    a = ayar()
    url, _ = _gizli_foto_url(gorsel)
    k = post(f"{a['ig_id']}/media", a["page_token"], image_url=url, media_type="STORIES")
    return _ig_yayinla(k["id"])


def ig_reels(video, metin, kapak_sn=11.5, deneme=False):
    """Video dogrudan bu bilgisayardan Instagram'a yuklenir (resumable upload).
    deneme=True: Instagram Deneme Reels'i (once takipci olmayanlara gosterilir, iyi giderse Instagram kendisi
    takipcilere acar - SS_PERFORMANCE)."""
    a = ayar()
    ek = {"trial_params": json.dumps({"graduation_strategy": "SS_PERFORMANCE"})} if deneme else {}
    k = post(f"{a['ig_id']}/media", a["page_token"], media_type="REELS", upload_type="resumable",
             caption=metin, share_to_feed="true", thumb_offset=str(int(kapak_sn * 1000)), **ek)
    adres = k.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VERSIYON}/{k['id']}"
    if TABAN != "https://graph.facebook.com" and "rupload.facebook.com" in adres:
        adres = adres.replace("https://rupload.facebook.com", TABAN)       # test sunucusu
    _rupload(adres, a["page_token"], video)
    return _ig_yayinla(k["id"])


def ig_carousel(gorseller, metin):
    """Instagram carousel: once her kart icin 'carousel ogesi' kabi, sonra hepsini baglayan ana kap."""
    a = ayar()
    if not 2 <= len(gorseller) <= 10:
        raise MetaHata("Carousel 2-10 gorsel olmali")
    cocuklar = []
    for g in gorseller:
        url, _ = _gizli_foto_url(g)
        k = post(f"{a['ig_id']}/media", a["page_token"], image_url=url, is_carousel_item="true")
        cocuklar.append(k["id"])
    for c in cocuklar:
        _bekle_hazir(c, a["page_token"], sure=180)
    k = post(f"{a['ig_id']}/media", a["page_token"], media_type="CAROUSEL", children=",".join(cocuklar), caption=metin)
    return _ig_yayinla(k["id"])


# ---------------- Facebook ----------------
def _plan(zaman_unix):
    """Facebook'un kendi zamanlamasi: yayinlanmamis + planli saat (Business Suite planlayicisinda gorunur)."""
    return {"published": "false", "scheduled_publish_time": str(int(zaman_unix))} if zaman_unix else {"published": "true"}


def fb_post(gorsel, metin, zaman_unix=None):
    a = ayar()
    r = post(f"{a['page_id']}/photos", a["page_token"], dosya=gorsel, message=metin, **_plan(zaman_unix))
    pid = r.get("post_id") or r["id"]
    return {"id": pid, "link": f"https://www.facebook.com/{pid}", "foto_id": r.get("id")}


def fb_carousel(gorseller, metin, zaman_unix=None):
    """Facebook'ta coklu fotografli gonderi: fotograflar yayinlanmamis yuklenir, tek gonderide birlestirilir."""
    a = ayar()
    idler = [post(f"{a['page_id']}/photos", a["page_token"], dosya=g, published="false")["id"] for g in gorseller]
    ek = {f"attached_media[{i}]": json.dumps({"media_fbid": fid}) for i, fid in enumerate(idler)}
    if zaman_unix:
        ek.update(_plan(zaman_unix))
    r = post(f"{a['page_id']}/feed", a["page_token"], message=metin, **ek)
    return {"id": r["id"], "link": f"https://www.facebook.com/{r['id']}"}


def fb_story(gorsel):
    a = ayar()
    r = post(f"{a['page_id']}/photos", a["page_token"], dosya=gorsel, published="false")
    s = post(f"{a['page_id']}/photo_stories", a["page_token"], photo_id=r["id"])
    return {"id": s.get("post_id") or s.get("id"), "link": None}


def fb_reels(video, metin, zaman_unix=None):
    a = ayar()
    bas = post(f"{a['page_id']}/video_reels", a["page_token"], upload_phase="start")
    adres = bas.get("upload_url") or f"https://rupload.facebook.com/video-upload/{VERSIYON}/{bas['video_id']}"
    if TABAN != "https://graph.facebook.com" and "rupload.facebook.com" in adres:
        adres = adres.replace("https://rupload.facebook.com", TABAN)
    _rupload(adres, a["page_token"], video)
    durum = {"video_state": "SCHEDULED", "scheduled_publish_time": str(int(zaman_unix))} if zaman_unix \
        else {"video_state": "PUBLISHED"}
    post(f"{a['page_id']}/video_reels", a["page_token"], upload_phase="finish", video_id=bas["video_id"],
         description=metin, **durum)
    return {"id": bas["video_id"], "link": f"https://www.facebook.com/reel/{bas['video_id']}"}


# ---------------- istatistik ----------------
IG_METRIKLER = {"post": ["reach", "likes", "saved", "shares", "comments", "views"],
                "reels": ["reach", "likes", "saved", "shares", "comments", "views"],
                "story": ["reach", "replies", "shares", "views"]}


def ig_istatistik(medya_id, tur="post"):
    """Metrikleri tek tek dener (Meta zaman zaman metrik adlarini degistiriyor; olmayan atlanir)."""
    a = ayar()
    sonuc = {}
    try:
        d = get(f"{medya_id}/insights", a["page_token"], metric=",".join(IG_METRIKLER[tur]))
        for m in d.get("data", []):
            sonuc[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
    except MetaHata:
        for metrik in IG_METRIKLER[tur]:
            try:
                d = get(f"{medya_id}/insights", a["page_token"], metric=metrik)
                for m in d.get("data", []):
                    sonuc[m["name"]] = (m.get("values") or [{}])[0].get("value")
            except MetaHata:
                continue
    return {k: v for k, v in sonuc.items() if isinstance(v, (int, float))}


def fb_ozet(nesne_id):
    """Facebook gonderisi/Reels: tepki, yorum, paylasim + (varsa) erisim/izlenme. Olmayan metrik atlanir."""
    a, sonuc = ayar(), {}
    try:
        d = get(nesne_id, a["page_token"],
                fields="shares,reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)")
        sonuc["likes"] = ((d.get("reactions") or {}).get("summary") or {}).get("total_count")
        sonuc["comments"] = ((d.get("comments") or {}).get("summary") or {}).get("total_count")
        sonuc["shares"] = (d.get("shares") or {}).get("count", 0) if "shares" in d or d else None
    except MetaHata:
        pass
    for yol, metrik in ((f"{nesne_id}/insights", "post_total_media_view_unique"),
                        (f"{nesne_id}/insights", "post_impressions_unique"),
                        (f"{nesne_id}/video_insights", "blue_reels_play_count"),
                        (f"{nesne_id}/video_insights", "post_impressions_unique")):
        try:
            for m in get(yol, a["page_token"], metric=metrik).get("data", []):
                v = (m.get("values") or [{}])[0].get("value")
                if isinstance(v, (int, float)):
                    sonuc.setdefault("views" if "view" in metrik or "play" in metrik else "reach", v)
        except MetaHata:
            continue
    return {k: v for k, v in sonuc.items() if isinstance(v, (int, float))}


def yayinda_mi(fb_id):
    """Facebook'ta planlanmis gonderi yayina girdi mi? (bilinmiyorsa None)"""
    a = ayar()
    try:
        return bool(get(fb_id, a["page_token"], fields="is_published").get("is_published"))
    except MetaHata:
        return None


def hesap_ozeti():
    """Takipci sayilari + Instagram takipcilerinin saatlik cevrimici dagilimi (en iyi saat icin)."""
    a, o = ayar(), {}
    try:
        o["fb_takipci"] = get(a["page_id"], a["page_token"], fields="followers_count,fan_count").get("followers_count")
    except MetaHata:
        pass
    if a.get("ig_id"):
        try:
            d = get(a["ig_id"], a["page_token"], fields="followers_count,media_count")
            o["ig_takipci"], o["ig_gonderi"] = d.get("followers_count"), d.get("media_count")
        except MetaHata:
            pass
        try:
            d = get(f"{a['ig_id']}/insights", a["page_token"], metric="online_followers", period="lifetime")
            v = ((d.get("data") or [{}])[0].get("values") or [{}])[-1].get("value")
            if isinstance(v, dict) and v:
                o["ig_cevrimici_saat"] = {str(k): int(x) for k, x in v.items()}   # saatler Meta'da Pasifik saati
        except MetaHata:
            pass
        try:
            d = get(f"{a['ig_id']}/insights", a["page_token"], metric="reach,profile_views,accounts_engaged",
                    period="day", metric_type="total_value")
            for m in d.get("data", []):
                v = (m.get("total_value") or {}).get("value")
                if isinstance(v, (int, float)):
                    o["ig_gunluk_" + m["name"]] = v
        except MetaHata:
            pass
    return o


# ---------------- baglanti testi ----------------
def tani():
    """Her yetenegi tek tek dener, Meta'nin kendi hata mesajiyla doner. Hicbir sey yayinlamaz/silmez.
    Sonuc veri/meta_tani.json'a yazilir (anahtar YAZILMAZ)."""
    a = ayar()
    tok, sonuc = a.get("page_token"), []

    def dene(ad, aciklama, f):
        try:
            d = f()
            sonuc.append({"ad": ad, "aciklama": aciklama, "ok": True, "bilgi": d})
        except Exception as e:
            sonuc.append({"ad": ad, "aciklama": aciklama, "ok": False, "hata": str(e)[:300]})

    def anahtar():
        d = get("debug_token", tok, input_token=tok).get("data", {})
        if d.get("is_valid") is False:
            raise MetaHata("Anahtar gecersiz: " + str((d.get("error") or {}).get("message", "")))
        return {"gecerli": d.get("is_valid"), "tur": d.get("type"), "uygulama": d.get("application"),
                "bitis": d.get("expires_at"), "izinler": d.get("scopes", []),
                "hata": (d.get("error") or {}).get("message")}
    dene("anahtar", "Anahtar geçerli mi, hangi izinler var", anahtar)
    dene("sayfa", "Facebook sayfasını okuma", lambda: {"ad": get(a["page_id"], tok, fields="name").get("name")})
    dene("fb_yayin_izni", "Facebook'ta paylaşım/planlama listesi (pages_manage_posts)",
         lambda: {"planli_sayisi": len(get(f"{a['page_id']}/scheduled_posts", tok, limit=5).get("data", []))})
    if a.get("ig_id"):
        dene("ig_hesap", "Instagram hesabını okuma", lambda: {"kullanici": get(a["ig_id"], tok, fields="username").get("username")})
        dene("ig_yayin_izni", "Instagram'a paylaşım kotası (instagram_content_publish)",
             lambda: get(f"{a['ig_id']}/content_publishing_limit", tok, fields="quota_usage,config").get("data", [{}])[0])
        dene("ig_istatistik", "Instagram istatistikleri (instagram_manage_insights)",
             lambda: {"n": len(get(f"{a['ig_id']}/insights", tok, metric="reach", period="day").get("data", []))})

        def yorum():
            m = get(f"{a['ig_id']}/media", tok, limit=1, fields="id").get("data", [])
            return {"son_gonderi_yorum": len(get(f"{m[0]['id']}/comments", tok, limit=5).get("data", []))} if m else {"gonderi": 0}
        dene("ig_yorum", "Instagram yorumlarını okuma (instagram_manage_comments)", yorum)
        dene("ig_dm", "Instagram DM okuma (instagram_manage_messages)",
             lambda: {"konusma": len(get(f"{a['page_id']}/conversations", tok, platform="instagram", limit=1).get("data", []))})
    dene("fb_dm", "Messenger mesajlarını okuma (pages_messaging)",
         lambda: {"konusma": len(get(f"{a['page_id']}/conversations", tok, platform="messenger", limit=1).get("data", []))})
    r = {"zaman": time.strftime("%Y-%m-%d %H:%M"), "sonuclar": sonuc}
    (VERI / "meta_tani.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    return r


def engel_mi(hata_metni):
    """Hesap/uygulama capinda engel ya da gecersiz anahtar: tekrar tekrar denemek durumu kotulestirir."""
    m = str(hata_metni)
    return any(x in m for x in ("API access blocked", "(kod 190", "(kod 368", "(kod 4,", "(kod 4)", "(kod 17",
                                "(kod 32", "(kod 613", "temporarily blocked", "Error validating access token"))


# ---------------- iletisim (SADECE OKUMA) ----------------
def ig_yorumlar(medya_id, limit=50):
    a = ayar()
    d = get(f"{medya_id}/comments", a["page_token"], limit=limit,
            fields="id,text,timestamp,username,like_count,replies{username,text,timestamp}")
    benim = (a.get("ig_kullanici") or "").lower()
    out = []
    for c in d.get("data", []):
        cevaplar = (c.get("replies") or {}).get("data", [])
        out.append({"id": c["id"], "metin": c.get("text", ""), "zaman": c.get("timestamp"), "kim": c.get("username"),
                    "cevaplandi": any((r.get("username") or "").lower() == benim for r in cevaplar),
                    "kendimiz": (c.get("username") or "").lower() == benim})
    return out


def fb_yorumlar(nesne_id, limit=50):
    a = ayar()
    d = get(f"{nesne_id}/comments", a["page_token"], limit=limit,
            fields="id,message,created_time,from{id,name},comments.limit(10){from{id}}")
    out = []
    for c in d.get("data", []):
        cevaplar = (c.get("comments") or {}).get("data", [])
        out.append({"id": c["id"], "metin": c.get("message", ""), "zaman": c.get("created_time"),
                    "kim": (c.get("from") or {}).get("name"),
                    "cevaplandi": any((r.get("from") or {}).get("id") == a["page_id"] for r in cevaplar),
                    "kendimiz": (c.get("from") or {}).get("id") == a["page_id"]})
    return out


def konusmalar(platform="instagram", limit=40):
    """Gelen kutusu (Messenger / Instagram DM) - sadece okunur. Izin yoksa MetaHata."""
    a = ayar()
    d = get(f"{a['page_id']}/conversations", a["page_token"], platform=platform, limit=limit,
            fields="id,updated_time,messages.limit(15){message,created_time,from}")
    benim = {str(a.get("page_id")), str(a.get("ig_id")), (a.get("ig_kullanici") or "").lower()}
    out = []
    for k in d.get("data", []):
        mesajlar = []
        for m in (k.get("messages") or {}).get("data", []):
            f = m.get("from") or {}
            mesajlar.append({"metin": m.get("message", ""), "zaman": m.get("created_time"),
                             "biz": str(f.get("id")) in benim or (f.get("username") or "").lower() in benim})
        out.append({"id": k["id"], "guncelleme": k.get("updated_time"), "mesajlar": mesajlar})
    return out


def sil(nesne_id):
    """Facebook gonderisi/Reels'i (planli ya da yayinda) veya Instagram medyasini siler.
    YALNIZCA kullanicinin 'Kaldir' istegiyle (yayin.kaldir) cagrilir."""
    a = ayar()
    r = sil_istek(nesne_id, a["page_token"])
    return bool(r.get("success", True)) if isinstance(r, dict) else True
