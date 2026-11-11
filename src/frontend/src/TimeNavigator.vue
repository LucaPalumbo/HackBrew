<script setup lang="ts">
defineProps<{
  start: number
  end: number
  minimum: number
  maximum: number
  following: boolean
}>()
const emit = defineEmits<{
  range: [start: number, end: number]
  preset: [hours: number | null]
  live: []
}>()
const value = (event: Event) => Number((event.target as HTMLInputElement).value)
</script>
<template>
  <section class="time-navigator" aria-label="Navigazione temporale">
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
    <label
      >Inizio intervallo<input
        type="range"
        aria-label="Inizio intervallo"
        :min="minimum"
        :max="maximum"
        step="any"
        :value="start"
        @input="emit('range', Math.min(value($event), end), end)"
    /></label>
    <label
      >Fine intervallo<input
        type="range"
        aria-label="Fine intervallo"
        :min="minimum"
        :max="maximum"
        step="any"
        :value="end"
        @input="emit('range', start, Math.max(value($event), start))"
    /></label>
    <p aria-label="Intervallo visualizzato">
      {{ new Date(start * 1000).toISOString() }} →
      {{ new Date(end * 1000).toISOString() }} · Unix {{ start }}–{{ end }}
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
label {
  display: block;
  margin: 12px 0;
}
input {
  display: block;
  width: 100%;
}
</style>
