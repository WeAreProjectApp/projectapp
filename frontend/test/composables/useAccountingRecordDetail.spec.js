jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn() }))

import { effectScope, nextTick, ref } from 'vue'
import { get_request } from '~/stores/services/request_http'
import { useAccountingRecordDetail } from '~/composables/useAccountingRecordDetail'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve
    reject = nextReject
  })
  return { promise, resolve, reject }
}

function createDetail({ id = 7, isOpen = true } = {}) {
  const recordId = ref(id)
  const open = ref(isOpen)
  const scope = effectScope()
  let detail
  scope.run(() => { detail = useAccountingRecordDetail('accounting/pocket/', recordId, open) })
  return { ...detail, recordId, open, stop: () => scope.stop() }
}

async function settle() {
  await Promise.resolve()
  await nextTick()
}

describe('useAccountingRecordDetail', () => {
  let detail

  beforeEach(() => { jest.clearAllMocks() })
  afterEach(() => { detail?.stop() })

  // Bug caught: a closed detail caused an unnecessary request for a hidden modal.
  it('does not request a record while its detail is closed', async () => {
    // quality: allow-negation-only (the public contract is deliberately that a hidden detail has no request or record)
    detail = createDetail({ isOpen: false })
    await settle()

    expect(get_request).not.toHaveBeenCalled()
    expect(detail.record.value).toBeNull()
  })

  // Bug caught: detail URLs omitted the final slash and were redirected before loading.
  it('loads the selected record from its canonical endpoint', async () => {
    get_request.mockResolvedValueOnce({ data: { id: 7, concept: 'Abono de Kore' } })
    detail = createDetail()
    await settle()

    expect(get_request).toHaveBeenCalledWith('accounting/pocket/7/')
    expect(detail.record.value).toEqual({ id: 7, concept: 'Abono de Kore' })
    expect(detail.loading.value).toBe(false)
  })

  // Bug caught: an unavailable movement was reported as a generic network error.
  it('classifies a 404 as a missing record', async () => {
    get_request.mockRejectedValueOnce({ response: { status: 404 } })
    detail = createDetail()
    await settle()

    expect(detail.error.value).toBe('missing')
    expect(detail.loading.value).toBe(false)
  })

  // Bug caught: a transport failure left the modal indefinitely loading.
  it('classifies a non-404 failure as retryable', async () => {
    get_request.mockRejectedValueOnce(new Error('offline'))
    detail = createDetail()
    await settle()

    expect(detail.error.value).toBe('failed')
    expect(detail.loading.value).toBe(false)
  })

  // Bug caught: retry preserved an old movement while loading the replacement response.
  it('reloads a failed record into the fetched detail', async () => {
    get_request
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ data: { id: 7, concept: 'Abono recuperado' } })
    detail = createDetail()
    await settle()

    await detail.reload()

    expect(get_request).toHaveBeenNthCalledWith(2, 'accounting/pocket/7/')
    expect(detail.error.value).toBe('')
    expect(detail.record.value).toEqual({ id: 7, concept: 'Abono recuperado' })
  })

  // Bug caught: a slow first record overwrote the movement selected immediately afterwards.
  it('ignores a superseded response after the selected record changes', async () => {
    const first = deferred()
    get_request
      .mockImplementationOnce(() => first.promise)
      .mockResolvedValueOnce({ data: { id: 8, concept: 'Movimiento actual' } })
    detail = createDetail()
    detail.recordId.value = 8
    await settle()
    first.resolve({ data: { id: 7, concept: 'Movimiento anterior' } })
    await settle()

    expect(detail.record.value).toEqual({ id: 8, concept: 'Movimiento actual' })
  })

  // Bug caught: a response finishing after the modal unmounted changed disposed state.
  it('ignores a response after its scope is disposed', async () => {
    const request = deferred()
    get_request.mockImplementationOnce(() => request.promise)
    detail = createDetail()
    detail.stop()
    request.resolve({ data: { id: 7, concept: 'No debe aparecer' } })
    await settle()

    expect(detail.record.value).toBeNull()
    expect(detail.loading.value).toBe(true)
  })
})
