"""Sanal ofisin calisanlari. Her ajanin TEK ve DAR bir isi var.

LLM'in yaptigi: secim, yaratici metin, elestiri.
Kodun yaptigi: veri cekme, fiyat hesabi, cizim, video (hata kabul etmeyen isler).
"""
import json
import random
import re
import time
from pathlib import Path
from datetime import date

from . import fiyat, llm, musteri, pano
from .ayarlar import AYAR, KOK, VERI, MUZIK

KOK_MUZIK = MUZIK

YASAKLI = musteri.yasak_ifadeler()   # musteri online satmiyorsa "buy online" vb. yasak


class Ajan:
    ad = unvan = emoji = ""
    sistem = ""

    def __init__(self, sira):
        pano.ajan_kaydet(self.ad, self.unvan, self.emoji, sira)

    def calis(self, konusma):
        pano.durum(self.ad, "calisiyor", konusma)

    def soyle(self, alici, metin, tur="mesaj"):
        pano.yaz(self.ad, alici, metin, tur)
        pano.durum(self.ad, "calisiyor", metin)
        time.sleep(0.6)  # ofis ekraninda takip edilebilsin diye

    def bitir(self, metin="Tamam, isim bitti."):
        pano.durum(self.ad, "bitti", metin)

    def dusun(self, istem, json_mod=False, sicaklik=0.7):
        return llm.sor(self.sistem, istem, json_mod=json_mod, sicaklik=sicaklik)


# ------------------------------------------------------------------
class Yonetici(Ajan):
    ad, unvan, emoji = "Yonetici", "Ofis Muduru", "🧑‍💼"
    sistem = (f"You are the office manager of the social media team of {musteri.tanim()}. "
              "Speak in short, friendly Turkish sentences (max 2 sentences).")

    def toplanti_ac(self, tema):
        self.calis("Gunluk toplantiyi baslatiyorum...")
        metin = self.dusun(f"Bugunun temasi: '{tema}'. Ekibe kisa bir gunaydin ve bugunun planini soyle: "
                           "urun sec, metin yaz, kontrol et, gorsel ve Reels hazirla.")
        self.soyle("Herkes", metin or f"Gunaydin ekip! Bugunun temasi: {tema}. "
                   "Urun sec, metin yaz, kontrol et, gorsel ve Reels hazirla.")

    def kapanis(self, klasor, revizyon):
        self.soyle("Herkes", f"Harika is! {revizyon} revizyonla tamamladik. Ciktilar: {klasor.name}/ klasorunde. "
                   "📤 Yayin sekmesinde: otomatik yayin aciksa saatinde paylasilir; istemezseniz 'Kaldir' deyin.", "rapor")
        self.bitir("Gun tamamlandi ✅")


# ------------------------------------------------------------------
class UrunSorumlusu(Ajan):
    ad, unvan, emoji = "UrunSorumlusu", "Urun Sorumlusu", "📦"

    def _fikirden(self):
        from . import fikir_kaynagi
        self.calis("Sektor arastirmasindan bugunun icerik fikirlerini hazirliyorum...")
        urunler = fikir_kaynagi.fikir_urunleri(3, gunluk=lambda m: (print(m, flush=True), pano.durum(self.ad, "calisiyor", m)))
        self.tum_urunler = list(urunler)
        if not urunler:
            self.soyle("Yonetici", "Icerik fikri icin gorsel bulamadim (stok foto / yapay zeka kapali).", "hata")
            pano.durum(self.ad, "hata", "Gorsel kaynagi yok")
            return []
        self.soyle("PazarlamaUzmani", f"Bugun icin {len(urunler)} icerik fikri ve gorselleri hazir: "
                   + "; ".join(u["ad"] for u in urunler))
        self.bitir()
        return urunler

    def urunleri_getir(self, demo=False):
        from . import urun_cekici
        self.calis("Siteden urunleri cekiyorum...")
        from . import fikir_kaynagi
        if demo:
            from .demo import demo_urunler
            urunler = demo_urunler()
            self.soyle("Yonetici", f"Demo modu: {len(urunler)} ornek urun hazirladim.")
        elif fikir_kaynagi.veri_yok_mu():
            # Urun sitesi/verisi olmayan isletme: icerigi sektor bilgisi + arastirma + yapay zeka saglar
            return self._fikirden()
        else:
            try:
                urunler = urun_cekici.urunleri_cek(lambda m: pano.durum(self.ad, "calisiyor", m))
            except Exception as e:
                self.soyle("Yonetici", f"Siteye ulasamadim ({type(e).__name__}). Onbellekteki listeyi kullaniyorum.")
                urunler = urun_cekici.onbellekten()
        self.tum_urunler = list(urunler)   # plan icin: son 30 gun filtresinden ONCEKI tam liste
        hazirlanmis = pano.son_hazirlananlar(AYAR.get("tekrar_etmeme_gun", 30))
        taze = [u for u in urunler if u["url"] not in hazirlanmis] or urunler
        for u in taze:  # fiyat hesabi: KOD yapar, LLM degil
            fiyat.hazirla(u)
        if not taze:
            # Site urun listesi vermiyor (kurumsal site, hizmet isletmesi...): icerigi biz uretiriz
            self.soyle("Yonetici", "Sitede urun listesi bulamadim; sektor bilgisinden icerik fikirlerine geciyorum.")
            return self._fikirden()
        self.soyle("PazarlamaUzmani",
                   f"{len(taze)} aday urun var (son {AYAR.get('tekrar_etmeme_gun', 30)} gunde hazirlananlari cikardim). "
                   f"Fiyatlar {fiyat.yerel_para()} cinsine cevrildi.")
        self.bitir()
        return taze


# ------------------------------------------------------------------
class PazarlamaUzmani(Ajan):
    def plandan(self, gun, adaylar, tum_urunler):
        """Haftalik plandaki urunu taze fiyatlariyla bulur. Bulamazsa None."""
        from . import fiyat
        url = gun["urun"]["url"]
        u = next((x for x in list(adaylar) + list(tum_urunler) if x["url"] == url), None)
        if not u:
            self.soyle("Yonetici", f"Plandaki urun ({gun['urun']['ad']}) artik sitede yok, yerine ben seciyorum.", "uyari")
            return None, None
        fiyat.hazirla(u)
        self.soyle("MetinYazari", f"Haftalik plana gore bugun '{u['ad']}' ({u['fiyat_metni']}). Aci: {gun['aci']}")
        self.bitir()
        return u, gun["aci"]

    def haftalik_plan(self, urunler, baslangic=None, secili=None, gun_kategorileri=None):
        from . import plan
        self.calis("Gelecek haftanin icerik planini hazirliyorum...")
        p = plan.olustur(urunler, baslangic, gunluk=lambda m: pano.durum(self.ad, "calisiyor", m),
                         secili=secili, gun_kategorileri=gun_kategorileri)
        ozet = " | ".join(f"{g['gun'][:3]}: {g['urun']['ad']}" for g in p["gunler"])
        self.soyle("Yonetici", f"7 gunluk plan hazir: {ozet}")
        self.bitir("Plan hazir 📅")
        return p


    ad, unvan, emoji = "PazarlamaUzmani", "Pazarlama Uzmani", "📈"
    sistem = (f"You are a social media marketing strategist for {musteri.tanim()}. "
              f"{musteri.satis_kanali()} Answer ONLY with valid JSON.")

    def urun_sec(self, adaylar, tema):
        self.calis("Bugun hangi urun one cikmali, dusunuyorum...")
        secenek = random.sample(adaylar, min(8, len(adaylar)))
        liste = "\n".join(f"{i}. {u['ad']} | {u.get('kategori', '')[:60]} | {u['fiyat_metni']}"
                          for i, u in enumerate(secenek))
        from . import analiz
        cevap = self.dusun(
            f"Today's theme: {tema}\n{analiz.istem_ozeti()}\nCandidate products:\n{liste}\n\n"
            f'Pick ONE product that best fits the theme and the local Instagram audience{musteri.yer()}. '
            'Return JSON: {"index": <number>, "angle": "<one sentence marketing angle in English>", '
            '"reason_tr": "<why, one short sentence in Turkish>"}',
            json_mod=True, sicaklik=0.5)
        try:
            urun = secenek[int(cevap["index"])]
            aci, neden = cevap.get("angle", tema), cevap.get("reason_tr", "")
        except Exception:
            urun, aci, neden = secenek[0], tema, "(sablon modu) ilk adayi sectim"
        self.soyle("MetinYazari", f"Bugun '{urun['ad']}' ({urun['fiyat_metni']}) one cikacak. Aci: {aci}. {neden}")
        self.bitir()
        return urun, aci


