---
name: rilievo
description: Trasforma il materiale di un sopralluogo in tavole tecniche (pianta, prospetti, sezioni in DWG e PDF). Usala quando l'utente carica uno schizzo con misure a mano, una pianta DWG/DXF/PDF o foto di un edificio, oppure chiede prospetti, sezioni, una sanatoria, una CILA/SCIA, una perizia o una scheda di sopralluogo.
---

# Rilievo → tavole

L'utente e' un tirocinante: parla in italiano semplice e spiega il *perche'* di ogni domanda e di ogni scelta.
Lo strumento e' il pacchetto `rilievo` di questo repository (`rilievo --help`); il modello unico
`pratiche/<codice>/modello/edificio.yaml` e' la sola fonte di verita': ogni tavola nasce da li'.

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
4. **Modello.** Completa `edificio.yaml` (schema: `rilievo/modello.py`). `rilievo verifica <pratica>` deve dare
   "Dati del modello: OK". Aggiungi sempre almeno due `sezioni` (una trasversale al colmo, una longitudinale)
   che passino per porte o finestre significative.
5. **Tavole.** `rilievo genera <pratica>`. Apri i PNG in `output/` e guardali davvero: quote leggibili, nessuna
   scritta coperta, prospetti coerenti con le foto. Correggi e rigenera finche' il report e' senza ERRORE.
6. **Consegna.** Invia DWG + PDF + `verifica.md` + `registro_ipotesi.md`. Nel messaggio: cosa c'e', i controlli
   superati con i numeri, l'elenco delle ipotesi da verificare, e che le tavole vanno firmate da un tecnico abilitato.

## Regole che non si piegano

- Quote progressive: la misura e' la distanza dal punto 0, non il parziale. Nel modello `da`/`a` sono progressive
  dal `zero` del muro (lo spigolo interno da cui si e' misurato).
- Le dimensioni scritte dentro un locale sono **interne**; gli assi dei muri si ricavano aggiungendo meta' spessore.
- Un valore barrato non vale; vale quello riscritto accanto. Una cifra illeggibile e' una domanda, mai una stima.
- Profili di pratica e contenuti tipici: [../../../docs/guida/pratiche.md](../../../docs/guida/pratiche.md).
