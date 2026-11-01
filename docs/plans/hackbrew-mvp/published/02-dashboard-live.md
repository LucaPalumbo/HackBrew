## Parent

[HackBrew MVP — issue #1](https://github.com/LucaPalumbo/HackBrew/issues/1)

## What to build

Aggiornare automaticamente la dashboard quando arriva una nuova lettura persistita e permettere all'homebrewer di riconoscere dati assenti o non aggiornati. Il percorso completo comprende ricezione HTTP, stato salvato in MongoDB, notifiche SSE e visualizzazione su computer e cellulare.

La funzione deve essere dimostrabile sulla dashboard diagnostica anche prima di introdurre le fermentazioni.

Tracciabilità alla specifica: user story 2, 6–7, 11, 13–14 e 38–41.

## Acceptance criteria

- [ ] Una lettura inviata al ricevitore aggiorna i valori e l'orario nella dashboard già aperta, senza ricaricare la pagina.
- [ ] Gli aggiornamenti SSE riflettono letture effettivamente persistite; la connessione live non sostituisce MongoDB come fonte dei dati.
- [ ] All'apertura della pagina e dopo la riconnessione viene recuperato lo stato persistito corrente, anche se una notifica live è stata persa.
- [ ] L'interfaccia distingue almeno assenza di letture, lettura disponibile e lettura non aggiornata. Quando i dati invecchiano conserva i valori e l'orario reali, senza mostrarli come nuovi.
- [ ] La soglia di freschezza è configurabile e inizialmente pari a cinque minuti. Non è presentata come frequenza di trasmissione della pillola né come prova che un componente hardware specifico sia offline.
- [ ] Un'interruzione del collegamento browser-applicazione produce un feedback comprensibile e la ripresa aggiorna nuovamente la schermata senza richiedere di ricreare i dati.
- [ ] Valori, stato e controlli rimangono leggibili e utilizzabili con viewport desktop e telefono.
- [ ] Test API/SSE e browser attraversano il confine pubblico dell'applicazione con MongoDB reale; verificano aggiornamento automatico, dati invecchiati e recupero dopo una notifica persa.
- [ ] I controlli sono eseguibili tramite il workflow Docker già introdotto e la configurazione della freschezza è documentata.
