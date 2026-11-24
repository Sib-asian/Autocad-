import pytest

from rilievo.modello import Edificio


def scatola(lx=6.35, ly=3.70, sp=0.40, colmo=4.0, gronda=3.0, aperture=None, sporto=0.0):
    """Locale rettangolare con dimensioni interne lx * ly e tetto a capanna (colmo parallelo a x)."""
    h = sp / 2
    x0, y0, x1, y1 = -h, -h, lx + h, ly + h
    muri = [
        {"id": "MS", "asse": [[x0, y0], [x1, y0]], "spessore": sp, "zero": h},  # sud (in basso)
        {"id": "ME", "asse": [[x1, y0], [x1, y1]], "spessore": sp, "zero": h},
        {"id": "MN", "asse": [[x1, y1], [x0, y1]], "spessore": sp, "zero": h},
        {"id": "MO", "asse": [[x0, y1], [x0, y0]], "spessore": sp, "zero": h},
    ]
    ym = ly / 2
    e = sp + sporto
    falde = [
        {"id": "F1", "poligono": [[-e, -e], [lx + e, -e], [lx + e, ym], [-e, ym]],
         "quote": [gronda, gronda, colmo, colmo]},
        {"id": "F2", "poligono": [[-e, ym], [lx + e, ym], [lx + e, ly + e], [-e, ly + e]],
         "quote": [colmo, colmo, gronda, gronda]},
    ]
    return Edificio.model_validate({
        "muri": muri,
        "aperture": aperture or [],
        "locali": [{"id": "L1", "nome": "Deposito", "punto": [1, 1], "h_min": 2.1, "h_max": 3.8}],
        "falde": falde,
    })


@pytest.fixture
def ed_scatola():
    return scatola(aperture=[
        {"id": "P1", "muro": "MS", "da": 1.0, "a": 2.0, "altezza": 2.2, "tipo": "porta", "forma": "arco"},
        {"id": "F1", "muro": "MS", "da": 3.5, "a": 4.3, "altezza": 0.8, "davanzale": 1.2},
    ])
