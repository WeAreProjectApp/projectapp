import { createPinia, setActivePinia } from 'pinia'
import { useProcurementStore } from '../../stores/procurement'

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}))

const {
  get_request,
  create_request,
  patch_request,
} = require('../../stores/services/request_http')

function deferred() {
  let resolve
  const promise = new Promise((res) => { resolve = res })
  return { promise, resolve }
}

describe('procurement store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useProcurementStore()
    jest.clearAllMocks()
  })

  it('keeps the newest opportunity listing after an older response resolves', async () => {
    // Falla si una respuesta lenta sobrescribe oportunidades de filtros más recientes.
    const first = deferred()
    const second = deferred()
    get_request.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const firstList = store.list({ page: 1 })
    const secondList = store.list({ page: 2 })
    second.resolve({ data: { results: [{ id: 22, title: 'Puente' }], count: 1 } })
    await secondList
    first.resolve({ data: { results: [{ id: 11, title: 'Escuela' }], count: 9 } })
    await firstList

    expect(store.records).toEqual([{ id: 22, title: 'Puente' }])
    expect(store.count).toBe(1)
    expect(store.loading).toBe(false)
  })

  it('serializes list filters for the opportunities endpoint', async () => {
    // Falla si el panel consulta oportunidades con criterios distintos de los elegidos.
    get_request.mockResolvedValue({ data: { results: [], count: 0 } })

    await store.list({ filters: { keywords: ['obra civil'] } })

    expect(get_request).toHaveBeenCalledWith('procurement/opportunities/', {
      params: { filters: '{"keywords":["obra civil"]}' },
    })
    expect(store.count).toBe(0)
  })

  it('serializes export filters for the spreadsheet endpoint', async () => {
    // Falla si la descarga usa criterios distintos o interpreta el archivo como JSON.
    get_request.mockResolvedValue({ data: 'archivo-binario' })

    const exported = await store.export({ filters: { keywords: ['obra civil'] } })

    expect(get_request).toHaveBeenCalledWith('procurement/export/', {
      responseType: 'blob',
      params: { filters: '{"keywords":["obra civil"]}' },
    })
    expect(exported).toBe('archivo-binario')
  })

  it.each([
    [undefined, create_request, 'procurement/alerts/'],
    [7, patch_request, 'procurement/alerts/7/'],
  ])('reloads alerts after saving alert %s', async (id, request, path) => {
    // Falla si una alerta guardada no aparece en el panel hasta una recarga manual.
    const payload = { name: 'Obras Bogotá', frequency: 'daily' }
    request.mockResolvedValue({ data: { id: id || 12, ...payload } })
    get_request.mockResolvedValue({ data: [{ id: id || 12, ...payload }] })

    await store.saveAlert(payload, id)

    expect(request).toHaveBeenCalledWith(path, payload)
    expect(store.alerts).toEqual([{ id: id || 12, ...payload }])
    expect(store.saving).toBe(false)
  })

  it('releases the saving state when alert creation fails', async () => {
    // Falla si un error de red deja el formulario de alertas bloqueado.
    create_request.mockRejectedValue(new Error('sin conexión'))

    await expect(store.saveAlert({ name: 'Obras Bogotá' })).rejects.toThrow('sin conexión')

    expect(store.saving).toBe(false)
  })
})
