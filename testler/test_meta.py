"""Meta Graph API hata cevaplarinin okunmasi ve engel tespiti (ag yok)."""
import pytest

from ofis import meta


class Cevap:
    def __init__(self, kod, govde=None, metin=""):
        self.status_code, self._g, self.text = kod, govde, metin

    def json(self):
        if self._g is None:
            raise ValueError("json degil")
        return self._g


def test_meta_hata_mesaji_kod_ve_alt_kod_icerir():
    with pytest.raises(meta.MetaHata) as e:
        meta._cevap(Cevap(400, {"error": {"message": "Invalid OAuth access token", "code": 190, "error_subcode": 463}}))
    assert "(kod 190, alt kod 463)" in str(e.value)
    assert meta.engel_mi(str(e.value))


def test_json_olmayan_cevap():
    with pytest.raises(meta.MetaHata, match="HTTP 502"):
        meta._cevap(Cevap(502, None, "<html>Bad gateway</html>"))


def test_basarili_cevap():
    assert meta._cevap(Cevap(200, {"id": "123"})) == {"id": "123"}


@pytest.mark.parametrize("metin,engel", [
    ("Application request limit reached (kod 4)", True),
    ("User request limit reached (kod 17)", True),
    ("API access blocked. (kod 200)", True),
    ("Error validating access token: Session has expired", True),
    ("(#100) Invalid parameter (kod 100)", False),
    ("Media upload failed (kod 9004)", False),
])
def test_engel_tespiti(metin, engel):
    assert meta.engel_mi(metin) is engel


def test_baglanti_yoksa_bagli_degil(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "AYAR_DOSYA", tmp_path / "meta.json")
    assert meta.bagli() is False
    meta.ayar_kaydet({"page_token": "t", "page_id": "p"})
    assert meta.bagli() is True
