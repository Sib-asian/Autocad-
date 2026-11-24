from pathlib import Path

from rilievo.banco.caso import genera_caso
from rilievo.cli import main
from rilievo.modello import carica, salva


def test_cli_nuova_e_genera(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["nuova", "P001"]) == 0
    base = tmp_path / "pratiche" / "P001"
    assert (base / "modello" / "edificio.yaml").exists()
    salva(genera_caso(4), base / "modello" / "edificio.yaml")
    assert main(["genera", str(base), "--no-dwg", "--pdf"]) == 0
    out = base / "output"
    assert (out / "P001.pdf").exists() and (out / "P001.dxf").exists()
    assert "Report di verifica" in (out / "verifica.md").read_text()
    assert (out / "registro_ipotesi.md").exists()


def test_cli_scheda_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["nuova", "P002"])
    base = tmp_path / "pratiche" / "P002"
    salva(genera_caso(5), base / "modello" / "edificio.yaml")
    assert main(["scheda", str(base)]) == 0
    assert (base / "output" / "scheda_sopralluogo.pdf").exists()


def test_cli_zoom(tmp_path):
    import cv2
    import numpy as np
    img = tmp_path / "a.png"
    cv2.imwrite(str(img), np.full((100, 200, 3), 255, np.uint8))
    assert main(["zoom", str(img), "10", "10", "50", "40", "--fattore", "3", "--out", str(tmp_path / "z.png")]) == 0
    assert cv2.imread(str(tmp_path / "z.png")).shape[:2] == (120, 150)


def test_cli_sanatoria_con_legittimo(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from conftest import scatola
    monkeypatch.chdir(tmp_path)
    main(["nuova", "S001"])
    base = tmp_path / "pratiche" / "S001"
    fatto = scatola(aperture=[{"id": "F1", "muro": "MS", "da": 3.5, "a": 4.3, "altezza": 0.8, "davanzale": 1.2}])
    fatto.pratica.tipo = "sanatoria"
    salva(fatto, base / "modello" / "edificio.yaml")
    assert main(["genera", str(base), "--no-dwg"]) == 2  # manca lo stato legittimo: messaggio chiaro
    salva(scatola(), base / "modello" / "legittimo.yaml")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "studio.yaml").write_text("tecnico: Ing. Prova\n")
    assert main(["genera", str(base), "--no-dwg"]) == 0


def test_cli_costruisci(tmp_path, monkeypatch):
    import shutil
    esempio = Path(__file__).parents[1] / "esempi" / "rilievo_caso_2031.yaml"
    monkeypatch.chdir(tmp_path)
    main(["nuova", "C001"])
    base = tmp_path / "pratiche" / "C001"
    shutil.copy(esempio, base / "modello" / "rilievo.yaml")
    assert main(["costruisci", str(base)]) == 0
    from rilievo.modello import carica
    assert len(carica(base / "modello" / "edificio.yaml").aperture) == 10


def test_cli_solo_pianta_senza_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["nuova", "APE1"])
    base = tmp_path / "pratiche" / "APE1"
    salva(genera_caso(4), base / "modello" / "edificio.yaml")
    assert main(["genera", str(base), "--no-dwg", "--tavole", "pianta"]) == 0
    out = base / "output"
    assert (out / "APE1.dxf").exists() and not (out / "APE1.pdf").exists()
    import ezdxf
    testi = [e.dxf.text for e in ezdxf.readfile(out / "APE1.dxf").modelspace().query("TEXT")]
    assert any("TAV. 1 - PIANTA" in t for t in testi) and not any("PROSPETTI" in t for t in testi)
