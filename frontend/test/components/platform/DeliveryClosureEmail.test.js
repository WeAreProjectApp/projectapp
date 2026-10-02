import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DeliveryClosureEmail from '../../../components/platform/delivery/DeliveryClosureEmail.vue'
import { usePlatformDeliveryStore } from '../../../stores/platform-delivery'
import spanish from '../../../locales/platformDelivery/es'

jest.mock('../../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../../composables/usePlatformApi')
const translate = (key, params = {}) => Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, String(value)), key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key)
const emailId = 'c1f2aa00-1111-4444-8888-222233334444'
const resendId = 'c1f2aa00-5555-4444-8888-222233334444'
const digest = 'a'.repeat(64)
const createAttempt = (status) => ({ id: 101, status, claimed_at: '2026-10-01T12:00:00Z', finished_at: '2026-10-01T12:00:01Z', created_at: '2026-10-01T12:00:00Z' })
const createEmail = (overrides = {}) => ({
  id: emailId, status: 'prepared', to: ['cliente@example.test'], subject: 'Conformidad de inventario',
  text_body: 'La etapa Inventario quedó aprobada.\nConservamos los resultados de cada requerimiento.',
  manifest_sha256: digest, version: 4, captured_version: 4, attachments: [], error_message: '', attempts: [],
  created_at: '2026-10-01T12:00:00Z', ...overrides,
})
const createDocument = () => ({ id: 31, title: 'Guía publicada', filename: 'guia-ronda-2.pdf', version: 2, sha256: 'c'.repeat(64), round: 2 })
const createAttachment = () => ({ id: 'file-31', title: 'guia-ronda-2.pdf', filename: 'guia-ronda-2.pdf', version: 2, sha256: 'c'.repeat(64), download_url: `/api/accounts/projects/7/delivery/closure-emails/${emailId}/attachments/file-31/download/` })
const createHistory = (overrides = {}) => ({ version: 4, available_documents: [createDocument()], emails: [], ...overrides })
const createStage = () => ({ id: 11, publication_id: 9, status: 'approved', requirements: [{ id: 20, review_status: 'approved' }] })

