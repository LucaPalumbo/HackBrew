<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { capabilityNames, modeNames } from './thermalDevices'
import type { Capability, ThermalDevice } from './thermalDevices'
import { useLatestRequest } from './useLatestRequest'

const devices = ref<ThermalDevice[]>([])
const loaded = ref(false)
const name = ref('')
const capability = ref<Capability>('heating')
const baseUrl = ref('')
const saving = ref(false)
const checking = ref<string[]>([])
const registrationError = ref('')
const notice = ref('')
const { loading, error, run } = useLatestRequest(
  'Non è stato possibile recuperare i dispositivi termici. Riprova.',
)
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const numbers = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 3 })

async function load() {
  await run(
    async (signal) => {
      const response = await fetch('/api/thermal-devices', {
        signal,
        cache: 'no-store',
      })
      if (!response.ok) throw new Error('Devices unavailable')
      return (await response.json()) as { devices: ThermalDevice[] }
    },
    (payload) => {
      devices.value = payload.devices
      loaded.value = true
    },
  )
}

async function register() {
  saving.value = true
  registrationError.value = ''
  notice.value = ''
  try {
    const response = await fetch('/api/thermal-devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.value.trim(),
        capability: capability.value,
        base_url: baseUrl.value.trim(),
      }),
      signal: AbortSignal.timeout(10000),
    })
    const payload: { detail?: unknown } = await response.json()
    if (!response.ok) {
      registrationError.value =
        typeof payload.detail === 'string'
          ? payload.detail
          : 'Controlla nome, funzioni e indirizzo HTTP(S) del dispositivo.'
      return
    }
    notice.value = `Dispositivo “${name.value.trim()}” registrato.`
    name.value = ''
    baseUrl.value = ''
    await load()
  } catch {
    registrationError.value =
      'Non è stato possibile registrare il dispositivo. Riprova.'
  } finally {
    saving.value = false
  }
}

async function check(device: ThermalDevice) {
  checking.value = [...checking.value, device.id]
  try {
    const response = await fetch(
      `/api/thermal-devices/${encodeURIComponent(device.id)}/check`,
      {
        method: 'POST',
        signal: AbortSignal.timeout(10000),
      },
    )
    if (!response.ok) throw new Error('Verification unavailable')
    const payload: { device: ThermalDevice } = await response.json()
    devices.value = devices.value.map((item) =>
      item.id === device.id ? payload.device : item,
    )
  } catch {
    devices.value = devices.value.map((item) =>
      item.id === device.id
        ? {
            ...item,
            verification_status: 'error',
            actual_mode: null,
            application_status: null,
            desired_mode: null,
            reported_capability: null,
            confirmed_at: null,
            applied_timeout_seconds: null,
            applied_config_revision: null,
            communication_error:
              'Non è stato possibile completare la verifica. Riprova.',
          }
        : item,
    )
  } finally {
    checking.value = checking.value.filter((id) => id !== device.id)
  }
}

function stateLabel(device: ThermalDevice) {
  if (device.actual_mode === null) return 'Stato sconosciuto'
  if (device.verification_status === 'pending')
    return `Ultimo stato rilevato: ${modeNames[device.actual_mode]}`
  return device.actual_mode === 'off'
    ? 'Spento confermato'
    : `${modeNames[device.actual_mode]} confermato`
}
onMounted(load)
</script>

