<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId } from 'vue'
import {
  measurements,
  formatMeasurement,
  type MeasurementKey,
} from './measurements'
import type { Reading } from './readings'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{
  identifier: string
  fermentationName: string
  range: [number, number]
  bounds: [number, number]
}>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const titleId = useId()
const readings = ref<Reading[]>([])
const latest = computed(() => readings.value.at(-1))
function rawValue(reading: Reading, key: MeasurementKey) {
  const value = reading[key]
  return value == null ? 'Non disponibile' : formatMeasurement(value, key)
}
const scope = ref<'period' | 'all'>('period')
const selected = computed(() =>
  scope.value === 'period' ? props.range : props.bounds,
)
const cursors = ref<Array<string | null>>([null])
const nextBefore = ref<string | null>(null)
let requestedBefore: string | null = null
let requestedDirection: 'refresh' | 'older' | 'newer' = 'refresh'
function changeScope() {
  cursors.value = [null]
  nextBefore.value = null
  void load(null, 'refresh')
}
function older() {
  if (nextBefore.value) void load(nextBefore.value, 'older')
}
function newer() {
  if (cursors.value.length > 1)
    void load(cursors.value[cursors.value.length - 2], 'newer')
}
const { loading, error, run } = useLatestRequest(
  'Non è stato possibile recuperare i dati grezzi. Riprova.',
)
const previousOverflow = document.body.style.overflow
function trapFocus(event: KeyboardEvent) {
  if (event.key !== 'Tab') return
  const controls = dialog.value?.querySelectorAll<HTMLElement>(
    'button:not([disabled]), select, [tabindex="0"]',
  )
  const first = controls?.[0],
    last = controls?.[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}
async function load(
  before: string | null = requestedBefore,
  direction: 'refresh' | 'older' | 'newer' = requestedDirection,
) {
  requestedBefore = before
  requestedDirection = direction
  readings.value = []
  return run(
    async (signal) => {
      const query = new URLSearchParams({
        limit: '200',
        from_timestamp: String(selected.value[0]),
        to_timestamp: String(selected.value[1]),
      })
      if (before) query.set('before', before)
      const response = await fetch(
        `/api/fermentations/${encodeURIComponent(props.identifier)}/readings?${query}`,
        { signal, cache: 'no-store' },
      )
      if (!response.ok) throw new Error('Raw readings unavailable')
      return (await response.json()) as {
        readings: Reading[]
        next_before: string | null
      }
    },
    (result) => {
      readings.value = result.readings
      nextBefore.value = result.next_before
      if (direction === 'older') cursors.value.push(before)
      if (direction === 'newer') cursors.value.pop()
      requestedDirection = 'refresh'
    },
  )
}
onMounted(() => {
  dialog.value?.showModal()
  document.body.style.overflow = 'hidden'
  void load()
})
onUnmounted(() => {
  document.body.style.overflow = previousOverflow
})
</script>

<template>
  <dialog
    ref="dialog"
    class="raw-dialog"
    :aria-labelledby="titleId"
    @close="emit('close')"
    @keydown="trapFocus"
  >
    <header>
      <div>
        <h2 :id="titleId">Dati grezzi</h2>
        <p>{{ fermentationName }}</p>
      </div>
      <button
        type="button"
        class="text-button"
        autofocus
        aria-label="Chiudi dati grezzi"
        @click="dialog?.close()"
      >
        Chiudi
      </button>
    </header>
    <label
      >Ambito dei dati
      <select
        v-model="scope"
        aria-label="Ambito dei dati"
        @change="changeScope"
      >
        <option value="period">Periodo del grafico</option>
        <option value="all">Intera fermentazione</option>
      </select>
    </label>
    <p class="raw-period">
      Dal {{ new Date(selected[0] * 1000).toLocaleString('it-IT') }} al
      {{ new Date(selected[1] * 1000).toLocaleString('it-IT') }}. Il periodo è
      fissato all’apertura.
    </p>
    <p>
      Le velocità non valide restano consultabili qui e sono escluse dal
      grafico. Scorri la tabella in orizzontale per vedere tutte le misure.
    </p>
    <p v-if="latest && !loading && !error" aria-label="Riepilogo storico">
      Ultima lettura mostrata:
      {{ formatMeasurement(latest.specific_gravity, 'specific_gravity') }} SG ·
      {{ formatMeasurement(latest.temperature, 'temperature') }} °C ·
      {{ formatMeasurement(latest.battery, 'battery') }}% batteria
    </p>
    <p v-if="loading" role="status">Caricamento dati grezzi…</p>
    <p v-else-if="error" role="alert">
      {{ error }}
      <button type="button" class="text-button" @click="load()">
        Riprova dati grezzi
      </button>
    </p>
    <p v-else-if="!readings.length" role="status">
      Nessuna lettura nell’ambito selezionato.
    </p>
    <nav
      v-if="!loading && !error && readings.length"
      aria-label="Pagine dei dati grezzi"
      class="history-navigation"
    >
      <button
        type="button"
        class="text-button"
        :disabled="cursors.length === 1"
        @click="newer"
      >
        Letture più recenti
      </button>
      <span>{{ readings.length }} letture mostrate</span>
      <button
        type="button"
        class="text-button"
        :disabled="!nextBefore"
        @click="older"
      >
        Letture precedenti
      </button>
    </nav>
    <div
      v-if="!loading && !error && readings.length"
      class="readings-table"
      tabindex="0"
      aria-label="Scorri le letture storiche"
    >
      <table aria-label="Letture della fermentazione">
        <thead>
          <tr>
            <th scope="col">Acquisizione</th>
            <th v-for="metric in measurements" :key="metric.key" scope="col">
              {{ metric.label }}
            </th>
            <th scope="col">Validità</th>
            <th scope="col">Ricezione</th>
            <th scope="col">Pillola</th>
            <th scope="col">MAC Bluetooth</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(reading, index) in readings" :key="index">
            <td>
              <time
                :datetime="new Date(reading.timestamp * 1000).toISOString()"
                >{{
                  new Date(reading.timestamp * 1000).toLocaleString('it-IT')
                }}</time
              ><span class="exact-timestamp"
                >Unix: {{ reading.timestamp }}</span
              >
            </td>
            <td v-for="metric in measurements" :key="metric.key">
              {{ rawValue(reading, metric.key) }}
            </td>
            <td>
              {{
                reading.valid === true
                  ? 'Valida'
                  : reading.valid === false
                    ? 'Non valida'
                    : 'Non dichiarata'
              }}
            </td>
            <td>{{ reading.received_at }}</td>
            <td>{{ reading.pill_id }}</td>
            <td>{{ reading.pill_mac }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </dialog>
</template>

<style scoped>
.raw-dialog {
  width: min(1100px, calc(100vw - 64px));
  max-width: none;
  max-height: calc(100dvh - 64px);
  border: 1px solid #dce3e7;
  border-radius: 12px;
  padding: 24px;
  color: inherit;
  background: white;
}
.raw-dialog[open] {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.raw-dialog::backdrop {
  background: #17313c99;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
h2,
p {
  margin: 0;
}
label {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
select {
  font: inherit;
  padding: 10px;
  border: 1px solid #b6c9bd;
  border-radius: 6px;
  background: white;
}
.readings-table {
  overflow: auto;
  min-height: 0;
}
th,
td {
  white-space: nowrap;
}
@media (max-width: 640px) {
  .raw-dialog {
    margin: 0;
    width: 100vw;
    height: 100dvh;
    max-height: none;
    padding: 16px;
    border: 0;
    border-radius: 0;
  }
}
</style>
