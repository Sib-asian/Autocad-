import math

import numpy as np
import pytest

from rilievo.geometria import apertura_mondo, perimetro_esterno, poligono_locale, poligoni_muri
from rilievo.modello import Edificio
from rilievo.modello3d import facce
from conftest import scatola


def test_area_locale_rettangolare():
    ed = scatola()
    p = poligono_locale(ed, ed.locali[0])
    assert p.area == pytest.approx(6.35 * 3.70, abs=0.005)


def test_angoli_muri_chiusi():
    ed = scatola()
    from shapely.ops import unary_union
    u = unary_union(list(poligoni_muri(ed, con_aperture=False).values()))
    # ingombro esterno pieno: (6.35+0.8) x (3.70+0.8)
    assert u.envelope.area == pytest.approx(7.15 * 4.50, abs=1e-6)
    assert u.area == pytest.approx(7.15 * 4.50 - 6.35 * 3.70, abs=1e-6)


def test_apertura_mondo_progressiva():
    ed = Edificio.model_validate({
        "muri": [{"id": "M", "asse": [[0, 0], [4, 0]], "spessore": 0.4, "zero": 0.2}],
        "aperture": [{"id": "A", "muro": "M", "da": 1.0, "a": 1.8, "altezza": 1}],
    })
    p0, p1 = apertura_mondo(ed, ed.aperture[0])
    assert p0 == pytest.approx((1.2, 0.0)) and p1 == pytest.approx((2.0, 0.0))


def test_muro_obliquo_80_gradi():
    a = math.radians(80)
    fine = (3 * math.cos(a), 3 * math.sin(a))
    ed = Edificio.model_validate({
        "muri": [{"id": "M", "asse": [[0, 0], list(fine)], "spessore": 0.3}],
        "aperture": [{"id": "A", "muro": "M", "da": 1.0, "a": 2.0, "altezza": 1}],
    })
    p0, p1 = apertura_mondo(ed, ed.aperture[0])
    assert p0 == pytest.approx((math.cos(a), math.sin(a)))
    assert math.dist(p0, p1) == pytest.approx(1.0)
    assert poligoni_muri(ed, con_aperture=False)["M"].area == pytest.approx(0.9)
    assert poligoni_muri(ed, con_aperture=True)["M"].area == pytest.approx(0.6)


def test_parete_timpano_ha_punta():
    ed = scatola(colmo=4.0, gronda=3.0)
    ovest = [f for f in facce(ed) if f.tipo == "parete_est" and f.rif_id == "MO"]
    assert ovest, "manca la parete esterna ovest"
    pts = np.vstack([f.pts for f in ovest])
    zmax = pts[:, 2].max()
    sp_falda = 0.25
    assert zmax == pytest.approx(4.0 - sp_falda, abs=0.01)
    # la punta sta a meta' (y = 3.70/2)
    y_punta = pts[np.argmax(pts[:, 2]), 1]
    assert y_punta == pytest.approx(1.85, abs=0.06)


def test_fori_in_parete_esterna(ed_scatola):
    sud = [f for f in facce(ed_scatola) if f.tipo == "parete_est" and f.rif_id == "MS"]
    assert len(sud) == 1
    assert len(sud[0].fori) == 2
    finestra = [h for h in sud[0].fori if h[:, 2].min() > 1.0][0]
    assert finestra[:, 2].min() == pytest.approx(1.2) and finestra[:, 2].max() == pytest.approx(2.0)
    assert np.ptp(finestra[:, 0]) == pytest.approx(0.8)


def test_perimetro_normali_verso_esterno():
    ed = scatola()
    lati = perimetro_esterno(ed)
    assert len(lati) == 4
    for p0, p1, n in lati:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        # il centro del locale e' dalla parte opposta alla normale
        cx, cy = 3.175, 1.85
        assert (mx - cx) * n[0] + (my - cy) * n[1] > 0
