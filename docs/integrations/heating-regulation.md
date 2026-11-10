# Regolazione del riscaldamento

La pagina Monitoraggio permette di avviare una fermentazione in **Solo monitoraggio** oppure **Riscaldamento**. Il riscaldamento richiede una pillola disponibile e un dispositivo registrato con capacità `heating`. Dispositivi di raffreddamento e combinati saranno selezionabili con la #17. Non esiste un override ON manuale.

## Avvio e prenotazione

Esempio di richiesta pubblica:

```http
POST /api/fermentations
Content-Type: application/json

{
  "name": "Prima IPA",
  "pill_id": "<pillola registrata>",
  "control_mode": "heating",
  "heater_id": "<dispositivo di solo riscaldamento>",
  "temperature_min": 18,
  "temperature_max": 22,
  "hysteresis": 0.5
}
```

Temperature e isteresi sono in °C e devono essere finite: minimo inferiore al massimo, isteresi positiva, minimo più isteresi entro il massimo. Input incoerenti, modi non supportati e impostazioni termiche in `monitor_only` producono HTTP 422. Un dispositivo inesistente produce HTTP 404. Omettere `control_mode` mantiene Solo monitoraggio, senza soglie né attuatori.

Pillola e heater vengono prenotati con un solo inserimento della fermentazione, protetto da indici univoci parziali. HTTP 409 indica pillola già attiva o dispositivo ancora riservato: non rimangono associazioni parziali. Le assegnazioni restano fisse. Il registro termico espone `available` e `reserved_fermentation_id`; una fermentazione conclusa può mantenere la prenotazione finché il suo OFF non è confermato.

## Soglie, conferme e comunicazione

Con minimo 18, massimo 22 e isteresi 0,5:

- A temperatura **≤ 18 °C**, richiedere riscaldamento.
- A temperatura **≥ 18,5 °C**, richiedere OFF.
- Fra 18 e 18,5 °C, mantenere lo stato fisico confermato.

Il server esegue il controllo anche senza browser. Prima di assumere il dispositivo, conferma OFF nella nuova assegnazione; dopo un riavvio interroga nuovamente lo stato reale. Comandi, revisioni, isteresi, prenotazioni e ricevimenti delle pillole sono persistiti. Il solo ricordo di un comando non prova che sia stato applicato. Il [contratto HTTP](thermal-devices.md) usa identità di avvio, epoch di assegnazione, sequenze e identità idempotenti per rifiutare comandi precedenti.

Il controllo usa l'ultima temperatura della pillola acquisita durante il ciclo corrente. Prima di una temperatura utilizzabile rimane in attesa con OFF richiesto; `valid: false` riguarda solo la velocità della densità e non invalida la temperatura. Il timeout globale decorre dall'ultima ricezione HTTP valida di quella pillola. Altra telemetria, richieste invalide, polling del bridge e modifiche alle impostazioni non rinnovano questo istante.

Il server rinnova i comandi a un intervallo pari al minore fra cinque secondi e un terzo del timeout globale. Il dispositivo misura autonomamente il tempo dall'ultimo controllo valido: GET, configurazioni e retry identici non lo rinnovano. Le durate brevissime ammesse per le prove rimangono soggette al tempo effettivo di esecuzione e trasporto. Un timeout più breve rivaluta il silenzio già trascorso, senza fabbricare una ricezione.

Assenza dati, timeout o comunicazione non confermata sospendono il controllo e richiedono OFF, lasciando il ciclo attivo. Se è nota l'identità dell'avvio, viene tentato OFF anche quando GET fallisce: una risposta di controllo valida può confermare lo spegnimento. Dati utilizzabili e comunicazione confermata permettono la ripresa automatica; dopo una scadenza o un guasto serve prima una conferma OFF corrente. I dispositivi irraggiungibili non vengono descritti come spenti.

## Termine definitivo e stato osservabile

`POST /api/fermentations/{id}/end` persiste subito `status: concluded`, un unico `ended_at` definitivo e OFF richiesto. La risposta non attende l'hardware. Lo spegnimento pendente viene ritentato anche dopo un riavvio; fino alla conferma il dispositivo resta riservato. Ripetere il termine conserva l'istante iniziale. Nuovi dati o vecchi ON non riaprono il ciclo e non superano il successivo OFF o la nuova assegnazione.

Liste, dettaglio e snapshot live espongono fascia, isteresi, heater e `regulation`: `desired_mode`, `actual_mode`, `confirmed_at`, `reason`, `error` e `status`. Lo stato può essere `waiting`, `pending`, `heating`, `idle`, `suspended`, `stopping` o `stopped`. `actual_mode: null` significa sconosciuto. `heater_reserved` resta distinto dallo stato del ciclo. Card e dettaglio mostrano queste informazioni anche durante il termine pendente; il live notifica anche le conferme successive alla conclusione.

MongoDB indisponibile produce HTTP 503: un avvio o termine non salvato non viene confermato. Il watchdog autonomo del dispositivo resta responsabile dello spegnimento quando il server non può più inviare controlli validi.

## Prove senza hardware

Registrare una pillola e un simulatore di solo riscaldamento:

```sh
HACKBREW_SIMULATOR_CAPABILITY=heating ./scripts/hackbrew simulator
```

Nella pagina Dispositivi usare `http://thermal-simulator:8000` e **Riscaldamento**. Avviare il ciclo e inviare letture della pillola con timestamp attuali tramite `/telemetry`. Le temperature dell'esempio sono 17 °C per accendere e 18,5 °C per spegnere.

```sh
./scripts/hackbrew test tests/integration/test_heating.py
./scripts/hackbrew test tests/browser/test_heating_dashboard.py
./scripts/hackbrew test-recovery
./scripts/hackbrew check
```

Configurare prima l'accesso alla sorgente privata del gateway come indicato nel README. Le prove usano MongoDB e simulatori reali nel progetto Docker isolato; nessun hardware o volume applicativo viene modificato. Le schermate sono `artifacts/riscaldamento-{1440,390}.png`. Il contratto resta provvisorio: queste prove verificano l'integrazione software, non il firmware fisico.
