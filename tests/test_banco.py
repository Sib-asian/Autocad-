import numpy as np
import pytest

from rilievo.banco.caso import genera_caso
from rilievo.banco.confronta import confronta
from rilievo.banco.foto_sintetiche import foto_facciata
from rilievo.banco.schizzo import schizzo
from rilievo.genera.prospetti import lati_prospetto


@pytest.mark.parametrize("seed", range(20))
def test_caso_valido(seed):
    ed = genera_caso(seed)
    assert ed.valida() == []
    assert 3 <= len(ed.locali) <= 5
    assert any(a.forma == "arco" for a in ed.aperture)
    assert ed.lesioni and ed.sezioni and ed.falde


def test_caso_riproducibile():
    assert genera_caso(7) == genera_caso(7)
    assert genera_caso(7) != genera_caso(8)


def test_confronta_identico_zero():
    ed = genera_caso(3)
    r = confronta(ed, ed)
    assert r.errore_max_cm == 0
    assert not r.mancanti and not r.in_piu


def test_confronta_vede_errore():
    ed = genera_caso(3)
    altro = ed.model_copy(deep=True)
    ap = altro.aperture[0]
    altro.aperture[0] = ap.model_copy(update={"a": ap.a.model_copy(update={"valore": ap.a.valore + 0.05})})
    r = confronta(ed, altro)
    assert r.errore_max_cm == pytest.approx(5, abs=0.01)


def test_schizzo_png_creato(tmp_path):
    ed = genera_caso(1)
    p = schizzo(ed, tmp_path / "s.png", seed=1)
    from PIL import Image
    im = Image.open(p)
    assert im.size[0] >= 1800


def test_foto_facciata_punti_veri(tmp_path):
    ed = genera_caso(2)
    v = [x for x in lati_prospetto(ed) if x.nome == "Prospetto Sud"][0]
    info = foto_facciata(ed, v, tmp_path / "f.jpg", k1=-0.12, seed=2)
    assert (tmp_path / "f.jpg").exists()
    pts = np.array(info["angoli_facciata_px"])
    assert pts.shape == (4, 2)
    w, h = info["dimensioni"]
    assert (pts[:, 0] > 0).all() and (pts[:, 0] < w).all()
