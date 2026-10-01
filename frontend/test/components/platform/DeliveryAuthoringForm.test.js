import { mount } from '@vue/test-utils'
import DeliveryAuthoringForm from '../../../components/platform/delivery/DeliveryAuthoringForm.vue'
import spanish from '../../../locales/platformDelivery/es'

const createDraft = (overrides = {}) => ({ key: 'client-guide', title: 'Invoice validation', ...overrides })
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key

describe('Delivery draft authoring', () => {
  const wrappers = []
  beforeEach(() => { global.useI18n = () => ({ t: translate }) })
  afterEach(() => { wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0; delete global.useI18n })
  const renderForm = (props = {}) => {
    const wrapper = mount(DeliveryAuthoringForm, { props: { entity: 'contracts', initial: createDraft(), ...props }, global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } } })
    wrappers.push(wrapper)
    return wrapper
  }

  it('submits a contract using the contract API fields', async () => {
    const wrapper = renderForm()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0]).toEqual({ key: 'client-guide', title: 'Invoice validation', document_id: null, proposal_document_id: null, client_visible: true })
  })

  it('links a scope to its original contract', async () => {
    const wrapper = renderForm({ entity: 'scopes', initial: createDraft({ contract_id: 8, description: 'Agreed work', amendment_id: 2 }), contracts: [{ id: 8, title: 'Service agreement', amendments: [{ id: 2, title: 'Additional work' }] }] })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0]).toEqual({ key: 'client-guide', title: 'Invoice validation', description: 'Agreed work', contract_id: 8, amendment_id: 2, is_current: true })
  })

  it('keeps a new stage attached to the selected phase', async () => {
    const wrapper = renderForm({ entity: 'stages', initial: createDraft({ phase_id: 3 }) })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].phase_id).toBe(3)
  })

  it('turns separate guide lines into ordered test steps', async () => {
    const wrapper = renderForm({ entity: 'requirements', initial: createDraft({ stage_id: 11 }) })
    await wrapper.get('#delivery-author-steps').setValue('Open invoices\n\nSelect the prepared invoice')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].guide.steps).toEqual(['Open invoices', 'Select the prepared invoice'])
  })
})
