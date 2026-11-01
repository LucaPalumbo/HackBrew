# HackBrew: prima versione

Stato: perimetro e stack confermati esplicitamente dall'utente al termine dell'intervista. La specifica operativa è pubblicata nella [issue GitHub #1](https://github.com/LucaPalumbo/HackBrew/issues/1).

## Obiettivo

Una piattaforma web facile da usare per monitorare la fermentazione della birra prodotta in casa, consultabile da computer e cellulare.

## Requisiti confermati

- Uso personale.
- Frontend Vue 3 con TypeScript e Vite, grafici Chart.js e aggiornamenti tramite Server-Sent Events (SSE).
- Backend in Python con FastAPI, confermato dall'utente.
- Database MongoDB, scelto dall'utente.
- Intero progetto dockerizzato: build e avvio riproducibili tramite Docker, con Docker Compose per coordinare i servizi.
- La dockerizzazione riguarda frontend, backend e MongoDB. Il gateway Bluetooth è un progetto esterno ed è escluso dal lavoro corrente.
- Un solo fermentatore e una sola fermentazione attiva alla volta.
- Integrazione con il gateway esistente [RaptPillGateway-ble-http](https://github.com/LucaPalumbo/RaptPillGateway-ble-http).
- Dashboard adattabile al cellulare con densità, temperatura, batteria, grafici nel tempo e orario dell'ultima lettura ricevuta.
- Aggiornamento automatico quando arrivano nuovi dati.
- Temperatura in °C e densità espressa in SG.
- Fermentazioni identificate da un nome, con avvio e termine manuali.
- Le letture ricevute durante una fermentazione alimentano il suo storico; le fermentazioni concluse restano consultabili.
- Senza una fermentazione attiva, viene mostrata l'ultima lettura per verificare il funzionamento; non viene registrato uno storico di prove.

## Perimetro concordato per la prima consegna

- Esecuzione in ambiente locale per lo sviluppo e la verifica.
- Ricezione dei messaggi HTTP nel formato attuale del gateway e memorizzazione delle letture delle fermentazioni.
- Gestione delle fermentazioni e dashboard secondo i requisiti confermati.
- Salvataggio persistente: chiudere il browser o riavviare l'applicazione non cancella i dati già registrati.
- Orario di acquisizione visibile; le letture assenti o non valide non vengono presentate come valori aggiornati o inventati.
- Il lavoro iniziale riguarda HackBrew. Le modifiche al gateway per aggiungere autenticazione o recupero degli invii falliti saranno valutate in seguito.

## Fasi future esplicitamente rimandate

- Hosting: l'utente ha un computer che potrà utilizzare; la distribuzione sarà affrontata più avanti.
- Accesso da fuori casa, riservato all'utente.
- Autenticazione: la preferenza espressa è l'accesso GitHub riservato all'account LucaPalumbo; realizzazione e dettagli saranno affrontati in seguito.

## Vincoli dell'integrazione attuale

Il gateway può perdere una lettura se il suo invio HTTP fallisce. HackBrew può conservare i dati ricevuti, ma non recuperare da solo quelli che il gateway ha già eliminato. Dettagli e fonti: [integrazione del gateway](../integrations/rapt-gateway.md).

## Stack concordato

| Responsabilità | Tecnologia |
| --- | --- |
| Interfaccia web | Vue 3, TypeScript e Vite. |
| API e ricezione delle letture | Python e FastAPI. |
| Persistenza | MongoDB. |
| Grafici | Chart.js. |
| Aggiornamenti della dashboard | Server-Sent Events (SSE), dal server al browser. |
| Build e avvio riproducibili | Docker e Docker Compose con un volume persistente per MongoDB. |

Il frontend compilato sarà servito da FastAPI. La distribuzione comprende un servizio applicativo e un servizio MongoDB, con un volume persistente per il database. Il gateway comunica con HackBrew tramite HTTP.

Vue 3 con Composition API, TypeScript e Vite organizzerà gli stati e le interazioni della dashboard. FastAPI gestirà il contratto del gateway e la validazione. SSE gestirà gli aggiornamenti dal server alla dashboard, mentre le azioni dell'utente passeranno per le API HTTP.

MongoDB è stato scelto esplicitamente dall'utente. Il modello delle collezioni e degli indici sarà definito nella specifica tecnica; la presenza di dati temporali non implica automaticamente l'uso di collezioni time series.

### Organizzazione Docker

- Build multi-stage: un container con Node compila il frontend; gli artefatti prodotti vengono copiati nell'immagine dell'applicazione Python.
- Il servizio applicativo esegue FastAPI e serve API e frontend dallo stesso indirizzo.
- MongoDB viene eseguito in un container distinto, raggiunto dall'applicazione sulla rete di Compose, con i dati conservati in un volume persistente.
- Sviluppo e test dovranno poter essere eseguiti tramite container, mantenendo Python, Node e le rispettive dipendenze dentro Docker.
- Per lo sviluppo, il frontend potrà avere un servizio Vite dedicato per il ricaricamento automatico.
- Il gateway Bluetooth rimane esterno ai servizi Docker di HackBrew e invia i dati all'endpoint HTTP dell'applicazione.

Questa sezione definisce i requisiti di organizzazione. Dockerfile, configurazioni Compose e comandi di progetto saranno creati durante l'implementazione.

Fonti primarie consultate:

- [Vue: componenti a file singolo](https://vuejs.org/guide/scaling-up/sfc.html) e [supporto TypeScript](https://vuejs.org/guide/typescript/overview.html).
- [FastAPI: funzionalità e validazione](https://fastapi.tiangolo.com/features/).
- [MongoDB: serie temporali](https://www.mongodb.com/docs/manual/core/timeseries-collections/) e [installazione del servizio Community](https://www.mongodb.com/docs/manual/administration/install-community/).
- [MongoDB Community in Docker](https://www.mongodb.com/docs/manual/administration/install-community-docker/).
- [Chart.js: grafici responsive](https://www.chartjs.org/docs/latest/configuration/responsive.html).
- [FastAPI: Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/).
- [Docker Compose: volumi persistenti](https://docs.docker.com/reference/compose-file/volumes/).
- [Docker: build multi-stage](https://docs.docker.com/build/building/multi-stage/).

## Specifica operativa

La [issue GitHub #1](https://github.com/LucaPalumbo/HackBrew/issues/1) contiene le user story, le decisioni di implementazione e il piano dei test confermato dall'utente. È il riferimento per suddividere e implementare il lavoro.

La specifica chiarisce normalizzazione e validazione delle letture, duplicati, associazione temporale alle fermentazioni e soglia configurabile per i dati non aggiornati. Le versioni delle dipendenze e l'organizzazione concreta di comandi, collezioni e indici saranno definite durante l'implementazione. La verifica con un messaggio reale del gateway rimane parte della verifica di integrazione.

La terminologia del dominio è definita in [GLOSSARY.md](../../GLOSSARY.md).
