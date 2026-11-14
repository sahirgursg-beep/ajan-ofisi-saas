"""Uretken tasarim: gorsel dil -> tuval HTML -> olcum (tasma, guvenli alan, zorunlu metin) -> duzeltme -> puan."""
import pytest

from ofis import ajanlar, fiyat, llm, uretken

pytestmark = pytest.mark.skipif(__import__("os").environ.get("AJAN_TAM_TEST") != "1", reason="tarayici gerekir (AJAN_TAM_TEST=1)")

IYI = """<style>.tuval{width:1080px;height:1350px;position:relative;overflow:hidden;background:#F3EFE7;padding:64px;
display:grid;grid-template-rows:1fr auto;gap:24px}.foto{border-radius:32px;overflow:hidden;min-height:0}
.foto img{width:100%;height:100%;object-fit:cover}.alt{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.alt>*{min-width:0;border-radius:32px;padding:36px}.b{background:#141414;color:#fff;font:700 64px/1 var(--bf)}
.f{background:#FF5A36;font:700 60px/1 var(--bf);white-space:nowrap}</style>
<div class="tuval"><div class="foto"><img src="{{FOTO1}}"></div><div class="alt"><div class="b" data-metin>HEAD</div>
<div class="f" data-metin>PRICE</div></div></div>"""
KOTU = """<style>.tuval{width:1080px;height:1350px;position:relative;overflow:hidden}.h{position:absolute;left:-60px;top:8px;
font:900 220px var(--bf);white-space:nowrap}</style><div class="tuval"><div class="h" data-metin>HEAD and much more</div></div>"""


def test_kotu_tasarim_olculur_duzeltilir_iyi_tasarim_gecer(tmp_path, monkeypatch):
    from PIL import Image
    foto = tmp_path / "f.jpg"
    Image.new("RGB", (900, 1200), "#7a8c6e").save(foto)
    urun = fiyat.hazirla({"ad": "Milano Sofa", "fiyat": 1250, "para_birimi": "USD", "kategori": "Sofas", "gorseller": []})
    iyi = IYI.replace("HEAD", "Comfort that feels like home").replace("PRICE", urun["fiyat_metni"])
    sorular = []

    def sor(sistem, mesaj, json_mod=False, sicaklik=0.7):
        if json_mod:
            return {"stil": "bento", "fikir": "x", "font": "cagdas", "palet": {"bg": "#F3EFE7", "ink": "#111111",
                    "accent": "#FF5A36", "accent2": "#2D5BFF"}, "dokular": "tiles"}
        sorular.append(mesaj)
        if "problems" in mesaj:
            assert "outside the safe area" in mesaj and "required text missing" in mesaj
            return iyi
        return KOTU.replace("HEAD", "Comfort that feels like home")
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", sor)
    monkeypatch.setattr(llm, "gor", lambda *a, **k: {"score": 8, "problems": []})
    r = uretken.tasarla(urun, [str(foto)], {"headline": "Comfort that feels like home"}, tmp_path, "reels")
    assert r and r["puanlar"] == {"post": 8.0} and (tmp_path / "post_1080x1350.jpg").stat().st_size > 5000
    assert len(sorular) == 2 and uretken.gecmis()[-1]["stil"] == "bento"


def test_gorsel_puan_dusukse_ve_duzelmezse_eski_sablona_duser(tmp_path, monkeypatch):
    urun = fiyat.hazirla({"ad": "Lamp", "fiyat": 50, "para_birimi": "USD", "gorseller": []})
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", lambda s, m, json_mod=False, sicaklik=0.7: {"stil": "x", "font": "zzz"} if json_mod
                        else IYI.replace("HEAD", "Light").replace("PRICE", urun["fiyat_metni"]).replace('<img src="{{FOTO1}}">', ""))
    monkeypatch.setattr(llm, "gor", lambda *a, **k: {"score": 3, "problems": ["looks dated"]})
    assert uretken.tasarla(urun, [], {"headline": "Light"}, tmp_path, "reels") is None


def test_temizlik_dis_adres_ve_script_birakmaz():
    h = uretken._temizle('```html\n<style>@import url(https://x.y/a.css); .a{background:url(https://evil/x.png)}</style>'
                         '<script>alert(1)</script><div class="tuval" onclick="x()"><img src="https://evil/p.jpg">'
                         '<img src="{{FOTO1}}"></div>```')
    assert "script" not in h and "evil" not in h and "onclick" not in h and "@import" not in h and "{{FOTO1}}" in h


def test_carousel_kartlari_farkli_duzenlerde_tutmayan_kart_atilir_sira_bozulmaz(tmp_path, monkeypatch):
    from PIL import Image
    fotolar = []
    for i in range(3):
        f = tmp_path / f"f{i}.jpg"
        Image.new("RGB", (900, 1200), (40 * i, 120, 90)).save(f)
        fotolar.append(str(f))
    urun = fiyat.hazirla({"ad": "Sofa", "fiyat": 900, "para_birimi": "USD", "gorseller": []})
    roller = []

    def sor(sistem, mesaj, json_mod=False, sicaklik=0.7):
        if json_mod:
            return {"stil": "renk_blok", "fikir": "x", "font": "cagdas", "palet": {}}
        rol = mesaj.split("Role: ")[1].split("\n")[0]
        roller.append(rol)
        if "Line two" in mesaj:                                     # bu kart hic duzelmez
            return KOTU.replace("HEAD", "Line two")
        metin = "Line one" if "Line one" in mesaj else "Line three" if "Line three" in mesaj else "Comfort"
        return IYI.replace("HEAD", metin).replace("PRICE", urun["fiyat_metni"])
    monkeypatch.setattr(llm, "hazir", lambda: True)
    monkeypatch.setattr(llm, "sor", sor)
    monkeypatch.setattr(llm, "gor", lambda *a, **k: {"score": 8})
    r = uretken.tasarla(urun, fotolar, {"headline": "Comfort", "carousel_lines": ["Line one", "Line two", "Line three"]},
                        tmp_path, "carousel")
    adlar = sorted(p.name for p in tmp_path.glob("carousel_*.jpg"))
    assert adlar == ["carousel_1.jpg", "carousel_2.jpg", "carousel_3.jpg", "carousel_4.jpg"]   # 2. satir atildi, bosluk yok
    assert not r.get("carousel_eksik")
    duzenler = {x.split("Layout for THIS slide: ")[1].split(".")[0] for x in roller if "Layout for THIS slide" in x}
    assert len(duzenler) == 3                                        # her kart farkli duzen
