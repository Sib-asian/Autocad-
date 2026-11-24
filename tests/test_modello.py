from pathlib import Path

from rilievo.modello import Edificio, V, carica, salva

BASE = """
pratica: {codice: T1, tipo: rilievo}
muri:
  - {id: M1, asse: [[0, 0], [4, 0]], spessore: 0.4, materiale: pietra}
aperture:
  - {id: F1, muro: M1, da: 1.0, a: 1.8, altezza: 1.2, davanzale: 0.9, tipo: finestra}
"""


def _ed(testo=BASE):
    import yaml
    return Edificio.model_validate(yaml.safe_load(testo))


def test_numero_nudo_diventa_misura():
    ed = _ed()
    sp = ed.muri[0].spessore
    assert isinstance(sp, V)
    assert sp.valore == 0.4 and sp.fonte == "misura"


def test_valore_con_fonte_ipotesi():
    ed = _ed(BASE.replace("altezza: 1.2", "altezza: {valore: 1.2, fonte: ipotesi, nota: da foto}"))
    assert ed.aperture[0].altezza.fonte == "ipotesi"


def test_roundtrip_yaml(tmp_path: Path):
    ed = _ed()
    p = tmp_path / "e.yaml"
    salva(ed, p)
    assert carica(p) == ed


def test_apertura_fuori_muro_errore():
    ed = _ed(BASE.replace("da: 1.0, a: 1.8", "da: 3.5, a: 4.2"))
    errori = ed.valida()
    assert any("supera la lunghezza" in e for e in errori)


def test_aperture_sovrapposte_errore():
    testo = BASE + "  - {id: F2, muro: M1, da: 1.5, a: 2.5, altezza: 1.2, tipo: finestra}\n"
    errori = _ed(testo).valida()
    assert any("si sovrappone" in e for e in errori)


def test_caso_valido_senza_errori():
    assert _ed().valida() == []


def test_apertura_su_muro_inesistente():
    errori = _ed(BASE.replace("muro: M1", "muro: M9")).valida()
    assert any("M9" in e for e in errori)
