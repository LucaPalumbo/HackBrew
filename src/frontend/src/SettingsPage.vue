<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import type { GlobalSettings } from './settings'
import { useLatestRequest } from './useLatestRequest'

const settings = ref<GlobalSettings | null>(null)
const draft = ref('')
const dirty = ref(false)
const saving = ref(false)
const notice = ref('')
const saveError = ref('')
const { loading, error, run, refresh, invalidate } = useLatestRequest(
  'Non è stato possibile leggere le impostazioni. Riprova.',
)
const numbers = new Intl.NumberFormat('it-IT', { maximumSignificantDigits: 15 })
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
let timer: ReturnType<typeof setInterval> | undefined

function accept(payload: GlobalSettings) {
  settings.value = payload
  if (!dirty.value) draft.value = String(payload.communication_timeout_seconds)
}
async function load(background = false) {
  await run(
    async (signal) => {
      const response = await fetch('/api/settings', {
        signal,
        cache: 'no-store',
      })
      if (!response.ok) throw new Error('Settings unavailable')
      return (await response.json()) as GlobalSettings
    },
    accept,
    background,
  )
}
async function save() {
  const duration = Number(draft.value)
  saveError.value = ''
  notice.value = ''
  if (!Number.isFinite(duration) || duration <= 0) {
    saveError.value = 'Inserisci una durata positiva e finita, in secondi.'
    return
  }
  saving.value = true
  invalidate()
  try {
    const response = await fetch('/api/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ communication_timeout_seconds: duration }),
      signal: AbortSignal.timeout(10000),
    })
    if (!response.ok) throw new Error('Settings not saved')
    const payload = (await response.json()) as GlobalSettings
    dirty.value = false
    accept(payload)
    notice.value =
      'Timeout salvato. Lo stato di applicazione ai dispositivi è indicato sotto.'
  } catch {
    saveError.value =
      'Il salvataggio non è stato confermato. Controlla il collegamento e riprova.'
  } finally {
    saving.value = false
  }
}
onMounted(() => {
  void load()
  timer = setInterval(() => {
    if (!saving.value) refresh(() => load(true))
  }, 1000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="intro">
    <div>
      <p class="eyebrow">Configurazione globale</p>
      <h1>Impostazioni</h1>
      <p class="description">
        Un solo timeout di comunicazione per tutte le fermentazioni e i
        dispositivi termici.
      </p>
    </div>
  </div>
  <section class="fermentation-panel" aria-label="Timeout globale">
    <h2>Timeout di comunicazione</h2>
    <p>Il valore iniziale è di tre ore: 10.800 secondi.</p>
    <p class="description">
      Per le pillole il tempo decorre dall’ultima ricezione dei dati sul server.
      Per i dispositivi termici decorre dall’ultimo comando di controllo valido.
      Leggere lo stato o sincronizzare la configurazione non rinnova quel
      contatto.
    </p>
    <p class="metric-caption">
      Il timeout si applica a tutti i dispositivi associati alle fermentazioni
      con regolazione termica.
    </p>
    <p v-if="loading" role="status">Caricamento impostazioni…</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <button
      v-if="error"
      class="text-button"
      :disabled="loading || saving"
      @click="load()"
    >
      Riprova impostazioni
    </button>
    <template v-if="settings">
      <p aria-label="Timeout desiderato">
        Timeout desiderato:
        <strong
          >{{
            numbers.format(settings.communication_timeout_seconds)
          }}
          s</strong
        >
        · Revisione {{ settings.revision }}
      </p>
      <form class="fermentation-form" @submit.prevent="save">
        <div>
          <label for="communication-timeout"
            >Timeout di comunicazione (secondi)</label
          >
          <input
            id="communication-timeout"
            v-model="draft"
            type="number"
            step="any"
            required
            :disabled="saving"
            @input="dirty = true"
          />
        </div>
        <button class="refresh" type="submit" :disabled="saving || loading">
          {{ saving ? 'Salvataggio…' : 'Salva timeout' }}
        </button>
      </form>
      <p v-if="saveError" class="error" role="alert">{{ saveError }}</p>
      <p
        v-if="notice"
        class="operation-notice"
        role="status"
        aria-label="Esito salvataggio"
      >
        {{ notice }}
      </p>
    </template>
  </section>
  <section v-if="settings" aria-label="Sincronizzazione dei dispositivi">
    <h2>Applicazione ai dispositivi</h2>
    <p v-if="settings.devices.length === 0">
      Nessun dispositivo termico registrato.
    </p>
    <section
      v-for="device in settings.devices"
      :key="device.id"
      class="fermentation-panel"
      :aria-label="`Sincronizzazione ${device.name}`"
    >
      <h3>{{ device.name }}</h3>
      <p role="status">
        {{
          device.status === 'confirmed'
            ? 'Sincronizzato'
            : device.status === 'error'
              ? 'Errore di sincronizzazione'
              : 'Sincronizzazione in attesa'
        }}
      </p>
      <p class="fermentation-period">
        Richiesto: {{ numbers.format(device.desired_timeout_seconds) }} s ·
        Revisione {{ device.desired_revision }}
      </p>
      <template
        v-if="
          device.applied_revision !== null &&
          device.applied_timeout_seconds !== null
        "
      >
        <p class="fermentation-period">
          Revisione confermata: {{ device.applied_revision }}
        </p>
        <p class="fermentation-period">
          Ultimo timeout confermato:
          {{ numbers.format(device.applied_timeout_seconds) }} s
        </p>
        <p v-if="device.confirmed_at" class="fermentation-period">
          Ultima conferma:
          <time :datetime="device.confirmed_at">{{
            dates.format(new Date(device.confirmed_at))
          }}</time>
        </p>
      </template>
      <p v-else class="fermentation-period">
        Applicazione non ancora confermata.
      </p>
      <p v-if="device.error" class="error">{{ device.error }}</p>
    </section>
  </section>
</template>
