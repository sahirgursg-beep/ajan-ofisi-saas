"""Haftalik plan toplantisi: Performans Analisti ogrenimleri gunceller, Pazarlama Uzmani 7 gunluk plani cikarir.
    python planla.py [--demo] [--baslangic 2026-11-11]
"""
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ofis import fiyat, pano, urun_cekici  # noqa: E402
from ofis.ajanlar import tum_ekip  # noqa: E402


def main():
    pano.kur()
    ekip = tum_ekip()
    Y, U, P, A = ekip["Yonetici"], ekip["UrunSorumlusu"], ekip["PazarlamaUzmani"], ekip["PerformansAnalisti"]
    Y.soyle("Herkes", "Haftalik plan toplantisi basliyor. Once performansa bakalim, sonra gelecek haftayi planlayalim.")
    A.analiz()
    from ofis import plan
    tercih = plan.tercih_oku()                      # ofis ekraninda sectiginiz kategoriler
    adaylar = U.urunleri_getir(demo="--demo" in sys.argv)
    if tercih.get("kategoriler") and "--demo" not in sys.argv:
        tum = urun_cekici.tum_onbellekten()          # secim, varsayilan kategori filtresinin disinda da olabilir
        secili = [u for u in tum if any(plan.eslesir(u, k) for k in tercih["kategoriler"])]
        adaylar = secili or adaylar
    if not adaylar:
        Y.soyle("Herkes", "Urun listesi alinamadi, plan yapilamadi.", "hata")
        return 1
    for u in adaylar:
        fiyat.hazirla(u)
    if tercih.get("kategoriler"):
        P.soyle("Yonetici", "Sectiginiz kategorilerle calisiyorum: " + ", ".join(tercih["kategoriler"])
                + (" | gunlere ozel: " + ", ".join(k for k in tercih.get("gunler", []) if k) if any(tercih.get("gunler", [])) else ""))
    bas = sys.argv[sys.argv.index("--baslangic") + 1] if "--baslangic" in sys.argv else None
    P.haftalik_plan(adaylar, date.fromisoformat(bas) if bas else None,
                    tercih.get("kategoriler"), tercih.get("gunler"))
    Y.soyle("Herkes", "Plan ofis ekranindaki 📅 Plan sekmesinde. Onaylayin, isterseniz urun degistirin.", "rapor")
    Y.bitir("Plan toplantisi bitti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
