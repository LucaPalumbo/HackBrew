export type Capability = 'heating' | 'cooling' | 'both'
export type ThermalMode = 'off' | 'heating' | 'cooling'

export type ThermalDevice = {
  id: string
  name: string
  capability: Capability
  base_url: string
  verification_status: 'unverified' | 'confirmed' | 'pending' | 'error'
  application_status: 'applied' | 'pending' | 'unknown' | 'timed_out' | null
  actual_mode: ThermalMode | null
  desired_mode: ThermalMode | null
  reported_capability: Capability | null
  confirmed_at: string | null
  checked_at: string | null
  applied_timeout_seconds: number | null
  applied_config_revision: number | null
  communication_error: string | null
  last_confirmation: {
    actual_mode: ThermalMode
    confirmed_at: string
  } | null
}

export const capabilityNames: Record<Capability, string> = {
  heating: 'Riscaldamento',
  cooling: 'Raffreddamento',
  both: 'Riscaldamento e raffreddamento',
}
export const modeNames: Record<ThermalMode, string> = {
  off: 'Spento',
  heating: 'Riscaldamento',
  cooling: 'Raffreddamento',
}
