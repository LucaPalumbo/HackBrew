<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { capabilityNames, modeNames } from './thermalDevices'
import type { Capability, ThermalDevice } from './thermalDevices'
import { useLatestRequest } from './useLatestRequest'

const emit = defineEmits<{ select: [identifier: string] }>()
const devices = ref<ThermalDevice[]>([])
const loaded = ref(false)
const editor = ref(false)
const edited = ref<ThermalDevice | null>(null)
const name = ref('')
const capability = ref<Capability>('heating')
const baseUrl = ref('')
const saving = ref(false)
const checking = ref<string[]>([])
const registrationError = ref('')
const removalError = ref('')
const notice = ref('')
const removal = ref<ThermalDevice | null>(null)
const confirmation = ref<HTMLDialogElement | null>(null)
const nameField = ref<HTMLInputElement | null>(null)
const addButton = ref<HTMLButtonElement | null>(null)
const checkErrors = ref<Record<string, string>>({})
const savedRevisions = new Map<string, number>()
let trigger: HTMLButtonElement | null = null
let controller: AbortController | undefined
const checks = new Set<AbortController>()
let timer: ReturnType<typeof setInterval> | undefined
let disposed = false
const { loading, error, run, refresh, invalidate } = useLatestRequest(
  'Non è stato possibile recuperare i dispositivi termici. Riprova.',
)
const editable = computed(
  () =>
    !edited.value ||
    devices.value.some(
      (device) => device.id === edited.value?.id && device.available,
    ),
)
const removable = computed(() =>
  devices.value.some(
    (device) => device.id === removal.value?.id && device.available,
  ),
)
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const numbers = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 3 })

async function load(background = false) {
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
      for (const device of payload.devices) {
        const previous = devices.value.find((item) => item.id === device.id)
        if (previous && previous.base_url !== device.base_url) {
          savedRevisions.set(
            device.id,
            (savedRevisions.get(device.id) ?? 0) + 1,
          )
          delete checkErrors.value[device.id]
        }
      }
      devices.value = payload.devices
      loaded.value = true
    },
    background,
  )
}
function restoreFocus() {
  void nextTick(() =>
    (trigger?.isConnected ? trigger : addButton.value)?.focus(),
  )
}
function edit(device: ThermalDevice | null, event: MouseEvent) {
  if (saving.value) return
  trigger = event.currentTarget as HTMLButtonElement
  edited.value = device
  name.value = device?.name ?? ''
  capability.value = device?.capability ?? 'heating'
  baseUrl.value = device?.base_url ?? ''
  registrationError.value = ''
  notice.value = ''
  editor.value = true
  void nextTick(() => nameField.value?.focus())
}
function cancelEdit() {
  if (saving.value) return
  editor.value = false
  restoreFocus()
}
function requestRemoval(device: ThermalDevice, event: MouseEvent) {
  if (saving.value) return
  trigger = event.currentTarget as HTMLButtonElement
  removal.value = device
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
function follow(event: MouseEvent, identifier: string) {
  if (
    event.button ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
    return
  event.preventDefault()
  emit('select', identifier)
}
async function submit(removing = false) {
  if (saving.value || (removing && !removal.value)) return
  const failure = removing ? removalError : registrationError
  failure.value = ''
  notice.value = ''
  const identifier = removing ? removal.value?.id : edited.value?.id
  const chosenName = removing ? removal.value?.name : name.value.trim()
  saving.value = true
  invalidate()
  controller = new AbortController()
  const signal = controller.signal
  try {
    const response = await fetch(
      identifier
        ? `/api/thermal-devices/${encodeURIComponent(identifier)}`
        : '/api/thermal-devices',
      {
        method: removing ? 'DELETE' : identifier ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: removing
          ? undefined
          : JSON.stringify({
              name: name.value.trim(),
              base_url: baseUrl.value.trim(),
              ...(!identifier ? { capability: capability.value } : {}),
            }),
        signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
      },
    )
    const payload: { device?: ThermalDevice; detail?: unknown } =
      response.status === 204 ? {} : await response.json()
    if (signal.aborted) return
    if (
      !response.ok ||
      (removing ? response.status !== 204 : !payload.device)
    ) {
      failure.value =
        typeof payload.detail === 'string'
          ? payload.detail
          : 'Controlla nome, funzioni e indirizzo HTTP(S) del dispositivo.'
      if (response.status === 409 || response.status === 404) await load(true)
      return
    }
    notice.value = `Dispositivo “${removing ? chosenName : payload.device?.name}” ${removing ? 'rimosso dal registro' : identifier ? 'aggiornato. Il salvataggio non conferma lo stato fisico' : 'registrato'}.`
    if (identifier) {
      savedRevisions.set(identifier, (savedRevisions.get(identifier) ?? 0) + 1)
      delete checkErrors.value[identifier]
    }
    if (removing) {
      confirmation.value?.close()
      removal.value = null
    } else editor.value = false
    await load(true)
    if (!disposed) restoreFocus()
  } catch {
    if (!signal.aborted)
      failure.value =
        'Non è stato possibile confermare l’operazione. Controlla il registro e il collegamento prima di riprovare.'
  } finally {
    if (!signal.aborted) saving.value = false
  }
}
async function check(device: ThermalDevice) {
  if (checking.value.includes(device.id)) return
  checking.value = [...checking.value, device.id]
  const request = new AbortController()
  const savedRevision = savedRevisions.get(device.id) ?? 0
  checks.add(request)
  try {
    const response = await fetch(
      `/api/thermal-devices/${encodeURIComponent(device.id)}/check`,
      {
        method: 'POST',
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]),
      },
    )
    if (!response.ok) throw new Error('Verification unavailable')
    if (disposed) return
    delete checkErrors.value[device.id]
    await load(true)
  } catch {
    if (!disposed && savedRevision === (savedRevisions.get(device.id) ?? 0))
      checkErrors.value[device.id] =
        'Non è stato possibile completare la verifica. Riprova.'
  } finally {
    checks.delete(request)
    if (!disposed)
      checking.value = checking.value.filter((id) => id !== device.id)
  }
}
function stateLabel(device: ThermalDevice) {
  if (checkErrors.value[device.id] || device.actual_mode === null)
    return 'Stato sconosciuto'
  if (device.verification_status === 'pending')
    return `Ultimo stato rilevato: ${modeNames[device.actual_mode]}`
  return device.actual_mode === 'off'
    ? 'Spento confermato'
    : `${modeNames[device.actual_mode]} confermato`
}
onMounted(() => {
  void load()
  timer = setInterval(() => {
    if (!saving.value) refresh(() => load(true))
  }, 1500)
})
onUnmounted(() => {
  disposed = true
  clearInterval(timer)
  controller?.abort()
  checks.forEach((request) => request.abort())
})
</script>

