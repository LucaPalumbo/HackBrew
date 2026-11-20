# Verifica e dimostrazione del sistema completo

## Prova automatica riproducibile

Dalla checkout di HackBrew, configura l'accesso alla sorgente del bridge come nella [guida](../integrations/rapt-gateway.md#verifica-automatica-delle-due-repository). La sorgente remota è fissata al commit `de4cd6395b67b97f154fe0ed6f5cd8fa82a35e90`; una checkout locale dello stesso commit evita credenziali durante il build. Servono Docker e Compose, senza Python, Node, MongoDB o hardware installati sul computer ospite.

```sh
# Suite completa: controlli statici, HTTP/browser, upgrade e tutte le prove operative.
./scripts/hackbrew check

# Conversione standalone e persistenza della gestione del registro.
./scripts/hackbrew test-registry-upgrade

# Tutte le prove di guasto e recupero, senza rieseguire pytest.
./scripts/hackbrew test-recovery

# Solo il nuovo scenario continuo con bridge e più fermentazioni.
./scripts/hackbrew test-recovery assembled

# Solo le riconnessioni di rete su desktop e telefono.
./scripts/hackbrew test tests/browser/test_assembled_monitoring.py
```

`test-recovery assembled` è una dimostrazione eseguibile: parte da un database di test vuoto, registra quattro pillole (una resta libera), tre dispositivi e tre fermentazioni. IPA usa riscaldamento e raffreddamento separati, Lager un dispositivo combinato, Solo letture rimane in solo monitoraggio. Un unico processo del **vero bridge** sincronizza il registro e riceve advertisement BLE deterministici al proprio confine hardware; parser, trasporto HTTP, applicazione e MongoDB sono reali.

La sequenza verifica:

1. Tutte le misure delle sorgenti rimangono separate, compresi timestamp, velocità non valida e accelerazioni con segno. IPA riscalda mentre Lager raffredda, con gli attuatori appropriati.
2. Il browser desktop resta sul dettaglio IPA con un sottointervallo storico selezionato e batteria nascosta dalla legenda; il telefono resta sul dettaglio Lager. Tabelle, istanti acquisiti, intervalli, serie selezionate e indirizzi rimangono quelli scelti durante tutti i guasti.
3. Una modifica di fascia e isteresi viene salvata nella cronologia. Un arresto reale del processo applicativo seguito dal riavvio conserva l'isteresi in corso, assegnazioni e dati. Un secondo riavvio trova il riscaldatore senza conferma fisica, pur con dati freschi e ON persistito: l'osservazione HTTP dei comandi verifica che non venga inviato ON prima della riconciliazione. L'altra fermentazione continua indipendentemente.
4. Si interrompono separatamente il collegamento del browser e gli endpoint raggiunti dal bridge. Le consegne fallite non sono confermate né ritrasmesse e non aggiornano l'ultima comunicazione. Il registro riprende il polling senza diventare telemetria.
5. Il coordinatore ferma davvero MongoDB. Telemetria, modifiche di fascia/timeout e termine non vengono confermati; i watchdog degli attuatori raggiungono OFF. Al ripristino, letture, configurazione e tempi di ricezione coincidono con quelli salvati prima del guasto. Nuove acquisizioni consentono la ripresa.
6. Si salva il termine della Lager mentre manca la conferma fisica del combinato. La prenotazione resta bloccata. Una nuova revisione del timeout rimane in attesa per quel dispositivo.
7. Il coordinatore arresta il server mentre IPA è ancora in riscaldamento. La prova osserva ON dopo l'arresto, quindi OFF autonomo; ricrea applicazione e MongoDB sullo stesso volume. Stato concluso, OFF pendente, revisioni richieste/applicate, fascia e cronologia sono recuperati.
8. Un vecchio ON viene rifiutato. Nuove misure non riaprono la Lager; Solo letture rimane in monitoraggio. IPA riprende e cambia funzione solo dopo la conferma OFF del riscaldatore. Il ritorno delle conferme libera il combinato e completa la sincronizzazione del timeout.
9. **Torna al live** riprende il grafico IPA. Il termine dal browser conferma lo spegnimento dei suoi dispositivi, lasciando indipendente la fermentazione in solo monitoraggio.

I timeout sono durate reali brevi configurate attraverso l'API, con margine per il coordinamento Docker. Non vengono introdotti controlli dell'orologio o endpoint di guasto nell'applicazione. Il coordinatore comunica con il driver di prova tramite file nel container degli strumenti e ferma soltanto servizi del progetto `hackbrew-tests-*` della singola esecuzione. Reset e pulizia sono limitati al database `hackbrew_test` e al relativo volume temporaneo; non usano il progetto o il volume applicativo dell'utente.

Le schermate generate sono in `artifacts/`, esclusa da Git:

| Fase | Desktop | Telefono |
| --- | --- | --- |
| Prima dei guasti | `ripresa-integrata-prima-1440.png` | `ripresa-integrata-prima-390.png` |
| MongoDB indisponibile | `ripresa-integrata-guasto-1440.png` | `ripresa-integrata-guasto-390.png` |
| Recupero completato | `ripresa-integrata-recupero-1440.png` | `ripresa-integrata-recupero-390.png` |

## Primo avvio e dimostrazione dal browser

