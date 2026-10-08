import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import DeliveryWorkspace from '../../../components/platform/delivery/DeliveryWorkspace.vue'
import spanish from '../../../locales/platformDelivery/es'

jest.mock('../../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
jest.mock('../../../composables/useClipboardFeedback', () => ({
  useClipboardFeedback: () => ({ copyText: jest.fn().mockResolvedValue(true) }),
}))

const { usePlatformApi } = require('../../../composables/usePlatformApi')
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key
const createWorkspace = () => ({
  project: { id: 7, name: 'Proyecto de inventario', documents: [] }, version: 4, is_admin: false,
  contracts: [{ id: 3, key: 'contract', title: 'Contrato de inventario', signature_status: 'portal', documents: [], amendments: [] }],
  scopes: [{ id: 2, key: 'scope', title: 'Inventario', contract_id: 3, documents: [], phases: [{
    id: 5, key: 'phase', title: 'Fase de inventario', status: 'in_review', documents: [], stages: [{
      id: 11, key: 'stage', title: 'Revisión del inventario', status: 'in_review', editorial_status: 'published', publication_id: 9,
      documents: [], messages: [], requirements: [{
        id: 20, key: 'transfer', title: 'Traslado de prueba', version: 2, review_status: 'in_review', documents: [], reviews: [],
        guide: { environment: 'Staging', steps: ['Abrir el traslado.'], expected_result: 'La sucursal recibe las cantidades.' },
      }],
    }],
  }] }],
})
const failures = [
  { label: 'version conflict', error: { response: { status: 409, data: { detail: 'Versión desactualizada.' } } }, message: spanish.conflict },
  { label: 'permission denial', error: { response: { status: 403, data: { detail: 'No puedes registrar este resultado.' } } }, message: 'No puedes registrar este resultado.' },
  { label: 'server failure', error: { response: { status: 503, data: { detail: 'No se pudo guardar el reporte.' } } }, message: 'No se pudo guardar el reporte.' },
  { label: 'lost connection', error: new Error('Connection lost'), message: spanish.actionError },
]

describe('Delivery workspace failed submissions', () => {
  let api
  let wrapper
  beforeEach(() => {
    setActivePinia(createPinia())
    global.useI18n = () => ({ t: translate, locale: ref('es-CO') })
    global.useLocalePath = () => (value) => typeof value === 'string' ? value : value.path
    global.useRoute = () => ({ query: {} })
    api = { get: jest.fn().mockResolvedValue({ data: createWorkspace() }), request: jest.fn() }
    usePlatformApi.mockReturnValue(api)
  })
  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
    delete global.useI18n
    delete global.useLocalePath
    delete global.useRoute
    jest.clearAllMocks()
  })
  async function renderWorkspace() {
    wrapper = mount(DeliveryWorkspace, {
      props: { projectId: 7 }, attachTo: document.body,
      global: { stubs: { teleport: true, NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } },
    })
    await flushPromises()
    return wrapper
  }
  async function enterObservation() {
    await wrapper.get('[data-testid="delivery-review-open-11"]').trigger('click')
    await wrapper.get('[data-testid="delivery-review-decision-20"]').setValue('objected')
    await wrapper.get('[data-testid="delivery-review-message-20"]').setValue('El traslado no conserva las cantidades.')
  }

  // Detecta que la vista del cliente consulte el catálogo administrativo de avisos.
  it('keeps administrative notice history outside the client workspace', async () => {
    await renderWorkspace()

    expect(wrapper.findAll('[data-testid="delivery-notice-history"]')).toHaveLength(0)
    expect(wrapper.get('[data-testid="delivery-stage-11"]').text()).toContain('Revisión del inventario')
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledWith('projects/7/delivery/')
  })

  // Detecta que fallar el guardado descarte el motivo escrito por el cliente.
  it.each(failures)('preserves an unsent review after $label', async ({ error, message }) => {
    api.request.mockRejectedValueOnce(error)
    await renderWorkspace()
    await enterObservation()

    await wrapper.get('[data-testid="delivery-review-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="delivery-review-form"]').text()).toContain(message)
    expect(wrapper.get('[data-testid="delivery-review-message-20"]').element.value).toBe('El traslado no conserva las cantidades.')
    expect(wrapper.get('[data-testid="delivery-review-decision-20"]').element.value).toBe('objected')
  })

  // Detecta que una respuesta fallida cierre el editor sin guardar el texto.
  it.each(failures)('preserves an unsent response after $label', async ({ error, message }) => {
    api.request.mockRejectedValueOnce(error)
    await renderWorkspace()
    await wrapper.get('[data-testid="delivery-report-open-11"]').trigger('click')
    await wrapper.get('[data-testid="delivery-report-message"]').setValue('Voy a comprobar el traslado con el registro preparado.')

    await wrapper.get('[data-testid="delivery-report-submit"]').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="dialog"]').text()).toContain(message)
    expect(wrapper.get('[data-testid="delivery-report-message"]').element.value).toBe('Voy a comprobar el traslado con el registro preparado.')
    expect(wrapper.get('[data-testid="delivery-requirement-20"]').text()).toContain('En revisión')
  })

  // Detecta que reintentar una revisión incierta cree otra identidad de operación.
  it('retries the retained observation with the original request identifier', async () => {
    api.request.mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce({ data: createWorkspace() })
    await renderWorkspace()
    await enterObservation()
    await wrapper.get('[data-testid="delivery-review-form"]').trigger('submit')
    await flushPromises()

    await wrapper.get('[data-testid="delivery-review-form"]').trigger('submit')
    await flushPromises()

    expect(api.request.mock.calls[1][0].data.request_id).toBe(api.request.mock.calls[0][0].data.request_id)
    expect(api.request.mock.calls[1][0].data.decisions).toEqual([{ requirement_id: 20, version: 2, decision: 'objected', message: 'El traslado no conserva las cantidades.', environment: 'Staging' }])
    expect(wrapper.findAll('[data-testid="delivery-review-form"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('Tus resultados quedaron registrados.')
  })
})
