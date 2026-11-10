<script setup lang="ts">
import { computed } from 'vue'
import type { Fermentation } from './fermentations'
import { controlModeNames, regulationNames } from './fermentations'
import { capabilityNames, modeNames } from './thermalDevices'
const props = defineProps<{ fermentation: Fermentation }>()
const numbers = new Intl.NumberFormat('it-IT', { maximumSignificantDigits: 15 })
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const devices = computed(
  () =>
    props.fermentation.devices?.map((device) => ({
      ...device,
      control: props.fermentation.regulation?.devices[device.id],
      reserved: props.fermentation.reserved_device_ids?.includes(device.id),
    })) ?? [],
)
</script>

<template>
  <section
    v-if="fermentation.regulation"
    class="thermal-status"
    :aria-label="`Regolazione ${fermentation.name}`"
  >
    <h3>{{ regulationNames[fermentation.regulation.status] }}</h3>
    <p>{{ controlModeNames[fermentation.control_mode] }}</p>
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
    <section
      v-for="device in devices"
      :key="device.id"
      class="device-control"
      :aria-label="`Stato ${device.name}`"
    >
      <h4>{{ device.name }}</h4>
      <p>{{ capabilityNames[device.capability] }}</p>
      <template v-if="device.control">
        <p>
          Richiesto: {{ modeNames[device.control.desired_mode] }} · Effettivo:
          {{
            device.control.actual_mode === null
              ? 'Sconosciuto'
              : modeNames[device.control.actual_mode]
          }}
        </p>
        <p v-if="device.control.error" class="error">
          {{ device.control.error }}
        </p>
        <p>
          {{
            device.reserved
              ? 'Dispositivo ancora riservato'
              : 'Assegnazione rilasciata'
          }}
        </p>
        <p v-if="device.control.confirmed_at" class="metric-caption">
          Ultima conferma:
          <time :datetime="device.control.confirmed_at">{{
            dates.format(new Date(device.control.confirmed_at))
          }}</time>
        </p>
      </template>
    </section>
  </section>
</template>
