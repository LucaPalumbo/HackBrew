<script setup lang="ts">
import { ref } from 'vue'
import type { Fermentation } from './fermentations'
import type { PillSnapshot } from './readings'

const props = defineProps<{
  fermentation: Fermentation | null
  loading: boolean
  pills: PillSnapshot[]
}>()
const emit = defineEmits<{ changed: [] }>()
const name = ref('')
const pillId = ref('')
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
            ? JSON.stringify({ name: name.value.trim(), pill_id: pillId.value })
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
    emit('changed')
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
    <form v-else class="fermentation-form" @submit.prevent="submit('start')">
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
        <label for="fermentation-pill">Pillola della fermentazione</label>
        <select
          id="fermentation-pill"
          v-model="pillId"
          required
          :disabled="saving || loading || !pills.length"
        >
          <option disabled value="">Scegli una pillola</option>
          <option v-for="pill in pills" :key="pill.id" :value="pill.id">
            {{ pill.name }} · {{ pill.mac }}
          </option>
        </select>
        <p v-if="!pills.length" class="metric-caption">
          Registra prima una pillola nella pagina Dispositivi.
        </p>
      </div>
      <button
        class="refresh"
        type="submit"
        :disabled="saving || loading || !pills.length"
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
