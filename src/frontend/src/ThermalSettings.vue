<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { Fermentation, ThermalSettingsEntry } from './fermentations'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{ fermentation: Fermentation }>()
const emit = defineEmits<{ changed: [] }>()
const saved = ref(props.fermentation)
const history = ref<ThermalSettingsEntry[]>([])
const minimum = ref('')
const maximum = ref('')
const hysteresis = ref('')
const draftRevision = ref(0)
const dirty = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
let controller: AbortController | undefined
onUnmounted(() => controller?.abort())
const conflict = computed(
  () =>
    dirty.value &&
    draftRevision.value !== saved.value.thermal_settings_revision,
)
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const numbers = new Intl.NumberFormat('it-IT', { maximumSignificantDigits: 15 })

function resetDraft() {
  minimum.value = String(saved.value.temperature_min)
  maximum.value = String(saved.value.temperature_max)
  hysteresis.value = String(saved.value.hysteresis)
  draftRevision.value = saved.value.thermal_settings_revision ?? 0
  dirty.value = false
}
function acceptSnapshot(cycle: Fermentation) {
  if (
    (saved.value.status === 'concluded' && cycle.status === 'active') ||
    (cycle.thermal_settings_revision ?? 0) <
      (saved.value.thermal_settings_revision ?? 0)
  )
    return false
  saved.value = cycle
  if (!dirty.value && !saving.value) resetDraft()
  return true
}
const {
  loading,
  error: historyError,
  run,
  refresh,
} = useLatestRequest(
  'Non è stato possibile recuperare la cronologia delle impostazioni. Riprova.',
)
async function loadHistory() {
  return run(
    async (signal) => {
      const response = await fetch(
        `/api/fermentations/${encodeURIComponent(props.fermentation.id)}/thermal-settings/history`,
        { signal, cache: 'no-store' },
      )
      if (!response.ok) throw new Error('Settings history unavailable')
      return (await response.json()) as {
        fermentation: Fermentation
        history: ThermalSettingsEntry[]
      }
    },
    (payload) => {
      if (acceptSnapshot(payload.fermentation)) history.value = payload.history
    },
  )
}
watch(
  () => props.fermentation,
  (cycle, previous) => {
    acceptSnapshot(cycle)
    if (
      !previous ||
      cycle.thermal_settings_revision !== previous.thermal_settings_revision ||
      cycle.status !== previous.status
    )
      refresh(loadHistory)
  },
  { immediate: true },
)

async function reloadSaved() {
  if (await loadHistory()) {
    resetDraft()
    error.value = ''
    notice.value = ''
  }
}
async function submit() {
  error.value = ''
  notice.value = ''
  const low = Number(minimum.value),
    high = Number(maximum.value),
    margin = Number(hysteresis.value)
  if (
    ![minimum.value, maximum.value, hysteresis.value].every((value) =>
      String(value).trim(),
    ) ||
    ![low, high, margin].every(Number.isFinite) ||
    low < -273.15 ||
    low >= high ||
    margin <= 0 ||
    low + margin > high
  ) {
    error.value =
      'Minimo inferiore al massimo, isteresi positiva e spegnimento entro la fascia richiesti.'
    return
  }
  if (saving.value || saved.value.status !== 'active') return
  saving.value = true
  controller = new AbortController()
  const signal = controller.signal
  try {
    const response = await fetch(
      `/api/fermentations/${encodeURIComponent(saved.value.id)}/thermal-settings`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
        body: JSON.stringify({
          expected_revision: draftRevision.value,
          temperature_min: low,
          temperature_max: high,
          hysteresis: margin,
        }),
      },
    )
    const payload: { fermentation?: Fermentation; detail?: unknown } =
      await response.json()
    if (signal.aborted) return
    if (!response.ok || !payload.fermentation) {
      error.value =
        typeof payload.detail === 'string'
          ? payload.detail
          : 'Salvataggio non confermato. Controlla i valori salvati e riprova.'
      await loadHistory()
      return
    }
    if (acceptSnapshot(payload.fermentation)) {
      resetDraft()
      notice.value =
        'Impostazioni salvate. La conferma dei dispositivi è mostrata nella regolazione.'
    } else {
      error.value =
        'Esiste una revisione più recente o la fermentazione è conclusa. Controlla i valori salvati.'
    }
    emit('changed')
    await loadHistory()
  } catch {
    if (!signal.aborted)
      error.value =
        'Salvataggio non confermato. Controlla il collegamento e i valori salvati prima di riprovare.'
  } finally {
    if (!signal.aborted) saving.value = false
  }
}
</script>

