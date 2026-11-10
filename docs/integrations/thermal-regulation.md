# Regolazione termica

La pagina Monitoraggio offre Solo monitoraggio, Riscaldamento, Raffreddamento, Riscaldamento e raffreddamento separati e Dispositivo combinato. Una fermentazione usa una sola pillola; le assegnazioni restano fisse durante il ciclo.

## Creazione e capacità

`POST /api/fermentations` accetta nome, `pill_id` e la configurazione scelta:

| `control_mode` | Dispositivi richiesti | Capacità |
| --- | --- | --- |
| `monitor_only` (predefinito) | Nessuno | Nessuna soglia |
| `heating` | `heater_id` | `heating` |
| `cooling` | `cooler_id` | `cooling` |
| `heating_cooling` | `heater_id` e `cooler_id` distinti | `heating` e `cooling` |
| `combined` | Solo `combined_id` | `both` |

Ogni modalità termica richiede `temperature_min`, `temperature_max` e `hysteresis` in °C: valori finiti, minimo inferiore al massimo, isteresi positiva e minimo più isteresi entro il massimo. Solo monitoraggio non accetta dispositivi o soglie. Capacità incompatibili, identificatori ripetuti e combinato insieme ad altri dispositivi producono HTTP 422; identità sconosciute HTTP 404. Il form propone soltanto capacità compatibili e disabilita i dispositivi riservati.

Pillola e insieme completo dei dispositivi vengono prenotati con un unico inserimento MongoDB. Un indice univoco sui dispositivi ancora riservati impedisce sovrapposizioni anche fra coppie e configurazioni singole. HTTP 409 non lascia assegnazioni parziali.

## Soglie e commutazione

Con fascia 18–22 °C e isteresi 0,5 °C:

| Funzione | ON | OFF |
| --- | --- | --- |
| Riscaldamento | Temperatura ≤ 18 °C | Temperatura ≥ 18,5 °C |
| Raffreddamento | Temperatura ≥ 22 °C | Temperatura ≤ 21,5 °C |

Fra le soglie della funzione viene conservato lo stato fisico confermato. Una funzione non disponibile resta spenta. Senza temperatura utilizzabile non si accende nulla; `valid: false` riguarda la velocità della densità e non invalida la temperatura.

Il controllo gira sul server senza browser, con una riconciliazione indipendente per fermentazione. Prima di assumere una nuova assegnazione conferma OFF. Prima della funzione opposta richiede e conferma OFF, anche sul combinato. Un ON accettato ma non ancora applicato viene superato da un OFF con sequenza successiva. Conferme mancanti sospendono il controllo senza presumere uno spegnimento.

Guasti di lettura, comando o conferma richiedono OFF a tutto l'insieme. Un errore non impedisce il tentativo di spegnimento dell'altro dispositivo. La ripresa richiede ciclo attivo, dati utilizzabili e stato fisico riconciliato. Non esiste un override ON manuale.

## Timeout e termine definitivo

Il timeout globale delle Impostazioni è inizialmente 10.800 secondi. Sul server decorre dall'ultima ricezione valida della singola pillola; sul dispositivo dall'ultimo controllo valido. Altre pillole, polling del bridge, GET e configurazioni non rinnovano questi istanti. I rinnovi avvengono al minore fra cinque secondi e un terzo del timeout. Le durate brevi delle prove restano soggette ai tempi di esecuzione e trasporto.

La scadenza dei dati richiede OFF a tutti e sospende la regolazione, lasciando il ciclo attivo. Il watchdog autonomo spegne i dispositivi se il server smette di inviare controlli validi. Accorciare il timeout rivaluta il tempo già trascorso.

`POST /api/fermentations/{id}/end` persiste subito una conclusione definitiva, il suo unico `ended_at` e OFF richiesto per ciascun dispositivo. Non attende l'hardware: ogni OFF non confermato mantiene la prenotazione ed è ritentato anche dopo un riavvio. Sul combinato OFF disabilita entrambe le funzioni. Un dispositivo confermato OFF può essere rilasciato e riutilizzato mentre il suo compagno rimane pendente; il vecchio ciclo non gli invia più comandi.

Nuove letture, risposte in ritardo, retry del termine e vecchi ON non riaprono il ciclo né cambiano l'istante finale. Identità di avvio, epoch e sequenze del [contratto HTTP](thermal-devices.md) proteggono il riuso. MongoDB indisponibile produce HTTP 503 senza confermare operazioni non salvate.

## Stato e aggiornamento

Liste, dettaglio e live espongono `devices` con identità, nome, capacità e ruolo, più `reserved_device_ids` e `thermal_reserved`. `regulation` contiene stato complessivo, modo richiesto/effettivo, motivo ed errore; `regulation.devices` separa modi, conferme, errori e prenotazioni per identificatore. `actual_mode: null` significa sconosciuto. Il campo compatibile `heater_reserved` riguarda soltanto il riscaldatore.

Gli stati sono `waiting`, `pending`, `heating`, `cooling`, `idle`, `suspended`, `stopping` e `stopped`. Una conferma di un'assegnazione rilasciata è storica, non descrive il dispositivo nella nuova fermentazione. Il live aggiorna anche gli OFF confermati dopo il termine.

L'aggiornamento dal formato della #16 conserva in loco comandi, soglie, isteresi, assegnazioni e OFF pendenti, senza azzerare dati. Al riavvio viene letto lo stato reale: il comando ricordato non è una conferma. La modifica della fascia durante il ciclo appartiene al successivo ticket dedicato.

## Prove Docker

Il simulatore opzionale può usare una capacità alla volta: `HACKBREW_SIMULATOR_CAPABILITY=both ./scripts/hackbrew simulator`. Registrare `http://thermal-simulator:8000` con entrambe le funzioni e scegliere Dispositivo combinato. L'applicazione continua a richiedere soltanto frontend, backend e MongoDB; i test avviano simulatori distinti su rete e volume isolati.

```sh
./scripts/hackbrew test tests/integration/test_thermal_regulation.py
./scripts/hackbrew test tests/browser/test_thermal_regulation_dashboard.py
./scripts/hackbrew test-recovery
./scripts/hackbrew check
```

Configurare prima l'accesso alla sorgente privata del gateway come indicato nel README. Le prove usano API, browser, MongoDB e simulatori reali. Coprono combinazioni, estremi, concorrenza, conferme mancanti o ritardate, risposte obsolete, timeout, conclusione e riuso. Le prove operative riavviano il server e verificano aggiornamento dalla #16, isteresi della coppia e spegnimento parziale senza interferire con una nuova assegnazione. Schermate: `artifacts/termoregolazione-{cooling,heating_cooling,combined}-{1440,390}.png`.

Le prove verificano l'integrazione software e il simulatore; il firmware fisico dovrà implementare il contratto e conferme reali.