<template>
  <section class="thermal-registry" aria-label="Dispositivi termici">
    <h2>Dispositivi termici</h2>
    <p class="description">
      Registra riscaldatori, raffreddatori o dispositivi combinati e verifica il
      loro stato.
    </p>
    <section
      class="fermentation-panel"
      aria-label="Registrazione dispositivo termico"
    >
      <h3>Registra un dispositivo termico</h3>
      <form class="fermentation-form" @submit.prevent="register">
        <div>
          <label for="thermal-name">Nome del dispositivo termico</label>
          <input
            id="thermal-name"
            v-model="name"
            required
            maxlength="200"
            :disabled="saving"
          />
        </div>
        <div>
          <label for="thermal-capability">Funzioni del dispositivo</label>
          <select
            id="thermal-capability"
            v-model="capability"
            :disabled="saving"
          >
            <option
              v-for="(label, value) in capabilityNames"
              :key="value"
              :value="value"
            >
              {{ label }}
            </option>
          </select>
        </div>
        <div>
          <label for="thermal-url">Indirizzo HTTP</label>
          <input
            id="thermal-url"
            v-model="baseUrl"
            type="url"
            required
            :disabled="saving"
            placeholder="http://192.168.1.50:8000"
            autocapitalize="off"
            spellcheck="false"
          />
        </div>
        <button
          class="refresh"
          type="submit"
          :disabled="saving || loading || checking.length > 0"
        >
          {{ saving ? 'Registrazione…' : 'Registra dispositivo termico' }}
        </button>
      </form>
      <p class="metric-caption">
        Usa l’indirizzo HTTP(S) raggiungibile dal server, senza credenziali. La
        registrazione non accende il dispositivo.
      </p>
      <p v-if="registrationError" class="error" role="alert">
        {{ registrationError }}
      </p>
      <p v-if="notice" class="operation-notice" role="status">{{ notice }}</p>
    </section>
    <button
      class="text-button"
      :disabled="loading || saving || checking.length > 0"
      @click="load"
    >
      Aggiorna dispositivi termici
    </button>
    <p v-if="loading" role="status">Caricamento dispositivi termici…</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loaded && !loading && !error && devices.length === 0">
      Nessun dispositivo termico registrato.
    </p>
    <section
      v-for="device in devices"
      :key="device.id"
      class="fermentation-panel thermal-device"
      :aria-label="`Dispositivo termico ${device.name}`"
    >
      <h3>{{ device.name }}</h3>
      <p>{{ capabilityNames[device.capability] }}</p>
      <p class="fermentation-period thermal-address">{{ device.base_url }}</p>
      <p v-if="device.verification_status === 'unverified'">Non verificato</p>
      <p v-if="device.verification_status === 'pending'" role="status">
        Conferma fisica in attesa. Il comando richiesto non è ancora confermato.
      </p>
      <p class="thermal-state">{{ stateLabel(device) }}</p>
      <p
        v-if="device.application_status === 'timed_out'"
        class="fermentation-period"
      >
        Spegnimento autonomo per timeout di comunicazione.
      </p>
      <p v-if="device.desired_mode !== null" class="fermentation-period">
        Stato richiesto: {{ modeNames[device.desired_mode] }}
      </p>
      <p v-if="device.reported_capability" class="fermentation-period">
        Funzioni riportate: {{ capabilityNames[device.reported_capability] }}
      </p>
      <p
        v-if="device.applied_timeout_seconds !== null"
        class="fermentation-period"
      >
        Timeout applicato:
        {{ numbers.format(device.applied_timeout_seconds) }} s
      </p>
      <p
        v-if="device.applied_config_revision !== null"
        class="fermentation-period"
      >
        Revisione applicata: {{ device.applied_config_revision }}
      </p>
      <p v-if="device.confirmed_at" class="fermentation-period">
        Ultima conferma:
        <time :datetime="device.confirmed_at">{{
          dates.format(new Date(device.confirmed_at))
        }}</time>
      </p>
      <p v-if="device.checked_at" class="fermentation-period">
        Ultima verifica:
        <time :datetime="device.checked_at">{{
          dates.format(new Date(device.checked_at))
        }}</time>
      </p>
      <p v-if="device.communication_error" class="error" role="alert">
        {{ device.communication_error }}
      </p>
      <p
        v-if="device.actual_mode === null && device.last_confirmation"
        class="fermentation-period"
      >
        Ultima conferma precedente:
        {{ modeNames[device.last_confirmation.actual_mode] }} ·
        <time :datetime="device.last_confirmation.confirmed_at">{{
          dates.format(new Date(device.last_confirmation.confirmed_at))
        }}</time>
      </p>
      <button
        class="refresh"
        :disabled="loading || saving || checking.includes(device.id)"
        @click="check(device)"
      >
        {{
          checking.includes(device.id)
            ? 'Verifica in corso…'
            : 'Verifica collegamento'
        }}
      </button>
    </section>
  </section>
</template>
