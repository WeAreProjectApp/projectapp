import { mount } from '@vue/test-utils'
import DeliveryAuthoringForm from '../../../components/platform/delivery/DeliveryAuthoringForm.vue'
import spanish from '../../../locales/platformDelivery/es'

const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key

describe('Confirmed contractual source selection', () => {
  let wrapper
  beforeEach(() => { global.useI18n = () => ({ t: translate }) })
  afterEach(() => { wrapper?.unmount(); delete global.useI18n })
  const render = (initial = {}) => {
    wrapper = mount(DeliveryAuthoringForm, { props: {
      entity: 'contracts', initial: { key: 'confirmed', title: 'Confirmed agreement', ...initial },
      documents: [{ id: 8, title: 'Existing document' }],
      proposalDocuments: [{ id: 9, title: 'Proposal contract' }],
      approvalFiles: [{ id: 12, title: 'Custom agreement', filename: 'agreement.docx' }],
    }, global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } } })
    return wrapper
  }

  it('requires a contractual source before saving', async () => {
    render()

    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('[data-testid="delivery-source-error"]').text()).toBe('Selecciona una sola fuente del contrato.')
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('selects the confirmed file instead of the prior document', async () => {
    render({ document_id: 8 })

    await wrapper.get('#delivery-author-approval-file').setValue('12')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')[0][0]).toEqual({
      key: 'confirmed', title: 'Confirmed agreement', approval_file_id: 12,
      document_id: null, proposal_document_id: null, client_visible: false,
    })
    expect(wrapper.get('[data-testid="delivery-approval-private"]').text()).toContain('sin firma registrada')
  })

  it('clears a confirmed file after choosing a proposal document', async () => {
    render({ approval_file_id: 12 })

    await wrapper.get('#delivery-author-proposal').setValue('9')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')[0][0]).toEqual(expect.objectContaining({
      proposal_document_id: 9, approval_file_id: null, document_id: null,
    }))
    expect(wrapper.find('[data-testid="delivery-approval-private"]').exists()).toBe(false)
  })

  it('keeps visibility explicitly enabled on an existing contract', async () => {
    render({ id: 3, approval_file_id: 12, client_visible: true })

    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')[0][0].client_visible).toBe(true)
    expect(wrapper.find('[data-testid="delivery-approval-private"]').exists()).toBe(false)
  })

  it('identifies the confirmed original by filename', () => {
    render()

    expect(wrapper.get('#delivery-author-approval-file').text()).toContain('Custom agreement · agreement.docx')
  })
})
