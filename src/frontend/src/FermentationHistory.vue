<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import MeasurementChart from './MeasurementChart.vue'
import FermentationControls from './FermentationControls.vue'
import type { Fermentation } from './fermentations'
import type { Reading } from './readings'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{
  identifier: string | null
  revision: number
  live: boolean
  recoveryRevision: number
}>()
const emit = defineEmits<{ changed: [] }>()
const notice = ref('')
const detailSection = ref<HTMLElement | null>(null)
const fermentation = ref<Fermentation | null>(null)
const readings = ref<Reading[]>([])
const nextBefore = ref<string | null>(null)
const cursors = ref<Array<string | null>>([null])
const { loading, error, run, invalidate, refresh } = useLatestRequest(
  'Non è stato possibile recuperare lo storico. Riprova.',
)
const latest = computed(() => readings.value.at(-1))
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const temperatures = new Intl.NumberFormat('it-IT', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
let loadedId: string | null = null
let loadedLive = props.live
let requestedBefore: string | null = null
let requestedDirection: 'refresh' | 'older' | 'newer' = 'refresh'

async function load(
  before: string | null = requestedBefore,
  direction: 'refresh' | 'older' | 'newer' = requestedDirection,
  background = false,
): Promise<boolean> {
  const identifier = props.identifier
  if (!identifier) return false
  requestedBefore = before
  requestedDirection = direction
  return run(
    async (signal) => {
      const query = new URLSearchParams({ limit: '200' })
      if (before) query.set('before', before)
      const options = {
        cache: 'no-store' as const,
        signal,
      }
      const [details, history] = await Promise.all([
        fetch(`/api/fermentations/${encodeURIComponent(identifier)}`, options),
        fetch(
          `/api/fermentations/${encodeURIComponent(identifier)}/readings?${query}`,
          options,
        ),
      ])
      if (!details.ok || !history.ok) throw new Error('History unavailable')
      const detailPayload: { fermentation: Fermentation } = await details.json()
      const historyPayload: {
        readings: Reading[]
        next_before: string | null
      } = await history.json()
      return { detailPayload, historyPayload }
    },
    ({ detailPayload, historyPayload }) => {
      fermentation.value = detailPayload.fermentation
      readings.value = historyPayload.readings
      nextBefore.value = historyPayload.next_before
      if (direction === 'older') cursors.value.push(before)
      if (direction === 'newer') cursors.value.pop()
      requestedDirection = 'refresh'
    },
    background,
  )
}
function older() {
  const cursor = nextBefore.value
  if (cursor) void load(cursor, 'older')
}
function newer() {
  if (cursors.value.length > 1)
    void load(cursors.value[cursors.value.length - 2], 'newer')
}
function ended(updated: Fermentation) {
  fermentation.value = updated
  notice.value = `Fermentazione “${updated.name}” conclusa.`
  emit('changed')
  void load()
}
watch(
  () =>
    [
      props.identifier,
      props.revision,
      props.recoveryRevision,
      props.live,
    ] as const,
  ([identifier, , , live]) => {
    const changed = identifier !== loadedId
    const viewChanged = live !== loadedLive
    loadedLive = live
    if (changed) {
      invalidate()
      loadedId = identifier
      fermentation.value = null
      readings.value = []
      nextBefore.value = null
      cursors.value = [null]
      requestedBefore = null
      requestedDirection = 'refresh'
      error.value = ''
      notice.value = ''
    }
    if ((changed || viewChanged) && identifier && !live)
      void nextTick(() => {
        detailSection.value?.focus({ preventScroll: true })
        detailSection.value?.scrollIntoView({ block: 'start' })
      })
    if (identifier) {
      if (changed || viewChanged) void load()
      else refresh(() => load(requestedBefore, requestedDirection, true))
    }
  },
  { immediate: true },
)
</script>

<template>
  <section
    v-if="identifier"
    ref="detailSection"
    tabindex="-1"
    class="history-data"
    aria-label="Dati della fermentazione"
  >
    <h2>
      {{
        live
          ? 'Andamento della fermentazione'
          : `${fermentation?.status === 'active' ? 'Dettaglio' : 'Storico'}: ${fermentation?.name ?? (error ? 'non disponibile' : 'caricamento…')}`
      }}
    </h2>
    <FermentationControls
      v-if="!live && fermentation?.status === 'active'"
      :fermentation="fermentation"
      :pills="[]"
      :loading="loading"
      @changed="ended"
    />
    <p
      v-if="notice"
      class="operation-notice"
      role="status"
      aria-label="Esito operazione"
    >
      {{ notice }}
    </p>
    <p v-if="fermentation" class="history-period">
      {{ fermentation.name }} ·
      {{ fermentation.status === 'concluded' ? 'Conclusa' : 'In corso' }} · Solo
      monitoraggio<br />
      {{ fermentation.pill_name }} · {{ fermentation.pill_mac }}<br />
      <time :datetime="fermentation.started_at">{{
        dates.format(new Date(fermentation.started_at))
      }}</time>
      <template v-if="fermentation.ended_at">
        →
        <time :datetime="fermentation.ended_at">{{
          dates.format(new Date(fermentation.ended_at))
        }}</time></template
      >
    </p>
    <p v-if="error" class="error" role="alert">
      {{ error }}
      <button type="button" class="text-button" @click="load()">
        Riprova storico
      </button>
    </p>
    <p v-if="loading" role="status">Caricamento storico…</p>
    <p v-if="fermentation && !readings.length && !loading && !error">
      {{
        live
          ? 'I grafici appariranno alla prima lettura.'
          : 'Nessuna lettura registrata per questa fermentazione.'
      }}
    </p>
    <template v-if="readings.length">
      <p
        v-if="!live && latest"
        class="history-summary"
        aria-label="Riepilogo storico"
      >
        Ultima lettura mostrata: {{ latest.specific_gravity.toFixed(3) }} SG ·
        {{ temperatures.format(latest.temperature) }} °C ·
        {{ latest.battery.toFixed(0) }}% batteria
      </p>
      <p class="history-period">
        Ogni punto è una lettura acquisita; gli intervalli senza campioni
        restano senza punti.
      </p>
      <div class="charts">
        <MeasurementChart
          :readings="readings"
          metric="specific_gravity"
          label="Densità SG"
        />
        <MeasurementChart
          :readings="readings"
          metric="temperature"
          label="Temperatura °C"
        />
      </div>
      <div class="history-navigation">
        <button
          class="text-button"
          type="button"
          :disabled="loading || cursors.length === 1"
          @click="newer"
        >
          Letture più recenti
        </button>
        <span>{{ readings.length }} letture mostrate</span>
        <button
          class="text-button"
          type="button"
          :disabled="loading || !nextBefore"
          @click="older"
        >
          Letture precedenti
        </button>
      </div>
      <div
        class="readings-table"
        tabindex="0"
        aria-label="Scorri le letture storiche"
      >
        <table aria-label="Letture della fermentazione">
          <thead>
            <tr>
              <th scope="col">Acquisizione</th>
              <th scope="col">Densità SG</th>
              <th scope="col">Temperatura °C</th>
              <th scope="col">Batteria %</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(reading, index) in readings"
              :key="`${reading.timestamp}-${index}`"
            >
              <td>
                <time
                  :datetime="new Date(reading.timestamp * 1000).toISOString()"
                  >{{ dates.format(new Date(reading.timestamp * 1000)) }}</time
                >
              </td>
              <td>{{ reading.specific_gravity.toFixed(3) }}</td>
              <td>{{ temperatures.format(reading.temperature) }}</td>
              <td>{{ reading.battery.toFixed(0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
