<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { current, metricLabels, state, timestamp, type Metric } from './demo'
import ProtoIcon from './ProtoIcon.vue'
const scope = ref('window')
const page = ref(0)
const dialog = ref<HTMLElement>()
const trigger = document.activeElement as HTMLElement | null
const metrics = Object.keys(metricLabels) as Metric[]
const rows = computed(() =>
  (current.value?.samples ?? []).filter(
    (point) =>
      scope.value === 'all' ||
      (point.time >= state.from && point.time <= state.to),
  ),
)
const pages = computed(() => Math.max(1, Math.ceil(rows.value.length / 10)))
const visible = computed(() =>
  rows.value.slice(page.value * 10, page.value * 10 + 10),
)
watch(scope, () => {
  page.value = 0
})
function csv() {
  const content = [
    'timestamp,temperature,specific_gravity,battery,velocity,accel_x,accel_y,accel_z',
    ...rows.value.map((point) =>
      [
        new Date(point.time).toISOString(),
        ...metrics.map((metric) => point[metric] ?? ''),
      ].join(','),
    ),
  ].join('\r\n')
  const url = URL.createObjectURL(
    new Blob([content], { type: 'text/csv;charset=utf-8' }),
  )
  const link = document.createElement('a')
  link.href = url
  link.download = `${current.value?.id}-${scope.value}-demo.csv`
  link.click()
  URL.revokeObjectURL(url)
  state.notice = `CSV dimostrativo scaricato: ${rows.value.length} letture, tutte le metriche.`
}
function key(event: KeyboardEvent) {
  if (event.key === 'Escape') state.raw = false
  if (event.key !== 'Tab') return
  const controls = [
    ...dialog.value!.querySelectorAll<HTMLElement>(
      'button, select, [tabindex="0"]',
    ),
  ]
  const first = controls[0],
    last = controls.at(-1)
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}
onMounted(() => {
  dialog.value?.focus()
  window.addEventListener('keydown', key)
})
onUnmounted(() => {
  window.removeEventListener('keydown', key)
  trigger?.focus()
})
</script>
<template>
  <div class="p-modal-backdrop" @click.self="state.raw = false">
    <section
      ref="dialog"
      class="p-modal p-raw-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="raw-title"
      tabindex="-1"
    >
      <header>
        <div>
          <span class="p-overline">{{ current?.name }}</span>
          <h2 id="raw-title">Dati grezzi</h2>
        </div>
        <button
          class="p-icon-button"
          aria-label="Chiudi dati grezzi"
          @click="state.raw = false"
        >
          <ProtoIcon name="close" />
        </button>
      </header>
      <div class="p-raw-toolbar">
        <label
          >Periodo<select v-model="scope" aria-label="Periodo">
            <option value="window">Intervallo del grafico</option>
            <option value="all">Intera fermentazione</option>
          </select></label
        ><button class="p-primary" @click="csv">
          <ProtoIcon name="download" />Scarica CSV ({{ rows.length }})
        </button>
      </div>
      <p class="p-help">
        Tutte le metriche ricevute. Il CSV contiene ogni lettura del periodo,
        anche quelle nelle altre pagine. Dati dimostrativi.
      </p>
      <div
        class="p-table-scroll"
        tabindex="0"
        aria-label="Tabella delle letture, scorrimento orizzontale"
      >
        <table>
          <thead>
            <tr>
              <th>Data e ora</th>
              <th v-for="metric in metrics" :key="metric">
                {{ metricLabels[metric] }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="point in visible" :key="point.time">
              <td :title="new Date(point.time).toISOString()">
                {{ timestamp(point.time) }}
              </td>
              <td v-for="metric in metrics" :key="metric">
                {{ point[metric] ?? '—' }}
              </td>
            </tr>
            <tr v-if="!visible.length">
              <td colspan="8">Nessuna lettura in questo intervallo.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <footer>
        <span
          >{{ rows.length }} letture · pagina {{ page + 1 }} di
          {{ pages }}</span
        >
        <div class="p-actions">
          <button :disabled="page === 0" @click="page--">Precedente</button
          ><button :disabled="page + 1 >= pages" @click="page++">
            Successiva
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>
