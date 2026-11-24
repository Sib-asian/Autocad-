import numpy as np
import pytest

from rilievo.dxf.stile import nuovo_documento
from rilievo.genera.prospetti import disegna_prospetto, lati_prospetto
from rilievo.modello import Edificio
from rilievo.modello3d import facce
from rilievo.proiezione import proietta
from test_pianta import _testi


def _vista(ed, nome):
    return [v for v in lati_prospetto(ed) if v.nome == nome][0]


def test_quattro_prospetti_con_estremi_cardinali(ed_scatola):
    viste = {v.nome: v for v in lati_prospetto(ed_scatola)}
    assert set(viste) == {"Prospetto Sud", "Prospetto Nord", "Prospetto Est", "Prospetto Ovest"}
    assert (viste["Prospetto Nord"].sinistra, viste["Prospetto Nord"].destra) == ("EST", "OVEST")
    assert (viste["Prospetto Sud"].sinistra, viste["Prospetto Sud"].destra) == ("OVEST", "EST")


def test_apertura_in_prospetto_coincide_con_pianta(ed_scatola):
    v = _vista(ed_scatola, "Prospetto Sud")
    pezzi = proietta(facce(ed_scatola), v.direzione)
    inf = [p for p in pezzi if p.faccia.tipo == "infisso" and p.faccia.rif_id == "F1"]
    assert len(inf) == 1
    x0, z0, x1, z1 = inf[0].poligono2d.bounds
    assert (x0, x1) == pytest.approx((3.5, 4.3), abs=1e-3)
    assert (z0, z1) == pytest.approx((1.2, 2.0), abs=1e-3)


def test_corpo_avanti_nasconde_retro():
    def box(pref, y0, y1, h):
        pts = [(0, y0), (5, y0), (5, y1), (0, y1)]
        return [{"id": f"{pref}{i}", "asse": [list(pts[i]), list(pts[(i + 1) % 4])], "spessore": 0.3,
                 "altezza": h} for i in range(4)]
    muri = box("A", 0, 3, 2.5) + box("B", 3, 8, 5.0)
    muri = [m for m in muri if m["id"] != "B0"]  # muro in comune: A2 (y=3)
    for m in muri:
        if m["id"] == "A2":
            m["altezza"] = 5.0
    ed = Edificio.model_validate({"muri": muri})
    pezzi = proietta(facce(ed), np.array([0.0, 1.0, 0.0]))
    retro = [p for p in pezzi if abs(p.faccia.pts[:, 1].mean() - 2.85) < 1e-6 and p.faccia.normale[1] < -0.9]
    assert retro, "la parte alta del muro posteriore deve essere visibile"
    zmin = min(p.poligono2d.bounds[1] for p in retro)
    zmax = max(p.poligono2d.bounds[3] for p in retro)
    assert zmin == pytest.approx(2.5, abs=1e-6) and zmax == pytest.approx(5.0)


def test_quote_livello_gronda_colmo(ed_scatola):
    doc = nuovo_documento(50)
    disegna_prospetto(ed_scatola, _vista(ed_scatola, "Prospetto Ovest"), doc.modelspace(), scala=50)
    t = _testi(doc)
    assert "±0,00" in t
    assert "+4,00" in t  # colmo
    assert "+3,00" in t  # gronda (estradosso)


def test_muro_obliquo_in_prospetto():
    import math
    a = math.radians(80)
    ed = Edificio.model_validate({
        "muri": [{"id": "M", "asse": [[0, 0], [3 * math.cos(a), 3 * math.sin(a)]], "spessore": 0.3, "altezza": 3},
                 {"id": "N", "asse": [[3 * math.cos(a), 3 * math.sin(a)], [5, 3 * math.sin(a)]], "spessore": 0.3,
                  "altezza": 3}],
        "aperture": [{"id": "A", "muro": "M", "da": 1.0, "a": 2.0, "altezza": 1, "davanzale": 1}],
    })
    # vista perpendicolare al muro obliquo
    n = np.array([math.sin(a), -math.cos(a), 0.0])  # normale destra dell'asse
    pezzi = proietta(facce(ed), -n)
    inf = [p for p in pezzi if p.faccia.tipo == "infisso"]
    assert inf
    x0, _, x1, _ = inf[0].poligono2d.bounds
    assert x1 - x0 == pytest.approx(1.0, abs=1e-6)


def test_lesione_solo_sulla_facciata_del_muro(ed_scatola):
    from rilievo.modello import Lesione
    ed = ed_scatola.model_copy(deep=True)
    ed.lesioni.append(Lesione(id="L1", muro="MS", punti=[(2.3, 2.4), (2.4, 1.2)]))
    for v in lati_prospetto(ed):
        doc = nuovo_documento(50)
        disegna_prospetto(ed, v, doc.modelspace(), scala=50)
        presente = any(e.dxf.layer == "DEGRADO" for e in doc.modelspace())
        assert presente == (v.nome == "Prospetto Sud"), v.nome


def test_quote_livello_vicine_non_si_accavallano():
    from rilievo.dxf.stile import mm
    from rilievo.genera.pianta import _Penna
    from rilievo.genera.prospetti import _quote_livello
    doc = nuovo_documento(50)
    P = _Penna(doc.modelspace(), (0, 0), 50)
    _quote_livello(P, [0.0, 2.2, 4.10, 4.17], 0.0, 50)
    zs = sorted(e.dxf.insert.y for e in doc.modelspace().query("TEXT"))
    assert all(b - a >= mm(4.5, 50) - 1e-9 for a, b in zip(zs, zs[1:])), zs
    testi = {e.dxf.text for e in doc.modelspace().query("TEXT")}
    assert "+4,17" in testi and "±0,00" in testi  # estremi sempre presenti
