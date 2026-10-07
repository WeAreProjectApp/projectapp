import { setActivePinia, createPinia } from 'pinia'
import { usePlatformDeliverablesStore } from '../../stores/platform-deliverables'

jest.mock('../../composables/usePlatformApi', () => {
  const mockGet = jest.fn()
  const mockPost = jest.fn()
  const mockPatch = jest.fn()
  const mockDelete = jest.fn()
  return {
    usePlatformApi: () => ({
      get: mockGet,
      post: mockPost,
      patch: mockPatch,
      delete: mockDelete,
    }),
    readPlatformSession: jest.fn(() => ({
      accessToken: '',
      refreshToken: '',
      user: null,
      verificationToken: '',
      pendingEmail: '',
    })),
    writePlatformSession: jest.fn(),
    clearPlatformSession: jest.fn(),
    __mockGet: mockGet,
    __mockPost: mockPost,
    __mockPatch: mockPatch,
    __mockDelete: mockDelete,
  }
})

const {
  __mockGet: mockGet,
  __mockPost: mockPost,
  __mockPatch: mockPatch,
  __mockDelete: mockDelete,
} = require('../../composables/usePlatformApi')

describe('usePlatformDeliverablesStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformDeliverablesStore()
    jest.clearAllMocks()
  })

  it('totalCount returns length', () => {
    store.deliverables = [{ id: 1 }, { id: 2 }]
    expect(store.totalCount).toBe(2)
  })

  it('groupedByCategory orders known categories', () => {
    store.deliverables = [
      { id: 1, category: 'documents' },
      { id: 2, category: 'designs' },
    ]
    const groups = store.groupedByCategory
    expect(groups.map((g) => g.category)).toEqual(['designs', 'documents'])
  })

  it.each(['contract', 'amendment', 'legal_annex'])('exposes a %s resource in its category group', (category) => {
    const resource = { id: 7, category, title: 'Recurso contractual conservado' }
    store.deliverables = [resource]

    const groups = store.groupedByCategory

    expect(groups).toEqual([{ category, items: [resource] }])
  })

  it('groupedByCategory omits empty categories', () => {
    store.deliverables = [{ id: 1, category: 'other' }]
    expect(store.groupedByCategory).toHaveLength(1)
  })

  it('fetchDeliverables sets projectId', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchDeliverables(4, null)
    expect(store.projectId).toBe(4)
  })

  it('fetchDeliverables appends category query', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchDeliverables(1, 'apks')
    expect(mockGet).toHaveBeenCalledWith('projects/1/deliverables/?category=apks')
  })

  it('fetchDeliverables adds include_archived when requested', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchDeliverables(1, null, true)
    expect(mockGet).toHaveBeenCalledWith('projects/1/deliverables/?include_archived=1')
  })

  it('fetchDeliverables combines category and include_archived', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchDeliverables(1, 'documents', true)
    expect(mockGet).toHaveBeenCalledWith('projects/1/deliverables/?category=documents&include_archived=1')
  })

  it('fetchAllDeliverables clears projectId', async () => {
    store.projectId = 1
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchAllDeliverables()
    expect(store.projectId).toBeNull()
    expect(mockGet).toHaveBeenCalledWith('deliverables/')
  })

  it('fetchAllDeliverables adds include_archived when requested', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchAllDeliverables(null, true)
    expect(mockGet).toHaveBeenCalledWith('deliverables/?include_archived=1')
  })

  it('fetchDeliverable sets current', async () => {
    mockGet.mockResolvedValueOnce({ data: { id: 9 } })
    const result = await store.fetchDeliverable(2, 9)
    expect(result.success).toBe(true)
    expect(store.currentDeliverable).toEqual({ id: 9 })
  })

  it('createDeliverable prepends with multipart', async () => {
    const fd = new FormData()
    mockPost.mockResolvedValueOnce({ data: { id: 3 } })
    await store.createDeliverable(1, fd)
    expect(mockPost).toHaveBeenCalledWith(
      'projects/1/deliverables/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    expect(store.deliverables[0].id).toBe(3)
  })

  it('updateDeliverable merges into list and current', async () => {
    store.deliverables = [{ id: 5, name: 'a' }]
    store.currentDeliverable = { id: 5, name: 'a' }
    mockPatch.mockResolvedValueOnce({ data: { id: 5, name: 'b' } })
    await store.updateDeliverable(1, 5, { name: 'b' })
    expect(store.deliverables[0].name).toBe('b')
    expect(store.currentDeliverable.name).toBe('b')
  })

  it('deleteDeliverable removes id', async () => {
    store.deliverables = [{ id: 1 }]
    mockDelete.mockResolvedValueOnce({})
    await store.deleteDeliverable(1, 1)
    expect(store.deliverables).toEqual([])
  })

  it('uploadNewVersion merges response', async () => {
    store.deliverables = [{ id: 8, v: 1 }]
    store.currentDeliverable = { id: 8, v: 1 }
    const fd = new FormData()
    mockPost.mockResolvedValueOnce({ data: { id: 8, v: 2 } })
    await store.uploadNewVersion(1, 8, fd)
    expect(store.deliverables[0].v).toBe(2)
  })

  it('fetchDeliverables returns failure on error', async () => {
    mockGet.mockRejectedValueOnce({ response: { data: { detail: 'e' } } })
    expect((await store.fetchDeliverables(1)).success).toBe(false)
  })

  it('fetchAllDeliverables returns failure on error', async () => {
    mockGet.mockRejectedValueOnce({ response: { data: { detail: 'f' } } })
    expect((await store.fetchAllDeliverables()).success).toBe(false)
  })

  it('fetchDeliverable returns failure on error', async () => {
    mockGet.mockRejectedValueOnce({ response: { data: { detail: 'g' } } })
    expect((await store.fetchDeliverable(1, 1)).success).toBe(false)
  })

  it('createDeliverable returns failure on error', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: 'h' } } })
    expect((await store.createDeliverable(1, new FormData())).success).toBe(false)
  })

  it('updateDeliverable returns failure on error', async () => {
    mockPatch.mockRejectedValueOnce({ response: { data: { detail: 'i' } } })
    expect((await store.updateDeliverable(1, 1, {})).success).toBe(false)
  })

  it('deleteDeliverable returns failure on error', async () => {
    mockDelete.mockRejectedValueOnce({ response: { data: { detail: 'j' } } })
    expect((await store.deleteDeliverable(1, 1)).success).toBe(false)
  })

  it('uploadNewVersion returns failure on error', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: 'k' } } })
    expect((await store.uploadNewVersion(1, 1, new FormData())).success).toBe(false)
  })

  describe('error fallback messages', () => {
    it('fetchDeliverables uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const result = await store.fetchDeliverables(1)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar los entregables.')
    })

    it('fetchAllDeliverables uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const result = await store.fetchAllDeliverables()
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar los entregables.')
    })

    it('fetchDeliverable uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const result = await store.fetchDeliverable(1, 1)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar el entregable.')
    })

    it('createDeliverable uses fallback when detail is absent', async () => {
      mockPost.mockRejectedValueOnce(new Error('network'))
      const result = await store.createDeliverable(1, new FormData())
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos subir el recurso.')
    })

    it('updateDeliverable uses fallback when detail is absent', async () => {
      mockPatch.mockRejectedValueOnce(new Error('network'))
      const result = await store.updateDeliverable(1, 1, {})
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos actualizar el entregable.')
    })

    it('deleteDeliverable uses fallback when detail is absent', async () => {
      mockDelete.mockRejectedValueOnce(new Error('network'))
      const result = await store.deleteDeliverable(1, 1)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos archivar el entregable.')
    })

    it('uploadNewVersion uses fallback when detail is absent', async () => {
      mockPost.mockRejectedValueOnce(new Error('network'))
      const result = await store.uploadNewVersion(1, 1, new FormData())
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos subir la nueva versión.')
    })
  })

  describe('fetchAllDeliverables with category filter', () => {
    it('appends category query when category is provided', async () => {
      mockGet.mockResolvedValueOnce({ data: [] })
      await store.fetchAllDeliverables('designs')
      expect(mockGet).toHaveBeenCalledWith('deliverables/?category=designs')
    })
  })

  describe('updateDeliverable conditional branches', () => {
    it('does not update list entry when id is not found', async () => {
      store.deliverables = [{ id: 99, name: 'unchanged' }]
      mockPatch.mockResolvedValueOnce({ data: { id: 5, name: 'updated' } })
      await store.updateDeliverable(1, 5, { name: 'updated' })
      expect(store.deliverables[0].name).toBe('unchanged')
    })

    it('does not update currentDeliverable when id does not match', async () => {
      store.deliverables = []
      store.currentDeliverable = { id: 99, name: 'unchanged' }
      mockPatch.mockResolvedValueOnce({ data: { id: 5, name: 'updated' } })
      await store.updateDeliverable(1, 5, { name: 'updated' })
      expect(store.currentDeliverable.name).toBe('unchanged')
    })
  })

  describe('uploadNewVersion conditional branches', () => {
    it('does not update list entry when id is not found', async () => {
      store.deliverables = [{ id: 99, v: 1 }]
      mockPost.mockResolvedValueOnce({ data: { id: 5, v: 2 } })
      await store.uploadNewVersion(1, 5, new FormData())
      expect(store.deliverables[0].v).toBe(1)
    })

    it('does not update currentDeliverable when id does not match', async () => {
      store.deliverables = []
      store.currentDeliverable = { id: 99, v: 1 }
      mockPost.mockResolvedValueOnce({ data: { id: 5, v: 2 } })
      await store.uploadNewVersion(1, 5, new FormData())
      expect(store.currentDeliverable.v).toBe(1)
    })
  })

  describe('deleteDeliverable detail message', () => {
    it('returns data detail as message when present', async () => {
      mockDelete.mockResolvedValueOnce({ data: { detail: 'Archived.' } })
      const result = await store.deleteDeliverable(1, 1)
      expect(result.success).toBe(true)
      expect(result.message).toBe('Archived.')
    })
  })

  it('fetchDeliverables uses fallback message when error has no detail', async () => {
    mockGet.mockRejectedValueOnce({})
    const result = await store.fetchDeliverables(1)
    expect(result.message).toBe('No pudimos cargar los entregables.')
  })

  it('fetchAllDeliverables uses fallback message when error has no detail', async () => {
    mockGet.mockRejectedValueOnce({})
    const result = await store.fetchAllDeliverables()
    expect(result.message).toBe('No pudimos cargar los entregables.')
  })

  it('fetchAllDeliverables appends category query when provided', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchAllDeliverables('apks')
    expect(mockGet).toHaveBeenCalledWith('deliverables/?category=apks')
  })

  it('fetchDeliverable uses fallback message when error has no detail', async () => {
    mockGet.mockRejectedValueOnce({})
    const result = await store.fetchDeliverable(1, 1)
    expect(result.message).toBe('No pudimos cargar el entregable.')
  })

  it('createDeliverable uses fallback message when error has no detail', async () => {
    mockPost.mockRejectedValueOnce({})
    const result = await store.createDeliverable(1, new FormData())
    expect(result.message).toBe('No pudimos subir el recurso.')
  })

  it('updateDeliverable leaves list intact when deliverable not in list', async () => {
    store.deliverables = [{ id: 5, name: 'a' }]
    mockPatch.mockResolvedValueOnce({ data: { id: 99, name: 'b' } })
    await store.updateDeliverable(1, 99, { name: 'b' })
    expect(store.deliverables[0].name).toBe('a')
  })

  it('updateDeliverable does not touch currentDeliverable when ids differ', async () => {
    store.currentDeliverable = { id: 5, name: 'a' }
    mockPatch.mockResolvedValueOnce({ data: { id: 99, name: 'b' } })
    await store.updateDeliverable(1, 99, { name: 'b' })
    expect(store.currentDeliverable.name).toBe('a')
  })

  it('updateDeliverable uses fallback message when error has no detail', async () => {
    mockPatch.mockRejectedValueOnce({})
    const result = await store.updateDeliverable(1, 1, {})
    expect(result.message).toBe('No pudimos actualizar el entregable.')
  })

  it('deleteDeliverable returns detail message on success when provided', async () => {
    store.deliverables = [{ id: 1 }]
    mockDelete.mockResolvedValueOnce({ data: { detail: 'Archivado.' } })
    const result = await store.deleteDeliverable(1, 1)
    expect(result.message).toBe('Archivado.')
  })

  it('deleteDeliverable uses fallback message when error has no detail', async () => {
    mockDelete.mockRejectedValueOnce({})
    const result = await store.deleteDeliverable(1, 1)
    expect(result.message).toBe('No pudimos archivar el entregable.')
  })

  it('uploadNewVersion leaves list intact when deliverable not in list', async () => {
    store.deliverables = [{ id: 8, v: 1 }]
    mockPost.mockResolvedValueOnce({ data: { id: 99, v: 2 } })
    await store.uploadNewVersion(1, 99, new FormData())
    expect(store.deliverables[0].v).toBe(1)
  })

  it('uploadNewVersion does not touch currentDeliverable when ids differ', async () => {
    store.currentDeliverable = { id: 8, v: 1 }
    mockPost.mockResolvedValueOnce({ data: { id: 99, v: 2 } })
    await store.uploadNewVersion(1, 99, new FormData())
    expect(store.currentDeliverable.v).toBe(1)
  })

  it('uploadNewVersion uses fallback message when error has no detail', async () => {
    mockPost.mockRejectedValueOnce({})
    const result = await store.uploadNewVersion(1, 1, new FormData())
    expect(result.message).toBe('No pudimos subir la nueva versión.')
  })
})
