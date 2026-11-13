"""Supabase deposu: Postgres (PostgREST) + Storage, yalnizca HTTP ile (ek paket yok).
Servis anahtari RLS'i asar; bu yuzden yalnizca sunucuda kullanilir ve her istekte musteri_id filtresi vardir."""
import json
import mimetypes
from pathlib import Path
from urllib.parse import quote

import requests

from .taban import IS_TURLERI, Cakisma, Depo, simdi_iso


class SupabaseHata(Exception):
    pass


class SupabaseDepo(Depo):
    def __init__(self, url, servis_anahtari, kova="ajan-ofisi", oturum=None):
        if not url or not servis_anahtari:
            raise SupabaseHata("SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY gerekli")
        self.url, self.kova = url.rstrip("/"), kova
        self.http = oturum or requests.Session()
        self.baslik = {"apikey": servis_anahtari, "Authorization": f"Bearer {servis_anahtari}"}

    # ---- yardimcilar ----
    def _istek(self, yontem, yol, beklenen=(200, 201, 204), **kw):
        h = {**self.baslik, **kw.pop("headers", {})}
        r = self.http.request(yontem, self.url + yol, headers=h, timeout=kw.pop("timeout", 60), **kw)
        if r.status_code not in beklenen:
            raise SupabaseHata(f"{yontem} {yol.split('?')[0]} -> HTTP {r.status_code}: {r.text[:300]}")
        return r

    def _rest(self, yontem, tablo, params=None, govde=None, prefer=None, beklenen=(200, 201, 204)):
        h = {"Content-Type": "application/json"}
        if prefer:
            h["Prefer"] = prefer
        r = self._istek(yontem, f"/rest/v1/{tablo}", beklenen=beklenen, params=params,
                        data=json.dumps(govde) if govde is not None else None, headers=h)
        return r.json() if r.content else []

    @staticmethod
    def _eq(v):
        return f"eq.{v}"

    # ---- musteriler ----
    def musteri_al(self, mid):
        s = self._rest("GET", "musteriler", {"id": self._eq(mid), "select": "*"})
        return s[0] if s else None

    def musteri_ekle(self, kayit):
        try:
            return self._rest("POST", "musteriler", govde=kayit, prefer="return=representation")[0]
        except SupabaseHata as e:
            if "409" in str(e) or "23505" in str(e):
                raise Cakisma(f"Musteri zaten var: {kayit.get('id')}")
            raise

    def musteri_guncelle(self, mid, **alanlar):
        alanlar["guncelleme"] = simdi_iso()
        s = self._rest("PATCH", "musteriler", {"id": self._eq(mid)}, alanlar, prefer="return=representation")
        return s[0] if s else None

    def musteriler(self, durumlar=None):
        p = {"select": "*", "order": "id"}
        if durumlar:
            p["durum"] = f"in.({','.join(durumlar)})"
        return self._rest("GET", "musteriler", p)

    # ---- uyelikler ----
    def uyelik_ekle(self, kullanici_id, mid, rol="sahip", eposta=None):
        self._rest("POST", "uyelikler", govde={"kullanici_id": str(kullanici_id), "musteri_id": mid, "rol": rol,
                                                "eposta": eposta}, prefer="resolution=merge-duplicates")

    def uyelikler(self, kullanici_id):
        return self._rest("GET", "uyelikler", {"kullanici_id": self._eq(kullanici_id), "select": "*"})

    # ---- icerikler ----
    def icerikler(self, mid, n=60):
        return self._rest("GET", "icerikler", {"musteri_id": self._eq(mid), "select": "*",
                                               "order": "klasor.desc", "limit": str(n)})

    def icerik_al(self, mid, klasor):
        s = self._rest("GET", "icerikler", {"musteri_id": self._eq(mid), "klasor": self._eq(klasor), "select": "*"})
        return s[0] if s else None

    def icerik_yaz(self, mid, kayit, beklenen_surum=None):
        veri = {k: kayit[k] for k in ("tur", "meta", "yayin", "caption", "ekler", "dosyalar") if k in kayit}
        veri["guncelleme"] = simdi_iso()
        if beklenen_surum is None:
            eski = self.icerik_al(mid, kayit["klasor"])
            if eski is None:
                try:
                    self._rest("POST", "icerikler", govde={**veri, "musteri_id": mid, "klasor": kayit["klasor"],
                                                           "surum": 1}, prefer="return=minimal")
                    return 1
                except SupabaseHata as e:
                    if "409" not in str(e):
                        raise
                    eski = self.icerik_al(mid, kayit["klasor"])
            beklenen_surum = eski["surum"]
        veri["surum"] = beklenen_surum + 1
        s = self._rest("PATCH", "icerikler", {"musteri_id": self._eq(mid), "klasor": self._eq(kayit["klasor"]),
                                              "surum": self._eq(beklenen_surum)}, veri,
                       prefer="return=representation")
        if not s:
            raise Cakisma(kayit["klasor"])
        return veri["surum"]

    # ---- is kuyrugu ----
    def is_ekle(self, mid, tur, parametre=None):
        if tur not in IS_TURLERI:
            raise ValueError(f"Bilinmeyen is turu: {tur}")
        return self._rest("POST", "isler", govde={"musteri_id": mid, "tur": tur, "parametre": parametre or {}},
                          prefer="return=representation")[0]

    def is_al(self, isci, zaman_asimi_dk=60):
        s = self._rest("POST", "rpc/is_al", govde={"isci_adi": isci, "zaman_asimi_dk": zaman_asimi_dk})
        return s[0] if s else None

    def is_bitir(self, is_id, durum, kayit=""):
        self._rest("PATCH", "isler", {"id": self._eq(is_id)},
                   {"durum": durum, "kayit": kayit[-4000:], "bitis": simdi_iso()})

    def is_geri_birak(self, is_id):
        self._rest("PATCH", "isler", {"id": self._eq(is_id)}, {"durum": "bekliyor"})

    def yarim_kalanlar_geri(self):
        """Onceki isci (yeniden dagitim/cokme) yarida biraktiysa: 3. denemeye kadar kuyruga, sonra hata."""
        geri = self._rest("PATCH", "isler", {"durum": "eq.calisiyor", "deneme": "lt.3"}, {"durum": "bekliyor"},
                          prefer="return=representation") or []
        self._rest("PATCH", "isler", {"durum": "eq.calisiyor"},
                   {"durum": "hata", "kayit": "Isci uc kez yarida kaldi", "bitis": simdi_iso()})
        return len(geri)

    def isler(self, mid, n=20):
        return self._rest("GET", "isler", {"musteri_id": self._eq(mid), "select": "*",
                                           "order": "olusturma.desc", "limit": str(n)})

    def son_isler(self, n=50, durum=None):
        p = {"select": "id,musteri_id,tur,durum,deneme,olusturma,baslama,bitis", "order": "olusturma.desc", "limit": str(n)}
        if durum:
            p["durum"] = self._eq(durum)
        return self._rest("GET", "isler", p)

    def uyeler(self, mid):
        return self._rest("GET", "uyelikler", {"musteri_id": self._eq(mid), "select": "*"})

    # ---- pano ----
    def pano_ekle(self, mid, mesajlar):
        if mesajlar:
            self._rest("POST", "pano", govde=[{"musteri_id": mid, "zaman": m.get("zaman") or simdi_iso(),
                                               "gonderen": m.get("gonderen"), "alici": m.get("alici"),
                                               "tur": m.get("tur"), "icerik": m.get("icerik")} for m in mesajlar],
                       prefer="return=minimal")

    def pano_son(self, mid, n=60, sonra=0):
        s = self._rest("GET", "pano", {"musteri_id": self._eq(mid), "id": f"gt.{int(sonra)}", "select": "*",
                                       "order": "id.desc", "limit": str(n)})
        return s[::-1]

    # ---- dosyalar ----
    def _nesne(self, anahtar):
        if ".." in Path(anahtar).parts or anahtar.startswith("/"):
            raise ValueError(f"Gecersiz dosya anahtari: {anahtar!r}")
        return f"{self.kova}/{quote(anahtar)}"

    def dosya_yukle(self, anahtar, yerel_yol, tip=None):
        tip = tip or mimetypes.guess_type(str(yerel_yol))[0] or "application/octet-stream"
        with open(yerel_yol, "rb") as f:
            self._istek("POST", f"/storage/v1/object/{self._nesne(anahtar)}", data=f,
                        headers={"Content-Type": tip, "x-upsert": "true"}, timeout=600)

    def dosya_sil(self, anahtar):
        self._istek("DELETE", f"/storage/v1/object/{self._nesne(anahtar)}", beklenen=(200, 204, 400, 404))

    def dosya_indir(self, anahtar, hedef):
        r = self.http.get(f"{self.url}/storage/v1/object/{self._nesne(anahtar)}", headers=self.baslik,
                          stream=True, timeout=600)
        if r.status_code in (400, 404):
            return False
        if r.status_code != 200:
            raise SupabaseHata(f"Dosya indirilemedi {anahtar}: HTTP {r.status_code}")
        Path(hedef).parent.mkdir(parents=True, exist_ok=True)
        with open(hedef, "wb") as f:
            for parca in r.iter_content(1 << 20):
                f.write(parca)
        return True

    def dosya_adresi(self, anahtar, sure_sn=3600):
        r = self._istek("POST", f"/storage/v1/object/sign/{self._nesne(anahtar)}",
                        data=json.dumps({"expiresIn": sure_sn}), headers={"Content-Type": "application/json"})
        yol = r.json().get("signedURL") or r.json().get("signedUrl")
        return f"{self.url}/storage/v1{yol}" if yol and yol.startswith("/") else yol

    def dosya_adresleri(self, anahtarlar, sure_sn=3600):
        anahtarlar = list(anahtarlar)
        if not anahtarlar:
            return {}
        for a in anahtarlar:
            self._nesne(a)        # dogrulama
        r = self._istek("POST", f"/storage/v1/object/sign/{self.kova}",
                        data=json.dumps({"expiresIn": sure_sn, "paths": anahtarlar}),
                        headers={"Content-Type": "application/json"})
        out = {}
        for x in r.json():
            yol = x.get("signedURL") or x.get("signedUrl")
            if yol and not x.get("error"):
                out[x["path"]] = f"{self.url}/storage/v1{yol}" if yol.startswith("/") else yol
        return out
