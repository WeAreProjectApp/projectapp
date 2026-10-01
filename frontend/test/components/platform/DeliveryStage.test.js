import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import DeliveryStage from '../../../components/platform/delivery/DeliveryStage.vue'
import spanish from '../../../locales/platformDelivery/es'

const createRequirement = (overrides = {}) => ({ id: 20, key: 'invoice', title: 'Review invoice', version: 2, review_status: 'in_review', guide: { role: 'Client', steps: ['Open the invoice'], expected_result: 'Shows the agreed total' }, documents: [], reviews: [], ...overrides })
const createStage = (overrides = {}) => ({ id: 11, key: 'invoices', title: 'Invoice review', editorial_status: 'published', publication_id: 9, status: 'in_review', requirements: [createRequirement()], documents: [], messages: [], ...overrides })
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key

describe('Published delivery stage', () => {
  const wrappers = []
  beforeEach(() => {
    global.useI18n = () => ({ t: translate, locale: ref('es-CO') })
    global.useLocalePath = () => (value) => typeof value === 'string' ? value : `${value.path}?stage=${value.query.stage}`
    global.useRoute = () => ({ query: {} })
  })
  afterEach(() => {
    wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0
    delete global.useI18n; delete global.useLocalePath; delete global.useRoute
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
})
