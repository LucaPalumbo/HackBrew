export type DeviceTimeoutSync = {
  id: string
  name: string
  desired_revision: number
  desired_timeout_seconds: number
  status: 'pending' | 'confirmed' | 'error'
  applied_revision: number | null
  applied_timeout_seconds: number | null
  confirmed_at: string | null
  last_attempt_at: string | null
  error: string | null
}

export type GlobalSettings = {
  communication_timeout_seconds: number
  revision: number
  updated_at: string
  devices: DeviceTimeoutSync[]
}
