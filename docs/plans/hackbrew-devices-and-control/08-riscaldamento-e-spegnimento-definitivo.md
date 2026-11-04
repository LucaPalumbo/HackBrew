## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Avviare una fermentazione con pillola e un dispositivo di riscaldamento, impostare fascia termica e isteresi e vedere il riscaldamento regolato automaticamente. Il percorso completo comprende prenotazione esclusiva, timeout simmetrico, conferme, sospensione/ripresa e termine manuale definitivo. Raffreddamento e combinazioni vengono aggiunti in T9.

## Acceptance criteria

- [ ] La creazione permette di scegliere una pillola disponibile e un heater, con temperatura minima/massima e isteresi valide. Solo monitoraggio resta disponibile senza soglie; la selezione degli altri modi termici non è abilitata prima di T9.
- [ ] Il dispositivo è riservato atomicamente a una sola fermentazione attiva; avvii concorrenti o richieste incompatibili non producono associazioni parziali. Le assegnazioni non cambiano durante il ciclo.
- [ ] Il riscaldamento parte a temperatura minore o uguale al minimo, si arresta a minimo più isteresi e mantiene lo stato nella banda intermedia. Senza temperatura utilizzabile non si accende. Card e dettaglio mostrano impostazioni, stato richiesto ed effettivo.
- [ ] Il controllo gira sul server indipendentemente dal browser, rinnova i comandi e valuta le scadenze anche senza nuove letture. Dopo il timeout globale senza dati dalla pillola richiede OFF; traffico di altre pillole, sincronizzazioni del bridge e input invalido non azzerano il timer.
- [ ] Il simulatore si spegne autonomamente se non riceve comandi per lo stesso timeout. Accorciare il timeout rivaluta il tempo già trascorso e può richiedere subito OFF; modificarlo non finge una nuova lettura.
- [ ] Dati mancanti, timeout o dispositivo irraggiungibile sospendono il controllo e richiedono OFF senza concludere la fermentazione. Il ritorno di dati utilizzabili e comunicazione confermata permette la ripresa automatica soltanto se è ancora attiva.
- [ ] Il termine manuale persiste una conclusione definitiva e richiede OFF. Anche se il dispositivo non risponde, non riapre il ciclo; lo spegnimento rimane pendente e ritentabile, e il dispositivo resta riservato fino alla conferma OFF.
- [ ] Nuove letture, riconnessioni, richieste di termine ripetute e vecchi comandi ON non riattivano un ciclo concluso né ne modificano l'istante finale. Stato desiderato e stato effettivo non vengono confusi.
- [ ] Stato del ciclo, isteresi, prenotazioni, tempi di comunicazione e OFF pendenti sono persistenti. Un riavvio riconcilia prima lo stato reale e riprende solo il controllo ancora appropriato; non presume una conferma dal solo ricordo del comando.
- [ ] Test HTTP/browser e simulatore coprono soglie ed uguaglianze, isteresi, concorrenza, creazione monitor-only, assenza dati, rinnovi, due lati del timeout, fine durante un guasto, OFF non confermato, riuso bloccato e ripresa. I test usano durate brevi attraverso la configurazione pubblica, con MongoDB reale.
- [ ] Una prova Docker ferma realmente il server mentre il simulatore riscalda e ne osserva lo spegnimento autonomo; un riavvio conserva conclusione e OFF pendente. I criteri non vengono rimandati al solo ticket finale di recupero.

## Blocked by

- T2 — Monitorare fermentazioni parallele con card e dettaglio.
- T7 — Configurare e sincronizzare il timeout globale simmetrico.
