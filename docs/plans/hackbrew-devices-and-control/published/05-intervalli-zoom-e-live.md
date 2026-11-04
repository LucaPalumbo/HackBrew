## Parent

[Specifica #8](https://github.com/LucaPalumbo/HackBrew/issues/8).

## What to build

Esplorare un sottoinsieme dello storico dal grafico usando una barra temporale, intervalli rapidi, zoom e pan, quindi tornare al live. Il periodo scelto deve contenere tutte le letture effettive pertinenti, anche oltre una singola pagina API, e rimanere fermo all'arrivo di nuovi dati.

## Acceptance criteria

- [ ] La barra temporale ha due estremi trascinabili e permette di scegliere un intervallo entro la fermentazione; sono disponibili 1h, 6h, 24h e Tutto.
- [ ] Sono disponibili zoom con rotella, zoom tramite selezione di un'area con il mouse, pinch sul telefono e pan orizzontale. I gesti di selezione e trascinamento non si confondono e rimangono usabili con controlli accessibili.
- [ ] Il ricevitore delle query storiche accetta limiti temporali espliciti e paginazione coerente; il grafico carica tutti i campioni del periodo richiesto senza fermarsi silenziosamente agli ultimi 200.
- [ ] Paginazione e limiti preservano timestamp uguali, precisione delle misure e confini di fermentazione. Cursori o intervalli non validi ricevono errori chiari.
- [ ] Cambiare periodo, zoomare o fare pan ferma l'inseguimento del live. Nuove letture aggiornano lo stato senza muovere l'intervallo ispezionato o cambiare le serie selezionate.
- [ ] Torna al live ripristina lo scorrimento verso gli ultimi campioni; aggiornamenti di altre fermentazioni non alterano la vista corrente.
- [ ] Cambi rapidi di intervallo non applicano risposte obsolete. Caricamento, periodo vuoto, errore e riprova sono espliciti e non mostrano valori inventati.
- [ ] Test HTTP/browser percorrono più di una pagina di dati, periodi brevi e completi, tutti i gesti di zoom/pan, barra e preset, live congelato e ripresa. Le asserzioni osservano intervalli e valori accessibili, senza ispezionare gli oggetti interni del grafico.
- [ ] I flussi sono provati su desktop e telefono, comprese interazioni touch, senza modificare la regola che le linee non si interrompono per gap temporali.
