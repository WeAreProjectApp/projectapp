import { flushPromises, mount } from '@vue/test-utils'
import DeliveryNoticeHistory from '../../../components/platform/delivery/DeliveryNoticeHistory.vue'
import spanish from '../../../locales/platformDelivery/es'

jest.mock('../../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../../composables/usePlatformApi')
const mountOptions = { props: { projectId: 7 }, global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } } }
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key
const eventId = '1cf423a3-737b-4d76-ae2a-90a1a867aaad'
const createEvent = (overrides = {}) => ({
  id: eventId, subject: 'Etapa disponible: Inventario', recipients: ['client@example.test'],
  status: 'failed', version: 3, text_body: 'Revisa el traslado publicado en el proyecto de pruebas.',
  preview_sha256: 'a'.repeat(64), ...overrides,
})
const history = (events = [createEvent()]) => ({ count: events.length, page: 1, results: events })
const deferred = () => {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

describe('Administrative delivery notice history', () => {
  let api
  let wrapper
  beforeEach(() => {
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2026-10-07T12:00:00Z'))
    global.useI18n = () => ({ t: translate })
    api = { get: jest.fn().mockResolvedValue({ data: history() }), post: jest.fn() }
    usePlatformApi.mockReturnValue(api)
  })
  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    delete global.useI18n
    jest.useRealTimers()
    jest.clearAllMocks()
  })
  async function renderHistory() {
    wrapper = mount(DeliveryNoticeHistory, mountOptions)
    await flushPromises()
  }
  const button = (label) => wrapper.findAll('button').find((item) => item.text() === label)
  async function prepareRetry() {
    api.get.mockResolvedValueOnce({ data: createEvent() })
    await button(spanish.notices.preview).trigger('click')
    await flushPromises()
  }

  // Detecta que abrir el contenido conservado envíe un aviso sin confirmación.
  it('previews the retained failure without sending it', async () => {
    await renderHistory()

    await prepareRetry()

    expect(wrapper.get('[data-testid="delivery-notice-retry-preview"]').text()).toContain('Revisa el traslado publicado en el proyecto de pruebas.')
    expect(api.get).toHaveBeenLastCalledWith(`projects/7/delivery/notices/${eventId}/retry-preview/`, { params: { expected_version: 3 } })
    expect(api.post).not.toHaveBeenCalled()
  })

  // Detecta que confirmar reenvíe una versión o huella distintas a las revisadas.
  it('sends the reviewed notice manifest', async () => {
    api.post.mockResolvedValueOnce({ data: createEvent({ status: 'sent' }) })
    await renderHistory()
    await prepareRetry()
    api.get.mockResolvedValueOnce({ data: history([createEvent({ status: 'sent' })]) })

    await button(spanish.notices.confirm).trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith(`projects/7/delivery/notices/${eventId}/retry/`, { expected_version: 3, preview_sha256: 'a'.repeat(64), request_id: expect.any(String) })
    expect(wrapper.findAll('[data-testid="delivery-notice-retry-preview"]')).toHaveLength(0)
    expect(wrapper.get('[data-testid="delivery-notice-history"]').text()).toContain(spanish.notices.status.sent)
  })

  // Detecta que una respuesta de red perdida genere otro identificador de envío.
  it('reuses the retry identifier after losing the response', async () => {
    api.post.mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce({ data: createEvent({ status: 'sent' }) })
    await renderHistory()
    await prepareRetry()
    await button(spanish.notices.confirm).trigger('click')
    await flushPromises()

    await button(spanish.notices.confirm).trigger('click')
    await flushPromises()

    expect(api.post.mock.calls[1][1].request_id).toBe(api.post.mock.calls[0][1].request_id)
    expect(wrapper.findAll('[data-testid="delivery-notice-retry-preview"]')).toHaveLength(0)
  })

  // Detecta que se ofrezca reintento para un transporte cuyo resultado no se conoce.
  it.each(['unknown', 'sending'])('withholds retry for a $0 notice', async (status) => {
    api.get.mockResolvedValueOnce({ data: history([createEvent({ status })]) })

    await renderHistory()

    expect(wrapper.text()).toContain(spanish.notices.uncertain)
    expect(wrapper.findAll('button').map((item) => item.text())).toEqual([spanish.refresh])
  })

  // Detecta que una lectura antigua vuelva a mostrar el correo de otro proyecto.
  it('ignores a history response from the previous project', async () => {
    const oldRequest = deferred()
    api.get.mockReturnValueOnce(oldRequest.promise).mockResolvedValueOnce({ data: history([createEvent({ subject: 'Aviso del proyecto actual' })]) })
    wrapper = mount(DeliveryNoticeHistory, mountOptions)
    await wrapper.setProps({ projectId: 8 })
    await flushPromises()

    oldRequest.resolve({ data: history([createEvent({ subject: 'Aviso antiguo privado' })]) })
    await flushPromises()

    expect(wrapper.text()).toContain('Aviso del proyecto actual')
    expect(wrapper.text()).not.toContain('Aviso antiguo privado')
  })

  // Detecta que navegar a otro proyecto conserve correos anteriores mientras carga.
  it('clears the previous project notice during navigation', async () => {
    await renderHistory()
    const nextRequest = deferred()
    api.get.mockReturnValueOnce(nextRequest.promise)

    await wrapper.setProps({ projectId: 8 })

    expect(wrapper.text()).not.toContain('Etapa disponible: Inventario')
    expect(wrapper.text()).not.toContain('client@example.test')
    expect(wrapper.get('[data-testid="delivery-notice-history"]').text()).toContain(spanish.notices.title)
  })

  // Detecta que una preparación lenta termine mostrando un reintento del proyecto anterior.
  it('ignores a retry preview from the previous project', async () => {
    await renderHistory()
    const oldPreview = deferred()
    api.get.mockReturnValueOnce(oldPreview.promise)
    await button(spanish.notices.preview).trigger('click')
    api.get.mockResolvedValueOnce({ data: history([]) })
    await wrapper.setProps({ projectId: 8 })
    await flushPromises()

    oldPreview.resolve({ data: createEvent() })
    await flushPromises()

    expect(wrapper.findAll('[data-testid="delivery-notice-retry-preview"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('client@example.test')
    expect(api.post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain(spanish.notices.empty)
  })
})
