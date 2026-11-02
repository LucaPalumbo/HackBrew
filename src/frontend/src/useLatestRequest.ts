import { onUnmounted, ref } from 'vue'

export function useLatestRequest(failureMessage: string) {
  const loading = ref(false)
  const error = ref('')
  let controller: AbortController | undefined
  let revision = 0

  function invalidate() {
    revision += 1
    controller?.abort()
    controller = undefined
    loading.value = false
    error.value = ''
  }

  async function run<T>(
    request: (signal: AbortSignal) => Promise<T>,
    accept: (payload: T) => void,
  ): Promise<boolean> {
    controller?.abort()
    const current = new AbortController()
    controller = current
    const requestRevision = ++revision
    loading.value = true
    error.value = ''
    try {
      const payload = await request(
        AbortSignal.any([current.signal, AbortSignal.timeout(10000)]),
      )
      if (requestRevision !== revision) return false
      accept(payload)
      return true
    } catch {
      if (requestRevision === revision && !current.signal.aborted)
        error.value = failureMessage
      return false
    } finally {
      if (requestRevision === revision) loading.value = false
    }
  }

  onUnmounted(invalidate)
  return { loading, error, run, invalidate }
}
