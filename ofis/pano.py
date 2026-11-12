"""Ofis panosu: ajanlarin birbirine mesaj yazdigi ortak SQLite veritabani.

Her ajan buraya yazar, digerleri buradan okur. 2D ofis ekrani da
ayni panoyu okuyarak kimin ne yaptigini gosterir.
"""
import json
import sqlite3
import threading
from datetime import datetime, date
from pathlib import Path

from .ayarlar import KOK, VERI

DB_YOLU = VERI / "pano.db"
_kilit = threading.Lock()


def _baglan():
    DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_YOLU, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def kur():
    with _kilit, _baglan() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS mesajlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zaman TEXT, gonderen TEXT, alici TEXT, tur TEXT, icerik TEXT
            );
            CREATE TABLE IF NOT EXISTS ajanlar (
                ad TEXT PRIMARY KEY, unvan TEXT, emoji TEXT, sira INTEGER,
                durum TEXT, konusma TEXT, guncelleme TEXT
            );
            CREATE TABLE IF NOT EXISTS hazirlananlar (
                urun_url TEXT, urun_adi TEXT, tarih TEXT, klasor TEXT
            );
            """
        )


def _simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ajan_kaydet(ad, unvan, emoji, sira):
    with _kilit, _baglan() as con:
        con.execute(
            "INSERT INTO ajanlar(ad, unvan, emoji, sira, durum, konusma, guncelleme) "
            "VALUES(?,?,?,?, 'bosta', '', ?) "
            "ON CONFLICT(ad) DO UPDATE SET unvan=excluded.unvan, emoji=excluded.emoji, "
            "sira=excluded.sira, durum='bosta', konusma=''",
            (ad, unvan, emoji, sira, _simdi()),
        )


def durum(ad, durum_, konusma=""):
    """durum_: bosta | calisiyor | bekliyor | bitti | hata"""
    with _kilit, _baglan() as con:
        con.execute(
            "UPDATE ajanlar SET durum=?, konusma=?, guncelleme=? WHERE ad=?",
            (durum_, konusma[:220], _simdi(), ad),
        )


def yaz(gonderen, alici, icerik, tur="mesaj"):
    if not isinstance(icerik, str):
        icerik = json.dumps(icerik, ensure_ascii=False)
    with _kilit, _baglan() as con:
        con.execute(
            "INSERT INTO mesajlar(zaman, gonderen, alici, tur, icerik) VALUES(?,?,?,?,?)",
            (_simdi(), gonderen, alici, tur, icerik),
        )
    print(f"  [{gonderen} -> {alici}] {icerik[:160]}")


def son_mesajlar(n=40, sonra_id=0):
    with _kilit, _baglan() as con:
        rows = con.execute(
            "SELECT * FROM mesajlar WHERE id>? ORDER BY id DESC LIMIT ?", (sonra_id, n)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def ajan_listesi():
    with _kilit, _baglan() as con:
        rows = con.execute("SELECT * FROM ajanlar ORDER BY sira").fetchall()
    return [dict(r) for r in rows]


def hazirlandi_isaretle(url, ad, klasor):
    with _kilit, _baglan() as con:
        con.execute(
            "INSERT INTO hazirlananlar VALUES(?,?,?,?)",
            (url, ad, date.today().isoformat(), str(klasor)),
        )


def son_hazirlananlar(gun):
    with _kilit, _baglan() as con:
        rows = con.execute(
            "SELECT urun_url FROM hazirlananlar WHERE tarih >= date('now', ?)",
            (f"-{int(gun)} days",),
        ).fetchall()
    return {r["urun_url"] for r in rows}


def son_id():
    with _kilit, _baglan() as con:
        r = con.execute("SELECT COALESCE(MAX(id), 0) AS m FROM mesajlar").fetchone()
    return r["m"]
