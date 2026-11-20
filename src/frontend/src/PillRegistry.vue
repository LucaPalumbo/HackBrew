<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
import type { PillSnapshot } from './readings'
import type { FermentationSummary } from './fermentations'
import { pillCommunication, type CommunicationClock } from './communication'

type Identity = Pick<PillSnapshot, 'id' | 'name' | 'mac'>
const props = defineProps<{
  pills: PillSnapshot[]
  active: FermentationSummary[]
  ready: boolean
  loading: boolean
  error: string
  clock: CommunicationClock | null
  connected: boolean
}>()
const emit = defineEmits<{
  changed: []
  diagnostic: [identifier: string]
  select: [identifier: string]
}>()
const editor = ref(false)
const edited = ref<Identity | null>(null)
const name = ref('')
const mac = ref('')
const saving = ref(false)
const editorError = ref('')
const removalError = ref('')
const notice = ref('')
const removal = ref<Identity | null>(null)
const confirmation = ref<HTMLDialogElement | null>(null)
const nameField = ref<HTMLInputElement | null>(null)
const addButton = ref<HTMLButtonElement | null>(null)
let trigger: HTMLButtonElement | null = null
let controller: AbortController | undefined
onUnmounted(() => controller?.abort())
const editable = computed(
  () =>
    !edited.value ||
    props.pills.some((pill) => pill.id === edited.value?.id && pill.available),
)
const removable = computed(() =>
  props.pills.some((pill) => pill.id === removal.value?.id && pill.available),
)
const temperatures = new Intl.NumberFormat('it-IT', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
function cycle(pill: PillSnapshot) {
  return props.active.find((entry) => entry.id === pill.active_fermentation_id)
}
function communication(pill: PillSnapshot) {
  const status = pillCommunication(pill, props.clock, props.connected)
  return {
    unknown: 'Verifica comunicazione…',
    never_received: 'Nessuna comunicazione ricevuta',
    receiving: props.connected
      ? 'Comunicazione entro il timeout'
      : 'Ultima comunicazione confermata',
    timed_out: 'Timeout di comunicazione superato',
    unconfirmed_timeout: 'Ultima comunicazione confermata oltre il timeout',
  }[status]
}
function follow(
  event: MouseEvent,
  action: 'diagnostic' | 'select',
  identifier: string,
) {
  if (
    event.button ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
    return
  event.preventDefault()
  if (action === 'diagnostic') emit('diagnostic', identifier)
  else emit('select', identifier)
}
function edit(pill: PillSnapshot | null, event: MouseEvent) {
  if (saving.value) return
  trigger = event.currentTarget as HTMLButtonElement
  edited.value = pill ? { id: pill.id, name: pill.name, mac: pill.mac } : null
  name.value = pill?.name ?? ''
  mac.value = pill?.mac ?? ''
  editorError.value = ''
  notice.value = ''
  editor.value = true
  void nextTick(() => nameField.value?.focus())
}
function restoreFocus() {
  void nextTick(() =>
    (trigger?.isConnected ? trigger : addButton.value)?.focus(),
  )
}
function cancelEdit() {
  if (saving.value) return
  editor.value = false
  restoreFocus()
}
function requestRemoval(pill: PillSnapshot, event: MouseEvent) {
  if (saving.value) return
  trigger = event.currentTarget as HTMLButtonElement
  removal.value = { id: pill.id, name: pill.name, mac: pill.mac }
  removalError.value = ''
  notice.value = ''
  confirmation.value?.showModal()
}
function cancelRemoval() {
  if (saving.value) return
  confirmation.value?.close()
  removal.value = null
  restoreFocus()
}
function failure(detail: unknown) {
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
  return 'Non è stato possibile confermare l’operazione. Controlla il registro e riprova.'
}
async function submit(action: 'save' | 'remove') {
  if (saving.value) return
  const removing = action === 'remove'
  const error = removing ? removalError : editorError
  error.value = ''
  notice.value = ''
  if (removing && !removal.value) return
  if (!removing && (!name.value.trim() || !mac.value.trim())) {
    error.value = 'Inserisci nome e MAC Bluetooth della pillola.'
    return
  }
  const identifier = removing ? removal.value?.id : edited.value?.id
  const chosenName = removing ? removal.value?.name : name.value.trim()
  saving.value = true
  controller = new AbortController()
  const signal = controller.signal
  try {
    const response = await fetch(
      identifier
        ? `/api/pills/${encodeURIComponent(identifier)}`
        : '/api/pills',
      {
        method: removing ? 'DELETE' : identifier ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: removing
          ? undefined
          : JSON.stringify({
              name: name.value.trim(),
              ...(!identifier ? { mac: mac.value.trim() } : {}),
            }),
        signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
      },
    )
    const payload: { pill?: Identity; detail?: unknown } =
      response.status === 204 ? {} : await response.json()
    if (signal.aborted) return
    if (!response.ok || (removing ? response.status !== 204 : !payload.pill)) {
      error.value = failure(payload.detail)
      if (response.status === 409 || response.status === 404) emit('changed')
      return
    }
    notice.value = `Pillola “${removing ? chosenName : payload.pill?.name}” ${removing ? 'rimossa dal registro' : identifier ? 'rinominata' : 'registrata'}.`
    if (removing) {
      confirmation.value?.close()
      removal.value = null
    } else {
      editor.value = false
    }
    emit('changed')
    restoreFocus()
  } catch {
    if (!signal.aborted)
      error.value =
        'Non è stato possibile confermare l’operazione. Controlla il registro e il collegamento prima di riprovare.'
  } finally {
    if (!signal.aborted) saving.value = false
  }
}
</script>

<template>
  <div class="pill-registry-heading">
    <p>
      {{
        ready
          ? `${pills.length} ${pills.length === 1 ? 'pillola' : 'pillole'} nel registro`
          : 'Il registro delle tue pillole'
      }}
    </p>
    <button
      ref="addButton"
      type="button"
      class="refresh"
      :disabled="saving || loading"
      @click="edit(null, $event)"
    >
      <span aria-hidden="true">＋ </span>Aggiungi pillola
    </button>
  </div>
  <p v-if="error" class="error" role="alert">
    {{ error }}
    <button type="button" class="text-button" @click="emit('changed')">
      Riprova
    </button>
  </p>
  <p
    v-if="notice"
    class="operation-notice"
    role="status"
    aria-label="Esito registro"
  >
    {{ notice }}
  </p>
  <p v-if="loading || (!ready && !error)" role="status">Caricamento pillole…</p>
  <div class="pill-registry-layout" :class="{ 'pill-with-editor': editor }">
    <div class="pill-card-list">
      <section
        v-for="pill in pills"
        :key="pill.id"
        class="pill-card"
        :aria-label="`Pillola ${pill.name}`"
      >
        <header>
          <span class="pill-symbol" aria-hidden="true">◉</span>
          <div>
            <h2>{{ pill.name }}</h2>
            <p>Pillola Bluetooth</p>
          </div>
          <span
            class="pill-availability"
            :class="{ 'pill-in-use': !pill.available }"
            >{{ pill.available ? 'Libera' : 'In uso' }}</span
          >
        </header>
        <code>{{ pill.mac }}</code>
        <p v-if="pill.active_fermentation_id" class="pill-assignment">
          Fermentazione:
          <a
            :href="`/?fermentation=${encodeURIComponent(pill.active_fermentation_id)}`"
            @click="follow($event, 'select', pill.active_fermentation_id)"
            >{{ cycle(pill)?.name ?? 'Fermentazione attiva' }}</a
          >
        </p>
        <p v-else class="pill-assignment">
          Pronta per una nuova fermentazione.
        </p>
        <dl v-if="pill.reading" class="pill-card-metrics">
          <div>
            <dt>Densità <small>SG</small></dt>
            <dd>{{ pill.reading.specific_gravity.toFixed(3) }}</dd>
          </div>
          <div>
            <dt>Temperatura <small>°C</small></dt>
            <dd>{{ temperatures.format(pill.reading.temperature) }}</dd>
          </div>
          <div>
            <dt>Batteria <small>%</small></dt>
            <dd>{{ pill.reading.battery.toFixed(0) }}</dd>
          </div>
        </dl>
        <p v-else class="pill-no-reading">Nessuna lettura ricevuta.</p>
        <p class="pill-communication">
          {{ communication(pill)
          }}<template v-if="pill.last_received_at"
            ><br /><time :datetime="pill.last_received_at">{{
              dates.format(new Date(pill.last_received_at))
            }}</time></template
          >
        </p>
        <footer>
          <a
            v-if="pill.available"
            :href="`/?page=diagnostics&pill=${encodeURIComponent(pill.id)}`"
            @click="follow($event, 'diagnostic', pill.id)"
            >Esplora letture</a
          >
          <button
            type="button"
            class="text-button"
            :disabled="saving || !pill.available"
            @click="edit(pill, $event)"
          >
            Rinomina
          </button>
          <button
            type="button"
            class="text-button pill-remove"
            :disabled="saving || !pill.available"
            @click="requestRemoval(pill, $event)"
          >
            Rimuovi
          </button>
        </footer>
      </section>
      <section
        v-if="ready && !loading && !pills.length && !error"
        class="pill-empty"
      >
        <h2>Il registro è vuoto</h2>
        <p>Aggiungi una pillola per preparare la tua prossima fermentazione.</p>
      </section>
    </div>
    <section
      v-if="editor"
      class="pill-editor"
      :aria-label="edited ? 'Rinomina pillola' : 'Registrazione pillola'"
    >
      <header>
        <h2>{{ edited ? 'Rinomina pillola' : 'Registra una pillola' }}</h2>
        <button
          type="button"
          class="text-button"
          aria-label="Chiudi editor"
          :disabled="saving"
          @click="cancelEdit"
        >
          ×
        </button>
      </header>
      <form novalidate @submit.prevent="submit('save')">
        <div>
          <label for="pill-name">Nome della pillola</label
          ><input
            id="pill-name"
            ref="nameField"
            v-model="name"
            required
            :disabled="saving"
            autocomplete="off"
          />
        </div>
        <div>
          <label for="pill-mac">MAC Bluetooth</label
          ><input
            id="pill-mac"
            v-model="mac"
            required
            :disabled="saving"
            :readonly="!!edited"
            autocapitalize="characters"
            spellcheck="false"
            placeholder="AA:BB:CC:DD:EE:FF"
          />
        </div>
        <p>
          {{
            edited
              ? 'Il MAC identifica la pillola e resta invariato.'
              : 'Usa l’indirizzo Bluetooth della pillola.'
          }}
        </p>
        <p v-if="!editable" class="error" role="status">
          La pillola non è più libera o è stata rimossa. Le modifiche inserite
          sono conservate.
        </p>
        <p v-if="editorError" class="error" role="alert">{{ editorError }}</p>
        <div class="pill-editor-actions">
          <button
            type="button"
            class="text-button"
            :disabled="saving"
            @click="cancelEdit"
          >
            Annulla</button
          ><button
            class="refresh"
            type="submit"
            :disabled="saving || loading || !editable"
          >
            {{
              saving
                ? 'Salvataggio…'
                : edited
                  ? 'Salva nome'
                  : 'Registra pillola'
            }}
          </button>
        </div>
      </form>
    </section>
  </div>
  <dialog
    ref="confirmation"
    class="end-confirmation"
    aria-labelledby="pill-removal-title"
    @cancel.prevent="cancelRemoval"
  >
    <h2 id="pill-removal-title">Rimuovi pillola</h2>
    <p>Rimuovere “{{ removal?.name }}” dal registro operativo?</p>
    <p>
      <code>{{ removal?.mac }}</code>
    </p>
    <p>
      Letture e fermentazioni precedenti rimangono conservate. Una nuova
      registrazione esplicita dello stesso MAC recupererà la stessa identità.
    </p>
    <p v-if="removal && !removable" class="error" role="status">
      La pillola non è più disponibile per la rimozione.
    </p>
    <p v-if="removalError" class="error" role="alert">{{ removalError }}</p>
    <div class="confirmation-actions">
      <button
        type="button"
        class="text-button"
        autofocus
        :disabled="saving"
        @click="cancelRemoval"
      >
        Annulla</button
      ><button
        type="button"
        class="refresh"
        :disabled="saving || !removable"
        @click="submit('remove')"
      >
        {{ saving ? 'Rimozione…' : 'Conferma rimozione' }}
      </button>
    </div>
  </dialog>
</template>
