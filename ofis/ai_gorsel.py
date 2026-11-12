"""Ekran karti (NVIDIA) ile yerel yapay zeka gorsel islemleri. Tamamen ucretsiz, internetsiz calisir
(modeller ilk kullanimda bir kez iner).

  netlestir(yol)               -> kucuk fotograflari Real-ESRGAN ile 4x buyutur/netlestirir
  dikey_genislet(yol, kutu)    -> yatay oda fotografini 9:16'ya tamamlar (ust: duvar/tavan, alt: zemin)

ALTIN KURAL: Urunun kendisi asla yapay zekayla degistirilmez. Genisletmede orijinal fotograf en sonda
piksel piksel geri yapistirilir; yapay zeka yalnizca fotografin DISINDA kalan bos alani doldurur.
"""
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .ayarlar import AYAR, KOK, PAYLASIK

MODEL_KLASOR = PAYLASIK / "ai_modeller"
ESRGAN_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
INPAINT_MODEL = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
VAE_MODEL = "madebyollin/sdxl-vae-fp16-fix"   # SDXL'in fp16'da siyah/bozuk goruntu sorununu giderir

_esrgan = None
_pipe = None


def ayar(anahtar, varsayilan=None):
    return (AYAR.get("ai_gorsel") or {}).get(anahtar, varsayilan)


def durum():
    """(hazir_mi, aciklama)"""
    if not ayar("aktif", True):
        return False, "config.json'da kapali"
    try:
        import torch
    except Exception:
        return False, "PyTorch kurulu degil (AI_KURULUM.bat calistirin)"
    if not torch.cuda.is_available():
        return False, "NVIDIA ekran karti/CUDA bulunamadi (surucu guncel mi?)"
    try:
        import diffusers  # noqa: F401
    except Exception:
        return False, "diffusers kurulu degil (AI_KURULUM.bat calistirin)"
    return True, torch.cuda.get_device_name(0)


# ------------------------------------------------------------------ netlestirme
def _esrgan_yukle():
    global _esrgan
    if _esrgan is None:
        import torch
        from spandrel import ModelLoader
        MODEL_KLASOR.mkdir(parents=True, exist_ok=True)
        agirlik = MODEL_KLASOR / "RealESRGAN_x4plus.pth"
        if not agirlik.exists():
            import requests
            agirlik.write_bytes(requests.get(ESRGAN_URL, timeout=300).content)
        _esrgan = ModelLoader().load_from_file(str(agirlik)).cuda().eval().half()
        torch.cuda.empty_cache()
    return _esrgan


def netlestir(yol, hedef_kenar=2400):
    """Uzun kenari hedef_kenar'dan kucukse 4x buyutup hedef boyuta indirir. Buyukse dokunmaz."""
    yol = Path(yol)
    cikti = yol.with_name(yol.stem + "_net.jpg")
    if cikti.exists():
        return cikti
    im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
    if max(im.size) >= hedef_kenar * 0.7:
        return yol
    import numpy as np
    import torch
    model = _esrgan_yukle()
    x = torch.from_numpy(np.asarray(im)).permute(2, 0, 1).unsqueeze(0).half().cuda() / 255.0
    parca, ust = 384, 16                                   # 8 GB'a sigsin diye parca parca isle
    _, _, h, w = x.shape
    sonuc = torch.zeros((1, 3, h * 4, w * 4), dtype=torch.half, device="cuda")
    with torch.no_grad():
        for y0 in range(0, h, parca):
            for x0 in range(0, w, parca):
                ya, xa = max(0, y0 - ust), max(0, x0 - ust)
                yb, xb = min(h, y0 + parca + ust), min(w, x0 + parca + ust)
                o = model(x[:, :, ya:yb, xa:xb])
                oy, ox = (y0 - ya) * 4, (x0 - xa) * 4
                hh, ww = min(parca, h - y0) * 4, min(parca, w - x0) * 4
                sonuc[:, :, y0 * 4:y0 * 4 + hh, x0 * 4:x0 * 4 + ww] = o[:, :, oy:oy + hh, ox:ox + ww]
    out = (sonuc.clamp(0, 1)[0].permute(1, 2, 0).float().cpu().numpy() * 255).round().astype("uint8")
    buyuk = Image.fromarray(out)
    buyuk.thumbnail((hedef_kenar, hedef_kenar), Image.LANCZOS)
    buyuk.save(cikti, quality=95, subsampling=0)
    torch.cuda.empty_cache()
    return cikti


