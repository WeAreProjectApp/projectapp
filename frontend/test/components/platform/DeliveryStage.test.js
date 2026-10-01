import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import DeliveryStage from '../../../components/platform/delivery/DeliveryStage.vue'
import DeliveryClosureEmail from '../../../components/platform/delivery/DeliveryClosureEmail.vue'
import { usePlatformDeliveryStore } from '../../../stores/platform-delivery'
import spanish from '../../../locales/platformDelivery/es'

jest.mock('../../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
const { usePlatformApi } = require('../../../composables/usePlatformApi')
const createRequirement = (overrides = {}) => ({ id: 20, key: 'invoice', title: 'Review invoice', version: 2, review_status: 'in_review', guide: { role: 'Client', steps: ['Open the invoice'], expected_result: 'Shows the agreed total' }, documents: [], reviews: [], ...overrides })
const createStage = (overrides = {}) => ({ id: 11, key: 'invoices', title: 'Invoice review', editorial_status: 'published', publication_id: 9, status: 'in_review', requirements: [createRequirement()], documents: [], messages: [], ...overrides })
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key

describe('Published delivery stage', () => {
  const wrappers = []
  let api
  beforeEach(() => {
    setActivePinia(createPinia())
    api = { get: jest.fn().mockResolvedValue({ data: { version: 4, available_documents: [], emails: [] } }), request: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    const store = usePlatformDeliveryStore()
    store.projectId = 7
    store.workspace = { version: 4, project: { id: 7 }, contracts: [], scopes: [] }
    global.useI18n = () => ({ t: translate, locale: ref('es-CO') })
    global.useLocalePath = () => (value) => typeof value === 'string' ? value : `${value.path}?stage=${value.query.stage}`
    global.useRoute = () => ({ query: {} })
  })
  afterEach(() => {
    wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0
    delete global.useI18n; delete global.useLocalePath; delete global.useRoute
    jest.clearAllMocks()
  })
  const renderStage = (props = {}) => {
    const wrapper = mount(DeliveryStage, { props: { projectId: 7, stage: createStage(), ...props }, global: { stubs: { NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    wrappers.push(wrapper)
    return wrapper
  }

  it('offers review against the last publication while edits are in draft', async () => {
    const wrapper = renderStage({ stage: createStage({ editorial_status: 'draft' }) })
    await wrapper.get('[data-testid="delivery-review-open-11"]').trigger('click')
    expect(wrapper.emitted('review')[0][0].publication_id).toBe(9)
  })

  it('hides client decisions before the first publication', () => {
    const wrapper = renderStage({ stage: createStage({ editorial_status: 'draft', publication_id: null }) })
    expect(wrapper.find('[data-testid="delivery-review-open-11"]').exists()).toBe(false)
  })

  it('lets the administrator reopen an objected round', async () => {
    const wrapper = renderStage({ isAdmin: true, stage: createStage({ requirements: [createRequirement({ review_status: 'objected' })] }) })
    const action = wrapper.get('[data-testid="delivery-publish-11"]')
    expect(action.text()).toBe('Abrir nueva ronda')
    await action.trigger('click')
    expect(wrapper.emitted('publish')[0][0].id).toBe(11)
  })

  it('waits for the next round after an objection', () => {
    const wrapper = renderStage({ stage: createStage({ requirements: [createRequirement({ review_status: 'objected' })] }) })
    expect(wrapper.find('[data-testid="delivery-review-open-11"]').exists()).toBe(false)
  })

  it('keeps a frozen requirement outside the admin editing actions', () => {
    const wrapper = renderStage({ isAdmin: true, stage: createStage({ requirements: [createRequirement({ review_status: 'approved' })] }) })
    expect(wrapper.find('[data-testid="delivery-edit-requirement-20"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Este requerimiento está aprobado.')
  })

  it('offers response preparation for an approved stage to the administrator', async () => {
    const wrapper = renderStage({ isAdmin: true, stage: createStage({ status: 'approved' }) })
    await wrapper.get('[data-testid="delivery-prepare-reply-11"]').trigger('click')
    expect(wrapper.emitted('prepare-reply')[0][0].id).toBe(11)
  })

  it('keeps response preparation out of client actions', () => {
    const wrapper = renderStage()
    expect(wrapper.find('[data-testid="delivery-prepare-reply-11"]').exists()).toBe(false)
  })

  // Detecta que una etapa totalmente aprobada no permita preparar su constancia manual.
  it('opens approval email preparation for a fully approved stage administrator', async () => {
    const wrapper = renderStage({ isAdmin: true, stage: createStage({ status: 'approved', requirements: [createRequirement({ review_status: 'approved' })] }) })
    await wrapper.get('[data-testid="delivery-closure-email-open-11"]').trigger('click')
    await flushPromises()
    expect(wrapper.getComponent(DeliveryClosureEmail).get('[data-testid="delivery-closure-history"]').text()).toContain('Todavía no se han preparado correos para esta etapa.')
    expect(api.get).toHaveBeenCalledWith('projects/7/delivery/stages/11/closure-email/history/')
    expect(api.request).not.toHaveBeenCalled()
  })

  // Detecta que se ofrezca la constancia a un cliente, una etapa incompleta o requerimientos sin conformidad total.
  it.each([
    { scenario: 'client', isAdmin: false, stage: createStage({ status: 'approved', requirements: [createRequirement({ review_status: 'approved' })] }) },
    { scenario: 'partial approval', isAdmin: true, stage: createStage({ status: 'in_review', requirements: [createRequirement({ review_status: 'approved' }), createRequirement({ id: 21 })] }) },
    { scenario: 'pending requirement', isAdmin: true, stage: createStage({ status: 'approved', requirements: [createRequirement({ review_status: 'approved' }), createRequirement({ id: 21 })] }) },
    { scenario: 'objected requirement', isAdmin: true, stage: createStage({ status: 'approved', requirements: [createRequirement({ review_status: 'objected' })] }) },
    { scenario: 'rejected stage', isAdmin: true, stage: createStage({ status: 'rejected', requirements: [createRequirement({ review_status: 'rejected' })] }) },
    { scenario: 'unpublished stage', isAdmin: true, stage: createStage({ status: 'approved', publication_id: null, requirements: [createRequirement({ review_status: 'approved' })] }) },
    { scenario: 'empty stage', isAdmin: true, stage: createStage({ status: 'approved', requirements: [] }) },
  ])('withholds the approval email action for $scenario', ({ isAdmin, stage }) => {
    const wrapper = renderStage({ isAdmin, stage })
    expect(wrapper.findAll('[data-testid="delivery-closure-email-open-11"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('Invoice review')
    expect(api.get).not.toHaveBeenCalled()
  })

  // Detecta que abrir otra acción sea posible mientras se está enviando el correo de la etapa.
  it('disables approval email preparation while the stage is busy', () => {
    const wrapper = renderStage({ isAdmin: true, busy: true, stage: createStage({ status: 'approved', requirements: [createRequirement({ review_status: 'approved' })] }) })
    expect(wrapper.get('[data-testid="delivery-closure-email-open-11"]').text()).toBe('Correo de conformidad')
    expect(wrapper.get('[data-testid="delivery-closure-email-open-11"]').element.disabled).toBe(true)
  })
})
