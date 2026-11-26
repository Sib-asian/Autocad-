# C005: appartamento al secondo piano (catastale ortogonale, stretto e lungo) per APE

Pratica C005 (26/11/2026). Richiesta "stesso discorso": pianta per APE come le precedenti.

## Cosa ha funzionato
- `rilievo linee` + `rilievo assi` come in C004: lettura delle linee, assi, sovrapposizione, disegno pulito.
- Muri interni disegnati pieni nel catastale (circa 20 cm): asse al centro della linea piena, spessore 10.

## Errori al primo giro e rimedi permanenti
| Errore | Causa | Rimedio permanente |
|---|---|---|
| 4 "dentini" di 8-12 cm accanto alle porte | Crocette approssimate; la regola dei vani arrivava alla faccia solo entro 6 cm | Tolleranza portata a 12 cm (`assi.py`) |
| Con 12 cm una finestra arrivava alla faccia **opposta** di un tramezzo innestato | Lo scatto guardava entrambe le facce del muro | Ogni estremo scatta solo alla faccia dalla sua parte (test `test_vano_non_attraversa_il_tramezzo`) |

Controllato che C003 e C004 restano identiche con la regola nuova.

## Regole
1. Dopo ogni modifica a `assi.py`: rigenerare le pratiche gia' fatte e confrontarle (devono restare uguali o
   migliorare), e rimandare all'utente il file solo se cambia.
2. Striscia a linea sottile lungo un muro esterno, su cui danno porte-finestre o finestre: e' un balcone
   (confermato dall'utente). Si disegna solo il bordo, senza chiedere.
3. Piani sopra e sotto (per l'APE): l'utente li verifica da se'; basta ricordarlo nella consegna.
