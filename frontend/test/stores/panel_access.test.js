const { createPinia, setActivePinia } = require('pinia')

const mockGetRequest = jest.fn()

jest.mock('../../stores/services/request_http', () => ({
  get_request: mockGetRequest,
  create_request: jest.fn(),
  patch_request: jest.fn(),
}))

const { usePanelAccessStore } = require('../../stores/panel_access')

function deferred() {
  let resolve
  const promise = new Promise((nextResolve) => { resolve = nextResolve })
  return { promise, resolve }
}

describe('usePanelAccessStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePanelAccessStore()
    jest.clearAllMocks()
  })

  it('keeps the latest access response after earlier request resolves', async () => {
    // Falla si los filtros muestran resultados de una búsqueda anterior que terminó tarde.
    const earlier = deferred()
    const latest = deferred()
    const olderResult = {
      results: [{ id: 4, email: 'old@example.com' }], count: 1, page: 1, pages: 1,
      counts: { all: 1 }, can_manage_team: false,
    }
    const latestResult = {
      results: [{ id: 8, email: 'new@example.com' }], count: 1, page: 2, pages: 3,
      counts: { all: 9, enabled: 7 }, can_manage_team: true,
    }
    mockGetRequest.mockReturnValueOnce(earlier.promise).mockReturnValueOnce(latest.promise)

    const earlierLoad = store.fetchList({ search: 'old' })
    const latestLoad = store.fetchList({ search: 'new' })
    latest.resolve({ data: latestResult })
    await latestLoad
    earlier.resolve({ data: olderResult })
    await earlierLoad

    expect(store.results).toEqual([{ id: 8, email: 'new@example.com' }])
    expect(store.count).toBe(1)
    expect(store.page).toBe(2)
    expect(store.pages).toBe(3)
    expect(store.counts).toEqual({ all: 9, enabled: 7 })
    expect(store.canManageTeam).toBe(true)
    expect(store.loading).toBe(false)
  })

  it('finishes loading after the active access request fails', async () => {
    // Falla si una carga rechazada deja la pantalla bloqueada sin mostrar su error.
    mockGetRequest.mockRejectedValueOnce({ response: { data: { detail: 'No se pudo conectar.' } } })

    await store.fetchList({ search: 'ana' })

    expect(store.error).toBe('No se pudo conectar.')
    expect(store.loading).toBe(false)
  })
})
