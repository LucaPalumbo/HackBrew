# Evoluzione di HackBrew: dispositivi, regolazione e dettaglio delle fermentazioni

Documento della sessione `grill-with-docs`, conclusa con conferma esplicita della comprensione condivisa da parte dell'utente. Le decisioni sotto costituiscono la base concordata per la successiva specifica di implementazione.

## Decisioni confermate

- Creare una birra significa creare il ciclo di fermentazione da monitorare, con nome della birra, pillola, dispositivi termici e impostazioni della temperatura.
- Sono previste più fermentazioni attive contemporaneamente, ciascuna con la propria pillola.
- Una pagina permette di registrare le pillole e i dispositivi termici, classificati per riscaldamento, raffreddamento o entrambe le funzioni.
- Ogni fermentazione usa una pillola, che non può essere assegnata contemporaneamente a un'altra fermentazione attiva. Per la regolazione si sceglie un dispositivo di riscaldamento e/o uno di raffreddamento, oppure un singolo dispositivo con entrambe le funzioni. Ogni dispositivo termico è esclusivo di una fermentazione attiva.
- È possibile avviare una fermentazione in modalità **solo monitoraggio**, senza dispositivi termici e senza impostare temperatura minima, temperatura massima o isteresi.
- Quando si usa la regolazione, alla creazione si inseriscono temperatura minima, temperatura massima e isteresi.
- Le impostazioni guidano la regolazione termica automatica durante la fermentazione attiva.
- Si possono definire endpoint provvisori per comandare i dispositivi termici; saranno sostituiti con gli endpoint reali in seguito.
- La logica di regolazione risiede in HackBrew. I dispositivi termici eseguono i comandi HTTP e comunicano lo stato effettivo.
- Il **timeout di comunicazione** è un'unica impostazione **globale** nella pagina Impostazioni, comune a tutte le fermentazioni e configurabile in qualsiasi momento, anche durante fermentazioni attive. Il valore iniziale è **3 ore** ed è **simmetrico**: server e attuatori devono usare lo stesso valore configurato. Le modifiche vengono sincronizzate con gli attuatori.
- Se il server non riceve dati dalla pillola associata per la durata del timeout, invia il comando di spegnimento a tutti gli attuatori della relativa fermentazione e sospende la regolazione, lasciando attiva la fermentazione. La ricezione di dati da altre pillole non rinnova questo intervallo.
- Se un attuatore non riceve comandi dal server per la stessa durata, si spegne autonomamente, anche se HackBrew è arrestato o non raggiungibile. Il timeout si misura dall'ultimo comando ricevuto; sul server si misura dall'ultima ricezione dei dati della pillola. Le due scadenze hanno uguale durata, ma non necessariamente lo stesso istante di decorrenza.
- Con un intervallo di 18–22 °C e isteresi di 0,5 °C, il riscaldamento si accende a temperatura ≤ 18 °C e si spegne a temperatura ≥ 18,5 °C; il raffreddamento si accende a temperatura ≥ 22 °C e si spegne a temperatura ≤ 21,5 °C. Riscaldamento e raffreddamento non possono essere attivi contemporaneamente.
- Se manca una temperatura utilizzabile, la regolazione rimane sospesa e i dispositivi non vengono accesi.
- La regolazione riprende automaticamente all'arrivo di una nuova temperatura valida. Dopo un riavvio, HackBrew verifica prima lo stato effettivo dei dispositivi e poi riprende il controllo delle fermentazioni ancora attive.
- Un dispositivo irraggiungibile sospende la regolazione e produce una segnalazione, senza concludere la fermentazione. In assenza di conferma, lo stato effettivo viene mostrato come sconosciuto o in errore, senza dichiarare il dispositivo spento.
- Il termine manuale della fermentazione è **definitivo** e richiede lo spegnimento di **tutti i dispositivi associati**, comprese entrambe le funzioni di un dispositivo combinato. La fermentazione viene conclusa anche se un dispositivo è irraggiungibile; lo spegnimento resta da completare e il dispositivo non può essere riassegnato finché non risulta confermato spento. Il ritorno di letture o della connessione non riattiva una fermentazione conclusa.
- Durante una fermentazione attiva si possono modificare temperatura minima, temperatura massima e isteresi, conservando traccia delle modifiche. Pillola e dispositivi associati rimangono quelli scelti all'avvio.
- L'evoluzione comprende modifiche al gateway per identificare la pillola da cui arriva ciascuna lettura. L'identificativo confermato è il **MAC Bluetooth della pillola**, attualmente presente nella configurazione `ble.mac_address`. La registrazione avviene nella pagina web inserendo nome e MAC Bluetooth.
- Il bridge/gateway è unico per tutte le pillole: deve gestire più pillole, senza richiedere un'istanza distinta per ciascuna. Acquisisce automaticamente da HackBrew l'elenco delle pillole registrate e inizia a leggerle: non è richiesta una seconda configurazione manuale dei MAC nel gateway.
- Una pagina elenca tutte le fermentazioni come card riassuntive, evidenziando quelle in corso. Ogni card apre la pagina di dettaglio della fermentazione.
- Le card mostrano nome, stato, pillola, ultima temperatura, densità, batteria e stato della regolazione. Le fermentazioni attive precedono quelle concluse; è disponibile la ricerca per nome.
- Il dettaglio contiene un unico grafico grande a linee, con serie selezionabili e scale distinte per le diverse unità.
- Tutte le misure numeriche ricevute dal gateway devono essere conservate e disponibili nel grafico: temperatura, densità, batteria, velocità di variazione della densità e accelerazioni X/Y/Z. Il timestamp è l'asse temporale; `valid` indica la qualità della velocità di variazione.
- Il grafico permette di scegliere un intervallo temporale e usare lo zoom. La selezione dell'intervallo resta ferma all'arrivo di nuove letture; il pulsante **Torna al live** riattiva lo scorrimento automatico.
- I controlli comprendono una barra temporale con due estremi trascinabili, intervalli rapidi **1h / 6h / 24h / Tutto**, zoom con rotella, gesto sul cellulare e **selezione di un'area con il mouse sul grafico**, oltre allo spostamento laterale dell'intervallo.
- Le linee collegano i campioni disponibili anche quando distanti nel tempo: **nessuna interruzione o evidenziazione dei gap basata sulla distanza temporale** e nessuna soglia configurabile per i gap. Vengono rappresentati solo i campioni effettivamente ricevuti, senza aggiungere misure ai periodi senza dati.
- Lo stato di comunicazione mostrato nell'interfaccia riflette il timeout globale configurato, senza reintrodurre soglie fisse precedenti.
- I dati applicativi attuali possono essere **eliminati nel passaggio alla nuova versione**: non è richiesta la migrazione di fermentazioni e letture precedenti. La decisione autorizza il reset previsto dall'evoluzione; questa sessione di progettazione non ha ancora cancellato dati.

