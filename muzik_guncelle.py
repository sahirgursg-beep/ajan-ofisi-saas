"""Muzik kutuphanesini simdi doldurur ve listeler: python muzik_guncelle.py [parca_sayisi_her_ruh]"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from ofis import muzik  # noqa: E402

hedef = int(sys.argv[1]) if len(sys.argv) > 1 else None
print("Openverse'ten sadece CC0 / CC BY (ticari kullanima acik) parcalar araniyor...\n")
n = muzik.guncelle(hedef)
k = muzik.kutuphane()
print(f"\n{n} yeni parca indirildi. Kutuphanede toplam {len(k)} parca:")
for ruh in ("sakin", "enerjik", "festival"):
    print(f"\n[{ruh}]")
    for x in [x for x in k if x["ruh"] == ruh]:
        print(f"  {x['lisans'].upper():4} {x['sure_sn']:>5.0f} sn  \"{x['baslik']}\" - {x['sanatci']}  ({x['kaynak']})")
print("\nLisans kayitlari: muzik/otomatik/kutuphane.json")
