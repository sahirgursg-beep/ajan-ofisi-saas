"""SaaS ortam ayarlari. Hepsi ortam degiskeninden gelir (Cloud Run'da Secret Manager doldurur).
Yerel gelistirmede .env dosyasi da okunur. Sirlar koda ve depoya ASLA yazilmaz."""
import os
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _env_dosyasi():
    yol = Path(os.environ.get("AJAN_ENV_DOSYA") or KOK / ".env")
    if not yol.exists():
        return
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        k, v = satir.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_env_dosyasi()


def al(ad, varsayilan=None, zorunlu=False):
    v = os.environ.get(ad, varsayilan)
    if zorunlu and not v:
        raise RuntimeError(f"Ortam degiskeni eksik: {ad}")
    return v


# ---- calisma bicimi ----
ORTAM = al("SAAS_ORTAM", "yerel")                 # yerel | bulut
DEPO = al("SAAS_DEPO", "yerel")                   # yerel (SQLite + klasor) | supabase
TETIK = al("SAAS_TETIK", "yerel")                 # isciyi tetikleme: yerel (alt surec) | surekli (VPS) | cloudrun | yok
GENEL_ADRES = al("SAAS_GENEL_ADRES", "http://localhost:8800").rstrip("/")   # panelin dis adresi (OAuth donusu)

# ---- yerel depo ----
YEREL_KLASOR = Path(al("SAAS_YEREL_KLASOR", str(KOK / ".saas_yerel")))

# ---- Supabase ----
SUPABASE_URL = (al("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVIS_ANAHTARI = al("SUPABASE_SERVICE_ROLE_KEY")   # yalnizca sunucuda; tarayiciya asla
SUPABASE_ANON_ANAHTARI = al("SUPABASE_ANON_KEY")             # panelde giris icin (gizli degil)
SUPABASE_JWT_SECRET = al("SUPABASE_JWT_SECRET")              # eski HS256 projeler; yoksa JWKS kullanilir
DEPO_KOVA = al("SAAS_DEPO_KOVA", "ajan-ofisi")

# ---- guvenlik ----
SIFRELEME_ANAHTARI = al("SAAS_SIFRELEME_ANAHTARI")      # Fernet anahtari: Meta tokenlarini sifreler
IMZA_ANAHTARI = al("SAAS_IMZA_ANAHTARI", "")             # OAuth state imzasi
ZAMANLAYICI_ANAHTARI = al("SAAS_ZAMANLAYICI_ANAHTARI", "")   # Cloud Scheduler -> /ic/zamanlayici
YEREL_GIRIS = al("SAAS_YEREL_GIRIS", "0") == "1"         # sadece gelistirme: e-postayla sahte giris

# ---- Meta uygulamasi (tek uygulama, her musteri kendi hesabini baglar) ----
META_APP_ID = al("META_APP_ID")
META_APP_SECRET = al("META_APP_SECRET")
META_GRAPH = al("AJAN_GRAPH_URL", "https://graph.facebook.com").rstrip("/")
META_DIALOG = al("META_DIALOG_URL", "https://www.facebook.com").rstrip("/")
META_VERSIYON = al("META_GRAPH_VERSIYON", "v23.0")
META_IZINLER = al("META_IZINLER", ",".join([
    "pages_show_list", "pages_read_engagement", "pages_manage_posts", "pages_read_user_content",
    "read_insights", "business_management", "instagram_basic", "instagram_content_publish",
    "instagram_manage_insights", "instagram_manage_comments",
]))

# ---- Cloud Run Job (isci) ----
GCP_PROJE = al("GCP_PROJE")
GCP_BOLGE = al("GCP_BOLGE", "europe-west1")
ISCI_IS_ADI = al("SAAS_ISCI_IS_ADI", "ajan-isci")
ISCI_EN_UZUN_DK = int(al("SAAS_ISCI_EN_UZUN_DK", "50"))     # bir isci calismasinin ust siniri

# ---- urun kurallari ----
DENEME_GUN = int(al("SAAS_DENEME_GUN", "14"))
VARSAYILAN_YZ = al("AJAN_YZ_SAGLAYICI", "openai")


def kontrol():
    """Bulutta acilista eksik sirlari erken yakala."""
    eksik = []
    if DEPO == "supabase":
        eksik += [a for a in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY") if not al(a)]
    if ORTAM == "bulut":
        eksik += [a for a in ("SAAS_SIFRELEME_ANAHTARI", "SAAS_IMZA_ANAHTARI", "META_APP_ID", "META_APP_SECRET")
                  if not al(a)]
        if TETIK == "cloudrun" and not al("SAAS_ZAMANLAYICI_ANAHTARI"):
            eksik.append("SAAS_ZAMANLAYICI_ANAHTARI")
        if YEREL_GIRIS:
            eksik.append("SAAS_YEREL_GIRIS bulutta kapali olmali")
    return eksik
