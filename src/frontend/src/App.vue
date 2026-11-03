<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import FermentationControls from './FermentationControls.vue'
import FermentationArchive from './FermentationArchive.vue'
import FermentationHistory from './FermentationHistory.vue'
import type { Fermentation } from './fermentations'
import type { Reading } from './readings'

type Snapshot = {
  reading: Reading | null
  freshness_seconds: number
  server_time: number
  fermentation: Fermentation | null
  fermentation_reading: Reading | null
}

const diagnosticReading = ref<Reading | null>(null)
const fermentation = ref<Fermentation | null>(null)
const fermentationReading = ref<Reading | null>(null)
const selectedId = ref(
  new URLSearchParams(window.location.search).get('fermentation') || null,
)
function selectFermentation(identifier: string | null) {
  if (selectedId.value === identifier) return
  const url = new URL(window.location.href)
  if (identifier) url.searchParams.set('fermentation', identifier)
  else url.searchParams.delete('fermentation')
  window.history.pushState(null, '', url)
  selectedId.value = identifier
}
function restoreSelection() {
  selectedId.value =
    new URLSearchParams(window.location.search).get('fermentation') || null
}
const reading = computed(() =>
  fermentation.value ? fermentationReading.value : diagnosticReading.value,
)
const isLoading = ref(false)
const hasSnapshot = ref(false)
const error = ref('')
const connection = ref<'connecting' | 'live' | 'reconnecting'>('connecting')
const connectionStatus = computed(() => {
  if (connection.value === 'live') return 'Collegamento live attivo'
  if (connection.value === 'reconnecting')
    return 'Collegamento live interrotto. Riconnessione automatica…'
  return 'Collegamento live in corso…'
})
let events: EventSource | undefined
let streamRevision = 0
const historyRevision = ref(0)
const recoveryRevision = ref(0)
let disposed = false
let freshnessTimer: ReturnType<typeof setInterval> | undefined
const freshnessSeconds = ref<number | null>(null)
const serverReference = ref<{ time: number; observedAt: number } | null>(null)
const clock = ref(performance.now())
const dataStatus = computed(() => {
  if (!hasSnapshot.value) return 'Stato dei dati non disponibile'
  if (!reading.value)
    return fermentation.value ? 'In attesa di letture' : 'Nessuna lettura'
  if (!serverReference.value || freshnessSeconds.value === null)
    return 'Verifica freschezza…'
  const serverNow =
    serverReference.value.time +
    (clock.value - serverReference.value.observedAt) / 1000
  return serverNow - reading.value.timestamp >= freshnessSeconds.value
    ? 'Dati non aggiornati'
    : 'Lettura disponibile'
})

const temperatureFormat = new Intl.NumberFormat('it-IT', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const dateFormat = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})

async function loadLatest() {
  const revision = streamRevision
  isLoading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/readings/latest', {
      cache: 'no-store',
      signal: AbortSignal.timeout(10000),
    })
    if (!response.ok) throw new Error('Reading unavailable')
    const payload: Snapshot = await response.json()
    if (!disposed && revision === streamRevision) applySnapshot(payload)
  } catch {
    if (!disposed && revision === streamRevision)
      error.value = 'Non è stato possibile recuperare la lettura. Riprova.'
  } finally {
    isLoading.value = false
  }
}

function applySnapshot(snapshot: Snapshot) {
  hasSnapshot.value = true
  historyRevision.value += 1
  diagnosticReading.value = snapshot.reading
  fermentation.value = snapshot.fermentation
  fermentationReading.value = snapshot.fermentation_reading
  freshnessSeconds.value = snapshot.freshness_seconds
  clock.value = performance.now()
  serverReference.value = {
    time: snapshot.server_time,
    observedAt: clock.value,
  }
}

function connectLive() {
  events?.close()
  if (!navigator.onLine) {
    connection.value = 'reconnecting'
    return
  }
  connection.value = 'connecting'
  events = new EventSource('/api/readings/events')
  events.addEventListener('reading', (event: MessageEvent<string>) => {
    const snapshot: Snapshot = JSON.parse(event.data)
    streamRevision += 1
    applySnapshot(snapshot)
    if (connection.value !== 'live') recoveryRevision.value += 1
    error.value = ''
    connection.value = 'live'
  })
  events.onerror = () => {
    connection.value = 'reconnecting'
  }
  events.addEventListener('unavailable', () => {
    connection.value = 'reconnecting'
  })
}

function disconnectLive() {
  events?.close()
  connection.value = 'reconnecting'
}

onMounted(() => {
  void loadLatest()
  window.addEventListener('offline', disconnectLive)
  window.addEventListener('online', connectLive)
  window.addEventListener('popstate', restoreSelection)
  connectLive()
  freshnessTimer = setInterval(() => {
    clock.value = performance.now()
  }, 1000)
})
onUnmounted(() => {
  disposed = true
  window.removeEventListener('offline', disconnectLive)
  window.removeEventListener('online', connectLive)
  window.removeEventListener('popstate', restoreSelection)
  events?.close()
  clearInterval(freshnessTimer)
})
</script>

