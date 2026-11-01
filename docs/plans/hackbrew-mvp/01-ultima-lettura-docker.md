## Parent

[HackBrew MVP — issue #1](https://github.com/LucaPalumbo/HackBrew/issues/1)

## What to build

Avviare HackBrew con Docker e visualizzare nella dashboard Vue l'ultima lettura inviata al ricevitore FastAPI e salvata in MongoDB, anche senza una fermentazione attiva. Questo è il primo percorso completo e dimostrabile dal messaggio del gateway alla schermata dell'homebrewer.

Il gateway resta esterno. Il frontend viene compilato in Docker e servito dall'applicazione; MongoDB usa un volume persistente. Non sono ancora richiesti aggiornamenti live, gestione delle fermentazioni o grafici.

Tracciabilità alla specifica: user story 1, 3–6, 13–15, 28–34, 36 e 42–48, limitatamente al comportamento disponibile in questa prima porzione.

## Acceptance criteria

- [ ] Build e avvio di applicazione e MongoDB funzionano tramite Docker Compose senza richiedere Node, Python o MongoDB installati sul computer host.
- [ ] La dashboard è costruita con Vue 3, TypeScript e Vite; il backend è Python/FastAPI e il salvataggio usa MongoDB reale.
- [ ] Il ricevitore accetta il formato HTTP attuale del gateway senza richiedere nuovi identificatori, intestazioni di autenticazione o modifiche al progetto esterno.
- [ ] Una lettura ricevuta viene mostrata con densità in SG, temperatura in °C, batteria in percentuale e orario di acquisizione. La densità trasmessa viene divisa per 1000, preservando la precisione dei dati salvati.
- [ ] Il timestamp del gateway mantiene la parte frazionaria; acquisizione e ricezione HTTP sono concetti distinti. Una lettura più vecchia non sostituisce quella più recente.
- [ ] Il flag `valid` falso non fa scartare temperatura, densità o batteria: riguarda la velocità di variazione della densità.
- [ ] JSON malformati, misure obbligatorie mancanti, numeri non finiti e percentuali batteria fuori intervallo producono un errore comprensibile e non sostituiscono una lettura valida.
- [ ] Prima della prima lettura compare uno stato vuoto esplicito. Senza fermentazioni attive è conservata soltanto l'ultima lettura diagnostica, senza accumulare uno storico di prove.
- [ ] Ricaricare la pagina o riavviare l'applicazione mantenendo il volume MongoDB conserva l'ultima lettura accettata. Il caricamento iniziale non dipende dalla memoria del browser.
- [ ] Un test d'integrazione invia un messaggio deterministico al ricevitore reale, ne verifica il recupero dall'applicazione e un test browser verifica i valori visualizzati. I dati di test usano MongoDB e volumi isolati.
- [ ] Sono disponibili in container i comandi effettivi per sviluppo, build, test, formattazione e lint; la documentazione li descrive insieme alla struttura iniziale del progetto.
- [ ] La configurazione di esempio usa valori segnaposto e le esclusioni dal controllo versione comprendono segreti locali, dati runtime e artefatti generati.

## Blocked by

None (can start immediately).
