"""Casi reali da non sbagliare mai piu'.

R001 (rustico, 24/11/2026): prospetti e sezioni rifatti molte volte. Errori trovati: pareti interne visibili nei
prospetti, gronde che sparivano, linee storte e dentelli negli angoli, totali diversi dalla pianta, tetti
reinterpretati dalle foto invece che presi dalle altezze scritte dall'utente. Questo test rigenera R001 e
pretende tavole pulite e coerenti con la pianta.
"""
from pathlib import Path

import pytest
import yaml

from rilievo.costruttore import costruisci
from rilievo.genera.tavola import componi_tavole
from rilievo.verifica import verifica

R001 = Path(__file__).parents[1] / "pratiche" / "R001" / "modello" / "rilievo.yaml"


@pytest.fixture(scope="module")
def r001():
    ed = costruisci(yaml.safe_load(R001.read_text(encoding="utf-8")))
    return ed, componi_tavole(ed, tavole={"prospetti", "sezioni"})


def test_r001_tetti_come_scritti_in_pianta(r001):
    ed, _ = r001
    alte = sorted(round(max(q.valore - f.spessore.valore for q in f.quote), 2) for f in ed.falde)
    assert len(ed.falde) == 3 and all(f.poligono for f in ed.falde)
    assert max(alte) >= 3.80  # H max 3,80 di Vano 1 e Vano 2 (piu' la pendenza sopra il muro)


def test_r001_verifica_senza_errori(r001):
    ed, t = r001
    rep = verifica(ed, t)
    errori = [(c.nome, c.dettagli[:3]) for c in rep.righe if c.esito == "ERRORE"]
    assert not errori
    nomi = {c.nome: c for c in rep.righe}
    assert nomi["Prospetti puliti"].esito == "OK"
    assert nomi["Catene di quote"].trovato.split()[0] != "0"


def test_r001_totali_dei_prospetti_uguali_alla_pianta(r001):
    _, t = r001
    testi = [d.dxf.text for d in t.doc.modelspace().query("DIMENSION")]
    # 0,35 + 6,35 + 0,35 + 3,85 + 0,45 = 11,35 (sud, nord, sezione A); 0,49 + 3,71 + 0,60 + 3,16 + 0,15 = 8,11
    assert testi.count("11,35") >= 2 and testi.count("8,11") >= 2
    assert "11,36" not in testi and "8,12" not in testi
