## Parent

[HackBrew MVP — issue #1](https://github.com/LucaPalumbo/HackBrew/issues/1)

## What to build

Permettere di avviare una fermentazione con un nome, raccogliere le letture del suo intervallo di monitoraggio e terminarla manualmente dalla dashboard. Rendere visibile la fermentazione attiva e mantenere una sola fermentazione attiva anche con richieste concorrenti o dopo un riavvio.

Questo ticket comprende il percorso ordinario completo, dal comando nell'interfaccia alla persistenza dello stato e delle letture. La consultazione con grafici delle fermentazioni concluse viene aggiunta in un ticket successivo.

Tracciabilità alla specifica: user story 16–23, 26–29 e 41.

## Acceptance criteria

- [ ] Dall'interfaccia si può creare e avviare una fermentazione assegnandole un nome non vuoto, senza introdurre un ciclo di bozze separato.
- [ ] La fermentazione possiede un identificatore stabile, un istante di avvio e, quando conclusa, un istante di termine; lo stato è recuperato da MongoDB al caricamento.
- [ ] La dashboard mostra nome e stato della fermentazione attiva. Se non ha ancora letture associate, lo indica senza attribuirle lo storico diagnostico precedente.
- [ ] Una seconda richiesta di avvio mentre una fermentazione è attiva restituisce un conflitto comprensibile e lascia invariata quella già attiva.
- [ ] L'invariante di una sola fermentazione attiva è garantita dalla persistenza ed è verificata con richieste concorrenti e dopo un riavvio.
- [ ] Nel percorso ordinario le letture vengono associate e salvate usando l'istante di acquisizione e l'intervallo di monitoraggio: avvio incluso e termine escluso. L'interfaccia della fermentazione ne recupera i dati persistiti.
- [ ] L'homebrewer può terminare manualmente la fermentazione dalla dashboard e ottiene conferma dell'operazione; lo stato concluso e le letture raccolte rimangono salvati.
- [ ] Dopo il termine si può avviare una nuova fermentazione, riutilizzando la pillola senza trasferire automaticamente le letture precedenti alla nuova.
- [ ] Le letture acquisite fuori dagli intervalli di monitoraggio alimentano solo l'ultima lettura diagnostica e non generano uno storico senza fermentazione.
- [ ] Gli errori di nome, avvio o termine vengono resi visibili senza far credere che un'operazione fallita sia riuscita.
- [ ] Test d'integrazione con MongoDB reale e test browser verificano il percorso avvio, lettura e termine, l'attesa della prima lettura, i conflitti concorrenti e il recupero dello stato salvato.
