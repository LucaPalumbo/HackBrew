## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Modificare fascia termica e isteresi dal dettaglio di una fermentazione attiva e consultare quando le impostazioni sono cambiate. Il nuovo insieme di valori viene validato e applicato senza cambiare pillola, dispositivi, nome del ciclo o intervallo monitorato.

## Acceptance criteria

- [ ] Nel dettaglio di una fermentazione regolata attiva è possibile modificare minimo, massimo e isteresi come un aggiornamento atomico; API e form rifiutano valori non finiti, fascia invertita e isteresi incoerente.
- [ ] L'aggiornamento ricalcola il comando appropriato usando l'ultima temperatura utilizzabile e mantiene interblocchi, timeout e distinzione tra richiesta e conferma. Non viene acceso un dispositivo senza dati o in uno stato di comunicazione sospeso.
- [ ] Ogni modifica riuscita conserva valori, istante e revisione in una cronologia persistita consultabile dal dettaglio e dall'API. La configurazione iniziale è ricostruibile.
- [ ] Richieste concorrenti o risposte ritardate non sovrascrivono silenziosamente una revisione più recente né producono applicazioni fuori ordine; la UI mostra il valore effettivamente salvato o il conflitto.
- [ ] Pillola e dispositivi restano quelli scelti all'avvio. La modifica non resetta il timer dei dati, non cambia avvio/termine e non crea una nuova fermentazione.
- [ ] Solo monitoraggio continua a non richiedere impostazioni inutilizzate; un ciclo concluso non viene riaperto né riattivato da una modifica concorrente con il termine.
- [ ] Errori di salvataggio e conferme dei dispositivi mancanti sono visibili senza inventare cambiamenti applicati. Reload e riavvio conservano impostazioni e cronologia.
- [ ] Test HTTP/browser verificano validazione, applicazione, cronologia, concorrenza, errore e gara con il termine manuale. Il percorso usa il controllo termico disponibile da [#16](https://github.com/LucaPalumbo/HackBrew/issues/16) ed è indipendente dall'abilitazione del raffreddamento; le stesse regole si applicano alle modalità introdotte da [#17](https://github.com/LucaPalumbo/HackBrew/issues/17).
