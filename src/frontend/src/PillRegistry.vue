<script setup lang="ts">
import { ref } from 'vue'
import type { PillSnapshot } from './readings'

defineProps<{ pills: PillSnapshot[]; loading: boolean; error: string }>()
const emit = defineEmits<{ changed: [] }>()
const name = ref('')
const mac = ref('')
const saving = ref(false)
const registrationError = ref('')
const notice = ref('')
const numbers = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 6 })
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
function quantity(value: number | null) {
  return value === null ? 'Non disponibile' : numbers.format(value)
}
async function register() {
  saving.value = true
  registrationError.value = ''
  notice.value = ''
  try {
    const response = await fetch('/api/pills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.value.trim(), mac: mac.value.trim() }),
      signal: AbortSignal.timeout(10000),
    })
    const payload: { detail?: unknown } = await response.json()
    if (!response.ok) {
      registrationError.value =
        typeof payload.detail === 'string'
          ? payload.detail
          : 'Controlla nome e MAC Bluetooth della pillola.'
      return
    }
    notice.value = `Pillola “${name.value.trim()}” registrata.`
    name.value = ''
    mac.value = ''
    emit('changed')
  } catch {
    registrationError.value =
      'Non è stato possibile registrare la pillola. Controlla il collegamento e riprova.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="intro">
    <div>
      <p class="eyebrow">Le tue pillole</p>
      <h1>Dispositivi</h1>
      <p class="description">
        Registra le pillole e i dispositivi termici, controlla letture e stato.
      </p>
    </div>
  </div>
  <section class="fermentation-panel" aria-label="Registrazione pillola">
    <h2>Registra una pillola</h2>
    <form class="fermentation-form" @submit.prevent="register">
      <div>
        <label for="pill-name">Nome della pillola</label>
        <input id="pill-name" v-model="name" required :disabled="saving" />
      </div>
      <div>
        <label for="pill-mac">MAC Bluetooth</label>
        <input
          id="pill-mac"
          v-model="mac"
          required
          :disabled="saving"
          placeholder="AA:BB:CC:DD:EE:FF"
          autocapitalize="characters"
          spellcheck="false"
        />
      </div>
      <button class="refresh" type="submit" :disabled="saving || loading">
        {{ saving ? 'Registrazione…' : 'Registra pillola' }}
      </button>
    </form>
    <p class="metric-caption">Usa l’indirizzo Bluetooth della pillola.</p>
    <p v-if="registrationError" class="error" role="alert">
      {{ registrationError }}
    </p>
    <p v-if="notice" class="operation-notice" role="status">{{ notice }}</p>
  </section>
  <p v-if="error" class="error" role="alert">
    {{ error }}
    <button class="text-button" type="button" @click="emit('changed')">
      Riprova
    </button>
  </p>
  <p v-if="loading" role="status">Caricamento pillole…</p>
  <p v-else-if="!pills.length && !error">Nessuna pillola registrata.</p>
  <section
    v-for="pill in pills"
    :key="pill.id"
    class="fermentation-panel pill-entry"
    :aria-label="`Pillola ${pill.name}`"
  >
    <h2>{{ pill.name }}</h2>
    <p class="fermentation-period">{{ pill.mac }}</p>
    <p class="fermentation-period">
      {{
        pill.available ? 'Disponibile' : 'Assegnata a una fermentazione attiva'
      }}
    </p>
    <p v-if="!pill.reading">Nessuna lettura ricevuta.</p>
    <template v-else>
      <dl class="pill-quantities">
        <div>
          <dt>Densità SG</dt>
          <dd>{{ pill.reading.specific_gravity.toFixed(3) }}</dd>
        </div>
        <div>
          <dt>Temperatura °C</dt>
          <dd>{{ quantity(pill.reading.temperature) }}</dd>
        </div>
        <div>
          <dt>Batteria %</dt>
          <dd>{{ quantity(pill.reading.battery) }}</dd>
        </div>
        <div>
          <dt>Velocità densità · punti SG/giorno</dt>
          <dd>
            {{
              pill.reading.valid === false
                ? 'Non disponibile (misura non valida)'
                : quantity(pill.reading.gravity_velocity)
            }}
          </dd>
        </div>
        <div>
          <dt>Accelerazione X</dt>
          <dd>{{ quantity(pill.reading.accel_x) }}</dd>
        </div>
        <div>
          <dt>Accelerazione Y</dt>
          <dd>{{ quantity(pill.reading.accel_y) }}</dd>
        </div>
        <div>
          <dt>Accelerazione Z</dt>
          <dd>{{ quantity(pill.reading.accel_z) }}</dd>
        </div>
      </dl>
      <p class="metric-caption">
        Accelerazioni: unità non specificata dal gateway.
      </p>
      <p class="fermentation-period">
        Acquisizione:
        <time
          :datetime="new Date(pill.reading.timestamp * 1000).toISOString()"
          >{{ dates.format(new Date(pill.reading.timestamp * 1000)) }}</time
        >
        <br />Prima ricezione della lettura:
        <time :datetime="pill.reading.received_at">{{
          dates.format(new Date(pill.reading.received_at))
        }}</time>
      </p>
    </template>
    <p v-if="pill.last_received_at" class="fermentation-period">
      Ultima comunicazione:
      <time :datetime="pill.last_received_at">{{
        dates.format(new Date(pill.last_received_at))
      }}</time>
    </p>
  </section>
</template>
