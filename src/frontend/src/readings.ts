export type Reading = {
  pill_id: string
  pill_mac: string
  temperature: number
  specific_gravity: number
  battery: number
  timestamp: number
  received_at: string
  valid: boolean | null
  gravity_velocity: number | null
  accel_x: number | null
  accel_y: number | null
  accel_z: number | null
}

export type PillSnapshot = {
  id: string
  name: string
  mac: string
  reading: Reading | null
  last_received_at: string | null
}
