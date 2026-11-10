<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  controlModeNames,
  regulationNames,
  type FermentationSummary,
} from './fermentations'
import { capabilityNames, modeNames } from './thermalDevices'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{
  selectedId: string | null
  activeId: string | null
  recoveryRevision: number
  revision: number
}>()
const emit = defineEmits<{ select: [identifier: string | null] }>()
const entries = ref<FermentationSummary[]>([])
const search = ref('')
const appliedSearch = ref('')
const offset = ref(0)
const requestedOffset = ref(0)
const nextOffset = ref<number | null>(null)
const { loading, error, run, refresh } = useLatestRequest(
  'Non è stato possibile recuperare le fermentazioni.',
)
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

async function load(target = 0, background = false) {
  requestedOffset.value = target
  await run(
    async (signal) => {
      const query = new URLSearchParams({
        q: appliedSearch.value,
        limit: '20',
        offset: String(target),
      })
      const response = await fetch(`/api/fermentations?${query}`, {
        cache: 'no-store',
        signal,
      })
      if (!response.ok) throw new Error('Archive unavailable')
      const payload: {
        fermentations: FermentationSummary[]
        next_offset: number | null
      } = await response.json()
      return payload
    },
    (payload) => {
      entries.value = payload.fermentations
      nextOffset.value = payload.next_offset
      offset.value = target
    },
    background,
  )
}
function searchByName() {
  appliedSearch.value = search.value.trim()
  void load(0)
}
onMounted(() => {
  void load()
})
watch(
  () => [props.activeId, props.recoveryRevision, props.revision] as const,
  () => {
    refresh(() => load(requestedOffset.value, true))
  },
)
</script>

<template>
  <section class="archive" aria-label="Fermentazioni">
    <div class="archive-heading">
      <h2>Le tue fermentazioni</h2>
      <button
        class="text-button"
        type="button"
        :aria-pressed="!selectedId"
        @click="emit('select', null)"
      >
        Monitoraggio attuale
      </button>
    </div>
    <form class="archive-search" @submit.prevent="searchByName">
      <label for="history-search">Cerca per nome</label>
      <input
        id="history-search"
        v-model="search"
        type="search"
        maxlength="200"
        placeholder="Nome della fermentazione"
      />
      <button class="text-button" type="submit" :disabled="loading">
        Cerca fermentazioni
      </button>
    </form>
    <p v-if="error" class="error" role="alert">
      {{ error }}
      <button class="text-button" type="button" @click="load(requestedOffset)">
        Riprova elenco
      </button>
    </p>
    <p v-if="loading" role="status">Caricamento fermentazioni…</p>
    <p v-else-if="!error && !entries.length" class="history-period">
      {{
        appliedSearch
          ? 'Nessuna fermentazione corrisponde alla ricerca.'
          : 'Nessuna fermentazione registrata.'
      }}
    </p>
    <ul v-if="entries.length" class="fermentation-cards">
      <li v-for="entry in entries" :key="entry.id">
        <button
          type="button"
          class="fermentation-card"
          :class="{ 'fermentation-card-active': entry.status === 'active' }"
          :aria-label="`Apri ${entry.name}, ${dates.format(new Date(entry.started_at))}`"
          :aria-current="selectedId === entry.id ? 'true' : undefined"
          @click="emit('select', entry.id)"
        >
          <span class="card-title">{{ entry.name }}</span>
          <span class="card-status">{{
            entry.status === 'active' ? 'In corso' : 'Conclusa'
          }}</span>
          <span class="card-pill"
            >{{ entry.pill_name }} · {{ entry.pill_mac }}</span
          >
          <span class="card-mode">{{
            controlModeNames[entry.control_mode]
          }}</span>
          <template v-if="entry.regulation">
            <span class="card-mode">{{
              regulationNames[entry.regulation.status]
            }}</span>
            <span class="card-pill"
              >{{ entry.devices?.map((device) => device.name).join(' + ') }} ·
              Fascia {{ entry.temperature_min }}–{{ entry.temperature_max }} °C
              · Isteresi {{ entry.hysteresis }} °C</span
            >
            <span
              v-for="device in entry.devices"
              :key="device.id"
              class="card-pill"
            >
              {{ device.name }} · {{ capabilityNames[device.capability] }} ·
              {{
                entry.regulation.devices[device.id]?.error
                  ? 'Comunicazione non confermata'
                  : entry.regulation.devices[device.id]?.reserved
                    ? 'Riservato'
                    : 'Assegnazione rilasciata'
              }}
              <template v-if="entry.regulation.devices[device.id]">
                · Effettivo:
                {{
                  modeNames[
                    entry.regulation.devices[device.id]?.actual_mode ??
                      'unknown'
                  ]
                }}
              </template>
            </span>
            <span class="card-pill"
              >Richiesto: {{ modeNames[entry.regulation.desired_mode] }} ·
              Effettivo:
              {{
                entry.regulation.actual_mode === null
                  ? 'Sconosciuto'
                  : modeNames[entry.regulation.actual_mode]
              }}</span
            >
          </template>
          <span v-if="entry.latest_reading" class="card-values">
            <span
              >Temperatura
              <strong
                >{{
                  entry.latest_reading.temperature.toLocaleString('it-IT', {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })
                }}
                °C</strong
              ></span
            >
            <span
              >Densità
              <strong
                >{{
                  entry.latest_reading.specific_gravity.toFixed(3)
                }}
                SG</strong
              ></span
            >
            <span
              >Batteria
              <strong
                >{{ entry.latest_reading.battery.toFixed(0) }}%</strong
              ></span
            >
            <span
              >Acquisizione
              <time
                :datetime="
                  new Date(entry.latest_reading.timestamp * 1000).toISOString()
                "
                >{{
                  dates.format(new Date(entry.latest_reading.timestamp * 1000))
                }}</time
              ></span
            >
          </span>
          <span v-else>Nessuna lettura registrata</span>
          <time :datetime="entry.started_at"
            >Avvio · {{ dates.format(new Date(entry.started_at)) }}</time
          >
          <time v-if="entry.ended_at" :datetime="entry.ended_at"
            >Termine · {{ dates.format(new Date(entry.ended_at)) }}</time
          >
        </button>
      </li>
    </ul>
    <div v-if="offset || nextOffset !== null" class="history-navigation">
      <button
        type="button"
        class="text-button"
        :disabled="loading || !offset"
        @click="load(Math.max(0, offset - 20))"
      >
        Fermentazioni più recenti</button
      ><button
        type="button"
        class="text-button"
        :disabled="loading || nextOffset === null"
        @click="load(nextOffset ?? 0)"
      >
        Altre fermentazioni
      </button>
    </div>
  </section>
</template>
