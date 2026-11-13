"""Yerel depo: SQLite + klasor. Gelistirme ve testler icin; semasi sql/001_sema.sql ile ayni."""
import hashlib
import hmac
import json
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .taban import IS_TURLERI, Cakisma, Depo, simdi_iso

JSON_ALANLAR = {"profil", "yayin_ayar", "meta_bilgi", "meta", "yayin", "ekler", "dosyalar", "parametre"}

SEMA = """
CREATE TABLE IF NOT EXISTS musteriler (id TEXT PRIMARY KEY, ad TEXT NOT NULL, profil TEXT NOT NULL,
  yayin_ayar TEXT NOT NULL DEFAULT '{}', durum TEXT NOT NULL DEFAULT 'deneme', deneme_bitis TEXT,
  meta_bilgi TEXT NOT NULL DEFAULT '{}', meta_token TEXT, meta_aday TEXT, son_uretim TEXT,
  olusturma TEXT, guncelleme TEXT);
CREATE TABLE IF NOT EXISTS uyelikler (kullanici_id TEXT NOT NULL, musteri_id TEXT NOT NULL, rol TEXT NOT NULL,
  eposta TEXT, PRIMARY KEY (kullanici_id, musteri_id));
CREATE TABLE IF NOT EXISTS icerikler (musteri_id TEXT NOT NULL, klasor TEXT NOT NULL, tur TEXT,
  meta TEXT NOT NULL DEFAULT '{}', yayin TEXT NOT NULL DEFAULT '{}', caption TEXT NOT NULL DEFAULT '',
  ekler TEXT NOT NULL DEFAULT '{}', dosyalar TEXT NOT NULL DEFAULT '[]', surum INTEGER NOT NULL DEFAULT 1,
  olusturma TEXT, guncelleme TEXT, PRIMARY KEY (musteri_id, klasor));
CREATE TABLE IF NOT EXISTS isler (id TEXT PRIMARY KEY, musteri_id TEXT NOT NULL, tur TEXT NOT NULL,
  parametre TEXT NOT NULL DEFAULT '{}', durum TEXT NOT NULL DEFAULT 'bekliyor', deneme INTEGER NOT NULL DEFAULT 0,
  isci TEXT, kayit TEXT, olusturma TEXT, baslama TEXT, bitis TEXT);
CREATE TABLE IF NOT EXISTS pano (id INTEGER PRIMARY KEY AUTOINCREMENT, musteri_id TEXT NOT NULL, zaman TEXT,
  gonderen TEXT, alici TEXT, tur TEXT, icerik TEXT);
"""


def _anahtar_temiz(anahtar):
    p = Path(anahtar)
    if p.is_absolute() or ".." in p.parts or not anahtar:
        raise ValueError(f"Gecersiz dosya anahtari: {anahtar!r}")
    return anahtar