# ------------------------------------------------------------------
class SanatYonetmeni(Ajan):
    ad, unvan, emoji = "SanatYonetmeni", "Sanat Yonetmeni", "🎭"
    YONLER = {
        "A": ("A_editoryal_post.html", "Editoryal: full-bleed photo, minimal text, quiet luxury (no price on image)"),
        "B": ("B_altin_cerceve_post.html", "Gold frame: dark espresso gallery look, premium, price shown"),
        "C": ("C_showroom_firsati_post.html", "Showroom deal: photo + cream panel + gold discount badge, sales-focused"),
        "D": ("D_kolaj_post.html", "Collage: one big + two small photos, shows details/angles"),
        "E": ("E_canli_post.html", "Vivid: bold color from the photo, big 'XX% OFF' headline, energetic"),
    }
    sistem = (f"You are the art director of the Instagram account of {musteri.tanim()}. "
              "You keep the feed varied and on-brand. Answer ONLY with valid JSON.")
    GECMIS = None

    def _gecmis(self):
        import json
        from .ayarlar import KOK, VERI, MUZIK
        yol = VERI / "sanat_gecmis.json"
        try:
            return yol, json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            return yol, []

    def sec(self, urun, tema, gorsel_yollari=None, ek_kisit="", tarih=None):
        """dinamik modda bugune ozel YENI bir tarif (dict) uretir; sabit modda A/B/C/E harfi doner."""
        if AYAR.get("sanat_modu", "dinamik") == "dinamik":
            return self.tarif_uret(urun, gorsel_yollari or [], ek_kisit, tarih)
        return self.sabit_sec(urun, tema)

    def tarif_uret(self, urun, gorsel_yollari, ek_kisit="", tarih=None):
        from datetime import date as _d
        from . import marka, sanat
        self.calis("Trendlere ve takvime bakip bugunun sablonunu tasarliyorum...")
        bglm = sanat.baglam(_d.fromisoformat(tarih) if tarih else None)
        foto_vurgu = None
        if gorsel_yollari:
            try:
                v, k, _ = marka.vurgu_rengi(marka.gorsel_hazirla(Path(gorsel_yollari[0])), sum(map(ord, urun["ad"])))
                foto_vurgu = (k, v)
            except Exception:
                pass
        cevap = self.dusun(sanat.llm_istemi(urun, bglm, sanat.son_tarifler(), ek_kisit), json_mod=True, sicaklik=0.9)
        if cevap and isinstance(cevap, dict) and cevap.get("duzen"):
            tarif = sanat.dogrula(cevap, urun, foto_vurgu)
        else:
            tarif = sanat.rastgele_tarif(urun, bglm, foto_vurgu=foto_vurgu)
        tarif["neden"] = str(tarif.get("neden", ""))[:200]
        sanat.kaydet(tarif)
        olay = ", ".join(e["ad"] for e in bglm["etkinlikler"]) or "ozel gun yok"
        self.soyle("Tasarimci", f"Yeni sablon: '{tarif['isim']}' — {tarif['duzen']} duzen, {tarif['fontlar']} fontlar, "
                   f"{tarif['motif']} motif, {tarif['fiyat_stili']} fiyat. ({olay}) {tarif['neden']}")
        satis = tarif["fiyat_stili"] in ("rozet", "serit") or bool(tarif["banner"])
        self.soyle("MetinYazari", "Satis odakli, kisa ve enerjik yaz." if satis else "Sakin, zarif ve premium bir dil kullan.")
        self.bitir()
        return tarif

    # ---------- REVIZYON: kullanicinin Onay kartindan gelen istegi tarife cevirir ----------
    SECENEKLER = {
        "sablon": "Farkli sablon", "foto": "Farkli fotograf", "fiyat": "Fiyati one cikar", "sade": "Daha sade",
        "acik": "Daha acik renkler", "koyu": "Daha koyu renkler", "metin": "Metni yeniden yaz", "muzik": "Farkli muzik",
    }
    ACIK_PALET = {"zemin": "#F3EDE4", "vurgu": "#8A6A3B", "panel": "#EFE6D8"}
    KOYU_PALET = {"zemin": "#1C1612", "vurgu": "#C9A24B", "panel": "#241C17"}

    def _not_coz(self, eski, not_metni, urun):
        """Serbest notu (Turkce) tarif degisikligine + metin talimatina cevirir.
        Doner: (degisiklik_dict, ek_secenekler, metin_notu, aciklama)"""
        from . import sanat
        sozluk = "\n".join(f"- {alan}: " + ", ".join(f"{k} = {v}" for k, v in d.items())
                           for alan, d in sanat._aktif_aciklama().items())
        cevap = self.dusun(
            f"Current Instagram template recipe (JSON): {json.dumps({k: eski.get(k) for k in ('duzen', 'fontlar', 'motif', 'fiyat_stili', 'efekt', 'banner', 'palet')})}\n"
            f"Product: {urun['ad']} (discount {urun.get('indirim_yuzde') or 0}%)\n"
            f"The business owner looked at the design and asked for this revision (in Turkish): \"{not_metni}\"\n\n"
            f"Design vocabulary (use ONLY these keys/values):\n{sozluk}\n{__import__('ofis.kurallar', fromlist=['x']).istem('gorsel')}\n"
            "Translate the request into recipe changes. Change ONLY what the owner asked; keep everything else. "
            "If the request is about the text/caption/headline, put an English instruction for the copywriter in "
            "\"copy_note\". If it asks for another photo set \"other_photo\": true. If it asks for different music "
            "set \"other_music\": true.\n"
            'Return JSON: {"changes": {"duzen"?: "...", "fontlar"?: "...", "motif"?: "...", "fiyat_stili"?: "...", '
            '"efekt"?: "...", "banner"?: "<max 3 words or empty>", "palet"?: {"zemin": "#hex", "vurgu": "#hex", "panel": "#hex"}}, '
            '"copy_note": "<or empty>", "other_photo": false, "other_music": false, '
            '"summary_tr": "<one short Turkish sentence: what you will change>"}',
            json_mod=True, sicaklik=0.3)
        if isinstance(cevap, dict) and isinstance(cevap.get("changes", {}), dict):
            ek = [k for k, b in (("foto", cevap.get("other_photo")), ("muzik", cevap.get("other_music"))) if b is True]
            return (cevap.get("changes") or {}, ek, str(cevap.get("copy_note") or "").strip(),
                    str(cevap.get("summary_tr") or "").strip())
        # LLM yoksa: anahtar kelimelerle anla
        n = not_metni.lower()
        ek = []
        for anahtar, secenek in (("sade", "sade"), ("kalabal", "sade"), ("fiyat", "fiyat"), ("açık", "acik"),
                                 ("acik", "acik"), ("aydınlık", "acik"), ("koyu", "koyu"), ("şablon", "sablon"),
                                 ("sablon", "sablon"), ("tasarım", "sablon"), ("düzen", "sablon"), ("foto", "foto"),
                                 ("resim", "foto"), ("müzik", "muzik"), ("muzik", "muzik"), ("şarkı", "muzik")):
            if anahtar in n and secenek not in ek:
                ek.append(secenek)
        # "fiyat yazisi" gorsel istegidir; metin yazarina sadece acikca metinle ilgili notlar gider
        metin_notu = not_metni if any(a in n for a in ("metin", "başlık", "baslik", "caption", "açıklama", "kelime",
                                                       "cümle", "hashtag", "kanca")) else ""
        return {}, ek, metin_notu, "(sablon modu) notu anahtar kelimelerle yorumladim"

    def revize_et(self, eski, secenekler, not_metni, urun, gorsel_yollari, tarih=None):
        """Doner: (yeni_tarif, metin_notlari[list], ek_secenekler[list])"""
        from . import sanat
        import copy
        self.calis("Revizyon istegini inceliyorum...")
        secenekler = [s for s in secenekler if s in self.SECENEKLER]
        degisiklik, metin_notlari, aciklama = {}, [], ""
        if not_metni:
            degisiklik, ek, mn, aciklama = self._not_coz(eski, not_metni, urun)
            secenekler += [e for e in ek if e not in secenekler]
            if mn:
                metin_notlari.append(mn)
        if "sablon" in secenekler:
            yeni = self.tarif_uret(urun, gorsel_yollari, ek_kisit=(
                f"The owner did not like the previous design ({eski.get('duzen')} layout, {eski.get('fontlar')} fonts). "
                "Use a clearly DIFFERENT layout and font set."), tarih=tarih)
            if yeni["duzen"] == eski.get("duzen"):
                diger = [d for d in sanat.kurallar.izinli("duzen", sanat.DUZENLER) if d != eski.get("duzen")]
                if diger:
                    yeni["duzen"] = random.choice(diger)
            t = yeni
        else:
            t = copy.deepcopy(eski)
        for alan in ("duzen", "fontlar", "motif", "fiyat_stili", "efekt", "banner"):
            if alan in degisiklik:
                t[alan] = degisiklik[alan]
        if isinstance(degisiklik.get("palet"), dict):
            t["palet"] = {**(t.get("palet") or {}), **degisiklik["palet"]}
        indirim = (urun.get("indirim_yuzde") or 0) >= 5
        if "fiyat" in secenekler:
            t["fiyat_stili"] = "rozet" if indirim else "etiket_kart"
        if "sade" in secenekler:
            t.update({"motif": "yok", "efekt": "yok", "banner": ""})
            if t.get("fiyat_stili") == "serit":
                t["fiyat_stili"] = "rozet" if indirim else "sade"
        if "acik" in secenekler:
            t["palet"] = dict(self.ACIK_PALET)
        if "koyu" in secenekler:
            t["palet"] = dict(self.KOYU_PALET)
        if "metin" in secenekler and not metin_notlari:
            metin_notlari.append("The owner wants a fresh version: write a NEW hook, headline, caption and reels "
                                 "lines with a different angle than before.")
        t = sanat.dogrula(t, urun)   # Marka Kurallari yine burada kesinlesir
        t["isim"] = (str(eski.get("isim") or t.get("isim") or "Tasarim")[:30] + " (revize)") if "sablon" not in secenekler else t["isim"]
        t["neden"] = ("Revizyon: " + ", ".join(self.SECENEKLER[s] for s in secenekler)
                      + (f" | Not: {not_metni}" if not_metni else ""))[:200]
        ne = []
        for alan, ad in (("duzen", "duzen"), ("fontlar", "font"), ("motif", "motif"), ("fiyat_stili", "fiyat"),
                         ("efekt", "efekt"), ("banner", "banner")):
            if t.get(alan) != eski.get(alan):
                ne.append(f"{ad}: {eski.get(alan) or '-'} → {t.get(alan) or '-'}")
        if t.get("palet") != eski.get("palet"):
            ne.append("renkler degisti")
        self.soyle("Tasarimci", "Revizyon tarifi hazir: " + ("; ".join(ne) or "tasarim ayni kaliyor")
                   + (f". {aciklama}" if aciklama else ""))
        if metin_notlari:
            self.soyle("MetinYazari", "Patronun metin istegi var: " + " | ".join(metin_notlari), "revizyon")
        self.bitir("Revizyon tarifi hazir")
        return t, metin_notlari, secenekler

    def sabit_sec(self, urun, tema):
        import json
        self.calis("Bugunun tasarim yonunu seciyorum...")
        yol, gecmis = self._gecmis()
        izinli = [y for y in AYAR.get("tasarim_yonleri", "ABCE") if y in self.YONLER]
        if len(urun.get("gorseller", [])) < 3:
            izinli = [y for y in izinli if y != "D"]
        if (urun.get("indirim_yuzde") or 0) < 5:
            izinli = [y for y in izinli if y not in ("C", "E")]
        izinli = izinli or ["B"]
        son = gecmis[-2:]
        adaylar = [y for y in izinli if y not in son] or izinli
        liste = "\n".join(f"{y}: {self.YONLER[y][1]}" for y in adaylar)
        cevap = self.dusun(
            f"Today's theme: {tema}\nProduct: {urun['ad']} ({urun.get('kategori', '')}), "
            f"discount: {urun.get('indirim_yuzde') or 0}%\nRecent: {gecmis[-5:]}\n\nAvailable:\n{liste}\n\n"
            'Pick ONE. Return JSON: {"direction": "<letter>", "reason_tr": "<one short Turkish sentence>"}',
            json_mod=True, sicaklik=0.6)
        yon = (cevap or {}).get("direction", "").strip().upper()[:1]
        neden = (cevap or {}).get("reason_tr", "")
        if yon not in adaylar:
            yon = adaylar[len(gecmis) % len(adaylar)]
            neden = "(sablon modu) sirayla donduruyorum"
        gecmis.append(yon)
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(json.dumps(gecmis[-30:]), encoding="utf-8")
        tr = {"A": "Editoryal", "B": "Altin Cerceve", "C": "Showroom Firsati", "D": "Kolaj", "E": "Canli"}
        self.soyle("Tasarimci", f"Bugun {yon} · {tr[yon]} yonu. {neden}")
        self.soyle("MetinYazari", "Satis odakli, kisa ve enerjik yaz." if yon in ("C", "E")
                   else "Sakin, zarif ve premium bir dil kullan.")
        self.bitir()
        return yon


