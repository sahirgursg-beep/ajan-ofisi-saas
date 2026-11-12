"""Urun algilama: fotograftaki ana mobilyanin kutusunu bulur (0-1 arasi oranlarla).

1) rembg (U2Net/ISNet "ana nesne" modeli) kuruluysa onu kullanir - en isabetlisi.
2) Yoksa renk zitligi + kenar dokusu + merkez onceligiyle "belirginlik haritasi" cikarir.
3) Hicbiri olmazsa guvenli varsayilan: fotografin orta-alt kismi.
Sonuc fotografin yanina .kutu.json olarak onbelleklenir.
"""
import json
from pathlib import Path

from PIL import Image, ImageCms, ImageFilter, ImageOps

VARSAYILAN = {"x0": 0.15, "y0": 0.35, "x1": 0.85, "y1": 0.88, "yontem": "varsayilan"}
_rembg_oturum = None


def _kutu_maskeden(m, alt=0.04, ust=0.96):
    """Agirlikli maskeden yuzdelik dilimlerle kutu (tek tuk gurultu kutuyu buyutmesin)."""
    import numpy as np
    m = np.asarray(m, dtype=float)
    if m.sum() <= 0:
        return None
    h, w = m.shape
    xs, ys = m.sum(0), m.sum(1)
    cx, cy = np.cumsum(xs) / xs.sum(), np.cumsum(ys) / ys.sum()
    x0, x1 = np.searchsorted(cx, alt) / w, np.searchsorted(cx, ust) / w
    y0, y1 = np.searchsorted(cy, alt) / h, np.searchsorted(cy, ust) / h
    return {"x0": round(float(x0), 3), "y0": round(float(y0), 3), "x1": round(float(x1), 3), "y1": round(float(y1), 3)}


def _rembg_var():
    try:
        import importlib.util
        return importlib.util.find_spec("rembg") is not None
    except Exception:
        return False


def _rembg(im):
    global _rembg_oturum
    from rembg import new_session, remove  # isteğe bagli paket
    if _rembg_oturum is None:
        _rembg_oturum = new_session("isnet-general-use")
    k = im.copy()
    k.thumbnail((640, 640))
    maske = remove(k, session=_rembg_oturum, only_mask=True).convert("L")
    import numpy as np
    a = np.asarray(maske, dtype=float) / 255.0
    a[a < 0.35] = 0
    if a.mean() < 0.01:  # model bir sey bulamadi
        return None
    return _kutu_maskeden(a, 0.02, 0.98)


def _belirginlik(im):
    import numpy as np
    k = im.convert("RGB")
    k.thumbnail((320, 320))
    w, h = k.size
    lab_t = ImageCms.buildTransformFromOpenProfiles(ImageCms.createProfile("sRGB"), ImageCms.createProfile("LAB"),
                                                    "RGB", "LAB")
    lab = np.asarray(ImageCms.applyTransform(k.filter(ImageFilter.GaussianBlur(3)), lab_t), dtype=float)
    lab[..., 1:] -= 128
    lab[..., 1:] *= 1.8
    duz = lab.reshape(-1, 3)

    def uzaklik(ornekler, n=6):
        # ornek bolgenin en sik n rengine (kaba kumeleme) en yakin uzaklik
        ornekler = ornekler[:: max(1, len(ornekler) // 1500)]
        merkezler = ornekler[np.linspace(0, len(ornekler) - 1, n).astype(int)]
        for _ in range(6):
            et = np.argmin(((ornekler[:, None] - merkezler[None]) ** 2).sum(2), 1)
            merkezler = np.array([ornekler[et == i].mean(0) if (et == i).any() else merkezler[i] for i in range(n)])
        return np.sqrt(((duz[:, None] - merkezler[None]) ** 2).sum(2)).min(1).reshape(h, w)

    duvar = np.concatenate([lab[: h // 5].reshape(-1, 3), lab[: h // 2, : w // 12].reshape(-1, 3),
                            lab[: h // 2, -w // 12:].reshape(-1, 3)])
    zemin = lab[-h // 9:].reshape(-1, 3)
    # urun = ne duvara ne zemine benzeyen bolge
    farklilik = np.minimum(uzaklik(duvar), uzaklik(zemin, 4))
    gri = np.asarray(k.convert("L").filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(5)), dtype=float)
    norm = lambda x: (x - x.min()) / (np.ptp(x) + 1e-6)
    s = 0.75 * norm(farklilik) + 0.25 * norm(gri)
    yy, xx = np.mgrid[0:h, 0:w]
    # mobilya zemine oturur: dikeyde orta-alt, yatayda merkez agirlikli
    onc = np.exp(-(((xx / w - 0.5) / 0.38) ** 2 + ((yy / h - 0.62) / 0.24) ** 2) / 2)
    s = s * onc
    s[s < np.percentile(s, 80)] = 0
    return _kutu_maskeden(s, 0.05, 0.95)


def urun_kutusu(yol):
    yol = Path(yol)
    onbellek = yol.with_name(yol.name + ".kutu.json")
    if onbellek.exists():
        try:
            k = json.loads(onbellek.read_text(encoding="utf-8"))
            if k.get("yontem") == "rembg" or not _rembg_var():
                return k        # rembg sonradan kurulduysa eski tahmini yenile
        except Exception:
            pass
    im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
    kutu, yontem = None, "varsayilan"
    for ad, f in (("rembg", _rembg), ("belirginlik", _belirginlik)):
        try:
            kutu = f(im)
            if kutu and (kutu["x1"] - kutu["x0"]) > 0.08 and (kutu["y1"] - kutu["y0"]) > 0.08:
                yontem = ad
                break
            kutu = None
        except Exception:
            kutu = None
    kutu = dict(kutu or VARSAYILAN)
    kutu["yontem"] = yontem
    kutu["cx"] = round((kutu["x0"] + kutu["x1"]) / 2, 3)
    kutu["cy"] = round((kutu["y0"] + kutu["y1"]) / 2, 3)
    try:
        onbellek.write_text(json.dumps(kutu), encoding="utf-8")
    except Exception:
        pass
    return kutu
