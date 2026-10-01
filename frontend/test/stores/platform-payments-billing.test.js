import { createPinia, setActivePinia } from 'pinia'
import { usePlatformPaymentsStore } from '../../stores/platform-payments'

jest.mock('../../composables/usePlatformApi', () => {
  const mockGet = jest.fn()
  return {
    usePlatformApi: () => ({ get: mockGet }),
    __mockGet: mockGet,
  }
})

const { __mockGet: mockGet } = require('../../composables/usePlatformApi')

function deferred() {
  let resolve
  const promise = new Promise((nextResolve) => {
    resolve = nextResolve
  })
  return { promise, resolve }
}

describe('usePlatformPaymentsStore billing reads', () => {
  let store

  beforeEach(() => {
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2025-06-10T12:00:00.000Z'))
    setActivePinia(createPinia())
    store = usePlatformPaymentsStore()
    jest.clearAllMocks()
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  it('keeps the newer subscription when an older read arrives late', async () => {
    // Falla si la respuesta de un proyecto anterior reemplaza sus pagos actuales.
    const first = deferred()
    const second = deferred()
    mockGet.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const requestA = store.fetchProjectSubscription(101)
    const requestB = store.fetchProjectSubscription(202)
    second.resolve({
      data: { id: 202, payments: [{ id: 2020, status: 'pending' }] },
    })
    await requestB
    first.resolve({
      data: { id: 101, payments: [{ id: 1010, status: 'overdue' }] },
    })
    const oldResult = await requestA

    expect(oldResult).toEqual({ success: false, stale: true })
    expect(store.currentSubscription).toEqual({
      id: 202,
      payments: [{ id: 2020, status: 'pending' }],
    })
    expect(store.payments).toEqual([{ id: 2020, status: 'pending' }])
  })

  it('otherPayments retains future payments outside the urgent slot', () => {
    // Falla si el historial oculta un pago futuro que no es el cobro urgente actual.
    store.payments = [
      { id: 1, status: 'overdue', billing_period_start: '2025-06-01' },
      { id: 2, status: 'pending', due_date: '2025-09-01', billing_period_start: '2025-09-01' },
      { id: 3, status: 'paid', billing_period_start: '2025-05-01' },
    ]

    expect(store.otherPayments).toEqual([
      { id: 2, status: 'pending', due_date: '2025-09-01', billing_period_start: '2025-09-01' },
      { id: 3, status: 'paid', billing_period_start: '2025-05-01' },
    ])
  })

  it('keeps phases from the latest project after navigation', async () => {
    // Falla si las fases comerciales del proyecto anterior reemplazan las actuales.
    const first = deferred()
    const second = deferred()
    mockGet.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const requestA = store.fetchProjectPhases(301)
    const requestB = store.fetchProjectPhases(302)
    second.resolve({ data: [{ id: 3020, name: 'Fase de Proyecto B' }] })
    await requestB
    first.resolve({ data: [{ id: 3010, name: 'Fase de Proyecto A' }] })
    const oldResult = await requestA

    expect(oldResult).toEqual({ success: false, stale: true })
    expect(store.phases).toEqual([{ id: 3020, name: 'Fase de Proyecto B' }])
  })
})