<template>
  <div class="dashboard">
    <header class="topbar">
      <a class="brand" href="/" aria-label="HackBrew, pagina iniziale">
        <span class="brand-mark" aria-hidden="true">hb</span>
        <span>Hack<span class="brand-accent">Brew</span></span>
      </a>
      <span class="mode">{{
        selectedId
          ? 'Storico fermentazioni'
          : !hasSnapshot
            ? 'Monitoraggio non disponibile'
            : fermentation
              ? 'Fermentazione in corso'
              : 'Modalità diagnostica'
      }}</span>
    </header>

    <main>
      <div class="intro">
        <div>
          <p class="eyebrow">Il tuo fermentatore</p>
          <h1>La tua pillola,<br />a colpo d’occhio.</h1>
          <p class="description">
            I valori della pillola, raccolti in un unico posto.
          </p>
        </div>
        <button
          v-if="!selectedId"
          class="refresh"
          type="button"
          :disabled="isLoading"
          @click="loadLatest"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18">
            <path
              d="M20 7v5h-5M4 17v-5h5M6.1 7a7 7 0 0 1 11.5-1L20 9M4 15l2.4 3A7 7 0 0 0 17.9 17"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          {{ isLoading ? 'Aggiornamento…' : 'Aggiorna lettura' }}
        </button>
      </div>

      <FermentationArchive
        :recovery-revision="recoveryRevision"
        :selected-id="selectedId"
        :active-id="fermentation?.id ?? null"
        @select="selectFermentation"
      />
      <FermentationControls
        v-if="!selectedId && hasSnapshot"
        :fermentation="fermentation"
        :loading="isLoading"
        @changed="loadLatest"
      />
      <p v-if="error && !selectedId" class="error" role="alert">{{ error }}</p>
      <p
        class="connection-status"
        :class="{ error: connection === 'reconnecting' }"
        :role="connection === 'reconnecting' ? 'alert' : 'status'"
        aria-label="Collegamento live"
      >
        {{ connectionStatus }}
      </p>
      <template v-if="!selectedId">
        <p
          class="data-status"
          :class="{ stale: dataStatus === 'Dati non aggiornati' }"
          role="status"
          aria-label="Stato dei dati"
        >
          {{ dataStatus }}
        </p>
        <p v-if="isLoading && !reading" class="loading" role="status">
          Caricamento lettura…
        </p>

        <section
          v-else-if="hasSnapshot && !reading && !error"
          class="empty"
          aria-labelledby="empty-heading"
        >
          <span class="empty-symbol" aria-hidden="true">◌</span>
          <p class="eyebrow">Pronti a ricevere</p>
          <h2 id="empty-heading">
            {{
              fermentation
                ? 'In attesa della prima lettura della fermentazione'
                : 'In attesa della prima lettura'
            }}
          </h2>
          <p v-if="fermentation">
            Le letture acquisite dall’avvio di questa fermentazione appariranno
            qui. I dati diagnostici precedenti restano separati.
          </p>
          <p v-else>
            Non abbiamo ancora ricevuto dati dalla pillola. Le nuove letture
            appariranno automaticamente qui.
          </p>
        </section>
        <section v-else-if="reading" aria-label="Ultima lettura">
          <div class="reading-heading">
            <h2>Misure della pillola</h2>
            <span>Ultima rilevazione disponibile</span>
          </div>
          <div class="metrics">
            <section
              class="metric metric-primary"
              aria-labelledby="density-label"
            >
              <div class="metric-heading">
                <h3 id="density-label">Densità</h3>
                <span class="metric-symbol" aria-hidden="true">ρ</span>
              </div>
              <p class="metric-value">
                <span>{{ reading.specific_gravity.toFixed(3) }}</span>
                <span class="metric-unit">SG</span>
              </p>
              <p class="metric-caption">Densità relativa</p>
            </section>
            <section class="metric" aria-labelledby="temperature-label">
              <div class="metric-heading">
                <h3 id="temperature-label">Temperatura</h3>
                <span class="metric-symbol" aria-hidden="true">°</span>
              </div>
              <p class="metric-value">
                <span>{{ temperatureFormat.format(reading.temperature) }}</span>
                <span class="metric-unit">°C</span>
              </p>
              <p class="metric-caption">Nel fermentatore</p>
            </section>
            <section class="metric" aria-labelledby="battery-label">
              <div class="metric-heading">
                <h3 id="battery-label">Batteria</h3>
                <svg
                  class="battery-icon"
                  aria-hidden="true"
                  viewBox="0 0 26 16"
                >
                  <rect
                    x="1"
                    y="2"
                    width="21"
                    height="12"
                    rx="3"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.5"
                  />
                  <path
                    d="M24 6v4"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                  />
                </svg>
              </div>
              <p class="metric-value">
                <span>{{ reading.battery.toFixed(0) }}</span>
                <span class="metric-unit">%</span>
              </p>
              <div class="battery-track" aria-hidden="true">
                <div :style="{ width: `${reading.battery}%` }"></div>
              </div>
              <p class="metric-caption">Carica della pillola</p>
            </section>
          </div>
          <div class="acquisition">
            <div>
              <p class="eyebrow">Acquisizione della lettura</p>
              <time
                aria-label="Acquisizione della lettura"
                :datetime="new Date(reading.timestamp * 1000).toISOString()"
                >{{
                  dateFormat.format(new Date(reading.timestamp * 1000))
                }}</time
              >
            </div>
            <p>
              Ricevuta da HackBrew<br />
              <time :datetime="reading.received_at">{{
                dateFormat.format(new Date(reading.received_at))
              }}</time>
            </p>
          </div>
        </section>
      </template>
      <FermentationHistory
        :recovery-revision="recoveryRevision"
        :identifier="selectedId ?? fermentation?.id ?? null"
        :revision="historyRevision"
        :live="!selectedId"
      />
      <footer class="footnote">
        <span>{{
          selectedId
            ? 'Consultazione storico'
            : !hasSnapshot
              ? 'Stato della fermentazione non disponibile'
              : fermentation
                ? `Fermentazione attiva: ${fermentation.name}`
                : 'Nessuna fermentazione attiva'
        }}</span>
        <span>{{
          selectedId
            ? 'Valori dell’intervallo selezionato'
            : fermentation
              ? 'Ultima lettura della fermentazione'
              : 'Ultima lettura della pillola'
        }}</span>
      </footer>
    </main>
  </div>
</template>
