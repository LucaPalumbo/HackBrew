<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import HeatingStatus from './HeatingStatus.vue'
import type { Fermentation } from './fermentations'
import type { PillSnapshot } from './readings'
import type { ThermalDevice } from './thermalDevices'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{
  fermentation: Fermentation | null
  loading: boolean
  pills: PillSnapshot[]
  allowStart?: boolean
}>()
const emit = defineEmits<{ changed: [fermentation: Fermentation] }>()
const name = ref('')
const pillId = ref('')
const mode = ref('monitor_only')
const heaterId = ref('')
const minimum = ref('18')
const maximum = ref('22')
const hysteresis = ref('0.5')
const heaters = ref<ThermalDevice[]>([])
const {
  error: heaterError,
  run: readHeaters,
  refresh: refreshHeaters,
} = useLatestRequest(
  'Non è stato possibile recuperare i dispositivi di riscaldamento. Riprova.',
)
let heaterTimer: ReturnType<typeof setInterval> | undefined
async function loadHeaters() {
  await readHeaters(
    async (signal) => {
      const response = await fetch('/api/thermal-devices', {
        signal,
        cache: 'no-store',
      })
      if (!response.ok) throw new Error('Heaters unavailable')
      return (await response.json()) as { devices: ThermalDevice[] }
    },
    (payload) => {
      heaters.value = payload.devices.filter(
        (device) => device.capability === 'heating',
      )
    },
    true,
  )
}
onMounted(() => {
  if (props.fermentation && !props.allowStart) return
  void loadHeaters()
  heaterTimer = setInterval(() => refreshHeaters(loadHeaters), 2000)
})
onUnmounted(() => clearInterval(heaterTimer))
const availablePills = computed(() =>
  props.pills.filter((pill) => pill.available),
)
watch(
  () => props.pills,
  () => {
    if (!availablePills.value.some((pill) => pill.id === pillId.value))
      pillId.value = ''
  },
)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const dateFormat = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})

