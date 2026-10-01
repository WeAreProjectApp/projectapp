import { setActivePinia, createPinia } from 'pinia'
import { usePlatformChangeRequestsStore } from '../../stores/platform-change-requests'

jest.mock('../../composables/usePlatformApi', () => {
  const mockGet = jest.fn()
  const mockPost = jest.fn()
  const mockDelete = jest.fn()
  return {
    usePlatformApi: () => ({
      get: mockGet,
      post: mockPost,
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
    __mockDelete: mockDelete,
  }
})

const {
  __mockGet: mockGet,
  __mockPost: mockPost,
  __mockDelete: mockDelete,
} = require('../../composables/usePlatformApi')

describe('usePlatformChangeRequestsStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformChangeRequestsStore()
    jest.clearAllMocks()
  })

  it('status count getters aggregate list', () => {
    store.changeRequests = [
      { status: 'pending' },
      { status: 'pending' },
      { status: 'evaluating' },
      { status: 'approved' },
      { status: 'rejected' },
    ]
    expect(store.pendingCount).toBe(2)
    expect(store.evaluatingCount).toBe(1)
    expect(store.approvedCount).toBe(1)
    expect(store.rejectedCount).toBe(1)
  })

  it('filteredByStatus returns full list for all', () => {
    store.changeRequests = [{ id: 1 }]
    expect(store.filteredByStatus('all')).toEqual([{ id: 1 }])
  })

  it('fetchChangeRequests sets projectId', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchChangeRequests(8, null)
    expect(store.projectId).toBe(8)
  })

  it('fetchChangeRequest loads single item', async () => {
    mockGet.mockResolvedValueOnce({ data: { id: 4 } })
    const result = await store.fetchChangeRequest(1, 4)
    expect(result.success).toBe(true)
    expect(store.currentChangeRequest).toEqual({ id: 4 })
  })

  it('createChangeRequest posts JSON payload', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 2 } })
    const body = { title: 't' }
    await store.createChangeRequest(3, body)
    expect(mockPost).toHaveBeenCalledWith('projects/3/change-requests/', body, {})
  })

  it('createChangeRequest uses multipart for FormData', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 3 } })
    const fd = new FormData()
    await store.createChangeRequest(3, fd)
    expect(mockPost).toHaveBeenCalledWith(
      'projects/3/change-requests/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  })

  it('fetchAllChangeRequests clears projectId', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchAllChangeRequests()
    expect(store.projectId).toBeNull()
  })

  it('fetchChangeRequests adds include_archived when requested', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchChangeRequests(8, null, true)
    expect(mockGet).toHaveBeenCalledWith('projects/8/change-requests/?include_archived=1')
  })

  it('fetchAllChangeRequests adds include_archived when requested', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchAllChangeRequests(null, true)
    expect(mockGet).toHaveBeenCalledWith('change-requests/?include_archived=1')
  })

  it('evaluateChangeRequest updates current when ids match', async () => {
    store.changeRequests = [{ id: 10, status: 'pending' }]
    store.currentChangeRequest = { id: 10, status: 'pending' }
    mockPost.mockResolvedValueOnce({ data: { id: 10, status: 'approved' } })
    await store.evaluateChangeRequest(1, 10, {})
    expect(store.currentChangeRequest.status).toBe('approved')
  })

  it('deleteChangeRequest filters list', async () => {
    store.changeRequests = [{ id: 1 }]
    mockDelete.mockResolvedValueOnce({})
    await store.deleteChangeRequest(2, 1)
    expect(store.changeRequests).toEqual([])
  })

  it('addComment appends when current matches', async () => {
    store.currentChangeRequest = { id: 7, comments: [] }
    mockPost.mockResolvedValueOnce({ data: { id: 20 } })
    await store.addComment(1, 7, 'note', true)
    expect(store.currentChangeRequest.comments).toHaveLength(1)
  })

  it('convertToRequirement updates list entry', async () => {
    store.changeRequests = [{ id: 5, status: 'pending' }]
    mockPost.mockResolvedValueOnce({ data: { id: 5, status: 'converted' } })
    const result = await store.convertToRequirement(1, 5, { stage_id: 11, expected_version: 4 })
    expect(mockPost).toHaveBeenCalledWith('projects/1/change-requests/5/convert/', { stage_id: 11, expected_version: 4 })
    expect(result.success).toBe(true)
    expect(store.changeRequests[0].status).toBe('converted')
  })

  it('fetchChangeRequests returns failure on error', async () => {
    mockGet.mockRejectedValueOnce({ response: { data: { detail: 'x' } } })
    expect((await store.fetchChangeRequests(1)).success).toBe(false)
  })

  it('fetchChangeRequest returns failure on error', async () => {
    mockGet.mockRejectedValueOnce({ response: { data: { detail: 'y' } } })
    expect((await store.fetchChangeRequest(1, 1)).success).toBe(false)
  })

  it('createChangeRequest returns failure on error', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: 'z' } } })
    expect((await store.createChangeRequest(1, {})).success).toBe(false)
  })

  it('fetchAllChangeRequests returns failure on error', async () => {
    mockGet.mockRejectedValueOnce({ response: { data: { detail: 'a' } } })
    expect((await store.fetchAllChangeRequests()).success).toBe(false)
  })

  it('evaluateChangeRequest returns failure on error', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: 'b' } } })
    expect((await store.evaluateChangeRequest(1, 1, {})).success).toBe(false)
  })

  it('deleteChangeRequest returns failure on error', async () => {
    mockDelete.mockRejectedValueOnce({ response: { data: { detail: 'c' } } })
    expect((await store.deleteChangeRequest(1, 1)).success).toBe(false)
  })

  it('addComment returns failure on error', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: 'd' } } })
    expect((await store.addComment(1, 1, 'x', false)).success).toBe(false)
  })

  it('convertToRequirement returns failure on error', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: 'e' } } })
    expect((await store.convertToRequirement(1, 1)).success).toBe(false)
  })

  describe('error fallback messages', () => {
    it('fetchChangeRequests uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const result = await store.fetchChangeRequests(1)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar las solicitudes de cambio.')
    })

    it('fetchChangeRequest uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const result = await store.fetchChangeRequest(1, 1)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar la solicitud de cambio.')
    })

    it('createChangeRequest uses fallback when detail is absent', async () => {
      mockPost.mockRejectedValueOnce(new Error('network'))
      const result = await store.createChangeRequest(1, {})
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos crear la solicitud de cambio.')
    })

    it('fetchAllChangeRequests uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const result = await store.fetchAllChangeRequests()
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar las solicitudes de cambio.')
    })

    it('evaluateChangeRequest uses fallback when detail is absent', async () => {
      mockPost.mockRejectedValueOnce(new Error('network'))
      const result = await store.evaluateChangeRequest(1, 1, {})
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos evaluar la solicitud de cambio.')
    })

    it('deleteChangeRequest uses fallback when detail is absent', async () => {
      mockDelete.mockRejectedValueOnce(new Error('network'))
      const result = await store.deleteChangeRequest(1, 1)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos archivar la solicitud de cambio.')
    })

    it('addComment uses fallback when detail is absent', async () => {
      mockPost.mockRejectedValueOnce(new Error('network'))
      const result = await store.addComment(1, 1, 'text', false)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos agregar el comentario.')
    })

    it('convertToRequirement uses fallback when detail is absent', async () => {
      mockPost.mockRejectedValueOnce(new Error('network'))
      const result = await store.convertToRequirement(1, 1)
      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos convertir la solicitud en requerimiento.')
    })
  })

  describe('filteredByStatus', () => {
    it('returns filtered list for specific status', () => {
      store.changeRequests = [
        { id: 1, status: 'pending' },
        { id: 2, status: 'approved' },
      ]
      expect(store.filteredByStatus('pending')).toHaveLength(1)
      expect(store.filteredByStatus('pending')[0].id).toBe(1)
    })

    it('returns empty list for null statusFilter', () => {
      store.changeRequests = [{ id: 1, status: 'pending' }]
      expect(store.filteredByStatus(null)).toEqual([{ id: 1, status: 'pending' }])
    })
  })

  describe('fetchChangeRequests with statusFilter', () => {
    it('passes status param when statusFilter is provided', async () => {
      mockGet.mockResolvedValueOnce({ data: [] })
      await store.fetchChangeRequests(8, 'pending')
      expect(mockGet).toHaveBeenCalledWith('projects/8/change-requests/?status=pending')
    })
  })

  describe('fetchAllChangeRequests with statusFilter', () => {
    it('passes status param when statusFilter is provided', async () => {
      mockGet.mockResolvedValueOnce({ data: [] })
      await store.fetchAllChangeRequests('approved')
      expect(mockGet).toHaveBeenCalledWith('change-requests/?status=approved')
    })
  })

  describe('evaluateChangeRequest conditional branches', () => {
    it('does not update list entry when change request id is not found', async () => {
      store.changeRequests = [{ id: 99, status: 'pending' }]
      mockPost.mockResolvedValueOnce({ data: { id: 10, status: 'approved' } })
      await store.evaluateChangeRequest(1, 10, {})
      expect(store.changeRequests[0].status).toBe('pending')
    })

    it('does not update currentChangeRequest when id does not match', async () => {
      store.changeRequests = []
      store.currentChangeRequest = { id: 99, status: 'pending' }
      mockPost.mockResolvedValueOnce({ data: { id: 10, status: 'approved' } })
      await store.evaluateChangeRequest(1, 10, {})
      expect(store.currentChangeRequest.status).toBe('pending')
    })
  })

  describe('convertToRequirement conditional branches', () => {
    it('does not update list entry when change request id is not found', async () => {
      store.changeRequests = [{ id: 99, status: 'pending' }]
      mockPost.mockResolvedValueOnce({ data: { id: 5, status: 'converted' } })
      await store.convertToRequirement(1, 5)
      expect(store.changeRequests[0].status).toBe('pending')
    })

    it('does not update currentChangeRequest when id does not match', async () => {
      store.changeRequests = []
      store.currentChangeRequest = { id: 99, status: 'pending' }
      mockPost.mockResolvedValueOnce({ data: { id: 5, status: 'converted' } })
      await store.convertToRequirement(1, 5)
      expect(store.currentChangeRequest.status).toBe('pending')
    })

    it('updates currentChangeRequest when id matches', async () => {
      store.changeRequests = [{ id: 5, status: 'pending' }]
      store.currentChangeRequest = { id: 5, status: 'pending' }
      mockPost.mockResolvedValueOnce({ data: { id: 5, status: 'converted' } })
      await store.convertToRequirement(1, 5)
      expect(store.currentChangeRequest.status).toBe('converted')
    })
  })

  describe('addComment conditional branches', () => {
    it('does not append when currentChangeRequest id does not match', async () => {
      store.currentChangeRequest = { id: 99, comments: [] }
      mockPost.mockResolvedValueOnce({ data: { id: 20 } })
      await store.addComment(1, 7, 'note', false)
      expect(store.currentChangeRequest.comments).toHaveLength(0)
    })
  })

  describe('deleteChangeRequest', () => {
    it('returns data detail as message when present', async () => {
      store.changeRequests = [{ id: 1 }]
      mockDelete.mockResolvedValueOnce({ data: { detail: 'Deleted.' } })
      const result = await store.deleteChangeRequest(2, 1)
      expect(result.success).toBe(true)
      expect(result.message).toBe('Deleted.')
    })
  })

  it('filteredByStatus returns full list when filter is null', () => {
    store.changeRequests = [{ id: 1 }, { id: 2 }]
    expect(store.filteredByStatus(null)).toHaveLength(2)
  })

  it('filteredByStatus returns only matching status', () => {
    store.changeRequests = [{ id: 1, status: 'pending' }, { id: 2, status: 'approved' }]
    expect(store.filteredByStatus('approved')).toEqual([{ id: 2, status: 'approved' }])
  })

  it('fetchChangeRequests sends status filter in query string', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await store.fetchChangeRequests(8, 'pending')
    expect(mockGet).toHaveBeenCalledWith(expect.stringContaining('status=pending'))
  })

  it('fetchChangeRequests uses fallback message when error has no detail', async () => {
    mockGet.mockRejectedValueOnce({})
    const result = await store.fetchChangeRequests(1)
    expect(result.message).toBe('No pudimos cargar las solicitudes de cambio.')
  })

  it('fetchChangeRequest uses fallback message when error has no detail', async () => {
    mockGet.mockRejectedValueOnce({})
    const result = await store.fetchChangeRequest(1, 1)
    expect(result.message).toBe('No pudimos cargar la solicitud de cambio.')
  })

  it('createChangeRequest uses fallback message when error has no detail', async () => {
    mockPost.mockRejectedValueOnce({})
    const result = await store.createChangeRequest(1, {})
    expect(result.message).toBe('No pudimos crear la solicitud de cambio.')
  })

  it('fetchAllChangeRequests uses fallback message when error has no detail', async () => {
    mockGet.mockRejectedValueOnce({})
    const result = await store.fetchAllChangeRequests()
    expect(result.message).toBe('No pudimos cargar las solicitudes de cambio.')
  })

  it('evaluateChangeRequest leaves list intact when crId not found', async () => {
    store.changeRequests = [{ id: 10, status: 'pending' }]
    mockPost.mockResolvedValueOnce({ data: { id: 99, status: 'approved' } })
    await store.evaluateChangeRequest(1, 99, {})
    expect(store.changeRequests[0].status).toBe('pending')
  })

  it('evaluateChangeRequest does not touch currentChangeRequest when ids differ', async () => {
    store.currentChangeRequest = { id: 10, status: 'pending' }
    mockPost.mockResolvedValueOnce({ data: { id: 99, status: 'approved' } })
    await store.evaluateChangeRequest(1, 99, {})
    expect(store.currentChangeRequest.status).toBe('pending')
  })

  it('evaluateChangeRequest uses fallback message when error has no detail', async () => {
    mockPost.mockRejectedValueOnce({})
    const result = await store.evaluateChangeRequest(1, 1, {})
    expect(result.message).toBe('No pudimos evaluar la solicitud de cambio.')
  })

  it('deleteChangeRequest returns detail message on success when provided', async () => {
    store.changeRequests = [{ id: 1 }]
    mockDelete.mockResolvedValueOnce({ data: { detail: 'Archivado.' } })
    const result = await store.deleteChangeRequest(2, 1)
    expect(result.message).toBe('Archivado.')
  })

  it('deleteChangeRequest uses fallback message when error has no detail', async () => {
    mockDelete.mockRejectedValueOnce({})
    const result = await store.deleteChangeRequest(1, 1)
    expect(result.message).toBe('No pudimos archivar la solicitud de cambio.')
  })

  it('addComment skips append when currentChangeRequest has no comments array', async () => {
    store.currentChangeRequest = { id: 7 }
    mockPost.mockResolvedValueOnce({ data: { id: 20 } })
    const result = await store.addComment(1, 7, 'x', false)
    expect(result.success).toBe(true)
    expect(store.currentChangeRequest.comments).toBeUndefined()
  })

  it('addComment skips append when currentChangeRequest id does not match', async () => {
    store.currentChangeRequest = { id: 99, comments: [] }
    mockPost.mockResolvedValueOnce({ data: { id: 20 } })
    await store.addComment(1, 7, 'x', false)
    expect(store.currentChangeRequest.comments).toHaveLength(0)
  })

  it('addComment uses fallback message when error has no detail', async () => {
    mockPost.mockRejectedValueOnce({})
    const result = await store.addComment(1, 1, 'x', false)
    expect(result.message).toBe('No pudimos agregar el comentario.')
  })

  it('convertToRequirement leaves list intact when crId not found', async () => {
    store.changeRequests = [{ id: 5, status: 'pending' }]
    mockPost.mockResolvedValueOnce({ data: { id: 99, status: 'converted' } })
    await store.convertToRequirement(1, 99)
    expect(store.changeRequests[0].status).toBe('pending')
  })

  it('convertToRequirement updates currentChangeRequest when ids match', async () => {
    store.currentChangeRequest = { id: 5, status: 'pending' }
    mockPost.mockResolvedValueOnce({ data: { id: 5, status: 'converted' } })
    await store.convertToRequirement(1, 5)
    expect(store.currentChangeRequest.status).toBe('converted')
  })

  it('convertToRequirement uses fallback message when error has no detail', async () => {
    mockPost.mockRejectedValueOnce({})
    const result = await store.convertToRequirement(1, 1)
    expect(result.message).toBe('No pudimos convertir la solicitud en requerimiento.')
  })
})
