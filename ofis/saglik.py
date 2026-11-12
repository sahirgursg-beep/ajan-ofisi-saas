"""Sabah saglik kontrolu + haftalik yedek. Sonuc veri/saglik.json; sorun varsa Genel Bakis'ta uyari cikar."""
import json
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path

from . import musteri
from .ayarlar import AYAR, KOK, MUSTERI_KOK, VERI, CIKTI

YOL = VERI / "saglik.json"
YEDEK = MUSTERI_KOK / "yedek"


def _k(ad, durum, mesaj):
    return {"ad": ad, "durum": durum, "mesaj": mesaj}      # durum: ok | uyari | hata


def kontrol():
    from . import meta, yayin
    out = []
    # Meta anahtari
    if not meta.bagli():
        out.append(_k("Meta bağlantısı", "hata", "Bağlı değil — Yayın sayfasından bağlayın"))
    else:
        try:
            a = meta.ayar()
            d = meta.get("debug_token", a["page_token"], input_token=a["page_token"]).get("data", {})
            if d.get("is_valid") is False:
                out.append(_k("Meta bağlantısı", "hata", "Anahtar geçersiz — yeni anahtar gerekli"))
            else:
                bitis = d.get("expires_at") or 0
                kalan = (bitis - time.time()) / 86400 if bitis else None
                out.append(_k("Meta bağlantısı", "uyari" if kalan is not None and kalan < 10 else "ok",
                              f"Geçerli{f', {kalan:.0f} gün sonra bitiyor' if kalan is not None else ' (süresiz)'}"))
        except Exception as e:
            out.append(_k("Meta bağlantısı", "hata", str(e)[:160]))
    # Saat: Meta sunucusunun saatiyle karsilastir
    try:
        import email.utils
        import requests
        r = requests.head("https://graph.facebook.com", timeout=10)
        uzak = email.utils.parsedate_to_datetime(r.headers["Date"]).timestamp()
        fark = abs(uzak - time.time()) / 60
        out.append(_k("Bilgisayar saati", "hata" if fark > 10 else ("uyari" if fark > 2 else "ok"),
                      f"{'Doğru' if fark <= 2 else f'{fark:.0f} dk sapmış — Windows saatini otomatik ayarlayın'}"
                      f" · {musteri.KISALTMA} {yayin.simdi():%H:%M}"))
    except Exception:
        out.append(_k("Bilgisayar saati", "uyari", "İnternetten kontrol edilemedi"))
    # Yapay zeka modeli
    try:
        from . import llm
        llm.sifirla()
        ok = llm.hazir()
        ana = (AYAR.get("yz") or {}).get("saglayici", "ollama")
        yedek = ok and llm.saglayici_adi() != ana          # ana saglayici yok, yedekle calisiyor
        if ok and not yedek and ana == "ollama":
            yedek = llm.model_adi().split(":")[0] != AYAR["model"].split(":")[0]   # Ollama'da istenen model yok
        out.append(_k(f"Yapay zeka ({ana})", "ok" if ok and not yedek else "uyari",
                      (llm.durum() if (yedek or not ok) else llm.model_adi())
                      + ("" if ok else " Bu arada metinler şablonla yazılır.")))
    except Exception:
        out.append(_k("Yapay zeka", "uyari", "Kontrol edilemedi"))
    # Disk
    bos = shutil.disk_usage(str(KOK)).free / 1e9
    out.append(_k("Disk", "hata" if bos < 3 else ("uyari" if bos < 10 else "ok"), f"{bos:.0f} GB boş"))
    # Gunun uretimi
    bugun = yayin.simdi().date().isoformat()
    bugunku = [x for x in yayin.liste(40) if (x["meta"].get("plan_gunu") or x["meta"].get("tarih", ""))[:10] == bugun]
    saat = yayin.simdi().hour
    if len(bugunku) >= 3:
        out.append(_k("Bugünün içerikleri", "ok", f"{len(bugunku)} içerik hazır"))
    else:
        out.append(_k("Bugünün içerikleri", "hata" if saat >= 11 else "uyari",
                      f"{len(bugunku)}/3 hazır" + (" — 08:00 görevi çalışmamış olabilir" if saat >= 9 else "")))
    # Yayinci hatalari
    log = VERI / "yayinci_hata.log"
    if log.exists() and time.time() - log.stat().st_mtime < 86400:
        out.append(_k("Yayıncı", "uyari", "Son 24 saatte hata kaydı var (veri/yayinci_hata.log)"))
    else:
        out.append(_k("Yayıncı", "ok", "Hata yok"))
    kilit = VERI / "yayin.kilit"
    if kilit.exists() and time.time() - kilit.stat().st_mtime > 3600:
        kilit.unlink(missing_ok=True)
        out.append(_k("Yayın kilidi", "uyari", "Takılı kalmış kilit temizlendi"))
    r = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "kontroller": out,
         "durum": "hata" if any(k["durum"] == "hata" for k in out) else ("uyari" if any(k["durum"] == "uyari" for k in out) else "ok")}
    YOL.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    return r


def son():
    try:
        return json.loads(YOL.read_text(encoding="utf-8"))
    except Exception:
        return {}


def yedekle(tut=8):
    """Ayarlar, planlar, raporlar, satis kayitlari ve sablon kutuphanesi (gorseller/videolar haric) -> yedek/*.zip"""
    YEDEK.mkdir(parents=True, exist_ok=True)
    hedef = YEDEK / f"yedek_{datetime.now():%Y-%m-%d}.zip"
    with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(KOK / "config.json", "config.json")
        z.write(MUSTERI_KOK / "profil.json", "profil.json")
        for p in VERI.glob("*.json"):
            if p.name in ("meta.json", "tum_urunler.json", "urunler.json"):
                continue                       # erisim anahtari yedege girmez; katalog siteden yeniden cekilir
            z.write(p, f"veri/{p.name}")
        for alt in ("iletisim",):
            for p in (VERI / alt).glob("*.json"):
                z.write(p, f"veri/{alt}/{p.name}")
        for p in (VERI / "sablon_kutuphane").glob("*.json"):
            z.write(p, f"sablonlar/kutuphane/{p.name}")
        for p in CIKTI.glob("*/meta.json"):
            for ad in ("meta.json", "yayin.json", "performans.json", "caption.txt"):
                f = p.parent / ad
                if f.exists():
                    z.write(f, f"cikti/{p.parent.name}/{ad}")
        for p in (CIKTI / "raporlar").glob("*.html"):
            z.write(p, f"cikti/raporlar/{p.name}")
    for eski in sorted(YEDEK.glob("yedek_*.zip"))[:-tut]:
        eski.unlink(missing_ok=True)
    return hedef
