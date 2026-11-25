# C003: appartamento con muri inclinati da planimetria catastale per APE

Pratica C003 (appartamento al primo piano, 25/11/2026). Richiesta: "identico procedimento di prima, svelto ma
preciso": pianta semplice 1:100 **in metri**, un layer bianco, muri esterni 30 e interni 10.

## Errori al primo giro e rimedi permanenti
| Errore | Causa | Rimedio permanente |
|---|---|---|
| Tramezzi ondulati, moncherini, scalini e ganci nei balconi | Muri ricavati in automatico dai pixel (massa + divisione dello spazio): segue il rumore della scansione | **Assi a mano**: si leggono le rette degli assi sul catastale raddrizzato (griglia + sovrapposizione degli assi alla scansione), si scrivono in `modello/assi.yaml` e `rilievo assi <pratica>` costruisce muri dritti per costruzione |
| Scalino dove un muro esterno da 30 prosegue come tramezzo da 10 | Stesso asse per spessori diversi | Il tratto esterno si sposta di 10 cm (15 - 5) verso fuori: la faccia verso il locale resta dritta. Il catastale lo conferma (la faccia esterna coincide col bordo del balcone) |
| Pezzetti di muro di 4-12 cm accanto alle porte | Porta centrata sulla crocetta, che sta a pochi cm dal tramezzo | Un vano a meno di 6 cm dalla faccia di un muro che s'innesta arriva alla faccia (`assi.py`); `rilievo assi` segnala ogni lato sotto i 9 cm |

## Regole
1. Catastale con muri inclinati o locali non rettangolari: **assi a mano**, non vettorializzazione dei pixel.
   Controllo: sovrapporre gli assi alla scansione e guardarli prima di disegnare.
2. Muri inclinati e rientranze si tengono se sono chiaramente la forma dell'edificio (angoli grandi, ripetuti
   nelle due linee del muro); si raddrizza solo l'imprecisione del disegno.
3. Prima di consegnare: render come in AutoCAD (sfondo nero) e nessun lato sotto i 9 cm.
