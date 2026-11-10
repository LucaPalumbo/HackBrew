# Regolazione del riscaldamento

La regolazione introdotta dalla #16 fa ora parte della [regolazione termica completa](thermal-regulation.md), che documenta anche raffreddamento, coppie separate e dispositivi combinati.

Per il solo riscaldamento scegliere **Riscaldamento**, una pillola e un dispositivo con capacità heating. Con minimo 18 °C e isteresi 0,5 °C il dispositivo parte a temperatura ≤ 18 °C e si spegne a temperatura ≥ 18,5 °C. Nella banda intermedia mantiene lo stato fisico confermato.

Il controllo continua senza browser. Timeout e guasti richiedono OFF e sospendono la regolazione senza terminare il ciclo; il termine manuale è definitivo. La prenotazione viene rilasciata solo dopo la conferma OFF. La guida completa descrive API, validazione, timeout simmetrico, persistenza e prove Docker.
