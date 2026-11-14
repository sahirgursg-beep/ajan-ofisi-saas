"""Reklam tarzi Reels: sablonlar/reels.html'i tarayicida kare kare oynatip MP4'e cevirir."""
import json
import random
import subprocess
from pathlib import Path

from .ayarlar import AYAR, KOK
from . import algila, marka, musteri, tasarim

SURE = 15.0
FPS = 25          # Reels icin yeterli akicilik; 30'a gore %17 daha az kare
YEDEK_FAYDALAR = (musteri.faydalar() or list(musteri.bilgi().get("hizmetler") or [])[:2] or [musteri.ad()]) * 2


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def reklam_yap(urun, gorsel_yollari, taslak, tarif, hedef: Path, gunluk=print, dikey_yollari=None,
               muzik_id=None, muzik_haric=None, format_adi="luks", son_kart=None):
    """format_adi: "luks" (sablonlar/reels.html) veya reels_formatlari.FORMATLAR icindeki trend formatlardan biri."""
    from . import sanat
    tarif = tarif if isinstance(tarif, dict) else sanat.rastgele_tarif(urun, sanat.baglam())
    farkli = len({str(g) for g in gorsel_yollari})
    if dikey_yollari:   # AI ile 9:16'ya tamamlanmis fotolar: kirpma yok, urun tam gorunur
        gorsel_yollari = list(dikey_yollari) + [g for g in gorsel_yollari[len(dikey_yollari):]]
    v = tasarim.veri_hazirla(urun, gorsel_yollari, taslak, tarif)
    logolar = marka.logolar()
    koyu_zemin = sanat._parlaklik(tarif["palet"]["zemin"]) < 0.5
    v["logo_son"] = tasarim._uri(logolar["altin"] if koyu_zemin else logolar["koyu"])
    v["f_sinif"] = f"f-{tarif['fontlar']}"
    satirlar = taslak.get("reels_lines") or []
    satirlar = [satirlar] if isinstance(satirlar, str) else satirlar
    faydalar = [str(x) for x in satirlar if str(x).strip()][:2]
    faydalar += YEDEK_FAYDALAR[len(faydalar):2]
    if format_adi and format_adi != "luks":
        from . import reels_formatlari
        farkli_yollar = list(dict.fromkeys(str(g) for g in gorsel_yollari))[:4] or [None]
        for i, g in enumerate(farkli_yollar if farkli_yollar[0] else [], 1):
            v[f"foto{i}"] = tasarim._uri(marka.gorsel_hazirla(Path(g)))
        S = reels_formatlari.senaryo(format_adi, taslak, urun, len(farkli_yollar) if farkli_yollar[0] else 1)
        S["kutular"] = [algila.urun_kutusu(marka.gorsel_hazirla(Path(g))) for g in farkli_yollar] if farkli_yollar[0] else []
        v["veri_json"] = json.dumps(S, ensure_ascii=False)
        sablon_adi = "reels_format.html"
    else:
        sablon_adi = "reels.html"
        v["veri_json"] = json.dumps({
            "kanca": taslak.get("hook") or __import__("ofis.dil", fromlist=["x"]).etiket("kanca"),
            "ad": urun["ad"], "fayda": faydalar, "ayni": farkli < 3,
            "kutular": [algila.urun_kutusu(marka.gorsel_hazirla(Path(g))) for g in
                        (list(gorsel_yollari) + list(gorsel_yollari[:1]) * 3)[:3]] if gorsel_yollari else [],
        }, ensure_ascii=False)

    from . import dil as _dil, fontlar as _fontlar
    # Tum font ciftlerinin degiskenleri (--bf, --bo...): sablonda yalniz 5 eski cift tanimli; digerlerinde
    # degiskenler tanimsiz kalip yazilar 16px serif'e dusuyordu
    metin = _dil.html_isareti((tasarim.SABLON / sablon_adi).read_text(encoding="utf-8")).replace(
        "</head>", f"<style>{_fontlar.css_siniflari()}</style></head>", 1)
    for k, deger in v.items():
        guvenli = deger if k in ("ortak", "fontlar", "veri_json") or k.startswith(("foto", "logo", "t_")) \
            else __import__("html").escape(str(deger))
        metin = metin.replace("{{" + k + "}}", guvenli)
    metin = metin.replace("</head>", f"<style>:root{{{tasarim.marka_css()}}}</style></head>", 1)
    if son_kart and Path(son_kart).exists():
        # Sanat Yonetmeni'nin icerige ozel kapanis karti son ~3 saniyede yumusakca gelir (logo/renk karari ondan)
        bas = SURE - 3.2
        metin = metin.replace("</body>",
            f'<img id="sonkart" src="{tasarim._uri(son_kart)}" style="position:fixed;left:0;top:0;width:1080px;'
            'height:1920px;object-fit:cover;opacity:0;z-index:2147483647;pointer-events:none">'
            f"<script>window.__sk=function(t){{var e=document.getElementById('sonkart');var a=Math.min(1,Math.max(0,(t-{bas})/0.45));"
            "e.style.opacity=a;e.style.transform='scale('+(1.035-0.035*a)+')';}}</script></body>", 1)
    gecici = tasarim.SABLON / f"_render_{AYAR['musteri_id']}_reels.html"
    gecici.write_text(metin, encoding="utf-8")

    # Kareler kayipsiz PNG; video telefonlarin bekledigi BT.709 renk uzayina dogru donusturulup etiketlenir
    # (aksi halde kirmizi/turuncu tonlar kayar).
    # Kareler yuksek kaliteli JPEG: PNG'ye gore cok daha hizli cekilir ve cozulur (renk farki gozle gorulmez)
    komut = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
             "-vcodec", "mjpeg", "-i", "-"]
    # Muzik: ruh haline uygun, lisansi temiz (CC0 / CC BY) parca; en canli 15 sn bolumu
    from . import muzik
    parca = None
    try:
        parca = muzik.bul(muzik_id) or muzik.sec(muzik.ruh_hali(tarif), haric=muzik_haric)
    except Exception as e:
        gunluk(f"Muzik secilemedi: {e}")
    if parca:
        bas = muzik.en_canli_bolum(parca["yol"], SURE)
        komut += ["-ss", str(bas), "-i", parca["yol"],
                  "-af", f"afade=t=in:d=0.6,afade=t=out:st={SURE - 1.8}:d=1.8,loudnorm=I=-16:TP=-1.5:LRA=11",
                  "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    komut += ["-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264",
              "-preset", "veryfast", "-crf", "18", "-colorspace", "bt709", "-color_primaries", "bt709",
              "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", str(hedef)]

    sayfa = tasarim._tarayici_al().new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
    p = subprocess.Popen(komut, stdin=subprocess.PIPE)
    try:
        sayfa.goto(gecici.as_uri(), wait_until="load")
        sayfa.evaluate("document.fonts.ready")
        sayfa.evaluate("Promise.all([...document.images].map(i => i.decode().catch(() => {})))")
        toplam = int(SURE * FPS)
        import time as _t
        _bas = _t.time()
        for i in range(toplam):
            sayfa.evaluate(f"ciz({i / FPS:.4f}); window.__sk && __sk({i / FPS:.4f})")
            p.stdin.write(sayfa.screenshot(type="jpeg", quality=93))
            if i % 90 == 0:
                gunluk(f"Reels kurguluyorum... %{int(100 * i / toplam)}")
        gunluk(f"Reels kareleri {toplam} adet, {_t.time() - _bas:.0f} sn")
    finally:
        p.stdin.close()
        p.wait()
        sayfa.close()
        tasarim.kapat()
        gecici.unlink(missing_ok=True)
    if p.returncode != 0:
        raise RuntimeError("FFmpeg reklam videosunu olusturamadi")
    if parca:
        muzik.kullanildi(parca)
        bilgi = {k: parca.get(k) for k in ("id", "baslik", "sanatci", "lisans", "lisans_surum", "lisans_url",
                                            "kaynak", "sayfa", "ruh")}
        bilgi["atif"] = muzik.atif_satiri(parca)
        (Path(hedef).parent / "muzik.json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=2), encoding="utf-8")
    (Path(hedef).parent / "kurgu.json").write_text(json.dumps({"reels_format": format_adi or "luks"}), encoding="utf-8")
    return hedef