## Fatti verificati

- Il gateway corrente invia nove campi ma non l'identità della pillola; seleziona un solo MAC per istanza e non contiene un protocollo per attuatori.
- HackBrew attualmente impone una sola fermentazione attiva globale e conserva soltanto temperatura, densità, batteria e timestamp della misura. Le altre misure dei dati già salvati non sono ricostruibili.
- Identità delle letture, ultima lettura diagnostica e associazione agli intervalli sono attualmente globali e dovranno distinguere le pillole.
- Le unità fisiche degli accelerometri non sono documentate nel gateway; il significato di `valid` non va esteso alla temperatura o all'intera lettura.

Fonti: [serializzazione del gateway](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/blob/0bfc4a7fbbcfc2f231f75452d194de86677d46e2/telemetryData.py), [configurazione di esempio](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/blob/0bfc4a7fbbcfc2f231f75452d194de86677d46e2/config.example.yaml), codice corrente di HackBrew.

## Stato della progettazione

- È confermato un timeout globale simmetrico configurabile, inizialmente di 3 ore, per mancata ricezione di dati sul server e mancata ricezione di comandi sugli attuatori. È eliminata la gestione dei gap temporali nel grafico.
- L'utente ha confermato esplicitamente la comprensione condivisa sul riepilogo complessivo. La sessione di progettazione è conclusa.
- La specifica è stata pubblicata come [GitHub Issue #8](https://github.com/LucaPalumbo/HackBrew/issues/8), con etichetta `ready-for-agent`; una copia è disponibile nel [documento di specifica](../specs/hackbrew-devices-and-control.md).
- Il perimetro dei test è stato confermato dall'utente durante `to-spec`: API HTTP e browser con MongoDB reale in Docker, contratto del bridge e simulatori HTTP degli attuatori. Il contratto HTTP provvisorio è definito nella specifica sulla base dei comportamenti concordati.
