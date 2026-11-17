<script setup lang="ts">
import NavigationIcon from './NavigationIcon.vue'
import {
  controlModeNames,
  regulationNames,
  type FermentationSummary,
} from './fermentations'
import type { PillSnapshot } from './readings'
defineProps<{
  fermentation: FermentationSummary
  communication?: PillSnapshot['communication_status']
}>()
defineEmits<{ select: [id: string] }>()
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const temperatures = new Intl.NumberFormat('it-IT', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
</script>
<template>
  <button
    class="home-card"
    :class="{
      'home-card-active': fermentation.status === 'active',
      'home-card-warning':
        fermentation.status === 'active' &&
        (fermentation.regulation?.status === 'suspended' ||
          communication === 'timed_out'),
    }"
    :aria-label="`Apri ${fermentation.name}, ${dates.format(new Date(fermentation.started_at))}`"
    @click="$emit('select', fermentation.id)"
  >
    <div class="home-card-top">
      <span class="card-beer-symbol" aria-hidden="true"
        ><NavigationIcon name="beer" /></span
      ><span class="home-card-status">{{
        fermentation.status === 'active' ? 'In corso' : 'Conclusa'
      }}</span
      ><span class="card-open-arrow" aria-hidden="true">→</span>
    </div>
    <span class="eyebrow">{{
      fermentation.status === 'active'
        ? 'Fermentazione attiva'
        : 'Dal tuo archivio'
    }}</span>
    <h2>{{ fermentation.name }}</h2>
    <div class="home-card-period">
      <time :datetime="fermentation.started_at"
        >Avvio · {{ dates.format(new Date(fermentation.started_at)) }}</time
      ><time v-if="fermentation.ended_at" :datetime="fermentation.ended_at"
        >Termine · {{ dates.format(new Date(fermentation.ended_at)) }}</time
      >
    </div>
    <div v-if="fermentation.latest_reading" class="home-card-values">
      <div>
        <span>Temperatura</span
        ><strong
          >{{ temperatures.format(fermentation.latest_reading.temperature)
          }}<small> °C</small></strong
        >
      </div>
      <div>
        <span>Densità</span
        ><strong
          >{{ fermentation.latest_reading.specific_gravity.toFixed(3)
          }}<small> SG</small></strong
        >
      </div>
      <div v-if="fermentation.status === 'active'" class="home-card-battery">
        <span>Batteria pillola</span
        ><strong
          >{{ fermentation.latest_reading.battery.toFixed(0)
          }}<small> %</small></strong
        >
      </div>
    </div>
    <p v-else class="home-card-empty">Nessuna lettura registrata</p>
    <p
      v-if="fermentation.status === 'active'"
      class="card-communication"
      :class="{ 'card-communication-warning': communication === 'timed_out' }"
    >
      {{
        communication === 'timed_out'
          ? 'Timeout di comunicazione superato'
          : fermentation.latest_reading
            ? 'Ultima lettura disponibile'
            : 'In attesa della prima lettura'
      }}
    </p>
    <div class="home-card-footer">
      <span>{{
        fermentation.regulation
          ? regulationNames[fermentation.regulation.status]
          : controlModeNames[fermentation.control_mode]
      }}</span
      ><span v-if="fermentation.control_mode !== 'monitor_only'"
        >Fascia {{ fermentation.temperature_min }}–{{
          fermentation.temperature_max
        }}
        °C<template v-if="fermentation.regulation?.actual_mode === null">
          · Effettivo: sconosciuto</template
        ></span
      ><span class="home-card-open"
        >Apri <span aria-hidden="true">→</span></span
      >
    </div>
  </button>
</template>
