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
const props = defineProps<{ readings: Reading[] }>()
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
  const first = props.readings[0]!.timestamp * 1000
  const last = props.readings.at(-1)!.timestamp * 1000
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
watch(graduatedScale, update)
onUnmounted(() => {
  observer?.disconnect()
  chart?.destroy()
})
</script>

<template>
  <section class="measurement-chart" aria-label="Grafico delle misure">
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
        role="img"
        :aria-label="`Grafico a linee: ${readings.length} ${readings.length === 1 ? 'lettura' : 'letture'}`"
        :aria-describedby="descriptionId"
        >Valori esatti disponibili nella tabella delle letture.</canvas
      >
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