# ------------------------------------------------------------------
METIN_ALANLARI = ("hook", "headline", "caption", "pov")
LISTE_ALANLARI = ("hashtags", "reels_lines", "carousel_lines", "carousel_points")


def taslak_duzelt(t):
    """LLM cevabinda metin olmasi gereken alan liste, liste olmasi gereken alan metin gelebilir."""
    if not isinstance(t, dict):
        return t
    for k in METIN_ALANLARI:
        v = t.get(k)
        if isinstance(v, (list, tuple)):
            t[k] = ("\n" if k == "caption" else " ").join(str(x) for x in v if x)
        elif v is not None and not isinstance(v, str):
            t[k] = str(v)
    for k in LISTE_ALANLARI:
        v = t.get(k)
        if isinstance(v, str):
            t[k] = [x.strip() for x in re.split(r"[\n,]" if k == "hashtags" else r"\n", v) if x.strip()]
        elif isinstance(v, (list, tuple)):
            t[k] = [str(x) if not isinstance(x, dict) else " ".join(map(str, x.values())) for x in v if x]
    return t


class MetinYazari(Ajan):
    ad, unvan, emoji = "MetinYazari", "Metin Yazari", "✍️"
    sistem = (f"You are a copywriter for {musteri.ad()}, {musteri.tanim()}. "
              "Write warm, aspirational, clear English for Instagram/Facebook. "
              f"{musteri.satis_kanali()} "
              "Use the exact price given, never invent prices. Answer ONLY with valid JSON.")

    def yaz(self, urun, aci, geri_bildirim=None):
        self.calis("Caption yaziyorum..." if not geri_bildirim else "Notlara gore duzeltiyorum...")
        if urun.get("proje"):
            return self._proje_yaz(urun, aci, geri_bildirim)
        if urun.get("fikir"):
            return self._fikir_yaz(urun, aci, geri_bildirim)
        istem = (f"Product: {urun['ad']}\nCategory: {urun.get('kategori', '')}\n"
                 f"Details: {urun.get('aciklama', '')[:300]}\nPrice: {urun['fiyat_metni']}\n"
                 f"Marketing angle: {aci}\nCall to action: {AYAR['marka']['cta']}\n\n"
                 'Return JSON: {"hook": "<max 7 words, scroll-stopping, for the first 2 seconds of a Reel>", '
                 '"headline": "<max 9 words emotional benefit line for the post image, do NOT repeat the product name>", '
                 '"caption": "<3-5 short lines, include the exact price once, end with the call to action>", '
                 f'"hashtags": ["<8-12 hashtags, mix local {musteri.sehirler_metni()} tags for this business>"], '
                 '"reels_lines": ["<benefit line 1, max 6 words>", "<benefit line 2, max 6 words>"], '
                 '"carousel_lines": ["<3 lines, max 7 words each>"], '
                 '"carousel_points": ["<3 short selling points, max 5 words each>"], '
                 '"pov": "<POV line for a Reel, max 10 words, starts with POV:, relatable home moment>"}\n'
                 'reels_lines appear on the video over product photos: emotional benefits, no prices, '
                 'no invented technical specs.\n'
                 'carousel_lines are written on swipeable carousel slides over product photos (one line per slide): '
                 'emotional benefits or styling ideas, no prices, no invented sizes/materials/specs. '
                 'carousel_points appear on the last slide next to the price: only things that are surely true '
                 f'(e.g. {", ".join(musteri.carousel_maddeleri())}) - no invented specs, '
                 'no delivery or warranty promises.')
        from . import analiz, kurallar
        istem += "\n" + analiz.istem_ozeti() + kurallar.istem("metin")
        if geri_bildirim:
            istem += "\n\nFix these issues (from quality control or the business owner):\n- " + "\n- ".join(geri_bildirim)
        cevap = taslak_duzelt(self.dusun(istem, json_mod=True))
        if not cevap or "caption" not in cevap:
            cevap = self._sablon(urun)
        cevap["hashtags"] = [("#" + h.lstrip("#")).replace(" ", "") for h in cevap.get("hashtags", [])][:15]
        self.soyle("KaliteKontrol", f"Kanca: \"{cevap.get('hook', '')}\" — taslak hazir, kontrol eder misin?")
        pano.durum(self.ad, "bekliyor", "Kalite kontrolu bekliyorum...")
        return cevap

    def _fikir_yaz(self, urun, aci, geri_bildirim=None):
        """Urunsuz icerik (ipucu, hikaye, sektor bilgisi, davet): fiyat YOK, uydurma bilgi YOK."""
        from . import analiz
        istem = (f"Post topic: {urun['ad']}\nContent pillar: {urun.get('kategori', '')}\n"
                 f"What it should say: {urun.get('aciklama', '')}\nAngle: {aci}\n"
                 f"Call to action: {AYAR['marka']['cta']}\n{analiz.istem_ozeti()}\n"
                 "Write like a skilled local social media manager: specific, human, useful. Speak to the "
                 "business's customers about their real problem, then show how this business helps. One idea per "
                 "post. No generic filler ('in today's fast-paced world'), no hashtags inside the caption body.\n"
                 'Return JSON: {"hook": "<max 7 words, scroll-stopping>", '
                 '"headline": "<max 9 words for the image>", '
                 '"caption": "<3-6 short lines that give real value (tip, insight, story or invitation), end with the '
                 'call to action. NO prices, NO invented facts, numbers, awards or customer names>", '
                 f'"hashtags": ["<8-12 hashtags: niche + local {musteri.sehirler_metni()}>"], '
                 '"reels_lines": ["<line 1, max 6 words>", "<line 2, max 6 words>"], '
                 '"carousel_lines": ["<4 slide lines, max 7 words each: a mini guide or story>"], '
                 '"carousel_points": ["<3 short takeaways, max 5 words each>"], '
                 '"pov": "<POV line, max 10 words, starts with POV:>"}')
        from . import kurallar
        istem += kurallar.istem("metin")
        if geri_bildirim:
            istem += "\n\nFix these issues:\n- " + "\n- ".join(geri_bildirim)
        cevap = taslak_duzelt(self.dusun(istem, json_mod=True))
        if not cevap or "caption" not in cevap:
            cevap = {"hook": urun["ad"][:50], "headline": urun["ad"][:60],
                     "caption": f"{urun['ad']}.\n{urun.get('aciklama', '')}\n\n{AYAR['marka']['cta']}.",
                     "hashtags": musteri.hashtagler(), "reels_lines": [urun["ad"][:40], musteri.ad()],
                     "carousel_lines": [urun["ad"][:50]], "carousel_points": musteri.carousel_maddeleri(),
                     "pov": f"POV: you found {musteri.ad()}"}
        cevap["hashtags"] = [("#" + h.lstrip("#")).replace(" ", "") for h in cevap.get("hashtags", [])][:15]
        self.soyle("KaliteKontrol", f"Icerik metni: \"{cevap.get('hook', '')}\" — kontrol eder misin?")
        pano.durum(self.ad, "bekliyor", "Kalite kontrolu bekliyorum...")
        return cevap

    def _proje_yaz(self, urun, aci, geri_bildirim=None):
        """Tamamlanan proje: fiyat YOK, gercek is oldugu vurgulanir, musteri bilgisi verilmez."""
        istem = (f"Completed project by {musteri.ad()}: {urun['ad']}\n"
                 f"Location: {urun.get('konum') or musteri.bilgi()['ulke'] or '-'}\nNotes from the team: {urun.get('aciklama') or '-'}\n"
                 f"Angle: {aci}\nCall to action: {AYAR['marka']['cta']}\n\n"
                 'Return JSON: {"hook": "<max 7 words, scroll-stopping, e.g. about the transformation>", '
                 '"headline": "<max 9 words, inspiring line about this real project>", '
                 '"caption": "<3-5 short lines: what we created, the feeling of the space, invite them to plan their own '
                 'project with us; end with the call to action. NO prices>", '
                 f'"hashtags": ["<8-12 hashtags, local {musteri.sehirler_metni()} tags for this kind of project>"], '
                 '"reels_lines": ["<line 1, max 6 words>", "<line 2, max 6 words>"], '
                 '"carousel_lines": ["<6 short lines, max 7 words each, one per photo: details, materials, mood>"], '
                 f'"carousel_points": ["<3 points, max 5 words each, e.g. {" / ".join(musteri.carousel_maddeleri(proje=True))}>"], '
                 '"pov": "<POV line, max 10 words, starts with POV:>"}\n'
                 "Do not invent client names, prices, sizes, delivery or warranty promises.")
        from . import kurallar
        istem += kurallar.istem("metin")
        if geri_bildirim:
            istem += "\n\nFix these issues:\n- " + "\n- ".join(geri_bildirim)
        cevap = self.dusun(istem, json_mod=True)
        if not cevap or "caption" not in cevap:
            yer = f" in {urun['konum']}" if urun.get("konum") else ""
            cevap = {"hook": "From plan to a finished home", "headline": "A real home we brought to life",
                     "caption": (f"Our latest completed project{yer}: {urun['ad']}.\nDesigned and furnished by our team.\n"
                                 f"Planning your own space? {AYAR['marka']['cta']}."),
                     "hashtags": musteri.hashtagler(proje=True),
                     "reels_lines": ["Designed for real family life", "Every detail, made to fit"],
                     "carousel_lines": ["Every detail planned for this home", "Warm materials, calm lines",
                                        "Made to fit the space", "Light that changes the mood", "Storage that stays hidden",
                                        "A room the family loves"],
                     "carousel_points": musteri.carousel_maddeleri(proje=True),
                     "pov": "POV: your dream room finally became real"}
        cevap["hashtags"] = [("#" + h.lstrip("#")).replace(" ", "") for h in cevap.get("hashtags", [])][:15]
        self.soyle("KaliteKontrol", f"Proje metni: \"{cevap.get('hook', '')}\" — kontrol eder misin?")
        pano.durum(self.ad, "bekliyor", "Kalite kontrolu bekliyorum...")
        return cevap

    def _sablon(self, u):
        return {
            "hook": "Your living space deserves this",
            "headline": "Comfort that feels like home",
            "caption": (f"Meet the {u['ad']}.\nDesigned for comfort, built to last.\n"
                        f"Now {u['fiyat_metni']}.\n{AYAR['marka']['cta']}."),
            "hashtags": musteri.hashtagler(),
            "reels_lines": ["Timeless design for your home", "Comfort for the whole family"],
            "carousel_lines": ["Timeless design for your home", "Comfort for the whole family", "Made for everyday living"],
            "carousel_points": musteri.carousel_maddeleri(),
            "pov": "POV: you finally found the piece your room was missing",
        }


