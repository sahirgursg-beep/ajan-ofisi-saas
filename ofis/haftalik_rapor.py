"""Haftalik yonetici raporu: tek sayfalik, paylasilabilir HTML (gorseller icine gomulu; tarayicidan PDF'e yazdirilabilir).
cikti/raporlar/YYYY-MM-DD.html"""
import base64
import html
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

from .ayarlar import KOK, CIKTI
from . import musteri

KLASOR = CIKTI / "raporlar"
E = lambda s: html.escape(str(s if s is not None else ""))


def _kucuk(yol, gen=360):
    try:
        from PIL import Image
        im = Image.open(yol).convert("RGB")
        im.thumbnail((gen, gen * 2))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=72)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    except Exception:
        return ""


def _sayi(n):
    return "–" if n is None else f"{int(n):,}".replace(",", ".")


def olustur():
    from . import analiz, iletisim, oneriler, plan, projeler, rakip, yayin
    bugun = datetime.now()
    bas = bugun - timedelta(days=7)
    sinir = bas.strftime("%Y-%m-%d")
    icerikler = [c for c in analiz.ciktilar(200)
                 if (c["meta"].get("plan_gunu") or c["meta"].get("tarih", ""))[:10] >= sinir
                 and yayin.oku(c["klasor"]).get("durum") in ("yayinlandi", "kismen")]
    izl = sum(c["performans"].get("goruntulenme") or 0 for c in icerikler)
    etk = sum(sum(c["performans"].get(k) or 0 for k in ("begeni", "kaydetme", "paylasim", "yorum")) for c in icerikler)
    skor = lambda c: sum(c["performans"].get(k) or 0 for k in ("begeni", "kaydetme", "paylasim", "yorum")) + (c["performans"].get("goruntulenme") or 0) / 50
    en_iyi = sorted(icerikler, key=skor, reverse=True)[:3]
    h = yayin.hesap_gecmisi().get("gunler", {})
    gunler = sorted(h.items())
    son = gunler[-1][1] if gunler else {}
    once = next((v for k, v in gunler if k >= sinir), {}) if gunler else {}
    tk = lambda a: (son.get(a) or 0) - (once.get(a) or 0) if son.get(a) is not None and once.get(a) is not None else None
    yeni_proje = [p_ for p_ in projeler.liste() if not p_["kullanildi"]]
    paylasilan_proje = [p_ for p_ in projeler.liste() if (p_["kullanildi"] or "") >= sinir]
    il = iletisim.son_rapor()
    rk = rakip.son()
    bekleyen = [o for o in oneriler.liste()["oneriler"] if o["durum"] == "bekliyor"]
    p = plan.oku()
    gelecek = [g for g in p.get("gunler", []) if g["tarih"] > bugun.strftime("%Y-%m-%d")][:7]

    def kpi(e, d, a=""):
        return f'<div class="k"><div class="e">{E(e)}</div><div class="d">{d}</div><div class="a">{a}</div></div>'
    fark = lambda n: "" if n is None else (f'<span class="{"art" if n >= 0 else "eks"}">{"+" if n >= 0 else ""}{_sayi(n)}</span> bu hafta')
    kartlar = []
    for c in en_iyi:
        k = CIKTI / c["klasor"]
        g = _kucuk(k / ("carousel_1.jpg" if (k / "carousel_1.jpg").exists() else "post_1080x1350.jpg"))
        pf = c["performans"]
        kartlar.append(f'''<div class="ic"><img src="{g}"><div><b>{E(c["meta"]["urun"]["ad"])}</b>
          <span>{E((c["meta"].get("format") or "").upper())} · {E((c["meta"].get("plan_gunu") or c["meta"].get("tarih", ""))[:10])}</span>
          <p>👁 {_sayi(pf.get("goruntulenme"))} · ❤ {_sayi(pf.get("begeni"))} · 🔖 {_sayi(pf.get("kaydetme"))} · ↗ {_sayi(pf.get("paylasim"))}
          {f"<br>💬 {pf['soru']} satın alma sorusu" if pf.get("soru") else ""}</p></div></div>''')
    satirlar = iletisim.ozet_satirlari(il) if il else []
    html_ = f'''<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8"><title>Haftalık rapor · {bugun:%d.%m.%Y}</title>
<style>
 body {{ margin:0; background:#f4efe6; color:#1c1612; font-family:"Segoe UI",system-ui,sans-serif; }}
 .s {{ max-width:960px; margin:0 auto; padding:36px 40px 60px; background:#fffdf9; min-height:100vh; }}
 header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:2px solid #c9a24b; padding-bottom:14px; }}
 header b {{ letter-spacing:.2em; color:#8a6a28; font-size:13px; }} header h1 {{ margin:6px 0 0; font:600 30px Georgia,serif; }}
 header span {{ color:#7a6f63; font-size:13px; }}
 h2 {{ font:600 18px Georgia,serif; margin:30px 0 12px; color:#2b211b; }}
 .kpi {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:22px; }}
 .k {{ background:#f6efe2; border-radius:12px; padding:14px 16px; }} .k .e {{ font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:#8a7d6c; }}
 .k .d {{ font:700 28px Georgia,serif; margin-top:4px; }} .k .a {{ font-size:12px; color:#7a6f63; }}
 .art {{ color:#2f8a55; }} .eks {{ color:#b04040; }}
 .icler {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
 .ic {{ background:#f6efe2; border-radius:12px; overflow:hidden; }} .ic img {{ width:100%; aspect-ratio:4/5; object-fit:cover; display:block; }}
 .ic div {{ padding:10px 12px 12px; font-size:13px; }} .ic b {{ display:block; font-size:14px; }} .ic span {{ color:#8a7d6c; font-size:11.5px; }} .ic p {{ margin:6px 0 0; }}
 ul {{ margin:0; padding-left:18px; line-height:1.65; font-size:14px; }}
 .iki {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
 table {{ width:100%; border-collapse:collapse; font-size:13px; }} td, th {{ text-align:left; padding:7px 6px; border-bottom:1px solid #eadfcd; }} th {{ color:#8a7d6c; font-weight:600; }}
 .yok {{ color:#8a7d6c; font-size:13px; }}
 footer {{ margin-top:40px; font-size:11.5px; color:#9a8f83; border-top:1px solid #eadfcd; padding-top:10px; }}
 @media print {{ body {{ background:#fff; }} .s {{ padding:10px; }} }}
</style></head><body><div class="s">
<header><div><b>{html.escape(musteri.ad().upper())} · SOSYAL MEDYA</b><h1>Haftalık rapor</h1></div><span>{bas:%d.%m} – {bugun:%d.%m.%Y}</span></header>
<div class="kpi">{kpi("Yayınlanan içerik", len(icerikler), "post · carousel · Reels")}
{kpi("İzlenme", _sayi(izl), f"{_sayi(etk)} etkileşim")}
{kpi("Instagram takipçi", _sayi(son.get("ig_takipci")), fark(tk("ig_takipci")))}
{kpi("Tamamlanan projeler", len(paylasilan_proje), f"bu hafta paylaşıldı · {len(yeni_proje)} sırada")}</div>
<h2>Haftanın en iyi içerikleri</h2>{'<div class="icler">' + "".join(kartlar) + "</div>" if kartlar else '<div class="yok">Bu hafta rakamı gelmiş yayın yok.</div>'}
<div class="iki"><div><h2>Müşteriler ne soruyor?</h2>{"<ul>" + "".join(f"<li>{E(x)}</li>" for x in satirlar) + "</ul>" if satirlar else '<div class="yok">Rapor henüz yok.</div>'}</div>
<div><h2>Proje paylaşımları</h2>{"<ul>" + "".join(f"<li><b>{E(p_['baslik'])}</b>{(' — ' + E(p_['konum'])) if p_['konum'] else ''} ({p_['foto_sayisi']} fotoğraf)</li>" for p_ in paylasilan_proje) + "</ul>" if paylasilan_proje else '<div class="yok">Bu hafta proje paylaşılmadı' + (f' · sırada {len(yeni_proje)} proje' if yeni_proje else ' · yeni proje eklenmedi') + '.</div>'}</div></div>
<h2>Rakipler ve ilham hesapları</h2>{"<ul>" + "".join(f"<li>{E(x)}</li>" for x in rakip.ozet_satirlari(rk)) + "</ul>" if rk.get("hesaplar") else '<div class="yok">Rakip listesi henüz taranmadı.</div>'}
<h2>Ofisin önerileri (onay bekliyor)</h2>{"<ul>" + "".join(f"<li><b>{E(o['baslik'])}</b> — {E(o['gerekce'])}</li>" for o in bekleyen) + "</ul>" if bekleyen else '<div class="yok">Bekleyen öneri yok.</div>'}
<h2>Gelecek hafta</h2>{"<table><tr><th>Gün</th><th>Post 12:00</th><th>Carousel 15:00</th><th>Reels</th></tr>" + "".join(
        f"<tr><td>{E(g['tarih'][8:10] + '.' + g['tarih'][5:7])}</td>" + "".join(
            f"<td>{E(((g.get('icerikler') or {}).get(t) or {}).get('urun', {}).get('ad') or 'otomatik seçilecek')}</td>" for t in ("post", "carousel", "reels")) + "</tr>"
        for g in gelecek) + "</table>" if gelecek else '<div class="yok">Plan henüz oluşturulmadı.</div>'}
<footer>Ajan Ofisi tarafından {bugun:%d.%m.%Y %H:%M}'de otomatik hazırlandı. Rakamlar Meta'dan.</footer>
</div></body></html>'''
    KLASOR.mkdir(parents=True, exist_ok=True)
    yol = KLASOR / f"{bugun:%Y-%m-%d}.html"
    yol.write_text(html_, encoding="utf-8")
    return yol


def liste():
    if not KLASOR.exists():
        return []
    return [{"ad": p.name, "url": f"/raporlar/{p.name}", "tarih": p.stem}
            for p in sorted(KLASOR.glob("*.html"), reverse=True)[:20]]
