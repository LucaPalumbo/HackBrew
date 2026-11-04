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
  control_mode: 'monitor_only'
}

export type FermentationSummary = Fermentation & {
  latest_reading: Reading | null
  reading_count: number
}
