"""Veri katmani: web ve isci yalnizca bu arayuzu kullanir.

  yerel    -> SQLite + klasor (gelistirme ve testler; internet gerekmez)
  supabase -> Supabase Postgres (REST/PostgREST) + Supabase Storage (bulut)

Iki arka uc ayni testlerden gecer; birinde calisan kod digerinde de calisir.
"""
from .. import ayar
from .taban import Cakisma, Depo  # noqa: F401

_depo = None


def depo():
    global _depo
    if _depo is None:
        if ayar.DEPO == "supabase":
            from .supabase import SupabaseDepo
            _depo = SupabaseDepo(ayar.SUPABASE_URL, ayar.SUPABASE_SERVIS_ANAHTARI, ayar.DEPO_KOVA)
        else:
            from .yerel import YerelDepo
            _depo = YerelDepo(ayar.YEREL_KLASOR)
    return _depo


def ayarla(d):
    """Testler icin: belirli bir depo nesnesi kullan."""
    global _depo
    _depo = d
