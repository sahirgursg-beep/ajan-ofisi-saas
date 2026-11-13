"""Isletme sahiplerine kisa e-postalar (Resend API). Anahtar yoksa hicbir sey gonderilmez, sistem calismaya devam eder.

* Haftalik ozet (pazartesi sabahi, isletmenin saatiyle): gecen hafta ne paylasildi, bu hafta ne hazir, bakmasi
  gereken bir sey var mi. Tek tus: paneli ac.
* Deneme bitiyor (son 2 gun): ne olacagini sade anlatir.
Ortam: RESEND_API_KEY (DigitalOcean'da sifreli), SAAS_EPOSTA_GONDEREN (or. "FeedZync <hello@feedzync.com>").
Gonderilenler depoda {mid}/eposta.json'da tutulur: ayni hafta/ayni deneme icin ikinci kez gonderilmez.
"""
import html
import os
from datetime import datetime, timedelta, timezone

import requests

from . import ayar
from .depo import depo

API = "https://api.resend.com/emails"

METIN = {
    "en": {"ozet_konu": "Your week on social media", "ozet_bas": "Here is your week, {ad}.",
           "gecen": "Posted last week", "hazir": "Ready for this week", "bak": "Need a quick look", "ac": "Open FeedZync",
           "deneme_konu": "Your free trial ends in {n} days", "deneme_bas": "Your FeedZync trial for {ad} ends in {n} days.",
           "deneme_alt": "Keep your office running: choose a plan in the app. If you do nothing, posting simply pauses — nothing is deleted.",
           "dipnot": "You get this email because you own {ad} on FeedZync."},
    "tr": {"ozet_konu": "Sosyal medyada haftanız", "ozet_bas": "{ad}, haftanızın özeti burada.",
           "gecen": "Geçen hafta paylaşılan", "hazir": "Bu hafta için hazır", "bak": "Kısa bakış gereken", "ac": "FeedZync'i aç",
           "deneme_konu": "Ücretsiz denemeniz {n} gün sonra bitiyor", "deneme_bas": "{ad} için FeedZync denemeniz {n} gün sonra bitiyor.",
           "deneme_alt": "Ofisiniz çalışmaya devam etsin: uygulamadan bir paket seçin. Hiçbir şey yapmazsanız paylaşım durur, hiçbir şey silinmez.",
           "dipnot": "Bu e-postayı FeedZync'te {ad} hesabının sahibi olduğunuz için alıyorsunuz."},
    "fr": {"ozet_konu": "Votre semaine sur les réseaux", "ozet_bas": "Voici votre semaine, {ad}.",
           "gecen": "Publiés la semaine dernière", "hazir": "Prêts pour cette semaine", "bak": "À vérifier rapidement", "ac": "Ouvrir FeedZync",
           "deneme_konu": "Votre essai gratuit se termine dans {n} jours", "deneme_bas": "Votre essai FeedZync pour {ad} se termine dans {n} jours.",
           "deneme_alt": "Gardez votre bureau actif : choisissez une formule dans l'appli. Sinon, la publication se met en pause — rien n'est supprimé.",
           "dipnot": "Vous recevez cet e-mail car vous êtes propriétaire de {ad} sur FeedZync."},
    "es": {"ozet_konu": "Tu semana en redes", "ozet_bas": "Aquí está tu semana, {ad}.",
           "gecen": "Publicado la semana pasada", "hazir": "Listo para esta semana", "bak": "Necesitan una revisión", "ac": "Abrir FeedZync",
           "deneme_konu": "Tu prueba gratis termina en {n} días", "deneme_bas": "Tu prueba de FeedZync para {ad} termina en {n} días.",
           "deneme_alt": "Mantén tu oficina en marcha: elige un plan en la app. Si no haces nada, la publicación se pausa; no se borra nada.",
           "dipnot": "Recibes este correo porque eres el propietario de {ad} en FeedZync."},
    "pt": {"ozet_konu": "Sua semana nas redes", "ozet_bas": "Aqui está sua semana, {ad}.",
           "gecen": "Publicados na semana passada", "hazir": "Prontos para esta semana", "bak": "Precisam de uma olhada", "ac": "Abrir FeedZync",
           "deneme_konu": "Seu teste grátis termina em {n} dias", "deneme_bas": "Seu teste do FeedZync para {ad} termina em {n} dias.",
           "deneme_alt": "Mantenha seu escritório funcionando: escolha um plano no app. Se não fizer nada, as publicações pausam — nada é apagado.",
           "dipnot": "Você recebe este e-mail porque é o dono de {ad} no FeedZync."},
    "de": {"ozet_konu": "Deine Woche auf Social Media", "ozet_bas": "Hier ist deine Woche, {ad}.",
           "gecen": "Letzte Woche gepostet", "hazir": "Fertig für diese Woche", "bak": "Kurz prüfen", "ac": "FeedZync öffnen",
           "deneme_konu": "Dein kostenloser Test endet in {n} Tagen", "deneme_bas": "Dein FeedZync-Test für {ad} endet in {n} Tagen.",
           "deneme_alt": "Damit dein Büro weiterläuft: wähle in der App einen Tarif. Tust du nichts, pausiert das Posten — nichts wird gelöscht.",
           "dipnot": "Du erhältst diese E-Mail, weil dir {ad} auf FeedZync gehört."},
    "ar": {"ozet_konu": "أسبوعك على السوشيال ميديا", "ozet_bas": "إليك ملخص أسبوعك يا {ad}.",
           "gecen": "نُشر الأسبوع الماضي", "hazir": "جاهز لهذا الأسبوع", "bak": "يحتاج نظرة سريعة", "ac": "افتح FeedZync",
           "deneme_konu": "تنتهي تجربتك المجانية خلال {n} أيام", "deneme_bas": "تنتهي تجربة FeedZync لـ {ad} خلال {n} أيام.",
           "deneme_alt": "ليستمر مكتبك في العمل اختر باقة من التطبيق. إن لم تفعل شيئاً يتوقف النشر فقط ولا يُحذف شيء.",
           "dipnot": "تصلك هذه الرسالة لأنك مالك {ad} على FeedZync."},
}


