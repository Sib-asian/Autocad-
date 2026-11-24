import pytest

from conftest import scatola
from rilievo.dxf.stile import nuovo_documento
from rilievo.genera.comparativa import differenze, differenze_da_stati, disegna_comparativa, stato_progetto
from rilievo.genera.tavola import componi_tavole

F1 = {"id": "F1", "muro": "MS", "da": 3.5, "a": 4.3, "altezza": 0.8, "davanzale": 1.2}
P1 = {"id": "P1", "muro": "MS", "da": 1.0, "a": 2.0, "altezza": 2.2, "tipo": "porta"}


def _area(g):
    return 0.0 if g is None or g.is_empty else g.area


def test_finestra_aperta_e_porta_chiusa():
    legittimo = scatola(aperture=[P1])
    fatto = scatola(aperture=[F1])
    dem, cos = differenze(legittimo, fatto)
    assert _area(dem) == pytest.approx(0.8 * 0.4, abs=1e-3)  # vano della finestra nuova: muro demolito
    assert _area(cos) == pytest.approx(1.0 * 0.4, abs=1e-3)  # porta tamponata: muro nuovo


def test_stati_nello_stesso_modello():
    ed = scatola(aperture=[dict(F1, stato="nuovo"), dict(P1, stato="demolire")])
    dem, cos = differenze_da_stati(ed)
    assert _area(dem) == pytest.approx(0.32, abs=1e-3)
    assert _area(cos) == pytest.approx(0.40, abs=1e-3)
    prog = stato_progetto(ed)
    assert [a.id for a in prog.aperture] == ["F1"]


def test_disegno_comparativa_su_layer_colorati():
    legittimo, fatto = scatola(aperture=[P1]), scatola(aperture=[F1])
    doc = nuovo_documento(50)
    disegna_comparativa(fatto, doc.modelspace(), 50, (0, 0), *differenze(legittimo, fatto))
    layers = {e.dxf.layer for e in doc.modelspace()}
    assert {"COMPARATIVA_DEMOLIZIONI", "COMPARATIVA_COSTRUZIONI"} <= layers
    assert doc.layers.get("COMPARATIVA_DEMOLIZIONI").color == 2


def test_profilo_sanatoria():
    legittimo, fatto = scatola(aperture=[P1]), scatola(aperture=[F1])
    t = componi_tavole(fatto, profilo="sanatoria", legittimo=legittimo)
    contenuti = [f.contenuto for f in t.fogli]
    assert contenuti[0].startswith("Stato legittimo") and "Comparativa" in contenuti[-1]
    assert any(c.startswith("Stato di fatto") for c in contenuti)


def test_profilo_cila_da_stati():
    ed = scatola(aperture=[dict(F1, stato="nuovo"), P1])
    t = componi_tavole(ed, profilo="cila")
    contenuti = [f.contenuto for f in t.fogli]
    assert any(c.startswith("Stato di progetto") for c in contenuti) and "Comparativa" in contenuti[-1]


def test_sanatoria_senza_legittimo_errore_chiaro():
    with pytest.raises(ValueError, match="stato legittimo"):
        componi_tavole(scatola(aperture=[F1]), profilo="sanatoria")
