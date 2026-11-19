<script setup lang="ts">
import { nextTick, ref } from 'vue'
import ThermalRegulationStatus from './ThermalRegulationStatus.vue'
import type { Fermentation } from './fermentations'

const props = defineProps<{
  fermentation: Fermentation
  loading: boolean
}>()
const emit = defineEmits<{ changed: [fermentation: Fermentation] }>()
const saving = ref(false)
const confirmation = ref<HTMLDialogElement | null>(null)
const endButton = ref<HTMLButtonElement | null>(null)
const confirming = ref(false)
function requestEnd() {
  confirming.value = true
  error.value = ''
  void nextTick(() => confirmation.value?.showModal())
}
function cancelEnd() {
  if (saving.value) return
  confirmation.value?.close()
  confirming.value = false
  endButton.value?.focus()
}
const error = ref('')
const notice = ref('')
const dateFormat = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})

async function endFermentation() {
  if (saving.value) return
  error.value = ''
  notice.value = ''
  saving.value = true
  try {
    const response = await fetch(
      `/api/fermentations/${props.fermentation.id}/end`,
      {
        method: 'POST',
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
    notice.value = `Fermentazione “${payload.fermentation.name}” conclusa.`
    confirmation.value?.close()
    confirming.value = false
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
    <div class="fermentation-active">
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
        ref="endButton"
        class="refresh"
        type="button"
        :disabled="saving || loading"
        @click="requestEnd"
      >
        {{ saving ? 'Operazione in corso…' : 'Termina fermentazione' }}
      </button>
    </div>
    <dialog
      ref="confirmation"
      class="end-confirmation"
      aria-labelledby="end-confirmation-title"
      @cancel.prevent="cancelEnd"
    >
      <h2 id="end-confirmation-title">Concludi la fermentazione</h2>
      <p>Vuoi terminare definitivamente “{{ fermentation.name }}”?</p>
      <p>
        Il termine è definitivo. Le letture e la configurazione restano
        consultabili.
      </p>
      <p v-if="fermentation.control_mode !== 'monitor_only'">
        Verrà richiesto lo spegnimento di tutti i dispositivi associati. Ogni
        dispositivo resta riservato fino alla conferma dello spegnimento.
      </p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="confirmation-actions">
        <button
          type="button"
          class="text-button"
          autofocus
          :disabled="saving"
          @click="cancelEnd"
        >
          Annulla
        </button>
        <button
          type="button"
          class="refresh"
          :disabled="saving"
          @click="endFermentation"
        >
          {{ saving ? 'Operazione in corso…' : 'Conferma termine' }}
        </button>
      </div>
    </dialog>
    <ThermalRegulationStatus :fermentation="fermentation" />
    <p v-if="error && !confirming" class="error" role="alert">{{ error }}</p>
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
