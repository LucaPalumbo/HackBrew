## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Registrare una pillola nella pagina web e vederne arrivare le letture attraverso l'unico bridge, insieme alle altre pillole registrate. Il lavoro comprende il vero software della repository RaptPillGateway-ble-http, il contratto di sincronizzazione con HackBrew e la verifica automatica delle due estremità, senza hardware Bluetooth.

## Acceptance criteria

- [ ] HackBrew espone al bridge l'elenco delle pillole registrate con identità stabile, nome, MAC Bluetooth normalizzato e revisione del registro.
- [ ] Un solo processo bridge acquisisce e aggiorna automaticamente il registro; aggiungere nome e MAC dalla pagina web è sufficiente e non richiede un secondo elenco manuale dei MAC nella configurazione del bridge.
- [ ] Il vero ricevitore Bluetooth del bridge distingue più pillole registrate e invia ogni rilevazione al ricevitore HTTP con il MAC della sorgente e tutti i nove campi originali.
- [ ] Filtri, soppressione dei duplicati e stato di raccolta non confondono pillole diverse. Dispositivi non registrati non creano automaticamente registrazioni o misure attribuite ad altre pillole.
- [ ] Errore di sincronizzazione, elenco iniziale indisponibile e invio HTTP fallito producono uno stato diagnosticabile; non vengono inventati dati o conferme di persistenza. Non sono introdotti buffering durevole o ritrasmissione delle letture fallite.
- [ ] Una verifica usa il vero percorso di decodifica/ricezione del bridge con input BLE deterministici e la vera comunicazione HTTP con HackBrew; una seconda verifica mostra nell'interfaccia due pillole con misure separate e l'aggiunta di una nuova pillola senza riconfigurare il bridge.
- [ ] I test distinguono chiaramente sorgente, normalizzazione SG, flag valid e accelerazioni. La scala fisica degli accelerometri non viene inventata; eventuali incompatibilità del parser emerse dalle fixture vengono risolte o documentate con evidenza.
- [ ] Sono documentati configurazione della connessione a HackBrew, protocollo, prova riproducibile senza hardware e procedura di verifica con pillole vere. Gli strumenti di verifica restano containerizzati; il bridge non deve diventare un quarto servizio obbligatorio di HackBrew.
- [ ] Le modifiche nelle due repository restano collegabili alla specifica e verificabili insieme; non si considera completato il ticket implementando soltanto un finto bridge di test.
