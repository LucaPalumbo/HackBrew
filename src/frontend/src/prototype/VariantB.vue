<script setup lang="ts">
import { current, nav, state, navigate } from './demo'
import ProtoIcon from './ProtoIcon.vue'
</script>
<template>
  <div class="p-journal-shell">
    <header class="p-journal-top">
      <a href="?variant=B" class="p-brand" @click.prevent="navigate('home')"
        ><ProtoIcon name="beer" />HackBrew<span class="p-brand-sub"
          >IL DIARIO DELLE TUE BIRRE</span
        ></a
      ><span class="p-demo">Prototipo B · dati demo</span
      ><button class="p-primary" @click="navigate('new')">
        <ProtoIcon name="plus" />Nuova fermentazione
      </button>
    </header>
    <nav class="p-journal-nav" aria-label="Navigazione principale">
      <button
        v-for="item in nav"
        :key="item.id"
        :class="{
          'p-current':
            state.page === item.id ||
            (item.id === (current?.end ? 'archive' : 'home') &&
              state.page === 'detail') ||
            (item.id === 'devices' && state.page === 'diagnostic'),
        }"
        @click="navigate(item.id)"
      >
        <ProtoIcon :name="item.icon" />{{ item.label }}
      </button>
    </nav>
    <main class="p-main"><slot /></main>
    <footer class="p-journal-footer">
      HackBrew <span>Ogni birra ha la sua storia.</span>
    </footer>
  </div>
</template>
