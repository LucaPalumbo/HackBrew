import type { PillSnapshot } from './readings'

export type CommunicationClock = { now: number; timeout: number }
export type CommunicationStatus =
  PillSnapshot['communication_status'] | 'unconfirmed_timeout' | 'unknown'

export function pillCommunication(
  pill: PillSnapshot | undefined,
  clock: CommunicationClock | null,
  connected: boolean,
): CommunicationStatus {
  if (!pill) return 'unknown'
  if (!pill.last_received_at) return 'never_received'
  if (pill.communication_status === 'timed_out') return 'timed_out'
  if (!clock) return 'unknown'
  const received = new Date(pill.last_received_at).getTime() / 1000
  if (!Number.isFinite(received)) return 'unknown'
  if (clock.now - received >= clock.timeout)
    return connected ? 'timed_out' : 'unconfirmed_timeout'
  return 'receiving'
}