# ------------------------------------------------------------------
class KaliteKontrol(Ajan):
    ad, unvan, emoji = "KaliteKontrol", "Kalite Kontrol", "🔍"
    sistem = (f"You are a strict but fair brand quality reviewer for {musteri.tanim()}. "
              "Answer ONLY with valid JSON.")

    def kontrol(self, urun, taslak):
        self.calis("Taslagi inceliyorum...")
        notlar = []
        # 1) Kural tabanli kontroller (kod) - kesin
        metin = taslak.get("caption", "")
        bulunan = re.findall(fiyat.fiyat_deseni(), metin)
        dogru = f"{urun['ngn']:,.0f}" if urun.get("ngn") else None
        if dogru and dogru not in metin.replace(" ", ""):
            notlar.append(f"The caption must include the exact price {urun['fiyat_metni']}.")
        for b in bulunan:
            if dogru and b.strip(",") != dogru:
                notlar.append(f"Wrong price '{b}' found. Only use {urun['fiyat_metni']}.")
        for satir in taslak.get("reels_lines", [])[:2]:
            if len(str(satir).split()) > 8:
                notlar.append(f"Reels line too long: '{satir}'. Keep each reels line max 6 words.")
        for satir in (taslak.get("carousel_lines") or [])[:3]:
            if len(str(satir).split()) > 9:
                notlar.append(f"Carousel line too long: '{satir}'. Keep each carousel line max 7 words.")
        for satir in (taslak.get("carousel_points") or [])[:3]:
            if len(str(satir).split()) > 7:
                notlar.append(f"Carousel point too long: '{satir}'. Keep each point max 5 words.")
            if re.search(r"\d|deliver|warrant|guarantee|free ", str(satir).lower()):
                notlar.append(f"Carousel point '{satir}' makes a promise/number we cannot verify. Use a safe benefit instead.")
        if len(taslak.get("hook", "").split()) > 8:
            notlar.append("Hook is too long, keep it max 7 words.")
        if len(str(taslak.get("pov", "")).split()) > 12:
            notlar.append("POV line is too long, keep it max 10 words.")
        if taslak.get("headline", "").strip().lower() == urun["ad"].strip().lower():
            notlar.append("Headline must not repeat the product name; write an emotional benefit line instead.")
        if len(taslak.get("headline", "").split()) > 10:
            notlar.append("Headline is too long, keep it max 9 words.")
        if not 5 <= len(taslak.get("hashtags", [])) <= 15:
            notlar.append("Use 8-12 hashtags.")
        for y in YASAKLI:
            if y in metin.lower():
                notlar.append(f"Remove '{y}': {musteri.satis_kanali()}")
        if urun.get("fikir"):
            from . import marka_ozeti
            from . import yuklemeler
            gercek = " ".join((marka_ozeti.ozet().get("kanitlanmis_bilgiler") or [])
                              + yuklemeler.belge_gercekleri()).lower()
            butun = " ".join([metin, str(taslak.get("hook", "")), str(taslak.get("headline", ""))]
                             + [str(x) for x in (taslak.get("reels_lines") or []) + (taslak.get("carousel_lines") or [])])
            for sayi in re.findall(r"\d[\d,.]*\s*(?:%|x\b|percent|followers|clients|customers|sales|likes|"
                                   r"views|years|k\b)", butun.lower()):
                if sayi.split()[0].rstrip("%x") not in gercek:
                    notlar.append(f"'{sayi}' is an invented number/result. Remove it or make the example clearly "
                                  "hypothetical; never claim results we cannot prove.")
            if re.search(r"customer spotlight|case study|testimonial|our client\b", butun.lower()):
                notlar.append("Do not present an invented customer story or case study as real.")
        from . import kurallar
        tum_metin = " ".join([metin, taslak.get("hook", ""), taslak.get("headline", "")]
                             + [str(x) for x in taslak.get("reels_lines") or []] + [str(taslak.get("pov", ""))]
                             + [str(x) for x in (taslak.get("carousel_lines") or []) + (taslak.get("carousel_points") or [])])
        for k in kurallar.yasak_kelime_bul(tum_metin):
            notlar.append(f"The business owner banned the word '{k}'. Remove it everywhere.")
        # 2) LLM ile marka dili kontrolu - yorumsal
        if not notlar:
            cevap = self.dusun(
                f"Product/topic: {urun['ad']}\nDraft:\n{taslak}\n{kurallar.istem('metin')}\n"
                f"{__import__('ofis.marka_ozeti', fromlist=['x']).istem_ozeti()}"
                "Also reject any claim, number, customer story or result that is not in BUSINESS FACTS.\n"
                f"{__import__('ofis.dil', fromlist=['x']).talimat()}Reject the draft if it is not written in that language.\n"
                "Check: is it clear, warm, premium, free of spelling mistakes, does it follow the brand rules above "
                "(if any), and does it avoid exaggerated or "
                "false claims (like 'best in the country', 'free delivery', discounts that were not given)? "
                'Return JSON: {"approved": true/false, "issues": ["<short fix instructions in English>"]}',
                json_mod=True, sicaklik=0.2)
            if cevap and not cevap.get("approved", True):
                notlar += [str(n) for n in cevap.get("issues", [])][:3]
        if notlar:
            self.soyle("MetinYazari", "Duzeltme lazim: " + " | ".join(notlar), "revizyon")
            pano.durum(self.ad, "bekliyor", "Duzeltilmis taslagi bekliyorum...")
            return False, notlar
        self.soyle("Tasarimci", "Metin onaylandi ✅ Gorsellere gecebiliriz.")
        self.bitir("Onayladim ✅")
        return True, []


