---
name: rilievo
description: Trasforma il materiale di un sopralluogo in tavole tecniche (pianta, prospetti, sezioni in DWG e PDF). Usala quando l'utente carica uno schizzo con misure a mano, una pianta DWG/DXF/PDF o foto di un edificio, oppure chiede prospetti, sezioni, una sanatoria, una CILA/SCIA, una perizia o una scheda di sopralluogo.
---

# Rilievo → tavole

L'utente e' un tirocinante: parla in italiano semplice e spiega il *perche'* di ogni domanda e di ogni scelta.
Lo strumento e' il pacchetto `rilievo` di questo repository (`rilievo --help`); il modello unico
`pratiche/<codice>/modello/edificio.yaml` e' la sola fonte di verita': ogni tavola nasce da li'.

## Cosa consegnare: lo decide l'utente, ogni volta

- Fai solo le tavole che chiede: a volte solo la pianta (es. per un APE), a volte stato di fatto + progetto, a volte
  prospetti e sezioni. `rilievo genera <pratica> --tavole pianta` (oppure `pianta,prospetti`, `sezioni`, ...).
  Se la richiesta non e' chiara su cosa produrre, chiedi prima di disegnare.
- Consegna di norma solo il **DWG, ordinato e pulito** (layer con nome, niente entita' inutili). Il PDF solo se lo
  chiede (`--pdf`). Le anteprime PNG in `output/anteprime/` servono a te per controllare, non si consegnano.

## Planimetrie catastali vecchie (anni '70 e simili)

Disegni imprecisi: interpretali con buon senso da tecnico, non ricalcarli.
- Una riga singola tra due locali e' un **tramezzo da 10 cm**: disegnalo con le due facce.
- Le linee storte per l'imprecisione del disegno vanno **raddrizzate**: muri ortogonali e allineati, salvo
  che la storpiatura sia reale (lo dicono le misure o le foto).
- Ogni scelta interpretativa va nelle domande o tra le ipotesi; i casi dubbi si discutono con l'utente.
- PDF catastale: e' una scansione. La scala si prende dalla barra vettoriale "10 metri" del PDF; si misura con i
  profili dei pixel; muri dello spessore indicato dall'utente centrati sugli assi del catastale.
- Per un APE consegna anche `rilievo genera <pratica> --tavole pianta --ape`: pianta solo geometria, in metri, in
  formato AutoCAD 2000 (i programmi APE come Blumatica non aprono il DWG 2018), un solo layer bianco, linee
  normali, niente quote ne' scritte. Lezioni: `docs/lezioni/C001-...`, `C002-...`.
- Catastale storto: raddrizzarlo prima di misurare (angolo dalla nitidezza delle proiezioni dei pixel).

## Passi

1. **Pratica.** `rilievo nuova <codice>`; copia gli input in `input/schizzi`, `input/dwg`, `input/foto`
   (le foto originali dal repo hanno gli EXIF; quelle in chat no). Fatto quando ogni file caricato sta nel fascicolo.
2. **Lettura.** Per ogni input:
   - schizzo: segui [lettura-schizzo.md](lettura-schizzo.md);
   - DWG/DXF: `rilievo analizza-dwg <file> --out modello/bozza_dwg.yaml`, poi guarda l'anteprima e correggi la bozza;
   - foto: assegna ogni foto a facciata o locale; per misurare usa `rilievo punti` + `rilievo raddrizza`.
   Fatto quando ogni numero e ogni segno dell'input e' trascritto nel modello oppure e' una domanda aperta.
3. **Domande.** Scrivi in `modello/domande.md` e in chat le domande numerate, raggruppate, ognuna con il motivo
   ("serve per..."). Ogni valore che resta incerto entra nel modello con `fonte: ipotesi` e una `nota`.
   Fatto quando non resta nessun dato inventato in silenzio.
4. **Modello.** Scrivi il rilievo per locali in `modello/rilievo.yaml` (come si misura: locali con dimensioni
   interne e posizione reciproca, spessori, aperture con progressive dal punto 0, coperture con H min/H max;
   esempio `esempi/rilievo_caso_2031.yaml`) e lancia `rilievo costruisci <pratica>`: muri, falde e sezioni
   si calcolano da soli. Le coperture si prendono dalle altezze scritte dall'utente (H min sul lato basso,
   H max sul lato alto): non reinterpretarle dalle foto e non inventare sporti o elementi che non ha dato
   (`sporto: 0` se non e' indicato). Dove due tetti si incontrano il piu' alto poggia sul muro in comune.
   Scrivi `edificio.yaml` a mano solo per forme che la descrizione per locali non copre
   (schema: `rilievo/modello.py`). `rilievo verifica <pratica>` deve dare "Dati del modello: OK".
   Pratiche con piu' stati: `legittimo.yaml` (sanatoria) o `progetto.yaml` (CILA/SCIA/permesso) accanto a
   `edificio.yaml`, oppure `stato: demolire|nuovo` su muri e aperture; il tipo di pratica sceglie le tavole.
5. **Tavole.** `rilievo genera <pratica>`. Apri i PNG in `output/` e guardali davvero: quote leggibili, nessuna
   scritta coperta, prospetti coerenti con la pianta. Correggi e rigenera finche' il report e' senza ERRORE.
   Prima di consegnare prospetti e sezioni (la prima consegna deve essere quella giusta):
   - guarda il DXF anche come lo vede l'utente in AutoCAD (sfondo nero, colori dei layer), non solo il PNG;
   - ogni prospetto: si distinguono muro, testa del tetto e manto; nessuna linea storta, doppia o di pochi cm;
     nessuna parete interna visibile; niente sporti, coppi, travi o altri elementi che l'utente non ha dato;
   - totali dei prospetti = misure esterne della pianta; stesse quote di gronda e colmo in prospetti e sezioni;
   - se qualcosa non torna, si corregge il programma (con un test) prima di consegnare, non dopo.
   Errori gia' fatti e da non ripetere: `docs/lezioni/R001-errori-da-non-ripetere.md` (leggerlo prima).
6. **Consegna.** Invia solo il DWG pulito delle tavole richieste (PDF solo se l'utente lo chiede). Nel messaggio: cosa c'e', i controlli
   superati con i numeri, l'elenco delle ipotesi da verificare, e che le tavole vanno firmate da un tecnico abilitato.
7. **Lezione.** Finita la pratica: lezione in `docs/lezioni/`, test del caso reale, controllo automatico se
   l'errore si può riconoscere, regole nuove qui. Procedura completa in `docs/lezioni/README.md`.

## Regole che non si piegano

- Quote progressive: la misura e' la distanza dal punto 0, non il parziale. Nel modello `da`/`a` sono progressive
  dal `zero` del muro (lo spigolo interno da cui si e' misurato).
- Le dimensioni scritte dentro un locale sono **interne**; gli assi dei muri si ricavano aggiungendo meta' spessore.
- Un valore barrato non vale; vale quello riscritto accanto. Una cifra illeggibile e' una domanda, mai una stima.
- Profili di pratica e contenuti tipici: [../../../docs/guida/pratiche.md](../../../docs/guida/pratiche.md).
