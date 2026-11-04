## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Modificare un'unica impostazione globale del timeout dalla pagina Impostazioni e vederla applicata ai dispositivi termici, distinguendo il valore richiesto da quello effettivamente confermato. Questo prepara il contratto di timeout usato dalla regolazione, senza attivare ancora alcun flusso automatico ON.

## Acceptance criteria

- [ ] L'impostazione globale persistita parte da tre ore, è comune a tutte le fermentazioni e si legge/modifica dalla pagina Impostazioni e dall'API pubblica con unità esplicite.
- [ ] Durate nulle, negative, non finite o malformate sono rifiutate senza modificare lo stato; sono ammesse durate brevi valide per prove automatiche senza aspettare ore.
- [ ] Salvare un nuovo valore sincronizza lo stesso timeout con gli attuatori attraverso il contratto di [#14](https://github.com/LucaPalumbo/HackBrew/issues/14). La configurazione può essere modificata in qualsiasi momento, senza riavvio dell'applicazione.
- [ ] La UI distingue valore desiderato, revisione confermata dai dispositivi e sincronizzazione in attesa/errore; un dispositivo irraggiungibile non risulta aggiornato soltanto perché il valore globale è stato salvato.
- [ ] Il ritorno di un dispositivo raggiungibile consente di completare la sincronizzazione della revisione corrente, senza applicare risposte obsolete o cambiare arbitrariamente modalità.
- [ ] La durata è uguale su server e attuatori, ma gli istanti di decorrenza sono espliciti: ultima ricezione dati per pillola sul server e ultimo comando valido sull'attuatore. I controlli di scadenza per le fermentazioni sono abilitati insieme alla regolazione in [#16](https://github.com/LucaPalumbo/HackBrew/issues/16).
- [ ] Lo stato di comunicazione visibile usa questa configurazione, sostituendo le vecchie soglie fisse. Non esistono soglie per interrompere o evidenziare gap nel grafico.
- [ ] Configurazione, revisione e applicazioni in attesa sopravvivono a un riavvio. Nessuna scrittura fallita su MongoDB viene presentata come salvataggio riuscito.
- [ ] Test API/browser con simulatori e MongoDB reale verificano valore iniziale, modifica con monitoraggi attivi, validazione, conferme discordanti/in ritardo, dispositivo irraggiungibile e successivo recupero, senza aggiungere endpoint di controllo dell'orologio all'applicazione.
