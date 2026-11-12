"""Haftalik icerik plani: 7 gun icin urun + tema + etkinlik + pazarlama acisi.
veri/haftalik_plan.json. Gun durumlari: taslak -> onayli -> uretildi.
calistir.py bir gunu uretirken plandaki urunu kullanir (fiyat feed'den taze alinir).
"""
import json
import random
from collections import Counter
from datetime import date, timedelta

from . import analiz, fiyat, llm, musteri, sanat
from .ayarlar import AYAR, KOK, VERI

FORMATLAR = ["post", "carousel", "reels"]          # her gun 3 icerik, her biri farkli urun
FORMAT_AD = {"post": "Post", "carousel": "Carousel", "reels": "Reels"}
PLAN = VERI / "haftalik_plan.json"
TERCIH = VERI / "plan_tercih.json"   # kullanicinin son sectigi kategoriler (sonraki haftalar icin de gecerli)


def eslesir(urun, secim):
    uk, s = (urun.get("kategori") or "").strip().lower(), (secim or "").strip().lower()
    return bool(s) and (uk == s or uk.startswith(s + " >"))


def kategori_agaci(urunler):
    agac = {}
    for u in urunler:
        if not u.get("gorseller"):
            continue
        parca = [x.strip() for x in (u.get("kategori") or "").split(">") if x.strip()]
        if not parca:
            continue
        ana = agac.setdefault(parca[0], {"ad": parca[0], "sayi": 0, "alt": {}})
        ana["sayi"] += 1
        if len(parca) > 1:
            alt = " > ".join(parca[:2])
            ana["alt"][alt] = ana["alt"].get(alt, 0) + 1
    return sorted(({"ad": a["ad"], "sayi": a["sayi"],
                    "alt": sorted(({"ad": k, "kisa": k.split(">")[-1].strip(), "sayi": v} for k, v in a["alt"].items()),
                                  key=lambda x: -x["sayi"])} for a in agac.values()), key=lambda x: -x["sayi"])


