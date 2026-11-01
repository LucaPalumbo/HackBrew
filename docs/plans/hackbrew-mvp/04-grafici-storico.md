## Parent

[HackBrew MVP — issue #1](https://github.com/LucaPalumbo/HackBrew/issues/1)

## What to build

Consultare l'andamento della fermentazione attiva e riaprire quelle concluse attraverso grafici e valori storici. L'homebrewer deve poter ritrovare una fermentazione per nome, selezionarla e leggere soltanto le misure che le appartengono, da computer o cellulare.

Il percorso comprende query sui dati realmente salvati, risposta dell'applicazione e visualizzazione con Chart.js. Usa il meccanismo live per aggiornare anche i grafici quando arrivano nuove letture e recupera i dati persistiti al normale caricamento della pagina.

Tracciabilità alla specifica: user story 2, 8–12, 20, 24–29 e 40.

## Acceptance criteria

- [ ] La fermentazione attiva presenta i grafici di densità SG e temperatura °C usando le proprie letture persistite.
- [ ] Una nuova lettura dell'attiva aggiorna anche i grafici senza ricaricare la pagina; la consultazione di una fermentazione conclusa mantiene la selezione dell'utente quando arrivano nuovi dati.
- [ ] Le fermentazioni concluse sono elencate con un nome riconoscibile e possono essere selezionate per consultarne valori e grafici.
- [ ] Le misure di batteria rimangono consultabili insieme alle altre letture storiche, senza introdurre nuove metriche non richieste.
- [ ] L'identità della fermentazione selezionata è chiara e i suoi dati non sono sostituiti da quelli dell'attiva o dell'ultima lettura diagnostica.
- [ ] Le letture sono restituite e rappresentate in ordine di acquisizione; grafici e riepiloghi usano le stesse unità e la stessa sorgente persistita.
- [ ] Una fermentazione senza dati ha uno stato esplicito. Le lacune non vengono riempite con misurazioni inventate o presentando interpolazioni come campioni acquisiti.
- [ ] Il volume di dati trasferiti o disegnati è controllato per mantenere utilizzabile la pagina su cellulare, preservando le misure salvate e i loro valori originali.
- [ ] Navigazione, grafici e informazioni restano utilizzabili con viewport desktop e telefono, senza vincolare i test a una specifica palette o a dettagli interni del rendering.
- [ ] Ricaricare il browser o riavviare l'applicazione mantenendo il database permette di riaprire le fermentazioni concluse e consultarne lo storico.
- [ ] Test attraverso le interfacce pubbliche e il browser creano due fermentazioni con letture distinguibili e verificano che la selezione restituisca lo storico corretto con MongoDB reale.

## Blocked by

- T2 — Aggiornare la dashboard in tempo reale e segnalare dati non aggiornati.
- T3 — Avviare e terminare una fermentazione registrandone le letture.