Per provare un primo avvio pulito senza intervenire sui dati abituali, usa un **nome di progetto Docker non ancora usato** e porte distinte. Per esempio, in una nuova shell:

```sh
export COMPOSE_PROJECT_NAME=hackbrew-demo
export HACKBREW_PORT=8090
export HACKBREW_SIMULATOR_PORT=8091
./scripts/hackbrew up
```

Apri **http://localhost:8090**. Il progetto dimostrativo ha rete e volume propri; i normali riavvii li conservano. Il primo build richiede il download delle immagini. Non è necessario cancellare un volume per ogni avvio.

1. In **Dispositivi → Pillole → Aggiungi pillola**, registra le pillole con i MAC Bluetooth reali. Per il replay senza hardware usa `AA:BB:CC:DD:EE:FF` e `11:22:33:44:55:66`. Su una pillola libera **Esplora letture** apre la diagnostica completa della sorgente scelta.
2. Per una dimostrazione con attuatore simulato avvia `HACKBREW_SIMULATOR_CAPABILITY=both ./scripts/hackbrew simulator`. Nella scheda **Dispositivi termici** registra un dispositivo con entrambe le funzioni e indirizzo **`http://thermal-simulator:8000`**, poi usa **Verifica collegamento**. Il simulatore è opzionale e appartiene a questa dimostrazione; non è un servizio applicativo obbligatorio.
3. In **Nuova fermentazione**, scegli nome e pillola, passa a Regolazione e conferma dal Riepilogo. **Solo monitoraggio** non chiede soglie o attuatori. Per l'altro ciclo scegli **Dispositivo combinato**, il simulatore e una fascia come 20–23 °C con isteresi 1 °C. Lo stesso dispositivo non è riutilizzabile finché rimane riservato.
4. Configura un'unica istanza del [bridge](../integrations/rapt-gateway.md) con gli URL raggiungibili del server:

   ```yaml
   registry:
     url: http://localhost:8090/api/bridge/pills
     poll_interval_seconds: 30
     timeout_seconds: 5
   http:
     url: http://localhost:8090/telemetry
     timeout_seconds: 5
   ```

   Su un computer distinto sostituisci `localhost` con l'indirizzo LAN del server e configura coerentemente `HACKBREW_BIND_ADDRESS`. Segui il README del bridge per il suo avvio Docker con Bluetooth oppure per `--replay -`. Il replay documentato invia i byte di due pillole attraverso lo stesso decoder usato con Bluetooth. Nei log, `registry_synced ... pills=2` conferma le identità; `reading_forwarded source=...` conferma le nuove consegne. Il bridge rimane esterno a HackBrew.
5. Controlla le due card: le letture devono appartenere alle rispettive pillole, con tempi di acquisizione reali. Apri un dettaglio, scegli un intervallo, nascondi una serie, prova zoom/pan e poi **Torna al live**. Nel replay le due fixture originali mostrano circa 19,69 °C/SG 1,0213 e 23,94 °C/SG 1,0109; `valid=false` riguarda solo la velocità della densità.
6. Nella scheda **Gestione** del dettaglio regolato modifica insieme minimo, massimo e isteresi. Controlla i valori salvati, la revisione e la cronologia iniziale/modificata. Lo stato di regolazione distingue richiesta e conferma fisica. In **Impostazioni**, modifica il timeout comune e controlla le conferme dei dispositivi; per una demo manuale scegli una durata sufficiente a completare le operazioni.
7. Interrompi e ripristina la rete del browser lasciando aperto il dettaglio. Le vecchie letture devono conservare i propri istanti e l'intervallo scelto. Dopo nuove acquisizioni il live riprende senza cambiare fermentazione. Per riprodurre anche i guasti ai servizi usa `test-recovery assembled`, che opera su un ambiente separato invece di fermare questo progetto manuale.
8. Nella scheda **Gestione** premi **Termina fermentazione** e poi **Conferma termine**. Il ciclo rimane concluso dopo reload o riavvio; lo spegnimento non confermato rimane visibile e trattiene la prenotazione. Non viene riaperto dall'arrivo di nuove letture.
9. Torna a **Dispositivi → Pillole** e rinomina la pillola libera: il MAC resta in sola lettura. Prova **Rimuovi → Annulla**, poi conferma una rimozione. La pillola scompare dal registro operativo e dal bridge; il ciclo concluso resta consultabile in Archivio con nome e MAC storici. Una successiva registrazione esplicita dello stesso MAC recupera la stessa identità.

Per arrestare la dimostrazione, nella stessa shell usa `./scripts/hackbrew down`; il volume viene conservato. Le variabili esportate valgono per questa shell: una nuova shell senza queste variabili torna al progetto e alle porte abituali.

## Risultati automatici e compatibilità fisica

La verifica automatica dimostra l'integrazione software sul commit fissato del bridge e sul contratto HTTP degli attuatori simulati. Non certifica ricezione radio, calibrazione o firmware di una pillola/attuatore fisico. Con l'hardware reale vanno osservati i MAC ricevuti, tutte le misure, capacità dichiarate, conferme ON/OFF, esclusione tra funzioni, timeout applicato e spegnimento autonomo senza server. Le procedure sono nelle guide di [bridge](../integrations/rapt-gateway.md) e [dispositivi termici](../integrations/thermal-devices.md).
