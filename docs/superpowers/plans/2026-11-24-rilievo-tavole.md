# Rilievo → Tavole — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Libreria Python + skill di sessione che trasforma schizzo/DWG/foto in un modello edificio tracciabile e da esso genera pianta, prospetti, sezioni (DWG 2018 + PDF), con controlli automatici e un banco di prova a casi inventati.

**Architecture:** Un modello unico (`edificio.yaml`, pydantic) → un modello 3D a facce (pareti con fori, falde) → un proiettore ortogonale con rimozione delle parti nascoste che alimenta prospetti e sezioni; la pianta deriva dai poligoni dei muri. Il disegno è fatto con ezdxf su layer standard, l'impaginazione su foglio con cartiglio, l'export con ODA (DWG) e matplotlib (PDF). Controlli e banco di prova leggono lo stesso modello.

**Tech Stack:** Python ≥3.11, ezdxf 1.4.5, shapely 2.x, pydantic 2, PyYAML, numpy, opencv-python-headless, pymupdf, matplotlib, pytest; ODAFileConverter 27.10 via `xvfb-run`.

**Spec:** `docs/superpowers/specs/2026-11-24-rilievo-tavole-design.md`

## Global Constraints
- Unità: metri, `$INSUNITS = 6`, DXF R2018; DWG in uscita AC1032 via ODA.
- Quote: testo 2,2 mm su carta, tick architettonici, virgola decimale, 2 decimali, arrotondamento HALF-UP al cm su ogni estremo (`decimal`).
- Spessori: tagliato 0,50 mm; contorni prospetto 0,50; visto 0,18; quote 0,18; terreno 0,70.
- Layer: MURI, TRAMEZZI, APERTURE, QUOTE, TESTI, PROSPETTI_CONTORNO, PROSPETTI_DETTAGLI, COPERTURA, TERRENO, SEZ_TAGLIATO, SEZ_VISTO, SEZ_TRATTEGGI, LINEE_SEZIONE, DEGRADO, IPOTESI_DA_VERIFICARE (colore 1 rosso), NOTE, CARTIGLIO.
- Ogni valore numerico del modello ha `fonte ∈ {misura, dwg, foto, calcolo, ipotesi}`; un numero nudo vale `misura`. Le geometrie che dipendono da un valore `ipotesi` vanno (anche) sul layer IPOTESI_DA_VERIFICARE.
- Testi e messaggi all'utente in italiano.
- Scala: 1:50 se l'ingombro max dell'edificio ≤ 20 m, altrimenti 1:100.

## Review Focus
1. Aperture in quote progressive che sforano la lunghezza del muro o si sovrappongono → errore di validazione chiaro, non disegno silenzioso (test in Task 1).
2. Muri non ortogonali (angoli qualsiasi, come nello schizzo reale) → pianta e prospetti corretti (test in Task 2 e 4 con un muro a 80°).
3. Locale sotto falda con H min/H max → altezza media ponderata e sezione coerente (test in Task 5).
4. Edificio a L / corpi di altezze diverse → nel prospetto il corpo più vicino nasconde il retro (test in Task 4).
5. Foto senza EXIF → la correzione dell'obiettivo stima la distorsione dalle linee, oppure la salta dichiarandolo nel report (test in Task 9).

---

### Task 1: Modello dati e I/O YAML

**Files:** Create `rilievo/__init__.py`, `rilievo/modello.py`, `pyproject.toml`; Test `tests/test_modello.py`