def hazir():
    return bool(os.environ.get("RESEND_API_KEY"))


def gonder(alicilar, konu, govde_html, http=None):
    """-> True gonderildi / False (anahtar yok ya da hata). Hata uretimi asla durdurmaz."""
    alicilar = [a for a in alicilar if a and "@" in a]
    if not hazir() or not alicilar:
        return False
    try:
        r = (http or requests).post(API, timeout=20, headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
                                    json={"from": os.environ.get("SAAS_EPOSTA_GONDEREN") or "FeedZync <hello@feedzync.com>",
                                          "to": alicilar, "subject": konu, "html": govde_html})
        return r.status_code < 300
    except Exception as e:
        print(f"e-posta gonderilemedi: {type(e).__name__}", flush=True)
        return False


def _dil(m):
    i = ((m.get("profil") or {}).get("isletme") or {})
    d = (i.get("dil") or "en").split("-")[0]
    return d if d in METIN else "en"


def _sablon(dil, baslik, satirlar, dugme, dipnot):
    yon = "rtl" if dil == "ar" else "ltr"
    govde = "".join(f'<tr><td style="padding:10px 0;border-top:1px solid #e3e8e3">{html.escape(a)}</td>'
                    f'<td style="padding:10px 0;border-top:1px solid #e3e8e3;text-align:{"left" if yon == "rtl" else "right"};font-weight:600">{html.escape(str(b))}</td></tr>'
                    for a, b in satirlar)
    return (f'<div dir="{yon}" style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto;color:#1B3B2E">'
            f'<p style="font-size:20px;font-weight:600;margin:24px 0 16px">{html.escape(baslik)}</p>'
            + (f'<table style="width:100%;border-collapse:collapse;font-size:15px">{govde}</table>' if satirlar else "")
            + f'<p style="margin:24px 0"><a href="{html.escape(ayar.GENEL_ADRES)}/" style="background:#127F56;color:#fff;'
            f'padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:600">{html.escape(dugme)}</a></p>'
            f'<p style="font-size:12px;color:#5F6E66">{html.escape(dipnot)}</p></div>')


