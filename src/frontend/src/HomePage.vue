<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FermentationCard from './FermentationCard.vue'
import { pillCommunication, type CommunicationClock } from './communication'
import type { FermentationSummary } from './fermentations'
import type { PillSnapshot } from './readings'
import { useLatestRequest } from './useLatestRequest'
const props = defineProps<{
  ready: boolean
  loading: boolean
  error: string
  active: FermentationSummary[]
  pills: PillSnapshot[]
  revision: number
  clock: CommunicationClock | null
  connected: boolean
}>()
defineEmits<{ select: [id: string]; retry: [] }>()
const recent = ref<FermentationSummary[]>([])
const loaded = ref(false)
const entries = computed(() =>
  props.active.length ? props.active : recent.value,
)
const {
  loading: recentLoading,
  error: recentError,
  run,
  refresh,
  invalidate,
} = useLatestRequest(
  'Non è stato possibile recuperare le fermentazioni recenti. Riprova.',
)
async function loadRecent() {
  await run(
    async (signal) => {
      const response = await fetch(
        '/api/fermentations?status=concluded&limit=3',
        { signal, cache: 'no-store' },
      )
      if (!response.ok) throw new Error('Recent fermentations unavailable')
      return (await response.json()) as { fermentations: FermentationSummary[] }
    },
    (payload) => {
      recent.value = payload.fermentations
      loaded.value = true
    },
    loaded.value,
  )
}
watch(
  () => [props.ready, props.active.length, props.revision],
  () => {
    if (!props.ready || props.active.length) {
      invalidate()
      recent.value = []
      loaded.value = false
      return
    }
    refresh(loadRecent)
  },
  { immediate: true },
)
</script>
<template>
  <div class="page-heading">
    <p class="eyebrow">Panoramica</p>
    <h1>Il tuo birrificio, a colpo d’occhio.</h1>
    <p class="description">
      {{
        active.length
          ? 'Le tue birre stanno prendendo forma. Ecco come procede.'
          : 'Ritrova le tue ultime birre o prepara una nuova fermentazione.'
      }}
    </p>
  </div>
  <p v-if="error" class="error" role="alert">
    {{ error }}
    <button class="text-button" @click="$emit('retry')">Riprova</button>
  </p>
  <p v-if="!ready" role="status">
    {{
      loading
        ? 'Caricamento fermentazioni…'
        : 'Stato delle fermentazioni non disponibile.'
    }}
  </p>
  <section v-else aria-label="Fermentazioni">
    <p v-if="recentError" class="error" role="alert">
      {{ recentError }}
      <button type="button" class="text-button" @click="loadRecent">
        Riprova fermentazioni recenti
      </button>
    </p>
    <template v-if="entries.length"
      ><div class="home-summary">
        <div>
          <strong>{{ active.length }}</strong
          ><span>fermentazioni attive</span>
        </div>
        <div>
          <strong>{{ pills.length }}</strong
          ><span>pillole registrate</span>
        </div>
        <a href="/?page=archive">Apri archivio →</a>
      </div>
      <div class="home-section-heading">
        <h2>
          {{ active.length ? 'In fermentazione' : 'Le ultime fermentazioni' }}
        </h2>
        <span
          >{{ entries.length }}
          {{ entries.length === 1 ? 'birra' : 'birre' }}</span
        >
      </div>
      <ul class="home-cards">
        <li v-for="cycle in entries" :key="cycle.id">
          <FermentationCard
            :fermentation="cycle"
            :communication="
              pillCommunication(
                pills.find((pill) => pill.id === cycle.pill_id),
                clock,
                connected,
              )
            "
            @select="$emit('select', $event)"
          />
        </li></ul
    ></template>
    <p v-else-if="recentLoading || (!loaded && !recentError)" role="status">
      Caricamento fermentazioni…
    </p>
    <div v-else-if="!error && !recentError" class="home-empty">
      <p class="eyebrow">Il tuo birrificio è pronto</p>
      <h2>Inizia dalla prima fermentazione.</h2>
      <p>
        {{
          pills.length
            ? 'Scegli una pillola disponibile, un nome e segui la tua birra da qui.'
            : 'Registra una pillola, scegli un nome e segui la tua birra da qui.'
        }}
      </p>
      <div class="empty-actions">
        <a href="/?page=devices">Gestisci dispositivi</a
        ><a href="/?page=new">Nuova fermentazione</a>
      </div>
    </div>
  </section>
</template>
