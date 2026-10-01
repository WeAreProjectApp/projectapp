import { createPinia, setActivePinia } from 'pinia'
import { usePlatformDeliveryStore } from '../../stores/platform-delivery'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../composables/usePlatformApi')
const emailId = 'c1f2aa00-1111-4444-8888-222233334444'
const digest = 'a'.repeat(64)
const createWorkspace = () => ({ project: { id: 7 }, version: 4, contracts: [{ id: 3, title: 'Contrato' }], scopes: [{ id: 2, title: 'Inventario', phases: [] }] })
const createEmail = (overrides = {}) => ({ id: emailId, version: 4, captured_version: 4, status: 'prepared', manifest_sha256: digest, to: ['cliente@example.test'], subject: 'Conformidad', text_body: 'La etapa quedó aprobada.', attachments: [], ...overrides })

describe('Platform delivery approval email actions', () => {
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
  afterEach(() => { jest.useRealTimers(); jest.clearAllMocks() })

  // Detecta que preparar un correo reemplace el alcance por el DTO del correo.
  it('retains the hierarchy while preparing an approval email', async () => {
    api.request.mockResolvedValue({ data: createEmail() })
    const result = await store.prepareClosureEmail(11, { message: '', include_record_pdf: false, document_snapshot_ids: [] })
    expect(api.request).toHaveBeenCalledWith({ url: 'projects/7/delivery/stages/11/closure-email/prepare/', method: 'POST', data: { message: '', include_record_pdf: false, document_snapshot_ids: [], expected_version: 4, request_id: expect.any(String) } })
    expect(result.data.id).toBe(emailId)
    expect(store.workspace).toEqual(createWorkspace())
  })

  // Detecta una nueva operación de preparación cuando sólo se reintenta una respuesta perdida.
  it('reuses the approval email request identifier after a lost response', async () => {
    api.request.mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce({ data: createEmail() })
    await store.prepareClosureEmail(11, { message: 'Gracias.', document_snapshot_ids: [31] })
    const result = await store.prepareClosureEmail(11, { message: 'Gracias.', document_snapshot_ids: [31] })
    expect(api.request.mock.calls[1][0].data.request_id).toBe(api.request.mock.calls[0][0].data.request_id)
    expect(result.data.status).toBe('prepared')
    expect(store.workspace).toEqual(createWorkspace())
  })

  // Detecta que el historial de correos se consulte fuera del proyecto seleccionado.
  it('loads the approval email history for the selected stage', async () => {
    api.get.mockResolvedValue({ data: { version: 4, available_documents: [{ id: 31, filename: 'guia-ronda-2.pdf' }], emails: [createEmail()] } })
    const result = await store.fetchClosureEmailHistory(11)
    expect(api.get).toHaveBeenCalledWith('projects/7/delivery/stages/11/closure-email/history/')
    expect(result.data.available_documents).toEqual([{ id: 31, filename: 'guia-ronda-2.pdf' }])
    expect(store.workspace).toEqual(createWorkspace())
  })

  // Detecta que consultar una copia vieja rebobine la versión actual o sustituya la jerarquía.
  it('uses the current workspace version returned with a retained email', async () => {
    api.get.mockResolvedValue({ data: createEmail({ version: 5, captured_version: 3 }) })
    await store.fetchClosureEmail(emailId)
    expect(api.get).toHaveBeenCalledWith(`projects/7/delivery/closure-emails/${emailId}/`)
    expect(store.version).toBe(5)
    expect(store.scopes).toEqual([{ id: 2, title: 'Inventario', phases: [] }])
    expect(store.contracts).toEqual([{ id: 3, title: 'Contrato' }])
  })

  // Detecta que el envío omita el contenido exacto confirmado por la persona administradora.
  it('sends the confirmed manifest without replacing the hierarchy', async () => {
    api.request.mockResolvedValue({ data: createEmail({ status: 'sent' }) })
    const result = await store.sendClosureEmail(emailId, { preview_sha256: digest, human_reviewed: true })
    expect(api.request).toHaveBeenCalledWith({ url: `projects/7/delivery/closure-emails/${emailId}/send/`, method: 'POST', data: { preview_sha256: digest, human_reviewed: true, expected_version: 4, request_id: expect.any(String) } })
    expect(result.data.status).toBe('sent')
    expect(store.workspace).toEqual(createWorkspace())
  })

  // Detecta que preparar un reenvío mande el correo antes de revisar la nueva copia.
  it('prepares a resend without invoking the send endpoint', async () => {
    api.request.mockResolvedValue({ data: createEmail({ id: 'new-retained-email' }) })
    const result = await store.prepareClosureEmailResend(emailId)
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual([`projects/7/delivery/closure-emails/${emailId}/resend/prepare/`])
    expect(result.data.id).toBe('new-retained-email')
    expect(result.data.status).toBe('prepared')
    expect(store.workspace).toEqual(createWorkspace())
  })

  // Detecta que un envío con versión vencida borre la etapa o silencie el conflicto.
  it('preserves the stage after a send version conflict', async () => {
    api.request.mockRejectedValue({ response: { status: 409, data: { detail: 'La versión cambió.', code: 'version_conflict' } } })
    const result = await store.sendClosureEmail(emailId, { preview_sha256: digest, human_reviewed: true })
    expect(result).toEqual(expect.objectContaining({ success: false, status: 409, message: 'La versión cambió.', code: 'version_conflict' }))
    expect(store.hasConflict).toBe(true)
    expect(store.workspace).toEqual(createWorkspace())
  })
})
