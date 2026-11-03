<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import type { Fermentation } from './fermentations'
import { useLatestRequest } from './useLatestRequest'

const props = defineProps<{
  selectedId: string | null
  activeId: string | null
  recoveryRevision: number
}>()
const emit = defineEmits<{ select: [identifier: string | null] }>()
const entries = ref<Fermentation[]>([])
const search = ref('')
const appliedSearch = ref('')
const offset = ref(0)
const nextOffset = ref<number | null>(null)
const { loading, error, run } = useLatestRequest(
  'Non è stato possibile recuperare le fermentazioni concluse.',
)
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

async function load(target = 0) {
  await run(
    async (signal) => {
      const query = new URLSearchParams({
        q: appliedSearch.value,
        limit: '20',
        offset: String(target),
      })
      const response = await fetch(`/api/fermentations?${query}`, {
        cache: 'no-store',
        signal,
      })
      if (!response.ok) throw new Error('Archive unavailable')
      const payload: {
        fermentations: Fermentation[]
        next_offset: number | null
      } = await response.json()
      return payload
    },
    (payload) => {
      entries.value = payload.fermentations
      nextOffset.value = payload.next_offset
      offset.value = target
    },
  )
}
function searchByName() {
  appliedSearch.value = search.value.trim()
  void load(0)
}
onMounted(() => {
  void load()
})
watch(
  () => [props.activeId, props.recoveryRevision] as const,
  () => {
    void load(offset.value)
  },
)
</script>

<template>
  <section class="archive" aria-label="Storico fermentazioni">
    <div class="archive-heading">
      <h2>Storico fermentazioni</h2>
      <button
        class="text-button"
        type="button"
        :aria-pressed="!selectedId"
        @click="emit('select', null)"
      >
        Monitoraggio attuale
      </button>
    </div>
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
      <button class="text-button" type="button" @click="load(offset)">
        Riprova elenco
      </button>
    </p>
    <p v-if="loading" role="status">Caricamento fermentazioni…</p>
    <p v-else-if="!error && !entries.length" class="history-period">
      {{
        appliedSearch
          ? 'Nessuna fermentazione corrisponde alla ricerca.'
          : 'Nessuna fermentazione conclusa.'
      }}
    </p>
    <ul v-if="entries.length" class="archive-list">
      <li v-for="entry in entries" :key="entry.id">
        <button
          type="button"
          class="archive-entry"
          :aria-label="`Apri ${entry.name}, ${dates.format(new Date(entry.started_at))}`"
          :aria-current="selectedId === entry.id ? 'true' : undefined"
          @click="emit('select', entry.id)"
        >
          <span>{{ entry.name }}</span
          ><time :datetime="entry.started_at">{{
            dates.format(new Date(entry.started_at))
          }}</time>
        </button>
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
