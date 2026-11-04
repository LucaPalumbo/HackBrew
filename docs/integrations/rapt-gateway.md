# Integrazione con RaptPillGateway-ble-http

La [issue #11](https://github.com/LucaPalumbo/HackBrew/issues/11) collega il vero [bridge esterno](https://github.com/LucaPalumbo/RaptPillGateway-ble-http) al registro di HackBrew. Un solo processo acquisisce tutte le pillole registrate dalla pagina **Dispositivi**, senza un secondo elenco manuale di MAC. Il bridge resta esterno ai tre componenti applicativi; i test lo eseguono nello stesso container degli strumenti, senza un quarto servizio obbligatorio.

## Registro HTTP

`GET /api/bridge/pills` restituisce uno snapshot completo:

```json
{
  "revision": "<hash opaco del contenuto>",
  "pills": [{"id": "<identificatore stabile>", "name": "Pillola IPA", "mac": "AA:BB:CC:DD:EE:FF"}]
}
```

La revisione è una stringa opaca di uguaglianza, non un contatore o un orario. È calcolata sull'esatto elenco restituito, ordinato per identità stabile. Cambia con le registrazioni e resta uguale tra polling, misure, avvii/termini delle fermentazioni e riavvii dell'applicazione. La lettura del registro non rinnova il contatto di alcuna pillola. Con MongoDB indisponibile l'endpoint restituisce HTTP 503.

Il bridge acquisisce il registro all'avvio e periodicamente (30 secondi predefiniti). Valida tutto lo snapshot prima di sostituire il filtro delle sorgenti. Senza un primo snapshot valido ignora tutte le pillole e segnala `registry_sync_failed revision=unavailable`; con un precedente snapshot valido lo conserva e ne segnala la revisione. Nuove registrazioni entrano nel filtro alla successiva sincronizzazione riuscita. Non c'è una copia durevole del registro nel bridge.

La configurazione del gateway contiene soltanto gli URL `registry.url` e `http.url`, i rispettivi `timeout_seconds` e `registry.poll_interval_seconds`. Copiare il suo `config.example.yaml` in `config.yaml`: il vecchio `ble.mac_address` è stato sostituito. Gli URL devono essere raggiungibili dal bridge. Per una macchina LAN separata modificare anche il bind di HackBrew. Autenticazione rinviata; non vengono introdotte credenziali nel protocollo.

## Letture e sorgente

`POST /telemetry` mantiene i nove campi del gateway e aggiunge `pill_mac`, normalizzato in maiuscolo con due punti e ricavato dall'indirizzo BLE. Il server risolve la pillola dal MAC già registrato: nessun messaggio crea implicitamente una registrazione o viene assegnato a una sorgente arbitraria.

| Campo | Significato |
| --- | --- |
| `valid` | Validità della sola velocità della densità. `false` non invalida le altre quantità. |
| `gravity_velocity` | Punti SG/giorno; valore originale conservato anche se non valido. |
| `temperature` | °C, dal valore uint16 big endian / 128 − 273.15. |
| `specific_gravity` | SG × 1000 nel bridge; HackBrew divide per 1000 una sola volta. |
| `accel_x/y/z` | int16 big endian con segno / 16; unità fisica non specificata. |
| `battery` | Percentuale, valore originale / 256. |
| `timestamp` | Secondi Unix assegnati all'acquisizione dall'orologio del bridge. |

Il bridge decodifica misure RAPT v2 di 25 byte, inclusi i due byte manufacturer ID che Bleak espone separatamente. Ignora v1/versioni non supportate, messaggi KEG e messaggi HW; rifiuta esplicitamente v2 troncati e valori non validi. La prima versione aveva un accesso a una variabile non inizializzata per payload sconosciuti e interpretava gli assi come uint16: sono corretti senza inventare l'unità degli accelerometri.

Il [parser di riferimento](https://github.com/sairon/rapt-ble/blob/1473743be0d6dc9c151aae64588e7feffe7147c6/src/rapt_ble/parser.py) documenta il layout `>Bx?fHfhhhh`. Le [fixture originali](https://github.com/sairon/rapt-ble/blob/1473743be0d6dc9c151aae64588e7feffe7147c6/tests/test_parser.py) distinguono velocità valida/non valida, SG circa 1.0213/1.0109 e temperatura circa 19.69/23.94 °C. `fixtures/rapt-v2.json` nel gateway conserva questi byte e una variante esplicita con assi -1/-2/+3. Le asserzioni usano questi risultati indipendenti, non il parser per costruire l'atteso. La prova software non sostituisce una cattura da hardware reale.

## Duplicati e guasti

La finestra di soppressione di due secondi usa l'orologio monotono e uno stato distinto per MAC. Payload identici di pillole diverse non si sopprimono. Dispositivi sconosciuti vengono ignorati dal bridge; l'API rifiuta comunque un MAC non registrato con HTTP 404.

Il trasporto usa una coda in memoria e un solo tentativo HTTP per rilevazione. HTTP fallito o timeout producono `reading_delivery_failed`, senza `reading_forwarded`, buffer durevole o ritrasmissione. Il successo viene registrato solo dopo una risposta HTTP di successo. Dopo un guasto riprendono le nuove acquisizioni; le vecchie non sono ricostruite. La deduplicazione persistente di HackBrew rimane distinta dal filtro BLE.

## Verifica automatica delle due repository

Il build context Docker `gateway` in `compose.test.yaml` fissa il [commit reale del gateway `de4cd63`](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/commit/de4cd6395b67b97f154fe0ed6f5cd8fa82a35e90); non è una copia finta del bridge. I test avviano `main.py --replay -`: solo il confine hardware viene sostituito con JSON Lines che costruiscono gli oggetti Bleak e chiamano **lo stesso callback** registrato sullo scanner reale. Parser, sincronizzazione periodica e invio HTTP sono quelli di produzione; API HackBrew e MongoDB sono reali.

```sh
./scripts/hackbrew test tests/integration/test_bridge.py tests/browser/test_bridge_dashboard.py
```

Le prove verificano più sorgenti, tutti i nove campi, il filtro dei duplicati per MAC, payload non misura, assi negativi, flag qualità, aggiunte dal browser senza riavvio e problemi del registro. Un proxy HTTP controllabile verifica 503, timeout e snapshot malformati, inoltrando le richieste riuscite all'applicazione reale. Nessuna asserzione consulta direttamente MongoDB. Il controllo completo verifica anche la stabilità dello snapshot del registro attraverso un vero riavvio.

Per usare una checkout locale del gateway prima di pubblicarla:

```sh
HACKBREW_GATEWAY_SOURCE=/percorso/assoluto/RaptPillGateway-ble-http \
  ./scripts/hackbrew test tests/integration/test_bridge.py tests/browser/test_bridge_dashboard.py
```

L'override vale anche per `./scripts/hackbrew check`. La repository del gateway è privata: per il build delle prove occorre una checkout locale autorizzata (override sopra) oppure `HACKBREW_GATEWAY_TOKEN`, esportato nell'ambiente della shell con accesso in lettura alla repository. Con GitHub CLI già autenticata:

```sh
export HACKBREW_GATEWAY_TOKEN="$(gh auth token)"
./scripts/hackbrew test tests/integration/test_bridge.py tests/browser/test_bridge_dashboard.py
unset HACKBREW_GATEWAY_TOKEN
```

Lo script aggiunge `compose.bridge-auth.yaml` soltanto al build delle prove. Il token viene fornito al fetch Git come secret BuildKit `GIT_AUTH_TOKEN.github.com`, secondo la [documentazione Docker](https://docs.docker.com/build/building/secrets/#git-authentication-for-remote-contexts), senza credenziali nell'URL, build argument o immagine. L'override locale permette di verificare la stessa sorgente senza autenticazione durante il build; per riprodurre esattamente la consegna usa il commit fissato sopra, mentre per lo sviluppo puoi usare i file modificati della checkout. Il normale build remoto usa sempre il commit completo, non la testa mutevole di un branch. La build dell'applicazione non scarica né avvia il bridge e non richiede questa configurazione.

Il [README del bridge](https://github.com/LucaPalumbo/RaptPillGateway-ble-http#readme) descrive configurazione, comando replay riproducibile, strumenti containerizzati e procedura con pillole vere. Non sono richiesti adattatore Bluetooth, D-Bus, Python o Node sull'host per le prove automatiche. Il progetto Docker di test e il volume rimangono isolati dai dati applicativi.