# ------------------------------------------------------------------
class Tasarimci(Ajan):
    ad, unvan, emoji = "Tasarimci", "Grafik Tasarimci", "🎨"

    def ciz(self, urun, gorsel_yollari, gorseller, taslak, klasor, yon="B", dikey=None, tur=None):
        """tur: post -> post+story | carousel -> kapak+kartlar | reels -> sadece kapak (onizleme) | None -> hepsi"""
        from . import gorsel
        tarif = yon if isinstance(yon, dict) else None
        # 1) Markanin tasarim sistemi (guclu modelle kurulan, markaya ozel duzenler) -> hizli ve tutarli
        u = None
        try:
            from . import marka_tasarim
            if marka_tasarim.eski_mi() and llm.hazir():
                self.calis("Markana ozel tasarim sistemini kuruyorum (iki haftada bir yenilenir, birkac dakika)...")
                marka_tasarim.kur(urun, gorsel_yollari, taslak, lambda m: (print(f"[TASARIM] {m}", flush=True),
                                                                          pano.durum(self.ad, "calisiyor", m)))
            u = marka_tasarim.ciz_set(urun, gorsel_yollari, taslak, klasor, tur,
                                      lambda m: (print(f"[TASARIM] {m}", flush=True), pano.durum(self.ad, "calisiyor", m)))
        except Exception as e:
            u = None
            print(f"[TASARIM] tasarim sistemi calismadi: {type(e).__name__}: {str(e)[:160]}", flush=True)
        # 2) Tutmazsa uretken tasarim (her tuval sifirdan); o da tutmazsa sablon yolu devralir
        try:
            if u:
                raise StopIteration
            from . import uretken
            self.calis("Bugunun gorsel dilini seciyorum ve tasarimi sifirdan ciziyorum...")
            def sablon_ciz(hedef):
                from . import tasarim
                tasarim.ciz("dinamik.html" if tarif else SanatYonetmeni.YONLER.get(yon, SanatYonetmeni.YONLER["B"])[0],
                            tasarim.veri_hazirla(urun, gorsel_yollari, taslak, tarif), hedef)
            u = uretken.tasarla(urun, gorsel_yollari, taslak, klasor, tur,
                                lambda m: (print(f"[TASARIM] {m}", flush=True), pano.durum(self.ad, "calisiyor", m)),
                                sablon_ciz=sablon_ciz)
        except StopIteration:
            pass
        except Exception as e:
            u = None
            self.soyle("Yonetici", f"Uretken tasarim calismadi ({type(e).__name__}: {str(e)[:120]}), sablonla devam.", "uyari")
        if u:
            d = u["dil"]
            if tarif is not None:       # ogrenme ve Reels ayni gorsel dili kullansin
                # 'duzen' sablon motorunun anahtari olarak kalir (Reels onu kullanir); stil ayri tutulur
                tarif.update({"isim": f"{d['stil']} #{random.randint(100, 999)}", "uretken_stil": d["stil"],
                              "uretken_dil": d,
                              "fontlar": d["font"], "neden": d.get("neden") or d.get("fikir"),
                              "palet": {"zemin": d["palet"]["bg"], "vurgu": d["palet"]["accent"], "panel": d["palet"]["bg"]}})
            self.soyle("SanatYonetmeni", f"Yeni gorsel dil: '{d['stil']}' — {d['fikir']}")
            try:
                from . import tasarim
                if tur in (None, "post") and not (klasor / "story_1080x1920.jpg").exists() and tarif:
                    tasarim.ciz("dinamik.html", tasarim.veri_hazirla(urun, (dikey or [])[:1] + list(gorsel_yollari[1:]) if dikey else gorsel_yollari, taslak, tarif),
                                klasor / "story_1080x1920.jpg", (1080, 1920))
                if tur in (None, "carousel") and u.get("carousel_eksik"):
                    from . import carousel
                    carousel.uret(urun, gorsel_yollari, taslak, tarif, klasor, lambda m: pano.durum(self.ad, "calisiyor", m))
                tasarim.kapat()
            except Exception as e:
                self.soyle("Yonetici", f"Ek tuvaller cizilemedi ({type(e).__name__}: {e}).", "uyari")
            self.soyle("VideoEditoru" if tur in (None, "reels") else "Yonetici",
                       {"post": "Post ve story hazir.", "carousel": "Carousel kartlari hazir.",
                        "reels": "Kapak hazir, Reels'e gecebilirsin."}.get(tur, "Tasarimlar hazir."))
            self.bitir()
            return
        sablon = "dinamik.html" if tarif else SanatYonetmeni.YONLER.get(yon, SanatYonetmeni.YONLER["B"])[0]
        self.calis(f"'{tarif['isim'] if tarif else yon}' sablonuyla post ve story ciziyorum...")
        try:
            from . import tasarim
            v = tasarim.veri_hazirla(urun, gorsel_yollari, taslak, tarif)
            tasarim.ciz(sablon, v, klasor / "post_1080x1350.jpg")
            if tur in (None, "post"):
                if dikey:  # AI ile tamamlanmis dikey foto varsa story'de onu kullan
                    v = tasarim.veri_hazirla(urun, [dikey[0]] + list(gorsel_yollari[1:]), taslak, tarif)
                tasarim.ciz(sablon, v, klasor / "story_1080x1920.jpg", (1080, 1920))
            if tur in (None, "carousel"):
                try:
                    from . import carousel
                    self.calis("Carousel kartlarini ciziyorum...")
                    kartlar = carousel.uret(urun, gorsel_yollari, taslak, tarif, klasor,
                                            lambda m: pano.durum(self.ad, "calisiyor", m))
                    self.soyle("Yonetici", f"Carousel hazir: {len(kartlar)} kart (kapak + detaylar + fiyat/CTA).")
                except Exception as e:
                    self.soyle("Yonetici", f"Carousel cizilemedi ({type(e).__name__}: {e}); tek gorselli post kullanilacak.", "uyari")
            tasarim.kapat()
        except Exception as e:  # Playwright yoksa eski cizime dus
            self.soyle("Yonetici", f"HTML tasarim motoru calismadi ({type(e).__name__}: {e}), basit cizimle devam.", "uyari")
            kategori = urun.get("kategori", "").split(">")[-1].strip()[:40]
            gorsel.post_ciz(gorseller[0], urun["ad"], kategori, urun["fiyat_metni"],
                            taslak.get("headline", ""), klasor / "post_1080x1350.jpg")
            gorsel.story_ciz(gorseller[0], urun["ad"], urun["fiyat_metni"],
                             taslak.get("hook", ""), klasor / "story_1080x1920.jpg")
        self.soyle("VideoEditoru" if tur in (None, "reels") else "Yonetici",
                   {"post": "Post ve story hazir.", "carousel": "Carousel kartlari hazir.",
                    "reels": "Kapak hazir, Reels'e gecebilirsin."}.get(tur, "Post ve story hazir. Ayni gorsellerle Reels'e gecebilirsin."))
        self.bitir()


