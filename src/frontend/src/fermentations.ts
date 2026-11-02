export type Fermentation = {
  id: string
  name: string
  status: 'active' | 'concluded'
  started_at: string
  ended_at: string | null
}
