<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import type { Reading } from './readings'
const props = defineProps<{
  start: number
  end: number
  minimum: number
  maximum: number
  following: boolean
  readings: Reading[]
}>()
const emit = defineEmits<{
  range: [start: number, end: number]
  preset: [hours: number | null]
  live: []
}>()
const helpId = useId()
const track = ref<HTMLElement>()
const draft = ref<[number, number] | null>(null)
const selected = computed(() => draft.value ?? [props.start, props.end])
const span = computed(() => props.maximum - props.minimum)
const shortest = computed(() => Math.min(0.001, span.value))
const step = computed(() => Math.max(shortest.value, span.value / 100))
const percent = (value: number) =>
  `${((value - props.minimum) / (span.value || 1)) * 100}%`
const dates = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'short',
  timeStyle: 'medium',
})
const date = (value: number) => dates.format(new Date(value * 1000))
let drag: {
  id: number
  x: number
  start: number
  end: number
  width: number
} | null = null
function shifted(start: number, end: number): [number, number] {
  const duration = Math.min(end - start, span.value)
  const left = Math.max(
    props.minimum,
    Math.min(start, props.maximum - duration),
  )
  return [left, left + duration]
}
function handle(event: Event, edge: 'start' | 'end') {
  const value = Number((event.target as HTMLInputElement).value)
  if (edge === 'start')
    emit(
      'range',
      Math.max(props.minimum, Math.min(value, props.end - shortest.value)),
      props.end,
    )
  else
    emit(
      'range',
      props.start,
      Math.min(props.maximum, Math.max(value, props.start + shortest.value)),
    )
}
function key(event: KeyboardEvent, edge: 'start' | 'end' | 'window') {
  const directions: Record<string, number> = {
    ArrowLeft: -1,
    ArrowDown: -1,
    ArrowRight: 1,
    ArrowUp: 1,
    PageDown: -10,
    PageUp: 10,
  }
  if (!(event.key in directions) && !['Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const amount =
    (directions[event.key] ?? 0) * step.value * (event.shiftKey ? 10 : 1)
  if (edge === 'window') {
    const start =
      event.key === 'Home'
        ? props.minimum
        : event.key === 'End'
          ? props.maximum - (props.end - props.start)
          : props.start + amount
    emit('range', ...shifted(start, start + props.end - props.start))
  } else {
    const current = edge === 'start' ? props.start : props.end
    const value =
      event.key === 'Home'
        ? props.minimum
        : event.key === 'End'
          ? props.maximum
          : current + amount
    if (edge === 'start')
      emit(
        'range',
        Math.max(props.minimum, Math.min(value, props.end - shortest.value)),
        props.end,
      )
    else
      emit(
        'range',
        props.start,
        Math.min(props.maximum, Math.max(value, props.start + shortest.value)),
      )
  }
}
function begin(event: PointerEvent) {
  if (event.button !== 0 || !track.value) return
  event.preventDefault()
  const target = event.currentTarget as HTMLElement
  target.focus({ preventScroll: true })
  target.setPointerCapture(event.pointerId)
  drag = {
    id: event.pointerId,
    x: event.clientX,
    start: props.start,
    end: props.end,
    width: track.value.getBoundingClientRect().width,
  }
}
function move(event: PointerEvent) {
  if (!drag || drag.id !== event.pointerId) return
  const delta = ((event.clientX - drag.x) / (drag.width || 1)) * span.value
  draft.value = shifted(drag.start + delta, drag.end + delta)
}
function finish(event: PointerEvent) {
  if (!drag || drag.id !== event.pointerId) return
  move(event)
  const range = draft.value
  cancel()
  if (range) emit('range', ...range)
}
function cancel() {
  drag = null
  draft.value = null
}
watch(() => [props.minimum, props.maximum], cancel)
const densityLine = computed(() => {
  let low = Infinity,
    high = -Infinity
  for (const reading of props.readings) {
    low = Math.min(low, reading.specific_gravity)
    high = Math.max(high, reading.specific_gravity)
  }
  return props.readings
    .map((reading) => {
      const x =
        ((reading.timestamp - props.minimum) /
          (props.maximum - props.minimum || 1)) *
        1000
      const y =
        high === low
          ? 40
          : 72 - ((reading.specific_gravity - low) / (high - low)) * 64
      return `${x},${y}`
    })
    .join(' ')
})
</script>
<template>
  <section class="time-navigator" aria-label="Navigazione temporale">
    <p>Densità SG · intera fermentazione</p>
    <div class="overview">
      <div ref="track" class="overview-track">
        <svg
          viewBox="0 0 1000 80"
          preserveAspectRatio="none"
          role="img"
          :aria-label="`Anteprima densità: ${readings.length} ${readings.length === 1 ? 'lettura' : 'letture'}`"
          class="density-preview"
        >
          <polyline
            :points="densityLine"
            fill="none"
            stroke="#1b6047"
            stroke-width="2"
            vector-effect="non-scaling-stroke"
          />
          <circle
            v-if="readings.length === 1"
            :cx="densityLine.split(',')[0]"
            cy="40"
            r="3"
            fill="#1b6047"
          />
        </svg>
        <div
          class="selected-window"
          role="slider"
          tabindex="0"
          aria-label="Periodo selezionato"
          :aria-describedby="helpId"
          :aria-valuemin="minimum"
          :aria-valuemax="maximum - (end - start)"
          :aria-valuenow="selected[0]"
          :aria-valuetext="`${date(selected[0]!)} – ${date(selected[1]!)}`"
          :style="{
            left: percent(selected[0]!),
            width: percent(minimum + selected[1]! - selected[0]!),
          }"
          @keydown="key($event, 'window')"
          @pointerdown="begin"
          @pointermove="move"
          @pointerup="finish"
          @pointercancel="cancel"
          @lostpointercapture="cancel"
        >
          <span class="window-grip" aria-hidden="true">↔</span>
        </div>
        <input
          type="range"
          aria-label="Inizio intervallo"
          :aria-describedby="helpId"
          :aria-valuetext="date(selected[0]!)"
          :min="minimum"
          :max="maximum"
          step="any"
          :value="selected[0]"
          @input="handle($event, 'start')"
          @keydown="key($event, 'start')"
        />
        <input
          type="range"
          aria-label="Fine intervallo"
          :aria-describedby="helpId"
          :aria-valuetext="date(selected[1]!)"
          :min="minimum"
          :max="maximum"
          step="any"
          :value="selected[1]"
          @input="handle($event, 'end')"
          @keydown="key($event, 'end')"
        />
      </div>
    </div>
    <p :id="helpId" class="navigator-help">
      Trascina le maniglie per gli estremi o la zona evidenziata per spostare il
      periodo. Tastiera: frecce, Pagina su/giù, Home e Fine.
    </p>
    <div class="history-navigation">
      <button
        v-for="hours in [1, 6, 24]"
        :key="hours"
        class="text-button"
        @click="emit('preset', hours)"
      >
        {{ hours }}h
      </button>
      <button class="text-button" @click="emit('preset', null)">Tutto</button>
      <button class="refresh" @click="emit('live')">Torna al live</button>
    </div>
    <p aria-label="Intervallo visualizzato">
      <time :datetime="new Date(start * 1000).toISOString()">{{
        date(start)
      }}</time>
      →
      <time :datetime="new Date(end * 1000).toISOString()">{{
        date(end)
      }}</time>
    </p>
    <p role="status">
      {{ following ? 'Inseguimento live' : 'Intervallo fermo' }}
    </p>
    <div class="history-navigation">
      <button
        class="text-button"
        @click="
          emit('range', start + (end - start) / 4, end - (end - start) / 4)
        "
      >
        Ingrandisci
      </button>
      <button
        class="text-button"
        @click="
          emit('range', start - (end - start) / 2, end + (end - start) / 2)
        "
      >
        Riduci
      </button>
      <button
        class="text-button"
        @click="
          emit('range', start - (end - start) / 2, end - (end - start) / 2)
        "
      >
        Sposta prima
      </button>
      <button
        class="text-button"
        @click="
          emit('range', start + (end - start) / 2, end + (end - start) / 2)
        "
      >
        Sposta dopo
      </button>
    </div>
  </section>
</template>
<style scoped>
.time-navigator {
  margin: 20px 0;
  overflow-wrap: anywhere;
}
.overview {
  height: 112px;
  padding: 12px 18px;
  border: 1px solid #b6c9bd;
  border-radius: 10px;
  background: #f4f7f3;
}
.overview-track {
  position: relative;
  height: 88px;
}
.density-preview {
  display: block;
  width: 100%;
  height: 80px;
}
.selected-window {
  position: absolute;
  top: 0;
  height: 88px;
  border: 1px solid #1b6047;
  background: #1b604722;
  cursor: grab;
  touch-action: none;
}
.selected-window:active {
  cursor: grabbing;
}
.selected-window:focus-visible {
  outline: 3px solid #bc4434;
  outline-offset: 3px;
}
.window-grip {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  min-width: 24px;
  text-align: center;
  background: #1b6047;
  color: white;
  border-radius: 3px;
}
input[type='range'] {
  position: absolute;
  top: 0;
  left: -12px;
  width: calc(100% + 24px);
  height: 64px;
  margin: 0;
  padding: 0;
  appearance: none;
  background: transparent;
  pointer-events: none;
}
input[type='range']::-webkit-slider-thumb {
  appearance: none;
  width: 24px;
  height: 64px;
  border: 2px solid #1b6047;
  border-radius: 6px;
  background: #fff;
  cursor: ew-resize;
  pointer-events: auto;
  touch-action: none;
}
input[type='range']::-moz-range-thumb {
  width: 20px;
  height: 60px;
  border: 2px solid #1b6047;
  border-radius: 6px;
  background: #fff;
  cursor: ew-resize;
  pointer-events: auto;
  touch-action: none;
}
input[type='range']:focus-visible {
  outline: none;
}
input[type='range']:focus-visible::-webkit-slider-thumb {
  outline: 3px solid #bc4434;
  outline-offset: 2px;
}
input[type='range']:focus-visible::-moz-range-thumb {
  outline: 3px solid #bc4434;
  outline-offset: 2px;
}
.navigator-help {
  font-size: 0.8rem;
  color: #52695c;
}
</style>
