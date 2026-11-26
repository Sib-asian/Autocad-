# C004: appartamento al piano terra (catastale ortogonale) per APE

Pratica C004 (26/11/2026). Richiesta "al solito": pianta 1:100 in metri, un layer bianco, niente quote o legende.

## Cosa ha funzionato
- `rilievo assi` anche per una pianta ortogonale: disegno pulito al primo giro, in meno tempo del rilievo per
  locali. Le linee del catastale si leggono con `rilievo linee <scansione raddrizzata>` (apertura morfologica):
  posizione e spessore di ogni linea in pixel, poi si controlla con la sovrapposizione degli assi alla scansione.
- Muri esterni dalla **faccia interna** del catastale (+15 cm verso fuori per l'asse): le superfici dei locali
  restano quelle del catastale anche se il catastale disegna muri da 26-39 cm.
- Porte centrate sulle crocette; dove la porta cade a pochi cm da un tramezzo si sposta di qualche cm perche'
  arrivi alla faccia (regola dei 6 cm) invece di lasciare un pezzetto.

## Errore al primo giro e rimedio
| Errore | Causa | Rimedio |
|---|---|---|
| Scalino di 1 mm dove un tramezzo prosegue la faccia interna di un muro esterno | Asse del tramezzo arrotondato (280,8 invece di 280,837 px) | `rilievo assi` lo segnala (lati sotto i 9 cm); l'asse del tramezzo = faccia interna del muro esterno -/+ 5 cm esatti |

## Regole
1. Piano terra: le scalette esterne senza segno di porta non si inventano: si chiede (porta-finestra?).
2. Vano scala, corte e marciapiedi (linee sottili esterne) non si disegnano nella pianta per l'APE.