**Interfaces — Produces:**
- `class V(BaseModel)`: `valore: float`, `fonte: Fonte = "misura"`, `confidenza: float = 1.0`, `rif: str = ""`, `nota: str = ""`; un float nudo nel YAML si converte in `V`.
- `Muro`: `id`, `asse: list[tuple[float,float]]` (2 punti), `spessore: V`, `materiale: str`, `ruolo: Literal["portante","tramezzo"]`, `stato: Literal["esistente","demolire","nuovo"]="esistente"`, `altezza: V|None` (None = fino alla copertura).
- `Apertura`: `id`, `muro: str`, `da: V`, `a: V` (progressive dall'origine = primo punto dell'asse), `altezza: V`, `davanzale: V = 0`, `tipo: Literal["porta","finestra","varco","feritoia"]`, `forma: Literal["rettangolare","arco","arco_ribassato"]`, `freccia: V|None` (monta dell'arco).
- `Locale`: `id`, `nome`, `destinazione`, `punto: tuple` (punto interno), `h_min: V`, `h_max: V|None`, `soffitto: str`, `quota_pavimento: V = 0`.
- `Falda`: `id`, `poligono: list[tuple]`, `quote: list[V]` (z estradosso ai vertici), `spessore: V`, `manto: str`, `struttura: str`, `sporto: V = 0`.
- `Elemento` (forno, camino, pluviale, scala…), `Lesione` (`muro`, `punti: list[tuple[s,z]]`, `ampiezza_mm`), `Foto` (`file`, `punto`, `direzione_gradi`, `soggetto`).
- `Pratica` (anagrafica, `tipo`), `Edificio`: `pratica`, `nord_gradi`, `muri`, `aperture`, `locali`, `falde`, `elementi`, `lesioni`, `foto`, `quota_terreno: V = 0`.
- `carica(path) -> Edificio`, `salva(ed, path)`, `Edificio.valida() -> list[str]` (errori leggibili).

- [ ] Test: `test_numero_nudo_diventa_misura`, `test_roundtrip_yaml` (carica/salva/carica uguale), `test_apertura_fuori_muro_errore` (da=3.5, a=4.2 su muro lungo 4.0 → messaggio contiene "supera la lunghezza"), `test_aperture_sovrapposte_errore`.
- [ ] Implement; run `pytest tests/test_modello.py -v` → PASS; commit.

### Task 2: Geometria e modello 3D

**Files:** Create `rilievo/geometria.py`, `rilievo/modello3d.py`; Test `tests/test_geometria.py`

**Interfaces — Produces:**
- `poligoni_muri(ed) -> dict[str, Polygon]` (muri con giunti risolti per unione; aperture escluse), `pianta_piena(ed) -> Polygon|MultiPolygon` (unione), `poligono_locale(ed, loc) -> Polygon` (cella della differenza ingombro−muri che contiene `loc.punto`).
- `apertura_mondo(ed, ap) -> tuple[Point2, Point2]` (estremi sull'asse).
- `Faccia`: `pts: np.ndarray (n,3)`, `fori: list[np.ndarray]`, `tipo: str` (`parete_est`, `parete_int`, `falda`, `bordo_falda`, `terreno`, `infisso`), `materiale`, `rif_id`, `ipotesi: bool`.
- `facce(ed) -> list[Faccia]`: pareti esterne/interne come prismi da z=quota pavimento a profilo superiore (inviluppo delle falde lungo il lato), fori per le aperture (archi approssimati con 16 segmenti), falde come poligoni 3D + bordo con spessore.
- `perimetro_esterno(ed) -> list[tuple[Point2,Point2,normale]]`.

- [ ] Test: `test_area_locale_rettangolare` (6,35×3,70 → 23,50 m² ±0,01), `test_apertura_mondo_progressiva`, `test_muro_obliquo_80_gradi` (area e posizione aperture corrette), `test_parete_timpano_ha_punta` (muro sotto due falde → vertice alla quota di colmo).
- [ ] Implement; PASS; commit.

### Task 3: Stile DXF, quote, pianta

**Files:** Create `rilievo/dxf/stile.py`, `rilievo/dxf/quote.py`, `rilievo/genera/pianta.py`; Test `tests/test_pianta.py`

**Interfaces — Produces:**
- `nuovo_documento() -> ezdxf.Drawing` (layer, linetype, DIMSTYLE `RIL_50`/`RIL_100`, stile testo).
- `catena(msp, punti: list[Point2], direzione, offset, dimstyle) -> list[float]` (valori HALF-UP mostrati); `arrotonda(x) -> Decimal`.
- `disegna_pianta(ed, msp, origine=(0,0), scala=50) -> Ingombro` (bbox): muri con retino per materiale, aperture con arco di apertura porte, nomi locali + S m² + h, catene esterne (parziali + totale) per ogni lato, quote interne dei locali, linee di sezione, Nord, ±0,00.

- [ ] Test: `test_catena_somma_uguale_totale` (punti con decimali critici es. 0.125, 1.375 → somma mostrata = totale mostrato), `test_layer_presenti`, `test_testo_superficie_locale` ("S = 23,50 m²").
- [ ] Implement; PASS; commit.

### Task 4: Proiettore ortogonale e prospetti

**Files:** Create `rilievo/proiezione.py`, `rilievo/genera/prospetti.py`; Test `tests/test_prospetti.py`

**Interfaces — Produces:**
- `proietta(facce, direzione: np.ndarray, piano_taglio=None) -> list[Pezzo]` dove `Pezzo(poligono2d: Polygon, profondita: float, faccia: Faccia, tagliato: bool)`; rimozione nascoste: ordina per profondità, visibile = poligono − unione dei più vicini.
- `lati_prospetto(ed) -> list[Vista]` (`nome`: "Prospetto Sud", direzione, estremi cardinali sx/dx dal `nord_gradi`).
- `disegna_prospetto(ed, vista, msp, origine, scala) -> Ingombro`: contorni, aperture (con archi), falde con linee del manto, pluviali, terreno, quote di livello a sinistra (±0,00, davanzali, architravi, gronda, colmo), catena verticale a destra, nomi dei lati alle estremità.

- [ ] Test: `test_apertura_in_prospetto_coincide_con_pianta` (x e larghezza uguali ±1 mm), `test_corpo_avanti_nasconde_retro` (edificio a L), `test_quote_livello_gronda_colmo`.
- [ ] Implement; PASS; commit.

### Task 5: Sezioni

**Files:** Create `rilievo/genera/sezioni.py`; Test `tests/test_sezioni.py`

**Interfaces:** Consumes `proietta(..., piano_taglio=(p0,p1))`. Produces `LineaSezione(nome, p0, p1, verso)` nel modello (`Edificio.sezioni`), `disegna_sezione(ed, sez, msp, origine, scala) -> Ingombro`: muri tagliati spessi + ANSI31/pattern materiale, falda tagliata con spessore, struttura (travi in sezione come rettangoli), soffitto/cannucciato, terreno EARTH, visto oltre a tratto sottile, quote di livello e altezze nette dei locali (h min / h max / h media).

- [ ] Test: `test_muro_tagliato_spessore` (larghezza tagliato = spessore), `test_altezza_media_falda` (h_min 2,10 h_max 3,80 → testo "h media"), `test_nessun_visto_dietro_tagliato`.
- [ ] Implement; PASS; commit.

### Task 6: Tavola, cartiglio, tabelle, export

**Files:** Create `rilievo/genera/tavola.py`, `rilievo/genera/tabelle.py`, `rilievo/esporta.py`; Test `tests/test_esporta.py`

**Interfaces — Produces:**
- `componi_tavole(ed, profilo="rilievo") -> ezdxf.Drawing` (viste disposte senza sovrapposizioni in modelspace a scala carta, cartiglio, tabella superfici, riquadro NOTE con le ipotesi).
- `tabella_superfici(ed) -> list[RigaSup]` (S utile, h media, volume, RAI = S/8).
- `esporta(doc, cartella, nome) -> dict` con `dxf`, `dwg` (ODA via `xvfb-run -a ODAFileConverter in out ACAD2018 DWG 0 1`), `pdf`, `png`; `roundtrip_ok(dwg) -> bool` (conteggio entità uguale).

- [ ] Test: `test_dwg_ac1032_roundtrip` (skip se ODA assente), `test_pdf_creato`, `test_tabella_totali_somma_arrotondati`.
- [ ] Implement; PASS; commit.

### Task 7: Controlli e report

**Files:** Create `rilievo/verifica.py`; Test `tests/test_verifica.py`

**Interfaces — Produces:** `verifica(ed, doc) -> Report` (`righe: list[Controllo(nome, spiegazione, atteso, trovato, esito)]`), `Report.markdown()`. Controlli: catene=totali, aperture coerenti pianta↔prospetti, quote livello coerenti tra viste, progressive valide, testi sovrapposti (bbox dei TEXT/MTEXT), ipotesi sul layer giusto, roundtrip DWG.

- [ ] Test: `test_report_tutto_ok_su_caso_base`, `test_rileva_testi_sovrapposti`.
- [ ] Implement; PASS; commit.

### Task 8: Ingresso DWG

**Files:** Create `rilievo/ingresso/dwg.py`; Test `tests/test_ingresso_dwg.py`

**Interfaces — Produces:** `dwg_a_dxf(path) -> Path`; `analizza_pianta(doc) -> AnalisiDWG` (`muri: list[(asse, spessore)]` da coppie di linee parallele a distanza 0,08–0,90 m sovrapposte ≥0,3 m; `varchi: list[(muro_idx, da, a)]` dalle interruzioni; `testi`; `scala_stimata`), `bozza_modello(analisi) -> Edificio` (fonte `dwg`, altezze `ipotesi`), `anteprima_png(doc, path)`.

- [ ] Test: genera DWG da un modello noto (Task 6) e ritrova muri (spessore ±1 cm) e aperture (±1 cm).
- [ ] Implement; PASS; commit.

### Task 9: Foto — distorsione, raddrizzamento, misura

**Files:** Create `rilievo/foto/raddrizza.py`; Test `tests/test_foto.py`

**Interfaces — Produces:** `correggi_distorsione(img, k1=None) -> (img, k1, metodo)` (k1 da EXIF/parametro, altrimenti stima massimizzando la rettilineità dei segmenti lunghi LSD/Hough); `raddrizza(img, punti_px: 4×2, larghezza_m, altezza_m, px_per_m=200) -> img`; `misura(img_raddrizzata, p1, p2, px_per_m) -> float`; `pagina_punti(foto, out_html)` (HTML: clic su 4 punti → JSON copiabile).

- [ ] Test: su foto sintetica (Task 10) con k1 noto: dopo correzione+raddrizzamento la larghezza di una finestra ha errore < 2 cm; senza EXIF la stima di k1 riduce l'errore rispetto a nessuna correzione.
- [ ] Implement; PASS; commit.

### Task 10: Banco di prova (casi inventati)

**Files:** Create `rilievo/banco/caso.py`, `rilievo/banco/foto_sintetiche.py`, `rilievo/banco/schizzo.py`, `rilievo/banco/confronta.py`, `assets/fonts/Caveat.ttf`; Test `tests/test_banco.py`

**Interfaces — Produces:**
- `genera_caso(seed) -> Edificio` (rustico casuale: 3–4 locali in linea + annesso, muri 0,30–0,60 in pietra/blocchi, un muro obliquo, falde a capanna e a una falda, porta ad arco, finestre piccole, una lesione).
- `foto_facciata(ed, vista, out, k1=-0.15, rumore=True) -> dict` (render prospettico con texture intonaco/pietra, distorsione radiale; ritorna i punti veri degli angoli).
- `schizzo(ed, out_png, seed)`: pianta "stampata" grigia + misure a penna blu (Caveat, rotazioni e jitter), quote interne dei locali, progressive delle aperture dal punto 0, H min/H max, almeno 2 valori barrati e riscritti, 1 cifra ambigua, scarabocchi e un tramezzo cancellato con onda.
- `confronta(vero, letto) -> RapportoErrori` (per ogni grandezza: vero, letto, errore; aperture mancanti/extra).
- Truth salvata in `banco/<seed>/verita.yaml`, mai letta durante la lettura alla cieca.

- [ ] Test: `test_caso_valido` (valida() vuoto per 20 seed), `test_schizzo_png_creato`, `test_confronta_identico_zero`.
- [ ] Implement; PASS; commit.

### Task 11: CLI, skill di sessione, scheda di sopralluogo, guida

**Files:** Create `rilievo/cli.py` (entry `rilievo`), `rilievo/genera/scheda.py`, `.claude/skills/rilievo/SKILL.md`, `docs/guida/*.md`, `CLAUDE.md`, `README.md`

**Interfaces:** `rilievo nuova <codice>`, `rilievo zoom <img> x y w h --fattore 3`, `rilievo analizza-dwg <file>`, `rilievo genera <pratica> --profilo rilievo`, `rilievo verifica <pratica>`, `rilievo scheda <pratica|vuota>`, `rilievo banco <seed>`.

- [ ] Test: `test_cli_genera_su_caso` (produce dwg/pdf/report).
- [ ] Implement; PASS; commit.

### Task 12: Prove end-to-end e valutazione
- [ ] Prova A: DWG inventato + foto inventate → modello → tavole; confronto con la verità.
- [ ] Prova B: schizzo a penna inventato, lettura alla cieca da parte di Claude → domande → modello → tavole; confronto con la verità.
- [ ] Render PNG delle tavole e ispezione visiva; correzioni; report finale in `docs/prove/`.
