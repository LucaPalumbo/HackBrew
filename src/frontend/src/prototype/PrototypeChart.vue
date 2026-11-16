<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Chart, registerables, type ChartOptions } from 'chart.js'
import { current, metricLabels, state, timestamp, type Metric } from './demo'
import ProtoIcon from './ProtoIcon.vue'
Chart.register(...registerables)
const canvas = ref<HTMLCanvasElement>()
const overview = ref<SVGSVGElement>()
const plot = ref<HTMLElement>()
const interaction = ref('select')
const selection = ref<{ left: number; width: number } | null>(null)
let chart: Chart<'line', { x: number; y: number | null }[]> | undefined
const colors: Record<Metric, string> = {
  temperature: '#e49244',
  gravity: '#28a9a1',
  battery: '#a78bfa',
  velocity: '#f27a98',
  accel_x: '#579fed',
  accel_y: '#b8ad42',
  accel_z: '#ca80c5',
}
const groups: Record<Metric, string> = {
  temperature: 'temp',
  gravity: 'sg',
  battery: 'battery',
  velocity: 'velocity',
  accel_x: 'accel',
  accel_y: 'accel',
  accel_z: 'accel',
}
const units: Record<string, string> = {
  temp: '°C',
  sg: 'SG',
  battery: '%',
  velocity: 'punti SG/giorno',
  accel: 'accel.*',
}
const allMetrics = Object.keys(metricLabels) as Metric[]
const samples = computed(() => current.value?.samples ?? [])
const first = computed(() => current.value?.start ?? state.from)
const last = computed(() => samples.value.at(-1)?.time ?? state.to)
const duration = computed(() => Math.max(last.value - first.value, 1))
const left = computed(() => ((state.from - first.value) / duration.value) * 100)
const right = computed(() => ((state.to - first.value) / duration.value) * 100)
const densityPath = computed(() =>
  samples.value
    .map(
      (point, index) =>
        `${index ? 'L' : 'M'}${((point.time - first.value) / duration.value) * 1000},${54 - (((point.gravity ?? 1.01) - 1.01) / 0.06) * 46}`,
    )
    .join(' '),
)
const windowLabel = computed(
  () => `${timestamp(state.from)} — ${timestamp(state.to)}`,
)
function toggle(metric: Metric) {
  if (state.metrics.includes(metric)) {
    if (state.metrics.length > 1)
      state.metrics = state.metrics.filter((item) => item !== metric)
  } else state.metrics.push(metric)
}
function setWindow(from: number, to: number, live = false) {
  state.from = Math.max(first.value, Math.min(from, last.value - 60000))
  state.to = Math.min(last.value, Math.max(to, state.from + 60000))
  state.live = live
}
function preset(hours: number | null) {
  setWindow(
    hours ? Math.max(first.value, last.value - hours * 3600000) : first.value,
    last.value,
    true,
  )
}
function returnLive() {
  const span = state.to - state.from
  setWindow(Math.max(first.value, last.value - span), last.value, true)
}
function visibleValues(metric: Metric) {
  const valid = samples.value.filter((point) => point[metric] !== null)
  const values = valid
    .filter((point) => point.time >= state.from && point.time <= state.to)
    .map((point) => point[metric]!)
  // Boundary interpolation is only used for axis limits. Exported rows stay original.
  for (const boundary of [state.from, state.to]) {
    const before = [...valid].reverse().find((point) => point.time <= boundary)
    const after = valid.find((point) => point.time >= boundary)
    if (before && after) {
      const fraction =
        (boundary - before.time) / (after.time - before.time || 1)
      values.push(
        before[metric]! + fraction * (after[metric]! - before[metric]!),
      )
    }
  }
  return values
}
function draw() {
  if (!canvas.value || !samples.value.length) return
  const scales: NonNullable<ChartOptions<'line'>['scales']> = {
    x: {
      type: 'linear',
      min: state.from,
      max: state.to,
      grid: { display: false },
      ticks: {
        maxTicksLimit: 6,
        color: '#89959d',
        callback: (value) =>
          new Intl.DateTimeFormat('it-IT', {
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
          }).format(Number(value)),
      },
    },
  }
  const enabledGroups = [
    ...new Set(state.metrics.map((metric) => groups[metric])),
  ]
  for (const [index, group] of enabledGroups.entries()) {
    const metrics = state.metrics.filter((metric) => groups[metric] === group)
    const values = metrics.flatMap(visibleValues)
    const low = Math.min(...values),
      high = Math.max(...values)
    const padding = Math.max(
      (high - low) * 0.15,
      group === 'sg' ? 0.0003 : group === 'temp' ? 0.1 : 0.01,
    )
    scales[group] = {
      type: 'linear',
      position: index % 2 ? 'right' : 'left',
      min: Number.isFinite(low) ? low - padding : undefined,
      max: Number.isFinite(high) ? high + padding : undefined,
      title: { display: true, text: units[group], color: colors[metrics[0]!] },
      grid: {
        drawOnChartArea: index === 0,
        color: state.variant === 'C' ? '#28333c' : '#e9eceb',
      },
      ticks: {
        maxTicksLimit: 6,
        color: colors[metrics[0]!],
        callback: (value) =>
          Number(value).toFixed(group === 'sg' ? 3 : group === 'temp' ? 1 : 2),
      },
    }
  }
  chart?.destroy()
  chart = new Chart(canvas.value, {
    type: 'line',
    data: {
      datasets: state.metrics.map((metric) => ({
        label: metricLabels[metric],
        data: samples.value.map((point) => ({
          x: point.time,
          y: point[metric],
        })),
        yAxisID: groups[metric],
        borderColor: colors[metric],
        borderWidth:
          metric === 'gravity' || metric === 'temperature' ? 2.3 : 1.5,
        pointRadius: 0,
        pointHitRadius: 12,
        tension: 0,
        spanGaps: true,
        clip: 0,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      normalized: true,
      scales,
      interaction: { mode: 'nearest', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: (item) =>
            item.parsed.x !== null &&
            item.parsed.x >= state.from &&
            item.parsed.x <= state.to,
          callbacks: {
            title: (items) => timestamp(items[0]?.parsed.x ?? state.from),
            label: (item) => `${item.dataset.label}: ${item.parsed.y ?? '—'}`,
          },
        },
      },
    },
  })
}
let brush: {
  kind: string
  x: number
  from: number
  to: number
  width: number
} | null = null
function startBrush(event: PointerEvent, kind: string) {
  if (event.button !== 0) return
  event.preventDefault()
  ;(event.currentTarget as Element).setPointerCapture(event.pointerId)
  brush = {
    kind,
    x: event.clientX,
    from: state.from,
    to: state.to,
    width: overview.value!.getBoundingClientRect().width,
  }
}
function moveBrush(event: PointerEvent) {
  if (!brush) return
  const shift = ((event.clientX - brush.x) / brush.width) * duration.value
  if (brush.kind === 'from')
    setWindow(Math.min(brush.from + shift, brush.to - 60000), brush.to)
  else if (brush.kind === 'to')
    setWindow(brush.from, Math.max(brush.to + shift, brush.from + 60000))
  else {
    const delta = Math.max(
      first.value - brush.from,
      Math.min(shift, last.value - brush.to),
    )
    setWindow(brush.from + delta, brush.to + delta)
  }
}
function endBrush() {
  brush = null
}
function keyBrush(event: KeyboardEvent, kind: string) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return
  event.preventDefault()
  event.stopPropagation()
  const shift = (duration.value / 100) * (event.key === 'ArrowRight' ? 1 : -1)
  if (kind === 'from')
    setWindow(Math.min(state.from + shift, state.to - 60000), state.to)
  else if (kind === 'to')
    setWindow(state.from, Math.max(state.to + shift, state.from + 60000))
  else {
    const delta = Math.max(
      first.value - state.from,
      Math.min(shift, last.value - state.to),
    )
    setWindow(state.from + delta, state.to + delta)
  }
}
function wheel(event: WheelEvent) {
  if (!chart) return
  const area = chart.chartArea
  const ratio = Math.max(
    0,
    Math.min(
      1,
      (event.clientX - canvas.value!.getBoundingClientRect().left - area.left) /
        area.width,
    ),
  )
  const span = state.to - state.from,
    factor = event.deltaY > 0 ? 1.18 : 0.82
  const newSpan = Math.max(60000, Math.min(duration.value, span * factor))
  const anchor = state.from + ratio * span
  const from = Math.max(
    first.value,
    Math.min(last.value - newSpan, anchor - ratio * newSpan),
  )
  setWindow(from, from + newSpan)
}
let drag: { x: number; from: number; to: number } | null = null
const pointers = new Map<number, number>()
let pinch: { distance: number; from: number; to: number } | null = null
function startPlot(event: PointerEvent) {
  if (event.button !== 0 || !chart) return
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  pointers.set(event.pointerId, event.clientX)
  if (pointers.size === 2) {
    const positions = [...pointers.values()]
    pinch = {
      distance: Math.abs(positions[0]! - positions[1]!),
      from: state.from,
      to: state.to,
    }
    selection.value = null
    return
  }
  drag = { x: event.clientX, from: state.from, to: state.to }
}
function movePlot(event: PointerEvent) {
  if (!pointers.has(event.pointerId) || !drag || !chart) return
  pointers.set(event.pointerId, event.clientX)
  const width = chart.chartArea.width
  if (pinch && pointers.size === 2) {
    const positions = [...pointers.values()]
    const span = Math.max(
      60000,
      Math.min(
        duration.value,
        ((pinch.to - pinch.from) * pinch.distance) /
          Math.max(10, Math.abs(positions[0]! - positions[1]!)),
      ),
    )
    const from = Math.max(
      first.value,
      Math.min(last.value - span, (pinch.from + pinch.to - span) / 2),
    )
    setWindow(from, from + span)
    return
  }
  if (interaction.value === 'pan' || event.pointerType === 'touch') {
    const shift = (-(event.clientX - drag.x) / width) * (drag.to - drag.from)
    const delta = Math.max(
      first.value - drag.from,
      Math.min(shift, last.value - drag.to),
    )
    setWindow(drag.from + delta, drag.to + delta)
  } else {
    const rect = plot.value!.getBoundingClientRect()
    selection.value = {
      left: Math.min(drag.x, event.clientX) - rect.left,
      width: Math.abs(event.clientX - drag.x),
    }
  }
}
function endPlot(event: PointerEvent) {
  if (drag && !pinch && selection.value && selection.value.width > 8 && chart) {
    const rect = canvas.value!.getBoundingClientRect(),
      area = chart.chartArea
    const ratio = (x: number) =>
      Math.max(0, Math.min(1, (x - rect.left - area.left) / area.width))
    const a = drag.from + ratio(drag.x) * (drag.to - drag.from)
    const b = drag.from + ratio(event.clientX) * (drag.to - drag.from)
    setWindow(Math.min(a, b), Math.max(a, b))
  }
  pointers.delete(event.pointerId)
  drag = null
  pinch = null
  selection.value = null
}
function cancelPlot() {
  pointers.clear()
  drag = null
  pinch = null
  selection.value = null
}
watch(
  () => [
    state.from,
    state.to,
    [...state.metrics],
    samples.value.length,
    state.variant,
    state.selected,
  ],
  draw,
  { flush: 'post' },
)
onMounted(draw)
onBeforeUnmount(() => chart?.destroy())
</script>
<template>
  <section class="p-chart-panel" aria-label="Grafico della fermentazione">
    <div class="p-chart-title">
      <div>
        <span class="p-overline">L’EVOLUZIONE DELLA BIRRA</span>
        <h2>Andamento</h2>
      </div>
      <span
        class="p-live-label"
        :class="{ 'p-paused': !state.live || current?.end }"
        ><span class="p-dot" />{{
          current?.end
            ? 'Fermentazione conclusa'
            : state.live
              ? 'Live'
              : 'Esplorazione'
        }}</span
      >
    </div>
    <div class="p-chart-toolbar">
      <div class="p-segmented">
        <button
          v-for="hours in [1, 6, 24, null]"
          :key="String(hours)"
          @click="preset(hours)"
        >
          {{ hours ? `${hours}h` : 'Tutto' }}
        </button>
      </div>
      <button
        v-if="!state.live && !current?.end"
        class="p-live-button"
        @click="returnLive"
      >
        Torna al live <ProtoIcon name="arrow" /></button
      ><span class="p-chart-window">{{ windowLabel }}</span>
    </div>
    <div class="p-overview-label">
      <span>Densità · intera fermentazione</span
      ><span>Trascina la finestra o i bordi</span>
    </div>
    <div class="p-brush">
      <svg
        ref="overview"
        class="p-overview"
        viewBox="0 0 1000 64"
        preserveAspectRatio="none"
        aria-label="Selettore del periodo"
      >
        <path :d="`${densityPath} L1000,64 L0,64 Z`" class="p-overview-fill" />
        <path :d="densityPath" class="p-overview-line" />
        <rect
          x="0"
          y="0"
          :width="left * 10"
          height="64"
          class="p-overview-shade"
        />
        <rect
          :x="right * 10"
          y="0"
          :width="1000 - right * 10"
          height="64"
          class="p-overview-shade"
        />
        <rect
          :x="left * 10"
          y="1"
          :width="Math.max(1, (right - left) * 10)"
          height="62"
          class="p-overview-selection"
          role="slider"
          tabindex="0"
          aria-label="Sposta finestra temporale"
          :aria-valuemin="first"
          :aria-valuemax="last"
          :aria-valuenow="state.from"
          :aria-valuetext="windowLabel"
          @pointerdown="startBrush($event, 'move')"
          @pointermove="moveBrush"
          @pointerup="endBrush"
          @pointercancel="endBrush"
          @keydown="keyBrush($event, 'move')"
        />
      </svg>
      <button
        v-for="kind in ['from', 'to']"
        :key="kind"
        type="button"
        :style="{
          left: `clamp(13px, ${kind === 'from' ? left : right}%, calc(100% - 13px))`,
        }"
        class="p-brush-handle"
        role="slider"
        tabindex="0"
        :aria-label="kind === 'from' ? 'Inizio intervallo' : 'Fine intervallo'"
        :aria-valuemin="first"
        :aria-valuemax="last"
        :aria-valuenow="kind === 'from' ? state.from : state.to"
        :aria-valuetext="timestamp(kind === 'from' ? state.from : state.to)"
        @pointerdown="startBrush($event, kind)"
        @pointermove="moveBrush"
        @pointerup="endBrush"
        @pointercancel="endBrush"
        @keydown="keyBrush($event, kind)"
      />
    </div>
    <div
      ref="plot"
      class="p-chart-canvas"
      @wheel.prevent="wheel"
      @pointerdown="startPlot"
      @pointermove="movePlot"
      @pointerup="endPlot"
      @pointercancel="cancelPlot"
    >
      <canvas
        ref="canvas"
        role="img"
        :aria-label="`Andamento di ${state.metrics.map((metric) => metricLabels[metric]).join(', ')}. ${windowLabel}`"
      />
      <div
        v-if="selection"
        class="p-selection"
        :style="{ left: `${selection.left}px`, width: `${selection.width}px` }"
      />
    </div>
    <div class="p-chart-interactions">
      <div class="p-segmented">
        <button
          :class="{ 'p-selected': interaction === 'select' }"
          @click="interaction = 'select'"
        >
          Seleziona per zoom</button
        ><button
          :class="{ 'p-selected': interaction === 'pan' }"
          @click="interaction = 'pan'"
        >
          Sposta
        </button>
      </div>
      <span>Rotella per zoom · su touch, trascina o pizzica</span>
    </div>
    <div class="p-series">
      <button
        v-for="metric in allMetrics"
        :key="metric"
        :aria-pressed="state.metrics.includes(metric)"
        :class="{ 'p-series-on': state.metrics.includes(metric) }"
        @click="toggle(metric)"
      >
        <span :style="{ background: colors[metric] }" />{{ metricLabels[metric]
        }}<small>{{ state.metrics.includes(metric) ? '✓' : '+' }}</small>
      </button>
    </div>
    <p
      v-if="
        state.metrics.some(
          (metric) => metric.startsWith('accel') || metric === 'velocity',
        )
      "
      class="p-help"
    >
      * Unità degli accelerometri non specificata dal gateway. Velocità in punti
      SG/giorno.
    </p>
    <div class="p-chart-footer">
      <span>Assi adattati alla finestra · linea continua fra le letture</span
      ><button class="p-text-button" @click="state.raw = true">
        Dati grezzi e CSV <ProtoIcon name="arrow" />
      </button>
    </div>
  </section>
</template>
