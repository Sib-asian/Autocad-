from rilievo.dxf.stile import nuovo_documento
from rilievo.dxf.stile import testo as scrivi
from rilievo.genera.tavola import componi_tavole
from rilievo.modello import LineaSezione
from rilievo.verifica import testi_sovrapposti as sovrapposti
from rilievo.verifica import verifica


def _ed(ed_scatola):
    ed = ed_scatola.model_copy(deep=True)
    ed.sezioni.append(LineaSezione(nome="A", p0=(3, -1), p1=(3, 4.7)))
    return ed


def test_report_tutto_ok_su_caso_base(ed_scatola):
    ed = _ed(ed_scatola)
    t = componi_tavole(ed)
    rep = verifica(ed, t)
    errori = [c for c in rep.righe if c.esito == "ERRORE"]
    assert not errori, rep.markdown()
    nomi = {c.nome for c in rep.righe}
    assert {"Catene di quote", "Aperture pianta/prospetti", "Testi sovrapposti", "Dati del modello"} <= nomi
    assert "| Controllo |" in rep.markdown()


def test_rileva_testi_sovrapposti():
    doc = nuovo_documento(50)
    msp = doc.modelspace()
    scrivi(msp, "DEPOSITO", (0, 0), 3, 50)
    scrivi(msp, "CUCINA", (0.02, 0.01), 3, 50)
    scrivi(msp, "LONTANO", (10, 10), 3, 50)
    assert len(sovrapposti(doc)) == 1


def test_rileva_catena_sbagliata(ed_scatola):
    ed = _ed(ed_scatola)
    t = componi_tavole(ed)
    dims = [d for d in t.doc.modelspace().query("DIMENSION") if d.dxf.text == "7,15"]
    dims[0].dxf.text = "7,25"  # errore introdotto a mano
    rep = verifica(ed, t)
    riga = [c for c in rep.righe if c.nome == "Catene di quote"][0]
    assert riga.esito == "ERRORE"


def test_nessun_testo_sovrapposto_su_caso_banco():
    from rilievo.banco.caso import genera_caso
    for seed in (4, 2031):
        ed = genera_caso(seed)
        t = componi_tavole(ed)
        assert sovrapposti(t.doc) == [], seed


def test_note_raggruppate():
    from rilievo.genera.tavola import righe_note
    from rilievo.modello import Edificio
    ed = Edificio.model_validate({"falde": [{"id": "T1", "poligono": [[0, 0], [1, 0], [1, 1]],
        "quote": [{"valore": 3, "fonte": "ipotesi", "nota": "da verificare"}] * 3}]})
    righe = righe_note(ed)
    assert len([r for r in righe if r.startswith("T1")]) == 1