# ------------------------------------------------------------------
class VideoEditoru(Ajan):
    ad, unvan, emoji = "VideoEditoru", "Video Editoru", "🎬"

    def kurgula(self, urun, gorseller, taslak, klasor, gorsel_yollari=None, tarif=None, dikey=None,
                muzik_id=None, muzik_haric=None, reels_format=None):
        from . import gorsel, reels_formatlari
        hedef = klasor / "reels_1080x1920.mp4"
        foto_sayisi = len({str(g) for g in (gorsel_yollari or [])})
        bicim = reels_formatlari.sec(foto_sayisi, reels_format,
                                     haric=["luks", "fiyat_tahmini"] if urun.get("proje") or not urun.get("fiyat_metni") else None)
        from . import muzik
        if muzik.ayar("otomatik", True):
            try:
                self.calis("Muzik kutuphanesini kontrol ediyorum (sadece CC0 / CC BY, ticari kullanima acik)...")
                yeni = muzik.guncelle(gunluk=lambda m: pano.durum(self.ad, "calisiyor", m))
                if yeni:
                    self.soyle("Yonetici", f"Muzik kutuphanesine {yeni} yeni telifsiz parca ekledim (lisanslar kayitli).")
            except Exception as e:
                self.soyle("Yonetici", f"Muzik kutuphanesi guncellenemedi ({type(e).__name__}), mevcut parcalarla devam.", "uyari")
        son_kart = None
        try:
            from . import marka_tasarim
            self.calis("Kapanis kartini (logo + CTA) markanin tasarim sistemiyle hazirliyorum...")
            son_kart = marka_tasarim.son_kart(gorsel_yollari or [], klasor / "_reels_son.jpg",
                                              lambda m: (print(f"[TASARIM] {m}", flush=True), pano.durum(self.ad, "calisiyor", m)))
        except Exception as e:
                self.soyle("Yonetici", f"Kapanis karti tasarlanamadi ({type(e).__name__}), sablon kapanisi kullanilacak.", "uyari")
        self.calis(f"Bugunun Reels formati: {reels_formatlari.FORMATLAR[bicim]}. Kurguluyorum (yaklasik 1 dakika)...")
        try:
            from . import reklam
            try:
                reklam.reklam_yap(urun, gorsel_yollari or [], taslak, tarif if isinstance(tarif, dict) else None, hedef,
                                  lambda m: pano.durum(self.ad, "calisiyor", m), dikey_yollari=dikey,
                                  muzik_id=muzik_id, muzik_haric=muzik_haric, format_adi=bicim, son_kart=son_kart)
            except Exception as e:
                if bicim == "luks" or urun.get("proje") or not urun.get("fiyat_metni"):
                    raise
                self.soyle("Yonetici", f"'{bicim}' formati calismadi ({type(e).__name__}: {e}), lüks kurguya geciyorum.", "uyari")
                bicim = "luks"
                reklam.reklam_yap(urun, gorsel_yollari or [], taslak, tarif if isinstance(tarif, dict) else None, hedef,
                                  lambda m: pano.durum(self.ad, "calisiyor", m), dikey_yollari=dikey,
                                  muzik_id=muzik_id, muzik_haric=muzik_haric, format_adi="luks", son_kart=son_kart)
            tur = f"'{reels_formatlari.FORMATLAR[bicim]}' formati"
            if son_kart:
                tur += ", kapanis karti icerige ozel"
                Path(son_kart).unlink(missing_ok=True)
        except Exception as e:
            self.soyle("Yonetici", f"Reklam motoru calismadi ({type(e).__name__}: {e}), basit Reels'e geciyorum.", "uyari")
            try:
                gorsel.reels_yap(gorseller, urun["ad"], urun["fiyat_metni"], taslak.get("hook", ""), hedef,
                                 eski_fiyat_metni=urun.get("eski_fiyat_metni", ""))
                tur = "basit kurgu"
            except Exception as e2:
                self.soyle("Yonetici", f"Reels olusturulamadi ({type(e2).__name__}: {e2})", "hata")
                pano.durum(self.ad, "hata", "Reels olusturulamadi")
                return
        bilgi = klasor / "muzik.json"
        if bilgi.exists():
            import json as _j
            m = _j.loads(bilgi.read_text(encoding="utf-8"))
            ses = f"muzik: \"{m.get('baslik')}\" - {m.get('sanatci') or '?'} ({str(m.get('lisans')).upper()}, {m.get('ruh')})"
        else:
            ses = "muziksiz (basit kurgu muzik eklemez)" if tur == "basit kurgu" else "muziksiz (uygun parca bulunamadi)"
        self.soyle("Yonetici", f"Reels hazir 🎬 15 sn {tur}, {ses}.")
        self.bitir()


