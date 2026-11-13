import { createPinia, setActivePinia } from 'pinia'
import { useMonitoringStore } from '../../stores/monitoring'

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
}))

const { get_request, create_request } = require('../../stores/services/request_http')

const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

describe('useMonitoringStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useMonitoringStore()
    jest.clearAllMocks()
  })

  it('keeps the newer list result when an older request resolves last', async () => {
    // Falla si una recarga anterior vuelve a reemplazar los filtros más nuevos.
    const first = deferred()
    const second = deferred()
    get_request.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const firstLoad = store.list({ state: 'pending' })
    const secondLoad = store.list({ state: 'resolved' })
    second.resolve({ data: { results: [{ id: 22, title: 'Caso resuelto' }], count: 1, page_size: 50 } })
    await secondLoad
    first.resolve({ data: { results: [{ id: 11, title: 'Caso pendiente' }], count: 9, page_size: 25 } })
    await firstLoad

    expect(store.records).toEqual([{ id: 22, title: 'Caso resuelto' }])
    expect(store.count).toBe(1)
    expect(store.pageSize).toBe(50)
    expect(store.loading).toBe(false)
  })

  it('shows the API detail when the current list request fails', async () => {
    // Falla si un error de carga queda oculto o deja el indicador activo.
    get_request.mockRejectedValue({ response: { data: { detail: 'Sin permiso para ver los casos.' } } })

    await store.list({})

    expect(store.error).toBe('Sin permiso para ver los casos.')
    expect(store.loading).toBe(false)
  })

  it('clears stale cases when the current list request fails', async () => {
    // Falla si una falla deja visibles casos que no pertenecen al filtro actual.
    store.records = [{ id: 4, title: 'Caso de un filtro anterior' }]
    store.count = 1
    get_request.mockRejectedValue({ response: { data: { detail: 'Sin permiso para ver los casos.' } } })

    await store.list({ state: 'resolved' })

    expect(store.records).toEqual([])
    expect(store.count).toBe(0)
  })

  it('keeps page sources with their snapshot without replacing the global catalog', async () => {
    // Falla si una página mezcla sus fuentes de cobertura con el catálogo global de otro corte.
    store.sources = [{ id: 3, name: 'Fuente del catálogo', health: 'current' }]
    get_request.mockResolvedValue({
      data: {
        results: [{ id: 14, title: 'Alerta de disco' }], count: 26, page_size: 25, page: 2, snapshot: 'snapshot-42',
        sources: [{ id: 8, name: 'Fuente del corte', health: 'no_data' }],
      },
    })

    await store.list({ page: 2, snapshot: 'snapshot-42' })

    expect(store.currentPage).toBe(2)
    expect(store.snapshotSources).toEqual([{ id: 8, name: 'Fuente del corte', health: 'no_data' }])
    expect(store.sources).toEqual([{ id: 3, name: 'Fuente del catálogo', health: 'current' }])
  })

  it('keeps the detail closed when its request resolves after close', async () => {
    // Falla si una respuesta tardía vuelve a abrir un modal que el operador cerró.
    const detailRequest = deferred()
    get_request.mockReturnValue(detailRequest.promise)

    const opening = store.open(7)
    store.close()
    detailRequest.resolve({ data: { id: 7, title: 'Caso que ya no debe mostrarse' } })
    await opening

    // quality: allow-negation-only (el contrato observable de close es no reabrir ningún detalle).
    expect(store.detail).toBeNull()
  })

  it('sends the displayed case version on a state transition', async () => {
    // Falla si el cambio de estado pierde el control de versión del caso mostrado.
    store.detail = { id: 7, version: 3, state: 'pending' }
    create_request.mockResolvedValue({ data: { state: 'reviewing' } })
    get_request.mockResolvedValue({ data: { id: 7, version: 4, state: 'reviewing', title: 'Base lenta' } })

    await store.transition('reviewing', { history_snapshot: true })

    expect(create_request).toHaveBeenCalledWith('monitoring/cases/7/state/', { state: 'reviewing', version: 3 })
    expect(get_request).toHaveBeenCalledWith('monitoring/cases/7/', { params: { page: 1, history_snapshot: true } })
  })

  it('replaces the case detail after a state transition', async () => {
    // Falla si la vista conserva el estado anterior después de una transición aceptada.
    store.detail = { id: 7, version: 3, state: 'pending' }
    create_request.mockResolvedValue({ data: { state: 'reviewing' } })
    get_request.mockResolvedValue({ data: { id: 7, version: 4, state: 'reviewing', title: 'Base lenta' } })

    await store.transition('reviewing')

    expect(store.detail).toEqual({ id: 7, version: 4, state: 'reviewing', title: 'Base lenta' })
  })

  it('posts a note to the selected case', async () => {
    // Falla si una nota se envía al caso equivocado.
    store.detail = { id: 9, version: 2, activities: [] }
    create_request.mockResolvedValue({ data: { id: 31 } })
    get_request.mockResolvedValue({
      data: { id: 9, version: 2, activities: [{ id: 31, text: 'Revisé los índices.' }] },
    })

    await store.note('Revisé los índices.', { history_snapshot: true })

    expect(create_request).toHaveBeenCalledWith('monitoring/cases/9/notes/', { text: 'Revisé los índices.' })
    expect(get_request).toHaveBeenCalledWith('monitoring/cases/9/', { params: { page: 1, history_snapshot: true } })
  })

  it('replaces case activities after a note', async () => {
    // Falla si la vista conserva el historial viejo tras registrar una nota.
    store.detail = { id: 9, version: 2, activities: [] }
    create_request.mockResolvedValue({ data: { id: 31 } })
    get_request.mockResolvedValue({
      data: { id: 9, version: 2, activities: [{ id: 31, text: 'Revisé los índices.' }] },
    })

    await store.note('Revisé los índices.')

    expect(store.detail.activities).toEqual([{ id: 31, text: 'Revisé los índices.' }])
  })

  it('clears saving after a rejected state transition', async () => {
    // Falla si un rechazo del servidor bloquea para siempre los controles de seguimiento.
    store.detail = { id: 7, version: 3 }
    create_request.mockRejectedValue(new Error('conflicto de versión'))

    await expect(store.transition('resolved')).rejects.toThrow('conflicto de versión')

    expect(store.saving).toBe(false)
  })

  it.each([1, 50])('shares one pending catalog request across %i concurrent refreshes', async (refreshCount) => {
    // Falla si cada refresh solapado vuelve a pedir el catálogo completo.
    const catalogRequest = deferred()
    const catalog = {
      resources: [{ id: 4, name: 'Servidor de producción' }],
      sources: [{ id: 9, name: 'Uptime Robot' }],
    }
    get_request.mockReturnValue(catalogRequest.promise)

    const refreshes = Array.from({ length: refreshCount }, () => store.catalog())

    expect(get_request).toHaveBeenCalledTimes(1)
    expect(get_request).toHaveBeenCalledWith('monitoring/catalog/')

    catalogRequest.resolve({ data: catalog })
    const results = await Promise.all(refreshes)

    expect(results).toEqual(Array.from({ length: refreshCount }, () => undefined))
    expect(store.resources).toEqual([{ id: 4, name: 'Servidor de producción' }])
    expect(store.sources).toEqual([{ id: 9, name: 'Uptime Robot' }])
  })

  it('requests a fresh catalog after the pending request has resolved', async () => {
    // Falla si la deduplicación pendiente se convierte en una caché que deja obsoleto el catálogo.
    const firstRequest = deferred()
    const secondRequest = deferred()
    get_request.mockReturnValueOnce(firstRequest.promise).mockReturnValueOnce(secondRequest.promise)

    const firstLoad = store.catalog()
    firstRequest.resolve({ data: { resources: [{ id: 1, name: 'Servidor anterior' }], sources: [{ id: 2, name: 'Ping anterior' }] } })
    await firstLoad

    const secondLoad = store.catalog()
    expect(get_request).toHaveBeenCalledTimes(2)

    secondRequest.resolve({ data: { resources: [{ id: 3, name: 'Servidor actual' }], sources: [{ id: 4, name: 'Ping actual' }] } })
    await secondLoad

    expect(store.resources).toEqual([{ id: 3, name: 'Servidor actual' }])
    expect(store.sources).toEqual([{ id: 4, name: 'Ping actual' }])
  })

  it.each([1, 50])('keeps catalog filters after %i concurrent failures', async (refreshCount) => {
    // Falla si un rechazo borra los filtros visibles de la pantalla.
    const failingRequest = deferred()
    const previousResources = [{ id: 7, name: 'Servidor conservado' }]
    const previousSources = [{ id: 8, name: 'Fuente conservada' }]
    const expectedFailure = new Error('No fue posible actualizar el catálogo')
    store.resources = previousResources
    store.sources = previousSources
    get_request.mockReturnValue(failingRequest.promise)

    const failedRefreshes = Array.from({ length: refreshCount }, () => store.catalog())
    const outcomes = Promise.allSettled(failedRefreshes)
    failingRequest.reject(expectedFailure)
    const rejectedRefreshes = await outcomes

    expect(get_request).toHaveBeenCalledTimes(1)
    expect(rejectedRefreshes).toEqual(Array.from(
      { length: refreshCount },
      () => ({ status: 'rejected', reason: expectedFailure }),
    ))
    expect(store.resources).toEqual([{ id: 7, name: 'Servidor conservado' }])
    expect(store.sources).toEqual([{ id: 8, name: 'Fuente conservada' }])
  })

  it('allows a catalog retry after a rejected request', async () => {
    // Falla si una promesa rechazada impide actualizar el catálogo más adelante.
    const failingRequest = deferred()
    const retryRequest = deferred()
    const expectedFailure = new Error('No fue posible actualizar el catálogo')
    get_request.mockReturnValueOnce(failingRequest.promise).mockReturnValueOnce(retryRequest.promise)

    const failedRefresh = store.catalog()
    const outcome = Promise.allSettled([failedRefresh])
    failingRequest.reject(expectedFailure)
    await outcome

    const retry = store.catalog()
    expect(get_request).toHaveBeenCalledTimes(2)
    retryRequest.resolve({ data: { resources: [{ id: 10, name: 'Servidor recuperado' }], sources: [{ id: 11, name: 'Fuente recuperada' }] } })
    await retry

    expect(store.resources).toEqual([{ id: 10, name: 'Servidor recuperado' }])
    expect(store.sources).toEqual([{ id: 11, name: 'Fuente recuperada' }])
  })

  it('starts a catalog request for each Pinia instance', () => {
    // Falla si una promesa global mezcla dos solicitudes pendientes de sesiones distintas.
    const firstPinia = createPinia()
    const secondPinia = createPinia()
    const firstStore = useMonitoringStore(firstPinia)
    const secondStore = useMonitoringStore(secondPinia)
    const firstRequest = deferred()
    const secondRequest = deferred()
    get_request.mockReturnValueOnce(firstRequest.promise).mockReturnValueOnce(secondRequest.promise)

    firstStore.catalog()
    secondStore.catalog()

    expect(get_request.mock.calls).toEqual([
      ['monitoring/catalog/'],
      ['monitoring/catalog/'],
    ])
  })

  it('applies a catalog only to its originating Pinia instance', async () => {
    // Falla si resolver el catálogo de una sesión modifica las colecciones de otra.
    const firstPinia = createPinia()
    const secondPinia = createPinia()
    const firstStore = useMonitoringStore(firstPinia)
    const secondStore = useMonitoringStore(secondPinia)
    const firstRequest = deferred()
    const secondRequest = deferred()
    get_request.mockReturnValueOnce(firstRequest.promise).mockReturnValueOnce(secondRequest.promise)

    const firstLoad = firstStore.catalog()
    secondStore.catalog()

    firstRequest.resolve({ data: { resources: [{ id: 12, name: 'Servidor de la primera sesión' }], sources: [{ id: 13, name: 'Fuente de la primera sesión' }] } })
    await firstLoad

    expect(firstStore.resources).toEqual([{ id: 12, name: 'Servidor de la primera sesión' }])
    expect(firstStore.sources).toEqual([{ id: 13, name: 'Fuente de la primera sesión' }])
    expect(secondStore.resources).toEqual([])
    expect(secondStore.sources).toEqual([])
  })
})
