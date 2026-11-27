# T001: completare una tavola di un DWG esistente seguendo una tavola d'esempio

Pratica T001 (27/11/2026). Nel DWG del tecnico: una tavola d'esempio barrata (altra pratica), la TAV 1 da
completare ("noti cio' che manca"), la TAV 2 approvata da non toccare.

## Come si e' lavorato
- DWG -> DXF con ODA, rendering di tutto il modello per trovare le tavole (cornici) e la mappa catastale.
- Confronto esempio / tavola da completare: elenco di cio' che manca (piante quotate con nomi, superfici e
  altezze, linee di sezione, copertura con i coppi, tabella del condono, stralci con "IMMOBILE IN OGGETTO").
- Stile copiato dall'esempio: stile di testo, altezze dei testi, stile di quota, retino dei coppi (copia del
  retino esistente, con l'angolo giusto per il verso della falda), layer e tipo di linea delle sezioni.
- Lo stralcio catastale si ricava dalla mappa vettoriale nel file (ritaglio + scala 0,1 per 1:1000 su un foglio
  impaginato a 1:100).
- La geometria si prende dalla tavola approvata: la pianta grezza della tavola da completare era diversa.
- Controllo finale: la TAV 2 e l'esempio restano identici entita' per entita' (dopo il giro DWG -> DXF).

## Regole
1. Mai toccare cio' che l'utente dice "va bene": si verifica con un confronto automatico prima di consegnare.
2. Le tavole devono essere coerenti fra loro: se due piante dello stesso edificio differiscono, vale quella
   approvata e coerente con prospetti e sezioni; la differenza si dice all'utente.
3. Quello che non c'e' nel file (es. aerofotogrammetrico, dati dell'istanza) non si inventa: cornice pronta,
   nota su layer non stampabile, domanda all'utente.
4. Nessun nome del cliente nei file del repository (il repository e' pubblico).

## Esito
Consegna approvata dall'utente al primo giro ("impeccabile"): il metodo sopra e' quello da ripetere.