# ------------------------------------------------------------------ dikeye genisletme
def _pipe_yukle():
    global _pipe
    if _pipe is None:
        import torch
        from diffusers import AutoencoderKL, AutoPipelineForInpainting
        vae = AutoencoderKL.from_pretrained(VAE_MODEL, torch_dtype=torch.float16, cache_dir=str(MODEL_KLASOR))
        _pipe = AutoPipelineForInpainting.from_pretrained(INPAINT_MODEL, vae=vae, torch_dtype=torch.float16,
                                                          variant="fp16", cache_dir=str(MODEL_KLASOR))
        _pipe.enable_model_cpu_offload()      # 8 GB ekran kartina sigmasi icin
        try:
            _pipe.enable_vae_tiling()
        except Exception:
            pass
    return _pipe


def yerlesim(boyut, kutu, W=1080, H=1920):
    """Yatay fotografi dikey tuvale nasil koyacagimizi hesaplar.
    Urunun tamami gorunsun diye fotograf, urun genisligi tuvalin ~%92'sine sigacak kadar buyutulur;
    yanlardan sadece urun disi kisimlar kirpilir. Doner: (olcek, kirp_x0, kirp_x1, ust_y)."""
    w, h = boyut
    k = kutu or {"x0": .1, "x1": .9}
    urun_gen = max(0.3, min(1.0, (k["x1"] - k["x0"]) + 0.16))       # urun kenarlari kesilmesin diye genis pay
    olcek = min(W / (w * urun_gen) * 0.92, H * 0.62 / h)               # foto en fazla tuvalin %62'si kadar uzun
    olcek = max(olcek, W / w)                                          # en az tuval genisligi kadar
    gorunen = W / olcek                                                # fotografin tuvale sigan genisligi (piksel)
    merkez = ((k["x0"] + k["x1"]) / 2) * w
    x0 = int(min(max(0, merkez - gorunen / 2), w - gorunen))
    x1 = int(x0 + gorunen)
    yuk = h * olcek
    ust = int((H - yuk) * 0.5)                                         # ortala (ust: duvar, alt: zemin)
    return olcek, x0, x1, ust


def tuval_ve_maske(im, kutu, W=1080, H=1920, kenar=28):
    olcek, x0, x1, ust = yerlesim(im.size, kutu, W, H)
    kirpik = im.crop((x0, 0, x1, im.height)).resize((W, round(im.height * olcek)), Image.LANCZOS)
    yuk = kirpik.height
    # Dikis izi olmasin: urun kutusunun DISINDA kalan ust/alt seritler (tavan kenari, hali, zemin) de
    # yapay zekaya birakilir; boylece hali/zemin dogal sekilde devam eder. Urun kutusuna asla girilmez.
    k = kutu or {"y0": 0.3, "y1": 0.9}
    pay = 0.06
    ust_bindirme = int(min(max(kenar, (k["y0"] - pay) * yuk), 0.18 * yuk))
    alt_bindirme = int(min(max(kenar, (1 - k["y1"] - pay) * yuk), 0.22 * yuk))
    # tuval: bos alani fotografin kenar satirlarinin uzatilmis + bulaniklastirilmis haliyle doldur
    # (modele renk/isik ipucu verir, sonuc daha tutarli olur)
    tuval = kirpik.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
    ust_serit = kirpik.crop((0, 0, W, 6)).resize((W, max(1, ust)), Image.BICUBIC).filter(ImageFilter.GaussianBlur(25))
    alt_yuk = H - ust - yuk
    alt_serit = kirpik.crop((0, yuk - 6, W, yuk)).resize((W, max(1, alt_yuk)), Image.BICUBIC).filter(ImageFilter.GaussianBlur(25))
    if ust > 0:
        tuval.paste(ust_serit, (0, 0))
    if alt_yuk > 0:
        tuval.paste(alt_serit, (0, ust + yuk))
    tuval.paste(kirpik, (0, ust))
    # maske: beyaz = yapay zeka doldursun. Fotografin icine 'kenar' kadar tasar ki dikis gorunmesin.
    maske = Image.new("L", (W, H), 255)
    ImageDraw.Draw(maske).rectangle([0, ust + ust_bindirme, W, ust + yuk - alt_bindirme], fill=0)
    maske = maske.filter(ImageFilter.GaussianBlur(kenar / 2))
    # geri yapistirma maskesi: orijinal piksel (urun dahil), bindirme bolgesinde genis yumusak gecis
    yapistir = Image.new("L", (W, yuk), 0)
    ImageDraw.Draw(yapistir).rectangle([0, int(ust_bindirme * 0.75), W, yuk - int(alt_bindirme * 0.75)], fill=255)
    yapistir = yapistir.filter(ImageFilter.GaussianBlur(max(kenar, min(ust_bindirme, alt_bindirme)) / 2.5))
    return tuval, maske, kirpik, yapistir, ust


