<script setup lang="ts">
// Three throwaway information architectures, on the existing route. No real mutations.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  active,
  addReading,
  completed,
  current,
  date,
  navigate,
  restoreUrl,
  scenario,
  state,
  switchVariant,
  variantNames,
  type Cycle,
} from './demo'
import VariantA from './VariantA.vue'
import VariantB from './VariantB.vue'
import VariantC from './VariantC.vue'
import CycleCard from './CycleCard.vue'
import DetailMetrics from './DetailMetrics.vue'
import ProtoIcon from './ProtoIcon.vue'
import PrototypeChart from './PrototypeChart.vue'
import PrototypeForms from './PrototypeForms.vue'
import RawReadings from './RawReadings.vue'
import './prototype.css'
const layouts = { A: VariantA, B: VariantB, C: VariantC }
const search = ref('')
const sort = ref('newest')
const homeCycles = computed(() =>
  active.value.length ? active.value : completed.value.slice(0, 3),
)
const archive = computed(() =>
  completed.value
    .filter((cycle) =>
      cycle.name.toLowerCase().includes(search.value.toLowerCase()),
    )
    .sort((a, b) =>
      sort.value === 'name'
        ? a.name.localeCompare(b.name)
        : (b.end ?? 0) - (a.end ?? 0),
    ),
)
const heading = computed(() =>
  state.variant === 'B'
    ? 'La birra, giorno dopo giorno.'
    : state.variant === 'C'
      ? 'Stato delle fermentazioni'
      : 'Il tuo birrificio, a colpo d’occhio.',
)
const warning = computed(() => active.value.find((cycle) => cycle.stale))
function key(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (
    state.raw ||
    target.closest(
      'input, textarea, select, [contenteditable], [role="slider"]',
    ) ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey
  )
    return
  if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
    event.preventDefault()
    switchVariant(event.key === 'ArrowRight' ? 1 : -1)
  }
}
function openCycle(cycle: Cycle) {
  navigate('detail', cycle.id)
}
onMounted(() => {
  window.addEventListener('keydown', key)
  window.addEventListener('popstate', restoreUrl)
})
onUnmounted(() => {
  window.removeEventListener('keydown', key)
  window.removeEventListener('popstate', restoreUrl)
})
</script>
<template>
  <div class="ui-prototype" :class="`p-variant-${state.variant.toLowerCase()}`">
    <component :is="layouts[state.variant]">
      <div v-if="state.notice" class="p-notice" role="status">
        <span>{{ state.notice }}</span
        ><button
          class="p-icon-button"
          aria-label="Chiudi messaggio"
          @click="state.notice = ''"
        >
          <ProtoIcon name="close" />
        </button>
      </div>
      <template v-if="state.page === 'home'">
        <div class="p-page-heading">
          <div>
            <span class="p-overline">{{
              state.variant === 'B' ? 'BENVENUTO NEL TUO DIARIO' : 'PANORAMICA'
            }}</span>
            <h1>{{ heading }}</h1>
            <p>
              {{
                active.length
                  ? 'Le tue birre stanno prendendo forma. Ecco come procede.'
                  : completed.length
                    ? 'Una pausa tra una birra e la prossima. Ritrova le ultime fermentazioni.'
                    : 'La prossima buona birra comincia da qui.'
              }}
            </p>
          </div>
          <span v-if="state.variant === 'C'" class="p-live-label"
            ><span class="p-dot" />Anteprima in tempo reale</span
          >
        </div>
        <div v-if="warning" class="p-alert">
          <span class="p-alert-mark">!</span>
          <div>
            <strong>{{ warning.name }} richiede attenzione</strong
            ><span
              >Pillola non raggiungibile · regolazione sospesa, spegnimento da
              verificare.</span
            >
          </div>
          <button @click="openCycle(warning)">
            Controlla <ProtoIcon name="arrow" />
          </button>
        </div>
        <template v-if="homeCycles.length">
          <template v-if="state.variant === 'A'"
            ><div class="p-summary-strip">
              <div>
                <strong>{{ active.length }}</strong
                ><span>fermentazioni attive</span>
              </div>
              <div>
                <strong>{{
                  state.devices.filter((device) => device.type === 'pill')
                    .length
                }}</strong
                ><span>pillole registrate</span>
              </div>
              <div>
                <strong>{{ completed.length }}</strong
                ><span>birre nell’archivio</span
                ><button class="p-text-button" @click="navigate('archive')">
                  Apri archivio <ProtoIcon name="arrow" />
                </button>
              </div>
            </div>
            <div class="p-section-heading">
              <h2>
                {{
                  active.length ? 'In fermentazione' : 'Le ultime fermentazioni'
                }}
              </h2>
              <span
                >{{ homeCycles.length }}
                {{ homeCycles.length === 1 ? 'birra' : 'birre' }}</span
              >
            </div>
            <div class="p-cycle-grid">
              <CycleCard
                v-for="cycle in homeCycles"
                :key="cycle.id"
                :cycle="cycle"
              /></div
          ></template>
          <template v-else-if="state.variant === 'B'"
            ><div class="p-section-heading">
              <h2>
                {{ active.length ? 'Storie in corso' : 'Le ultime dal diario' }}
              </h2>
              <span>{{ homeCycles.length }} fermentazioni</span>
            </div>
            <div class="p-journal-home">
              <div class="p-journal-feature">
                <CycleCard :cycle="homeCycles[0]!" prominent />
                <div class="p-journal-note">
                  <span>DAL PRIMO GIORNO ALL’ULTIMO SORSO</span>
                  <p>
                    Segui ogni cambiamento.<br />Ritrova ogni fermentazione.
                  </p>
                  <button class="p-text-button" @click="navigate('archive')">
                    Sfoglia l’archivio <ProtoIcon name="arrow" />
                  </button>
                </div>
              </div>
              <div class="p-journal-others">
                <CycleCard
                  v-for="cycle in homeCycles.slice(1)"
                  :key="cycle.id"
                  :cycle="cycle"
                /><button class="p-new-card" @click="navigate('new')">
                  <ProtoIcon name="plus" /><span
                    >La prossima storia<br /><strong
                      >Nuova fermentazione</strong
                    ></span
                  >
                </button>
              </div>
            </div></template
          >
          <template v-else
            ><div class="p-monitor-stats">
              <div>
                <span>ATTIVE</span
                ><strong>{{
                  active.length.toString().padStart(2, '0')
                }}</strong>
              </div>
              <div>
                <span>DA CONTROLLARE</span
                ><strong class="p-warn-number">{{
                  warning ? '01' : '00'
                }}</strong>
              </div>
              <button @click="navigate('archive')">
                <span>NELL’ARCHIVIO</span
                ><strong>{{
                  completed.length.toString().padStart(2, '0')
                }}</strong
                ><ProtoIcon name="arrow" />
              </button>
            </div>
            <div class="p-section-heading">
              <h2>
                {{
                  active.length ? 'Monitoraggio attivo' : 'Ultime fermentazioni'
                }}
              </h2>
              <span>{{ homeCycles.length }} risultati</span>
            </div>
            <div class="p-monitor-list">
              <CycleCard
                v-for="cycle in homeCycles"
                :key="cycle.id"
                :cycle="cycle"
              /></div
          ></template>
        </template>
        <div v-else class="p-empty">
          <span class="p-empty-icon"><ProtoIcon name="beer" /></span
          ><span class="p-overline">IL TUO BIRRIFICIO È PRONTO</span>
          <h2>Inizia dalla prima fermentazione.</h2>
          <p>
            Registra una pillola, scegli un nome e segui la tua birra da qui.
          </p>
          <div class="p-actions">
            <button @click="navigate('devices')">Gestisci dispositivi</button
            ><button class="p-primary" @click="navigate('new')">
              Nuova fermentazione <ProtoIcon name="arrow" />
            </button>
          </div>
        </div>
      </template>
      <template v-else-if="state.page === 'archive'">
        <div class="p-page-heading">
          <div>
            <span class="p-overline">TUTTE LE TUE BIRRE</span>
            <h1>
              {{
                state.variant === 'B'
                  ? 'Il diario delle fermentazioni.'
                  : 'Archivio'
              }}
            </h1>
            <p>Fermentazioni concluse, con i loro dati e la loro storia.</p>
          </div>
          <span class="p-count">{{ completed.length }} fermentazioni</span>
        </div>
        <div class="p-archive-tools">
          <label class="p-search"
            >Cerca fermentazione<input
              v-model="search"
              type="search"
              placeholder="Cerca per nome…" /></label
          ><label
            >Ordina per<select v-model="sort">
              <option value="newest">Più recenti</option>
              <option value="name">Nome A–Z</option>
            </select></label
          >
        </div>
        <div
          class="p-archive-list"
          :class="state.variant === 'C' ? 'p-monitor-list' : 'p-cycle-grid'"
        >
          <CycleCard v-for="cycle in archive" :key="cycle.id" :cycle="cycle" />
        </div>
        <div v-if="!archive.length" class="p-empty">
          <h2>
            {{
              search
                ? 'Nessuna fermentazione trovata'
                : 'Le tue birre, presto qui.'
            }}
          </h2>
          <p>
            {{
              search
                ? 'Prova con un altro nome.'
                : 'Le fermentazioni concluse compariranno in questa pagina.'
            }}
          </p>
          <button v-if="!search" class="p-primary" @click="navigate('new')">
            Nuova fermentazione
          </button>
        </div>
      </template>
      <template v-else-if="state.page === 'detail' && current">
        <button
          class="p-back"
          @click="navigate(current.end ? 'archive' : 'home')"
        >
          <ProtoIcon name="back" />{{
            current.end ? 'Torna all’archivio' : 'Tutte le fermentazioni attive'
          }}
        </button>
        <div class="p-page-heading p-detail-heading">
          <div>
            <div class="p-detail-eyebrow">
              <span class="p-overline">FERMENTAZIONE</span
              ><span
                class="p-status"
                :class="{ 'p-warning': current.stale && !current.end }"
                >{{
                  current.end
                    ? 'Conclusa'
                    : current.stale
                      ? 'Regolazione sospesa'
                      : 'In corso'
                }}</span
              >
            </div>
            <h1>{{ current.name }}</h1>
            <p>
              {{ date(current.start) }}
              {{ current.end ? `— ${date(current.end)}` : '→ in corso' }}
            </p>
          </div>
          <button class="p-outline" @click="state.raw = true">
            <ProtoIcon name="download" />Dati grezzi e CSV
          </button>
        </div>
        <div class="p-tabs" role="tablist" aria-label="Dettaglio fermentazione">
          <button
            role="tab"
            :aria-selected="state.tab === 'trend'"
            @click="state.tab = 'trend'"
          >
            Andamento</button
          ><button
            role="tab"
            :aria-selected="state.tab === 'management'"
            @click="state.tab = 'management'"
          >
            Gestione
          </button>
        </div>
        <div v-if="state.tab === 'trend'" class="p-detail-layout">
          <DetailMetrics /><PrototypeChart />
          <div v-if="!current.end" class="p-reading-action">
            <span
              >Dati dimostrativi · ultima lettura, controlli e collegamenti
              simulati.</span
            ><button @click="addReading">Simula nuova lettura</button>
          </div>
        </div>
        <PrototypeForms v-else :key="current.id" />
      </template>
      <template v-else-if="state.page === 'diagnostic'"
        ><button class="p-back" @click="navigate('devices')">
          <ProtoIcon name="back" />Torna alle pillole
        </button>
        <div class="p-page-heading">
          <div>
            <span class="p-overline">PILLOLA LIBERA · DIAGNOSTICA</span>
            <h1>{{ current?.name }}</h1>
            <p>
              Ultime letture ricevute, anche senza una fermentazione associata.
            </p>
          </div>
        </div>
        <div class="p-detail-layout"><DetailMetrics /><PrototypeChart /></div
      ></template>
      <div v-else-if="state.page === 'detail'" class="p-empty">
        <h2>Questa fermentazione demo non è disponibile.</h2>
        <p>Ricaricando la pagina, le modifiche locali vengono azzerate.</p>
        <button class="p-primary" @click="navigate('home')">
          Torna alla Home
        </button>
      </div>
      <PrototypeForms v-else :key="state.page" />
      <div class="p-prototype-context">
        <span
          >Anteprima {{ state.variant }} · {{ variantNames[state.variant] }} ·
          {{
            state.page === 'detail'
              ? `${current?.name} / ${state.tab === 'trend' ? 'Andamento' : 'Gestione'}`
              : state.page
          }}<br /><small
            >{{ active.length }} attive · {{ completed.length }} concluse ·
            modifiche solo in memoria</small
          ></span
        ><label
          >Scenario Home<select
            aria-label="Scenario Home"
            :value="state.scenario"
            @change="scenario(($event.target as HTMLSelectElement).value)"
          >
            <option value="active">Fermentazioni attive</option>
            <option value="archive">Solo concluse</option>
            <option value="empty">Primo avvio</option>
          </select></label
        >
      </div>
    </component>
    <RawReadings v-if="state.raw" />
    <div class="p-prototype-switcher" aria-label="Confronta i prototipi">
      <button aria-label="Prototipo precedente" @click="switchVariant(-1)">
        ←
      </button>
      <div>
        <span>CONFRONTA LE PROPOSTE</span
        ><strong
          >{{ state.variant }} · {{ variantNames[state.variant] }}</strong
        >
      </div>
      <button aria-label="Prototipo successivo" @click="switchVariant(1)">
        →
      </button>
    </div>
  </div>
</template>
