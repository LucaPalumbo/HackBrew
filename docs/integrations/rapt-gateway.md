# Integrazione con RaptPillGateway-ble-http

Il gateway esistente è la sorgente delle letture per HackBrew. Questo documento descrive il codice esaminato, non un contratto già verificato con traffico della pillola reale.

Il gateway è un progetto esterno. Nel perimetro MVP l'utente aveva escluso la sua dockerizzazione e le modifiche al suo repository. La successiva [specifica su dispositivi e regolazione](../specs/hackbrew-devices-and-control.md) include ora le modifiche al gateway per più pillole, sincronizzazione del registro e identificazione della sorgente; la sua dockerizzazione resta esclusa. I servizi Docker di HackBrew comprendono frontend, backend e database; l'integrazione con il gateway avviene tramite HTTP. I fatti e le decisioni MVP riportati sotto descrivono il contratto precedente all'evoluzione.

## Fonti

- [Gateway, commit esaminato](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/tree/0bfc4a7fbbcfc2f231f75452d194de86677d46e2).
- [Decodifica delle letture](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/blob/0bfc4a7fbbcfc2f231f75452d194de86677d46e2/telemetryData.py).
- [Ricezione Bluetooth](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/blob/0bfc4a7fbbcfc2f231f75452d194de86677d46e2/ble_worker.py).
- [Invio HTTP](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/blob/0bfc4a7fbbcfc2f231f75452d194de86677d46e2/http_worker.py).
- [Configurazione](https://github.com/LucaPalumbo/RaptPillGateway-ble-http/blob/0bfc4a7fbbcfc2f231f75452d194de86677d46e2/config.py).
- [Parser originale rapt-ble](https://github.com/sairon/rapt-ble/blob/1473743be0d6dc9c151aae64588e7feffe7147c6/src/rapt_ble/parser.py) e [fixture di protocollo](https://github.com/sairon/rapt-ble/blob/1473743be0d6dc9c151aae64588e7feffe7147c6/tests/test_parser.py), usati per interpretare scala SG, batteria e flag di validità.

## Trasporto e campi

### Estensione HackBrew del ricevitore

Dal ticket [#9](https://github.com/LucaPalumbo/HackBrew/issues/9), HackBrew richiede anche `pill_mac`, il MAC Bluetooth di una pillola già registrata nella pagina Dispositivi. I messaggi senza identità sono rifiutati; il server non sceglie una sorgente al loro posto. Conserva tutti i campi della tabella sotto e distingue ultima lettura e ultima comunicazione per pillola. La modifica del bridge reale per aggiungere il MAC, leggere più pillole e sincronizzare il registro è il [ticket #11](https://github.com/LucaPalumbo/HackBrew/issues/11), ancora separato. Il [README](../../README.md) descrive registrazione, formato completo e prova HTTP di questo incremento.

### Contratto osservato nel bridge MVP

Il gateway seleziona la pillola tramite MAC Bluetooth e invia una lettura per richiesta HTTP POST con corpo JSON.

| Campo | Tipo JSON | Interpretazione |
| --- | --- | --- |
| `valid` | booleano | Validità della velocità di variazione della densità; non dell'intera lettura. |
| `gravity_velocity` | numero | Velocità di variazione della densità; il parser originale indica punti SG al giorno. |
| `temperature` | numero | Temperatura già convertita in °C. |
| `specific_gravity` | numero | Valore da dividere per 1000 per ottenere SG: per esempio 1021.2935 diventa circa 1.0213. |
| `accel_x`, `accel_y`, `accel_z` | numeri | Valori degli accelerometri; unità fisiche non documentate nel gateway. |
| `battery` | numero | Percentuale, secondo il parser originale e le fixture corrispondenti. |
| `timestamp` | numero | Secondi Unix assegnati dall'orologio del gateway alla ricezione Bluetooth. |

Il corpo non contiene identificatori della pillola, della lettura o della fermentazione, né una versione dello schema. Non scartare una lettura completa solo perché `valid` è falso: il flag riguarda esclusivamente `gravity_velocity`.

## Comportamento osservato nel codice

- Il gateway consente di configurare URL e timeout HTTP, ma non intestazioni di autenticazione.
- La coda degli invii è in memoria. In caso di errore HTTP o di rete, la lettura fallita viene rimossa senza un nuovo tentativo.
- Non esistono una coda persistente, un recupero dopo riavvio o uno svuotamento garantito della coda alla chiusura.
- Payload identici sono soppressi per meno di due secondi. Questa finestra non stabilisce la frequenza delle misurazioni della pillola.
- Non vengono eseguiti controlli generali sui numeri finiti o sugli intervalli fisici prima dell'invio.

## Decisioni di integrazione ancora da definire

- L'autenticazione è rinviata a una fase futura, per scelta esplicita dell'utente.
- L'adeguamento del gateway per recuperare gli invii falliti era stato proposto, ma non è stato approvato. Non considerarlo un requisito acquisito e non modificare il suo repository su questa base.
- La prima integrazione proposta usa il contratto HTTP attuale. Il recupero delle letture perse durante le interruzioni richiederebbe un intervento successivo sul gateway.
- Associazione delle letture consegnate in ritardo alle fermentazioni.
- Soglia per indicare letture non aggiornate e gestione dei duplicati.
- Validazione del ricevitore e verifica del formato con una lettura reale.

Le letture senza fermentazione attiva serviranno a mostrare l'ultima rilevazione; lo storico sarà registrato durante le fermentazioni attive.