async function submit(action: 'start' | 'end') {
  error.value = ''
  notice.value = ''
  if (action === 'start' && !name.value.trim()) {
    error.value = 'Inserisci un nome per la fermentazione.'
    return
  }
  const current = props.fermentation
  if (action === 'end' && !current) return
  saving.value = true
  try {
    const response = await fetch(
      action === 'start'
        ? '/api/fermentations'
        : `/api/fermentations/${current?.id}/end`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body:
          action === 'start'
            ? JSON.stringify({
                name: name.value.trim(),
                pill_id: pillId.value,
                control_mode: mode.value,
                ...(mode.value === 'heating'
                  ? {
                      heater_id: heaterId.value,
                      temperature_min: Number(minimum.value),
                      temperature_max: Number(maximum.value),
                      hysteresis: Number(hysteresis.value),
                    }
                  : {}),
              })
            : undefined,
        signal: AbortSignal.timeout(10000),
      },
    )
    const payload: { fermentation?: Fermentation; detail?: unknown } =
      await response.json()
    if (!response.ok || !payload.fermentation) {
      error.value =
        typeof payload.detail === 'string'
          ? payload.detail
          : 'Non è stato possibile confermare l’operazione. Riprova.'
      return
    }
    notice.value = `Fermentazione “${payload.fermentation.name}” ${action === 'start' ? 'avviata' : 'conclusa'}.`
    if (action === 'start') name.value = ''
    emit('changed', payload.fermentation)
  } catch {
    error.value =
      'Non è stato possibile confermare l’operazione. Controlla il collegamento e riprova.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="fermentation-panel" aria-label="Gestione fermentazione">
    <div v-if="fermentation" class="fermentation-active">
      <div>
        <p class="eyebrow">Fermentazione attiva</p>
        <h2>{{ fermentation.name }}</h2>
        <p class="fermentation-period">
          In corso · Avviata
          <time :datetime="fermentation.started_at">{{
            dateFormat.format(new Date(fermentation.started_at))
          }}</time>
        </p>
        <p class="fermentation-period">
          {{ fermentation.pill_name }} · {{ fermentation.pill_mac }}
        </p>
      </div>
      <button
        class="refresh"
        type="button"
        :disabled="saving || loading"
        @click="submit('end')"
      >
        {{ saving ? 'Operazione in corso…' : 'Termina fermentazione' }}
      </button>
    </div>
    <HeatingStatus v-if="fermentation" :fermentation="fermentation" />
    <form
      v-if="!fermentation || allowStart"
      class="fermentation-form"
      @submit.prevent="submit('start')"
    >
      <div>
        <p class="eyebrow">Un nuovo inizio</p>
        <h2>Avvia una fermentazione</h2>
        <label for="fermentation-name">Nome della fermentazione</label>
        <input
          id="fermentation-name"
          v-model="name"
          name="fermentation-name"
          autocomplete="off"
          required
          :disabled="saving || loading"
          placeholder="Es. Prima IPA"
        />
      </div>
      <div>
        <label for="fermentation-mode">Modalità della fermentazione</label>
        <select
          id="fermentation-mode"
          v-model="mode"
          :disabled="saving || loading"
        >
          <option value="monitor_only">Solo monitoraggio</option>
          <option value="heating">Riscaldamento</option>
          <option disabled value="cooling">
            Raffreddamento (non ancora disponibile)
          </option>
          <option disabled value="combined">
            Combinazioni (non ancora disponibili)
          </option>
        </select>
      </div>
      <template v-if="mode === 'heating'">
        <div>
          <label for="fermentation-heater">Dispositivo di riscaldamento</label>
          <select
            id="fermentation-heater"
            v-model="heaterId"
            required
            :disabled="saving || loading"
          >
            <option disabled value="">Scegli un dispositivo</option>
            <option
              v-for="heater in heaters"
              :key="heater.id"
              :value="heater.id"
              :disabled="!heater.available"
            >
              {{ heater.name }}{{ heater.available ? '' : ' · Riservato' }}
            </option>
          </select>
          <p v-if="heaterError" role="alert" class="error">
            {{ heaterError }}
            <button type="button" class="text-button" @click="loadHeaters">
              Riprova dispositivi
            </button>
          </p>
          <p
            v-else-if="!heaters.some((heater) => heater.available)"
            class="metric-caption"
          >
            Registra un dispositivo di solo riscaldamento disponibile nella
            pagina Dispositivi.
          </p>
        </div>
        <div>
          <label for="temperature-min">Temperatura minima (°C)</label>
          <input
            id="temperature-min"
            v-model="minimum"
            type="number"
            step="any"
            required
            :disabled="saving || loading"
          />
        </div>
        <div>
          <label for="temperature-max">Temperatura massima (°C)</label>
          <input
            id="temperature-max"
            v-model="maximum"
            type="number"
            step="any"
            required
            :disabled="saving || loading"
          />
        </div>
        <div>
          <label for="temperature-hysteresis">Isteresi (°C)</label>
          <input
            id="temperature-hysteresis"
            v-model="hysteresis"
            type="number"
            step="any"
            required
            :disabled="saving || loading"
          />
        </div>
      </template>
      <div>
        <label for="fermentation-pill">Pillola della fermentazione</label>
        <select
          id="fermentation-pill"
          v-model="pillId"
          required
          :disabled="saving || loading || !availablePills.length"
        >
          <option disabled value="">Scegli una pillola</option>
          <option
            v-for="pill in pills"
            :key="pill.id"
            :value="pill.id"
            :disabled="!pill.available"
          >
            {{ pill.name }} · {{ pill.mac
            }}{{ pill.available ? '' : ' · Occupata' }}
          </option>
        </select>
        <p v-if="!pills.length" class="metric-caption">
          Registra prima una pillola nella pagina Dispositivi.
        </p>
        <p v-else-if="!availablePills.length" class="metric-caption">
          Tutte le pillole sono già assegnate a fermentazioni attive.
        </p>
      </div>
      <button
        class="refresh"
        type="submit"
        :disabled="saving || loading || !availablePills.length"
      >
        {{ saving ? 'Operazione in corso…' : 'Avvia fermentazione' }}
      </button>
    </form>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p
      v-if="notice"
      class="operation-notice"
      role="status"
      aria-label="Esito operazione"
    >
      {{ notice }}
    </p>
  </section>
</template>
