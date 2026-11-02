# HackBrew

Dashboard web per monitorare una pillola nel fermentatore. Riceve le letture del gateway HTTP esistente, conserva l'ultima in MongoDB e aggiorna automaticamente densità SG, temperatura °C, batteria e orario di acquisizione. Il pulsante **Aggiorna lettura** permette anche un recupero manuale.

Frontend Vue 3 con TypeScript e Vite, backend Python/FastAPI e MongoDB. Il frontend viene compilato in Docker e servito da FastAPI. Il gateway Bluetooth è esterno al progetto. Fermentazioni e grafici sono descritti nei ticket successivi della [specifica](https://github.com/LucaPalumbo/HackBrew/issues/1).

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

Il messaggio attuale del gateway è accettato senza aggiungere identificatori o intestazioni di autenticazione:

```json
{
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
- I campi aggiuntivi del gateway sono accettati; le quattro misure necessarie sono temperatura, densità, batteria e timestamp.
- Valori più vecchi o dello stesso istante non sostituiscono l'ultima lettura. Viene conservato un solo documento diagnostico, non uno storico di prove.

Per una prova su un database vuoto, se `curl` è disponibile:

```sh
curl --fail-with-body http://localhost:8080/telemetry \
  --header 'Content-Type: application/json' \
  --data '{"valid":false,"temperature":19.6875,"specific_gravity":1050.125,"battery":63.2734375,"timestamp":1700000000.123456}'
```

Il timestamp dell'esempio è storico: il gateway reale deve usare il proprio orario di acquisizione. Una prova più vecchia dell'ultima lettura già salvata non la sostituisce.

| Operazione | Risultato |
| --- | --- |
| `POST /telemetry` | Salva atomicamente la lettura se è più recente e restituisce l'ultima disponibile. |
| `GET /api/readings/latest` | Snapshot con `reading: null` prima della prima lettura, altrimenti le misure normalizzate e i due istanti; include `freshness_seconds` e `server_time`. |
| `GET /api/readings/events` | Stream SSE: invia subito lo stato persistito e poi le variazioni dell'ultima lettura, con eventi `reading`. |
| `GET /api/health` | Verifica che l'applicazione possa raggiungere MongoDB. |

Un messaggio non valido restituisce HTTP 422. Se l'archivio non è disponibile, l'applicazione restituisce HTTP 503 invece di confermare un salvataggio inesistente. La documentazione interattiva delle API è disponibile all'indirizzo `/docs`.

## Aggiornamenti live e freschezza

La dashboard distingue **Nessuna lettura**, **Lettura disponibile** e **Dati non aggiornati**. L'età si riferisce all'acquisizione sul gateway, usando l'orario del server come riferimento; oltre la soglia conserva misure e orari reali. La soglia predefinita di cinque minuti è un criterio di freschezza, non la frequenza di trasmissione della pillola né una diagnosi di un dispositivo offline. L'esempio storico sopra apparirà quindi come non aggiornato.

Il collegamento live ha uno stato separato. Se si interrompe, la pagina conserva i valori e segnala la riconnessione automatica. Alla ripresa riceve un nuovo stato completo da MongoDB, recuperando anche le letture perse durante l'interruzione. Il recupero HTTP fornisce anche soglia e orario del server, così la freschezza viene valutata anche quando il live non è ancora disponibile.

Ogni connessione SSE legge MongoDB all'apertura e controlla le variazioni ogni secondo. Non usa notifiche in memoria come archivio. Gli eventi `reading` contengono `reading` (anche `null`), `freshness_seconds` e `server_time` (secondi Unix). Il browser usa il riferimento del server e il tempo trascorso per aggiornare lo stato anche senza nuovi eventi. Alla riconnessione viene sempre inviata l'ultima lettura persistita, anche con `Last-Event-ID`: non è uno stream dello storico. Se MongoDB diventa irraggiungibile, lo stream invia `unavailable` e si chiude per consentire un nuovo tentativo; le connessioni inattive ricevono commenti di mantenimento.

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
```

La suite invia messaggi HTTP all'applicazione reale, usa MongoDB reale e verifica la dashboard con Chromium tramite Playwright. L'ambiente isolato imposta la freschezza a 60 secondi; il test browser avanza il tempo per verificare l'invecchiamento senza attese reali. I test live verificano anche la riconnessione dopo un'interruzione di rete. Il controllo completo verifica inoltre che un riavvio del container applicativo conservi i dati.

Ogni esecuzione crea un progetto Compose distinto con database e volume di test isolati. Al termine vengono rimossi soltanto i container e il volume di quella esecuzione. I test non richiedono una pillola, il gateway reale, credenziali GitHub o l'accesso al volume dell'applicazione.

## Struttura

```text
src/hackbrew/          Applicazione FastAPI e gestione delle letture
src/frontend/         Applicazione Vue, configurazione e lockfile npm
tests/integration/    Verifiche attraverso l'API HTTP
tests/browser/        Verifiche della dashboard nel browser
tests/check_restart.py Verifica operativa di persistenza al riavvio
scripts/hackbrew      Comandi di progetto eseguiti tramite Docker
docs/                 Specifica, glossario operativo e piano dei ticket
compose.yaml          Applicazione e strumenti
compose.dev.yaml      Configurazione di sviluppo
compose.test.yaml     Ambiente di test isolato
Dockerfile            Build multi-stage e immagini di sviluppo e test
```

La terminologia è definita in [GLOSSARY.md](GLOSSARY.md); il formato del gateway e le fonti sono descritti nella [documentazione dell'integrazione](docs/integrations/rapt-gateway.md).
