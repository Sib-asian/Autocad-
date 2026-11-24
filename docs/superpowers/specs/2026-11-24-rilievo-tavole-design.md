# Rilievo → Tavole: documento di progetto

Data: 2026-11-24 · Stato: approvato (l'utente ha delegato le scelte)

## 1. Perché

Un tecnico fa un sopralluogo. Torna con uno schizzo a mano con le misure prese (spesso su una
stampa di pianta, pieno di correzioni), le foto e a volte un DWG esistente. Oggi trasformare
tutto questo in pianta, prospetti e sezioni professionali richiede ore di CAD. Lo strumento
deve farlo con l'IA (Claude, in sessione) come operatore. Le tavole devono essere fedeli alla
realtà, coerenti tra loro, quotate e pronte per qualsiasi uso: sanatoria, CILA/SCIA/permesso,
perizia, rilievo dello stato di fatto, base di progetto.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Accettare qualsiasi combinazione di ingressi, in qualsiasi ordine, anche in più riprese:
  schizzo a mano o foto dello schizzo, DWG/DXF, PDF, foto del sopralluogo, misure dettate.
- Leggere con attenzione lo schizzo. **Quando un dato è dubbio, fare una domanda puntuale**
  invece di indovinare.
- Usare le foto come riferimento per ciò che manca (tetto, forma delle aperture, materiali,
  elementi in facciata) e come strumento di misura quando possibile.
- Produrre DWG (AutoCAD 2018), PDF in scala e DXF di riserva, con pianta, prospetti, sezioni
  e tavole accessorie per il tipo di pratica.
- Rendere ogni dato **tracciabile**: misurato, da DWG, da foto, calcolato o ipotizzato.

**Non obiettivi (per ora)**
- Calcoli strutturali, verifiche sismiche, computi metrici.
- Modello BIM/IFC completo (possibile più avanti, perché il modello unico lo permette).
- Firma o asseverazione: le tavole restano da verificare e firmare a cura del tecnico abilitato.

**Anti-obiettivi (lo strumento ha fallito anche se "funziona")**
- Un dato inventato in silenzio, disegnato come se fosse misurato.
- Pianta, prospetti e sezioni che non coincidono: aperture, quote di livello, larghezze.
- Catene di quote la cui somma non dà il totale; testi sovrapposti.
- Un DWG che AutoCAD non apre o apre con errori.

## 3. Vincoli

- Si lavora in una sessione cloud Linux. AutoCAD non è disponibile; il DWG si legge e si
  scrive con strumenti esterni.
- Rete: PyPI, ftp.gnu.org (LibreDWG) e opendesign.com (ODA File Converter) sono raggiungibili;
  github.com diretto no.
- Le foto caricate in chat arrivano compresse e **senza dati EXIF** (obiettivo, focale). Gli
  originali vanno caricati nel repository (`pratiche/<nome>/input/foto/`) quando serve misurare.
- Le foto di questo sopralluogo sono grandangolari 0,5x, scattate vicino e parzialmente coperte
  dalla vegetazione. Sono utili per proporzioni e dettagli, non per misure precise.
- Unità: metri, `$INSUNITS = 6`, 1 unità = 1 m.

## 4. Approcci considerati

| | Approccio | Pro | Contro |
|---|---|---|---|
| **A (scelto)** | Strumento in sessione: Claude + libreria Python nel repo + pagine web al volo per i passaggi manuali | Risultati reali subito, massima capacità dell'IA, nessun server | Serve una sessione di Claude Code |
| B | App web autonoma con API Claude | Usabile senza Claude Code, da collaboratori | Mesi in più, costi API e server; serve comunque il motore di A |
| C | Plugin AutoCAD (LISP/.NET) | Dentro lo strumento abituale | Solo Windows, IA difficile da integrare, non sviluppabile né testabile qui |

Scelta: **A**. Il motore (modello, generatori, controlli) è una libreria indipendente, così B
potrà riusarlo. L'utente ha delegato la scelta del "come" ("evolvi la mia idea in meglio").

## 5. Architettura

```
 ingressi                      cuore                          uscite
 ─────────                     ─────                          ──────
 schizzo (foto) ─┐                                       ┌─► pianta
 DWG / DXF / PDF ┼─► lettori ─► MODELLO EDIFICIO ─► generatori ┼─► prospetti
 foto sopralluogo┤   (+ domande   (YAML, ogni dato          ├─► sezioni
 misure dettate ─┘    all'utente)  con la sua fonte)        ├─► comparativa gialli/rossi
                                        │                   ├─► doc. fotografica, quadro fessurativo
                                        ▼                   └─► tabelle superfici/volumi
                                    CONTROLLI ──────────────────► DWG 2018 + PDF + DXF + registro
```

### 5.1 Il fascicolo della pratica
```
pratiche/<codice-pratica>/
  input/schizzi/  input/dwg/  input/foto/  input/misure.md
  modello/edificio.yaml        # unica fonte di verità
  modello/domande.md           # domande aperte e risposte (storico)
  output/                      # DWG, PDF, DXF, report di verifica
```

### 5.2 Il modello dell'edificio (`edificio.yaml`)
Schema validato con pydantic. Contenuti:
- **pratica**: committente, indirizzo, foglio/particella, tipo (rilievo | sanatoria | cila |
  scia | permesso | perizia | progetto), tecnico, data.
- **riferimenti**: origine (punto 0), orientamento del Nord, quota ±0,00.
- **locali**: nome, destinazione, poligono interno, quota del pavimento, altezze (minima,
  massima, media ponderata per i locali sotto falda), tipo di soffitto (es. cannucciato,
  orditura in legno a vista).
- **muri**: asse o poligono, spessore, materiale (pietra lavica, blocchi, laterizio...), ruolo
  (portante, tramezzo), stato (esistente | da demolire | nuovo).
- **aperture**: muro di appartenenza, **quote progressive dal punto 0** come misurate,
  larghezza, altezza, davanzale, forma (rettangolare, arco a tutto sesto o ribassato), tipo
  (porta, finestra, varco, feritoia), infisso.
- **coperture**: falde (poligono, pendenza o quote di gronda e colmo), struttura (travi,
  travicelli, listelli, coppi), sporti, gronde e pluviali.
- **elementi**: forno, camino, scale, canne fumarie, muretti esterni, pluviali.
- **degrado**: lesioni (parete, posizione, andamento, ampiezza stimata), distacchi di intonaco,
  umidità, mancanze. Ogni voce è collegata alle foto.
- **foto**: file, punto e direzione di scatto in pianta, elementi visibili.
- **stati**: `legittimo`, `fatto` e `progetto` come varianti dello stesso modello; la
  comparativa nasce dal confronto.

**Ogni valore numerico** porta con sé: `valore`, `fonte` (misura | dwg | foto | calcolo |
ipotesi), `confidenza`, `rif` (es. "schizzo, locale centrale" o "IMG_0863"), `nota`. Le
abbreviazioni sono ammesse: un numero senza fonte vale come `misura`.

### 5.3 Lettori (ingressi)
1. **Schizzo.** Claude legge l'immagine. Uno strumento di ritaglio e ingrandimento ad alta
   risoluzione aiuta sulle cifre dubbie. Claude scrive la trascrizione nel modello e mette in
   `domande.md` tutto ciò che è incerto: cifre illeggibili, segni ambigui (muro demolito?
   scala?), misure incoerenti. Regole di lettura: dimensioni interne dei locali, aperture in
   quote progressive dal punto 0, H min/max per i locali sotto falda.
2. **DWG.** Conversione in DXF con ODA File Converter (headless, xvfb); in alternativa
   LibreDWG compilato da ftp.gnu.org. Poi lettura con ezdxf: layer, muri (linee parallele),
   aperture (interruzioni, blocchi), testi, quote. Verifica della scala con un elemento noto.
3. **PDF.** Vettori con pymupdf, con verifica della scala di stampa.
4. **Foto.**
   - Correzione della distorsione dell'obiettivo: da EXIF quando c'è, altrimenti stimata
     dalle linee che devono essere dritte.
   - Raddrizzamento della facciata con 4 punti o con le linee di fuga, e scala da una misura
     nota del modello. Il raddrizzamento vale solo per superfici piane: per un muro
     irregolare non si inventa una precisione che non c'è.
   - Misure "da foto" con errore stimato, scritte nel modello con `fonte: foto`.
   - Riconoscimento di aperture, materiali, lesioni e pluviali con la visione di Claude, più
     OpenCV per rifinire bordi e linee.
   - I punti si scelgono con una pagina web: si apre la foto, si clicca, le coordinate
     tornano a Claude. Se la pagina non è disponibile, Claude propone i punti e li mostra
     su un'anteprima da confermare.
5. **Misure dettate** in chat ("davanzale finestra cucina 1,10"): Claude le scrive nel modello.

### 5.4 Generatori (uscite)
Tutti leggono solo il modello: la coerenza tra le viste è garantita per costruzione.
- **Pianta**: muri tagliati con retino per materiale, aperture con verso di apertura, nomi
  dei locali, superfici (shapely), altezze (min/max), quote interne ed esterne (catene
  parziali più totale), linee di sezione, Nord, quota ±0,00.
- **Prospetti** (uno per lato, generati automaticamente dal perimetro):
  - contorno, aperture dalle progressive, archi, davanzali e soglie;
  - copertura dalle quote di gronda e colmo, con coppi in vista e sporti;
  - pluviali e retini dei materiali, terreno;
  - quote di livello a sinistra e catene verticali a destra;
  - orientamento a ciascuna estremità (Est/Ovest...).
  - In opzione, foto raddrizzata in sottofondo su un layer separato.
- **Sezioni** (dalle linee di sezione decise in pianta):
  - elementi tagliati a tratto spesso con retino;
  - elementi visti a tratto sottile, con nascosto ciò che sta dietro i tagliati;
  - struttura del tetto (travi, travicelli, manto);
  - soffitti (es. cannucciato), solai, scale, terreno.
- **Comparativa** (sanatoria, CILA...): demolizioni in giallo, costruzioni in rosso,
  calcolate dal confronto tra gli stati.
- **Documentazione fotografica**: pianta con coni ottici numerati e tavola delle foto con
  didascalie.
- **Quadro fessurativo e del degrado**: lesioni e degradi sui prospetti e sulle sezioni, con
  legenda e rimando alle foto.
- **Tabelle**: superfici utili e non residenziali, altezze medie ponderate, volume vuoto per
  pieno, superficie coperta, rapporti aeroilluminanti (1/8). Sono i dati che servono per
  oneri, oblazione e verifiche igienico-sanitarie.
- **Cartiglio**: dati della pratica e del tecnico, scala, formato, data, revisione, e una
  nota sulle ipotesi.
- **Registro dati e ipotesi** (PDF/MD): l'elenco di ogni dato non misurato, con la sua fonte,
  da verificare.
- **Scheda di sopralluogo** (PDF stampabile): cosa misurare e come fotografare. Viene
  generata anche "su misura", elencando ciò che manca al modello di una pratica aperta.

### 5.5 Profili di uscita
Un profilo stabilisce quali tavole produrre e con che contenuti:
- `rilievo`: pianta, prospetti, sezioni, tabelle.
- `sanatoria` e `cila-scia-permesso`: stato legittimo, stato di fatto (o di progetto),
  comparativa, tabelle superfici e volumi.
- `perizia`: rilievo, quadro fessurativo, documentazione fotografica, registro.
- `progetto`: stato di fatto e stato di progetto.

### 5.6 Convenzioni grafiche
Seguono la procedura "tavole tecniche DWG" già in uso:
- layer separati per categoria (MURI, APERTURE, QUOTE, SEZ_TAGLIATO, SEZ_VISTO,
  IPOTESI_DA_VERIFICARE in rosso, ...);
- spessori: tagliato 0,50; contorni 0,50; visto 0,18; terreno 0,70;
- quote: testo 2,2 mm, tick architettonici, virgola decimale, arrotondamento HALF-UP al
  centimetro su ogni estremo;
- scale: 1:50 per edifici piccoli, 1:100 oltre i 20 m circa; formato A3/A2/A1 scelto in
  base all'ingombro.

### 5.7 Controlli automatici (prima di ogni consegna)
1. Le catene di quote sommano al totale.
2. Le superfici dei locali più muri e pilastri danno l'area lorda.
3. Coerenza tra pianta, prospetti e sezioni: stesse aperture (larghezza, altezza, posizione),
   stesse quote di livello; ciò che sporge dal tetto compare nei prospetti.
4. Le quote progressive sono crescenti e stanno dentro la lunghezza del muro.
5. Nessun testo sovrapposto (render a scala reale delle zone dense).
6. Round trip DXF → DWG → DXF con lo stesso numero di entità.
7. Nessun valore con `fonte: ipotesi` fuori dal layer delle ipotesi.

Il risultato è un **report di verifica** (elemento | atteso | disegnato | esito), consegnato
insieme alle tavole.

### 5.8 Come lavora Claude (procedura)
Una skill di progetto (`.claude/skills/rilievo/SKILL.md`) codifica la procedura, così ogni
nuova sessione in questo repo sa come procedere:
1. creare il fascicolo;
2. leggere gli ingressi;
3. trascrivere nel modello;
4. fare le domande, raggruppate e numerate;
5. generare le tavole;
6. lanciare i controlli;
7. consegnare DWG, PDF e report.

Una riga di comando `rilievo` espone i passi: `nuova`, `importa`, `genera`, `verifica`,
`esporta`, `scheda`.

### 5.9 Modalità tirocinante
L'utente è un tirocinante alle prime armi. Lo strumento quindi insegna mentre lavora:
- ogni domanda spiega perché il dato serve (es. "l'altezza della gronda serve per il
  prospetto e per il volume");
- il report di verifica spiega ogni controllo in una riga;
- `docs/guida/` contiene una guida breve: come si misura un rilievo, quote progressive, come
  fotografare una facciata, cosa contiene una pratica di sanatoria, CILA o perizia, e le
  convenzioni grafiche con il loro perché.

### 5.10 Banco di prova
Un generatore di casi inventati ma coerenti, a partire da un "edificio vero" casuale:
- un DWG di pianta "come quello di un collega";
- foto sintetiche in prospettiva delle facciate, con distorsione dell'obiettivo;
- uno schizzo a penna su pianta stampata, con misure a mano, correzioni e scarabocchi.

La verità resta in un file separato. Serve a misurare l'errore dello strumento, anche la
lettura "alla cieca" dello schizzo da parte di Claude.

## 6. Tecnologie
Python 3.11 o superiore:
- ezdxf: disegno DXF, quote, retini, render;
- shapely: aree e occlusioni nelle sezioni;
- pydantic e PyYAML: il modello;
- OpenCV e numpy: foto;
- pymupdf: PDF;
- matplotlib (backend di ezdxf): PDF in scala;
- ODA File Converter (headless): DWG 2018; LibreDWG come riserva;
- pytest per i test.

Verificato il 2026-11-24: ODA File Converter 27.10 (pacchetto .deb) funziona senza
interfaccia grafica, con `xvfb-run` e le librerie libopengl0/libegl1. Il giro
DXF → DWG AC1032 → DXF conserva il numero di entità (LWPOLYLINE, TEXT, DIMENSION, HATCH).
Il carattere a mano Caveat (licenza OFL) è scaricabile da cdn.jsdelivr.net.

## 7. Fasi
1. **Motore e primo caso reale** (il rustico di questo sopralluogo):
   - modello, lettura dello schizzo con le domande, pianta, prospetti e sezioni;
   - controlli; DWG, PDF e DXF.
2. **Foto**: correzione dell'obiettivo, raddrizzamento, misure da foto, pagina web per i
   punti, documentazione fotografica, quadro fessurativo.
3. **DWG/PDF in ingresso**: riconoscimento di muri e aperture da disegni esistenti.
4. **Profili di pratica**: comparativa gialli/rossi, tabelle superfici e volumi, scheda di
   sopralluogo.
5. (Facoltativa) **App web** sopra lo stesso motore.

## 8. Decisioni prese da me (da verificare)
- Interfaccia: sessione di Claude Code, senza app autonoma in questa fase.
- DWG in uscita: AutoCAD 2018 tramite ODA File Converter; LibreDWG (che scrive solo
  AutoCAD 2000) come riserva.
- Formato del modello: YAML leggibile e modificabile anche a mano.
- Scala predefinita: 1:50 per edifici piccoli come questo, 1:100 per quelli più grandi.
- Dati del tecnico e del cartiglio: richiesti alla prima tavola e poi salvati in
  `config/studio.yaml`.
- Le domande all'utente si fanno in blocco (numerate), non una alla volta, per non
  rallentare.

## 9. Lasciato a chi costruisce
- La struttura interna dei moduli e i nomi dei file Python.
- L'algoritmo di riconoscimento dei muri da DWG (fase 3).
- La scelta tra raddrizzamento a 4 punti e a linee di fuga, caso per caso.
