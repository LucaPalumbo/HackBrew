<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import {
  active,
  current,
  date,
  demoNow,
  deviceName,
  free,
  latest,
  modes,
  navigate,
  owner,
  state,
  type Cycle,
  type Device,
} from './demo'
import ProtoIcon from './ProtoIcon.vue'
function previousStep() {
  step.value--
  formError.value = ''
}
function deviceTab(tab: string) {
  state.deviceTab = tab
  editing.value = false
}
function checkDevice(device: Device) {
  device.pending = false
  state.notice =
    'Verifica simulata: collegamento riuscito, funzioni corrispondenti e dispositivo spento.'
}
function saveTimeout() {
  state.timeout = timeout.value
  state.notice = `Timeout demo impostato a ${timeout.value} ore. I dispositivi non raggiungibili restano in attesa di sincronizzazione.`
}
const step = ref(1)
const draft = reactive({
  name: '',
  pill: '',
  mode: modes[0]!,
  heat: '',
  cool: '',
  both: '',
  min: 19,
  max: 20,
  hysteresis: 0.3,
})
const draftEquipment = computed(() =>
  draft.mode === modes[0]
    ? []
    : draft.mode === modes[1]
      ? [draft.heat]
      : draft.mode === modes[2]
        ? [draft.cool]
        : draft.mode === modes[3]
          ? [draft.heat, draft.cool]
          : [draft.both],
)
const formError = ref('')
function next() {
  formError.value = ''
  if (
    step.value === 1 &&
    (!draft.name.trim() ||
      !state.devices.some((device) => device.id === draft.pill && free(device)))
  ) {
    formError.value = 'Inserisci il nome e scegli una pillola libera.'
    return
  }
  if (
    step.value === 2 &&
    draft.mode !== modes[0] &&
    (draftEquipment.value.some((id) => !id) ||
      draft.min >= draft.max ||
      draft.hysteresis <= 0 ||
      draft.hysteresis >= draft.max - draft.min)
  ) {
    formError.value =
      'Scegli i dispositivi. La minima deve precedere la massima e l’isteresi deve essere positiva e inferiore alla loro differenza.'
    return
  }
  step.value++
}
function create() {
  const sample = latest(
    state.cycles[0] ??
      ({
        samples: [
          {
            time: demoNow,
            temperature: 19.2,
            gravity: 1.052,
            battery: 88,
            velocity: null,
            accel_x: 0.1,
            accel_y: 0.02,
            accel_z: 0.97,
          },
        ],
      } as Cycle),
  )
  const cycle: Cycle = {
    id: `demo-${Date.now()}`,
    name: draft.name.trim(),
    start: demoNow,
    end: null,
    pill: draft.pill,
    mode: draft.mode,
    equipment: [...draftEquipment.value],
    min: draft.min,
    max: draft.max,
    hysteresis: draft.hysteresis,
    stale: false,
    history: ['Fermentazione avviata nel prototipo.'],
    samples: [
      { ...sample, time: demoNow },
      { ...sample, time: demoNow + 60000 },
    ],
  }
  state.cycles.unshift(cycle)
  state.notice = 'Fermentazione creata solo in questa anteprima.'
  navigate('detail', cycle.id)
}
const edited = ref<Device | null>(null)
const deviceDraft = reactive({ name: '', address: '', type: 'pill' })
const editing = ref(false)
const deleteId = ref('')
function edit(device?: Device) {
  edited.value = device ?? null
  editing.value = true
  Object.assign(
    deviceDraft,
    device ?? {
      name: '',
      address: '',
      type: state.deviceTab === 'pill' ? 'pill' : 'heating',
    },
  )
  formError.value = ''
}
function saveDevice() {
  formError.value = ''
  if (!deviceDraft.name.trim() || !deviceDraft.address.trim()) {
    formError.value = 'Inserisci nome e indirizzo.'
    return
  }
  if (
    deviceDraft.type === 'pill' &&
    !/^([\dA-F]{2}:){5}[\dA-F]{2}$/i.test(deviceDraft.address)
  ) {
    formError.value = 'Usa un MAC Bluetooth nel formato AA:BB:CC:DD:EE:FF.'
    return
  }
  if (
    deviceDraft.type !== 'pill' &&
    !/^https?:\/\/[^\s]+$/.test(deviceDraft.address)
  ) {
    formError.value = 'Inserisci un indirizzo HTTP o HTTPS.'
    return
  }
  if (
    !edited.value &&
    state.devices.some(
      (device) =>
        device.address.toLowerCase() === deviceDraft.address.toLowerCase(),
    )
  ) {
    formError.value = 'Questo dispositivo è già registrato.'
    return
  }
  if (edited.value) {
    edited.value.name = deviceDraft.name.trim()
    if (free(edited.value) && edited.value.type !== 'pill')
      edited.value.address = deviceDraft.address
  } else
    state.devices.push({
      id: `device-${Date.now()}`,
      ...deviceDraft,
      name: deviceDraft.name.trim(),
      pending: false,
    })
  editing.value = false
  state.notice = 'Registro dimostrativo aggiornato.'
}
function removeDevice(device: Device) {
  if (free(device)) {
    state.retired.push({ ...device })
    state.devices = state.devices.filter((item) => item.id !== device.id)
    deleteId.value = ''
    state.notice =
      'Dispositivo rimosso dal registro demo. Lo storico delle fermentazioni è conservato.'
  }
}
const displayedDevices = computed(() =>
  state.devices.filter((device) =>
    state.deviceTab === 'pill'
      ? device.type === 'pill'
      : device.type !== 'pill',
  ),
)
const typeLabels: Record<string, string> = {
  pill: 'Pillola Bluetooth',
  heating: 'Riscaldamento',
  cooling: 'Raffreddamento',
  both: 'Riscaldamento e raffreddamento',
}
const timeout = ref(state.timeout)
const thermal = reactive({
  min: current.value?.min ?? 19,
  max: current.value?.max ?? 20,
  hysteresis: current.value?.hysteresis ?? 0.3,
})
const ending = ref(false)
function saveThermal() {
  if (!current.value) return
  if (
    thermal.min >= thermal.max ||
    thermal.hysteresis <= 0 ||
    thermal.hysteresis >= thermal.max - thermal.min
  ) {
    formError.value = 'Controlla minima, massima e isteresi.'
    return
  }
  Object.assign(current.value, thermal)
  current.value.history.unshift(
    `Soglie aggiornate: ${thermal.min}–${thermal.max} °C · isteresi ${thermal.hysteresis} °C`,
  )
  formError.value = ''
  state.notice = 'Soglie aggiornate nella demo.'
}
function end() {
  if (!current.value) return
  const cycle = current.value
  cycle.end = latest(cycle).time
  if (cycle.stale)
    cycle.equipment.forEach((id) => {
      const device = state.devices.find((item) => item.id === id)
      if (device) device.pending = true
    })
  ending.value = false
  state.notice = cycle.stale
    ? 'Fermentazione conclusa nella demo. Spegnimento da confermare: i dispositivi termici restano riservati.'
    : 'Fermentazione conclusa nella demo. Spegnimento simulato confermato.'
}
</script>
<template>
  <template v-if="state.page === 'new'">
    <div class="p-page-heading">
      <div>
        <span class="p-overline">UN NUOVO INIZIO</span>
        <h1>Nuova fermentazione</h1>
        <p>Prepara tutto, poi lascia che la birra faccia il suo corso.</p>
      </div>
    </div>
    <ol class="p-wizard-steps">
      <li
        v-for="(label, index) in [
          'Birra e pillola',
          'Regolazione',
          'Riepilogo',
        ]"
        :key="label"
        :class="{
          'p-step-current': step === index + 1,
          'p-step-done': step > index + 1,
        }"
      >
        <span>{{ step > index + 1 ? '✓' : index + 1 }}</span
        >{{ label }}
      </li>
    </ol>
    <form
      class="p-panel p-wizard"
      @submit.prevent="step < 3 ? next() : create()"
    >
      <template v-if="step === 1"
        ><span class="p-overline">PASSAGGIO 1 DI 3</span>
        <h2>Quale birra stai preparando?</h2>
        <label
          >Nome della fermentazione<input
            v-model="draft.name"
            placeholder="Es. West Coast IPA"
            required
            maxlength="80" /></label
        ><label
          >Pillola da associare<select
            v-model="draft.pill"
            aria-label="Pillola da associare"
            required
          >
            <option value="" disabled>Scegli una pillola libera</option>
            <option
              v-for="device in state.devices.filter(
                (item) => item.type === 'pill' && free(item),
              )"
              :key="device.id"
              :value="device.id"
            >
              {{ device.name }} · {{ device.address }}
            </option>
          </select></label
        >
        <p class="p-help">
          La pillola sarà riservata fino al termine della fermentazione.
        </p>
        <button
          v-if="
            !state.devices.some((item) => item.type === 'pill' && free(item))
          "
          type="button"
          class="p-text-button"
          @click="navigate('devices')"
        >
          Registra prima una pillola <ProtoIcon name="arrow" /></button
      ></template>
      <template v-else-if="step === 2"
        ><span class="p-overline">PASSAGGIO 2 DI 3</span>
        <h2>Come vuoi seguirla?</h2>
        <label
          >Modalità<select v-model="draft.mode" aria-label="Modalità">
            <option v-for="mode in modes" :key="mode">{{ mode }}</option>
          </select></label
        >
        <p v-if="draft.mode === modes[0]" class="p-info">
          Seguirai tutte le letture della pillola. Non servono dispositivi
          termici o soglie di temperatura.
        </p>
        <template v-else
          ><label v-if="draft.mode === modes[1] || draft.mode === modes[3]"
            >Dispositivo di riscaldamento<select
              v-model="draft.heat"
              aria-label="Dispositivo di riscaldamento"
              required
            >
              <option value="" disabled>Scegli un dispositivo libero</option>
              <option
                v-for="device in state.devices.filter(
                  (item) => item.type === 'heating' && free(item),
                )"
                :key="device.id"
                :value="device.id"
              >
                {{ device.name }}
              </option>
            </select></label
          ><label v-if="draft.mode === modes[2] || draft.mode === modes[3]"
            >Dispositivo di raffreddamento<select
              v-model="draft.cool"
              aria-label="Dispositivo di raffreddamento"
              required
            >
              <option value="" disabled>Scegli un dispositivo libero</option>
              <option
                v-for="device in state.devices.filter(
                  (item) => item.type === 'cooling' && free(item),
                )"
                :key="device.id"
                :value="device.id"
              >
                {{ device.name }}
              </option>
            </select></label
          ><label v-if="draft.mode === modes[4]"
            >Dispositivo combinato<select
              v-model="draft.both"
              aria-label="Dispositivo combinato"
              required
            >
              <option value="" disabled>Scegli un dispositivo libero</option>
              <option
                v-for="device in state.devices.filter(
                  (item) => item.type === 'both' && free(item),
                )"
                :key="device.id"
                :value="device.id"
              >
                {{ device.name }}
              </option>
            </select></label
          >
          <div class="p-form-grid">
            <label
              >Minima (°C)<input
                v-model.number="draft.min"
                type="number"
                step="0.1"
                required /></label
            ><label
              >Massima (°C)<input
                v-model.number="draft.max"
                type="number"
                step="0.1"
                required /></label
            ><label
              >Isteresi (°C)<input
                v-model.number="draft.hysteresis"
                type="number"
                min="0.1"
                step="0.1"
                required
            /></label></div></template
      ></template>
      <template v-else
        ><span class="p-overline">PASSAGGIO 3 DI 3</span>
        <h2>Pronto per {{ draft.name }}?</h2>
        <dl class="p-definition">
          <div>
            <dt>Pillola</dt>
            <dd>{{ deviceName(draft.pill) }}</dd>
          </div>
          <div>
            <dt>Modalità</dt>
            <dd>{{ draft.mode }}</dd>
          </div>
          <template v-if="draft.mode !== modes[0]"
            ><div>
              <dt>Dispositivi</dt>
              <dd>{{ draftEquipment.map(deviceName).join(', ') }}</dd>
            </div>
            <div>
              <dt>Temperatura</dt>
              <dd>
                {{ draft.min }}–{{ draft.max }} °C · isteresi
                {{ draft.hysteresis }} °C
              </dd>
            </div></template
          >
        </dl>
        <p class="p-info">
          L’avvio è manuale. Nella demo questa azione modifica solo i dati di
          anteprima.
        </p></template
      >
      <p v-if="formError" role="alert" class="p-error">{{ formError }}</p>
      <footer class="p-form-footer">
        <button v-if="step > 1" type="button" @click="previousStep">
          Indietro</button
        ><button v-else type="button" @click="navigate('home')">Annulla</button
        ><button class="p-primary" type="submit">
          {{ step < 3 ? 'Continua' : 'Avvia fermentazione'
          }}<ProtoIcon name="arrow" />
        </button>
      </footer>
    </form>
  </template>
  <template v-else-if="state.page === 'devices'">
    <div class="p-page-heading">
      <div>
        <span class="p-overline">IL TUO EQUIPAGGIAMENTO</span>
        <h1>Dispositivi</h1>
        <p>Pillole e controllo termico, ciascuno al proprio posto.</p>
      </div>
      <button class="p-primary" @click="edit()">
        <ProtoIcon name="plus" />{{
          state.deviceTab === 'pill'
            ? 'Aggiungi pillola'
            : 'Aggiungi dispositivo'
        }}
      </button>
    </div>
    <div class="p-tabs" role="tablist" aria-label="Tipo di dispositivo">
      <button
        role="tab"
        :aria-selected="state.deviceTab === 'pill'"
        @click="deviceTab('pill')"
      >
        Pillole
        <span>{{
          state.devices.filter((item) => item.type === 'pill').length
        }}</span></button
      ><button
        role="tab"
        :aria-selected="state.deviceTab === 'thermal'"
        @click="deviceTab('thermal')"
      >
        Dispositivi termici
        <span>{{
          state.devices.filter((item) => item.type !== 'pill').length
        }}</span>
      </button>
    </div>
    <div class="p-devices-layout" :class="{ 'p-with-editor': editing }">
      <div class="p-device-list">
        <article
          v-for="device in displayedDevices"
          :key="device.id"
          class="p-panel p-device"
        >
          <div class="p-device-heading">
            <span class="p-device-symbol"><ProtoIcon name="devices" /></span>
            <div>
              <h2>{{ device.name }}</h2>
              <span class="p-muted">{{ typeLabels[device.type] }}</span>
            </div>
            <span
              class="p-status"
              :class="{ 'p-warning': device.pending || owner(device)?.stale }"
              >{{
                device.pending
                  ? 'Spegnimento da confermare'
                  : owner(device)
                    ? `In uso · ${owner(device)?.name}`
                    : 'Libero'
              }}</span
            >
          </div>
          <code>{{ device.address }}</code>
          <p class="p-help">
            {{
              device.pending
                ? 'Riservato fino alla conferma dello spegnimento.'
                : owner(device)
                  ? 'La configurazione del collegamento è bloccata durante la fermentazione.'
                  : device.type === 'pill'
                    ? 'Pronta per una nuova fermentazione.'
                    : 'Nessuna fermentazione assegnata · spento'
            }}
          </p>
          <div v-if="deleteId === device.id" class="p-info">
            Rimuovere {{ device.name }}? Lo storico verrà conservato.
            <div class="p-actions">
              <button class="p-danger" @click="removeDevice(device)">
                Conferma rimozione</button
              ><button @click="deleteId = ''">Annulla</button>
            </div>
          </div>
          <div v-else class="p-device-actions">
            <button v-if="device.type !== 'pill'" @click="checkDevice(device)">
              Verifica collegamento</button
            ><button
              v-else-if="free(device)"
              @click="navigate('diagnostic', device.id)"
            >
              Esplora letture</button
            ><button
              :disabled="device.type === 'pill' && !free(device)"
              @click="edit(device)"
            >
              Modifica</button
            ><button
              class="p-text-danger"
              :disabled="!free(device)"
              @click="deleteId = device.id"
            >
              Rimuovi
            </button>
          </div>
        </article>
        <div v-if="!displayedDevices.length" class="p-empty">
          <h2>Il registro è vuoto</h2>
          <p>Aggiungi il primo dispositivo per preparare il tuo birrificio.</p>
          <button class="p-primary" @click="edit()">
            Aggiungi dispositivo
          </button>
        </div>
      </div>
      <form
        v-if="editing"
        class="p-panel p-device-editor"
        @submit.prevent="saveDevice"
      >
        <header>
          <h2>
            {{ edited ? 'Modifica' : 'Registra' }}
            {{ state.deviceTab === 'pill' ? 'pillola' : 'dispositivo' }}
          </h2>
          <button
            type="button"
            class="p-icon-button"
            aria-label="Chiudi editor"
            @click="editing = false"
          >
            <ProtoIcon name="close" />
          </button>
        </header>
        <label>Nome<input v-model="deviceDraft.name" required /></label
        ><label v-if="state.deviceTab !== 'pill'"
          >Funzioni<select v-model="deviceDraft.type" :disabled="!!edited">
            <option value="heating">Riscaldamento</option>
            <option value="cooling">Raffreddamento</option>
            <option value="both">Entrambi</option>
          </select></label
        ><label
          >{{
            state.deviceTab === 'pill'
              ? 'MAC Bluetooth'
              : 'Indirizzo del dispositivo'
          }}<input
            v-model="deviceDraft.address"
            :readonly="!!edited && (edited.type === 'pill' || !free(edited))"
            :placeholder="
              state.deviceTab === 'pill'
                ? 'AA:BB:CC:DD:EE:FF'
                : 'http://dispositivo.local'
            "
            required
        /></label>
        <p class="p-help">
          {{
            edited?.type === 'pill'
              ? 'Il MAC identifica la pillola e resta invariato.'
              : edited && !free(edited)
                ? 'L’indirizzo si può cambiare quando il dispositivo è libero.'
                : 'Il collegamento in questa anteprima è simulato.'
          }}
        </p>
        <p v-if="formError" class="p-error" role="alert">{{ formError }}</p>
        <button class="p-primary" type="submit">Salva dispositivo</button>
      </form>
    </div>
  </template>
  <template v-else-if="state.page === 'settings'">
    <div class="p-page-heading">
      <div>
        <span class="p-overline">PREFERENZE GENERALI</span>
        <h1>Impostazioni</h1>
        <p>Le regole comuni al tuo birrificio.</p>
      </div>
    </div>
    <form class="p-panel p-settings" @submit.prevent="saveTimeout">
      <span class="p-overline">COMUNICAZIONE E SICUREZZA</span>
      <h2>Timeout di comunicazione</h2>
      <p>Una sola durata, in entrambe le direzioni.</p>
      <label
        >Dopo quante ore senza comunicazione?
        <div class="p-input-unit">
          <input
            v-model.number="timeout"
            type="number"
            min="0.01"
            step="0.01"
            required
          /><span>ore</span>
        </div></label
      >
      <div class="p-settings-rules">
        <div>
          <ProtoIcon name="devices" />
          <p>
            <strong>Il server non riceve letture</strong
            ><span
              >Invia il comando di spegnimento ai dispositivi dopo
              {{ timeout }} ore.</span
            >
          </p>
        </div>
        <div>
          <ProtoIcon name="clock" />
          <p>
            <strong>Il dispositivo non riceve comandi</strong
            ><span>Si spegne autonomamente dopo lo stesso intervallo.</span>
          </p>
        </div>
      </div>
      <p class="p-help">
        La fermentazione continua. Cambiare questo valore non riaccende i
        dispositivi. La sincronizzazione degli attuatori qui è simulata.
      </p>
      <button class="p-primary" type="submit">Salva impostazioni</button>
      <p class="p-muted">Valore demo salvato: {{ state.timeout }} ore.</p>
    </form>
  </template>
  <template v-else-if="state.page === 'detail' && current">
    <div class="p-management-grid">
      <section class="p-panel">
        <span class="p-overline">CONTROLLO TERMICO</span>
        <h2>Regolazione</h2>
        <p class="p-muted">{{ current.mode }}</p>
        <p v-if="current.mode === modes[0]" class="p-info">
          Questa fermentazione è in solo monitoraggio. Non ci sono soglie o
          attuatori da gestire.
        </p>
        <form v-else @submit.prevent="saveThermal">
          <div class="p-form-grid">
            <label
              >Minima (°C)<input
                v-model.number="thermal.min"
                type="number"
                step="0.1"
                :disabled="!!current.end"
                required /></label
            ><label
              >Massima (°C)<input
                v-model.number="thermal.max"
                type="number"
                step="0.1"
                :disabled="!!current.end"
                required /></label
            ><label
              >Isteresi (°C)<input
                v-model.number="thermal.hysteresis"
                type="number"
                step="0.1"
                min="0.1"
                :disabled="!!current.end"
                required
            /></label>
          </div>
          <p v-if="formError" class="p-error" role="alert">{{ formError }}</p>
          <button v-if="!current.end" class="p-primary" type="submit">
            Aggiorna regolazione
          </button>
          <p v-else class="p-help">
            Fermentazione conclusa: impostazioni consultabili.
          </p>
        </form>
      </section>
      <section class="p-panel">
        <span class="p-overline">ASSOCIAZIONI</span>
        <h2>Equipaggiamento</h2>
        <dl class="p-definition">
          <div>
            <dt>Pillola</dt>
            <dd>{{ deviceName(current.pill) }}</dd>
          </div>
          <div v-for="id in current.equipment" :key="id">
            <dt>Dispositivo termico</dt>
            <dd>
              {{ deviceName(id)
              }}<small>{{
                state.devices.find((item) => item.id === id)?.pending
                  ? 'Spegnimento da confermare'
                  : current.end
                    ? 'Spento'
                    : current.stale
                      ? 'Comunicazione da verificare'
                      : 'Collegato'
              }}</small>
            </dd>
          </div>
          <div>
            <dt>Avvio manuale</dt>
            <dd>{{ date(current.start) }}</dd>
          </div>
          <div v-if="current.end">
            <dt>Termine manuale</dt>
            <dd>{{ date(current.end) }}</dd>
          </div>
        </dl>
        <p class="p-help">
          L’associazione dei dispositivi rimane nello storico.
        </p>
      </section>
      <section class="p-panel">
        <span class="p-overline">STORICO</span>
        <h2>Modifiche alla regolazione</h2>
        <ol class="p-history">
          <li v-for="(event, index) in current.history" :key="index">
            <span class="p-dot" />
            <div>
              {{ event }}<small>{{ date(demoNow) }} · modifica manuale</small>
            </div>
          </li>
        </ol>
      </section>
      <section v-if="!current.end" class="p-panel p-end-panel">
        <span class="p-overline">FINE DEL CICLO</span>
        <h2>Concludi la fermentazione</h2>
        <p>
          Il termine è definitivo. Verrà richiesto lo spegnimento di tutti i
          dispositivi associati.
        </p>
        <div v-if="ending" class="p-info">
          <strong>Concludere {{ current.name }}?</strong>
          <p>
            La fermentazione passerà nell’archivio e non potrà essere riaperta.
          </p>
          <div class="p-actions">
            <button class="p-danger" @click="end">
              Sì, concludi definitivamente</button
            ><button @click="ending = false">Annulla</button>
          </div>
        </div>
        <button v-else class="p-danger" @click="ending = true">
          Concludi fermentazione
        </button>
      </section>
    </div>
    <p class="p-help">
      {{ active.length }} fermentazioni in corso · tutte le azioni sono
      dimostrative.
    </p>
  </template>
</template>
