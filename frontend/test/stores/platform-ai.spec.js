import { createPinia, setActivePinia } from 'pinia'
import { usePlatformAIStore } from '../../stores/platform-ai'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../composables/usePlatformApi')

describe('usePlatformAIStore', () => {
  let api
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformAIStore()
    api = { get: jest.fn(), post: jest.fn(), delete: jest.fn() }
    usePlatformApi.mockReturnValue(api)
  })

  afterEach(() => { jest.clearAllMocks() })

  it('exposes the server voice availability for the current client', async () => {
    // Falla si un cliente bloqueado recibe el control de voz por una respuesta desactualizada.
    api.get.mockResolvedValueOnce({ data: { voice_reporting: { available: false } } })

    await store.refreshCapabilities()

    expect(store.voiceAvailable).toBe(false)
    expect(store.capabilities).toEqual({ voice_reporting: { available: false } })
  })

  it('sends the voice note as a webm transcription request', async () => {
    // Falla si una nota pierde su proyecto, propósito o clave de idempotencia antes de llegar al servidor.
    const note = new Blob(['reported issue'], { type: 'audio/webm;codecs=opus' })
    api.post.mockResolvedValueOnce({ data: { id: 'transcription-7', status: 'pending' } })

    const result = await store.transcribe(note, { purpose: 'voice_report', projectId: 41, requestId: 'request-voice-7' })
    const [, form] = api.post.mock.calls[0]

    expect(result).toEqual({ id: 'transcription-7', status: 'pending' })
    expect(api.post.mock.calls[0][0]).toBe('/api/platform/ai/transcriptions/')
    expect(form.get('audio').name).toBe('note.webm')
    expect(form.get('purpose')).toBe('voice_report')
    expect(form.get('project_id')).toBe('41')
    expect(form.get('request_id')).toBe('request-voice-7')
    expect(api.post.mock.calls[0][2]).toEqual({ baseURL: '', headers: { 'Content-Type': undefined } })
  })

  it('requests recoverable rows scoped to the selected report context', async () => {
    // Falla si recuperar un borrador ofrece una preparación de otra etapa o escenario.
    api.get.mockResolvedValueOnce({ data: [{ id: 'draft-1', operation: 'draft', scenario: 'bug', stage_id: 6 }] })

    const rows = await store.recent(41, 'bug', { stage_id: 6 })

    expect(rows).toEqual([{ id: 'draft-1', operation: 'draft', scenario: 'bug', stage_id: 6 }])
    expect(api.get).toHaveBeenCalledWith('/api/platform/ai/transcriptions/', {
      baseURL: '', params: { purpose: 'voice_report', project_id: 41, scenario: 'bug', stage_id: 6 },
    })
  })

  it('reads the AI capabilities outside the accounts API prefix', async () => {
    // Falla si el cliente pide /api/accounts/api/platform/ai y las funciones parecen inactivas.
    api.get.mockResolvedValueOnce({ data: { voice_reporting: { available: true } } })

    await store.refreshCapabilities()

    expect(api.get).toHaveBeenCalledWith('/api/platform/ai/capabilities/', { baseURL: '' })
    expect(store.voiceAvailable).toBe(true)
  })

  it('reads a transcription job outside the accounts API prefix', async () => {
    // Falla si consultar el resultado de una nota usa el prefijo autenticado equivocado.
    const signal = new AbortController().signal
    api.get.mockResolvedValueOnce({ data: { id: 'transcription-7', status: 'ready' } })

    const result = await store.job('transcription-7', signal)

    expect(result).toEqual({ id: 'transcription-7', status: 'ready' })
    expect(api.get).toHaveBeenCalledWith('/api/platform/ai/transcriptions/transcription-7/', { signal, baseURL: '' })
  })

  it('creates a report draft outside the accounts API prefix', async () => {
    // Falla si generar el texto revisable busca una ruta inexistente bajo /api/accounts.
    const payload = { transcript: 'La aprobación no avanza.', scenario: 'bug' }
    api.post.mockResolvedValueOnce({ data: { id: 'draft-7', status: 'pending' } })

    const result = await store.generateReport(41, payload)

    expect(result).toEqual({ id: 'draft-7', status: 'pending' })
    expect(api.post).toHaveBeenCalledWith('/api/platform/ai/projects/41/report-drafts/', payload, { baseURL: '' })
  })

  it('discards a preparation outside the accounts API prefix', async () => {
    // Falla si eliminar un borrador deja el audio pendiente por pedir una ruta inexistente.
    api.delete.mockResolvedValueOnce({ data: null })

    await store.discard('transcription-7')

    expect(api.delete).toHaveBeenCalledWith('/api/platform/ai/transcriptions/transcription-7/', { baseURL: '' })
  })
})