<template>
  <section class="thermal-registry" aria-label="Dispositivi termici">
    <div class="pill-registry-heading">
      <p>
        {{
          loaded
            ? `${devices.length} ${devices.length === 1 ? 'dispositivo termico' : 'dispositivi termici'} nel registro`
            : 'Il registro dei tuoi dispositivi termici'
        }}
      </p>
      <button
        ref="addButton"
        type="button"
        class="refresh"
        :disabled="saving || loading"
        @click="edit(null, $event)"
      >
        <span aria-hidden="true">＋ </span>Aggiungi dispositivo termico
      </button>
    </div>
    <button class="text-button" :disabled="loading || saving" @click="load()">
      Aggiorna dispositivi termici
    </button>
    <p v-if="loading" role="status">Caricamento dispositivi termici…</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p
      v-if="notice"
      class="operation-notice"
      role="status"
      aria-label="Esito registro termico"
    >
      {{ notice }}
    </p>
    <div class="pill-registry-layout" :class="{ 'pill-with-editor': editor }">
      <div class="pill-card-list">
        <section
          v-for="device in devices"
          :key="device.id"
          class="pill-card thermal-device"
          :aria-label="`Dispositivo termico ${device.name}`"
        >
          <header>
            <span class="pill-symbol" aria-hidden="true">⌁</span>
            <div>
              <h2>{{ device.name }}</h2>
              <p>{{ capabilityNames[device.capability] }}</p>
            </div>
            <span
              class="pill-availability"
              :class="{ 'pill-in-use': !device.available }"
              >{{ device.available ? 'Disponibile' : 'In uso' }}</span
            >
          </header>
          <code class="thermal-address">{{ device.base_url }}</code>
          <p v-if="device.reserved_fermentation_id" class="pill-assignment">
            Riservato a
            <a
              :href="`/?fermentation=${encodeURIComponent(device.reserved_fermentation_id)}`"
              @click="follow($event, device.reserved_fermentation_id)"
              >{{
                device.reserved_fermentation_name ?? 'Fermentazione associata'
              }}</a
            >, anche durante lo spegnimento pendente.
          </p>
          <p v-else class="pill-assignment">
            Pronto per una nuova fermentazione.
          </p>
          <p v-if="device.verification_status === 'unverified'">
            Non verificato
          </p>
          <p v-if="device.verification_status === 'pending'" role="status">
            Conferma fisica in attesa. Il comando richiesto non è ancora
            confermato.
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
            Funzioni riportate:
            {{ capabilityNames[device.reported_capability] }}
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

          <p v-if="checkErrors[device.id]" class="error" role="alert">
            {{ checkErrors[device.id] }}
          </p>
          <footer>
            <button
              class="text-button"
              :disabled="loading || saving || checking.includes(device.id)"
              @click="check(device)"
            >
              {{
                checking.includes(device.id)
                  ? 'Verifica in corso…'
                  : 'Verifica collegamento'
              }}
            </button>
            <button
              class="text-button"
              :disabled="saving || !device.available"
              @click="edit(device, $event)"
            >
              Modifica
            </button>
            <button
              class="text-button pill-remove"
              :disabled="saving || !device.available"
              @click="requestRemoval(device, $event)"
            >
              Rimuovi
            </button>
          </footer>
        </section>
        <section
          v-if="loaded && !loading && !error && !devices.length"
          class="pill-empty"
        >
          <h2>Nessun dispositivo termico registrato.</h2>
          <p>
            Aggiungi un dispositivo per regolare la temperatura delle tue
            fermentazioni.
          </p>
        </section>
      </div>
      <section
        v-if="editor"
        class="pill-editor"
        :aria-label="
          edited
            ? 'Modifica dispositivo termico'
            : 'Registrazione dispositivo termico'
        "
      >
        <header>
          <h2>
            {{ edited ? 'Modifica dispositivo' : 'Registra un dispositivo' }}
          </h2>
          <button
            class="text-button"
            type="button"
            aria-label="Chiudi editor dispositivo termico"
            :disabled="saving"
            @click="cancelEdit"
          >
            ×
          </button>
        </header>
        <form class="fermentation-form" @submit.prevent="submit()">
          <div>
            <label for="thermal-name">Nome del dispositivo termico</label
            ><input
              id="thermal-name"
              ref="nameField"
              v-model="name"
              required
              maxlength="200"
              :disabled="saving"
            />
          </div>
          <div>
            <label for="thermal-capability">Funzioni del dispositivo</label
            ><select
              id="thermal-capability"
              v-model="capability"
              :disabled="saving || !!edited"
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
            <label for="thermal-url">Indirizzo HTTP</label
            ><input
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
          <p class="metric-caption">
            Usa l’indirizzo HTTP(S) raggiungibile dal server, senza credenziali.
            Il salvataggio e la verifica non accendono il dispositivo. Cambiando
            indirizzo occorre verificare il nuovo collegamento.
          </p>
          <p v-if="!editable" class="error">
            Il dispositivo non è più disponibile. Attendi lo spegnimento
            confermato prima di riprovare.
          </p>
          <p v-if="registrationError" class="error" role="alert">
            {{ registrationError }}
          </p>
          <div class="pill-editor-actions">
            <button
              class="refresh"
              type="submit"
              :disabled="saving || !editable"
            >
              {{
                saving
                  ? 'Salvataggio…'
                  : edited
                    ? 'Salva modifiche'
                    : 'Registra dispositivo termico'
              }}</button
            ><button
              class="text-button"
              type="button"
              :disabled="saving"
              @click="cancelEdit"
            >
              Annulla
            </button>
          </div>
        </form>
      </section>
    </div>
    <dialog
      ref="confirmation"
      class="end-confirmation"
      aria-labelledby="thermal-removal-title"
      @cancel.prevent="cancelRemoval"
    >
      <h2 id="thermal-removal-title">Rimuovi dispositivo termico</h2>
      <p>
        Rimuovere “{{ removal?.name }}” dal registro? Le fermentazioni e i
        riferimenti storici saranno conservati.
      </p>
      <p v-if="!removable" class="error">
        Il dispositivo non è più disponibile. Attendi lo spegnimento confermato.
      </p>
      <p v-if="removalError" class="error" role="alert">{{ removalError }}</p>
      <div class="pill-editor-actions">
        <button
          type="button"
          class="text-button"
          :disabled="saving"
          @click="cancelRemoval"
        >
          Annulla</button
        ><button
          type="button"
          class="refresh"
          :disabled="saving || !removable"
          @click="submit(true)"
        >
          {{ saving ? 'Operazione in corso…' : 'Rimuovi dispositivo' }}
        </button>
      </div>
    </dialog>
  </section>
</template>
