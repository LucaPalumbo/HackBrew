// Throwaway UI comparison: three layouts on the existing route, ?variant=A/B/C.
import { computed, reactive } from 'vue'

export type Variant = 'A' | 'B' | 'C'
export type Metric =
  | 'temperature'
  | 'gravity'
  | 'battery'
  | 'velocity'
  | 'accel_x'
  | 'accel_y'
  | 'accel_z'
export type Sample = { time: number } & Record<Metric, number | null>
export type Cycle = {
  id: string
  name: string
  start: number
  end: number | null
  pill: string
  mode: string
  equipment: string[]
  min: number
  max: number
  hysteresis: number
  stale: boolean
  history: string[]
  samples: Sample[]
}
export type Device = {
  id: string
  name: string
  type: string
  address: string
  pending: boolean
}
export const metricLabels: Record<Metric, string> = {
  temperature: 'Temperatura',
  gravity: 'Densità',
  battery: 'Batteria',
  velocity: 'Velocità',
  accel_x: 'Accelerometro X',
  accel_y: 'Accelerometro Y',
  accel_z: 'Accelerometro Z',
}
export const modes = [
  'Solo monitoraggio',
  'Solo riscaldamento',
  'Solo raffreddamento',
  'Riscaldamento e raffreddamento separati',
  'Dispositivo combinato',
]
export const demoNow = Date.UTC(2026, 10, 16, 12)
const day = 86400000
function samples(start: number, end: number, index: number): Sample[] {
  return Array.from({ length: 181 }, (_, i) => ({
    time: start + ((end - start) * i) / 180,
    temperature: Number(
      (
        19.2 +
        index * 0.7 +
        Math.sin(i / 9) * 0.28 +
        Math.cos(i / 4) * 0.06
      ).toFixed(3),
    ),
    gravity: Number(
      (
        1.012 +
        index * 0.002 +
        0.043 * Math.exp(-i / 54) +
        Math.sin(i / 11) * 0.0003
      ).toFixed(6),
    ),
    battery: Number((92 - i * 0.09 - index * 12).toFixed(3)),
    velocity:
      i % 17 === 0 ? null : Number((-0.04 * Math.exp(-i / 70)).toFixed(6)),
    accel_x: Number((0.12 + Math.sin(i / 7) * 0.03).toFixed(6)),
    accel_y: Number((-0.04 + Math.cos(i / 8) * 0.02).toFixed(6)),
    accel_z: Number((0.97 + Math.sin(i / 13) * 0.01).toFixed(6)),
  }))
}
function seedCycles(): Cycle[] {
  return [
    'Pacific IPA',
    'Saison di casa',
    'Midnight Porter',
    'Amber Ale',
    'Pils di settembre',
    'Summer Wheat',
    'Bitter classica',
  ].map((name, i) => {
    const end = i < 3 ? null : demoNow - (i - 2) * 21 * day
    const start = (end ?? demoNow) - (i === 1 ? 3 : 6) * day
    return {
      id: ['ipa', 'saison', 'porter', 'amber', 'pils', 'wheat', 'bitter'][i]!,
      name,
      start,
      end,
      pill: `pill-${i < 3 ? i + 1 : 1}`,
      mode: i === 1 ? modes[0]! : i === 2 ? modes[4]! : modes[3]!,
      equipment:
        i === 1
          ? []
          : i === 0
            ? ['heat-1', 'cool-1']
            : i === 2
              ? ['both-1']
              : [],
      min: 19 + i * 0.5,
      max: 20 + i * 0.5,
      hysteresis: 0.3,
      stale: i === 2,
      history: ['Regolazione impostata all’avvio della fermentazione.'],
      samples: samples(
        start,
        end ?? (i === 2 ? demoNow - 4 * 3600000 : demoNow),
        i,
      ),
    }
  })
}
function seedDevices(): Device[] {
  return [
    ...['Ambra', 'Verde', 'Blu', 'Rossa'].map((name, i) => ({
      id: `pill-${i + 1}`,
      name: `Pillola ${name}`,
      type: 'pill',
      address: `AA:BB:CC:00:00:0${i + 1}`,
      pending: false,
    })),
    {
      id: 'heat-1',
      name: 'Fascia riscaldante',
      type: 'heating',
      address: 'http://fascia.local',
      pending: false,
    },
    {
      id: 'cool-1',
      name: 'Frigo fermentazione',
      type: 'cooling',
      address: 'http://frigo.local',
      pending: false,
    },
    {
      id: 'both-1',
      name: 'Camera Porter',
      type: 'both',
      address: 'http://camera.local',
      pending: false,
    },
    {
      id: 'heat-2',
      name: 'Fascia di riserva',
      type: 'heating',
      address: 'http://riserva.local',
      pending: false,
    },
    {
      id: 'both-2',
      name: 'Camera libera',
      type: 'both',
      address: 'http://camera2.local',
      pending: false,
    },
  ]
}
const params = new URLSearchParams(window.location.search)
export const state = reactive({
  variant: (['A', 'B', 'C'].includes(params.get('variant') ?? '')
    ? params.get('variant')
    : 'A') as Variant,
  page: params.get('fermentation') ? 'detail' : (params.get('page') ?? 'home'),
  selected: params.get('fermentation') ?? params.get('pill') ?? 'ipa',
  tab: 'trend',
  cycles: seedCycles(),
  devices: seedDevices(),
  retired: [] as Device[],
  scenario: 'active',
  notice: '',
  timeout: 3,
  deviceTab: 'pill',
  from: demoNow - 6 * day,
  to: demoNow,
  live: true,
  metrics: ['temperature', 'gravity'] as Metric[],
  raw: false,
})
const diagnosticCycle: Cycle = {
  ...seedCycles()[0]!,
  id: 'diagnostic',
  name: 'Pillola libera',
  mode: modes[0]!,
  equipment: [],
  samples: samples(demoNow - day, demoNow, 0),
}
export const current = computed(() => {
  if (state.page === 'diagnostic')
    return {
      ...diagnosticCycle,
      name: deviceName(state.selected),
      pill: state.selected,
      start: diagnosticCycle.samples[0]!.time,
    }
  return state.cycles.find((cycle) => cycle.id === state.selected)
})
export const active = computed(() => state.cycles.filter((cycle) => !cycle.end))
export const completed = computed(() =>
  state.cycles.filter((cycle) => cycle.end),
)
export const nav = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'archive', label: 'Archivio', icon: 'archive' },
  { id: 'devices', label: 'Dispositivi', icon: 'devices' },
  { id: 'settings', label: 'Impostazioni', icon: 'settings' },
]
export const variantNames = {
  A: 'Console operativa',
  B: 'Diario di birrificazione',
  C: 'Monitor compatto',
}
export function date(time: number, short = false) {
  return new Intl.DateTimeFormat('it-IT', {
    day: 'numeric',
    month: 'short',
    ...(short ? {} : { year: 'numeric' }),
  }).format(time)
}
export function timestamp(time: number) {
  return new Intl.DateTimeFormat('it-IT', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(time)
}
export function latest(cycle: Cycle) {
  return cycle.samples[cycle.samples.length - 1]!
}
export function owner(device: Device) {
  return state.cycles.find(
    (cycle) =>
      !cycle.end &&
      (cycle.pill === device.id || cycle.equipment.includes(device.id)),
  )
}
export function free(device: Device) {
  return !owner(device) && !device.pending
}
export function deviceName(id: string) {
  return (
    [...state.devices, ...state.retired].find((device) => device.id === id)
      ?.name ?? 'Dispositivo rimosso'
  )
}
function syncUrl(replace = false) {
  const url = new URL(window.location.href)
  url.searchParams.set('variant', state.variant)
  url.searchParams.delete('pill')
  url.searchParams.delete('page')
  url.searchParams.delete('fermentation')
  if (state.page === 'diagnostic') {
    url.searchParams.set('page', 'diagnostic')
    url.searchParams.set('pill', state.selected)
  } else if (state.page === 'detail')
    url.searchParams.set('fermentation', state.selected)
  else if (state.page !== 'home') url.searchParams.set('page', state.page)
  window.history[replace ? 'replaceState' : 'pushState'](null, '', url)
}
export function navigate(page: string, id?: string) {
  state.page = page
  if (id) {
    state.selected = id
    state.tab = 'trend'
    state.live = true
    const cycle = current.value!
    state.from = cycle.start
    state.to = latest(cycle).time
    state.metrics = ['temperature', 'gravity']
  }
  state.raw = false
  syncUrl()
  window.scrollTo({ top: 0 })
}
export function switchVariant(direction: number) {
  const variants: Variant[] = ['A', 'B', 'C']
  state.variant =
    variants[(variants.indexOf(state.variant) + direction + 3) % 3]!
  syncUrl(true)
  console.info('HackBrew UI prototype', {
    variant: state.variant,
    page: state.page,
    selected: state.selected,
    tab: state.tab,
    scenario: state.scenario,
    window: [state.from, state.to],
    series: [...state.metrics],
    cycles: state.cycles,
    devices: state.devices,
  })
}
export function restoreUrl() {
  const query = new URLSearchParams(window.location.search)
  state.variant = (query.get('variant') ?? 'A') as Variant
  navigateFromHistory(query)
}
function navigateFromHistory(query: URLSearchParams) {
  state.page = query.get('fermentation')
    ? 'detail'
    : (query.get('page') ?? 'home')
  state.selected = query.get('fermentation') ?? query.get('pill') ?? 'ipa'
  const cycle = current.value
  if (cycle) {
    state.from = cycle.start
    state.to = latest(cycle).time
  }
  state.raw = false
}
export function scenario(value: string) {
  state.scenario = value
  state.retired = []
  state.devices = seedDevices()
  state.cycles = seedCycles()
  if (value === 'archive')
    state.cycles = state.cycles.filter((cycle) => cycle.end)
  if (value === 'empty') {
    state.cycles = []
    state.devices = []
  }
  navigate('home')
  state.notice =
    'Scenario dimostrativo aggiornato. Le modifiche locali sono state azzerate.'
}
export function addReading() {
  const cycle = current.value
  if (!cycle || cycle.end) return
  const previous = latest(cycle)
  cycle.samples.push({
    ...previous,
    time: previous.time + 600000,
    temperature: Number(((previous.temperature ?? 19) + 0.04).toFixed(3)),
    gravity: Number(((previous.gravity ?? 1.02) - 0.0001).toFixed(6)),
  })
  if (state.live) {
    const duration = state.to - state.from
    state.to = latest(cycle).time
    state.from = Math.max(cycle.start, state.to - duration)
  }
  state.notice = state.live
    ? 'Nuova lettura dimostrativa: grafico aggiornato.'
    : 'Nuova lettura ricevuta. La finestra in esame è rimasta ferma.'
}
if (current.value) {
  state.from = current.value.start
  state.to = latest(current.value).time
}
