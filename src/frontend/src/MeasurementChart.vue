<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js'
import type { ChartOptions } from 'chart.js'
import type { Reading } from './readings'
import {
  measurements,
  measurementScales,
  measurementValue,
  exactMeasurement,
} from './measurements'
import type { Measurement, MeasurementScale } from './measurements'

Chart.register(LineController, LineElement, LinearScale, PointElement, Tooltip)
const props = defineProps<{ readings: Reading[]; range?: [number, number] }>()
const emit = defineEmits<{ range: [start: number, end: number] }>()
const gestureMode = ref<'zoom' | 'pan'>('zoom')
const selection = ref<[number, number] | null>(null)
const pointers = new Map<number, number>()
let origin: { x: number; range: [number, number]; distance: number } | null =
  null
function position(event: PointerEvent) {
  return event.clientX - canvas.value!.getBoundingClientRect().left
}
function pointTime(x: number, bounds: [number, number]) {
  const scale = chart?.scales.x
  if (!scale) return bounds[0]
  return (
    bounds[0] +
    Math.max(0, Math.min(1, (x - scale.left) / scale.width)) *
      (bounds[1] - bounds[0])
  )
}
function pointerDown(event: PointerEvent) {
  if (!props.range) return
  event.preventDefault()
  canvas.value?.setPointerCapture(event.pointerId)
  pointers.set(event.pointerId, position(event))
  const xs = [...pointers.values()]
  origin = {
    x: xs.reduce((sum, x) => sum + x, 0) / xs.length,
    range: [...props.range],
    distance: xs.length > 1 ? Math.abs(xs[1]! - xs[0]!) : 0,
  }
}
function pointerMove(event: PointerEvent) {
  if (!origin || !pointers.has(event.pointerId)) return
  pointers.set(event.pointerId, position(event))
  if (pointers.size === 1) selection.value = [origin.x, position(event)]
}
function pointerUp(event: PointerEvent) {
  if (!origin || !pointers.has(event.pointerId)) return
  const xs = [...pointers.values()]
  const base = origin
  if (pointers.size > 1 && base.distance > 0) {
    const factor = base.distance / Math.max(1, Math.abs(xs[1]! - xs[0]!))
    const center = pointTime(base.x, base.range)
    const width = (base.range[1] - base.range[0]) * factor
    emit('range', center - width / 2, center + width / 2)
  } else if (Math.abs(position(event) - base.x) > 4) {
    if (gestureMode.value === 'pan' || event.pointerType === 'touch') {
      const delta =
        ((position(event) - base.x) / (chart?.scales.x?.width ?? 1)) *
        (base.range[1] - base.range[0])
      emit('range', base.range[0] - delta, base.range[1] - delta)
    } else {
      const a = pointTime(base.x, base.range),
        b = pointTime(position(event), base.range)
      emit('range', Math.min(a, b), Math.max(a, b))
    }
  }
  pointers.clear()
  origin = null
  selection.value = null
}
function cancelGesture() {
  pointers.clear()
  origin = null
  selection.value = null
}
function wheel(event: WheelEvent) {
  if (!props.range || !chart?.scales.x) return
  event.preventDefault()
  const center = pointTime(
    event.clientX - canvas.value!.getBoundingClientRect().left,
    props.range,
  )
  const factor = event.deltaY < 0 ? 0.75 : 1.333333333
  emit(
    'range',
    center + (props.range[0] - center) * factor,
    center + (props.range[1] - center) * factor,
  )
}
const canvas = ref<HTMLCanvasElement | null>(null)
const descriptionId = useId()
const visibility = ref(measurements.map(() => true))
const compact = ref(false)
const graduatedScale = ref<MeasurementScale>('temperature')
const tooltip = ref<{
  timestamp: number
  lines: Array<{ label: string; value: string }>
} | null>(null)
const visibleCount = computed(() => visibility.value.filter(Boolean).length)
type Point = { x: number; y: number | null }
let chart: Chart<'line', Point[]> | undefined
let observer: ResizeObserver | undefined
const dates = new Intl.DateTimeFormat('it-IT', {
  day: 'numeric',
  month: 'short',
})
const times = new Intl.DateTimeFormat('it-IT', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})
const fullDates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const ticks = new Intl.NumberFormat('it-IT', {
  maximumSignificantDigits: 5,
  useGrouping: false,
})

