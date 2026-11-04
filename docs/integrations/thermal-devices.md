# Dispositivi termici e contratto HTTP provvisorio

La [#14](https://github.com/LucaPalumbo/HackBrew/issues/14) introduce registrazione e osservazione dei dispositivi. La regolazione delle fermentazioni appartiene alla [#16](https://github.com/LucaPalumbo/HackBrew/issues/16); impostazione globale e sincronizzazione del timeout alla [#15](https://github.com/LucaPalumbo/HackBrew/issues/15). Questa versione non offre un override manuale e non invia comandi ON dalle fermentazioni.

## Registrazione e verifica nell'applicazione

Nella pagina **Dispositivi**, sotto le pillole, inserire nome, funzioni e indirizzo HTTP(S) raggiungibile dal **server**. Sono supportati riscaldamento, raffreddamento e entrambe le funzioni. Nome non vuoto (massimo 200 caratteri), capacità riconosciuta e URL valido sono obbligatori. L'URL può contenere un percorso base, ma non credenziali, query o frammenti. Host, porta predefinita e slash finale sono normalizzati; un indirizzo equivalente già registrato produce HTTP 409, anche con richieste concorrenti.

| API HackBrew | Risultato |
| --- | --- |
| `GET /api/thermal-devices` | `devices`: registro persistito con identificatori stabili e ultima osservazione. |
| `POST /api/thermal-devices` | `{"name":"Frigo","capability":"both","base_url":"http://frigo.local:8000"}`; HTTP 201 con `device`. Capacità: `heating`, `cooling`, `both`. |
| `POST /api/thermal-devices/{id}/check` | Esegue soltanto GET dello stato del dispositivo. Restituisce `device` con risultato della verifica, anche se la comunicazione fallisce. Non invia comandi e non rinnova il timeout. |

Il registro distingue `verification_status`: `unverified`, `confirmed`, `pending`, `error`. Prima della verifica `actual_mode` è `null`. Una risposta valida espone capacità riportata, modo richiesto/effettivo, `application_status`, istante della conferma fisica e timeout/revisione applicati. Una semplice accettazione del comando non è una conferma fisica.

In caso di HTTP fallito, risposta malformata, capacità incompatibili o timeout di trasporto (due secondi), `actual_mode` e i campi di conferma corrente sono `null`; il dispositivo è sconosciuto/in errore, non spento confermato. `last_confirmation` conserva separatamente l'ultima osservazione fisica precedente con il suo vero orario. La pagina segnala anche i comandi in attesa di conferma e lo spegnimento autonomo. Le osservazioni mostrate sono riferite all'ultima verifica, non una garanzia di stato radio o hardware in tempo reale; **Verifica collegamento** esegue una nuova interrogazione e **Aggiorna dispositivi termici** rilegge il registro.

Una verifica HTTP più vecchia e lenta non può sovrascrivere una verifica iniziata successivamente. Le revisioni delle verifiche sono persistite e aggiornate atomicamente. HTTP 404 indica un identificatore sconosciuto, HTTP 422 input non valido. Se MongoDB è indisponibile, le API rispondono HTTP 503 senza confermare una registrazione o un risultato non salvato.

L'adattatore sostituibile è `src/hackbrew/thermal_client.py`: racchiude GET/PUT, percorsi, timeout di trasporto e validazione del protocollo. La futura regolazione userà l'operazione di comando dello stesso adattatore; in questa consegna l'applicazione usa soltanto la lettura dello stato.

## Contratto del dispositivo, versione 1

Gli endpoint seguenti appartengono al dispositivo esterno o al simulatore, non all'applicazione HackBrew.

- `GET /api/v1/state`: capacità, identità del dispositivo, identità dell'avvio e stato confermato.
- `PUT /api/v1/control`: comando assoluto `off`, `heating` o `cooling`. `off` disabilita entrambe le funzioni di un dispositivo combinato.

Esempio di comando:

```json
{
  "boot_id": "<dall'ultima lettura di stato>",
  "command_id": "<identificatore univoco del comando>",
  "ownership_epoch": 1,
  "ownership_id": "<identificatore dell'assegnazione>",
  "sequence": 1,
  "mode": "off",
  "timeout_seconds": 10800,
  "config_revision": 0
}
```

`timeout_seconds` è una durata positiva e finita, in secondi, con valore iniziale/predefinito **10800 (tre ore)**. Gli altri campi sono obbligatori. Epoch e sequenza sono interi positivi; revisione della configurazione intero non negativo. Il server deve conservare le proprie revisioni e assegnazioni attraverso i suoi riavvii. Non utilizzare l'orologio del browser per generare l'ordine dei comandi.

Ogni nuova assegnazione usa un epoch maggiore, un'identità coerente e un primo OFF; ON è accettabile soltanto dopo la conferma fisica dell'OFF di quell'epoch. All'interno dell'epoch la sequenza aumenta. Un'identità di assegnazione diversa nello stesso epoch è un conflitto. Un comando di epoch precedente resta obsoleto anche se ha una sequenza molto grande.

Ripetere esattamente l'ultimo comando restituisce lo stato corrente senza riapplicarlo e **senza rinnovare la scadenza**. Un vecchio comando superato, sequenze in conflitto o riuso dell'identità del comando producono HTTP 409 e non cambiano stato o scadenza. Un nuovo comando valido, con nuova sequenza/identità, rinnova il contatto anche se richiede lo stesso modo. Modi non supportati o valori malformati producono HTTP 422. Non esiste il modo `both`: riscaldamento e raffreddamento sono mutuamente esclusivi.

La revisione del timeout non può retrocedere; riusare la stessa revisione con una durata diversa è un conflitto. Timeout/revisione richiesti nel comando e timeout/revisione effettivamente applicati restano distinti finché manca l'applicazione fisica.

Un nuovo avvio del simulatore genera un `boot_id` diverso e parte OFF. I comandi di un avvio precedente sono rifiutati: dopo un riavvio occorre rileggere lo stato e riconciliare il dispositivo. Il simulatore non richiede persistenza su disco per impedire che un pacchetto del vecchio avvio lo riaccenda.

### Accettazione e conferma fisica

GET e PUT restituiscono lo stesso schema:

```json
{
  "protocol_version": 1,
  "device_id": "demo-thermal",
  "boot_id": "<identificatore dell'avvio>",
  "capability": "both",
  "desired_mode": "off",
  "actual_mode": "off",
  "application_status": "applied",
  "accepted_command": null,
  "applied_command_id": null,
  "applied_timeout_seconds": 10800,
  "applied_config_revision": 0,
  "confirmed_at": "2026-11-04T12:00:00Z",
  "last_command_at": null,
  "lease_expires_at": null
}
```

L'esempio rappresenta un dispositivo appena avviato, senza comandi. Dopo un comando, `accepted_command` contiene il corpo completo accettato, `last_command_at` il suo istante di ricezione e `lease_expires_at` la scadenza diagnostica in secondi Unix. I confronti di durata del simulatore usano l'orologio monotono, non l'orologio di parete.

`application_status` distingue:

- `applied`: modo, identità del comando, timeout e revisione sono confermati come applicati.
- `pending`: il comando è accettato; modo e configurazione applicati possono ancora essere quelli precedenti.
- `unknown`: conferma fisica indisponibile; `actual_mode` e `confirmed_at` sono `null`.
- `timed_out`: spegnimento autonomo confermato, anche se `desired_mode` era ON. La precedente identità applicata non costituisce una nuova conferma ON.

Dopo l'assenza di nuovi comandi validi per la durata applicata, il dispositivo deve spegnersi autonomamente. Il simulatore lo controlla con un task indipendente dalle richieste HTTP, ogni 20 ms. GET di stato, richieste rifiutate e retry identici non rinnovano il contatto. L'OFF autonomo cancella le applicazioni pendenti; un'applicazione ritardata non può attivare una lease già scaduta. Anche un OFF più recente o una nuova assegnazione sostituiscono il comando pendente, impedendo che il vecchio ON prevalga successivamente.

Le risposte vengono validate: HTTP 200 con `{"actual_mode":"off"}` non basta come conferma. Sono necessari versione, capacità, metadati e coerenza tra accettazione e applicazione. Non si deduce mai lo stato fisico dal solo completamento della scrittura HTTP.

## Simulatore opzionale di sviluppo

```sh
./scripts/hackbrew simulator
```

Il simulatore combinato è raggiungibile sull'host a `http://localhost:8081`; nella pagina Dispositivi registrare **`http://thermal-simulator:8000`**, perché la connessione parte dal container del backend. La normale applicazione continua a richiedere soltanto frontend, backend e MongoDB; il simulatore è uno strumento opzionale. `./scripts/hackbrew down` lo arresta insieme all'applicazione.

`HACKBREW_SIMULATOR_PORT` cambia la porta host e `HACKBREW_SIMULATOR_CAPABILITY` sceglie `heating`, `cooling` o `both` prima dell'avvio. Nessuna pillola o dispositivo fisico viene controllato dal simulatore.

Gli endpoint di simulazione sono presenti solo in questo servizio:

- `POST /__simulation/reset`: ripartenza OFF con nuovo `boot_id` e impostazioni predefinite.
- `PATCH /__simulation`: modifica solo le proprietà fornite: `state_http_status`/`control_http_status` (`200` o `503`), `state_delay_seconds`, `control_delay_seconds`, `apply_delay_seconds` (0–10 secondi), `confirmation_available` e `malformed_state` (booleani). `malformed_state` simula una risposta HTTP 200 senza un contratto valido.

Il ritardo HTTP di un comando avviene prima della sua accettazione, permettendo di simulare un vecchio pacchetto ricevuto dopo un OFF più recente. Il ritardo di applicazione riguarda invece il completamento fisico dopo l'accettazione; sono due condizioni distinte. La mancata conferma nasconde lo stato fisico, ma non ferma il watchdog.

Per osservare e simulare un errore, con `curl` disponibile:

```sh
curl --fail-with-body http://localhost:8081/api/v1/state
curl --fail-with-body -X PATCH http://localhost:8081/__simulation \
  -H 'Content-Type: application/json' --data '{"state_http_status":503}'
# Premi Verifica collegamento in HackBrew: deve mostrare stato sconosciuto.
curl --fail-with-body -X PATCH http://localhost:8081/__simulation \
  -H 'Content-Type: application/json' --data '{"state_http_status":200}'
```

## Verifiche automatiche

```sh
./scripts/hackbrew test tests/integration/test_thermal_devices.py
./scripts/hackbrew test tests/integration/test_thermal_contract.py
./scripts/hackbrew test tests/browser/test_thermal_devices_dashboard.py
./scripts/hackbrew check
```

Come per le altre prove, configurare prima l'accesso alla sorgente privata del gateway come indicato nel README. Il workflow crea simulatori distinti per ogni capacità sulla sola rete Docker di test, con MongoDB e volume isolati. I test osservano HTTP e browser; non interrogano internamente il database. Verificano tutte le capacità, validazione, doppie registrazioni concorrenti, stato sconosciuto, risposte malformate, ritardi, rifiuti e recupero; ordinamento, idempotenza, generazioni delle assegnazioni, nuova identità di avvio e spegnimento autonomo senza letture HTTP. Le prove veloci configurano durate brevi attraverso il contratto, senza cambiare il valore predefinito di tre ore.

Il controllo completo verifica inoltre che registro e conferme persistano dopo un vero riavvio dell'applicazione e che le API restituiscano HTTP 503 durante un guasto reale a MongoDB. Le schermate desktop/telefono sono in `artifacts/dispositivi-termici-1440.png` e `artifacts/dispositivi-termici-390.png` (escluse da Git).

Queste prove certificano il comportamento del simulatore e dell'integrazione software, **non firmware o hardware reali**. Non vengono implementati driver o firmware. I futuri dispositivi fisici dovranno implementare lo stesso protocollo, conferme reali e scadenza autonoma; gli endpoint potranno essere sostituiti nell'adattatore.
