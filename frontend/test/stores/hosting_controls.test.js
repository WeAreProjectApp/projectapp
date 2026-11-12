import { createPinia, setActivePinia } from 'pinia'
import { useHostingControlsStore } from '../../stores/hosting_controls'
import { get_request, patch_request } from '../../stores/services/request_http'

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn(), patch_request: jest.fn() }))

beforeEach(() => { setActivePinia(createPinia()); jest.clearAllMocks() })

test('an older search response cannot replace the latest results', async () => {
  const store = useHostingControlsStore()
  let first
  get_request.mockReturnValueOnce(new Promise(resolve => { first = resolve }))
  get_request.mockResolvedValueOnce({ data: { results: [{ id: 2, name: 'Segundo' }], page: 1, pages: 1 } })
  const previous = store.search('primero')
  await store.search('segundo')
  first({ data: { results: [{ id: 1, name: 'Primero' }], page: 1, pages: 1 } })
  await previous
  expect(store.records[0].name).toBe('Segundo')
})

test('a failed mode save leaves the configured mode intact', async () => {
  const store = useHostingControlsStore()
  store.selected = { id: 1, version: 0, mode: 'normal' }
  patch_request.mockRejectedValue({ response: { status: 503, data: { detail: 'No disponible' } } })
  expect(await store.save('mode', { expected_version: 0, mode: 'suspended' })).toBe(false)
  expect(store.selected.mode).toBe('normal')
  expect(store.error).toBe('No disponible')
})

test('a committed change remains successful if its history cannot refresh', async () => {
  const store = useHostingControlsStore()
  store.selected = { id: 1, version: 0, mode: 'normal' }
  patch_request.mockResolvedValue({ data: { id: 1, version: 1, mode: 'banner' } })
  get_request.mockRejectedValue(new Error('fixture history offline'))
  expect(await store.save('mode', { expected_version: 0, mode: 'banner' })).toBe(true)
  expect(store.selected.mode).toBe('banner')
  expect(store.error).toContain('Cambio guardado')
})

test('a stale refresh cannot undo a newer saved version', async () => {
  const store = useHostingControlsStore()
  store.selected = { id: 1, version: 2, mode: 'suspended' }
  get_request.mockResolvedValue({ data: { id: 1, version: 1, mode: 'banner' } })
  await store.refresh()
  expect(store.selected.mode).toBe('suspended')
})
