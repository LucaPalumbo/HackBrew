<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import MeasurementChart from './MeasurementChart.vue'
import ReadingSummary from './ReadingSummary.vue'
import TimeNavigator from './TimeNavigator.vue'
import FermentationControls from './FermentationControls.vue'
import ThermalRegulationStatus from './ThermalRegulationStatus.vue'
import ThermalSettings from './ThermalSettings.vue'
import {
  controlModeNames,
  regulationNames,
  type Fermentation,
  type FermentationTab,
} from './fermentations'
import { capabilityNames } from './thermalDevices'
import type { Reading } from './readings'
import type { ChartContext } from './chartCurve'
import { useLatestRequest } from './useLatestRequest'
import { measurements, exactMeasurement } from './measurements'

const props = defineProps<{
  identifier: string | null
  tab: FermentationTab
  revision: number
  live: boolean
  recoveryRevision: number
}>()
const emit = defineEmits<{ changed: []; tab: [tab: FermentationTab] }>()
const trendTab = ref<HTMLButtonElement>()
const managementTab = ref<HTMLButtonElement>()
function moveTab(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const next =
    event.key === 'Home'
      ? 'trend'
      : event.key === 'End'
        ? 'management'
        : props.tab === 'trend'
          ? 'management'
          : 'trend'
  emit('tab', next)
  void nextTick(() =>
    (next === 'trend' ? trendTab : managementTab).value?.focus(),
  )
}
const notice = ref('')
const detailSection = ref<HTMLElement | null>(null)
const fermentation = ref<Fermentation | null>(null)
const notFound = ref(false)
const readings = ref<Reading[]>([])
const chartReadings = ref<Reading[]>([])
const chartContext = ref<ChartContext>({})
const latestReading = ref<Reading | null>(null)
const chartAvailable = ref(false)
const window = ref<[number, number] | null>(null)
const domain = ref<[number, number] | null>(null)
const following = ref(true)
let liveWidth: number | null = null
function selectRange(start: number, end: number) {
  if (!domain.value) return
  const [low, high] = domain.value
  const width = Math.min(Math.max(end - start, 0.001), high - low)
  const left = Math.max(low, Math.min(start, high - width))
  window.value = [left, left + width]
  following.value = false
  cursors.value = [null]
  void load(null, 'refresh')
}
function preset(hours: number | null) {
  if (!domain.value) return
  selectRange(
    hours === null ? domain.value[0] : domain.value[1] - hours * 3600,
    domain.value[1],
  )
}
function backToLive() {
  liveWidth = window.value ? window.value[1] - window.value[0] : null
  following.value = true
  cursors.value = [null]
  void load(null, 'refresh')
}
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
      if (!following.value && window.value) {
        query.set('from_timestamp', String(window.value[0]))
        query.set('to_timestamp', String(window.value[1]))
      }
      if (before) query.set('before', before)
      const options = {
        cache: 'no-store' as const,
        signal,
      }
      const details = await fetch(
        `/api/fermentations/${encodeURIComponent(identifier)}`,
        options,
      )
      if (details.status === 404) return { missing: true as const }
      if (!details.ok) throw new Error('History unavailable')
      const detailPayload: {
        fermentation: Fermentation
        latest_reading: Reading | null
      } = await details.json()
      const first =
        new Date(detailPayload.fermentation.started_at).getTime() / 1000
      const last = Math.max(
        first + 0.001,
        detailPayload.latest_reading?.timestamp ?? first,
      )
      const selected: [number, number] = following.value
        ? [liveWidth === null ? first : Math.max(first, last - liveWidth), last]
        : (window.value ?? [first, last])
      query.set('from_timestamp', String(selected[0]))
      query.set('to_timestamp', String(selected[1]))
      const history = await fetch(
        `/api/fermentations/${encodeURIComponent(identifier)}/readings?${query}`,
        options,
      )
      if (!history.ok) throw new Error('History unavailable')
      const historyPayload: {
        readings: Reading[]
        next_before: string | null
      } = await history.json()
      const samples: Reading[] = []
      let cursor: string | null = null
      do {
        const period = new URLSearchParams({
          limit: '200',
          from_timestamp: String(selected[0]),
          to_timestamp: String(selected[1]),
        })
        if (cursor) period.set('before', cursor)
        const response = await fetch(
          `/api/fermentations/${encodeURIComponent(identifier)}/readings?${period}`,
          options,
        )
        if (!response.ok) throw new Error('Period unavailable')
        const page: { readings: Reading[]; next_before: string | null } =
          await response.json()
        samples.unshift(...page.readings)
        cursor = page.next_before
      } while (cursor)
      const contextResponse = await fetch(
        `/api/fermentations/${encodeURIComponent(identifier)}/chart-context?${new URLSearchParams({ from_timestamp: String(selected[0]), to_timestamp: String(selected[1]) })}`,
        options,
      )
      if (!contextResponse.ok) throw new Error('Chart context unavailable')
      const { context }: { context: ChartContext } =
        await contextResponse.json()
      return {
        context,
        missing: false as const,
        detailPayload,
        historyPayload,
        samples,
        selected,
        bounds: [first, last] as [number, number],
      }
    },
    (result) => {
      notFound.value = result.missing
      if (result.missing) {
        fermentation.value = null
        return
      }
      const { detailPayload, historyPayload, samples, selected, bounds } =
        result
      fermentation.value = detailPayload.fermentation
      latestReading.value = detailPayload.latest_reading
      readings.value = historyPayload.readings
      chartReadings.value = samples
      chartContext.value = result.context
      chartAvailable.value = detailPayload.latest_reading !== null
      window.value = selected
      domain.value = bounds
      nextBefore.value = historyPayload.next_before
      if (direction === 'older') cursors.value.push(before)
      if (direction === 'newer') cursors.value.pop()
      requestedDirection = 'refresh'
    },
    background,
  )
}
function older() {
  following.value = false
  const cursor = nextBefore.value
  if (cursor) void load(cursor, 'older')
}
function newer() {
  following.value = false
  if (cursors.value.length > 1)
    void load(cursors.value[cursors.value.length - 2], 'newer')
}
function ended(updated: Fermentation) {
  fermentation.value = updated
  notice.value = `Fermentazione “${updated.name}” conclusa.`
  emit('changed')
  void load()
  void nextTick(() => managementTab.value?.focus())
}
function settingsChanged() {
  invalidate()
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
      notFound.value = false
      latestReading.value = null
      readings.value = []
      chartReadings.value = []
      chartContext.value = {}
      chartAvailable.value = false
      domain.value = null
      window.value = null
      following.value = true
      liveWidth = null
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
      else if (!notFound.value)
        refresh(() => load(requestedBefore, requestedDirection, true))
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
    class="history-data fermentation-detail"
    aria-label="Dati della fermentazione"
  >
    <header class="detail-heading">
      <p class="eyebrow">
        Fermentazione
        <span v-if="fermentation" class="detail-badge">{{
          fermentation.status === 'active' ? 'In corso' : 'Conclusa'
        }}</span>
      </p>
      <h1>
        {{
          notFound
            ? 'Fermentazione non trovata'
            : `${fermentation?.status === 'active' ? 'Dettaglio' : 'Storico'}: ${fermentation?.name ?? (error ? 'non disponibile' : 'caricamento…')}`
        }}
      </h1>
      <p v-if="fermentation" class="description detail-period">
        <time :datetime="fermentation.started_at">{{
          dates.format(new Date(fermentation.started_at))
        }}</time>
        →
        <time v-if="fermentation.ended_at" :datetime="fermentation.ended_at">{{
          dates.format(new Date(fermentation.ended_at))
        }}</time
        ><span v-else>in corso</span>
      </p>
    </header>
    <p v-if="notFound">
      Questa fermentazione non esiste. Torna alla Home o consulta l’Archivio.
    </p>
    <p
      v-if="notice"
      class="operation-notice"
      role="status"
      aria-label="Esito operazione"
    >
      {{ notice }}
    </p>
    <p v-if="error" class="error" role="alert">
      {{ error }}
      <button type="button" class="text-button" @click="load()">
        Riprova storico
      </button>
    </p>
    <p v-if="loading" role="status">Caricamento storico…</p>
    <template v-if="fermentation">
      <div
        class="detail-tabs"
        role="tablist"
        aria-label="Schede della fermentazione"
        @keydown="moveTab"
      >
        <button
          id="detail-trend-tab"
          ref="trendTab"
          type="button"
          role="tab"
          :aria-selected="tab === 'trend'"
          aria-controls="detail-trend"
          :tabindex="tab === 'trend' ? 0 : -1"
          @click="emit('tab', 'trend')"
        >
          Andamento
        </button>
        <button
          id="detail-management-tab"
          ref="managementTab"
          type="button"
          role="tab"
          :aria-selected="tab === 'management'"
          aria-controls="detail-management"
          :tabindex="tab === 'management' ? 0 : -1"
          @click="emit('tab', 'management')"
        >
          Gestione
        </button>
      </div>
      <div
        v-show="tab === 'trend'"
        id="detail-trend"
        role="tabpanel"
        aria-labelledby="detail-trend-tab"
        tabindex="0"
        class="detail-trend"
      >
        <div class="detail-chart-column">
          <div class="detail-chart-heading">
            <p class="eyebrow">L'evoluzione della birra</p>
            <h2>Andamento</h2>
          </div>
          <TimeNavigator
            v-if="domain && window && chartAvailable"
            :minimum="domain[0]"
            :maximum="domain[1]"
            :start="window[0]"
            :end="window[1]"
            :following="following"
            @range="selectRange"
            @preset="preset"
            @live="backToLive"
          />
          <MeasurementChart
            v-if="domain && window && chartAvailable"
            :readings="chartReadings"
            :context="chartContext"
            :range="window"
            @range="selectRange"
          />
          <section
            v-else-if="fermentation.status === 'active' && !loading && !error"
            class="empty"
          >
            <h2>In attesa della prima lettura della fermentazione</h2>
            <p>Il grafico apparirà alla prima lettura.</p>
          </section>
          <p
            v-if="
              fermentation.status === 'concluded' &&
              !chartAvailable &&
              !loading &&
              !error
            "
          >
            Nessuna lettura registrata per questa fermentazione.
          </p>
          <p
            v-if="
              domain &&
              !chartReadings.length &&
              chartAvailable &&
              !loading &&
              !error
            "
            role="status"
          >
            Nessuna lettura nel periodo selezionato. Gli eventuali segmenti
            collegano acquisizioni esterne all’intervallo.
          </p>
        </div>
        <aside
          class="detail-last-reading"
          aria-label="Riepilogo della fermentazione"
        >
          <ReadingSummary v-if="latestReading" :reading="latestReading" />
          <p v-else>Nessuna lettura registrata</p>
          <div class="detail-cycle-summary">
            <p>{{ fermentation.pill_name }} · {{ fermentation.pill_mac }}</p>
            <p>{{ controlModeNames[fermentation.control_mode] }}</p>
            <template v-if="fermentation.regulation">
              <p>{{ regulationNames[fermentation.regulation.status] }}</p>
              <p v-if="fermentation.regulation.actual_mode === null">
                Effettivo: Sconosciuto
              </p>
              <p>
                Fascia {{ fermentation.temperature_min }}–{{
                  fermentation.temperature_max
                }}
                °C
              </p>
            </template>
          </div>
        </aside>
        <div class="detail-readings">
          <template v-if="readings.length">
            <p
              v-if="!live && latest"
              class="history-summary"
              aria-label="Riepilogo storico"
            >
              Ultima lettura mostrata:
              {{ latest.specific_gravity.toFixed(3) }} SG ·
              {{ temperatures.format(latest.temperature) }} °C ·
              {{ latest.battery.toFixed(0) }}% batteria
            </p>
            <p class="history-period">
              Le linee collegano le letture disponibili, anche distanti nel
              tempo. Ogni punto è un campione acquisito; nessun valore
              intermedio viene aggiunto alle letture.
            </p>
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
                    <th
                      v-for="metric in measurements"
                      :key="metric.key"
                      scope="col"
                    >
                      {{ metric.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(reading, index) in readings"
                    :key="`${reading.timestamp}-${index}`"
                  >
                    <td>
                      <time
                        :datetime="
                          new Date(reading.timestamp * 1000).toISOString()
                        "
                        >{{
                          dates.format(new Date(reading.timestamp * 1000))
                        }}</time
                      >
                      <span class="exact-timestamp"
                        >Unix: {{ reading.timestamp }}</span
                      >
                    </td>
                    <td v-for="metric in measurements" :key="metric.key">
                      {{ exactMeasurement(reading, metric.key) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </div>
      <div
        v-show="tab === 'management'"
        id="detail-management"
        role="tabpanel"
        aria-labelledby="detail-management-tab"
        tabindex="0"
        class="detail-management"
      >
        <section
          class="detail-assignments"
          aria-label="Associazioni della fermentazione"
        >
          <h2>Associazioni</h2>
          <p>Le associazioni sono quelle scelte all’avvio del ciclo.</p>
          <dl>
            <div>
              <dt>Pillola</dt>
              <dd>
                {{ fermentation.pill_name }} · {{ fermentation.pill_mac }}
              </dd>
            </div>
            <div>
              <dt>Regolazione</dt>
              <dd>{{ controlModeNames[fermentation.control_mode] }}</dd>
            </div>
            <div v-for="device in fermentation.devices" :key="device.id">
              <dt>{{ capabilityNames[device.capability] }}</dt>
              <dd>
                {{ device.name
                }}<small
                  v-if="device.base_url"
                  class="thermal-history-address"
                  >{{ device.base_url }}</small
                >
              </dd>
            </div>
          </dl>
          <p v-if="fermentation.control_mode === 'monitor_only'">
            Solo monitoraggio: nessuna soglia o dispositivo termico richiesto.
          </p>
        </section>
        <ThermalSettings
          v-if="fermentation.control_mode !== 'monitor_only'"
          :key="fermentation.id"
          :fermentation="fermentation"
          @changed="settingsChanged"
        />
        <FermentationControls
          v-if="fermentation.status === 'active'"
          :fermentation="fermentation"
          :loading="loading"
          @changed="ended"
        />
        <template v-else
          ><p class="detail-concluded">
            Fermentazione conclusa definitivamente. Le informazioni restano
            consultabili.
          </p>
          <ThermalRegulationStatus :fermentation="fermentation"
        /></template>
      </div>
    </template>
  </section>
</template>