<template>
  <section class="thermal-status" aria-label="Impostazioni termiche">
    <h3>Impostazioni termiche</h3>
    <p aria-label="Valori termici salvati">
      Revisione {{ saved.thermal_settings_revision }} · Fascia:
      {{ numbers.format(saved.temperature_min!) }}–{{
        numbers.format(saved.temperature_max!)
      }}
      °C · Isteresi: {{ numbers.format(saved.hysteresis!) }} °C
    </p>
    <form
      v-if="saved.status === 'active'"
      class="fermentation-form"
      @submit.prevent="submit"
    >
      <div>
        <label for="edit-temperature-min">Nuova temperatura minima (°C)</label>
        <input
          id="edit-temperature-min"
          v-model="minimum"
          type="number"
          step="any"
          required
          :disabled="saving"
          @input="dirty = true"
        />
      </div>
      <div>
        <label for="edit-temperature-max">Nuova temperatura massima (°C)</label>
        <input
          id="edit-temperature-max"
          v-model="maximum"
          type="number"
          step="any"
          required
          :disabled="saving"
          @input="dirty = true"
        />
      </div>
      <div>
        <label for="edit-hysteresis">Nuova isteresi (°C)</label>
        <input
          id="edit-hysteresis"
          v-model="hysteresis"
          type="number"
          step="any"
          required
          :disabled="saving"
          @input="dirty = true"
        />
      </div>
      <button class="refresh" type="submit" :disabled="saving">
        {{ saving ? 'Salvataggio…' : 'Salva impostazioni termiche' }}
      </button>
      <button
        class="text-button"
        type="button"
        :disabled="saving"
        @click="reloadSaved"
      >
        Carica impostazioni salvate
      </button>
    </form>
    <p v-if="conflict" class="error" role="alert">
      Le impostazioni sono cambiate durante la modifica. La bozza è conservata;
      carica i valori salvati prima di riprovare.
    </p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p
      v-if="notice"
      class="operation-notice"
      role="status"
      aria-label="Esito impostazioni"
    >
      {{ notice }}
    </p>
    <p v-if="loading" role="status">Caricamento cronologia…</p>
    <p v-if="historyError" class="error" role="alert">
      {{ historyError }}
      <button class="text-button" type="button" @click="loadHistory">
        Riprova cronologia
      </button>
    </p>
    <div
      v-if="history.length"
      class="readings-table"
      tabindex="0"
      aria-label="Scorri la cronologia delle impostazioni"
    >
      <table aria-label="Cronologia impostazioni termiche">
        <thead>
          <tr>
            <th scope="col">Revisione</th>
            <th scope="col">Salvata il</th>
            <th scope="col">Minimo °C</th>
            <th scope="col">Massimo °C</th>
            <th scope="col">Isteresi °C</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in history" :key="entry.revision">
            <th scope="row">
              {{ entry.revision
              }}{{ entry.revision === 0 ? ' · Iniziale' : '' }}
            </th>
            <td>
              <time :datetime="entry.changed_at">{{
                dates.format(new Date(entry.changed_at))
              }}</time>
            </td>
            <td>{{ numbers.format(entry.temperature_min) }}</td>
            <td>{{ numbers.format(entry.temperature_max) }}</td>
            <td>{{ numbers.format(entry.hysteresis) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