def _istem(kategori):
    kat = (kategori or "").lower()
    oda = "bedroom" if "bed" in kat else "dining room" if "dining" in kat else "living room"
    return (f"photorealistic interior photograph of an elegant {oda}, seamless continuation of the same room, "
            f"same wall, same ceiling, same floor and rug continuing naturally, same lighting and colors, "
            f"empty space, high detail, 8k",
            "furniture, sofa, chair, table, bed, lamp, people, person, text, watermark, logo, frame, border, "
            "duplicate, distorted, blurry, lowres, cartoon, painting")


def dikey_genislet(yol, kutu=None, kategori="", adim=None, tohum=7):
    """Doner: 1080x1920 jpg yolu. Onbellekli."""
    yol = Path(yol)
    cikti = yol.with_name(yol.stem + "_v2_dikey.jpg")
    if cikti.exists():
        return cikti
    im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
    if im.height / im.width > 1.4:          # zaten dikey
        return yol
    tuval, maske, kirpik, yapistir, ust = tuval_ve_maske(im, kutu)
    import torch
    pipe = _pipe_yukle()
    pozitif, negatif = _istem(kategori)
    # SDXL'in bildigi cozunurlukte uret (768x1344 ~ 9:16), sonra 1080x1920'ye cik
    ug, uy = 768, 1344
    t0 = time.time()
    sonuc = pipe(prompt=pozitif, negative_prompt=negatif,
                 image=tuval.resize((ug, uy), Image.LANCZOS), mask_image=maske.resize((ug, uy), Image.LANCZOS),
                 width=ug, height=uy, strength=0.99, guidance_scale=6.5,
                 num_inference_steps=adim or ayar("adim", 28),
                 generator=torch.Generator("cpu").manual_seed(tohum)).images[0]
    sonuc = sonuc.resize((1080, 1920), Image.LANCZOS)
    # URUNU KORU: orijinal fotografi piksel piksel geri koy
    sonuc.paste(kirpik, (0, ust), yapistir)
    sonuc.save(cikti, quality=95, subsampling=0)
    # urun kutusunu yeni goruntuye tasi (algila modulu onbellekten okur)
    if kutu:
        olcek, x0, x1, ust_ = yerlesim(im.size, kutu)
        es = lambda x: max(0.0, min(1.0, (x * im.width - x0) * olcek / 1080))
        yeni = {"x0": es(kutu["x0"]), "x1": es(kutu["x1"]),
                "y0": (ust_ + kutu["y0"] * im.height * olcek) / 1920, "y1": (ust_ + kutu["y1"] * im.height * olcek) / 1920,
                "yontem": "rembg" if kutu.get("yontem") == "rembg" else "esleme"}
        yeni["cx"], yeni["cy"] = (yeni["x0"] + yeni["x1"]) / 2, (yeni["y0"] + yeni["y1"]) / 2
        cikti.with_name(cikti.name + ".kutu.json").write_text(json.dumps(yeni))
    yol.with_name(yol.stem + "_v2_dikey.json").write_text(json.dumps({
        "kaynak": yol.name, "ust": ust, "foto_yuk": kirpik.height, "sure_sn": round(time.time() - t0, 1)}))
    torch.cuda.empty_cache()
    return cikti


def bosalt():
    """Ekran kartı bellegini birak (gunun geri kalani icin)."""
    global _pipe, _esrgan
    _pipe = _esrgan = None
    try:
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:
        pass