function points(metric: Measurement): Point[] {
  return props.readings.map((reading) => ({
    x: reading.timestamp * 1000,
    y: measurementValue(reading, metric.key),
  }))
}
function scaleVisible(scale: MeasurementScale): boolean {
  return measurements.some(
    (metric, index) => metric.scale === scale && visibility.value[index],
  )
}
function scales(): NonNullable<ChartOptions<'line'>['scales']> {
  const first = (props.range?.[0] ?? props.readings[0]?.timestamp ?? 0) * 1000
  const last =
    (props.range?.[1] ?? props.readings.at(-1)?.timestamp ?? 1) * 1000
  const gridScale = compact.value
    ? graduatedScale.value
    : measurementScales.find((scale) => scaleVisible(scale.id))?.id
  return {
    x: {
      type: 'linear',
      axis: 'x',
      min: first === last ? first - 1000 : first,
      max: first === last ? last + 1000 : last,
      title: { display: true, text: 'Acquisizione' },
      ticks: {
        maxTicksLimit: compact.value ? 3 : 5,
        maxRotation: 0,
        callback: (value) => {
          const date = new Date(Number(value))
          return [dates.format(date), times.format(date)]
        },
      },
    },
    ...Object.fromEntries(
      measurementScales.map((scale) => [
        scale.id,
        {
          type: 'linear',
          axis: 'y',
          position: compact.value ? 'left' : scale.position,
          display:
            (!compact.value || graduatedScale.value === scale.id) &&
            scaleVisible(scale.id),
          title: { display: true, text: scale.label },
          grid: {
            drawOnChartArea: scale.id === gridScale,
          },
          ticks: {
            maxTicksLimit: 6,
            callback: (value: string | number) => ticks.format(Number(value)),
          },
        },
      ]),
    ),
  }
}
function update() {
  if (!chart) return
  tooltip.value = null
  chart.data.datasets.forEach((dataset, index) => {
    dataset.data = points(measurements[index]!)
    chart!.setDatasetVisibility(index, visibility.value[index]!)
  })
  chart.options.scales = scales()
  chart.update('none')
}
function toggle(index: number) {
  visibility.value[index] = !visibility.value[index]
  if (!scaleVisible(graduatedScale.value)) {
    const next = measurementScales.find((scale) => scaleVisible(scale.id))
    if (next) graduatedScale.value = next.id
  }
  update()
}
onMounted(() => {
  if (!canvas.value) return
  compact.value = canvas.value.parentElement!.clientWidth < 640
  chart = new Chart<'line', Point[]>(canvas.value, {
    type: 'line',
    data: {
      datasets: measurements.map((metric) => ({
        label: metric.label,
        data: points(metric),
        yAxisID: metric.scale,
        borderColor: metric.color,
        backgroundColor: metric.color,
        borderDash: metric.dash,
        borderWidth: 2,
        pointStyle: metric.marker,
        pointRadius: 2.5,
        pointHoverRadius: 5,
        tension: 0,
        spanGaps: true,
        fill: false,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      locale: 'it-IT',
      interaction: { mode: 'nearest', axis: 'xy', intersect: false },
      scales: scales(),
      plugins: {
        tooltip: {
          enabled: false,
          external: ({ tooltip: model }) => {
            if (model.opacity === 0 || !model.dataPoints.length) {
              tooltip.value = null
              return
            }
            const reading = props.readings[model.dataPoints[0]!.dataIndex]
            if (!reading) return
            tooltip.value = {
              timestamp: reading.timestamp,
              // Keep all tooltip fields tied to one real sample, including
              // when different samples have the same acquisition timestamp.
              lines: measurements.flatMap((metric, index) => {
                if (!visibility.value[index]) return []
                const value = exactMeasurement(reading, metric.key)
                const unit =
                  measurementValue(reading, metric.key) === null
                    ? ''
                    : ` ${metric.unit}`
                return [{ label: metric.label, value: value + unit }]
              }),
            }
          },
        },
      },
    },
  })
  observer = new ResizeObserver(([entry]) => {
    const narrow = entry!.contentRect.width < 640
    if (narrow !== compact.value) {
      compact.value = narrow
      update()
    }
  })
  observer.observe(canvas.value.parentElement!)
})
watch(() => props.readings, update)
watch(() => props.range, update)
watch(graduatedScale, update)
onUnmounted(() => {
  observer?.disconnect()
  chart?.destroy()
})
</script>

<template>
  <section class="measurement-chart" aria-label="Grafico delle misure">
    <div v-if="range" class="history-navigation" aria-label="Gesti del grafico">
      <button
        class="text-button"
        :aria-pressed="gestureMode === 'zoom'"
        @click="gestureMode = 'zoom'"
      >
        Seleziona per zoom
      </button>
      <button
        class="text-button"
        :aria-pressed="gestureMode === 'pan'"
        @click="gestureMode = 'pan'"
      >
        Trascina per spostare
      </button>
      <span>Rotella: zoom · Due dita: pinch · Un dito: sposta</span>
    </div>
    <fieldset class="chart-legend" aria-label="Serie del grafico">
      <legend>Misure nel grafico</legend>
      <label
        v-for="(metric, index) in measurements"
        :key="metric.key"
        class="series-option"
      >
        <input
          type="checkbox"
          :checked="visibility[index]"
          :aria-label="metric.label"
          @change="toggle(index)"
        />
        <span
          class="series-swatch"
          aria-hidden="true"
          :style="{
            borderColor: metric.color,
            borderTopStyle: metric.dash.length ? 'dashed' : 'solid',
          }"
        ></span>
        <span>{{ metric.label }}</span>
      </label>
    </fieldset>
    <div v-if="compact" class="chart-scale-choice">
      <label :for="`${descriptionId}-scale`">Scala graduata</label>
      <select
        :id="`${descriptionId}-scale`"
        v-model="graduatedScale"
        :disabled="visibleCount === 0"
      >
        <option
          v-for="scale in measurementScales"
          :key="scale.id"
          :value="scale.id"
          :disabled="!scaleVisible(scale.id)"
        >
          {{ scale.label }}
        </option>
      </select>
    </div>
    <p :id="descriptionId" class="chart-description">
      Scale indipendenti per °C, SG, %, punti SG/giorno e accelerazioni (unità
      non specificata).
      <template v-if="compact">
        Scegli la scala graduata da leggere; tutte le serie mantengono la
        propria scala.</template
      >
      I valori esatti sono nella tabella. Tocca o passa sul tracciato per i
      dettagli.
    </p>
    <p v-if="visibleCount === 0" role="status">
      Nessuna serie selezionata. Seleziona una misura dalla legenda.
    </p>
    <div class="chart-box">
      <canvas
        ref="canvas"
        style="touch-action: none"
        role="img"
        :aria-label="`Grafico a linee: ${readings.length} ${readings.length === 1 ? 'lettura' : 'letture'}`"
        :aria-describedby="descriptionId"
        @pointerdown="pointerDown"
        @pointermove="pointerMove"
        @pointerup="pointerUp"
        @pointercancel="cancelGesture"
        @wheel="wheel"
        >Valori esatti disponibili nella tabella delle letture.</canvas
      >
      <div
        v-if="selection && gestureMode === 'zoom'"
        class="chart-selection"
        :style="{
          left: Math.min(...selection) + 'px',
          width: Math.abs(selection[1] - selection[0]) + 'px',
        }"
      />
    </div>
    <div
      v-if="tooltip && tooltip.lines.length"
      class="chart-tooltip"
      role="status"
      aria-label="Valori nel grafico"
    >
      <p>
        Acquisizione:
        {{ fullDates.format(new Date(tooltip.timestamp * 1000)) }} · Unix
        {{ tooltip.timestamp }}
      </p>
      <dl>
        <div v-for="(line, index) in tooltip.lines" :key="index">
          <dt>{{ line.label }}</dt>
          <dd>{{ line.value }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>
<style scoped>
.chart-box {
  position: relative;
}
.chart-selection {
  position: absolute;
  top: 0;
  bottom: 0;
  background: #19534233;
  border: 1px solid #195342;
  pointer-events: none;
}
</style>
