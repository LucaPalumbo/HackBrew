## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Avviare più fermentazioni contemporanee in solo monitoraggio, scegliendo una pillola disponibile per ciascuna, e consultarle da una pagina di card con dettaglio dedicato. Questo incremento sostituisce il vincolo globale di una sola attiva con l'esclusività per pillola e rende la nuova navigazione già utilizzabile senza attuatori.

## Acceptance criteria

- [ ] È possibile avviare più fermentazioni con nome e pillole distinte; la modalità solo monitoraggio non richiede dispositivi termici, temperatura minima/massima o isteresi.
- [ ] Una pillola appartiene ad al massimo una fermentazione attiva, anche con avvii concorrenti. Un conflitto è spiegato e non lascia prenotazioni o fermentazioni parziali.
- [ ] L'elenco contiene attive e concluse, con attive evidenziate e prima delle concluse, ricerca per nome e navigazione limitata senza perdere risultati.
- [ ] Le card mostrano nome, stato, pillola, ultima temperatura, densità SG, batteria e stato solo monitoraggio; valori mancanti sono espliciti. Gli aggiornamenti live interessano la card corretta.
- [ ] Ogni card apre un dettaglio direttamente indirizzabile con assegnazione, istanti, stato e letture esatte. Reload, Indietro/Avanti e riapertura del collegamento conservano la fermentazione selezionata.
- [ ] È possibile terminare manualmente una fermentazione senza terminare le altre; il termine è definitivo, ripetibile senza cambiarne l'istante, e libera la pillola per un nuovo ciclo.
- [ ] L'assegnazione della pillola non è modificabile durante il ciclo. Dati fuori ordine e ritardati sono attribuiti alla pillola e all'intervallo corretti, anche tra cicli successivi e con altri cicli simultanei.
- [ ] Diagnosticare una pillola senza fermentazione attiva resta possibile e non importa letture precedenti in un ciclo nuovo.
- [ ] Test HTTP/browser coprono concorrenza, almeno due fermentazioni attive, card, ricerca, dettaglio, navigazione, termine indipendente, letture identiche tra pillole e confini temporali. Interfaccia utilizzabile da desktop e telefono, con stati vuoti/errori espliciti.
- [ ] Assegnazioni, cicli e storico sopravvivono a un riavvio reale contro lo stesso volume di test; MongoDB indisponibile non produce conferme di scritture fallite.