class Rotuscu(Ajan):
    ad, unvan, emoji = "Rotuscu", "Rotuscu (AI)", "🖌️"

    def hazirla(self, urun, gorsel_yollari):
        """Doner: (netlestirilmis_yollar, dikey_yollar veya [])"""
        from . import ai_gorsel, algila, marka, rotus_bulut
        if urun.get("fikir"):
            self.bitir("Stok / yapay zeka gorselleri zaten hazir")
            return list(gorsel_yollari), []
        hazir, aciklama = ai_gorsel.durum()
        if not hazir and rotus_bulut.hazir():
            return self._bulut(urun, gorsel_yollari)
        if not hazir:
            self.soyle("Yonetici", f"AI rotus atlandi: {aciklama}. Orijinal fotograflarla devam.", "uyari")
            self.bitir("AI kapali")
            return list(gorsel_yollari), []
        self.calis(f"Ekran karti hazir ({aciklama}). Fotograflari inceliyorum...")
        net, dikey = [], []
        adet = int(ai_gorsel.ayar("dikey_adet", 3))
        for i, y in enumerate(gorsel_yollari[:3]):
            try:
                if ai_gorsel.ayar("netlestir", True):
                    self.calis(f"Fotograf {i + 1}: netlik kontrolu...")
                    y2 = ai_gorsel.netlestir(y)
                    if y2 != y:
                        self.soyle("Tasarimci", f"Fotograf {i + 1} kucuktu, AI ile 4x buyutup netlestirdim.")
                    y = y2
            except Exception as e:
                self.soyle("Yonetici", f"Netlestirme hatasi ({type(e).__name__}: {e})", "uyari")
            net.append(y)
            if ai_gorsel.ayar("genislet", True) and i < adet:
                try:
                    self.calis(f"Fotograf {i + 1}: ust/alt kismi AI ile tamamliyorum (urune dokunmadan, ~1 dk)...")
                    kaynak = marka.gorsel_hazirla(Path(y))
                    d = ai_gorsel.dikey_genislet(kaynak, algila.urun_kutusu(kaynak), urun.get("kategori", ""))
                    if d != kaynak:
                        dikey.append(d)
                except Exception as e:
                    self.soyle("Yonetici", f"Genisletme hatasi ({type(e).__name__}: {e}), kirpma ile devam.", "uyari")
        ai_gorsel.bosalt()
        if dikey:
            self.soyle("VideoEditoru", f"{len(dikey)} fotografi dikey 9:16'ya tamamladim; Reels ve story'de kirpma yok.")
        self.bitir()
        return net, dikey


    def _bulut(self, urun, gorsel_yollari):
        """GPU yok: netlestirme yerelde, dikeye tamamlama bulut yapay zekasiyla (urun alani korunur)."""
        from . import rotus_bulut
        self.calis("Bulut rotus: fotograflari netlestiriyor, dikey formata tamamliyorum...")
        net, dikey = [], []
        for i, y in enumerate(gorsel_yollari[:3]):
            try:
                y2 = rotus_bulut.netlestir(y)
                if y2 != y:
                    self.soyle("Tasarimci", f"Fotograf {i + 1} kucuktu, buyutup netlestirdim.")
                y = y2
            except Exception as e:
                self.soyle("Yonetici", f"Netlestirme hatasi ({type(e).__name__}: {e})", "uyari")
            net.append(y)
            if i < 2:
                d = rotus_bulut.dikey_genislet(y, ipucu=urun.get("kategori", ""))
                if d:
                    dikey.append(d)
        if dikey:
            self.soyle("VideoEditoru", f"{len(dikey)} fotografi bulut yapay zekasiyla dikey 9:16'ya tamamladim (urune dokunmadan).")
        self.bitir()
        return net, dikey


