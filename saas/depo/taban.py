"""Depo arayuzu. Tarihler ISO metin (UTC) olarak doner."""
from datetime import datetime, timezone


class Cakisma(Exception):
    """Iyimser kilit: kayit, okunduktan sonra baska biri tarafindan degistirildi."""


def simdi_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ICERIK_ALANLARI = ("klasor", "tur", "meta", "yayin", "caption", "ekler", "dosyalar")
IS_TURLERI = ("uret", "yayin_turu", "kaldir", "revize", "plan")


class Depo:
    # ---- musteriler ----
    def musteri_al(self, mid): raise NotImplementedError
    def musteri_ekle(self, kayit): raise NotImplementedError
    def musteri_guncelle(self, mid, **alanlar): raise NotImplementedError
    def musteriler(self, durumlar=None): raise NotImplementedError

    # ---- uyelikler ----
    def uyelik_ekle(self, kullanici_id, mid, rol="sahip", eposta=None): raise NotImplementedError
    def uyelikler(self, kullanici_id): raise NotImplementedError

    def uye_mi(self, kullanici_id, mid, roller=("sahip", "editor", "izleyici")):
        return any(u["musteri_id"] == mid and u["rol"] in roller for u in self.uyelikler(kullanici_id))

    # ---- icerikler ----
    def icerikler(self, mid, n=60): raise NotImplementedError
    def icerik_al(self, mid, klasor): raise NotImplementedError
    def icerik_yaz(self, mid, kayit, beklenen_surum=None):
        """beklenen_surum verilirse yalnizca o surumdeyse yazar (yoksa Cakisma). Yeni surumu doner."""
        raise NotImplementedError

    # ---- is kuyrugu ----
    def is_ekle(self, mid, tur, parametre=None): raise NotImplementedError
    def is_al(self, isci, zaman_asimi_dk=60): raise NotImplementedError
    def is_bitir(self, is_id, durum, kayit=""): raise NotImplementedError
    def isler(self, mid, n=20): raise NotImplementedError
    def son_isler(self, n=50, durum=None): raise NotImplementedError       # yonetim: tum musteriler
    def uyeler(self, mid): raise NotImplementedError                        # yonetim: musterinin kullanicilari

    def bekleyen_is(self, mid, tur, parametre=None):
        """Ayni turde (ve ayni parametreyle) bekleyen/calisan is varsa onu doner: cift is acilmasin."""
        for i in self.isler(mid, 30):
            if i["tur"] == tur and i["durum"] in ("bekliyor", "calisiyor") and \
                    (parametre is None or (i.get("parametre") or {}) == parametre):
                return i
        return None

    # ---- ofis panosu ----
    def pano_ekle(self, mid, mesajlar): raise NotImplementedError
    def pano_son(self, mid, n=60, sonra=0): raise NotImplementedError

    # ---- dosyalar (anahtar: "<musteri>/<yol>") ----
    def dosya_yukle(self, anahtar, yerel_yol, tip=None): raise NotImplementedError
    def dosya_indir(self, anahtar, hedef): raise NotImplementedError
    def dosya_adresi(self, anahtar, sure_sn=3600): raise NotImplementedError
    def dosya_sil(self, anahtar): raise NotImplementedError

    def json_oku(self, anahtar, varsayilan=None):
        """Depodaki kucuk bir JSON dosyasi (yukleme dizini gibi)."""
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            yol = Path(t) / "x.json"
            if not self.dosya_indir(anahtar, yol):
                return varsayilan
            try:
                return json.loads(yol.read_text(encoding="utf-8"))
            except ValueError:
                return varsayilan

    def json_yaz(self, anahtar, veri):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            yol = Path(t) / "x.json"
            yol.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
            self.dosya_yukle(anahtar, yol, "application/json")

    def dosya_adresleri(self, anahtarlar, sure_sn=3600):
        """Birden cok imzali adres (panelde gorseller). Arka uc toplu imzalayabiliyorsa onu kullanir."""
        return {a: self.dosya_adresi(a, sure_sn) for a in anahtarlar}
