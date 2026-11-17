<script setup lang="ts">
import { current, nav, state, navigate } from './demo'
import ProtoIcon from './ProtoIcon.vue'
</script>
<template>
  <div class="p-console-shell">
    <aside class="p-console-sidebar">
      <a href="?variant=A" class="p-brand" @click.prevent="navigate('home')"
        ><span class="p-brand-symbol" aria-hidden="true">hb</span>HackBrew</a
      >
      <div class="p-sidebar-caption">IL TUO BIRRIFICIO</div>
      <nav aria-label="Navigazione principale">
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
          <ProtoIcon :name="item.icon" /><span>{{ item.label }}</span>
        </button>
      </nav>
      <button class="p-primary" @click="navigate('new')">
        <ProtoIcon name="plus" />Nuova fermentazione
      </button>
      <div class="p-sidebar-bottom">
        <span class="p-dot" /> Ambiente dimostrativo<small
          >Il tuo spazio per fare buona birra.</small
        >
      </div>
    </aside>
    <div class="p-console-main">
      <header class="p-console-top">
        <span
          >Il tuo birrificio
          <span class="p-breadcrumb"
            >/
            {{
              state.page === 'detail'
                ? 'Fermentazione'
                : (nav.find((item) => item.id === state.page)?.label ??
                  'Nuova fermentazione')
            }}</span
          ></span
        ><span class="p-demo">Prototipo A · dati demo</span>
      </header>
      <main class="p-main"><slot /></main>
    </div>
  </div>
</template>