class PerformansAnalisti(Ajan):
    ad, unvan, emoji = "PerformansAnalisti", "Performans Analisti", "📊"
    sistem = (f"You are a social media performance analyst for {musteri.tanim()}. "
              "Write in clear, friendly Turkish.")

    def analiz(self):
        from . import analiz
        from .ayarlar import KOK, VERI, MUZIK
        self.calis("Puanlari ve rakamlari inceliyorum...")
        o = analiz.analiz_et()
        if not o.get("n"):
            self.soyle("Herkes", "Henuz puanlanmis icerik yok. Ofis ekranindaki Performans sekmesinden "
                       "post/story/Reels'e yildiz verin, ben de ogrenmeye baslayayim.")
            self.bitir("Veri bekliyorum")
            return o
        tr = lambda s: f"{analiz.ADLAR.get(s['alan'], s['alan'])}: {s['deger']} ({s['ort']}/5, {s['n']} icerik)"
        satirlar = [f"- Puanlanan icerik: {o['n']}, genel ortalama {o.get('genel_ort')}/5"
                    + (f", Reels ortalamasi {o['reels_ort']}/5" if o.get("reels_ort") else ""),
                    "- Iyi gidenler: " + ("; ".join(tr(s) for s in o["tercih"]) or "henuz belirgin degil"),
                    "- Zayif kalanlar: " + ("; ".join(tr(s) for s in o["kacin"]) or "henuz belirgin degil")]
        if o.get("en_iyi"):
            satirlar.append(f"- En iyi: {o['en_iyi']['urun']} ({o['en_iyi']['tarif']}, {o['en_iyi']['skor']}/5)")
        yorum = self.dusun("Here are our Instagram content performance findings:\n" + "\n".join(satirlar) +
                           "\n\nWrite a short Turkish summary (max 5 sentences) with 2-3 concrete recommendations "
                           "for next week's designs and products. If fewer than 6 posts are rated, say the "
                           "findings are still early.")
        rapor = "# Performans raporu — " + o["tarih"] + "\n\n" + "\n".join(satirlar) + "\n\n" + (yorum or "")
        (VERI / "analiz_raporu.md").write_text(rapor, encoding="utf-8")
        self.soyle("SanatYonetmeni", "Ogrenimler guncellendi: " + ("; ".join(tr(s) for s in o["tercih"][:3]) or "-"))
        self.soyle("PazarlamaUzmani", (yorum or "Rapor hazir.")[:220], "rapor")
        self.bitir("Rapor hazir 📊")
        return o


class SosyalMedya(Ajan):
    ad, unvan, emoji = "SosyalMedya", "Sosyal Medya Sorumlusu", "📱"


class IletisimAnalisti(Ajan):
    """Yorumlari ve DM'leri OKUR ve raporlar. Kimseye cevap yazmaz (bu is satis ekibinde ve Meta Business Agent'ta)."""
    ad, unvan, emoji = "IletisimAnalisti", "Iletisim Analisti", "💬"
    sistem = (f"You analyse customer comments and direct messages of {musteri.tanim()}. "
              "Write in short, clear Turkish. Never write replies to customers.")

    def rapor(self):
        from . import iletisim
        self.calis("Yorumlari ve mesajlari okuyorum (cevap yazmiyorum, sadece raporluyorum)...")
        try:
            r = iletisim.topla(gunluk=lambda m: pano.durum(self.ad, "calisiyor", m))
        except Exception as e:
            self.soyle("Yonetici", f"Iletisim raporu alinamadi: {type(e).__name__}: {e}", "uyari")
            self.bitir("Rapor alinamadi")
            return None
        satirlar = iletisim.ozet_satirlari(r)
        self.soyle("Yonetici", " ".join(satirlar)[:600], "rapor")
        if r.get("urun_ilgisi"):
            self.soyle("UrunSorumlusu", "Musterilerin en cok sordugu urunler: "
                       + ", ".join(f"{u} ({n})" for u, n in r["urun_ilgisi"][:5]) + ". Planlarken dikkate al.")
        if (r.get("konular") or {}).get("fiyat"):
            self.soyle("MetinYazari", f"Yorum ve mesajlarda {r['konular']['fiyat']} fiyat sorusu var; fiyati gorselde ve "
                       "metnin ilk satirinda net yazmaya devam.")
        self.bitir("Iletisim raporu hazir 💬")
        return r


def tum_ekip():
    siniflar = [Yonetici, UrunSorumlusu, PazarlamaUzmani, MetinYazari, KaliteKontrol, Tasarimci, VideoEditoru,
                SanatYonetmeni, Rotuscu, PerformansAnalisti, SosyalMedya, IletisimAnalisti]
    return {s.ad: s(i) for i, s in enumerate(siniflar)}


def bugunun_temasi():
    from . import musteri, sektor
    temalar = AYAR.get("haftalik_tema") or {}
    if temalar and temalar != musteri.sablon().get("haftalik_tema"):
        return temalar.get(date.today().strftime("%A"), "Behind the scenes")
    sutunlar = sektor.profil().get("sutunlar") or ["Behind the scenes"]
    return sutunlar[date.today().toordinal() % len(sutunlar)]
