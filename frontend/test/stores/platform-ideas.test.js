import { createPinia, setActivePinia } from 'pinia'
import { usePlatformIdeasStore } from '../../stores/platform-ideas'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('usePlatformIdeasStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformIdeasStore()
  })

  it('keeps only the newest project response after a late ideas load', async () => {
    // Falla si una respuesta tardía mezcla ideas de un proyecto anterior en el proyecto actual.
    const first = deferred()
    const projectAApi = { list: jest.fn(() => first.promise) }
    const projectBApi = { list: jest.fn().mockResolvedValue({ results: [{ id: 22, text: 'Idea B' }], count: 1, page: 1 }) }

    const loadingA = store.load(11, projectAApi)
    const loadingB = store.load(12, projectBApi)
    first.resolve({ results: [{ id: 11, text: 'Idea A' }], count: 1, page: 1 })
    await Promise.all([loadingA, loadingB])

    expect(store.projectId).toBe(12)
    expect(store.items).toEqual([{ id: 22, text: 'Idea B' }])
    expect(store.count).toBe(1)
    expect(store.page).toBe(1)
  })

  it('reuses the idempotency key after a failed idea creation', async () => {
    // Falla si reintentar una alta tras perder la respuesta genera una segunda sugerencia.
    const api = {
      create: jest.fn()
        .mockRejectedValueOnce({ response: { data: { detail: 'Sin conexión' } } })
        .mockResolvedValueOnce({ id: 31, text: 'Idea sin duplicado' }),
      list: jest.fn().mockResolvedValue({ results: [{ id: 31, text: 'Idea sin duplicado' }], count: 1, page: 1 }),
    }
    store.projectId = 12

    const first = await store.mutate(api, 'create', { text: 'Idea sin duplicado' })
    const second = await store.mutate(api, 'create', { text: 'Idea sin duplicado' })

    expect(first).toBeNull()
    expect(second).toEqual({ id: 31, text: 'Idea sin duplicado' })
    expect(api.create).toHaveBeenCalledTimes(2)
    expect(api.create.mock.calls[0][0].request_id).toBe(api.create.mock.calls[1][0].request_id)
    expect(api.list).toHaveBeenCalledWith(1)
    expect(store.items).toEqual([{ id: 31, text: 'Idea sin duplicado' }])
  })

  it('sends selected versions unchanged when collection creation conflicts', async () => {
    // Falla si la recopilación congela versiones distintas de las que eligió el administrador.
    const selected = [{ id: 4, version: 2 }, { id: 9, version: 7 }]
    const api = {
      collect: jest.fn().mockRejectedValue({ response: { data: { detail: 'Versión obsoleta' } } }),
      list: jest.fn(),
    }
    store.projectId = 12

    const result = await store.mutate(api, 'collect', { title: 'Contrato futuro', selected })

    expect(api.collect).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Contrato futuro',
      items: [{ idea_id: 4, expected_version: 2 }, { idea_id: 9, expected_version: 7 }],
    }))
    expect(result).toBeNull()
    expect(store.error).toBe('Versión obsoleta')
    expect(selected).toEqual([{ id: 4, version: 2 }, { id: 9, version: 7 }])
  })
})
