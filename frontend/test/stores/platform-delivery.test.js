import { setActivePinia, createPinia } from 'pinia'
import { usePlatformDeliveryStore } from '../../stores/platform-delivery'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../composables/usePlatformApi')
const createWorkspace = (overrides = {}) => ({ project: { id: 7, name: 'Client project' }, version: 4, is_admin: true, contracts: [], scopes: [], ...overrides })

describe('Platform delivery actions', () => {
  let api
  let store
  beforeEach(() => {
    setActivePinia(createPinia())
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2026-10-01T12:00:00Z'))
    api = { get: jest.fn(), request: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    store = usePlatformDeliveryStore()
    store.projectId = 7
    store.workspace = createWorkspace()
  })
  afterEach(() => { jest.useRealTimers(); jest.restoreAllMocks() })

  it('loads the hierarchy for the selected project', async () => {
    const data = createWorkspace({ contracts: [{ id: 3, title: 'Contract' }] })
    api.get.mockResolvedValue({ data })
    await store.fetchDelivery(7)
    expect(store.contracts).toEqual(data.contracts)
    expect(store.isLoading).toBe(false)
  })

  it('clears another project before a failed navigation', async () => {
    api.get.mockRejectedValue({ response: { status: 403, data: { detail: 'Forbidden' } } })
    await store.fetchDelivery(8)
    expect(store.workspace).toBeNull()
    expect(store.error).toBe('Forbidden')
  })

  it('uses the current version when publishing a stage', async () => {
    api.request.mockResolvedValue({ data: createWorkspace({ version: 5 }) })
    await store.publishStage(11)
    expect(api.request).toHaveBeenCalledWith(expect.objectContaining({ url: 'projects/7/delivery/stages/11/publish/', data: expect.objectContaining({ expected_version: 4, request_id: expect.any(String) }) }))
    expect(store.version).toBe(5)
  })

  it('preserves the retry identifier after a lost response', async () => {
    api.request.mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce({ data: createWorkspace({ version: 5 }) })
    await store.publishStage(11)
    await store.publishStage(11)
    expect(api.request.mock.calls[1][0].data.request_id).toBe(api.request.mock.calls[0][0].data.request_id)
  })

  it('keeps the reviewed content after a stale version response', async () => {
    api.request.mockRejectedValue({ response: { status: 409, data: { detail: 'Version changed', code: 'version_conflict' } } })
    const result = await store.reviewStage(11, { decisions: [{ requirement_id: 20, version: 2, decision: 'approved' }] })
    expect(result.status).toBe(409)
    expect(store.hasConflict).toBe(true)
    expect(store.version).toBe(4)
  })

  it('leaves saved content intact during import preview', async () => {
    const payload = { schema_version: 1, scopes: [] }
    api.request.mockResolvedValue({ data: { valid: true, summary: { stages: 2 }, payload } })
    const result = await store.previewImport(payload)
    expect(result.data.valid).toBe(true)
    expect(store.workspace).toEqual(createWorkspace())
  })

  it('applies a reviewed import into the hierarchy', async () => {
    const payload = { schema_version: 1, scopes: [{ key: 'scope-new' }] }
    api.request.mockResolvedValue({ data: createWorkspace({ version: 5, scopes: [{ id: 2, title: 'Draft scope', phases: [] }] }) })
    await store.applyImport(payload)
    expect(store.scopes[0].title).toBe('Draft scope')
    expect(api.request.mock.calls[0][0].data.payload).toEqual(payload)
  })

  it('sends external signature evidence as multipart data', async () => {
    const evidence = new FormData()
    evidence.set('file', new File(['%PDF'], 'signed.pdf', { type: 'application/pdf', lastModified: 1 }))
    evidence.set('signer_name', 'Client signer')
    api.request.mockResolvedValue({ data: createWorkspace({ version: 5 }) })
    await store.recordExternalSignature('contracts', 3, evidence)
    const request = api.request.mock.calls[0][0]
    expect(request.data.get('expected_version')).toBe('4')
    expect(request.data.get('file').name).toBe('signed.pdf')
    expect(request.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('sends the reported requirements with optional documents', async () => {
    api.request.mockResolvedValue({ data: createWorkspace({ version: 5 }) })
    await store.sendMessage({ level: 'stage', target_id: 11, requirement_ids: [20], message: 'Please test again', document_ids: [8] })
    expect(api.request.mock.calls[0][0].data).toEqual(expect.objectContaining({ target_id: 11, requirement_ids: [20], document_ids: [8], message: 'Please test again' }))
  })

  it('loads document sources scoped to the project', async () => {
    api.get.mockResolvedValue({ data: { documents: [{ id: 8, title: 'Contract PDF' }], proposal_documents: [{ id: 9, title: 'Proposal contract' }] } })
    await store.fetchDocumentOptions()
    expect(store.documentOptions[0].title).toBe('Contract PDF')
    expect(store.proposalDocumentOptions[0].title).toBe('Proposal contract')
  })

  it('leaves the hierarchy unchanged when retaining prompt sources', async () => {
    api.request.mockResolvedValue({ data: { id: 'retained-context', complete: true } })
    const result = await store.preparePrompt({ mode: 'guides', contract_id: 3 })
    expect(result.data.id).toBe('retained-context')
    expect(store.workspace).toEqual(createWorkspace())
  })

  it('loads a retained source context independently of the hierarchy', async () => {
    api.get.mockResolvedValue({ data: { id: 'retained-context', sources: [{ title: 'Signed source' }] } })
    const result = await store.fetchPromptContext('retained-context')
    expect(result.data.sources[0].title).toBe('Signed source')
    expect(api.get).toHaveBeenCalledWith('projects/7/delivery/prompt/retained-context/')
    expect(store.workspace).toEqual(createWorkspace())
  })

  it('preserves the hierarchy when previewing a response', async () => {
    api.request.mockResolvedValue({ data: { valid: true, response_text: 'We will attend the request.' } })
    await store.previewReply({ context_id: 'retained-context', response_text: 'We will attend the request.' })
    expect(store.workspace).toEqual(createWorkspace())
    expect(api.request.mock.calls[0][0].url).toBe('projects/7/delivery/reply/preview/')
  })
})
