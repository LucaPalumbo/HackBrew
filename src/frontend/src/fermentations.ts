export type Fermentation = {
  id: string
  name: string
  pill_id: string
  pill_name: string
  pill_mac: string
  status: 'active' | 'concluded'
  started_at: string
  ended_at: string | null
}
