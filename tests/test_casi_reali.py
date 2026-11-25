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
C001 = Path(__file__).parents[1] / "pratiche" / "C001" / "modello" / "rilievo.yaml"
C002 = Path(__file__).parents[1] / "pratiche" / "C002" / "modello" / "rilievo.yaml"


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


# --- C001 (bottega da planimetria catastale, 25/11/2026): pianta per APE a 1:100. Al primo giro: 15 scritte
# sovrapposte nei locali piccoli, linee di sezione non richieste, quote totali doppie, ingresso tutto rosso
# anche se la larghezza era misurata, volume calcolato con 3,00 invece di 4,00, WC contato come residenziale.

@pytest.fixture(scope="module")
def c001():
    ed = costruisci(yaml.safe_load(C001.read_text(encoding="utf-8")))
    return ed, componi_tavole(ed, scala=100, tavole={"pianta"})


def test_c001_pianta_senza_scritte_sovrapposte(c001):
    from rilievo.verifica import testi_sovrapposti
    _, t = c001
    assert testi_sovrapposti(t.doc) == []


def test_c001_niente_linee_di_sezione_se_non_richieste(c001):
    _, t = c001
    assert len(t.doc.modelspace().query('*[layer=="LINEE_SEZIONE"]')) == 0


def test_c001_totali_esterni_una_volta_per_lato(c001):
    _, t = c001
    testi = [d.dxf.text for d in t.doc.modelspace().query("DIMENSION")]
    assert testi.count("4,95") == 2 and testi.count("7,65") == 2  # un totale per lato, non due


def test_c001_ingresso_misurato_disegnato_a_due_ante_e_non_rosso(c001):
    ed, t = c001
    msp = t.doc.modelspace()
    p1 = next(a for a in ed.aperture if a.id == "P1")
    assert p1.battente == "doppio" and abs(p1.larghezza - 2.31) < 0.005
    archi = [e for e in msp.query("ARC") if abs(e.dxf.radius * 1 - 2.31 / 2) < 0.01]
    assert len(archi) == 2
    rossi = [e for e in msp.query('LWPOLYLINE[layer=="IPOTESI_DA_VERIFICARE"]')
             if e.closed and abs(max(p[1] for p in e.get_points()) - min(p[1] for p in e.get_points()) - 2.31) < 0.02]
    assert not rossi  # rossa solo la sigla (altezza ipotizzata), non il vano misurato


def test_c001_superfici_e_volume_per_ape(c001):
    from rilievo.genera.tabelle import dati_generali
    ed, _ = c001
    dg = dati_generali(ed)
    assert float(dg.su) == 0.0  # bottega: anche WC e antibagno sono superficie non residenziale
    assert float(dg.snr) == pytest.approx(30.14, abs=0.01)
    assert float(dg.volume_vpp) == pytest.approx(float(dg.superficie_lorda) * 4.00, abs=0.05)  # h 4,00, non 3,00


# --- C002 (appartamento da planimetria catastale, 25/11/2026): il disimpegno largo 87 cm fu scambiato per un
# muro da 87 cm e due tramezzi si allungarono fino a metà corridoio, chiudendo lo spazio aperto.

def test_c002_niente_muri_dentro_i_locali():
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from rilievo.geometria import poligono_locale
    ed = costruisci(yaml.safe_load(C002.read_text(encoding="utf-8")))
    assert max(m.spessore.valore for m in ed.muri) <= 0.30 + 1e-6  # solo muri da 30 e tramezzi da 10
    dati = yaml.safe_load(C002.read_text(encoding="utf-8"))
    from shapely.geometry import box
    stanze = unary_union([box(d["origine"][0], d["origine"][1], d["origine"][0] + d["larghezza"],
                              d["origine"][1] + d["profondita"]) for d in dati["locali"]])
    for m in ed.muri:
        asse = LineString(m.asse)
        assert asse.intersection(stanze.buffer(-0.02)).length < 0.01, m.id  # nessun asse passa in un locale
