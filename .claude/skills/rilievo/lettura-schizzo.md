# Lettura di uno schizzo di rilievo

Obiettivo: ogni segno a penna diventa un dato del modello o una domanda. Lavora a zone, mai a colpo d'occhio.

1. `rilievo griglia <schizzo>`: guarda l'immagine con la griglia e annota le zone (un locale, un muro, un gruppo
   di numeri). Fatto quando ogni scritta a penna appartiene a una zona.
2. Per ogni zona `rilievo zoom <schizzo> x y w h --fattore 3` e leggi. Per ogni numero annota: valore, a cosa si
   riferisce (dimensione interna, progressiva di quale muro, H min/H max/H, altezza porta, davanzale), certezza.
   Un numero letto a meta' resta una domanda.
3. Riconosci i segni:
   - freccia tra due muri = dimensione interna del locale;
   - linea lungo un muro con tacche e "0" = progressive delle aperture dal punto 0;
   - numero barrato + numero accanto = correzione: vale il nuovo;
   - riga ondulata sopra un muro stampato = muro cancellato/demolito: chiedi conferma;
   - "H min"/"H max" = soffitto inclinato; "h ... arco" = porta ad arco; "dav" = davanzale.
4. Controlli incrociati prima di scrivere il modello:
   - somma delle larghezze dei locali + spessori dei muri = progressiva totale del muro esterno;
   - le progressive crescono e stanno dentro la lunghezza del muro;
   - la stessa porta vista dai due locali ha la stessa larghezza.
   Ogni incoerenza diventa una domanda con i due valori in conflitto.
5. Trascrivi in `modello/rilievo.yaml` (per locali, vedi `esempi/rilievo_caso_2031.yaml`): locali con
   `larghezza`/`profondita` (e `larghezza_nord` se un lato e' storto), posizione con `a_destra_di`/`sopra_di`
   e `scostamento`, aperture con `lato`, `dal` (punto 0) e progressive. Spessori non scritti: misurali sulla
   stampa con la scala ricavata da una quota nota e mettili tra le domande. Poi `rilievo costruisci`.
   Fatto quando `rilievo verifica` passa e le superfici calcolate corrispondono alle dimensioni scritte (±1 cm).
