<script setup lang="ts">
import { current, nav, state, navigate } from './demo'
import ProtoIcon from './ProtoIcon.vue'
</script>
<template>
  <div class="p-monitor-shell">
    <aside class="p-monitor-rail">
      <a
        href="?variant=C"
        aria-label="Home HackBrew"
        @click.prevent="navigate('home')"
        ><ProtoIcon name="beer"
      /></a>
      <nav aria-label="Navigazione principale">
        <button
          v-for="item in nav"
          :key="item.id"
          :aria-label="item.label"
          :title="item.label"
          :class="{
            'p-current':
              state.page === item.id ||
              (item.id === (current?.end ? 'archive' : 'home') &&
                state.page === 'detail') ||
              (item.id === 'devices' && state.page === 'diagnostic'),
          }"
          @click="navigate(item.id)"
        >
          <ProtoIcon :name="item.icon" /><span>{{ item.label }}</span>
        </button>
      </nav>
    </aside>
    <div class="p-monitor-content">
      <header class="p-monitor-top">
        <a href="?variant=C" class="p-brand" @click.prevent="navigate('home')"
          >HackBrew <span>/ monitor</span></a
        >
        <div class="p-monitor-top-right">
          <span class="p-demo">C · dati demo</span
          ><button class="p-primary" @click="navigate('new')">
            <ProtoIcon name="plus" /><span>Nuova fermentazione</span>
          </button>
        </div>
      </header>
      <main class="p-main"><slot /></main>
    </div>
  </div>
</template>
