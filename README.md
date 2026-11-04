# HackBrew

Dashboard web per registrare pillole Bluetooth e monitorare la fermentazione della birra. La pagina **Dispositivi** mostra la diagnostica live di ciascuna pillola e tutte le misure ricevute. Il monitoraggio permette di scegliere una pillola, avviare una fermentazione con un nome e terminarla manualmente, registrandone le letture in MongoDB. Senza fermentazione attiva si può scegliere la pillola diagnostica; il pulsante **Aggiorna lettura** permette anche un recupero manuale.

Frontend Vue 3 con TypeScript e Vite, grafici Chart.js, backend Python/FastAPI e MongoDB. Il frontend viene compilato in Docker e servito da FastAPI. Il gateway Bluetooth è esterno al progetto. La [nuova specifica](https://github.com/LucaPalumbo/HackBrew/issues/8) estende l'[MVP](https://github.com/LucaPalumbo/HackBrew/issues/1): questo incremento consegna [registro e letture identificate](https://github.com/LucaPalumbo/HackBrew/issues/9). Rimane una sola fermentazione attiva globale; card, grafico unico, attuatori e impostazioni del timeout appartengono ai ticket successivi.

## Requisiti e avvio

Servono Docker Engine e Docker Compose. Node, Python, MongoDB e i browser di test vengono gestiti nei container. I comandi seguenti usano una shell POSIX.

```sh
./scripts/hackbrew up
```

Apri **http://localhost:8080**. Il primo avvio scarica le immagini e costruisce l'applicazione. MongoDB non pubblica una porta sull'host e conserva i dati nel volume del progetto.

Per fermare l'applicazione mantenendo le letture:

```sh
./scripts/hackbrew down
```

Un nuovo avvio recupera l'ultima lettura dal volume esistente.

Per un riavvio con conservazione dei dati, usa `./scripts/hackbrew down` seguito da `./scripts/hackbrew up`: avvio, termine, letture e ultima misura diagnostica restano nel volume MongoDB. Anche la ricostruzione dell'immagine con `up` mantiene quel volume. Questi comandi non richiedono di ricreare le fermentazioni.

## Passaggio deliberato dal dataset MVP

I dati della versione precedente non contengono l'identità della pillola. È stato concordato di eliminarli al passaggio a questa versione, senza migrazione. **Solo per questo passaggio**, usando lo stesso progetto Compose e la stessa configurazione dell'MVP:

```sh
./scripts/hackbrew down --volumes
./scripts/hackbrew up
```

Il primo comando elimina intenzionalmente il volume MongoDB dichiarato del progetto selezionato, quindi tutte le vecchie fermentazioni e letture. Non usare `--volumes` nei normali riavvii. La procedura non usa prune o rimozioni globali di volumi Docker. Un database nuovo non richiede questo reset; l'applicazione non cancella dati all'avvio e rifiuta il vecchio indice delle misure con un messaggio che rimanda a questa procedura.

## Registrare e controllare le pillole

Apri **Dispositivi** dalla navigazione e inserisci **Nome della pillola** e **MAC Bluetooth**. Sono accettati `AA:BB:CC:DD:EE:FF`, `aa-bb-cc-dd-ee-ff` e `aabbccddeeff`: identificano la stessa pillola e vengono conservati nel formato con due punti maiuscolo. Un MAC già registrato restituisce un conflitto, anche con registrazioni concorrenti.

Ogni pillola mostra densità SG, temperatura °C, batteria %, velocità della densità in punti SG/giorno e accelerazioni X/Y/Z, con unità degli accelerometri non specificata. La velocità non valida e le misure opzionali assenti sono indicate come non disponibili. Restano distinti acquisizione, prima ricezione della lettura e ultima comunicazione: un invio ripetuto rinnova il contatto senza cambiare la prima ricezione del campione. Le letture si aggiornano senza ricaricare la pagina.

| Operazione | Risultato |
| --- | --- |
| `POST /api/pills` con `{"name":"Pillola IPA","mac":"AA:BB:CC:DD:EE:FF"}` | Registra una pillola; HTTP 201 con `pill` e identificatore stabile. |
| `GET /api/pills` | Elenca `pills`, con identificatore, nome e MAC normalizzato. |
| `GET /api/readings/latest?pill_id=<id>` | Restituisce l'ultima lettura della pillola richiesta; HTTP 404 per identità sconosciuta. |

Il bridge corrente deve aggiungere `pill_mac` a ogni invio. L'adeguamento del bridge reale per più pillole e sincronizzazione automatica del registro è il [ticket #11](https://github.com/LucaPalumbo/HackBrew/issues/11); questo incremento può essere provato con messaggi HTTP identificati. Non attribuire un vecchio messaggio privo di MAC a una pillola scelta arbitrariamente.

## Configurazione

Le impostazioni predefinite funzionano senza un file di configurazione locale. Per cambiarle, copia `.env.example` in `.env` e modifica i valori:

| Variabile | Valore predefinito | Significato |
| --- | --- | --- |
| `HACKBREW_BIND_ADDRESS` | `127.0.0.1` | Indirizzo host su cui pubblicare l'applicazione. |
| `HACKBREW_PORT` | `8080` | Porta dell'applicazione. |
| `HACKBREW_FRONTEND_PORT` | `5173` | Porta Vite in sviluppo. |
| `MONGODB_DATABASE` | `hackbrew` | Database dell'applicazione. |
| `HACKBREW_FRESHNESS_SECONDS` | `300` | Età massima della lettura, in secondi interi positivi, prima di segnalare dati non aggiornati. |

Dopo aver modificato `.env`, esegui nuovamente `./scripts/hackbrew up` per applicare la configurazione.

Il gateway deve inviare le letture all'indirizzo raggiungibile del computer che esegue HackBrew, usando l'operazione `POST /telemetry`. Se gira sullo stesso computer, la destinazione predefinita è `http://localhost:8080/telemetry`. Per un gateway su un altro computer della rete locale, configura indirizzo di ascolto e destinazione in modo coerente.

Questa consegna riguarda l'esecuzione locale; autenticazione e pubblicazione su Internet saranno affrontate separatamente. `.env` e i dati runtime sono esclusi da Git.

## Contratto delle letture

Ogni messaggio deve contenere il MAC Bluetooth di una pillola già registrata; non sono richieste intestazioni di autenticazione:

```json
{
  "pill_mac": "AA:BB:CC:DD:EE:FF",
  "valid": false,
  "gravity_velocity": 0,
  "temperature": 19.6875,
  "specific_gravity": 1050.125,
  "accel_x": 0,
  "accel_y": 0,
  "accel_z": 0,
  "battery": 63.2734375,
  "timestamp": 1700000000.123456
}
```

- Densità: il valore del gateway viene diviso per 1000; nell'esempio diventa SG `1.050125` e il display mostra `1.050`.
- Temperatura: già espressa in °C. Batteria: percentuale da 0 a 100.
- `timestamp`: secondi Unix, inclusa la frazione, all'acquisizione sul gateway. La ricezione HTTP è registrata separatamente.
- `valid`: validità della velocità di variazione della densità; il valore `false` non invalida le altre misure.
- Tutte le quantità e il flag di qualità sono conservati. Le quattro misure necessarie restano temperatura, densità, batteria e timestamp, insieme all'identità della sorgente; i campi opzionali omessi sono restituiti come `null`.
- Valori più vecchi o dello stesso istante non sostituiscono l'ultima lettura della stessa pillola. Viene conservata una sola ultima lettura diagnostica per pillola, non uno storico di prove.

Per una prova su un database vuoto, se `curl` è disponibile, registra prima la pillola:

```sh
curl --fail-with-body http://localhost:8080/api/pills \
  --header 'Content-Type: application/json' \
  --data '{"name":"Pillola di prova","mac":"AA:BB:CC:DD:EE:FF"}'

curl --fail-with-body http://localhost:8080/telemetry \
  --header 'Content-Type: application/json' \
  --data '{"pill_mac":"AA:BB:CC:DD:EE:FF","valid":false,"gravity_velocity":0,"temperature":19.6875,"specific_gravity":1050.125,"accel_x":0,"accel_y":0,"accel_z":0,"battery":63.2734375,"timestamp":1700000000.123456}'
```

Il timestamp dell'esempio è storico: il gateway reale deve usare il proprio orario di acquisizione. Una prova più vecchia dell'ultima lettura già salvata non la sostituisce.

| Operazione | Risultato |
| --- | --- |
| `POST /telemetry` | Salva atomicamente la lettura se è più recente e restituisce l'ultima disponibile. |
| `GET /api/readings/latest` | Snapshot con `reading` e `pill_id` selezionati, `pills` con diagnostica e `last_received_at` per sorgente, `fermentation` attiva, `fermentation_reading`, `freshness_seconds` e `server_time`. Senza filtro sceglie la pillola attiva o, in diagnostica, la prima per nome e identificatore. |
| `GET /api/readings/events` | Stream SSE: invia subito lo stato persistito e poi le variazioni dell'ultima lettura, con eventi `reading`. |
| `GET /api/health` | Verifica che l'applicazione possa raggiungere MongoDB. |

Un messaggio non valido restituisce HTTP 422; una sorgente ben formata ma non registrata restituisce HTTP 404. Questi messaggi non modificano letture o ultima comunicazione. Se l'archivio non è disponibile, l'applicazione restituisce HTTP 503 invece di confermare un salvataggio inesistente. La documentazione interattiva delle API è disponibile all'indirizzo `/docs`.

## Avviare e terminare una fermentazione

Inserisci un nome nel campo **Nome della fermentazione**, scegli esplicitamente **Pillola della fermentazione** e premi **Avvia fermentazione**. Il nome non può essere vuoto o contenere soltanto spazi. La scelta della pillola è obbligatoria e rimane fissa durante il ciclo. La dashboard mostra nome, pillola, stato e istante di avvio; fino alla prima lettura della pillola nel suo intervallo mostra un'attesa esplicita, anche se esistono letture diagnostiche precedenti o dati di altre pillole.

Premi **Termina fermentazione** per concluderla: un messaggio conferma l'operazione, mentre nome, identificatore, avvio, termine e letture rimangono salvati. Puoi quindi avviarne un'altra, che inizierà senza ereditare le letture della precedente. Le operazioni fallite mostrano un errore e permettono di riprovare. Anche un'altra scheda del browser riceve lo stato corrente attraverso il collegamento live.

| Operazione | Risultato |
| --- | --- |
| `POST /api/fermentations` con `{"name":"Prima IPA","pill_id":"<id registrato>"}` | Crea e avvia la fermentazione; HTTP 201 con `fermentation` e identità della pillola scelta. |
| `GET /api/fermentations/active` | Restituisce `fermentation` attiva oppure `null`. |
| `GET /api/fermentations?q=IPA&limit=20&offset=0` | Elenco delle concluse, più recenti per prime; ricerca letterale per nome senza distinzione di maiuscole. Restituisce `fermentations` e `next_offset`. Limite da 1 a 50, predefinito 20. |
| `GET /api/fermentations/{id}` | Recupera nome, identificatore stabile, stato `active`/`concluded` e istanti UTC `started_at`/`ended_at`. |
| `GET /api/fermentations/{id}/readings?limit=200` | Recupera la finestra più recente dell'intervallo in ordine di acquisizione, anche dopo il termine. Restituisce `readings` e `next_before`; limite da 1 a 200, predefinito 200. |
| `POST /api/fermentations/{id}/end` | Conclude la fermentazione; HTTP 200 con lo stato aggiornato. |

Un nuovo avvio mentre esiste una fermentazione attiva, o il termine di una già conclusa, restituisce HTTP 409 con una spiegazione. Un identificatore sconosciuto restituisce HTTP 404; un nome non valido restituisce HTTP 422. Un indice univoco parziale MongoDB sullo stato attivo impone il vincolo anche con richieste concorrenti; viene creato all'avvio dell'applicazione e rimane nel volume del database. [Riferimento MongoDB sugli indici parziali univoci](https://www.mongodb.com/docs/manual/core/index-partial/).

Le letture sono associate per **pillola e timestamp di acquisizione: avvio incluso, termine escluso**. Gli estremi dell'intervallo sono conservati come secondi Unix UTC e restituiti dalle API come date ISO 8601. I campioni sono documenti separati, associati all'identificatore della fermentazione. Fuori dagli intervalli conosciuti viene mantenuta soltanto l'ultima lettura diagnostica di ogni pillola.

## Invii ripetuti e letture in ritardo

Una lettura viene riconosciuta da pillola, timestamp, valori completi di tutte le misure e flag `valid`. Una consegna identica conserva un solo campione, il suo primo orario di ricezione e il suo identificatore interno, anche con richieste simultanee o dopo un riavvio. Cambiare accelerazioni, velocità o flag di qualità produce un campione distinto, senza arrotondamenti. Un indice univoco MongoDB e un inserimento condizionale persistente impongono il vincolo. [Riferimento MongoDB sugli upsert e indici univoci](https://www.mongodb.com/docs/manual/reference/method/db.collection.updateOne/).

Una lettura consegnata in ritardo viene salvata nell'intervallo in cui è stata acquisita, anche se quella fermentazione è già conclusa e ne è iniziata un'altra. Una lettura più vecchia arricchisce lo storico senza sostituire quella corrente. I campioni distinti con lo stesso timestamp rimangono separati: i valori non sono arrotondati per riconoscere i duplicati. Il riepilogo della fermentazione segue lo stesso ordinamento dello storico, per acquisizione e poi ordine di persistenza; la lettura diagnostica non viene sostituita da consegne con timestamp uguale o più vecchio. I messaggi rifiutati dalla validazione non modificano lo storico.

Non è prevista una migrazione dal vecchio schema senza identità: il passaggio deliberato descritto sopra parte da un dataset pulito. Gli avvii ordinari del nuovo schema preservano registrazioni, campioni e indici.

## Grafici e storico

Durante una fermentazione attiva, i grafici di **densità SG** e **temperatura °C** e la tabella delle letture vengono caricati da MongoDB e aggiornati quando il collegamento live segnala una nuova lettura. La tabella include anche la **batteria %** e l'orario di acquisizione. Ogni punto dei grafici Chart.js corrisponde a un campione effettivo; non vengono aggiunti valori intermedi o campioni per colmare le lacune. I grafici a punti sono accompagnati dalla tabella, accessibile anche da tastiera. [Documentazione Chart.js: grafici a punti](https://www.chartjs.org/docs/latest/charts/scatter.html), [accessibilità](https://www.chartjs.org/docs/latest/general/accessibility.html).

Nel riquadro **Storico fermentazioni**, cerca un nome o scegli una fermentazione conclusa. La schermata mostra il nome, lo stato, gli istanti di avvio e termine, i grafici e i valori di quella fermentazione. Gli aggiornamenti dell'attiva non cambiano la scelta. La selezione è salvata nell'indirizzo `?fermentation=<id>`, quindi funziona anche dopo un reload, con Indietro/Avanti o riaprendo il collegamento dopo un riavvio dell'applicazione. **Monitoraggio attuale** torna all'attiva o alla lettura diagnostica. Una fermentazione senza dati ha uno stato esplicito; un caricamento fallito mostra un errore con possibilità di riprovare.

Ogni finestra contiene al massimo **200 letture originali**, condivise fra grafici e tabella; non è una media o una riduzione dei dati salvati. Usa **Letture precedenti** e **Letture più recenti** per consultare altre finestre. Il live aggiorna la finestra più recente dell'attiva; mentre consulti una finestra precedente questa rimane ferma. Le liste delle concluse mostrano 20 voci per pagina e permettono di caricarne altre. Su telefono i grafici si dispongono in verticale e la tabella scorre nel proprio riquadro.

Per le API, passa il valore opaco `next_before` come parametro `before` alla richiesta successiva, mantenendo lo stesso identificatore di fermentazione. Il cursore distingue anche campioni con lo stesso timestamp; ogni pagina è ordinata per acquisizione e conserva i valori originali. `next_before: null` indica la fine dello storico. Un cursore o un limite non valido restituisce HTTP 422. Le risposte dell'endpoint delle letture sono ora paginate: per recuperare uno storico intero occorre seguire i cursori.

## Aggiornamenti live e freschezza

La dashboard distingue **Nessuna lettura**, **Lettura disponibile** e **Dati non aggiornati**. L'età si riferisce all'acquisizione sul gateway, usando l'orario del server come riferimento; oltre la soglia conserva misure e orari reali. La soglia predefinita di cinque minuti è un criterio di freschezza, non la frequenza di trasmissione della pillola né una diagnosi di un dispositivo offline. L'esempio storico sopra apparirà quindi come non aggiornato.

Il collegamento live ha uno stato separato. Se si interrompe, la pagina conserva i valori e segnala la riconnessione automatica. Alla ripresa riceve un nuovo stato completo da MongoDB, recuperando anche le letture perse durante l'interruzione. Il recupero HTTP fornisce anche soglia e orario del server, così la freschezza viene valutata anche quando il live non è ancora disponibile.

Ogni connessione SSE legge MongoDB all'apertura e controlla le variazioni ogni secondo. Non usa notifiche in memoria come archivio. Gli eventi `reading` contengono lo stesso snapshot di `GET /api/readings/latest`, inclusi fermentazione e relativa lettura, soglia e `server_time` (secondi Unix). Il metadato `fermentation_reading_count`, ricavato dai campioni persistiti dell'attiva, permette di notificare anche una lettura precedente all'ultima: la tabella e i grafici si aggiornano mentre i valori correnti restano corretti. I duplicati non aumentano il conteggio. Il browser usa il riferimento del server e il tempo trascorso per aggiornare lo stato anche senza nuovi eventi. Alla riconnessione viene sempre inviato lo stato persistito corrente, anche con `Last-Event-ID`: non è uno stream dello storico. Se MongoDB diventa irraggiungibile, lo stream invia `unavailable` e si chiude per consentire un nuovo tentativo; le connessioni inattive ricevono commenti di mantenimento.

## Indisponibilità e ripresa

Quando MongoDB non è disponibile, letture, avvio e termine restituiscono HTTP 503 con una spiegazione. Un invio non salvato non viene confermato come riuscito e lo stream non invia una lettura inventata. La dashboard conserva gli eventuali valori già caricati con il loro vero istante di acquisizione; l'età continua a essere valutata senza trasformare un caricamento fallito in una nuova misura. Se non ha ancora ricevuto uno stato valido, indica che il monitoraggio non è disponibile e attende i dati prima di proporre l'avvio di una fermentazione.

Quando il collegamento live riprende, la pagina rilegge anche l'elenco delle concluse e lo storico selezionato, mantenendo fermentazione scelta e finestra delle letture. Un caricamento storico fallito può essere ritentato anche con il pulsante **Riprova storico**. Le operazioni di avvio o termine fallite non vengono eseguite automaticamente alla riconnessione: lo stato salvato rimane visibile e l'operazione può essere riprovata.

Ripristina i servizi con `./scripts/hackbrew up` se erano stati fermati. Dopo il ritorno di MongoDB, una nuova acquisizione valida riprende il monitoraggio sullo stesso volume. Il gateway esterno attuale può eliminare un messaggio dopo un invio fallito: HackBrew non ricostruisce quelle letture e non aggiunge buffer o ritrasmissioni al gateway.

Per osservare il protocollo, in un terminale separato:

```sh
curl --no-buffer http://localhost:8080/api/readings/events
```

## Sviluppo

```sh
./scripts/hackbrew dev
```

Apri **http://localhost:5173** per l'interfaccia con ricaricamento automatico. FastAPI resta disponibile sulla porta 8080 e viene ricaricato quando cambia il codice Python. Vite inoltra le richieste all'API attraverso la rete Docker.

## Build e controlli

```sh
./scripts/hackbrew build
./scripts/hackbrew format
./scripts/hackbrew format-check
./scripts/hackbrew lint
./scripts/hackbrew typecheck
./scripts/hackbrew test
./scripts/hackbrew test-recovery
```

`format` applica Ruff e Prettier ai file di codice. `lint` usa Ruff ed ESLint. `typecheck` usa mypy e vue-tsc. Ogni strumento viene eseguito in Docker.

Le immagini di base e di MongoDB sono fissate tramite digest. Le dipendenze npm sono risolte nel lockfile; le dipendenze Python, incluse quelle transitive, sono fissate nei file `requirements.lock` e `requirements-dev.lock`. Quando si aggiornano le dipendenze dirette, vanno rigenerati e verificati anche i rispettivi lockfile in Docker.

Il lockfile npm include una versione corretta di `minimatch` tramite override per [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249), in attesa che i pacchetti di lint aggiornino i propri intervalli di dipendenza.

Per eseguire tutti i controlli:

```sh
./scripts/hackbrew check
```

Per un solo file o un singolo caso:

```sh
./scripts/hackbrew test tests/integration/test_readings.py
./scripts/hackbrew test tests/integration/test_readings.py -k older
./scripts/hackbrew test tests/browser/test_dashboard.py
./scripts/hackbrew test tests/integration/test_live_readings.py
./scripts/hackbrew test tests/browser/test_live_dashboard.py
./scripts/hackbrew test tests/integration/test_fermentations.py
./scripts/hackbrew test tests/browser/test_fermentation_dashboard.py
./scripts/hackbrew test tests/integration/test_history.py
./scripts/hackbrew test tests/browser/test_history_dashboard.py
./scripts/hackbrew test tests/browser/test_history_pages.py
./scripts/hackbrew test tests/integration/test_delivery.py
./scripts/hackbrew test tests/browser/test_delivery_dashboard.py
./scripts/hackbrew test tests/integration/test_pills.py
./scripts/hackbrew test tests/browser/test_pills_dashboard.py
```

La suite invia messaggi HTTP all'applicazione reale, usa MongoDB reale e verifica la dashboard con Chromium tramite Playwright. L'ambiente isolato imposta la freschezza a 60 secondi; il test browser avanza il tempo per verificare l'invecchiamento senza attese reali. I test live verificano anche la riconnessione dopo un'interruzione di rete. I test dello storico creano fermentazioni distinguibili, verificano selezione e reload e percorrono oltre 200 campioni senza perderne i valori. I test di consegna coprono invii ripetuti e concorrenti, valori distinti allo stesso timestamp, letture fuori ordine e confini tra due fermentazioni.

Il controllo completo conserva fuori dall'applicazione uno snapshot JSON di pillole, fermentazioni, letture e identificatori, poi riavvia il container applicativo sullo stesso volume di test. Tutte le verifiche osservano le API e il browser: registrazioni e misure separate per pillola preservate, nuove consegne idempotenti anche concorrenti, riapertura dei grafici storici e vincolo di avvio concorrente dopo il riavvio. La vecchia prova di migrazione dei duplicati MVP è sostituita dalla verifica del nuovo schema persistente, coerentemente con il reset concordato.

Il controllo completo esegue inoltre la prova operativa disponibile separatamente con `./scripts/hackbrew test-recovery`. La prova crea una fermentazione conclusa e una attiva, apre monitoraggio e storico nel browser, ferma MongoDB e verifica gli errori HTTP 503, i valori conservati e un termine fallito nell'interfaccia. Ripristina MongoDB, invia una nuova acquisizione e verifica il recupero automatico dello storico; poi ferma l'applicazione e ricrea entrambi i container mantenendo il volume di test. Controlla dati persistiti, riconnessione live, nuova lettura e successivo termine manuale. I messaggi rifiutati durante i guasti non vengono ritrasmessi dal test.

La procedura usa soltanto un progetto `hackbrew-tests-*` e il suo volume isolato. Un coordinatore esterno interrompe e ripristina i servizi mentre il browser rimane aperto nel container dei test; il container applicativo non espone controlli speciali per i test. Non servono credenziali personali, hardware o dati di produzione. `./scripts/hackbrew test <file o argomenti pytest>` esegue soltanto i casi selezionati, mentre `test` senza argomenti e `check` includono anche riavvio e prova di indisponibilità.

Ogni esecuzione crea un progetto Compose distinto con database e volume di test isolati. La pulizia tra i casi rimuove i documenti mantenendo gli indici dell'applicazione; al termine vengono rimossi soltanto i container e il volume di quella esecuzione. I test non richiedono una pillola, il gateway reale, credenziali GitHub o l'accesso al volume dell'applicazione.

Le prove browser salvano schermate desktop/telefono in `artifacts/`, esclusa da Git. Le immagini `pillole-1440.png` e `pillole-390.png` mostrano il registro con due pillole e diagnostiche distinte.

## Struttura

```text
src/hackbrew/          Applicazione FastAPI e gestione delle letture
src/frontend/         Applicazione Vue, configurazione e lockfile npm
tests/integration/    Verifiche attraverso l'API HTTP
tests/browser/        Verifiche della dashboard nel browser
tests/check_restart.py Verifica operativa di persistenza al riavvio
tests/check_recovery.py Verifica operativa HTTP/browser delle indisponibilità
scripts/hackbrew      Comandi di progetto eseguiti tramite Docker
scripts/check-recovery Coordinamento dei guasti nel solo progetto di test
docs/                 Specifica, glossario operativo e piano dei ticket
compose.yaml          Applicazione e strumenti
compose.dev.yaml      Configurazione di sviluppo
compose.test.yaml     Ambiente di test isolato
Dockerfile            Build multi-stage e immagini di sviluppo e test
```

La terminologia è definita in [GLOSSARY.md](GLOSSARY.md); il formato del gateway e le fonti sono descritti nella [documentazione dell'integrazione](docs/integrations/rapt-gateway.md).