def tercih_oku():
    try:
        return json.loads(TERCIH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def tercih_kaydet(kategoriler, gunler):
    TERCIH.parent.mkdir(parents=True, exist_ok=True)
    TERCIH.write_text(json.dumps({"kategoriler": kategoriler, "gunler": gunler}, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def _normal(g):
    """Eski (gun basina tek urun) planlari yeni yapiya tasir: eski urun Reels slotunda kalir,
    post/carousel slotlari uretim sirasinda eksikleri_doldur() ile tamamlanir."""
    if "icerikler" not in g:
        g["icerikler"] = {"reels": {"urun": g["urun"], "aci": g.get("aci", ""), "klasor": g.get("klasor")}}
    for tur, ic in g["icerikler"].items():
        ic.setdefault("klasor", None)
    return g


def oku():
    try:
        p = json.loads(PLAN.read_text(encoding="utf-8"))
    except Exception:
        return {"gunler": []}
    for g in p.get("gunler", []):
        _normal(g)
    return p


def kaydet(p):
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def _ozet(u):
    return {"id": u.get("id"), "ad": u["ad"], "url": u["url"], "kategori": u.get("kategori", ""),
            "fiyat_metni": u.get("fiyat_metni", ""), "eski_fiyat_metni": u.get("eski_fiyat_metni", ""),
            "indirim_yuzde": u.get("indirim_yuzde") or 0, "gorsel": (u.get("gorseller") or [""])[0],
            "gorsel_sayisi": len(u.get("gorseller") or [])}


def _ana(u):
    return (u.get("kategori", "").split(">")[0] or "?").strip().lower()


def _alt(u):
    return (u.get("kategori", "").split(">")[-1] or "?").strip().lower()


def _puan(u, gun_bilgi):
    """Kural tabanli secim puani: indirim, foto sayisi, ogrenimler, etkinlik."""
    p = 1.0 + min(len(u.get("gorseller", [])), 4) * 0.15
    ind = u.get("indirim_yuzde") or 0
    if gun_bilgi["etkinlik"]:
        p += ind / 40                                         # kampanya gunlerinde indirimli urun one
    p *= analiz.ozellik_agirligi("ana_kategori", u.get("kategori", "").split(">")[0].strip())
    p *= analiz.ozellik_agirligi("alt_kategori", u.get("kategori", "").split(">")[-1].strip())
    p *= _oncelik(u)
    return p * random.uniform(0.85, 1.15)


def _oncelik(u):
    """Oneri kutusundan onaylanan oncelikli kategoriler."""
    try:
        from . import ofis_ayar
        kat = [k.strip().lower() for k in u.get("kategori", "").split(">") if k.strip()]
        c = 1.0
        for ad, carpan in (ofis_ayar.oku().get("oncelikli_kategoriler") or {}).items():
            if ad.strip().lower() in kat:
                c = max(c, float(carpan))
        return c
    except Exception:
        return 1.0


def olustur(urunler, baslangic=None, gun_sayisi=7, gunluk=print, secili=None, gun_kategorileri=None):
    """urunler: fiyat.hazirla'dan gecmis aday listesi.
    secili: kullanicinin sectigi kategoriler ("Living Room" ya da "Living Room > Corner Sofa").
    gun_kategorileri: 7 elemanli liste; dolu olan gun MUTLAKA o kategoriden urun alir."""
    secili = [k for k in (secili or []) if k]
    gun_kategorileri = list(gun_kategorileri or []) + [""] * gun_sayisi
    if secili:
        urunler = [u for u in urunler if any(eslesir(u, k) for k in secili)] or urunler
    baslangic = baslangic or date.today() + timedelta(days=1)
    hazirlanmis = set()
    try:
        from . import pano
        hazirlanmis = pano.son_hazirlananlar(AYAR.get("tekrar_etmeme_gun", 30))
    except Exception:
        pass
    havuz = [u for u in urunler if u.get("gorseller") and u["url"] not in hazirlanmis] or list(urunler)
    gunler = []
    for i in range(gun_sayisi):
        d = baslangic + timedelta(days=i)
        b = sanat.baglam(d)
        gunler.append({"tarih": d.isoformat(), "gun": d.strftime("%A"),
                       "tema": AYAR.get("haftalik_tema", {}).get(d.strftime("%A"), ""),
                       "etkinlik": ", ".join(e["ad"] for e in b["etkinlikler"]),
                       "yaklasan": ", ".join(b["yaklasan"])})

    # --- 1) kurallarla cesitli aday listesi: her gun 3 farkli urun (post / carousel / reels) ---
    slotlar_g = [(i, k) for i in range(len(gunler)) for k in range(len(FORMATLAR))]
    secim, kullanilan_url = [], set()
    sira = secili or AYAR.get("kategoriler", ["living room", "dining room", "bedroom"])
    for n, (i, k) in enumerate(slotlar_g):
        g = gunler[i]
        g["kategori_istegi"] = gun_kategorileri[i]
        gunun_alt = {_alt(secim[m]) for m, (ii, _) in enumerate(slotlar_g[:n]) if ii == i}
        uygun = [u for u in havuz if u["url"] not in kullanilan_url and _alt(u) not in gunun_alt]
        if gun_kategorileri[i]:       # kullanici bu gune ozel kategori istedi
            tercihli = ([u for u in uygun if eslesir(u, gun_kategorileri[i])]
                        or [u for u in urunler if eslesir(u, gun_kategorileri[i]) and u["url"] not in kullanilan_url]
                        or [u for u in urunler if eslesir(u, gun_kategorileri[i])])
        else:
            hedef = sira[n % len(sira)]
            tercihli = [u for u in uygun if eslesir(u, hedef) or hedef.lower().replace(" ", "") in _ana(u).replace(" ", "")]
        tercihli = tercihli or uygun or [u for u in havuz if u["url"] not in kullanilan_url] or havuz
        hafta_alt = Counter(_alt(x) for x in secim)
        u = max(tercihli, key=lambda x: _puan(x, g) / (1 + 0.8 * hafta_alt[_alt(x)]))
        secim.append(u)
        kullanilan_url.add(u["url"])

    # --- 2) LLM (varsa) her urune pazarlama acisi yazar, gerekirse secimi iyilestirir ---
    kisa = random.sample(havuz, min(30, len(havuz)))
    for u in secim:
        if u not in kisa:
            kisa.append(u)
    liste = "\n".join(f"{j}. {u['ad']} | {u.get('kategori', '')} | {u.get('fiyat_metni', '')} | "
                      f"-{u.get('indirim_yuzde') or 0}% | photos:{len(u.get('gorseller', []))}" for j, u in enumerate(kisa))
    slot_metni = "\n".join(f"Slot {n + 1}: {gunler[i]['tarih']} {gunler[i]['gun']}, theme '{gunler[i]['tema']}', "
                           f"event: {gunler[i]['etkinlik'] or 'none'}"
                           + (f", REQUIRED CATEGORY: {gunler[i]['kategori_istegi']}" if gunler[i].get("kategori_istegi") else "")
                           for n, (i, k) in enumerate(slotlar_g))
    oneri = ", ".join(f"Slot {n + 1}: #{kisa.index(u)}" for n, u in enumerate(secim))
    cevap = llm.sor(
        f"You are the content strategist of {musteri.tanim()}. {musteri.satis_kanali()} "
        "Answer ONLY with valid JSON.",
        f"Plan next week's Instagram content: THREE different products per day (3 slots per day).\nSlots:\n{slot_metni}\n\n"
        f"Candidate products:\n{liste}\n\n"
        f"A rule-based draft picked: {oneri}. Improve it if you can. Rules: no product twice in the week, the three "
        f"products of a day should be from different sub-categories, discounted items on campaign days, match the "
        f"day's theme. {analiz.istem_ozeti()}\n"
        'Return JSON: {"slots": [{"slot": 1, "product": <candidate number>, "angle": "<one-sentence English marketing angle>"}, ...]}',
        json_mod=True, sicaklik=0.5)
    acilar = {}
    if cevap and isinstance(cevap.get("slots"), list):
        yeni = list(secim)
        for d in cevap["slots"]:
            try:
                n, j = int(d["slot"]) - 1, int(d["product"])
                if not (0 <= n < len(slotlar_g) and 0 <= j < len(kisa)):
                    continue
                istek = gunler[slotlar_g[n][0]]["kategori_istegi"]
                if istek and not eslesir(kisa[j], istek):
                    continue
                yeni[n] = kisa[j]
                acilar[n] = str(d.get("angle", ""))[:200]
            except Exception:
                continue
        urls = [u["url"] for u in yeni]
        if len(set(urls)) == len(urls):
            secim = yeni
        else:
            gunluk("! LLM tekrar eden urun sectirdi, kural tabanli plana donuluyor.")
            acilar = {}
    for i, g in enumerate(gunler):
        gunun = [(n, secim[n]) for n, (ii, _) in enumerate(slotlar_g) if ii == i]
        # en cok fotografi olan carousel'e, sonraki reels'e, kalan post'a
        gunun.sort(key=lambda x: -len(x[1].get("gorseller") or []))
        g["icerikler"] = {}
        for tur, (n, u) in zip(["carousel", "reels", "post"], gunun):
            g["icerikler"][tur] = {"urun": _ozet(u), "aci": acilar.get(n) or g["tema"] or "Comfort for your home", "klasor": None}
        g["icerikler"] = {t: g["icerikler"][t] for t in FORMATLAR if t in g["icerikler"]}
        g["urun"] = g["icerikler"]["post"]["urun"]       # eski ekranlar icin
        g["aci"] = g["icerikler"]["post"]["aci"]
        g["durum"] = "taslak"
        g["klasor"] = None
    p = {"olusturma": date.today().isoformat(), "kategoriler": secili, "gunler": gunler}
    kaydet(p)
    return p


def gun(tarih):
    for g in oku().get("gunler", []):
        if g["tarih"] == tarih:
            return g
    return None


def guncelle(tarih, **alanlar):
    p = oku()
    for g in p.get("gunler", []):
        if g["tarih"] == tarih:
            g.update(alanlar)
    kaydet(p)
    return p


def icerik_guncelle(tarih, tur, **alanlar):
    p = oku()
    for g in p.get("gunler", []):
        if g["tarih"] == tarih:
            g["icerikler"].setdefault(tur, {"urun": None, "aci": g.get("tema", ""), "klasor": None}).update(alanlar)
            if all(g["icerikler"].get(t, {}).get("klasor") for t in FORMATLAR):
                g["durum"] = "uretildi"
                g["klasor"] = g["icerikler"]["post"]["klasor"]
    kaydet(p)
    return p


def _planli_urller(p):
    return {ic["urun"]["url"] for g in p.get("gunler", []) for ic in g["icerikler"].values() if ic.get("urun")}


def eksikleri_doldur(urunler, tarih=None, gunluk=print):
    """Eski planlardan gelen gunlerde eksik post/carousel slotlarini doldurur (gunun diger urunlerinden farkli
    alt kategoriden, haftada tekrar etmeyen urunle)."""
    p = oku()
    planli = _planli_urller(p)
    try:
        from . import pano
        planli |= pano.son_hazirlananlar(AYAR.get("tekrar_etmeme_gun", 30))
    except Exception:
        pass
    secili = p.get("kategoriler") or tercih_oku().get("kategoriler") or []
    havuz = [u for u in urunler if u.get("gorseller") and (not secili or any(eslesir(u, k) for k in secili))] \
        or [u for u in urunler if u.get("gorseller")]
    degisti = False
    for g in p.get("gunler", []):
        if tarih and g["tarih"] != tarih:
            continue
        for tur in FORMATLAR:
            if g["icerikler"].get(tur, {}).get("urun"):
                continue
            gunun_alt = {_alt(ic["urun"]) for ic in g["icerikler"].values() if ic.get("urun")}
            aday = [u for u in havuz if u["url"] not in planli and _alt(u) not in gunun_alt] \
                or [u for u in havuz if u["url"] not in planli] or havuz
            if tur == "carousel":
                aday = [u for u in aday if len(u.get("gorseller") or []) >= 3] or aday
            hafta_alt = Counter(_alt(ic["urun"]) for gg in p["gunler"] for ic in gg["icerikler"].values() if ic.get("urun"))
            u = max(aday, key=lambda x: _puan(x, g) / (1 + 0.8 * hafta_alt[_alt(x)]))
            fiyat.hazirla(u)
            g["icerikler"][tur] = {"urun": _ozet(u), "aci": g.get("tema") or "Comfort for your home", "klasor": None}
            planli.add(u["url"])
            degisti = True
            gunluk(f"{g['tarih']} {FORMAT_AD[tur]} slotu bostu, '{u['ad']}' eklendi.")
        g["icerikler"] = {t: g["icerikler"][t] for t in FORMATLAR if t in g["icerikler"]}
    if degisti:
        kaydet(p)
    return p


def urun_degistir(tarih, urunler, tur="post"):
    """O gunun ilgili slotundaki urunu ayni ana kategoriden baska bir urunle degistirir."""
    p = oku()
    planli = _planli_urller(p)
    for g in p.get("gunler", []):
        if g["tarih"] == tarih:
            ic = g["icerikler"].get(tur) or {}
            if ic.get("klasor"):
                continue     # uretilmis slot degismez
            ana = ((ic.get("urun") or {}).get("kategori", "").split(">")[0]).strip().lower()
            istek = g.get("kategori_istegi")
            adaylar = ([u for u in urunler if u["url"] not in planli and u.get("gorseller") and eslesir(u, istek)] if istek else
                       [u for u in urunler if u["url"] not in planli and u.get("gorseller") and _ana(u) == ana]) \
                or [u for u in urunler if u["url"] not in planli and u.get("gorseller")]
            if adaylar:
                u = random.choice(adaylar)
                fiyat.hazirla(u)
                g["icerikler"][tur] = {"urun": _ozet(u), "aci": g["tema"] or "Comfort for your home", "klasor": None}
                if tur == "post":
                    g["urun"], g["aci"] = g["icerikler"]["post"]["urun"], g["icerikler"]["post"]["aci"]
                g["durum"] = "taslak"
    kaydet(p)
    return p
