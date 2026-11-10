<script setup lang="ts">
import type { Fermentation } from './fermentations'
import { regulationNames } from './fermentations'
import { modeNames } from './thermalDevices'
defineProps<{ fermentation: Fermentation }>()
const numbers = new Intl.NumberFormat('it-IT', { maximumSignificantDigits: 15 })
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
</script>

<template>
  <section
    v-if="fermentation.regulation"
    class="heating-status"
    :aria-label="`Regolazione ${fermentation.name}`"
  >
    <h3>{{ regulationNames[fermentation.regulation.status] }}</h3>
    <p>{{ fermentation.heater_name }}</p>
    <p
      v-if="
        fermentation.temperature_min !== undefined &&
        fermentation.temperature_max !== undefined &&
        fermentation.hysteresis !== undefined
      "
    >
      Fascia: {{ numbers.format(fermentation.temperature_min) }}–{{
        numbers.format(fermentation.temperature_max)
      }}
      °C · Isteresi: {{ numbers.format(fermentation.hysteresis) }} °C
    </p>
    <p>
      Richiesto: {{ modeNames[fermentation.regulation.desired_mode] }} ·
      Effettivo:
      {{
        fermentation.regulation.actual_mode === null
          ? 'Sconosciuto'
          : modeNames[fermentation.regulation.actual_mode]
      }}
    </p>
    <p v-if="fermentation.regulation.reason">
      {{ fermentation.regulation.reason }}
    </p>
    <p v-if="fermentation.regulation.error" class="error">
      {{ fermentation.regulation.error }}
    </p>
    <p>
      {{
        fermentation.heater_reserved
          ? 'Dispositivo ancora riservato'
          : 'Dispositivo disponibile'
      }}
    </p>
    <p v-if="fermentation.regulation.confirmed_at" class="metric-caption">
      Ultima conferma:
      <time :datetime="fermentation.regulation.confirmed_at">{{
        dates.format(new Date(fermentation.regulation.confirmed_at))
      }}</time>
    </p>
  </section>
</template>
