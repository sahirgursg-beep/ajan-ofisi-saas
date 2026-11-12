"""Oneri kutusu + haftalik toplanti.

Her pazartesi ajanlar gecen haftanin verisini (performans, Reels formatlari, yorum/DM raporu, takipcilerin
cevrimici saatleri, satis kayitlari, rakipler) tartisir; Mudur somut ONERILER cikarir. Oneriler ofis ekraninda
onay/ret kartlari olarak durur. Onaylanan oneri SADECE asagidaki beyaz listedeki eylemlerle ayarlara islenir;
ajanlar kendi kendine ayar degistiremez.

veri/oneriler.json: {"oneriler": [...], "toplantilar": [{"tarih", "konusmalar": [[ajan, metin], ...]}]}
"""
import json
import uuid
from datetime import datetime, timedelta

from .ayarlar import KOK, VERI
from . import musteri

YOL = VERI / "oneriler.json"
EYLEMLER = {
    "yayin_saati": "Paylaşım saatini değiştir",
    "reels_format_kapat": "Reels formatını kapat",
    "reels_format_ac": "Reels formatını tekrar aç",
    "kategori_oncelik": "Kategoriye öncelik ver",
    "kural_ekle": "Marka kuralı ekle",
    "deneme_reels": "Deneme Reels ayarı",
    "not": "Fikir (ayar değişmez)",
}


def _oku():
    try:
        return json.loads(YOL.read_text(encoding="utf-8"))
    except Exception:
        return {"oneriler": [], "toplantilar": []}


def _yaz(d):
    YOL.parent.mkdir(parents=True, exist_ok=True)
    d["oneriler"] = d["oneriler"][-120:]
    d["toplantilar"] = d["toplantilar"][-12:]
    YOL.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def liste():
    d = _oku()
    sira = {"bekliyor": 0, "onaylandi": 1, "reddedildi": 2, "hata": 1}
    d["oneriler"] = sorted(d["oneriler"], key=lambda o: (sira.get(o["durum"], 3), o["tarih"]), reverse=False)
    d["oneriler"] = sorted(d["oneriler"], key=lambda o: sira.get(o["durum"], 3))
    return d


def bekleyen_sayisi():
    return sum(1 for o in _oku()["oneriler"] if o["durum"] == "bekliyor")


def _ayni_var(d, eylem, gun=30):
    """Ayni eylem son 'gun' icinde onerildiyse (bekleyen/reddedilen/onaylanan) tekrar onerme."""
    sinir = (datetime.now() - timedelta(days=gun)).strftime("%Y-%m-%d")
    anahtar = json.dumps(eylem, sort_keys=True)
    return any(json.dumps(o["eylem"], sort_keys=True) == anahtar and (o["durum"] == "bekliyor" or o["tarih"] >= sinir)
               for o in d["oneriler"])


def ekle(ajan, baslik, gerekce, eylem, d=None):
    kendi = d is None
    d = d or _oku()
    if eylem.get("tur") not in EYLEMLER or _ayni_var(d, eylem):
        return None
    o = {"id": uuid.uuid4().hex[:8], "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "ajan": ajan,
         "baslik": baslik[:140], "gerekce": gerekce[:400], "eylem": eylem, "durum": "bekliyor"}
    d["oneriler"].append(o)
    if kendi:
        _yaz(d)
    return o