def _sahipler(d, mid):
    return [u.get("eposta") for u in d.uyeler(mid) if u.get("rol") == "sahip" and u.get("eposta")]


def haftalik_ozet(d, m, simdi):
    t = METIN[_dil(m)]
    ad = m.get("ad") or m["id"]
    icerik = d.icerikler(m["id"], 60)
    gecen_bas = (simdi - timedelta(days=7)).date().isoformat()
    bugun = simdi.date().isoformat()
    gun = lambda x: str((x.get("yayin") or {}).get("zaman") or x["klasor"])[:10]
    gecen = sum(1 for x in icerik if (x.get("yayin") or {}).get("durum") == "yayinlandi" and gecen_bas <= gun(x) < bugun)
    hazir_ = sum(1 for x in icerik if gun(x) >= bugun and (x.get("yayin") or {}).get("durum", "bekliyor") in ("bekliyor", "onaylandi"))
    bak = sum(1 for x in icerik if gun(x) >= bugun and (x.get("meta") or {}).get("kk_uyari")
              and (x.get("yayin") or {}).get("durum", "bekliyor") == "bekliyor")
    satirlar = [(t["gecen"], gecen), (t["hazir"], hazir_)] + ([(t["bak"], bak)] if bak else [])
    return t["ozet_konu"], _sablon(_dil(m), t["ozet_bas"].format(ad=ad), satirlar, t["ac"], t["dipnot"].format(ad=ad))


def deneme_hatirlatma(m, gun):
    t = METIN[_dil(m)]
    ad = m.get("ad") or m["id"]
    return (t["deneme_konu"].format(n=gun),
            _sablon(_dil(m), t["deneme_bas"].format(ad=ad, n=gun), [], t["ac"], t["deneme_alt"] + " " + t["dipnot"].format(ad=ad)))


def tur(d=None, an_utc=None):
    """Zamanlayicidan cagrilir (10 dakikada bir). -> {"ozet": [...], "deneme": [...]} gonderilen musteriler"""
    rapor = {"ozet": [], "deneme": []}
    if not hazir():
        return rapor
    d = d or depo()
    an_utc = an_utc or datetime.now(timezone.utc)
    from .zamanlayici import _tz
    for m in d.musteriler(["deneme", "aktif"]):
        if ((m.get("profil") or {}).get("isletme") or {}).get("eposta_bildirim") is False:
            continue
        yerel = an_utc.astimezone(_tz(m))
        kayit = d.json_oku(f"{m['id']}/eposta.json", {}) or {}
        eski = dict(kayit)
        hafta = yerel.strftime("%G-W%V")
        try:
            if yerel.weekday() == 0 and 9 <= yerel.hour < 11 and kayit.get("ozet") != hafta:
                if gonder(_sahipler(d, m["id"]), *haftalik_ozet(d, m, yerel)):
                    kayit["ozet"] = hafta
                    rapor["ozet"].append(m["id"])
            if m["durum"] == "deneme" and m.get("deneme_bitis") and 9 <= yerel.hour < 18:
                kalan = (datetime.fromisoformat(str(m["deneme_bitis"]).replace("Z", "+00:00")) - an_utc).total_seconds() / 86400
                if 0 < kalan <= 2 and kayit.get("deneme") != str(m["deneme_bitis"]):
                    if gonder(_sahipler(d, m["id"]), *deneme_hatirlatma(m, max(1, round(kalan)))):
                        kayit["deneme"] = str(m["deneme_bitis"])
                        rapor["deneme"].append(m["id"])
        finally:
            if kayit != eski:
                d.json_yaz(f"{m['id']}/eposta.json", kayit)
    return rapor
