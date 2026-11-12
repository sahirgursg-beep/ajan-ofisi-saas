"""Iscinin musteri sureci icinde calistirdigi kucuk komutlar (ofis/ paketini o musteri icin ice aktarir).
Kullanim: AJAN_MUSTERI=<id> AJAN_MUSTERILER_KOK=<gecici> python -m saas.ofis_kopru <komut> [arguman]

  iptaller          -> paneldeki karar sonrasi 'bekleyen_iptal' listesindeki Facebook planlarini Meta'dan siler
  kaldir <klasor>   -> kullanicinin 'Kaldir' istegi: icerigi Meta'dan kaldirir
"""
import json
import sys


def iptaller():
    from ofis import meta, yayin
    from ofis.ayarlar import CIKTI
    hata = 0
    for k in sorted(CIKTI.iterdir()) if CIKTI.exists() else []:
        y_yol = k / "yayin.json"
        if not y_yol.exists():
            continue
        y = json.loads(y_yol.read_text(encoding="utf-8"))
        kalan = []
        for nid in y.get("bekleyen_iptal") or []:
            try:
                if meta.bagli():
                    meta.sil(nid)
                print(f"{k.name}: Meta planı iptal edildi ({nid})")
            except Exception as e:
                if "(kod 100" in str(e) or "does not exist" in str(e):
                    print(f"{k.name}: {nid} Meta'da zaten yok")
                else:
                    kalan.append(nid)
                    hata += 1
                    print(f"{k.name}: {nid} iptal edilemedi: {e}")
        if (y.get("bekleyen_iptal") or []) != kalan:
            if kalan:
                y["bekleyen_iptal"] = kalan
            else:
                y.pop("bekleyen_iptal", None)
            y_yol.write_text(json.dumps(y, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if hata else 0


def kaldir(klasor):
    from ofis import yayin
    try:
        yayin.kaldir(klasor)
        print(f"{klasor}: yayından kaldırıldı")
        return 0
    except Exception as e:
        print(f"{klasor}: kaldırma hatası: {e}")
        return 1


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "iptaller":
        sys.exit(iptaller())
    if komut == "kaldir" and len(sys.argv) > 2:
        sys.exit(kaldir(sys.argv[2]))
    print(__doc__)
    sys.exit(2)
