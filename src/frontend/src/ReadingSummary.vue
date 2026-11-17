<script setup lang="ts">
import type { Reading } from './readings'
defineProps<{ reading: Reading }>()
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const temperatures = new Intl.NumberFormat('it-IT', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
</script>
<template>
  <section class="reading-summary" aria-label="Ultima lettura">
    <div class="reading-heading">
      <h2>Misure della pillola</h2>
      <span>Ultima rilevazione disponibile</span>
    </div>
    <div class="metrics">
      <section class="metric metric-primary" aria-label="Densità">
        <div class="metric-heading">
          <h3>Densità</h3>
          <span class="metric-symbol" aria-hidden="true">ρ</span>
        </div>
        <p class="metric-value">
          <span>{{ reading.specific_gravity.toFixed(3) }}</span
          ><span class="metric-unit">SG</span>
        </p>
        <p class="metric-caption">Densità relativa</p>
      </section>
      <section class="metric" aria-label="Temperatura">
        <div class="metric-heading">
          <h3>Temperatura</h3>
          <span class="metric-symbol" aria-hidden="true">°</span>
        </div>
        <p class="metric-value">
          <span>{{ temperatures.format(reading.temperature) }}</span
          ><span class="metric-unit">°C</span>
        </p>
        <p class="metric-caption">Nel fermentatore</p>
      </section>
      <section class="metric" aria-label="Batteria">
        <div class="metric-heading"><h3>Batteria</h3></div>
        <p class="metric-value">
          <span>{{ reading.battery.toFixed(0) }}</span
          ><span class="metric-unit">%</span>
        </p>
        <p class="metric-caption">Carica della pillola</p>
      </section>
    </div>
    <div class="acquisition">
      <div>
        <p class="eyebrow">Acquisizione della lettura</p>
        <time
          aria-label="Acquisizione della lettura"
          :datetime="new Date(reading.timestamp * 1000).toISOString()"
          >{{ dates.format(new Date(reading.timestamp * 1000)) }}</time
        >
      </div>
      <p>
        Ricevuta da HackBrew<br /><time :datetime="reading.received_at">{{
          dates.format(new Date(reading.received_at))
        }}</time>
      </p>
    </div>
  </section>
</template>
