<script setup lang="ts">
defineProps<{ name: string }>()
const paths: Record<string, string> = {
  home: 'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
  archive: 'M4 7h16v14H4zM3 3h18v4H3zM9 11h6',
  devices: 'M7 3h5v14H7zM8 21h3M17 8h4v13h-4zM18 3v5',
  settings: 'M4 7h16M4 17h16M8 4v6M16 14v6',
  plus: 'M12 5v14M5 12h14',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  beer: 'M5 4h12v17H5zM17 7h4v9h-4M9 8v9m4-9v9',
  back: 'M19 12H5m5-5-5 5 5 5',
  close: 'm6 6 12 12M6 18 18 6',
  download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  check: 'm5 12 4 4L19 6',
  clock: 'M12 7v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  chart: 'M3 3v18h18M6 16l4-6 4 3 6-8',
}
</script>
<template>
  <svg
    class="p-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] ?? paths.beer" />
  </svg>
</template>
