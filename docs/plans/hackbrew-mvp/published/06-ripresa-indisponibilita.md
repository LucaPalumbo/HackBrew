## Parent

[HackBrew MVP — issue #1](https://github.com/LucaPalumbo/HackBrew/issues/1)

## What to build

Rendere comprensibile e recuperabile un'interruzione dell'applicazione o di MongoDB: l'homebrewer deve distinguere i valori precedentemente letti da un caricamento o salvataggio fallito e ritrovare fermentazione, storico e aggiornamenti quando il sistema torna disponibile.

Il percorso completo coinvolge le operazioni pubbliche dell'applicazione, la persistenza reale e la dashboard live con consultazione dello storico. Il recupero riguarda i dati arrivati a HackBrew; non ricostruisce letture eliminate dal gateway esterno.

Tracciabilità alla specifica: user story 28–29, 38–39, 41–42, 45–46 e 48.

## Acceptance criteria

- [ ] Se MongoDB è indisponibile, un invio che non viene persistito riceve un errore esplicito e non un successo; non vengono emesse notifiche che facciano apparire salvati dati mancanti.
- [ ] Anche avvio, termine e caricamento di una fermentazione segnalano i fallimenti reali senza presentare uno stato inventato o un'operazione non salvata come conclusa.
- [ ] La dashboard mostra un feedback recuperabile quando non può caricare i dati. Può conservare i valori già visibili con il loro orario e stato, senza farli apparire freschi.
- [ ] Dopo il ripristino di MongoDB una nuova lettura valida viene salvata e resa visibile senza dover ricreare fermentazioni o azzerare il volume.
- [ ] Riavviare l'applicazione o ricreare i container mantenendo il volume preserva la fermentazione attiva, le fermentazioni concluse, le letture e l'ultima lettura diagnostica.
- [ ] Dopo la riconnessione il browser recupera lo stato persistito, riapre lo storico corretto e riceve nuove letture tramite il meccanismo live.
- [ ] Un test operativo riproducibile avvia una fermentazione, salva dati, interrompe e ripristina i servizi e ne verifica il risultato tramite HTTP e browser usando MongoDB e volumi di test isolati.
- [ ] La procedura di verifica non usa credenziali personali, hardware o dati di produzione e non elimina il volume dell'utente. Le istruzioni effettive per avvio, controlli e riavvio con conservazione dei dati sono documentate.
- [ ] È esplicito che i messaggi rifiutati durante il guasto non vengono recuperati automaticamente dal gateway attuale; il test prosegue con una nuova lettura senza aggiungere ritrasmissione o buffer al progetto esterno.
