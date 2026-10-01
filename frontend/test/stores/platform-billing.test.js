import { createPinia, setActivePinia } from 'pinia'
import { usePlatformBillingStore } from '../../stores/platform-billing'

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
  let reject
  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve
    reject = nextReject
  })
  return { promise, resolve, reject }
}

describe('usePlatformBillingStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformBillingStore()
    jest.clearAllMocks()
  })

  it('clears the account immediately when a second fetch starts', async () => {
    // Falla si una cuenta anterior queda expuesta mientras se consulta otra.
    store.account = { id: 41, title: 'Cuenta anterior' }
    const pending = deferred()
    mockGet.mockReturnValueOnce(pending.promise)

    const request = store.fetchAccount(42)

    expect(store.account).toBeNull()
    expect(store.loading.account).toBe(true)

    pending.resolve({ data: { id: 42, title: 'Cuenta nueva' } })
    await request
  })

  it('keeps the newer account when an older success arrives late', async () => {
    // Falla si la respuesta lenta A reemplaza la cuenta B ya mostrada.
    const first = deferred()
    const second = deferred()
    mockGet.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const requestA = store.fetchAccount(10)
    const requestB = store.fetchAccount(20)
    second.resolve({ data: { id: 20, title: 'Cuenta B' } })
    await requestB
    first.resolve({ data: { id: 10, title: 'Cuenta A' } })
    const oldResult = await requestA

    expect(oldResult).toEqual({ success: false, stale: true })
    expect(store.account).toEqual({ id: 20, title: 'Cuenta B' })
  })

  it('keeps the latest request loading after an older failure', async () => {
    // Falla si el error de A apaga el indicador de carga de B.
    const first = deferred()
    const second = deferred()
    mockGet.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const requestA = store.fetchAccount(10)
    const requestB = store.fetchAccount(20)
    first.reject({ response: { data: { detail: 'Error de cuenta A' } } })
    const oldResult = await requestA

    expect(oldResult).toEqual({ success: false, stale: true })
    expect(store.loading.account).toBe(true)

    second.resolve({ data: { id: 20, title: 'Cuenta B' } })
    await requestB

    expect(store.loading.account).toBe(false)
    expect(store.account).toEqual({ id: 20, title: 'Cuenta B' })
  })

  it('replaces a failed account read after retry', async () => {
    // Falla si un fallo conserva el detalle anterior o bloquea una nueva lectura.
    store.account = { id: 10, title: 'Detalle obsoleto' }
    mockGet
      .mockRejectedValueOnce({ response: { data: { detail: 'No se pudo leer la cuenta' } } })
      .mockResolvedValueOnce({ data: { id: 11, title: 'Detalle recuperado' } })

    const failed = await store.fetchAccount(10)

    expect(failed).toEqual({ success: false, message: 'No se pudo leer la cuenta' })
    expect(store.account).toBeNull()
    expect(store.errors.account).toBe('No se pudo leer la cuenta')

    const retried = await store.fetchAccount(11)

    expect(retried).toEqual({ success: true, data: { id: 11, title: 'Detalle recuperado' } })
    expect(store.errors.account).toBe('')
    expect(store.account).toEqual({ id: 11, title: 'Detalle recuperado' })
  })

  it('keeps options empty after navigation clears a pending request', async () => {
    // Falla si las opciones del proyecto anterior reaparecen al volver al listado.
    const pending = deferred()
    mockGet.mockReturnValueOnce(pending.promise)

    const request = store.fetchOptions(77)
    store.clear('options')
    pending.resolve({ data: { project_name: 'Proyecto anterior', contracts: [{ id: 7 }] } })
    const result = await request

    expect(result).toEqual({ success: false, stale: true })
    expect(store.options).toBeNull()
  })
})