describe('Manual delivery approval email', () => {
  let api
  const wrappers = []
  beforeEach(() => {
    setActivePinia(createPinia())
    global.useI18n = () => ({ t: translate })
    api = { get: jest.fn().mockResolvedValue({ data: createHistory() }), request: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    const store = usePlatformDeliveryStore()
    store.projectId = 7
    store.workspace = { project: { id: 7 }, version: 4, contracts: [], scopes: [], is_admin: true }
  })
  afterEach(() => { wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0; delete global.useI18n; jest.clearAllMocks() })
  async function renderEmail() {
    const wrapper = mount(DeliveryClosureEmail, { props: { stage: createStage(), isAdmin: true }, global: { stubs: { NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    wrappers.push(wrapper)
    await flushPromises()
    return wrapper
  }
  async function prepare(wrapper, email = createEmail()) {
    api.request.mockResolvedValueOnce({ data: email })
    await wrapper.get('[data-testid="delivery-closure-prepare"]').trigger('click')
    await flushPromises()
  }
  async function confirm(wrapper) {
    await wrapper.get('[data-testid="delivery-closure-reviewed"] input').setValue(true)
  }

  // Detecta un envío automático al abrir la ventana o consultar su historial.
  it('opens the approval email without sending it', async () => {
    const wrapper = await renderEmail()
    expect(wrapper.get('[data-testid="delivery-closure-include-record"] input').element.checked).toBe(false)
    expect(wrapper.get('[data-testid="delivery-closure-history"]').text()).toContain('Todavía no se han preparado correos para esta etapa.')
    expect(api.request).not.toHaveBeenCalled()
  })

  // Detecta que el correo sin documentos pierda su vista previa exacta o interprete texto como HTML.
  it('prepares the exact plain text email without attachments', async () => {
    const wrapper = await renderEmail()
    await prepare(wrapper, createEmail({ text_body: 'Constancia\n<img src=x onerror="alert(1)">\nConformidad del cliente.' }))
    expect(api.request.mock.calls[0][0].data).toEqual({ message: '', include_record_pdf: false, document_snapshot_ids: [], expected_version: 4, request_id: expect.any(String) })
    expect(wrapper.get('[data-testid="delivery-closure-to"]').text()).toBe('cliente@example.test')
    expect(wrapper.get('[data-testid="delivery-closure-subject"]').text()).toBe('Conformidad de inventario')
    expect(wrapper.get('[data-testid="delivery-closure-body"]').text()).toBe('Constancia\n<img src=x onerror="alert(1)">\nConformidad del cliente.')
    expect(wrapper.get('[data-testid="delivery-closure-body"]').findAll('img')).toHaveLength(0)
    expect(wrapper.get('[data-testid="delivery-closure-no-attachments"]').text()).toBe('Sin adjuntos.')
  })

  // Detecta que adjuntar una versión publicada sustituya esa copia por el documento actual.
  it('prepares only the selected published document version', async () => {
    const wrapper = await renderEmail()
    await wrapper.get('[data-testid="delivery-closure-document-31"] input').setValue(true)
    await wrapper.get('[data-testid="delivery-closure-include-record"] input').setValue(true)
    await wrapper.get('[data-testid="delivery-closure-message"]').setValue('Gracias por validar la etapa.')
    await prepare(wrapper, createEmail({ attachments: [createAttachment()] }))
    expect(api.request.mock.calls[0][0].data).toEqual({ message: 'Gracias por validar la etapa.', include_record_pdf: true, document_snapshot_ids: [31], expected_version: 4, request_id: expect.any(String) })
    expect(wrapper.get('[data-testid="delivery-closure-preview"]').text()).toContain('guia-ronda-2.pdf · Versión 2')
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual(['projects/7/delivery/stages/11/closure-email/prepare/'])
  })

  // Detecta que una vista previa preparada pueda enviarse sin confirmación humana.
  it('requires confirmation before sending the prepared preview', async () => {
    const wrapper = await renderEmail()
    await prepare(wrapper)
    await wrapper.get('[data-testid="delivery-closure-send"]').trigger('click')
    expect(wrapper.get('[data-testid="delivery-closure-send"]').element.disabled).toBe(true)
    expect(wrapper.get('[data-testid="delivery-closure-not-sent"]').text()).toBe('El correo está preparado. Todavía no se ha enviado.')
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual(['projects/7/delivery/stages/11/closure-email/prepare/'])
  })

  // Detecta el envío de un contenido distinto del correo confirmado por el administrador.
  it('sends the explicitly confirmed preview', async () => {
    const wrapper = await renderEmail()
    await prepare(wrapper)
    await confirm(wrapper)
    api.request.mockResolvedValueOnce({ data: createEmail({ status: 'sent', attempts: [createAttempt('sent')] }) })
    await wrapper.get('[data-testid="delivery-closure-send"]').trigger('click')
    await flushPromises()
    expect(api.request.mock.calls[1][0]).toEqual({ url: `projects/7/delivery/closure-emails/${emailId}/send/`, method: 'POST', data: { preview_sha256: digest, human_reviewed: true, expected_version: 4, request_id: expect.any(String) } })
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Enviado')
    expect(wrapper.get(`[data-testid="delivery-closure-history-${emailId}"]`).text()).toContain('Enviado')
  })

  // Detecta que dos clics durante el envío creen dos peticiones al proveedor.
  it('blocks another send while the current send is pending', async () => {
    const wrapper = await renderEmail()
    await prepare(wrapper)
    await confirm(wrapper)
    let completeSend
    api.request.mockReturnValueOnce(new Promise((resolve) => { completeSend = resolve }))
    await wrapper.get('[data-testid="delivery-closure-send"]').trigger('click')
    await wrapper.get('[data-testid="delivery-closure-send"]').trigger('click')
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Enviando')
    expect(wrapper.get('[data-testid="delivery-closure-send"]').element.disabled).toBe(true)
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual(['projects/7/delivery/stages/11/closure-email/prepare/', `projects/7/delivery/closure-emails/${emailId}/send/`])
    completeSend({ data: createEmail({ status: 'sent', attempts: [createAttempt('sent')] }) })
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Enviado')
  })

  // Detecta que editar el mensaje o los adjuntos reutilice la confirmación de una selección anterior.
  it.each([
    { selector: '[data-testid="delivery-closure-message"]', value: 'Mensaje corregido.' },
    { selector: '[data-testid="delivery-closure-document-31"] input', value: true },
    { selector: '[data-testid="delivery-closure-include-record"] input', value: true },
  ])('requires another preview after changing $selector', async ({ selector, value }) => {
    const wrapper = await renderEmail()
    await prepare(wrapper)
    await confirm(wrapper)
    await wrapper.get(selector).setValue(value)
    expect(wrapper.get('[data-testid="delivery-closure-reviewed"] input').element.checked).toBe(false)
    expect(wrapper.get('[data-testid="delivery-closure-send"]').element.disabled).toBe(true)
    expect(wrapper.get('[data-testid="delivery-closure-stale"]').text()).toBe('La selección cambió. Prepara una nueva vista previa y revísala antes de enviar.')
  })

  // Detecta que otra copia preparada mantenga la confirmación del correo anterior.
  it('clears confirmation when preparing a different preview', async () => {
    const wrapper = await renderEmail()
    await prepare(wrapper)
    await confirm(wrapper)
    await prepare(wrapper, createEmail({ id: resendId, manifest_sha256: 'b'.repeat(64), text_body: 'Nueva copia preparada para revisar.' }))
    expect(wrapper.get('[data-testid="delivery-closure-body"]').text()).toBe('Nueva copia preparada para revisar.')
    expect(wrapper.get('[data-testid="delivery-closure-reviewed"] input').element.checked).toBe(false)
    expect(wrapper.get('[data-testid="delivery-closure-send"]').element.disabled).toBe(true)
  })

  // Detecta que un rechazo de permisos se oculte detrás de una vista previa utilizable.
  it('shows the permission error returned when preparing an email', async () => {
    const wrapper = await renderEmail()
    api.request.mockRejectedValueOnce({ response: { status: 403, data: { detail: 'Sólo el administrador puede preparar este correo.' } } })
    await wrapper.get('[data-testid="delivery-closure-prepare"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-error"]').text()).toBe('Sólo el administrador puede preparar este correo.')
    expect(wrapper.findAll('[data-testid="delivery-closure-preview"]')).toHaveLength(0)
  })

  // Detecta que se prepare un correo cuando no fue posible cargar las versiones autorizadas.
  it('offers a retry after the history request fails', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 403, data: { detail: 'No puedes consultar este historial.' } } })
    const wrapper = await renderEmail()
    expect(wrapper.get('[data-testid="delivery-closure-history-error"]').text()).toBe('No puedes consultar este historial.')
    expect(wrapper.get('[data-testid="delivery-closure-history-retry"]').text()).toBe('Reintentar')
    expect(api.request).not.toHaveBeenCalled()
  })

  // Detecta que un rechazo del proveedor aparezca como enviado o genere un reenvío automático.
  it('shows the failed send retained by the backend', async () => {
    const wrapper = await renderEmail()
    await prepare(wrapper)
    await confirm(wrapper)
    api.request.mockResolvedValueOnce({ data: createEmail({ status: 'failed', error_message: 'El proveedor rechazó el envío.', attempts: [createAttempt('failed')] }) })
    await wrapper.get('[data-testid="delivery-closure-send"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Envío fallido')
    expect(wrapper.get('[data-testid="delivery-closure-preview"]').text()).toContain('El proveedor rechazó el envío.')
    expect(wrapper.get('[data-testid="delivery-closure-attempts"]').text()).toContain('Envío fallido')
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual(['projects/7/delivery/stages/11/closure-email/prepare/', `projects/7/delivery/closure-emails/${emailId}/send/`])
  })

  // Detecta una afirmación de no envío cuando se perdió la respuesta y tampoco pudo consultarse el resultado.
  it.each([
    { action: 'email detail', selector: '[data-testid="delivery-closure-check-result"]', response: { data: createEmail({ status: 'sent', attempts: [createAttempt('sent')] }) } },
    { action: 'stage history', selector: '[data-testid="delivery-closure-history-refresh"]', response: { data: createHistory({ emails: [createEmail({ status: 'sent', attempts: [createAttempt('sent')] })] }) } },
  ])('keeps an unconfirmed send blocked until checking $action', async ({ selector, response }) => {
    const wrapper = await renderEmail()
    await prepare(wrapper)
    await confirm(wrapper)
    api.request.mockRejectedValueOnce(new Error('Connection lost'))
    api.get.mockRejectedValueOnce(new Error('Connection lost'))
    await wrapper.get('[data-testid="delivery-closure-send"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Resultado sin confirmar')
    expect(wrapper.get('[data-testid="delivery-closure-send"]').element.disabled).toBe(true)
    expect(wrapper.get('[data-testid="delivery-closure-unknown"]').text()).toBe('No se pudo confirmar el resultado. Consulta el estado antes de preparar un reenvío.')
    expect(wrapper.findAll('[data-testid="delivery-closure-not-sent"]')).toHaveLength(0)
    api.get.mockResolvedValueOnce(response)
    await wrapper.get(selector).trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Enviado')
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual(['projects/7/delivery/stages/11/closure-email/prepare/', `projects/7/delivery/closure-emails/${emailId}/send/`])
  })

  // Detecta un reenvío que copie la confirmación previa o se ejecute antes de revisar su nueva vista previa.
  it('prepares a manual resend for a fresh confirmation', async () => {
    api.get.mockResolvedValueOnce({ data: createHistory({ emails: [createEmail({ status: 'sent', attempts: [createAttempt('sent')] })] }) })
    const wrapper = await renderEmail()
    api.request.mockResolvedValueOnce({ data: createEmail({ id: resendId }) })
    await wrapper.get(`[data-testid="delivery-closure-resend-${emailId}"]`).trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-reviewed"] input').element.checked).toBe(false)
    expect(wrapper.get('[data-testid="delivery-closure-send"]').element.disabled).toBe(true)
    expect(api.request.mock.calls.map(([request]) => request.url)).toEqual([`projects/7/delivery/closure-emails/${emailId}/resend/prepare/`])
    await confirm(wrapper)
    api.request.mockResolvedValueOnce({ data: createEmail({ id: resendId, status: 'sent', attempts: [createAttempt('sent')] }) })
    await wrapper.get('[data-testid="delivery-closure-send"]').trigger('click')
    await flushPromises()
    expect(api.request.mock.calls[1][0].data.preview_sha256).toBe(digest)
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Enviado')
  })

  // Detecta que consultar un correo conservado dispare una entrega o cambie su texto.
  it('loads the retained contents only after opening a history item', async () => {
    api.get.mockResolvedValueOnce({ data: createHistory({ emails: [createEmail({ status: 'sent', attempts: [createAttempt('sent')] })] }) })
    const wrapper = await renderEmail()
    api.get.mockResolvedValueOnce({ data: createEmail({ status: 'sent', text_body: 'Constancia conservada de la etapa aprobada.', attempts: [createAttempt('sent')] }) })
    await wrapper.get(`[data-testid="delivery-closure-inspect-${emailId}"]`).trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-body"]').text()).toBe('Constancia conservada de la etapa aprobada.')
    expect(wrapper.get('[data-testid="delivery-closure-status"]').text()).toBe('Enviado')
    expect(api.request).not.toHaveBeenCalled()
  })

  // Detecta que consultar una copia anterior la coloque por delante de los correos más recientes.
  it('preserves the history order when inspecting an older email', async () => {
    api.get.mockResolvedValueOnce({ data: createHistory({ emails: [
      createEmail({ id: resendId, subject: 'Constancia más reciente' }),
      createEmail({ status: 'sent', subject: 'Constancia anterior', attempts: [createAttempt('sent')] }),
    ] }) })
    const wrapper = await renderEmail()
    api.get.mockResolvedValueOnce({ data: createEmail({ status: 'sent', subject: 'Constancia anterior', attempts: [createAttempt('sent')] }) })
    await wrapper.get(`[data-testid="delivery-closure-inspect-${emailId}"]`).trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="delivery-closure-history"]').findAll('article').map((row) => row.get('p').text())).toEqual(['Constancia más reciente', 'Constancia anterior'])
  })

  // Detecta que una copia privada inaccesible se descargue sin JWT o silencie el rechazo recibido.
  it('shows the rejection of a private attachment download', async () => {
    const wrapper = await renderEmail()
    await prepare(wrapper, createEmail({ attachments: [createAttachment()] }))
    api.get.mockRejectedValueOnce({ response: { status: 403, data: { detail: 'No puedes descargar esta copia.' } } })
    await wrapper.get('[data-testid="delivery-closure-download-file-31"]').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith(`/api/accounts/projects/7/delivery/closure-emails/${emailId}/attachments/file-31/download/`, { responseType: 'blob', baseURL: '' })
    expect(wrapper.get('[data-testid="delivery-closure-error"]').text()).toBe('No puedes descargar esta copia.')
  })
})
