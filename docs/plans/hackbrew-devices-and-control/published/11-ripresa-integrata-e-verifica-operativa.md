## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Riprendere l'intero monitoraggio e la regolazione dopo interruzioni di rete, arresti dell'applicazione e indisponibilità di MongoDB, conservando cicli indipendenti, selezione del grafico, impostazioni e conclusioni definitive. Estendere le prove operative esistenti al nuovo sistema completo, correggendo eventuali difetti di riconciliazione emersi.

Ogni ticket precedente include già i propri test e il recupero essenziale del suo comportamento. Questo ticket verifica le interazioni tra bridge reale con input BLE deterministici, applicazione, browser, persistenza e simulatori nel sistema assemblato.

## Acceptance criteria

- [ ] Una prova completa registra pillole e dispositivi, sincronizza il vero bridge, mantiene almeno due fermentazioni attive e verifica flussi di dati e regolazione indipendenti con hardware simulato.
- [ ] Una prova mantiene il browser aperto sul dettaglio con intervallo storico selezionato mentre interrompe collegamenti e servizi. I valori già caricati conservano i loro veri tempi; riconnessione e rilettura ripristinano lo stato senza spostare la vista o mescolare fermentazioni.
- [ ] L'arresto reale del server lascia agli attuatori il proprio timeout autonomo; il riavvio riconcilia gli stati effettivi prima della ripresa ed evita riscaldamento e raffreddamento simultanei.
- [ ] L'indisponibilità reale di MongoDB non produce scritture confermate falsamente, nuovi tempi di ricezione inventati o decisioni termiche basate su stato non verificato. Gli attuatori raggiungono OFF tramite riconciliazione o scadenza autonoma secondo il contratto.
- [ ] Un termine manuale salvato prima di un guasto rimane definitivo dopo ricreazione dei container: tutti gli OFF pendenti sono recuperati, prenotazioni non confermate rimangono bloccate e vecchi ON o nuove letture non riaprono il ciclo.
- [ ] Il timeout globale e le revisioni richieste/applicate, le modifiche della fascia, lo stato di isteresi, l'ultima comunicazione per pillola e le letture complete sopravvivono al riavvio sullo stesso volume di test.
- [ ] Il ritorno di dati utilizzabili e collegamenti consente la ripresa delle sole fermentazioni ancora attive. Quelle in solo monitoraggio e le concluse restano nel loro stato e la sincronizzazione del bridge non viene scambiata per telemetria.
- [ ] Le verifiche osservano API pubbliche, browser e protocollo degli attuatori, fermando/ricreando container reali. Non si sostituisce il riavvio con un semplice reload e non si accede alle strutture interne del database per le asserzioni.
- [ ] La procedura Docker di verifica completa include i nuovi scenari con durate brevi configurate e isolamento rigoroso dei volumi; pulizia e reset non coinvolgono i dati applicativi dell'utente.
- [ ] Documentazione e dimostrazione finale coprono primo avvio pulito, registrazione, collegamento del bridge, avvio monitor-only o regolato, grafico, impostazioni, termine e recupero. Sono distinti i risultati automatici dalle future prove di compatibilità con attuatori e pillole reali.
