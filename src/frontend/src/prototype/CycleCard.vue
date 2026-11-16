<script setup lang="ts">
import { date, latest, navigate, type Cycle } from './demo'
import ProtoIcon from './ProtoIcon.vue'
defineProps<{ cycle: Cycle; prominent?: boolean }>()
</script>
<template>
  <button
    class="p-cycle"
    :class="{
      'p-cycle-active': !cycle.end,
      'p-featured': prominent,
      'p-cycle-alert': cycle.stale && !cycle.end,
    }"
    @click="navigate('detail', cycle.id)"
  >
    <div class="p-card-heading">
      <span class="p-batch-mark"><ProtoIcon name="beer" /></span
      ><span
        class="p-status"
        :class="{ 'p-warning': cycle.stale && !cycle.end }"
        >{{
          cycle.end
            ? 'Conclusa'
            : cycle.stale
              ? 'Regolazione sospesa'
              : 'In fermentazione'
        }}</span
      ><ProtoIcon name="arrow" />
    </div>
    <div class="p-card-title">
      <span class="p-overline">{{
        cycle.end ? 'Dal tuo archivio' : 'Fermentazione attiva'
      }}</span>
      <h2>{{ cycle.name }}</h2>
      <p>
        {{ date(cycle.start, true) }}
        {{ cycle.end ? `— ${date(cycle.end)}` : '→ in corso' }}
      </p>
    </div>
    <div class="p-card-readings">
      <div>
        <span>Temperatura{{ cycle.end ? ' finale' : '' }}</span
        ><strong
          >{{ latest(cycle).temperature?.toFixed(1) }}<small> °C</small></strong
        >
      </div>
      <div>
        <span>Densità{{ cycle.end ? ' finale' : '' }}</span
        ><strong
          >{{ latest(cycle).gravity?.toFixed(3) }}<small> SG</small></strong
        >
      </div>
      <div v-if="!cycle.end" class="p-battery">
        <span>Batteria pillola</span
        ><strong
          >{{ latest(cycle).battery?.toFixed(0) }}<small> %</small></strong
        >
      </div>
    </div>
    <div class="p-card-footer">
      <span>{{
        cycle.end
          ? 'Visualizza il riepilogo'
          : cycle.stale
            ? 'Pillola non raggiungibile · dispositivi da verificare'
            : cycle.mode === 'Solo monitoraggio'
              ? 'Solo monitoraggio · nessuna regolazione'
              : `Regolazione attiva · ${cycle.min}–${cycle.max} °C`
      }}</span
      ><span class="p-open-label">Apri <ProtoIcon name="arrow" /></span>
    </div>
  </button>
</template>
