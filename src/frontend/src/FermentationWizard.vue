<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  controlModeNames,
  type Fermentation,
  type ThermalAssignment,
} from './fermentations'
import type { PillSnapshot } from './readings'
import type { Capability, ThermalDevice } from './thermalDevices'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{ pills: PillSnapshot[]; loading: boolean }>()
const emit = defineEmits<{
  created: [fermentation: Fermentation]
  cancelled: []
  refresh: []
}>()
type Role = ThermalAssignment['role']
type ControlMode = Fermentation['control_mode']
const roles: Record<Role, { label: string; capability: Capability }> = {
  heater: { label: 'Dispositivo di riscaldamento', capability: 'heating' },
  cooler: { label: 'Dispositivo di raffreddamento', capability: 'cooling' },
  combined: { label: 'Dispositivo combinato', capability: 'both' },
}
const modeRoles: Record<ControlMode, Role[]> = {
  monitor_only: [],
  heating: ['heater'],
  cooling: ['cooler'],
  heating_cooling: ['heater', 'cooler'],
  combined: ['combined'],
}
const step = ref(1)
const titles = ['Nome e pillola', 'Regolazione', 'Riepilogo']
const heading = ref<HTMLElement | null>(null)
const name = ref('')
const pillId = ref('')
const mode = ref<ControlMode>('monitor_only')
const equipment = reactive<Record<Role, string>>({
  heater: '',
  cooler: '',
  combined: '',
})
const minimum = ref<number | string>('18')
const maximum = ref<number | string>('22')
const hysteresis = ref<number | string>('0.5')
const thermalDevices = ref<ThermalDevice[]>([])
const requiredRoles = computed(() => modeRoles[mode.value])
const availablePills = computed(() =>
  props.pills.filter((pill) => pill.available),
)
const selectedPill = computed(() =>
  props.pills.find((pill) => pill.id === pillId.value),
)
function deviceFor(role: Role) {
  return thermalDevices.value.find((device) => device.id === equipment[role])
}
function choicesFor(role: Role) {
  return thermalDevices.value.filter(
    (device) =>
      device.capability === roles[role].capability &&
      (device.available || device.id === equipment[role]),
  )
}
const {
  error: devicesError,
  run,
  refresh,
} = useLatestRequest(
  'Non è stato possibile recuperare i dispositivi termici. Riprova.',
)
async function loadDevices() {
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
      thermalDevices.value = payload.devices
    },
    true,
  )
}
function refreshAvailability() {
  emit('refresh')
  void loadDevices()
}
let timer: ReturnType<typeof setInterval> | undefined
let controller: AbortController | undefined
onMounted(() => {
  void loadDevices()
  timer = setInterval(() => refresh(loadDevices), 2000)
})
onUnmounted(() => {
  clearInterval(timer)
  controller?.abort()
})
const saving = ref(false)
const error = ref('')
function focusStep() {
  void nextTick(() => heading.value?.focus())
}
function validateIdentity() {
  if (!name.value.trim()) {
    error.value = 'Inserisci un nome per la fermentazione.'
    return false
  }
  if (!selectedPill.value?.available) {
    error.value = 'Scegli una pillola libera per la fermentazione.'
    return false
  }
  return true
}
function validateRegulation() {
  if (mode.value === 'monitor_only') return true
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
    return false
  }
  if (
    requiredRoles.value.some((role) => {
      const device = deviceFor(role)
      return !device?.available || device.capability !== roles[role].capability
    })
  ) {
    error.value =
      'Scegli dispositivi compatibili e disponibili per la regolazione.'
    return false
  }
  return true
}
function next() {
  if (saving.value) return
  error.value = ''
  if (step.value === 1 ? !validateIdentity() : !validateRegulation()) return
  step.value += 1
  focusStep()
}
function previous() {
  if (saving.value) return
  error.value = ''
  step.value -= 1
  focusStep()
}
function responseError(detail: unknown) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item: unknown) =>
      item &&
      typeof item === 'object' &&
      'msg' in item &&
      typeof item.msg === 'string'
        ? [item.msg]
        : [],
    )
    if (messages.length) return messages.join(' ')
  }
  return 'Non è stato possibile confermare l’avvio. Controlla la Home e riprova.'
}
async function start() {
  if (saving.value || step.value !== 3) return
  error.value = ''
  if (!validateIdentity() || !validateRegulation()) return
  saving.value = true
  controller = new AbortController()
  const signal = controller.signal
  try {
    const response = await fetch('/api/fermentations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
      body: JSON.stringify({
        name: name.value.trim(),
        pill_id: pillId.value,
        control_mode: mode.value,
        ...(mode.value !== 'monitor_only'
          ? {
              ...Object.fromEntries(
                requiredRoles.value.map((role) => [
                  `${role}_id`,
                  equipment[role],
                ]),
              ),
              temperature_min: Number(minimum.value),
              temperature_max: Number(maximum.value),
              hysteresis: Number(hysteresis.value),
            }
          : {}),
      }),
    })
    const payload: { fermentation?: Fermentation; detail?: unknown } =
      await response.json()
    if (signal.aborted) return
    if (!response.ok || !payload.fermentation) {
      error.value = responseError(payload.detail)
      if (response.status === 409 || response.status === 404)
        refreshAvailability()
      return
    }
    emit('created', payload.fermentation)
  } catch {
    if (!signal.aborted)
      error.value =
        'Non è stato possibile confermare l’avvio. Controlla la Home e il collegamento prima di riprovare.'
  } finally {
    if (!signal.aborted) saving.value = false
  }
}
</script>