class YerelDepo(Depo):
    def __init__(self, klasor, imza_anahtari=b"yerel-gelistirme"):
        self.klasor = Path(klasor)
        self.klasor.mkdir(parents=True, exist_ok=True)
        self.dosyalar = self.klasor / "dosyalar"
        self.db_yolu = self.klasor / "saas.db"
        self._imza = imza_anahtari if isinstance(imza_anahtari, bytes) else imza_anahtari.encode()
        with self._baglan() as c:
            c.executescript(SEMA)

    def _baglan(self):
        c = sqlite3.connect(self.db_yolu, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return _Baglanti(c)

    @staticmethod
    def _sozluk(satir):
        if satir is None:
            return None
        d = dict(satir)
        for k in JSON_ALANLAR & d.keys():
            if isinstance(d[k], str):
                d[k] = json.loads(d[k])
        return d

    @staticmethod
    def _deger(k, v):
        return json.dumps(v, ensure_ascii=False) if k in JSON_ALANLAR and not isinstance(v, str) else v

    # ---- musteriler ----
    def musteri_al(self, mid):
        with self._baglan() as c:
            return self._sozluk(c.execute("SELECT * FROM musteriler WHERE id=?", (mid,)).fetchone())

    def musteri_ekle(self, kayit):
        k = {"olusturma": simdi_iso(), "guncelleme": simdi_iso(), **kayit}
        alanlar = list(k)
        with self._baglan() as c:
            try:
                c.execute(f"INSERT INTO musteriler ({','.join(alanlar)}) VALUES ({','.join('?' * len(alanlar))})",
                          [self._deger(a, k[a]) for a in alanlar])
            except sqlite3.IntegrityError:
                raise Cakisma(f"Musteri zaten var: {kayit.get('id')}")
        return self.musteri_al(kayit["id"])

    def musteri_guncelle(self, mid, **alanlar):
        alanlar["guncelleme"] = simdi_iso()
        with self._baglan() as c:
            c.execute(f"UPDATE musteriler SET {', '.join(a + '=?' for a in alanlar)} WHERE id=?",
                      [self._deger(a, v) for a, v in alanlar.items()] + [mid])
        return self.musteri_al(mid)

    def musteriler(self, durumlar=None):
        with self._baglan() as c:
            satirlar = c.execute("SELECT * FROM musteriler ORDER BY id").fetchall()
        out = [self._sozluk(s) for s in satirlar]
        return [m for m in out if not durumlar or m["durum"] in durumlar]

    # ---- uyelikler ----
    def uyelik_ekle(self, kullanici_id, mid, rol="sahip", eposta=None):
        with self._baglan() as c:
            c.execute("INSERT OR REPLACE INTO uyelikler VALUES (?,?,?,?)", (str(kullanici_id), mid, rol, eposta))

    def uyelikler(self, kullanici_id):
        with self._baglan() as c:
            return [dict(s) for s in c.execute("SELECT * FROM uyelikler WHERE kullanici_id=?", (str(kullanici_id),))]

    # ---- icerikler ----
    def icerikler(self, mid, n=60):
        with self._baglan() as c:
            return [self._sozluk(s) for s in c.execute(
                "SELECT * FROM icerikler WHERE musteri_id=? ORDER BY klasor DESC LIMIT ?", (mid, n))]

    def icerik_al(self, mid, klasor):
        with self._baglan() as c:
            return self._sozluk(c.execute("SELECT * FROM icerikler WHERE musteri_id=? AND klasor=?",
                                          (mid, klasor)).fetchone())

    def icerik_yaz(self, mid, kayit, beklenen_surum=None):
        veri = {k: kayit[k] for k in ("tur", "meta", "yayin", "caption", "ekler", "dosyalar") if k in kayit}
        with self._baglan() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                eski = c.execute("SELECT surum FROM icerikler WHERE musteri_id=? AND klasor=?",
                                 (mid, kayit["klasor"])).fetchone()
                if beklenen_surum is not None and (eski is None or eski["surum"] != beklenen_surum):
                    raise Cakisma(kayit["klasor"])
                if eski is None:
                    veri.update({"musteri_id": mid, "klasor": kayit["klasor"], "surum": 1,
                                 "olusturma": simdi_iso(), "guncelleme": simdi_iso()})
                    c.execute(f"INSERT INTO icerikler ({','.join(veri)}) VALUES ({','.join('?' * len(veri))})",
                              [self._deger(k, v) for k, v in veri.items()])
                    yeni = 1
                else:
                    yeni = eski["surum"] + 1
                    veri.update({"surum": yeni, "guncelleme": simdi_iso()})
                    c.execute(f"UPDATE icerikler SET {', '.join(k + '=?' for k in veri)} WHERE musteri_id=? AND klasor=?",
                              [self._deger(k, v) for k, v in veri.items()] + [mid, kayit["klasor"]])
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return yeni

    # ---- is kuyrugu ----
    def is_ekle(self, mid, tur, parametre=None):
        if tur not in IS_TURLERI:
            raise ValueError(f"Bilinmeyen is turu: {tur}")
        i = {"id": str(uuid.uuid4()), "musteri_id": mid, "tur": tur, "parametre": parametre or {},
             "durum": "bekliyor", "olusturma": simdi_iso()}
        with self._baglan() as c:
            c.execute("INSERT INTO isler (id, musteri_id, tur, parametre, durum, olusturma) VALUES (?,?,?,?,?,?)",
                      (i["id"], mid, tur, json.dumps(i["parametre"]), "bekliyor", i["olusturma"]))
        return i

    def is_al(self, isci, zaman_asimi_dk=60):
        sinir = (datetime.now(timezone.utc) - timedelta(minutes=zaman_asimi_dk)).isoformat(timespec="seconds")
        with self._baglan() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                c.execute("UPDATE isler SET durum='bekliyor', kayit=COALESCE(kayit,'')||' [zaman asimi, yeniden kuyrukta]' "
                          "WHERE durum='calisiyor' AND baslama < ? AND deneme < 3", (sinir,))
                s = c.execute("SELECT i.id FROM isler i WHERE i.durum='bekliyor' AND NOT EXISTS "
                              "(SELECT 1 FROM isler c2 WHERE c2.musteri_id=i.musteri_id AND c2.durum='calisiyor') "
                              "ORDER BY i.olusturma, i.rowid LIMIT 1").fetchone()
                if s is None:
                    c.execute("COMMIT")
                    return None
                c.execute("UPDATE isler SET durum='calisiyor', isci=?, baslama=?, deneme=deneme+1 WHERE id=?",
                          (isci, simdi_iso(), s["id"]))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
            return self._sozluk(c.execute("SELECT * FROM isler WHERE id=?", (s["id"],)).fetchone())

    def is_bitir(self, is_id, durum, kayit=""):
        with self._baglan() as c:
            c.execute("UPDATE isler SET durum=?, kayit=?, bitis=? WHERE id=?", (durum, kayit[-4000:], simdi_iso(), is_id))

    def is_geri_birak(self, is_id):
        with self._baglan() as c:
            c.execute("UPDATE isler SET durum='bekliyor' WHERE id=?", (is_id,))

    def yarim_kalanlar_geri(self):
        with self._baglan() as c:
            n = c.execute("UPDATE isler SET durum='bekliyor' WHERE durum='calisiyor' AND deneme < 3").rowcount
            c.execute("UPDATE isler SET durum='hata', kayit='Isci uc kez yarida kaldi', bitis=? WHERE durum='calisiyor'",
                      (simdi_iso(),))
        return n

    def isler(self, mid, n=20):
        with self._baglan() as c:
            return [self._sozluk(s) for s in c.execute(
                "SELECT * FROM isler WHERE musteri_id=? ORDER BY olusturma DESC, rowid DESC LIMIT ?", (mid, n))]

    def son_isler(self, n=50, durum=None):
        with self._baglan() as c:
            if durum:
                q = c.execute("SELECT * FROM isler WHERE durum=? ORDER BY olusturma DESC, rowid DESC LIMIT ?", (durum, n))
            else:
                q = c.execute("SELECT * FROM isler ORDER BY olusturma DESC, rowid DESC LIMIT ?", (n,))
            return [self._sozluk(x) for x in q]

    def uyeler(self, mid):
        with self._baglan() as c:
            return [dict(x) for x in c.execute("SELECT * FROM uyelikler WHERE musteri_id=?", (mid,))]

    # ---- pano ----
    def pano_ekle(self, mid, mesajlar):
        with self._baglan() as c:
            c.executemany("INSERT INTO pano (musteri_id, zaman, gonderen, alici, tur, icerik) VALUES (?,?,?,?,?,?)",
                          [(mid, m.get("zaman") or simdi_iso(), m.get("gonderen"), m.get("alici"), m.get("tur"),
                            m.get("icerik")) for m in mesajlar])

    def pano_son(self, mid, n=60, sonra=0):
        with self._baglan() as c:
            s = c.execute("SELECT * FROM pano WHERE musteri_id=? AND id>? ORDER BY id DESC LIMIT ?", (mid, sonra, n))
            return [dict(x) for x in s][::-1]

    # ---- dosyalar ----
    def _yol(self, anahtar):
        return self.dosyalar / _anahtar_temiz(anahtar)

    def dosya_yukle(self, anahtar, yerel_yol, tip=None):
        hedef = self._yol(anahtar)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(yerel_yol, hedef)

    def dosya_sil(self, anahtar):
        self._yol(anahtar).unlink(missing_ok=True)

    def dosya_indir(self, anahtar, hedef):
        kaynak = self._yol(anahtar)
        if not kaynak.exists():
            return False
        Path(hedef).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kaynak, hedef)
        return True

    def imza(self, anahtar, son):
        return hmac.new(self._imza, f"{anahtar}|{son}".encode(), hashlib.sha256).hexdigest()[:32]

    def dosya_adresi(self, anahtar, sure_sn=3600):
        son = int(time.time()) + sure_sn
        return f"/yerel-dosya/{_anahtar_temiz(anahtar)}?son={son}&imza={self.imza(anahtar, son)}"

    def imzali_oku(self, anahtar, son, imza):
        if int(son) < time.time() or not hmac.compare_digest(self.imza(anahtar, int(son)), imza):
            return None
        p = self._yol(anahtar)
        return p if p.exists() else None


class _Baglanti:
    def __init__(self, c):
        self.c = c

    def __enter__(self):
        return self.c

    def __exit__(self, *a):
        self.c.close()
