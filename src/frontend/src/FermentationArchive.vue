<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import FermentationCard from './FermentationCard.vue'
import type { FermentationSummary } from './fermentations'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{
  recoveryRevision: number
  revision: number
}>()
const emit = defineEmits<{ select: [identifier: string | null] }>()
const entries = ref<FermentationSummary[]>([])
const query = new URLSearchParams(window.location.search)
const search = ref(query.get('q') ?? '')
const appliedSearch = ref(search.value)
const initialOffset = Number(query.get('offset') ?? 0)
const offset = ref(
  Number.isSafeInteger(initialOffset) && initialOffset >= 0 ? initialOffset : 0,
)
const requestedOffset = ref(offset.value)
const nextOffset = ref<number | null>(null)
const { loading, error, run, refresh } = useLatestRequest(
  'Non è stato possibile recuperare le fermentazioni.',
)

async function load(target = 0, background = false) {
  requestedOffset.value = target
  await run(
    async (signal) => {
      const query = new URLSearchParams({
        q: appliedSearch.value,
        status: 'concluded',
        limit: '20',
        offset: String(target),
      })
      const response = await fetch(`/api/fermentations?${query}`, {
        cache: 'no-store',
        signal,
      })
      if (!response.ok) throw new Error('Archive unavailable')
      const payload: {
        fermentations: FermentationSummary[]
        next_offset: number | null
      } = await response.json()
      return payload
    },
    (payload) => {
      entries.value = payload.fermentations
      nextOffset.value = payload.next_offset
      offset.value = target
      const url = new URL(window.location.href)
      if (appliedSearch.value) url.searchParams.set('q', appliedSearch.value)
      else url.searchParams.delete('q')
      if (target) url.searchParams.set('offset', String(target))
      else url.searchParams.delete('offset')
      window.history.replaceState(window.history.state, '', url)
    },
    background,
  )
}
function searchByName() {
  appliedSearch.value = search.value.trim()
  void load(0)
}
onMounted(() => {
  void load(offset.value)
})
watch(
  () => [props.recoveryRevision, props.revision] as const,
  () => {
    refresh(() => load(requestedOffset.value, true))
  },
)
</script>

<template>
  <section class="archive" aria-label="Fermentazioni">
    <h2>Fermentazioni concluse</h2>
    <form class="archive-search" @submit.prevent="searchByName">
      <label for="history-search">Cerca per nome</label>
      <input
        id="history-search"
        v-model="search"
        type="search"
        maxlength="200"
        placeholder="Nome della fermentazione"
      />
      <button class="text-button" type="submit" :disabled="loading">
        Cerca fermentazioni
      </button>
    </form>
    <p v-if="error" class="error" role="alert">
      {{ error }}
      <button class="text-button" type="button" @click="load(requestedOffset)">
        Riprova elenco
      </button>
    </p>
    <p v-if="loading" role="status">Caricamento fermentazioni…</p>
    <p v-else-if="!error && !entries.length" class="history-period">
      {{
        appliedSearch
          ? 'Nessuna fermentazione corrisponde alla ricerca.'
          : 'Nessuna fermentazione conclusa. Le birre in corso sono nella Home.'
      }}
    </p>
    <ul v-if="entries.length" class="home-cards archive-cards">
      <li v-for="entry in entries" :key="entry.id">
        <FermentationCard
          :fermentation="entry"
          @select="emit('select', $event)"
        />
      </li>
    </ul>
    <div v-if="offset || nextOffset !== null" class="history-navigation">
      <button
        type="button"
        class="text-button"
        :disabled="loading || !offset"
        @click="load(Math.max(0, offset - 20))"
      >
        Fermentazioni più recenti</button
      ><button
        type="button"
        class="text-button"
        :disabled="loading || nextOffset === null"
        @click="load(nextOffset ?? 0)"
      >
        Altre fermentazioni
      </button>
    </div>
  </section>
</template>
