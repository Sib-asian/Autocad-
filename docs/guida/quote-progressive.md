# Quote progressive

Si appoggia il metro (o il laser) allo spigolo interno del muro, il **punto 0**, e senza spostarlo si leggono
le distanze di ogni spigolo di porta e finestra: 0 - 1,20 - 2,10 - 3,40 - 4,20 ...

Perche' conviene: con i parziali (1,20 + 0,90 + 1,30 ...) ogni errore di lettura si somma ai successivi;
con le progressive ogni misura e' indipendente e l'errore resta di 1 cm.

Sullo schizzo: una linea lungo il muro con una tacca per ogni spigolo, lo "0" all'inizio e i numeri accanto
alle tacche. Nel modello (`edificio.yaml`) ogni apertura ha `da` e `a` = le due progressive, e il muro ha
`zero` = la distanza del punto 0 dall'inizio del suo asse (di solito meta' dello spessore del muro d'angolo).
