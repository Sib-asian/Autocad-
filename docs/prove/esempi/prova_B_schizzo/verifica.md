# Report di verifica

| Controllo | Perche' serve | Atteso | Trovato | Esito |
|---|---|---|---|---|
| Dati del modello | progressive crescenti, aperture dentro i muri, niente doppioni | 0 errori | 0 errori | OK |
| Catene di quote | la somma delle quote parziali deve dare il totale scritto | somme = totali | 3 catene verificate, 0 errori | OK |
| Aperture pianta/prospetti | ogni finestra o porta deve avere la stessa misura in pianta e in prospetto | differenze <= 2 mm | 7 aperture confrontate | OK |
| Quota di colmo | il colmo deve essere alla stessa quota in tutte le viste | +3,85 in prospetti e sezioni | 5 etichette +3,85 | OK |
| Testi sovrapposti | una scritta coperta da un'altra non si legge in stampa | 0 | 0 | OK |
| Dati ipotizzati | cio' che non e' misurato deve essere evidenziato in rosso e verificato | tutte in rosso e nelle note | 12 dati ipotizzati, 70 elementi in rosso | ATTENZIONE |
| File DWG | il DWG riletto deve contenere gli stessi oggetti del disegno | stesso numero di entita' | uguale | OK |

## Aperture pianta/prospetti

- 3 aperture interne non compaiono nei prospetti (normale)

## Dati ipotizzati

- T1: quote[0] = 2.81 (copertura da H min/H max: colmo e spessore da verificare)
- T1: quote[1] = 2.81 (copertura da H min/H max: colmo e spessore da verificare)
- T1: quote[2] = 3.85 (copertura da H min/H max: colmo e spessore da verificare)
- T1: quote[3] = 3.85 (copertura da H min/H max: colmo e spessore da verificare)
- T2: quote[0] = 3.85 (copertura da H min/H max: colmo e spessore da verificare)
- T2: quote[1] = 3.85 (copertura da H min/H max: colmo e spessore da verificare)
- T2: quote[2] = 2.81 (copertura da H min/H max: colmo e spessore da verificare)
- T2: quote[3] = 2.81 (copertura da H min/H max: colmo e spessore da verificare)
- T3: quote[0] = 2.89 (falda dell'annesso da H max/H min)
- T3: quote[1] = 2.89 (falda dell'annesso da H max/H min)
- T3: quote[2] = 2.09 (falda dell'annesso da H max/H min)
- T3: quote[3] = 2.09 (falda dell'annesso da H max/H min)
