import { onUnmounted, ref } from 'vue'

export function useLatestRequest(failureMessage: string) {
  const loading = ref(false)
  const error = ref('')
  let controller: AbortController | undefined
  let revision = 0
  let inFlight = false
  let pendingRefresh: (() => Promise<unknown>) | undefined

  function invalidate() {
    revision += 1
    controller?.abort()
    controller = undefined
    inFlight = false
    pendingRefresh = undefined
    loading.value = false
    error.value = ''
  }

  async function run<T>(
    request: (signal: AbortSignal) => Promise<T>,
    accept: (payload: T) => void,
    background = false,
  ): Promise<boolean> {
    controller?.abort()
    const current = new AbortController()
    controller = current
    pendingRefresh = undefined
    inFlight = true
    const requestRevision = ++revision
    loading.value = !background
    if (!background) error.value = ''
    try {
      const payload = await request(
        AbortSignal.any([current.signal, AbortSignal.timeout(10000)]),
      )
      if (requestRevision !== revision) return false
      accept(payload)
      error.value = ''
      return true
    } catch {
      if (requestRevision === revision && !current.signal.aborted)
        error.value = failureMessage
      return false
    } finally {
      if (requestRevision === revision) {
        inFlight = false
        loading.value = false
        flushRefresh()
      }
    }
  }

  function refresh(request: () => Promise<unknown>) {
    if (inFlight) pendingRefresh = request
    else void request()
  }

  function flushRefresh() {
    const queued = pendingRefresh
    pendingRefresh = undefined
    if (queued) void queued()
  }

  onUnmounted(invalidate)
  return { loading, error, run, invalidate, refresh }
}
