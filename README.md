# Rilievo → Tavole

Dal materiale di un sopralluogo (schizzo con misure a mano, pianta DWG/DXF, foto) alle tavole tecniche:
**pianta, prospetti, sezioni** in **DWG (AutoCAD 2018)**, **PDF in scala** e DXF, con cartiglio, tabella delle
superfici, legenda, note sulle ipotesi e un **report di verifica** automatico. Pensato per lavorare in una
sessione con Claude, che legge gli schizzi, fa le domande e guida lo strumento (vedi `CLAUDE.md`).

## Installazione

```bash
pip install -e .[test]
# DWG: ODA File Converter (gratuito) + display virtuale
sudo apt-get install -y ./ODAFileConverter_QT6_lnxX64_*.deb xvfb libopengl0 libegl1
```
Senza ODA lo strumento produce comunque DXF e PDF (il DXF si apre in AutoCAD).

## Uso

```bash
rilievo nuova P001                 # crea pratiche/P001 con il modello vuoto
rilievo analizza-dwg pianta.dwg    # bozza del modello da un DWG esistente
rilievo genera pratiche/P001       # tavole DWG/PDF + verifica + registro ipotesi
rilievo scheda -                   # scheda di sopralluogo da stampare
rilievo punti foto.jpg             # pagina per cliccare i punti su una foto
rilievo raddrizza foto.jpg p.json  # raddrizza la facciata e misura
rilievo banco 7                    # caso di prova inventato (schizzo, DWG, foto)
```

## Come e' fatto

`edificio.yaml` (modello unico, ogni dato con la sua fonte) → modello 3D a facce → proiezione ortogonale con
parti nascoste → pianta, prospetti, sezioni con ezdxf → impaginazione → DWG/PDF → controlli.
Dettagli: `docs/superpowers/specs/2026-11-24-rilievo-tavole-design.md`. Guida: `docs/guida/`.

Font Caveat (scrittura a mano del banco di prova): SIL Open Font License, `assets/fonts/OFL-Caveat.txt`.
