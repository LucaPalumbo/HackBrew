## Parent

[Specifica #8 — Gestire pillole, dispositivi termici e fermentazioni parallele](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Registrare pillole dalla pagina Dispositivi e vedere l'ultima lettura diagnostica di ciascuna, conservando tutte le misure ricevute. Selezionare esplicitamente la pillola anche nel ciclo di monitoraggio esistente, ancora limitato a una fermentazione attiva in questo primo incremento. L'identità della sorgente deve attraversare ricezione, persistenza, consultazione e aggiornamento live senza confondere le pillole.

Questo è anche il primo passaggio alla nuova versione: predisporre la procedura deliberata di reset del dataset precedente, autorizzata dall'utente, e adattare il codice e le verifiche esistenti al nuovo contratto. Il reset non deve avvenire a ogni avvio.

## Acceptance criteria

- [ ] La pagina Dispositivi permette di registrare ed elencare pillole con nome, identificatore stabile e MAC Bluetooth; formati MAC equivalenti sono normalizzati e i duplicati rifiutati con una spiegazione.
- [ ] Il ricevitore HTTP richiede l'identità Bluetooth della sorgente; sorgenti mancanti, sconosciute o non valide non sono assegnate arbitrariamente e non modificano i dati persistiti.
- [ ] Tutti i campi del bridge sono conservati: temperatura, densità normalizzata SG, batteria, velocità della densità, accelerazioni X/Y/Z, timestamp e flag valid. Non vengono inventate unità degli accelerometri; valid riguarda soltanto la velocità della densità.
- [ ] Ogni pillola ha la propria ultima lettura diagnostica, interrogabile tramite API e visibile nell'interfaccia con aggiornamento live. Non viene creata una cronologia diagnostica completa fuori dalle fermentazioni.
- [ ] L'avvio della fermentazione esistente richiede la scelta di una pillola registrata; solo le sue letture vengono associate all'intervallo avvio incluso/termine escluso. Il vincolo globale di una sola attiva resta temporaneamente fino al ticket T2.
- [ ] L'identità delle letture include pillola e contenuto completo delle misure e della qualità. Duplicati concorrenti non moltiplicano i campioni; dati identici di pillole diverse e variazioni dei campi aggiuntivi restano distinti.
- [ ] Il timestamp di acquisizione, la prima ricezione del campione e l'ultima comunicazione accettata della pillola restano informazioni distinte. Letture fuori ordine non sostituiscono misure più recenti; richieste invalide non rinnovano la comunicazione.
- [ ] Il reset deliberato è documentato e circoscritto ai dati applicativi precedenti. Non serve migrazione dei dati vecchi; riavvii ordinari preservano tutti i dati nuovi e non cancellano volumi estranei.
- [ ] Test HTTP con MongoDB reale e browser verificano due pillole, diagnostica separata, selezione della sorgente, campi completi, duplicati e input errato. Le prove operative precedenti sono adattate al nuovo contratto, senza mantenere un obbligo di migrazione ormai escluso.
- [ ] Tutti i controlli e la procedura di prova usano il workflow Docker esistente; nessun hardware o dato reale è necessario.

## Blocked by

None (can start immediately).
