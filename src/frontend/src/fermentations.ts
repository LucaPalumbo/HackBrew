import type { Reading } from './readings'
import type { Capability, ThermalMode } from './thermalDevices'

export const controlModeNames = {
  monitor_only: 'Solo monitoraggio',
  heating: 'Riscaldamento',
  cooling: 'Raffreddamento',
  heating_cooling: 'Riscaldamento e raffreddamento separati',
  combined: 'Dispositivo combinato',
}

export type ThermalAssignment = {
  id: string
  name: string
  capability: Capability
  role: 'heater' | 'cooler' | 'combined'
}
export type DeviceControl = {
  desired_mode: ThermalMode
  actual_mode: ThermalMode | null
  confirmed_at: string | null
  error: string | null
  reserved: boolean
}

export type Fermentation = {
  id: string
  name: string
  pill_id: string
  pill_name: string
  pill_mac: string
  status: 'active' | 'concluded'
  started_at: string
  ended_at: string | null
  control_mode: keyof typeof controlModeNames
  heater_id?: string | null
  heater_name?: string | null
  heater_reserved?: boolean
  cooler_id?: string | null
  combined_id?: string | null
  devices?: ThermalAssignment[]
  reserved_device_ids?: string[]
  thermal_reserved?: boolean
  temperature_min?: number
  temperature_max?: number
  hysteresis?: number
  regulation?: {
    status:
      | 'waiting'
      | 'pending'
      | 'heating'
      | 'cooling'
      | 'idle'
      | 'suspended'
      | 'stopping'
      | 'stopped'
    reason: string | null
    desired_mode: ThermalMode
    actual_mode: ThermalMode | null
    devices: Record<string, DeviceControl>
    error: string | null
    confirmed_at: string | null
  }
}

export const regulationNames = {
  waiting: 'In attesa di temperatura',
  pending: 'Comando in attesa di conferma',
  heating: 'Riscaldamento attivo',
  cooling: 'Raffreddamento attivo',
  idle: 'In attesa nella fascia termica',
  suspended: 'Regolazione sospesa',
  stopping: 'Spegnimento in attesa di conferma',
  stopped: 'Spegnimento confermato',
}

export type FermentationSummary = Fermentation & {
  latest_reading: Reading | null
  reading_count: number
}
