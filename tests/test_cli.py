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
    assert main(["genera", str(base), "--no-dwg"]) == 0
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
