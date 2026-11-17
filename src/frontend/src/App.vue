<script setup lang="ts">
import { computed, onMounted, onUnmounted, nextTick, ref } from 'vue'
import FermentationControls from './FermentationControls.vue'
import FermentationArchive from './FermentationArchive.vue'
import FermentationHistory from './FermentationHistory.vue'
import PillRegistry from './PillRegistry.vue'
import ThermalDeviceRegistry from './ThermalDeviceRegistry.vue'
import SettingsPage from './SettingsPage.vue'
import HomePage from './HomePage.vue'
import NavigationIcon from './NavigationIcon.vue'
import ReadingSummary from './ReadingSummary.vue'
import type { Fermentation, FermentationSummary } from './fermentations'
import type { PillSnapshot, Reading } from './readings'

type Snapshot = {
  reading: Reading | null
  pill_id: string | null
  pills: PillSnapshot[]
  communication_timeout_seconds: number
  server_time: number
  fermentation: Fermentation | null
  fermentation_reading: Reading | null
  active_fermentations: FermentationSummary[]
}

type Page =
  'home' | 'archive' | 'devices' | 'settings' | 'new' | 'diagnostics' | 'detail'
const navigation = [
  { page: 'home', label: 'Home' },
  { page: 'archive', label: 'Archivio' },
  { page: 'devices', label: 'Dispositivi' },
  { page: 'settings', label: 'Impostazioni' },
] as const
const pageNames: Record<Page, string> = {
  home: 'Home',
  archive: 'Archivio',
  devices: 'Dispositivi',
  settings: 'Impostazioni',
  new: 'Nuova fermentazione',
  diagnostics: 'Diagnostica delle pillole',
  detail: 'Dettaglio fermentazione',
}
function requestedPage(): Page {
  const query = new URLSearchParams(window.location.search)
  if (query.get('fermentation')) return 'detail'
  const candidate = query.get('page') ?? 'home'
  return Object.hasOwn(pageNames, candidate) ? (candidate as Page) : 'home'
}
const page = ref<Page>(requestedPage())
const main = ref<HTMLElement>()
const operationNotice = ref('')
const activeNavigation = computed(() =>
  page.value === 'detail'
    ? 'home'
    : page.value === 'diagnostics'
      ? 'devices'
      : page.value,
)
function destination(target: Page, identifier?: string) {
  if (identifier) return `/?fermentation=${encodeURIComponent(identifier)}`
  return target === 'home' ? '/' : `/?page=${target}`
}
function navigate(target: Page, identifier?: string) {
  window.history.pushState(null, '', destination(target, identifier))
  restoreSelection()
  void nextTick(() => {
    main.value?.focus({ preventScroll: true })
    window.scrollTo({ top: 0 })
  })
}
function follow(event: MouseEvent, target: Page) {
  if (
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
    return
  event.preventDefault()
  navigate(target)
}
function created(cycle: Fermentation) {
  operationNotice.value = `Fermentazione “${cycle.name}” avviata.`
  navigate('detail', cycle.id)
  void loadLatest()
}
function historyChanged() {
  operationNotice.value = ''
  void loadLatest()
}
const pills = ref<PillSnapshot[]>([])
const diagnosticPillId = ref('')
const diagnosticReading = computed(
  () =>
    pills.value.find((pill) => pill.id === diagnosticPillId.value)?.reading ??
    null,
)
const fermentation = ref<Fermentation | null>(null)
const activeFermentations = ref<FermentationSummary[]>([])
const fermentationReading = ref<Reading | null>(null)
const selectedId = ref(
  new URLSearchParams(window.location.search).get('fermentation') || null,
)
function selectFermentation(identifier: string | null) {
  navigate(identifier ? 'detail' : 'home', identifier ?? undefined)
}
function restoreSelection() {
  page.value = requestedPage()
  selectedId.value =
    new URLSearchParams(window.location.search).get('fermentation') || null
}
const reading = diagnosticReading
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
let communicationTimer: ReturnType<typeof setInterval> | undefined
const communicationTimeout = ref<number | null>(null)
const serverReference = ref<{ time: number; observedAt: number } | null>(null)
const clock = ref(performance.now())
const dataStatus = computed(() => {
  if (!hasSnapshot.value) return 'Stato dei dati non disponibile'
  if (!reading.value) return 'Nessuna lettura'
  if (!serverReference.value || communicationTimeout.value === null)
    return 'Verifica comunicazione…'
  const serverNow =
    serverReference.value.time +
    (clock.value - serverReference.value.observedAt) / 1000
  const identifier = diagnosticPillId.value
  const received = pills.value.find(
    (pill) => pill.id === identifier,
  )?.last_received_at
  if (!received) return 'Nessuna comunicazione ricevuta'
  return serverNow - new Date(received).getTime() / 1000 >=
    communicationTimeout.value
    ? 'Timeout di comunicazione superato'
    : 'Lettura disponibile'
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
  pills.value = snapshot.pills
  if (!pills.value.some((pill) => pill.id === diagnosticPillId.value))
    diagnosticPillId.value = snapshot.pill_id ?? ''
  fermentation.value = snapshot.fermentation
  activeFermentations.value = snapshot.active_fermentations
  fermentationReading.value = snapshot.fermentation_reading
  communicationTimeout.value = snapshot.communication_timeout_seconds
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
  communicationTimer = setInterval(() => {
    clock.value = performance.now()
  }, 1000)
})
onUnmounted(() => {
  disposed = true
  window.removeEventListener('offline', disconnectLive)
  window.removeEventListener('online', connectLive)
  window.removeEventListener('popstate', restoreSelection)
  events?.close()
  clearInterval(communicationTimer)
})
</script>
<template>
  <div class="app-shell">
    <a class="skip-navigation" href="#main-content">Vai al contenuto</a>
    <aside class="app-sidebar">
      <a
        class="app-brand"
        href="/"
        aria-label="HackBrew, pagina iniziale"
        @click="follow($event, 'home')"
        ><span class="app-brand-mark" aria-hidden="true">hb</span>HackBrew</a
      >
      <span class="sidebar-caption">IL TUO BIRRIFICIO</span>
      <nav aria-label="Navigazione principale">
        <a
          v-for="item in navigation"
          :key="item.page"
          :href="destination(item.page)"
          :aria-current="activeNavigation === item.page ? 'page' : undefined"
          @click="follow($event, item.page)"
          ><NavigationIcon :name="item.page" /><span>{{ item.label }}</span></a
        >
      </nav>
      <a
        class="create-fermentation"
        href="/?page=new"
        :aria-current="page === 'new' ? 'page' : undefined"
        @click="follow($event, 'new')"
        ><span aria-hidden="true">＋</span>Nuova fermentazione</a
      >
      <div class="sidebar-footer">
        HackBrew<small>Il tuo spazio per fare buona birra.</small>
      </div>
    </aside>
    <div class="app-content">
      <header class="app-topbar">
        <span
          >Il tuo birrificio
          <span class="app-breadcrumb">/ {{ pageNames[page] }}</span></span
        >
        <p
          class="live-connection"
          :class="{ 'connection-error': connection === 'reconnecting' }"
          :role="connection === 'reconnecting' ? 'alert' : 'status'"
          aria-label="Collegamento live"
        >
          {{ connectionStatus }}
        </p>
      </header>
      <main id="main-content" ref="main" class="app-main" tabindex="-1">
        <HomePage
          v-if="page === 'home'"
          :ready="hasSnapshot"
          :loading="isLoading"
          :error="error"
          :active="activeFermentations"
          :pills="pills"
          :revision="historyRevision"
          @select="selectFermentation"
          @retry="loadLatest"
        />
        <template v-else-if="page === 'archive'"
          ><div class="page-heading">
            <p class="eyebrow">Tutte le tue birre</p>
            <h1>Archivio</h1>
            <p class="description">
              Ritrova le tue fermentazioni e aprine il dettaglio.
            </p>
          </div>
          <FermentationArchive
            :recovery-revision="recoveryRevision"
            :selected-id="null"
            :active-id="fermentation?.id ?? null"
            :revision="historyRevision"
            @select="selectFermentation"
        /></template>
        <template v-else-if="page === 'devices'"
          ><PillRegistry
            :pills="pills"
            :loading="isLoading"
            :error="error"
            @changed="loadLatest" /><a
            class="section-link"
            href="/?page=diagnostics"
            @click="follow($event, 'diagnostics')"
            >Diagnostica delle pillole →</a
          ><ThermalDeviceRegistry
        /></template>
        <SettingsPage v-else-if="page === 'settings'" />
        <template v-else-if="page === 'new'"
          ><div class="page-heading">
            <p class="eyebrow">Un nuovo inizio</p>
            <h1>Nuova fermentazione</h1>
            <p class="description">
              Scegli la pillola e la regolazione della tua prossima birra.
            </p>
          </div>
          <p v-if="error" role="alert" class="error">
            {{ error }}
            <button type="button" class="text-button" @click="loadLatest">
              Riprova
            </button>
          </p>
          <FermentationControls
            v-if="hasSnapshot"
            :fermentation="null"
            :loading="isLoading"
            :pills="pills"
            allow-start
            @changed="created"
          />
          <p v-else role="status">Caricamento dispositivi…</p></template
        >
        <template v-else-if="page === 'detail'"
          ><div class="detail-navigation">
            <a href="/" @click="follow($event, 'home')">← Home</a
            ><a href="/?page=archive" @click="follow($event, 'archive')"
              >Archivio →</a
            >
          </div>
          <p
            v-if="operationNotice"
            class="operation-notice"
            role="status"
            aria-label="Esito operazione"
          >
            {{ operationNotice }}
          </p>
          <FermentationHistory
            :recovery-revision="recoveryRevision"
            :identifier="selectedId"
            :revision="historyRevision"
            :live="false"
            @changed="historyChanged"
        /></template>
        <template v-else-if="page === 'diagnostics'"
          ><div class="page-heading">
            <p class="eyebrow">Misure e comunicazione</p>
            <h1>Diagnostica delle pillole</h1>
            <p class="description">
              L’ultima lettura di ogni pillola, anche senza una fermentazione.
            </p>
          </div>
          <button
            class="refresh"
            type="button"
            :disabled="isLoading"
            @click="loadLatest"
          >
            {{ isLoading ? 'Aggiornamento…' : 'Aggiorna lettura' }}
          </button>
          <div v-if="pills.length" class="diagnostic-selection">
            <label for="diagnostic-pill">Pillola diagnostica</label
            ><select id="diagnostic-pill" v-model="diagnosticPillId">
              <option v-for="pill in pills" :key="pill.id" :value="pill.id">
                {{ pill.name }} · {{ pill.mac }}
              </option>
            </select>
          </div>
          <p
            class="data-status"
            :class="{
              stale: dataStatus === 'Timeout di comunicazione superato',
            }"
            role="status"
            aria-label="Stato dei dati"
          >
            {{ dataStatus }}
          </p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <ReadingSummary v-if="reading" :reading="reading" />
          <section v-else-if="hasSnapshot && !error" class="empty">
            <h2>In attesa della prima lettura</h2>
            <p>
              Le nuove letture della pillola appariranno automaticamente qui.
            </p>
            <a href="/?page=devices" @click="follow($event, 'devices')"
              >Gestisci dispositivi</a
            >
          </section></template
        >
      </main>
    </div>
  </div>
</template>
