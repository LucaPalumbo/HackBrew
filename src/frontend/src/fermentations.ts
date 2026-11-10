import type { Reading } from './readings'

export type Fermentation = {
  id: string
  name: string
  pill_id: string
  pill_name: string
  pill_mac: string
  status: 'active' | 'concluded'
  started_at: string
  ended_at: string | null
  control_mode: 'monitor_only' | 'heating'
  heater_id?: string
  heater_name?: string
  heater_reserved?: boolean
  temperature_min?: number
  temperature_max?: number
  hysteresis?: number
  regulation?: {
    status:
      | 'waiting'
      | 'pending'
      | 'heating'
      | 'idle'
      | 'suspended'
      | 'stopping'
      | 'stopped'
    reason: string | null
    desired_mode: 'off' | 'heating'
    actual_mode: 'off' | 'heating' | null
    error: string | null
    confirmed_at: string | null
  }
}

export const regulationNames = {
  waiting: 'In attesa di temperatura',
  pending: 'Comando in attesa di conferma',
  heating: 'Riscaldamento attivo',
  idle: 'In attesa nella fascia termica',
  suspended: 'Regolazione sospesa',
  stopping: 'Spegnimento in attesa di conferma',
  stopped: 'Spegnimento confermato',
}

export type FermentationSummary = Fermentation & {
  latest_reading: Reading | null
  reading_count: number
}
