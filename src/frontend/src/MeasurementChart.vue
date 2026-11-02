<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Chart,
  ScatterController,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js'
import type { Reading } from './readings'

Chart.register(ScatterController, LinearScale, PointElement, Tooltip)
const props = defineProps<{
  readings: Reading[]
  metric: 'specific_gravity' | 'temperature'
  label: string
}>()
const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart<'scatter'> | undefined
const dates = new Intl.DateTimeFormat('it-IT', {
  day: 'numeric',
  month: 'short',
})
const times = new Intl.DateTimeFormat('it-IT', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})
function formatValue(value: number | null) {
  if (value === null) return ''
  return props.metric === 'specific_gravity'
    ? value.toFixed(3)
    : value.toLocaleString('it-IT')
}
function points() {
  return props.readings.map((reading) => ({
    x: reading.timestamp * 1000,
    y: reading[props.metric],
  }))
}
onMounted(() => {
  if (!canvas.value) return
  chart = new Chart(canvas.value, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: props.label,
          data: points(),
          pointRadius: 3,
          pointHoverRadius: 5,
          backgroundColor:
            props.metric === 'specific_gravity' ? '#1b4638' : '#b57826',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      locale: 'it-IT',
      scales: {
        x: {
          type: 'linear',
          title: { display: true, text: 'Acquisizione' },
          ticks: {
            maxTicksLimit: 3,
            callback: (value) => {
              const date = new Date(Number(value))
              return [dates.format(date), times.format(date)]
            },
          },
        },
        y: {
          title: { display: true, text: props.label },
          ticks: {
            callback: (value) => formatValue(Number(value)),
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: (items) => {
              const timestamp = items[0]?.parsed.x
              return timestamp == null
                ? ''
                : new Date(timestamp).toLocaleString('it-IT')
            },
            label: (item) => `${props.label}: ${formatValue(item.parsed.y)}`,
          },
        },
      },
    },
  })
})
watch(
  () => props.readings,
  () => {
    if (!chart) return
    chart.data.datasets[0]!.data = points()
    chart.update('none')
  },
)
onUnmounted(() => chart?.destroy())
</script>

<template>
  <div class="chart-box">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="`${label}: ${readings.length} ${readings.length === 1 ? 'lettura' : 'letture'}`"
      >{{ label }}: valori disponibili nella tabella delle letture.</canvas
    >
  </div>
</template>