# ---------------- uygula (yalnizca kullanici onayi) ----------------
def karar(oid, onay):
    d = _oku()
    o = next((x for x in d["oneriler"] if x["id"] == oid), None)
    if not o or o["durum"] != "bekliyor":
        raise ValueError("Öneri bulunamadı ya da zaten karara bağlandı")
    if not onay:
        o.update({"durum": "reddedildi", "karar": datetime.now().strftime("%Y-%m-%d %H:%M")})
        _yaz(d)
        return o
    try:
        o["sonuc"] = _uygula(o["eylem"])
        o["durum"] = "onaylandi"
    except Exception as e:
        o.update({"durum": "hata", "sonuc": f"{type(e).__name__}: {e}"[:300]})
    o["karar"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _yaz(d)
    return o


def _uygula(e):
    from . import kurallar, ofis_ayar, reels_formatlari, yayin
    t = e["tur"]
    if t == "yayin_saati":
        a = yayin.ayar_oku()
        saat = str(e["saat"])
        if not (yayin._dk(a["mesai_bas"]) <= yayin._dk(saat) <= yayin._dk(a["mesai_bit"]) - 15):
            raise ValueError("Saat mesai içinde olmalı")
        saatler = dict(a["saatler"]); saatler[e["format"]] = saat
        yayin.ayar_kaydet({"saatler": saatler})
        return f"{e['format']} artık {saat}'de (yeni üretilen içerikler için)"
    if t in ("reels_format_kapat", "reels_format_ac"):
        if e["format"] not in reels_formatlari.FORMATLAR:
            raise ValueError("Bilinmeyen format")
        k = set(ofis_ayar.oku().get("reels_kapali") or [])
        (k.add if t.endswith("kapat") else k.discard)(e["format"])
        if len(set(reels_formatlari.FORMATLAR) - k) < 2:
            raise ValueError("En az 2 Reels formatı açık kalmalı")
        ofis_ayar.guncelle(reels_kapali=sorted(k))
        return f"Reels formatları: {', '.join(f for f in reels_formatlari.FORMATLAR if f not in k)}"
    if t == "kategori_oncelik":
        oc = dict(ofis_ayar.oku().get("oncelikli_kategoriler") or {})
        oc[e["kategori"]] = max(1.0, min(2.0, float(e.get("carpan", 1.5))))
        ofis_ayar.guncelle(oncelikli_kategoriler=oc)
        return f"{e['kategori']} planlarda ×{oc[e['kategori']]} öncelikli"
    if t == "kural_ekle":
        d = kurallar.oku()
        d["kurallar"].append({"metin": e["metin"], "kapsam": e.get("kapsam", "hepsi"), "aktif": True})
        kurallar.kaydet(d)
        return "Marka kurallarına eklendi"
    if t == "deneme_reels":
        if e["deger"] not in ("kapali", "yeni_formatlar", "hepsi"):
            raise ValueError("Geçersiz değer")
        ofis_ayar.guncelle(deneme_reels=e["deger"])
        return f"Deneme Reels: {e['deger']}"
    if t == "not":
        return "Not alındı"
    raise ValueError("Bu eylem türü desteklenmiyor")


# ---------------- haftalik toplanti ----------------
def _veri():
    from . import analiz, iletisim, ofis_ayar, yayin
    v = {"ogrenim": analiz.ogrenimler(), "iletisim": iletisim.son_rapor(), "hesap": yayin.hesap_gecmisi(),
         "ayar": yayin.ayar_oku(), "ofis": ofis_ayar.oku()}
    v["satis"] = {}
    try:
        from . import rakip
        v["rakip"] = rakip.son()
    except Exception:
        v["rakip"] = {}
    return v


def aday_oneriler(v):
    """Kural tabanli, olculebilir oneriler. Doner: [(ajan, baslik, gerekce, eylem)]"""
    from . import reels_formatlari
    out = []
    o = v["ogrenim"] or {}
    satirlar = (o.get("tercih") or []) + (o.get("kacin") or [])
    acik = [f for f in reels_formatlari.FORMATLAR if f not in (v["ofis"].get("reels_kapali") or [])]
    # 1) zayif Reels formati
    for s in o.get("kacin") or []:
        if s["alan"] == "reels_format" and s["n"] >= 2 and s["fark"] <= -0.5 and s["deger"] in acik and len(acik) > 3:
            ad = reels_formatlari.FORMATLAR.get(s["deger"], s["deger"])
            out.append(("PerformansAnalisti", f"“{ad}” Reels formatını bir süre kapatalım",
                        f"{s['n']} Reels'te ortalamanın {abs(s['fark']):.1f} puan altında kaldı.",
                        {"tur": "reels_format_kapat", "format": s["deger"]}))
    # 2) takipcilerin en aktif saati -> Reels saati
    cs = (v["hesap"] or {}).get("cevrimici_saat") or {}
    if cs:
        mb, mbit = v["ayar"]["mesai_bas"], v["ayar"]["mesai_bit"]
        ad_saat = {}
        for k, n in cs.items():
            h = int(k)            # hesap_gecmisi zaten musterinin yerel saatine cevrilmis
            ad_saat[h] = ad_saat.get(h, 0) + n
        uygun = [(n, h) for h, n in ad_saat.items() if int(mb[:2]) + 1 <= h <= int(mbit[:2]) - 1]
        if uygun:
            n, h = max(uygun)
            simdiki = v["ayar"]["saatler"].get("reels", "18:30")
            if abs(h * 60 - (int(simdiki[:2]) * 60 + int(simdiki[3:]))) >= 60:
                saat = f"{h:02d}:00" if h * 60 <= int(mbit[:2]) * 60 - 30 else f"{int(mbit[:2]) - 1:02d}:30"
                out.append(("PerformansAnalisti", f"Reels'i {saat}'e alalım",
                            f"Instagram takipçilerimiz en çok bu saatte çevrimiçi (Meta verisi, mesai içindeki en yoğun saat).",
                            {"tur": "yayin_saati", "format": "reels", "saat": saat}))
    # 3) cok sorulan / cok satan kategori -> oncelik
    il = v["iletisim"] or {}
    for urun, n in (il.get("urun_ilgisi") or [])[:2]:
        if n >= 3:
            kat = _urun_kategori(urun)
            if kat and kat not in (v["ofis"].get("oncelikli_kategoriler") or {}):
                out.append(("IletisimAnalisti", f"“{kat}” kategorisini plana daha sık koyalım",
                            f"Son yorum ve DM'lerde “{urun}” {n} kez soruldu.", {"tur": "kategori_oncelik", "kategori": kat, "carpan": 1.5}))
    for kat, n in ((v["satis"] or {}).get("kategori_satis") or [])[:2]:
        if n >= 2 and kat not in (v["ofis"].get("oncelikli_kategoriler") or {}):
            out.append(("UrunSorumlusu", f"Çok satan “{kat}” kategorisine öncelik verelim",
                        f"Satış ekibi son 30 günde bu kategoriden sosyal medya kaynaklı {n} satış kaydetti.",
                        {"tur": "kategori_oncelik", "kategori": kat, "carpan": 1.6}))
    # 4) fiyat sorusu cok -> kural
    konular = il.get("konular") or {}
    if konular.get("fiyat", 0) >= 5:
        out.append(("MetinYazari", "Fiyatı her metnin ilk satırına yazalım",
                    f"Bu hafta {konular['fiyat']} fiyat sorusu geldi; fiyat göze çarpmıyor olabilir.",
                    {"tur": "kural_ekle", "metin": "Put the exact price in the first line of every caption.", "kapsam": "metin"}))
    if konular.get("konum", 0) >= 5:
        out.append(("MetinYazari", "Adresi metinlerde net yazalım",
                    f"Bu hafta {konular['konum']} kez adres/showroom soruldu.",
                    {"tur": "kural_ekle", "metin": f"Mention that customers can {musteri.bilgi()['yonlendirme']} and ask for the address by DM.", "kapsam": "metin"}))
    # 5) basarili tasarim ozelligi -> not
    for s in (o.get("tercih") or [])[:1]:
        if s["alan"] in ("duzen", "fontlar", "palet_ton", "fiyat_stili") and s["n"] >= 3:
            out.append(("SanatYonetmeni", f"Tasarımda “{s['deger']}” çizgisi iyi gidiyor",
                        f"{s['n']} içerikte ortalamanın {s['fark']:.1f} puan üstünde; Sanat Yönetmeni bunu zaten daha sık seçecek.",
                        {"tur": "not", "konu": f"{s['alan']}={s['deger']}"}))
    return out


def _urun_kategori(urun_adi):
    try:
        for dosya in ("tum_urunler.json", "urunler.json"):
            for u in json.loads((VERI / dosya).read_text(encoding="utf-8")):
                if u.get("ad", "").lower() == str(urun_adi).lower() or u.get("ad", "").lower().startswith(str(urun_adi).split(" serisi")[0].lower()):
                    return u.get("kategori", "").split(">")[-1].strip()
    except Exception:
        pass
    return None


def toplanti(gunluk=print):
    """Haftalik toplanti: veriyi toplar, ajanlar tartisir (pano + kayit), Mudur onerileri karta doker."""
    from . import llm, pano
    v = _veri()
    adaylar = aday_oneriler(v)
    o = v["ogrenim"] or {}
    il = v["iletisim"] or {}
    satis = v["satis"] or {}
    ozet = [f"Puanlanan içerik: {o.get('n', 0)}, genel ortalama {o.get('genel_ort', '-')}"]
    if o.get("en_iyi"):
        ozet.append(f"En iyi içerik: {o['en_iyi']['urun']} ({o['en_iyi']['skor']}/5)")
    if il.get("yorum"):
        ozet.append(f"Yorum/DM: {il['yorum'].get('toplam', 0)} yorum, {il.get('dm', {}).get('konusma_24s', 0)} DM; konular: "
                    + ", ".join(f"{k} {n}" for k, n in list((il.get('konular') or {}).items())[:4]))
    if satis.get("toplam"):
        ozet.append(f"Satış kayıtları (30 gün): {satis['toplam']} kayıt, {satis.get('satis', 0)} satış")
    if (v.get("rakip") or {}).get("hesaplar"):
        ozet.append("Rakipler: " + "; ".join(f"@{h['kullanici']} ort. {h.get('ort_begeni', 0)} beğeni"
                                             for h in v["rakip"]["hesaplar"][:3]))
    konusmalar = [("Yonetici", "Haftalık toplantıyı açıyorum. Geçen haftanın rakamlarına bakalım.")]
    konusmalar += [("PerformansAnalisti", " · ".join(ozet))]
    fikir = None
    try:
        cevap = llm.sor(f"You are the office manager of the social media team of {musteri.tanim()}. "
                        "Answer ONLY with valid JSON.",
                        "Weekly data:\n- " + "\n- ".join(ozet) + "\n\nProposals already on the table:\n- "
                        + "\n- ".join(b for _, b, _, _ in adaylar) +
                        f"\n\nGive ONE extra creative content idea for next week that fits {musteri.bilgi()['tanim']} in "
                        f"{musteri.sehirler_metni()} (no prices, no promises). "
                        "Return JSON: {\"fikir_tr\": \"<one Turkish sentence>\", "
                        "\"kapanis_tr\": \"<one short Turkish closing sentence from the manager>\"}", json_mod=True, sicaklik=0.7)
        if isinstance(cevap, dict):
            fikir = (cevap.get("fikir_tr") or "").strip()
            if fikir:
                konusmalar.append(("PazarlamaUzmani", "Bir fikrim var: " + fikir))
            if cevap.get("kapanis_tr"):
                konusmalar.append(("Yonetici", cevap["kapanis_tr"].strip()))
    except Exception:
        pass
    d = _oku()
    eklenen = []
    for ajan, baslik, gerekce, eylem in adaylar:
        x = ekle(ajan, baslik, gerekce, eylem, d)
        if x:
            eklenen.append(x)
            konusmalar.insert(-1 if fikir else len(konusmalar), (ajan, f"Önerim: {baslik}. {gerekce}"))
    if fikir:
        x = ekle("PazarlamaUzmani", "İçerik fikri: " + fikir[:110], fikir, {"tur": "not", "konu": fikir[:60]}, d)
        if x:
            eklenen.append(x)
    if not eklenen:
        konusmalar.append(("Yonetici", "Bu hafta onayınıza sunacak yeni bir değişiklik çıkmadı; mevcut düzenle devam."))
    else:
        konusmalar.append(("Yonetici", f"{len(eklenen)} öneriyi patronun onayına sunuyorum (Öneriler sayfası)."))
    d["toplantilar"].append({"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "konusmalar": konusmalar,
                             "oneriler": [x["id"] for x in eklenen]})
    _yaz(d)
    for ajan, metin in konusmalar:
        try:
            pano.yaz(ajan, "Herkes", metin[:600], "rapor" if ajan == "Yonetici" else "mesaj")
        except Exception:
            pass
    return {"oneriler": eklenen, "konusmalar": konusmalar}
