<script setup lang="ts">
import { computed, onMounted, onUnmounted, nextTick, ref } from 'vue'
import FermentationWizard from './FermentationWizard.vue'
import FermentationArchive from './FermentationArchive.vue'
import FermentationHistory from './FermentationHistory.vue'
import PillRegistry from './PillRegistry.vue'
import ThermalDeviceRegistry from './ThermalDeviceRegistry.vue'
import SettingsPage from './SettingsPage.vue'
import HomePage from './HomePage.vue'
import NavigationIcon from './NavigationIcon.vue'
import PillDiagnostics from './PillDiagnostics.vue'
import { pillCommunication, type CommunicationClock } from './communication'
import type {
  Fermentation,
  FermentationSummary,
  FermentationTab,
} from './fermentations'
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
type DeviceTab = 'pills' | 'thermal'
function requestedDeviceTab(): DeviceTab {
  return new URLSearchParams(window.location.search).get('tab') === 'thermal'
    ? 'thermal'
    : 'pills'
}
const deviceTab = ref<DeviceTab>(requestedDeviceTab())
function selectDeviceTab(tab: DeviceTab) {
  if (tab === deviceTab.value) return
  const url = new URL(window.location.href)
  if (tab === 'thermal') url.searchParams.set('tab', tab)
  else url.searchParams.delete('tab')
  window.history.pushState(null, '', url)
  restoreSelection()
}
function deviceTabKey(event: KeyboardEvent, index: number) {
  const target =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? 1
        : ['ArrowLeft', 'ArrowRight'].includes(event.key)
          ? 1 - index
          : null
  if (target === null) return
  event.preventDefault()
  const tab = target === 0 ? 'pills' : 'thermal'
  selectDeviceTab(tab)
  void nextTick(() => document.getElementById(`device-tab-${tab}`)?.focus())
}
function requestedTab(): FermentationTab {
  return new URLSearchParams(window.location.search).get('tab') === 'management'
    ? 'management'
    : 'trend'
}
const detailTab = ref<FermentationTab>(requestedTab())
function selectDetailTab(tab: FermentationTab) {
  if (tab === detailTab.value) return
  const url = new URL(window.location.href)
  if (tab === 'management') url.searchParams.set('tab', tab)
  else url.searchParams.delete('tab')
  window.history.pushState(null, '', url)
  restoreSelection()
}
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
  if (target === 'diagnostics' && identifier)
    return `/?page=diagnostics&pill=${encodeURIComponent(identifier)}`
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
const diagnosticPillId = ref(
  new URLSearchParams(window.location.search).get('pill') ?? '',
)
function selectDiagnostic(identifier: string) {
  navigate('diagnostics', identifier)
}
const diagnosticReading = computed(
  () =>
    pills.value.find((pill) => pill.id === diagnosticPillId.value)?.reading ??
    null,
)
const activeFermentations = ref<FermentationSummary[]>([])
const selectedId = ref(
  new URLSearchParams(window.location.search).get('fermentation') || null,
)
function selectFermentation(identifier: string | null) {
  navigate(identifier ? 'detail' : 'home', identifier ?? undefined)
}
function restoreSelection() {
  page.value = requestedPage()
  deviceTab.value = requestedDeviceTab()
  const diagnostic = new URLSearchParams(window.location.search).get('pill')
  if (diagnostic !== null) diagnosticPillId.value = diagnostic
  detailTab.value = requestedTab()
  selectedId.value =
    new URLSearchParams(window.location.search).get('fermentation') || null
}
const reading = diagnosticReading
const isLoading = ref(false)
const hasSnapshot = ref(false)
const diagnosticMissing = computed(
  () =>
    hasSnapshot.value &&
    !!diagnosticPillId.value &&
    !pills.value.some((pill) => pill.id === diagnosticPillId.value),
)
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
const communicationClock = computed<CommunicationClock | null>(() => {
  if (!serverReference.value || communicationTimeout.value === null) return null
  return {
    now:
      serverReference.value.time +
      (clock.value - serverReference.value.observedAt) / 1000,
    timeout: communicationTimeout.value,
  }
})
const dataStatus = computed(() => {
  if (!hasSnapshot.value) return 'Stato dei dati non disponibile'
  if (!reading.value) return 'Nessuna lettura'
  const status = pillCommunication(
    pills.value.find((pill) => pill.id === diagnosticPillId.value),
    communicationClock.value,
    connection.value === 'live',
  )
  return {
    unknown: 'Verifica comunicazione…',
    never_received: 'Nessuna comunicazione ricevuta',
    receiving: 'Lettura disponibile',
    timed_out: 'Timeout di comunicazione superato',
    unconfirmed_timeout: 'Timeout di comunicazione superato',
  }[status]
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
  const requested = new URLSearchParams(window.location.search).get('pill')
  if (page.value === 'diagnostics' && requested !== null)
    diagnosticPillId.value = requested
  else if (!pills.value.some((pill) => pill.id === diagnosticPillId.value))
    diagnosticPillId.value = snapshot.pill_id ?? ''
  activeFermentations.value = snapshot.active_fermentations
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
          :clock="communicationClock"
          :connected="connection === 'live'"
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
            :revision="historyRevision"
            @select="selectFermentation"
        /></template>
        <template v-else-if="page === 'devices'">
          <div class="page-heading">
            <p class="eyebrow">Il tuo equipaggiamento</p>
            <h1>Dispositivi</h1>
            <p class="description">
              Pillole e controllo termico, ciascuno al proprio posto.
            </p>
          </div>
          <div
            class="device-tabs"
            role="tablist"
            aria-label="Tipo di dispositivo"
          >
            <button
              v-for="(tab, index) in ['pills', 'thermal'] as const"
              :id="`device-tab-${tab}`"
              :key="tab"
              type="button"
              role="tab"
              :aria-selected="deviceTab === tab"
              :aria-controls="`device-panel-${tab}`"
              :tabindex="deviceTab === tab ? 0 : -1"
              @click="selectDeviceTab(tab)"
              @keydown="deviceTabKey($event, index)"
            >
              {{ tab === 'pills' ? 'Pillole' : 'Dispositivi termici' }}
            </button>
          </div>
          <div
            v-show="deviceTab === 'pills'"
            id="device-panel-pills"
            role="tabpanel"
            aria-labelledby="device-tab-pills"
          >
            <PillRegistry
              :pills="pills"
              :ready="hasSnapshot"
              :active="activeFermentations"
              :clock="communicationClock"
              :connected="connection === 'live'"
              :loading="isLoading"
              :error="error"
              @diagnostic="selectDiagnostic"
              @select="selectFermentation"
              @changed="loadLatest"
            /><a
              class="section-link"
              href="/?page=diagnostics"
              @click="follow($event, 'diagnostics')"
              >Diagnostica delle pillole →</a
            >
          </div>
          <div
            v-show="deviceTab === 'thermal'"
            id="device-panel-thermal"
            role="tabpanel"
            aria-labelledby="device-tab-thermal"
          >
            <ThermalDeviceRegistry />
          </div>
        </template>
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
          <FermentationWizard
            v-if="hasSnapshot"
            :loading="isLoading"
            :pills="pills"
            @created="created"
            @cancelled="navigate('home')"
            @refresh="loadLatest"
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
            :tab="detailTab"
            :recovery-revision="recoveryRevision"
            :identifier="selectedId"
            :revision="historyRevision"
            :live="false"
            @changed="historyChanged"
            @tab="selectDetailTab"
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
            ><select
              id="diagnostic-pill"
              v-model="diagnosticPillId"
              @change="selectDiagnostic(diagnosticPillId)"
            >
              <option
                v-if="diagnosticMissing"
                :value="diagnosticPillId"
                disabled
              >
                Pillola non disponibile
              </option>
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
          <section v-if="diagnosticMissing" class="empty">
            <h2>Pillola non disponibile</h2>
            <p>
              La pillola richiesta non è presente nel registro operativo. Le sue
              fermentazioni restano consultabili nell’Archivio.
            </p>
            <a href="/?page=devices" @click="follow($event, 'devices')"
              >Gestisci dispositivi</a
            >
          </section>
          <PillDiagnostics
            v-else-if="reading"
            :pill="pills.find((pill) => pill.id === diagnosticPillId)!"
          />
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