<template>
  <section class="fermentation-wizard" aria-label="Nuova fermentazione guidata">
    <ol class="wizard-steps" aria-label="Passaggi della fermentazione">
      <li
        v-for="(title, index) in titles"
        :key="title"
        :aria-current="step === index + 1 ? 'step' : undefined"
        :class="{ 'wizard-step-done': step > index + 1 }"
      >
        <span aria-hidden="true">{{ step > index + 1 ? '✓' : index + 1 }}</span
        >{{ title }}
      </li>
    </ol>
    <form
      class="wizard-panel"
      novalidate
      @submit.prevent="step === 3 ? start() : next()"
    >
      <p class="eyebrow">Passaggio {{ step }} di 3</p>
      <h2 ref="heading" tabindex="-1">{{ titles[step - 1] }}</h2>
      <div v-if="step === 1" class="wizard-fields">
        <div>
          <label for="fermentation-name">Nome della fermentazione</label>
          <input
            id="fermentation-name"
            v-model="name"
            required
            autocomplete="off"
            placeholder="Es. Prima IPA"
            :disabled="saving || loading"
          />
        </div>
        <div>
          <label for="fermentation-pill">Pillola della fermentazione</label>
          <select
            id="fermentation-pill"
            v-model="pillId"
            required
            :disabled="saving || loading || !availablePills.length"
          >
            <option disabled value="">Scegli una pillola libera</option>
            <option
              v-if="selectedPill && !selectedPill.available"
              :value="selectedPill.id"
              disabled
            >
              {{ selectedPill.name }} · Occupata
            </option>
            <option
              v-for="pill in availablePills"
              :key="pill.id"
              :value="pill.id"
            >
              {{ pill.name }} · {{ pill.mac }}
            </option>
          </select>
          <p v-if="!pills.length">
            Registra prima una pillola nella pagina Dispositivi.
          </p>
          <p v-else-if="!availablePills.length">
            Tutte le pillole sono già assegnate a fermentazioni attive.
          </p>
          <p v-if="!availablePills.length">
            <a href="/?page=devices">Gestisci dispositivi</a>
          </p>
        </div>
        <p>La pillola verrà riservata soltanto all’avvio.</p>
      </div>
      <div v-else-if="step === 2" class="wizard-fields">
        <div>
          <label for="fermentation-mode">Modalità della fermentazione</label>
          <select
            id="fermentation-mode"
            v-model="mode"
            :disabled="saving || loading"
          >
            <option
              v-for="(label, value) in controlModeNames"
              :key="value"
              :value="value"
            >
              {{ label }}
            </option>
          </select>
        </div>
        <p v-if="mode === 'monitor_only'">
          Solo monitoraggio: non servono dispositivi termici o soglie di
          temperatura.
        </p>
        <template v-else>
          <p v-if="devicesError" class="error" role="alert">
            {{ devicesError }}
            <button type="button" class="text-button" @click="loadDevices">
              Riprova dispositivi
            </button>
          </p>
          <div v-for="role in requiredRoles" :key="role">
            <label :for="`fermentation-${role}`">{{ roles[role].label }}</label>
            <select
              :id="`fermentation-${role}`"
              v-model="equipment[role]"
              required
              :disabled="saving || loading"
            >
              <option disabled value="">Scegli un dispositivo libero</option>
              <option
                v-for="device in choicesFor(role)"
                :key="device.id"
                :value="device.id"
                :disabled="!device.available"
              >
                {{ device.name }}{{ device.available ? '' : ' · Riservato' }}
              </option>
            </select>
            <p v-if="!choicesFor(role).some((device) => device.available)">
              Registra un dispositivo compatibile disponibile nella pagina
              Dispositivi.
            </p>
          </div>
          <div class="wizard-thresholds">
            <div>
              <label for="temperature-min">Temperatura minima (°C)</label
              ><input
                id="temperature-min"
                v-model="minimum"
                required
                type="number"
                step="any"
                :disabled="saving || loading"
              />
            </div>
            <div>
              <label for="temperature-max">Temperatura massima (°C)</label
              ><input
                id="temperature-max"
                v-model="maximum"
                required
                type="number"
                step="any"
                :disabled="saving || loading"
              />
            </div>
            <div>
              <label for="temperature-hysteresis">Isteresi (°C)</label
              ><input
                id="temperature-hysteresis"
                v-model="hysteresis"
                required
                type="number"
                step="any"
                :disabled="saving || loading"
              />
            </div>
          </div>
        </template>
      </div>
      <section
        v-else
        aria-label="Riepilogo della fermentazione"
        class="wizard-summary"
      >
        <p>Controlla le scelte prima di avviare la fermentazione.</p>
        <dl>
          <div>
            <dt>Nome</dt>
            <dd>{{ name.trim() }}</dd>
          </div>
          <div>
            <dt>Pillola</dt>
            <dd>
              {{ selectedPill?.name ?? 'Non disponibile' }} ·
              {{ selectedPill?.mac }}
            </dd>
          </div>
          <div>
            <dt>Regolazione</dt>
            <dd>{{ controlModeNames[mode] }}</dd>
          </div>
          <div v-for="role in requiredRoles" :key="role">
            <dt>{{ roles[role].label }}</dt>
            <dd>
              {{ deviceFor(role)?.name ?? 'Non disponibile'
              }}<span v-if="!deviceFor(role)?.available">
                · Non disponibile</span
              >
            </dd>
          </div>
          <template v-if="mode !== 'monitor_only'"
            ><div>
              <dt>Fascia di temperatura</dt>
              <dd>{{ minimum }}–{{ maximum }} °C</dd>
            </div>
            <div>
              <dt>Isteresi</dt>
              <dd>{{ hysteresis }} °C</dd>
            </div></template
          >
        </dl>
        <p>
          La disponibilità verrà verificata nuovamente dal server all’avvio.
        </p>
      </section>
      <p v-if="pillId && !selectedPill?.available" role="status" class="error">
        La pillola scelta non è più disponibile. Torna al primo passaggio per
        cambiarla.
      </p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button
        v-if="error && step === 3"
        type="button"
        class="text-button"
        :disabled="saving"
        @click="refreshAvailability"
      >
        Ricarica disponibilità
      </button>
      <div class="wizard-actions">
        <button
          type="button"
          class="text-button"
          :disabled="saving"
          @click="emit('cancelled')"
        >
          Annulla
        </button>
        <button
          v-if="step > 1"
          type="button"
          class="text-button"
          :disabled="saving || loading"
          @click="previous"
        >
          Indietro
        </button>
        <button
          v-if="step < 3"
          type="submit"
          class="refresh"
          :disabled="
            saving || loading || (step === 1 && !availablePills.length)
          "
        >
          Avanti
        </button>
        <button
          v-else
          type="submit"
          class="refresh"
          :disabled="saving || loading"
        >
          {{ saving ? 'Avvio in corso…' : 'Avvia fermentazione' }}
        </button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.fermentation-wizard {
  max-width: 840px;
  margin: 0 auto;
}
.wizard-steps {
  display: flex;
  gap: 20px;
  list-style: none;
  padding: 0;
  margin: 0 0 28px;
}
.wizard-steps li {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #74828b;
  font-size: 12px;
  flex: 1;
}
.wizard-steps li > span {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: 1px solid #dce3e7;
  border-radius: 50%;
  background: white;
}
.wizard-steps [aria-current] {
  color: #215a61;
  font-weight: 650;
}
.wizard-steps [aria-current] > span,
.wizard-steps .wizard-step-done > span {
  background: #215a61;
  border-color: #215a61;
  color: white;
}
.wizard-panel {
  padding: 32px;
  background: white;
  border: 1px solid #e0e6e9;
  border-radius: 10px;
}
.wizard-panel h2 {
  font-size: 24px;
  margin: 0 0 28px;
}
.wizard-panel h2:focus {
  outline: none;
}
.wizard-fields {
  display: grid;
  gap: 24px;
}
.wizard-panel label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
}
.wizard-panel input,
.wizard-panel select {
  width: 100%;
  min-width: 0;
  padding: 12px;
  border: 1px solid #c9d4da;
  border-radius: 6px;
  background: white;
  color: #20313b;
  font: inherit;
}
.wizard-panel input:disabled,
.wizard-panel select:disabled {
  background: #f5f6f8;
}
.wizard-panel p {
  font-size: 13px;
  line-height: 1.7;
  color: #627580;
}
.wizard-panel .error {
  color: #a23434;
}
.wizard-thresholds {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.wizard-summary dl {
  margin: 24px 0;
}
.wizard-summary dl > div {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid #e0e6e9;
  font-size: 14px;
}
.wizard-summary dt {
  color: #627580;
}
.wizard-summary dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.wizard-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #e0e6e9;
}
.wizard-actions > :first-child {
  margin-right: auto;
}
.wizard-actions button {
  min-height: 44px;
  padding: 10px 16px;
}
@media (max-width: 600px) {
  .wizard-steps {
    gap: 8px;
    margin-bottom: 22px;
  }
  .wizard-steps li {
    flex-direction: column;
    gap: 8px;
    text-align: center;
    font-size: 10px;
  }
  .wizard-panel {
    padding: 22px 18px;
  }
  .wizard-panel h2 {
    font-size: 22px;
  }
  .wizard-thresholds {
    grid-template-columns: 1fr;
  }
  .wizard-summary dl > div {
    grid-template-columns: 1fr;
    gap: 6px;
  }
  .wizard-actions {
    gap: 8px;
  }
  .wizard-actions button {
    padding: 10px;
    font-size: 12px;
  }
}
</style>
