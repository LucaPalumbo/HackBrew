## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Aprire il dettaglio di una fermentazione e vedere tutte le misure conservate in un unico grafico grande a linee, aggiornato per la fermentazione corretta. Ogni serie può essere selezionata dalla legenda e i valori esatti restano accessibili. La navigazione temporale avanzata arriva nel ticket successivo.

## Acceptance criteria

- [ ] Nel dettaglio esiste un solo grafico a linee, al posto dei due scatter plot precedenti, con temperatura, densità SG, batteria, velocità della densità e accelerazioni X/Y/Z inizialmente visibili.
- [ ] Ogni serie è distinguibile e selezionabile dalla legenda. Le scale sono separate per unità, con una scala comune per i tre accelerometri; etichette e tooltip non inventano unità fisiche.
- [ ] L'asse orizzontale usa il timestamp di acquisizione e i valori coincidono con le letture persistite, anche con timestamp uguali o invii fuori ordine.
- [ ] Le linee collegano i campioni disponibili anche quando distanti nel tempo: nessun gap temporale interrompe o evidenzia la linea, nessun campione viene inventato e nessuna misura mancante diventa zero.
- [ ] valid falso rende indisponibile solo la velocità della densità; le altre serie rimangono utilizzabili. Campi opzionali mancanti sono rappresentati come non disponibili nei valori esatti.
- [ ] La rappresentazione accessibile delle letture rende consultabili i valori delle sette misure; il grafico è grande e utilizzabile su desktop e telefono senza allargare la pagina oltre lo schermo.
- [ ] Lo storico selezionato rimane separato dalle letture delle altre fermentazioni. La finestra live attuale e la navigazione storica già esistente continuano a funzionare, senza richiedere ancora i nuovi controlli temporali.
- [ ] Test HTTP/browser verificano conservazione e visualizzazione delle sette misure, legenda, unità, casi senza dati, flag valid, campioni distanti e aggiornamenti live. Evidenza visiva conferma il tracciato a linee senza dipendere dagli oggetti interni della libreria grafica.

## Blocked by

- T2 — Monitorare fermentazioni parallele con card e dettaglio.
