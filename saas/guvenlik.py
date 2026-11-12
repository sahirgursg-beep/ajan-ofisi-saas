"""Kimlik dogrulama, sifreleme ve imzalar.

- Giris: Supabase Auth. Tarayici Supabase'den aldigi JWT'yi 'Authorization: Bearer' ile yollar; sunucu
  imzayi dogrular (yeni projeler: JWKS / ES256-RS256, eski projeler: HS256 JWT secret).
- Meta sayfa anahtarlari veritabaninda Fernet ile SIFRELI durur; anahtar yalnizca ortam degiskeninde.
- OAuth 'state' degeri imzali ve sureli (CSRF ve baska musteriye baglama engeli).
"""
import base64
import hashlib
import hmac
import json
import time

import jwt
from cryptography.fernet import Fernet, InvalidToken

from . import ayar

YEREL_JWT_SIRRI = "yerel-gelistirme-sirri-bulutta-kullanilmaz"


class YetkiHatasi(Exception):
    pass


# ---------------- giris (JWT) ----------------
_jwks = None


def _jwks_istemci():
    global _jwks
    if _jwks is None:
        _jwks = jwt.PyJWKClient(f"{ayar.SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True)
    return _jwks


def kullanici_dogrula(baslik):
    """'Bearer <jwt>' -> {"id", "eposta"}. Gecersizse YetkiHatasi."""
    if not baslik or not baslik.lower().startswith("bearer "):
        raise YetkiHatasi("Sign-in required")
    belirtec = baslik.split(" ", 1)[1].strip()
    try:
        if ayar.YEREL_GIRIS and ayar.ORTAM != "bulut":
            veri = jwt.decode(belirtec, YEREL_JWT_SIRRI, algorithms=["HS256"], audience="authenticated")
        elif ayar.SUPABASE_JWT_SECRET:
            veri = jwt.decode(belirtec, ayar.SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
        else:
            anahtar = _jwks_istemci().get_signing_key_from_jwt(belirtec).key
            veri = jwt.decode(belirtec, anahtar, algorithms=["ES256", "RS256"], audience="authenticated")
    except jwt.PyJWTError as e:
        raise YetkiHatasi(f"Invalid session: {e}")
    if not veri.get("sub"):
        raise YetkiHatasi("Invalid session")
    return {"id": veri["sub"], "eposta": veri.get("email")}


def yerel_belirtec(eposta):
    """SADECE gelistirme: e-postadan sabit kullanici kimligi ureten sahte giris."""
    if not ayar.YEREL_GIRIS or ayar.ORTAM == "bulut":
        raise YetkiHatasi("Yerel giris kapali")
    kid = hashlib.sha256(eposta.lower().encode()).hexdigest()
    uid = f"{kid[:8]}-{kid[8:12]}-4{kid[13:16]}-a{kid[17:20]}-{kid[20:32]}"
    return jwt.encode({"sub": uid, "email": eposta, "aud": "authenticated", "exp": int(time.time()) + 86400},
                      YEREL_JWT_SIRRI, algorithm="HS256")


# ---------------- sifreleme ----------------
def _fernet():
    anahtar = ayar.SIFRELEME_ANAHTARI
    if not anahtar:
        if ayar.ORTAM == "bulut":
            raise RuntimeError("SAAS_SIFRELEME_ANAHTARI tanimli degil")
        anahtar = base64.urlsafe_b64encode(hashlib.sha256(b"yerel-gelistirme").digest()).decode()
    return Fernet(anahtar.encode() if isinstance(anahtar, str) else anahtar)


def sifrele(veri):
    return _fernet().encrypt(json.dumps(veri).encode()).decode()


def coz(metin):
    if not metin:
        return None
    try:
        return json.loads(_fernet().decrypt(metin.encode()))
    except InvalidToken:
        raise RuntimeError("Sifreli veri cozulemedi (anahtar degismis olabilir)")


def yeni_sifreleme_anahtari():
    return Fernet.generate_key().decode()


# ---------------- imzali, sureli degerler (OAuth state) ----------------
def _imza_anahtari():
    a = ayar.IMZA_ANAHTARI
    if not a:
        if ayar.ORTAM == "bulut":
            raise RuntimeError("SAAS_IMZA_ANAHTARI tanimli degil")
        a = "yerel-imza"
    return a.encode()


def imzala(veri, sure_sn=900):
    govde = base64.urlsafe_b64encode(json.dumps({**veri, "son": int(time.time()) + sure_sn}).encode()).decode()
    imza = hmac.new(_imza_anahtari(), govde.encode(), hashlib.sha256).hexdigest()
    return f"{govde}.{imza}"


def imza_coz(deger):
    try:
        govde, imza = deger.rsplit(".", 1)
    except (ValueError, AttributeError):
        raise YetkiHatasi("Bozuk imza")
    if not hmac.compare_digest(hmac.new(_imza_anahtari(), govde.encode(), hashlib.sha256).hexdigest(), imza):
        raise YetkiHatasi("Imza gecersiz")
    veri = json.loads(base64.urlsafe_b64decode(govde.encode()))
    if veri.get("son", 0) < time.time():
        raise YetkiHatasi("Suresi dolmus")
    return veri


def zamanlayici_dogrula(baslik):
    """Cloud Scheduler istekleri paylasilan gizli anahtarla gelir (X-Zamanlayici-Anahtari)."""
    beklenen = ayar.ZAMANLAYICI_ANAHTARI
    if not beklenen:
        if ayar.ORTAM == "bulut":
            raise YetkiHatasi("Zamanlayici anahtari tanimli degil")
        return True
    if not baslik or not hmac.compare_digest(baslik, beklenen):
        raise YetkiHatasi("Zamanlayici anahtari yanlis")
    return True
