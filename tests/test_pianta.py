from decimal import Decimal

from rilievo.dxf.quote import arrotonda, catena, fmt
from rilievo.dxf.stile import LAYER, nuovo_documento
from rilievo.genera.pianta import disegna_pianta


def _testi(doc):
    out = []
    for e in doc.modelspace():
        if e.dxftype() == "TEXT":
            out.append(e.dxf.text)
        elif e.dxftype() == "MTEXT":
            out.append(e.plain_text())
        elif e.dxftype() == "DIMENSION":
            out.append(e.dxf.text)
    return out


def test_arrotonda_half_up():
    assert arrotonda(0.125) == Decimal("0.13")
    assert arrotonda(2.005) == Decimal("2.01")
    assert arrotonda(2.00499) == Decimal("2.00")
    assert arrotonda(2.00499999999999) == Decimal("2.01")  # rumore numerico ~1e-14 trattato come 2,005
    assert fmt(Decimal("23.5")) == "23,50"


def test_catena_somma_uguale_totale():
    doc = nuovo_documento(50)
    c = catena(doc.modelspace(), [(0, 0), (0.125, 0), (1.375, 0), (2.005, 0), (3.0, 0)], (1, 0), 0.5, "RIL_50")
    assert sum(c.parziali) == c.totale
    assert c.parziali == [Decimal("0.13"), Decimal("1.25"), Decimal("0.63"), Decimal("0.99")]


def test_layer_presenti():
    doc = nuovo_documento(50)
    for nome in ["MURI", "APERTURE", "QUOTE", "TESTI", "IPOTESI_DA_VERIFICARE", "SEZ_TAGLIATO", "CARTIGLIO"]:
        assert nome in doc.layers
    assert doc.layers.get("IPOTESI_DA_VERIFICARE").color == 1
    assert doc.header["$INSUNITS"] == 6


def test_testo_superficie_locale(ed_scatola):
    doc = nuovo_documento(50)
    disegna_pianta(ed_scatola, doc.modelspace(), scala=50)
    assert any("S = 23,50 m²" in t for t in _testi(doc))


def test_quote_esterne_con_aperture(ed_scatola):
    doc = nuovo_documento(50)
    disegna_pianta(ed_scatola, doc.modelspace(), scala=50)
    t = _testi(doc)
    for atteso in ["1,40", "1,00", "1,50", "0,80", "2,45", "7,15"]:
        assert atteso in t, atteso


def test_ingombro_contiene_muri(ed_scatola):
    doc = nuovo_documento(50)
    ing = disegna_pianta(ed_scatola, doc.modelspace(), scala=50, origine=(100, 200))
    assert ing.minx < 100 - 0.4 and ing.maxx > 100 + 6.75
    assert ing.miny < 200 - 0.4


def test_testo_quote_leggibile():
    """Il testo delle quote non deve mai risultare capovolto (angolo in (-90, 90])."""
    doc = nuovo_documento(50)
    c = catena(doc.modelspace(), [(5, 0), (0, 0)], (-1, 0), 0.5, "RIL_50")
    c2 = catena(doc.modelspace(), [(0, 5), (0, 0)], (0, -1), 0.5, "RIL_50")
    for e in c.entita + c2.entita:
        ang = e.dxf.angle % 360
        assert ang <= 90 or ang > 270, ang
    # la quota resta dal lato richiesto (a sinistra di (-1,0) = sotto)
    assert c.entita[0].dxf.defpoint[1] < 0


def test_etichette_aperture(ed_scatola):
    doc = nuovo_documento(50)
    disegna_pianta(ed_scatola, doc.modelspace(), scala=50)
    t = _testi(doc)
    assert "F1 80x80 dav.120" in t
    assert "P1 100x220" in t


def test_catena_dei_vani_con_muro_interno():
    from conftest import scatola
    ed = scatola()
    ed.muri.append(ed.muri[0].model_copy(update={"id": "MI", "asse": [(3.0, -0.2), (3.0, 3.9)],
                                                  "spessore": ed.muri[0].spessore.model_copy(update={"valore": 0.3})}))
    doc = nuovo_documento(50)
    disegna_pianta(ed, doc.modelspace(), scala=50)
    t = _testi(doc)
    for atteso in ("0,40", "2,85", "0,30", "3,20", "7,15"):  # muro, vano, muro, vano, muro
        assert atteso in t, atteso


def test_catena_vani_coerente_con_totale_su_lato_storto():
    import math
    from rilievo.verifica import controlla_catene
    from rilievo.costruttore import costruisci
    ed = costruisci({"spessori": {"esterni": 0.15, "interni": 0.3},
                     "locali": [{"nome": "A", "larghezza": 4.68, "larghezza_nord": 4.39, "profondita": 3.16}]})
    doc = nuovo_documento(50)
    disegna_pianta(ed, doc.modelspace(), scala=50)
    assert controlla_catene(doc).esito == "OK"
