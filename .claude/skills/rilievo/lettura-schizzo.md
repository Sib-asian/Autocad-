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
5. Costruisci il modello: fissa l'origine nello spigolo interno in basso a sinistra del primo locale; gli assi
   stanno a meta' spessore fuori dalle facce interne; i muri storti si ricavano dalle due dimensioni del locale.
   Fatto quando `rilievo verifica` passa e le superfici calcolate corrispondono alle dimensioni scritte (±1 cm).
