import type { PointStyle } from 'chart.js'
import type { Reading } from './readings'

export type MeasurementKey =
  | 'temperature'
  | 'specific_gravity'
  | 'battery'
  | 'gravity_velocity'
  | 'accel_x'
  | 'accel_y'
  | 'accel_z'
export type MeasurementScale =
  'temperature' | 'density' | 'battery' | 'velocity' | 'acceleration'
export type Measurement = {
  key: MeasurementKey
  label: string
  unit: string
  scale: MeasurementScale
  color: string
  dash: number[]
  marker: PointStyle
}

export const measurements: Measurement[] = [
  {
    key: 'temperature',
    label: 'Temperatura °C',
    unit: '°C',
    scale: 'temperature',
    color: '#bc4434',
    dash: [],
    marker: 'circle',
  },
  {
    key: 'specific_gravity',
    label: 'Densità SG',
    unit: 'SG',
    scale: 'density',
    color: '#1b6047',
    dash: [8, 3],
    marker: 'rect',
  },
  {
    key: 'battery',
    label: 'Batteria %',
    unit: '%',
    scale: 'battery',
    color: '#275eaa',
    dash: [3, 3],
    marker: 'triangle',
  },
  {
    key: 'gravity_velocity',
    label: 'Velocità densità · punti SG/giorno',
    unit: 'punti SG/giorno',
    scale: 'velocity',
    color: '#7751a3',
    dash: [10, 3, 2, 3],
    marker: 'rectRot',
  },
  {
    key: 'accel_x',
    label: 'Accelerazione X · unità non specificata',
    unit: 'unità non specificata',
    scale: 'acceleration',
    color: '#007f83',
    dash: [],
    marker: 'crossRot',
  },
  {
    key: 'accel_y',
    label: 'Accelerazione Y · unità non specificata',
    unit: 'unità non specificata',
    scale: 'acceleration',
    color: '#8a640e',
    dash: [6, 3],
    marker: 'star',
  },
  {
    key: 'accel_z',
    label: 'Accelerazione Z · unità non specificata',
    unit: 'unità non specificata',
    scale: 'acceleration',
    color: '#af4580',
    dash: [2, 3],
    marker: 'cross',
  },
]

export const measurementScales: Array<{
  id: MeasurementScale
  label: string
  position: 'left' | 'right'
}> = [
  { id: 'temperature', label: 'Temperatura · °C', position: 'left' },
  { id: 'density', label: 'Densità · SG', position: 'left' },
  { id: 'battery', label: 'Batteria · %', position: 'right' },
  { id: 'velocity', label: 'Velocità · punti SG/giorno', position: 'right' },
  {
    id: 'acceleration',
    label: 'Accelerazioni · unità non specificata',
    position: 'right',
  },
]

export function measurementValue(
  reading: Reading,
  key: MeasurementKey,
): number | null {
  return key === 'gravity_velocity' && reading.valid === false
    ? null
    : reading[key]
}

export function formatMeasurement(value: number, key: MeasurementKey): string {
  const text = String(value)
  if (key === 'specific_gravity' && !text.includes('e')) {
    const [whole, fraction = ''] = text.split('.')
    return `${whole}.${fraction.padEnd(3, '0')}`
  }
  if (key === 'temperature' && !text.includes('.') && !text.includes('e'))
    return `${text},0`
  return text.replace('.', ',')
}

export function exactMeasurement(
  reading: Reading,
  key: MeasurementKey,
): string {
  const value = measurementValue(reading, key)
  if (value === null)
    return key === 'gravity_velocity' && reading.valid === false
      ? 'Non disponibile (velocità non valida)'
      : 'Non disponibile'
  return formatMeasurement(value, key)
}
