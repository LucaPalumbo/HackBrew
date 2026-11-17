# Redesign UI e UX di HackBrew

Sessione `grill-with-docs` conclusa con conferma esplicita della comprensione condivisa. Le indicazioni sotto sono state raccolte una domanda per volta. Sono stati costruiti tre prototipi confrontabili; l'utente ha espresso una preferenza per **A — Console operativa**, adottato come base per i successivi affinamenti.

## Modalità della sessione

- Una domanda per volta, come richiesto dall'utente.
- Prima chiarire organizzazione delle funzionalità e flussi principali; successivamente confrontare tre prototipi.

## Indicazioni confermate

- La priorità del redesign è la disposizione delle funzionalità nelle pagine: l'applicazione attuale concentra troppe funzionalità in poche pagine.
- Serve una pagina dedicata alle card delle vecchie fermentazioni, come archivio consultabile.
- Selezionando una card si apre una pagina distinta di dettaglio, con grafici e informazioni sulla birra/fermentazione.
- I dati grezzi sono consultabili su richiesta esplicita, ad esempio attraverso un pulsante; non vengono mostrati come contenuto sempre aperto.
- Serve una pagina dedicata ai dispositivi, per aggiungerli, rimuoverli e gestire quelli esistenti.
- Serve una pagina dedicata alla creazione di una nuova fermentazione.
- La home mostra le fermentazioni attive quando presenti; in assenza di attive mostra le ultime fermentazioni. Il numero di voci recenti e lo stato iniziale senza alcuna fermentazione restano da precisare.
- La navigazione principale comprende **Home**, **Archivio**, **Dispositivi** e **Impostazioni**.
- Un pulsante **Nuova fermentazione**, ben visibile su computer e cellulare, apre la pagina dedicata alla creazione.
- **Dispositivi** e **Impostazioni** sono due pagine distinte. Le impostazioni globali includono il timeout di comunicazione; fascia e isteresi del singolo ciclo restano nel dettaglio della fermentazione.
- Il dettaglio è organizzato in due schede nella stessa pagina: **Andamento**, aperta inizialmente, contiene nome e stato, ultime misure e grafico grande; **Gestione** contiene modifica di minimo, massimo e isteresi, dispositivi associati, cronologia delle impostazioni e azioni sul ciclo, compreso il termine manuale.
- L'accesso ai dati grezzi avviene attraverso un pulsante e non come tabella sempre aperta.
- La pagina **Nuova fermentazione** usa un percorso guidato: **nome e pillola → modalità, dispositivi ed eventuali soglie → riepilogo e avvio**. In solo monitoraggio non compaiono i campi della regolazione termica.
- Rimuovere una pillola o un dispositivo termico dal registro conserva tutte le letture e i riferimenti nelle fermentazioni precedenti. La rimozione è consentita soltanto per dispositivi liberi, senza fermentazioni attive associate né spegnimenti ancora da confermare.
- La pagina **Dispositivi** è divisa nelle schede **Pillole** e **Dispositivi termici**, ciascuna con il proprio elenco e pulsante **Aggiungi**. Gli elenchi mostrano stato e disponibilità, con accesso ai dettagli e alle azioni del dispositivo selezionato.
- Le card delle fermentazioni mostrano nome, stato, ultime misure di temperatura e densità e un'indicazione sintetica della regolazione. La batteria compare nelle card delle fermentazioni attive, non in quelle concluse. Le card dell'archivio mostrano il periodo di inizio e fine.
- All'apertura, i dati grezzi corrispondono al periodo selezionato nel grafico. È possibile passare a tutti i dati della fermentazione. La tabella include anche le misure nascoste dalla legenda del grafico.
- I dati grezzi si aprono in una finestra sopra il dettaglio, a schermo intero sul cellulare. Alla chiusura si ritrovano intervallo, zoom e serie selezionate del grafico.
- Il download **CSV** include tutti i campioni del periodo scelto nella vista dei dati grezzi, oltre la singola pagina della tabella, con tutte le misure, tempi e precisione originali. Selezionando **Tutti i dati**, viene esportata l'intera fermentazione.
- Il grafico mostra inizialmente soltanto **temperatura e densità**, considerate le misure principali. Batteria, velocità della densità e accelerazioni sono attivabili su richiesta, senza comparire tra le curve iniziali.
- La selezione temporale usa **un'unica barra con anteprima dell'andamento e due maniglie sullo stesso intervallo**, al posto delle due barre separate per inizio e fine. Il [riferimento visivo fornito dall'utente](references/time-range-selector.jpeg) mostra il controllo desiderato sopra il grafico; il riferimento riguarda il selettore, non gli assi o le misure dello spettro rappresentato nell'immagine.
- La zona evidenziata del selettore può essere trascinata per spostare il periodo nel tempo, mantenendone invariata la durata; le maniglie modificano i due estremi.
- Selezionare un periodo ridotto deve apparire come uno zoom sulla curva completa. La linea continua fino ai bordi della finestra quando esistono campioni precedenti/successivi che la attraversano, invece di iniziare e terminare ai soli campioni interni al periodo.
- I campioni esterni necessari alla continuità visiva non estendono il periodo dei dati grezzi o del CSV, già definito dalla selezione. Non vengono create nuove letture ai bordi del grafico.
- Le scale verticali si adattano automaticamente ai valori visibili nel periodo selezionato. Temperatura e densità mantengono scale distinte, chiaramente etichettate in **°C** e **SG**.
- L'anteprima nella barra del periodo mostra la **densità dell'intera fermentazione**; il grafico principale mostra le misure selezionate nel periodo evidenziato.
- La gestione dei dispositivi comprende la modifica del nome e, per i dispositivi termici, dell'indirizzo di collegamento. Le modifiche alla pillola sono consentite quando è libera; il cambio dell'indirizzo di un dispositivo termico richiede che sia libero. Il MAC continua a identificare la pillola.
- I tre prototipi mantengono il nome **HackBrew** e possono esplorare colori, tipografia e stili visivi diversi. Devono differire soprattutto per **layout, navigazione e gerarchia delle informazioni**, non soltanto per la palette.
- Completata la creazione, si apre automaticamente il dettaglio della nuova fermentazione nella scheda **Andamento**, con conferma dell'avvio e grafico pronto per le prime letture.

## Domande visive da confrontare nei tre prototipi

- Densità delle card e quantità di fermentazioni recenti visibili nella home; presentazione del primo avvio senza cicli.
- Presentazione dei controlli del grafico, preservando selezione temporale, zoom, pan e ritorno al live.
- Navigazione tra i passaggi della creazione e chiarezza dell'annullamento, senza avviare il ciclo prima della conferma finale. Non è stata richiesta una funzione di bozze persistenti.
- Presentazione dei dettagli e dei moduli di aggiunta/modifica dei dispositivi.
- Navigazione su telefono e computer, gerarchia delle informazioni, palette e tipografia.

## Perimetro della prossima fase

- Confrontare tre prototipi con gli stessi flussi e contenuti concordati, ma strutture visive realmente diverse.
- Provare i flussi su computer e cellulare, includendo esempi con fermentazioni attive, concluse e assenza di cicli.
- I prototipi sono strumenti di valutazione: le azioni di modifica, avvio, termine e rimozione devono usare dati dimostrativi e stato locale, senza comandare dispositivi o modificare dati applicativi reali.
- Le decisioni sull'implementazione definitiva e i dettagli di consegna si formalizzano dopo la valutazione dei prototipi. Il codice di confronto è confinato al branch del prototipo e attivo soltanto in sviluppo; l’implementazione definitiva richiederà una fase separata dopo la scelta.

## Prototipi da confrontare

- Branch separato `prototype/ui-ux-redesign`.
- **A — Console operativa:** navigazione laterale, panoramica a griglia e dettaglio con grafico affiancato da un riepilogo.
- **B — Diario di birrificazione:** navigazione orizzontale, fermentazione principale in evidenza, altre card in una colonna e dettaglio con grafico a tutta larghezza.
- **C — Monitor compatto:** navigazione essenziale, card in righe dense e dettaglio orientato al confronto immediato delle misure.
- Le varianti usano gli stessi dati dimostrativi e stato in memoria. Il parametro `?variant=A`, `B` o `C` e un selettore flottante consentono il confronto sullo stesso percorso.

## Contesto dell'interfaccia esistente

La ricognizione ha verificato che il dettaglio rimane sotto l'elenco delle fermentazioni, con ripetizioni di identità, misure e stato di regolazione. Nel dettaglio, impostazioni e cronologia precedono il grafico; la tabella delle letture è sempre aperta. Questi sono fatti dell'interfaccia implementata, distinti dalle preferenze dell'utente sopra riportate.

Le decisioni funzionali precedenti sono documentate in [Dispositivi, regolazione e dettaglio delle fermentazioni](hackbrew-devices-and-control.md). Il nuovo assetto delle pagine è oggetto di questa sessione.

La ricognizione del grafico ha inoltre verificato che le query attuali caricano soltanto i campioni interni al periodo richiesto, senza campioni esterni di contesto. Le scale verticali sono già automatiche sui dati forniti al grafico. Le serie collegano i campioni utilizzabili attraverso valori mancanti; per la velocità della densità, `valid=false` esclude il valore dal tracciato senza invalidare le altre misure. Il nuovo comportamento ai bordi deve quindi considerare il contesto della curva e le misure utilizzabili, mantenendo distinto l'insieme esportato nella tabella e nel CSV.

## Avvio e percorso di confronto

```sh
./scripts/hackbrew prototype
```

- [A — Console operativa](http://localhost:15173/?variant=A)
- [B — Diario di birrificazione](http://localhost:15173/?variant=B)
- [C — Monitor compatto](http://localhost:15173/?variant=C)

La barra flottante e i tasti ←/→ cambiano proposta conservando pagina, finestra e stato dimostrativo. La barra non è parte del design finale. I tasti dei campi e dei selettori del grafico mantengono le proprie funzioni.

Per confrontare i flussi: aprire una card → Andamento → selezionare un periodo e attivare altre misure → Dati grezzi e CSV → Gestione. Provare poi Archivio, le due schede dei Dispositivi e i tre passaggi di Nuova fermentazione. Il selettore Scenario Home in fondo alla pagina consente di confrontare attive, solo concluse e primo avvio; cambiare scenario azzera le modifiche della demo. In assenza di attive vengono proposte tre concluse recenti.

La demo mostra esempi di regolazione normale, solo monitoraggio e assenza di comunicazione. “Simula nuova lettura” permette di confrontare live e finestra congelata. Sono simulati anche verifica collegamento, invio delle soglie, timeout e conferme di spegnimento: non sono prove del backend o dell’hardware. Tutte le modifiche si azzerano ricaricando. Il database Docker dedicato non alimenta i dati demo e non condivide il volume applicativo.

`./scripts/hackbrew prototype down` ferma l’istanza. `prototype capture` rigenera dodici immagini in `artifacts/prototypes/` (Home e dettaglio, tre varianti, desktop e mobile). Le anteprime seguenti sono conservate come riferimento insieme al codice sul branch separato; il puntatore andrà riportato nella futura issue di implementazione, una volta scelta la direzione.

| Proposta | Home desktop | Home mobile | Dettaglio desktop |
| --- | --- | --- | --- |
| A | [Anteprima](prototypes/A-home-1440.png) | [Anteprima](prototypes/A-home-390.png) | [Anteprima](prototypes/A-detail-1440.png) |
| B | [Anteprima](prototypes/B-home-1440.png) | [Anteprima](prototypes/B-home-390.png) | [Anteprima](prototypes/B-detail-1440.png) |
| C | [Anteprima](prototypes/C-home-1440.png) | [Anteprima](prototypes/C-home-390.png) | [Anteprima](prototypes/C-detail-1440.png) |

## Verifica del prototipo

- Lint, TypeScript e build frontend eseguiti nel container tramite `./scripts/hackbrew prototype check`.
- Anteprime Chromium a 1440 e 390 pixel; nessuno scorrimento orizzontale nelle sei pagine principali delle tre proposte a larghezza mobile.
- Prova interattiva dei flussi in Chromium su tutte e tre le varianti: avvio e termine, modifica della regolazione, diagnostica della pillola libera, modifica dell’indirizzo di un dispositivo libero, impostazioni, archivio e scenari vuoti.
- Verificati congelamento della finestra all’arrivo di una lettura e conservazione della selezione dopo chiusura dei dati grezzi e cambio variante; CSV con 182 letture demo esportate oltre la paginazione, tutte le metriche presenti. Le card concluse non mostrano la batteria.
- Su viewport mobile verificati finestra dei dati grezzi a schermo intero, uso delle frecce sul selettore senza cambiare variante e separazione fra navigazione e barra di confronto.
- Nessuna nuova suite di test: il codice è esplorativo e usa stato locale. Le prove non sostituiscono i test HTTP/browser della futura implementazione e non certificano gesti su hardware mobile reale.

## Preferenza emersa dal confronto

Il 17 novembre 2026 l'utente ha indicato: «Mi piace molto il prototipo A». **A — Console operativa** è quindi il riferimento per proseguire il redesign: navigazione laterale su desktop, card a griglia e dettaglio con grafico affiancato dalle misure. Su telefono mantiene la disposizione adattata e la navigazione inferiore mostrate nell'anteprima.

La preferenza definisce la direzione visiva; eventuali ritocchi restano da raccogliere una domanda per volta. Non equivale ancora all'approvazione di una specifica di implementazione. Le tre proposte restano conservate sul branch `prototype/ui-ux-redesign`; nessuna variante è stata promossa su `main`.
