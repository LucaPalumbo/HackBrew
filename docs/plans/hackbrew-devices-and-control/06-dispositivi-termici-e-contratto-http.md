## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Registrare un dispositivo di riscaldamento, raffreddamento o entrambe le funzioni, verificarne il collegamento e vedere lo stato effettivo nella pagina Dispositivi. Usare lo stesso contratto HTTP provvisorio con simulatori containerizzati, così che l'integrazione sia provabile senza attuatori reali prima di abilitarne la regolazione.

## Acceptance criteria

- [ ] La pagina Dispositivi e le API permettono di registrare ed elencare nome, identità stabile, capacità e indirizzo HTTP di ogni dispositivo termico, con validazione degli input e messaggi chiari.
- [ ] Una verifica di collegamento interroga il dispositivo e mostra stato effettivo confermato, capacità, ultima conferma e timeout/revisione applicati. Errore o assenza di risposta significa sconosciuto/errore e non spento confermato.
- [ ] Il contratto provvisorio definisce comandi assoluti off/heating/cooling, durata del timeout, identificazione e ordinamento dei comandi e conferma distinta dell'applicazione fisica. È racchiuso in un adattatore sostituibile per futuri endpoint reali.
- [ ] Il simulatore implementa lo stesso contratto HTTP, conferme, scadenza autonoma dall'ultimo comando valido, errori e ritardi controllabili. Le letture di stato non rinnovano la scadenza.
- [ ] Comandi ripetuti sono idempotenti; comandi obsoleti o di un'assegnazione superata non prevalgono su uno stato successivo, e modalità non supportate sono rifiutate. Un dispositivo combinato non può dichiarare heating e cooling insieme.
- [ ] Il timeout iniziale del contratto è di tre ore ed è configurabile tramite i comandi. La sincronizzazione dell'impostazione globale dall'interfaccia è consegnata da T7.
- [ ] Questo ticket non abilita comandi ON dal flusso delle fermentazioni né introduce un override manuale. Registra e osserva i dispositivi; la regolazione viene abilitata soltanto quando esiste il controllo completo di T8.
- [ ] Test HTTP e browser coprono registrazione, capacità, indirizzo non valido, stato confermato e dispositivo irraggiungibile; verifiche esterne del contratto coprono ordinamento, idempotenza, scadenza e simulazione dei guasti.
- [ ] Simulatori e verifiche funzionano nel workflow Docker isolato. È documentato che i test del simulatore non certificano firmware o hardware reali; non vengono implementati driver o firmware.

## Blocked by

- T1 — Registrare pillole e distinguere tutte le letture per sorgente.
