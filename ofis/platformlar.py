"""Platform uzmanlari: Instagram, Facebook, TikTok, LinkedIn.

Ayni icerik fikri her platformda o platformun diliyle yazilir. Kurallar kodda (sinirlar kesin), yaraticilik
yapay zekada. Ciktilar icerik klasorunde platformlar.json olarak saklanir:
  {"instagram": {...}, "facebook": {...}, "tiktok": {...}, "linkedin": {...}}
Instagram/Facebook Meta uzerinden otomatik yayinlanir; TikTok ve LinkedIn, API onaylari gelene kadar
panelden indirilip elle paylasilir (mod: "manuel").
"""
import json
import re

from . import dil, llm, musteri, sektor

KURALLAR = {
    "instagram": {
        "ad": "Instagram", "mod": "otomatik", "metin_siniri": 2200, "hashtag": (8, 15), "baslik": False,
        "formatlar": {"post": "1080x1350 feed post", "carousel": "1080x1350 swipe carousel", "reels": "1080x1920 Reel"},
        "ilke": "Visual-first. First line is the hook (it shows above 'more'). Short lines, emojis sparingly, "
                "clear CTA. Hashtags at the end, mix of niche + local.",
    },
    "facebook": {
        "ad": "Facebook", "mod": "otomatik", "metin_siniri": 5000, "hashtag": (0, 4), "baslik": False,
        "formatlar": {"post": "1080x1350 photo post", "carousel": "multi-photo post", "reels": "1080x1920 Reel"},
        "ilke": "Community and conversation. Slightly longer, warmer, local. Ask a simple question to invite "
                "comments. Few or no hashtags. Include practical info (location, how to order).",
    },
    "tiktok": {
        "ad": "TikTok", "mod": "manuel", "metin_siniri": 2200, "hashtag": (3, 6), "baslik": True,
        "formatlar": {"post": "photo mode (swipe images)", "carousel": "photo mode (swipe images)",
                      "reels": "1080x1920 vertical video"},
        "ilke": "Entertainment first, selling second. The hook must work in the first 2 seconds. Casual, "
                "native, human tone, no corporate language. Very short caption. On-screen text carries the story.",
    },
    "linkedin": {
        "ad": "LinkedIn", "mod": "manuel", "metin_siniri": 3000, "hashtag": (3, 5), "baslik": False,
        "formatlar": {"post": "single image post", "carousel": "document-style carousel", "reels": "native video"},
        "ilke": "Professional value. Lead with an insight, a lesson or a result; tell a short story; end with a "
                "takeaway or question. No hype, no emoji walls. Line breaks for readability.",
    },
}
SIRA = ("instagram", "facebook", "tiktok", "linkedin")


def aktif_platformlar():
    """Sektor agirligi 0 olan platformlar atlanir (or. kuafor icin LinkedIn)."""
    agirlik = (sektor.profil().get("platform") or {})
    secili = musteri.bilgi().get("platformlar")
    if secili:
        return [p for p in SIRA if p in secili]
    return [p for p in SIRA if agirlik.get(p, 1) > 0]


def _temizle(p, d, taban):
    k = KURALLAR[p]
    metin = str(d.get("caption") or taban.get("caption") or "").strip()[: k["metin_siniri"]]
    etiketler = [("#" + str(h).lstrip("#")).replace(" ", "") for h in (d.get("hashtags") or []) if str(h).strip("# ")]
    if len(etiketler) < k["hashtag"][0]:
        etiketler += [h for h in taban.get("hashtags", []) if h not in etiketler]
    etiketler = etiketler[: k["hashtag"][1]]
    out = {"caption": metin, "hashtags": etiketler, "hook": str(d.get("hook") or taban.get("hook") or "")[:120],
           "mod": k["mod"]}
    if p == "tiktok":
        out["ekran_yazilari"] = [str(x)[:60] for x in (d.get("on_screen") or taban.get("reels_lines") or [])][:4]
        out["baslik"] = str(d.get("title") or out["hook"])[:90]
    if p == "linkedin" and not re.search(r"\n", metin) and len(metin) > 200:
        out["caption"] = re.sub(r"(?<=[.!?]) ", "\n\n", metin, count=4)
    return out


def _sablon(p, taban):
    """Yapay zeka yoksa: taban metinden kurallara uygun surum."""
    cta = musteri.bilgi().get("yonlendirme") or "send us a DM"
    c = taban.get("caption", "")
    ingilizce = dil.kod() == "en"
    if p == "facebook" and ingilizce:
        c = c + f"\n\nWhat do you think? Tell us in the comments 👇"
    elif p == "tiktok":
        c = (taban.get("hook") or c.split("\n")[0])[:150]
    elif p == "linkedin":
        c = (f"{taban.get('headline') or taban.get('hook') or ''}\n\n{c}"
             + (f"\n\nInterested? {cta[:1].upper() + cta[1:]}." if ingilizce else "")).strip()
    return _temizle(p, {"caption": c}, taban)


def uret(urun, aci, taban, tur):
    """Taban taslaktan (Metin Yazari + Kalite Kontrol onayli) her platforma ozel surum."""
    platformlar = aktif_platformlar()
    out = {}
    fiyat = urun.get("fiyat_metni") or ""
    for p in platformlar:
        k = KURALLAR[p]
        cevap = None
        if llm.hazir():
            cevap = llm.sor(
                f"You are the {k['ad']} specialist of a social media team for {musteri.tanim()}. "
                f"{musteri.satis_kanali()} Answer ONLY with valid JSON.",
                f"Platform rules: {k['ilke']}\nFormat today: {k['formatlar'].get(tur or 'post')}\n{dil.talimat()}"
                f"{sektor.istem_ozeti()}\nTopic: {urun['ad']}\nAngle: {aci}\n"
                + (f"Exact price (use exactly, never change): {fiyat}\n" if fiyat else "No price for this content.\n")
                + f"Approved base copy:\n{json.dumps({x: taban.get(x) for x in ('hook', 'headline', 'caption')}, ensure_ascii=False)}\n\n"
                f"Rewrite it natively for {k['ad']}. Max {k['metin_siniri']} characters, "
                f"{k['hashtag'][0]}-{k['hashtag'][1]} hashtags. Never invent facts, prices, sizes or promises.\n"
                'Return JSON: {"hook": "...", "caption": "...", "hashtags": ["..."]'
                + (', "title": "<short video title>", "on_screen": ["<2-4 on-screen text lines, max 6 words>"]'
                   if p == "tiktok" else "") + "}",
                json_mod=True, sicaklik=0.7)
        if isinstance(cevap, dict) and cevap.get("caption"):
            sonuc = _temizle(p, cevap, taban)
            if fiyat and fiyat.replace(",", "") not in sonuc["caption"].replace(",", "") and p != "tiktok":
                sonuc = _sablon(p, taban)          # fiyat bozulduysa onayli metne don
        else:
            sonuc = _sablon(p, taban)
        out[p] = sonuc
    return out


def kaydet(klasor, veri):
    (klasor / "platformlar.json").write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def oku(klasor):
    try:
        return json.loads((klasor / "platformlar.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def metin(klasor, platform):
    """Yayinda kullanilacak metin (caption + hashtagler) ya da None."""
    p = oku(klasor).get(platform)
    if not p:
        return None
    return (p["caption"] + ("\n\n" + " ".join(p["hashtags"]) if p.get("hashtags") else "")).strip()
