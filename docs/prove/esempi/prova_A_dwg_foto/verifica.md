# Report di verifica

| Controllo | Perche' serve | Atteso | Trovato | Esito |
|---|---|---|---|---|
| Dati del modello | progressive crescenti, aperture dentro i muri, niente doppioni | 0 errori | 0 errori | OK |
| Catene di quote | la somma delle quote parziali deve dare il totale scritto | somme = totali | 3 catene verificate, 0 errori | OK |
| Aperture pianta/prospetti | ogni finestra o porta deve avere la stessa misura in pianta e in prospetto | differenze <= 2 mm | 5 aperture confrontate | OK |
| Quota di colmo | il colmo deve essere alla stessa quota in tutte le viste | +4,32 in prospetti e sezioni | 5 etichette +4,32 | OK |
| Testi sovrapposti | una scritta coperta da un'altra non si legge in stampa | 0 | 0 | OK |
| Dati ipotizzati | cio' che non e' misurato deve essere evidenziato in rosso e verificato | tutte in rosso e nelle note | 23 dati ipotizzati, 84 elementi in rosso | ATTENZIONE |
| File DWG | il DWG riletto deve contenere gli stessi oggetti del disegno | stesso numero di entita' | uguale | OK |

## Aperture pianta/prospetti

- 2 aperture interne non compaiono nei prospetti (normale)

## Dati ipotizzati

- A3: altezza = 2.50 (da foto, incertezza +/- 19 cm: misurare)
- A4: altezza = 2.10 (altezza tipica porta)
- A5: altezza = 1.20 (altezza tipica finestra)
- A5: davanzale = 0.90 (davanzale tipico)
- A7: altezza = 2.10 (altezza tipica porta)
- forno: h_min = 2.70 (altezza non presente nel DWG)
- CUCINA: h_min = 2.70 (altezza non presente nel DWG)
- PALMENTO: h_min = 2.70 (altezza non presente nel DWG)
- T1: quote[0] = 3.27 (gronda e colmo da foto, spessore ipotizzato)
- T1: quote[1] = 3.27 (gronda e colmo da foto, spessore ipotizzato)
- T1: quote[2] = 4.32 (gronda e colmo da foto, spessore ipotizzato)
- T1: quote[3] = 4.32 (gronda e colmo da foto, spessore ipotizzato)
- T1: spessore = 0.30 (ipotizzato)
- T2: quote[0] = 4.32 (gronda e colmo da foto, spessore ipotizzato)
- T2: quote[1] = 4.32 (gronda e colmo da foto, spessore ipotizzato)
- T2: quote[2] = 3.27 (gronda e colmo da foto, spessore ipotizzato)
- T2: quote[3] = 3.27 (gronda e colmo da foto, spessore ipotizzato)
- T2: spessore = 0.30 (ipotizzato)
- T3: quote[0] = 2.90 (annesso non misurato)
- T3: quote[1] = 2.90 (annesso non misurato)
- T3: quote[2] = 2.45 (annesso non misurato)
- T3: quote[3] = 2.45 (annesso non misurato)
- T3: spessore = 0.20 (ipotizzato)
