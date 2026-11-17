<script setup lang="ts">
defineProps<{ name: 'home' | 'archive' | 'devices' | 'settings' | 'beer' }>()
const paths = {
  beer: 'M5 4h12v17H5zM17 7h4v9h-4M9 8v9m4-9v9',
  home: 'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
  archive: 'M4 7h16v14H4zM3 3h18v4H3zM9 11h6',
  devices: 'M7 3h5v14H7zM8 21h3M17 8h4v13h-4zM18 3v5',
  settings: 'M4 7h16M4 17h16M8 4v6M16 14v6',
}
</script>
<template>
  <svg
    class="navigation-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name]" />
  </svg>
</template>
