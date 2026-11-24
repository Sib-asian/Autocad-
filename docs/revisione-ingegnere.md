# Revisione dello strumento "da ingegnere" (24/11/2026)

Ho usato lo strumento come lo userebbe un tecnico in studio: caso completo (rustico con annesso),
tavole in uscita, e poi le domande che farebbero un collega, un ufficio tecnico comunale o un CTU.

## Cosa regge gia' bene
- Coerenza tra pianta, prospetti e sezioni (nascono dallo stesso modello).
- Quote che tornano al centimetro, dati ipotizzati in rosso, report di verifica.
- Lettura di schizzi, DWG esistenti e foto con dichiarazione dell'incertezza.

## Cosa mancava, in ordine di importanza

| # | Mancanza | Chi la nota | Cosa serve |
|---|---|---|---|
| 1 | La tabella superfici dava solo la superficie finestrata **minima**, non quella **reale**: nessuna verifica vera del rapporto aeroilluminante | ufficio tecnico, ASL | per ogni locale: finestre che vi affacciano, superficie reale, esito 1/8; altezza minima per destinazione (2,70 / 2,40); superficie lorda, coperta, volume vuoto per pieno |
| 2 | In pianta le aperture non avevano la sigla L x H e davanzale | chiunque legga la pianta | etichetta su ogni apertura (es. "F1 80x120 dav. 110") |
| 3 | Il profilo di pratica non cambiava nulla; mancava la **comparativa gialli/rossi** | sanatoria, CILA, SCIA | stato legittimo + stato di fatto/progetto + comparativa calcolata dal confronto |
| 4 | Mancavano **documentazione fotografica** (coni ottici) e **quadro fessurativo** con tabella delle lesioni | perizie, CTU, sanatorie | punti di ripresa numerati in pianta, tavola delle foto, tabella lesioni con ampiezza |
| 5 | Trascrivere lo schizzo nel modello richiedeva di calcolare a mano gli assi dei muri | chi usa lo strumento (errori!) | descrivere il rilievo come si misura: locali, dimensioni interne, spessori, aperture con progressive; i muri si calcolano da soli |
| 6 | In sezione il tetto era una fascia unica | collega, strutturista | stratigrafia: manto, tavolato/listelli, travi principali in sezione |
| 7 | Dati del tecnico nel cartiglio da scrivere ogni volta | studio | file `config/studio.yaml` |

## Fuori da questo giro (da fare quando servira')
- Tavole in layout di AutoCAD con finestre in scala (oggi i fogli sono nello spazio modello, in scala reale:
  si stampano con "finestra" alla scala 1:50).
- Inquadramento: stralcio catastale, ortofoto, PRG.
- Piu' piani (scale, solai intermedi): il modello oggi descrive un piano terra con copertura.
