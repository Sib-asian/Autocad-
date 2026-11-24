# Fotografare un edificio

- **Facciate da misurare:** obiettivo 1x, telefono dritto (ne' inclinato in su ne' in giu'), centrato sulla
  facciata, il piu' lontano possibile. Se la facciata e' lunga, piu' foto sovrapposte di un terzo.
- **Una misura nota nella foto:** la larghezza della facciata (dalla pianta) e un'altezza misurata (gronda o
  porta). Servono 4 punti di cui si conoscono le coordinate reali per raddrizzare la foto.
- **Originali:** carica le foto nel repository (`pratiche/<codice>/input/foto/`), non solo in chat: la chat
  comprime e cancella i dati della fotocamera (focale, obiettivo) che servono a correggere la deformazione.
- **Lesioni:** foto frontale e ravvicinata con un metro accanto; annota muro, posizione e ampiezza.
- **Punti di scatto:** segna sulla pianta numero e direzione di ogni foto: servono per la tavola della
  documentazione fotografica.

**Tre regole imparate dalle prove:**
1. lo spigolo da cliccare e' dove cambia il piano del muro, non dove finisce il materiale;
2. i 4 punti noti devono racchiudere cio' che vuoi misurare (dentro: 1-4 cm; fuori: decine di cm);
3. misura sempre almeno un'altezza per facciata con il metro: la sola foto non basta.

Come si misura da una foto: `rilievo punti foto.jpg` apre una pagina dove si cliccano i punti; poi
`rilievo raddrizza foto.jpg punti.json` corregge la deformazione, raddrizza la facciata e da' le misure
in metri. Vale solo per superfici piane: rientranze e sporgenze non si misurano cosi'.
