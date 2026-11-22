import type { Reading } from './readings'
import { measurementValue } from './measurements'
import type { Measurement, MeasurementKey } from './measurements'

export type ChartContext = Partial<
  Record<
    MeasurementKey,
    {
      before: Reading | null
      after: Reading | null
    }
  >
>
export type CurvePoint = {
  x: number
  y: number
  reading?: Reading
  context: boolean
}

export function curvePoints(
  readings: Reading[],
  metric: Measurement,
  context?: ChartContext,
  range?: [number, number],
): CurvePoint[] {
  const edges = context?.[metric.key]
  const samples = [
    ...(edges?.before ? [{ reading: edges.before, context: true }] : []),
    ...readings.map((reading) => ({ reading, context: false })),
    ...(edges?.after ? [{ reading: edges.after, context: true }] : []),
  ]
  const points: CurvePoint[] = samples.flatMap((sample) => {
    const y = measurementValue(sample.reading, metric.key)
    return y == null
      ? []
      : [{ ...sample, x: sample.reading.timestamp * 1000, y }]
  })
  if (!range) return points
  const first = range[0] * 1000,
    last = range[1] * 1000
  const clipped: CurvePoint[] = []
  const edge = (a: CurvePoint, b: CurvePoint, x: number): CurvePoint => {
    const fraction = (x - a.x) / (b.x - a.x)
    // These are drawing vertices, never Reading objects or tooltip candidates.
    return { x, y: a.y * (1 - fraction) + b.y * fraction, context: true }
  }
  for (let index = 0; index < points.length; index++) {
    const point = points[index]!,
      previous = points[index - 1]
    if (previous && previous.x < first && point.x > first)
      clipped.push(edge(previous, point, first))
    if (point.x >= first && point.x <= last) clipped.push(point)
    if (previous && previous.x < last && point.x > last)
      clipped.push(edge(previous, point, last))
  }
  return clipped
}
