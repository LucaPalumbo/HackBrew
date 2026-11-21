<script setup lang="ts">
import type { PillSnapshot } from './readings'
import type { MeasurementKey } from './measurements'

defineProps<{ pill: PillSnapshot }>()
const metrics: { key: MeasurementKey; label: string; unit: string }[] = [
  { key: 'specific_gravity', label: 'Densità', unit: 'SG' },
  { key: 'temperature', label: 'Temperatura', unit: '°C' },
  { key: 'battery', label: 'Batteria', unit: '%' },
  {
    key: 'gravity_velocity',
    label: 'Velocità densità',
    unit: 'punti SG/giorno',
  },
  { key: 'accel_x', label: 'Accelerazione X', unit: 'unità non specificata' },
  { key: 'accel_y', label: 'Accelerazione Y', unit: 'unità non specificata' },
  { key: 'accel_z', label: 'Accelerazione Z', unit: 'unità non specificata' },
]
const numbers = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 6 })
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
</script>

<template>
  <section
    v-if="pill.reading"
    class="reading-summary"
    aria-label="Ultima lettura diagnostica"
  >
    <div class="reading-heading">
      <h2>{{ pill.name }}</h2>
      <span>{{ pill.mac }}</span>
    </div>
    <div class="metrics pill-diagnostic-grid">
      <section
        v-for="metric in metrics"
        :key="metric.key"
        class="metric"
        :aria-label="metric.label"
      >
        <h3>{{ metric.label }}</h3>
        <p
          v-if="
            metric.key === 'gravity_velocity' && pill.reading.valid === false
          "
          class="metric-caption"
        >
          Non disponibile (misura non valida)<br />Valore ricevuto:
          {{
            pill.reading.gravity_velocity === null
              ? 'Non disponibile'
              : numbers.format(pill.reading.gravity_velocity)
          }}
        </p>
        <p v-else class="metric-value">
          <span>{{
            pill.reading[metric.key] === null
              ? '—'
              : metric.key === 'specific_gravity'
                ? pill.reading.specific_gravity.toFixed(3)
                : numbers.format(pill.reading[metric.key]!)
          }}</span>
        </p>
        <p class="metric-caption">
          {{ metric.unit
          }}{{ pill.reading[metric.key] === null ? ' · Non disponibile' : '' }}
        </p>
      </section>
    </div>
    <div class="acquisition">
      <p>
        Acquisizione<br /><time
          aria-label="Acquisizione della lettura"
          :datetime="new Date(pill.reading.timestamp * 1000).toISOString()"
          >{{ dates.format(new Date(pill.reading.timestamp * 1000)) }}</time
        >
      </p>
      <p>
        Prima ricezione della lettura<br /><time
          :datetime="pill.reading.received_at"
          >{{ dates.format(new Date(pill.reading.received_at)) }}</time
        >
      </p>
      <p v-if="pill.last_received_at">
        Ultima comunicazione<br /><time :datetime="pill.last_received_at">{{
          dates.format(new Date(pill.last_received_at))
        }}</time>
      </p>
    </div>
  </section>
</template>
