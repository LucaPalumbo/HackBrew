## Parent

[HackBrew MVP — issue #1](https://github.com/LucaPalumbo/HackBrew/issues/1)

## What to build

Mantenere affidabili la lettura corrente e gli storici quando un messaggio viene consegnato più volte, fuori ordine o dopo la chiusura della fermentazione a cui appartiene. Una lettura della birra precedente deve restare nel suo intervallo temporale, anche se nel frattempo è iniziata una nuova fermentazione.

Il comportamento è verificabile dall'ingresso HTTP, dai dati storici restituiti dall'applicazione e dai valori mostrati nella dashboard. Non introduce una coda o una funzione di ritrasmissione nel gateway.

Tracciabilità alla specifica: user story 21, 27 e 34–37.

## Acceptance criteria

- [ ] Consegnare più volte una lettura identica, con lo stesso timestamp e contenuto, non duplica lo storico e non richiede un identificatore aggiuntivo al gateway.
- [ ] L'idempotenza è mantenuta anche con consegne concorrenti e dopo il riavvio dell'applicazione usando lo stesso database.
- [ ] Una lettura acquisita prima dell'ultima già nota può arricchire lo storico appropriato ma non sostituisce la lettura più recente nella dashboard.
- [ ] Una lettura arrivata dopo il termine viene associata alla fermentazione nel cui intervallo cade il suo istante di acquisizione, anche se nel frattempo ne è iniziata un'altra.
- [ ] I casi al confine rispettano avvio incluso e termine escluso; nessuna lettura viene attribuita contemporaneamente a due fermentazioni.
- [ ] Una lettura acquisita fuori da tutti gli intervalli aggiorna solo l'eventuale ultima lettura diagnostica, senza accumulare uno storico non assegnato.
- [ ] Messaggi rifiutati dalla validazione non creano campioni storici e non alterano le misure valide già salvate.
- [ ] Le interrogazioni storiche espongono una sequenza cronologica senza duplicati e la dashboard continua a mostrare l'ultima lettura effettiva.
- [ ] I test usano HTTP, MongoDB reale e verifica browser dei valori correnti; coprono duplicati, concorrenza, ritardi tra due fermentazioni, riavvio e istanti ai confini. Non richiedono i grafici del ticket #5 per essere eseguiti.
