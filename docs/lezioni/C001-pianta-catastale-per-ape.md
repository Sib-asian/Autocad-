# C001: pianta da planimetria catastale per APE

Pratica C001 (bottega al piano terra, 25/11/2026). Richiesta: ridisegnare la planimetria catastale (PDF, 1982) per
un APE, scala 1:100, muri esterni 30 cm, tramezzi 10 cm, porta d'ingresso disegnata bene. Consegna: DWG da
caricare nel programma APE dell'utente (Blumatica Energy 6.2).

## Cosa ha funzionato

- PDF catastale = scansione dentro il PDF. La scala si prende dalla **barra vettoriale "10 metri"** del PDF (non dal
  "1:200" scritto): 94,49 punti = 10 m, scansione a 200 dpi di un 1:200, quindi 1 pixel = 2,54 cm.
- Misure con i profili dei pixel (mediane lungo tutto il muro), non a occhio: errore ±3 cm.
- Muri da 30 centrati sugli **assi** dei muri del catastale (li' disegnati da ~23 cm): si sposta metà dentro e
  metà fuori. Tramezzi a linea singola = 10 cm. Porte dalle crocette del catastale.
- Nord letto dal simbolo ORIENTAMENTO (non ipotizzato). Rettangolo catastale dell'ingresso = vano misurato,
  ridisegnato come porta a due ante.

## Errori al primo giro e rimedi permanenti

| Errore | Causa | Rimedio permanente |
|---|---|---|
| 15 scritte sovrapposte nei locali piccoli | Etichetta dei locali di dimensione fissa; larghezze dei testi stimate a occhio (0,62 x altezza) mentre il font vero è più largo | Etichetta adattiva (completa, compatta, abbreviata "ANTIB."); larghezze misurate con il font vero (`larghezza_testo`) |
| Linee di sezione in una pianta senza sezioni | Le tracce si disegnavano sempre | Solo se le sezioni sono tra le tavole richieste |
| Totale esterno scritto due volte per lato | Catena delle aperture disegnata anche senza aperture | Catena aperture solo se ci sono aperture; un totale per lato |
| Quote interne ripetute (già nelle catene esterne) | Nessun confronto fra interne ed esterne | Una misura già scritta fuori non si ripete dentro |
| Ingresso tutto rosso con larghezza misurata | Rosso a tutto il vano se l'altezza era ipotizzata | Vano rosso solo se larghezza/posizione sono ipotesi; altrimenti solo la sigla |
| Sigle delle porte su muri, archi e quote | Posizione fissa | Sigle posate per ultime nel primo posto libero (testi, muri, ante, linee di quota); se non c'è posto, sigla corta |
| Testi "0,10"/"0,30" che si toccano in AutoCAD | Tratti più corti del loro testo | Testo oltre l'estremità della catena o appena fuori dalla linea, solo in un posto libero |
| Volume calcolato con 3,00 invece di 4,00; WC contato come residenziale | Senza copertura si usava un'altezza di riserva; categorie per nome | Altezza dei locali; in un'unità non residenziale tutto è SNR |
| "File non valido" in Blumatica Energy | DWG AutoCAD 2018 troppo recente per il suo CAD | `rilievo genera --ape`: pianta solo geometria, cm, origine, AutoCAD 2000 + DXF |
| Il controllo diceva "0 sovrapposizioni" ma l'occhio vedeva scritte sui muri | Il controllo guardava solo testo contro testo | Nuovo controllo "Scritte sui muri" |

## Regole

1. Per un APE si consegnano due file: la tavola (DWG) e la pianta per il programma APE (`--ape`, AutoCAD 2000).
   Chiedere quale programma usa l'utente; se non lo dice, il formato 2000 va bene per tutti.
2. Prima di consegnare: guardare il DXF come in AutoCAD (font vero), non solo l'anteprima PNG.
3. Un controllo che passa mentre l'occhio vede un difetto va corretto (con un test).
4. Le misure da scansione si dichiarano con la loro precisione (±3 cm) e si dice quali assi si sono mantenuti.
