<script setup lang="ts">
import { current, deviceName, latest, state, timestamp } from './demo'
</script>
<template>
  <section v-if="current" class="p-detail-metrics" aria-label="Ultima lettura">
    <div class="p-metric-heading">
      <span class="p-overline">ULTIMA LETTURA</span
      ><span class="p-muted">{{ timestamp(latest(current).time) }}</span>
    </div>
    <div class="p-measure p-temp">
      <span>Temperatura</span
      ><strong
        >{{ latest(current).temperature?.toFixed(1) }}<small> °C</small></strong
      >
    </div>
    <div class="p-measure p-gravity">
      <span>Densità</span
      ><strong
        >{{ latest(current).gravity?.toFixed(3) }}<small> SG</small></strong
      >
    </div>
    <div v-if="!current.end" class="p-measure p-detail-battery">
      <span>Batteria pillola</span
      ><strong
        >{{ latest(current).battery?.toFixed(0) }}<small> %</small></strong
      >
    </div>
    <div class="p-metric-context">
      <span>{{ deviceName(current.pill) }}</span
      ><strong>{{
        current.end
          ? 'Ciclo concluso'
          : current.stale
            ? 'Timeout · regolazione sospesa'
            : current.mode === 'Solo monitoraggio'
              ? 'Solo monitoraggio'
              : `Obiettivo ${current.min}–${current.max} °C`
      }}</strong
      ><small v-if="current.stale && !current.end"
        >Nessuna comunicazione da oltre {{ state.timeout }} ore. Spegnimento
        richiesto, conferma da verificare.</small
      >
    </div>
  </section>
</template>
