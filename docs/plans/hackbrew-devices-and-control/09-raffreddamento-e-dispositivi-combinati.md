## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Usare un raffreddatore, un riscaldatore più un raffreddatore separati, oppure un dispositivo combinato per la stessa fermentazione. La regolazione applica entrambe le soglie con isteresi e conferma lo spegnimento della funzione precedente prima di avviare quella opposta.

## Acceptance criteria

- [ ] La creazione offre heater-only, cooler-only, heater e cooler distinti, oppure un solo dispositivo combinato. Capacità incompatibili e combinato insieme ad altri dispositivi sono rifiutati chiaramente dall'API e non proposti dal form.
- [ ] L'insieme dei dispositivi viene prenotato atomicamente, senza doppio uso o assegnazioni parziali anche con avvii concorrenti. Una sola pillola rimane assegnata alla fermentazione.
- [ ] Il raffreddamento parte a temperatura maggiore o uguale al massimo e si arresta a massimo meno isteresi; le soglie del riscaldamento restano quelle di T8. Sono provati anche gli estremi esatti e le configurazioni con una sola funzione disponibile.
- [ ] Heating e cooling sono mutuamente esclusivi anche tra dispositivi distinti. Un passaggio richiede conferma OFF della funzione precedente prima del nuovo ON; conferma mancante sospende il controllo.
- [ ] L'esempio 18–22 °C con isteresi 0,5 °C produce heating ON/OFF a 18/18,5 e cooling ON/OFF a 22/21,5, senza accensioni simultanee.
- [ ] Timeout, errore o termine manuale richiedono OFF a tutti i dispositivi associati; off sul combinato disabilita entrambe le funzioni. Un guasto a uno non deve lasciare l'altro deliberatamente acceso dal controllo sospeso.
- [ ] La conclusione rimane definitiva; ogni dispositivo con OFF non confermato resta indisponibile per un nuovo ciclo. Conferme ritardate e comandi di un'assegnazione precedente non riattivano hardware.
- [ ] Card, dettaglio e registro mostrano capacità, assegnazioni, modalità e problemi dei dispositivi corretti senza confondere fermentazioni simultanee.
- [ ] Test HTTP/browser con simulatori coprono tutte le combinazioni, concorrenza, commutazione, conferme perse o fuori ordine, timeout e spegnimento completo. La persistenza al riavvio riguarda anche modalità e prenotazioni dei due dispositivi.

## Blocked by

- T8 — Regolare il riscaldamento e terminare definitivamente la fermentazione.
