import { mount } from '@vue/test-utils'
import DeliveryReviewForm from '../../../components/platform/delivery/DeliveryReviewForm.vue'
import DeliveryDocumentPicker from '../../../components/platform/delivery/DeliveryDocumentPicker.vue'
import spanish from '../../../locales/platformDelivery/es'

const createRequirement = (overrides = {}) => ({ id: 20, title: 'Check the invoice', version: 2, review_status: 'in_review', guide: { environment: 'Client test site' }, ...overrides })
const createStage = (overrides = {}) => ({ id: 11, title: 'Invoice review', requirements: [createRequirement(), createRequirement({ id: 21, title: 'Check email', review_status: 'approved' }), createRequirement({ id: 22, title: 'Check totals' })], ...overrides })
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key

describe('Client requirement review', () => {
  const wrappers = []
  beforeEach(() => { global.useI18n = () => ({ t: translate }) })
  afterEach(() => { wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0; delete global.useI18n })
  const renderForm = (props = {}) => {
    const wrapper = mount(DeliveryReviewForm, { props: { stage: createStage(), ...props }, global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } } })
    wrappers.push(wrapper)
    return wrapper
  }

  it('submits only the requirement the client approved', async () => {
    const wrapper = renderForm()
    await wrapper.get('[data-testid="delivery-review-decision-20"]').setValue('approved')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].decisions).toEqual([{ requirement_id: 20, version: 2, decision: 'approved', message: '', environment: 'Client test site' }])
  })

  it('keeps an earlier approval outside the editable results', () => {
    const wrapper = renderForm()
    expect(wrapper.find('[data-testid="delivery-review-decision-21"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="delivery-review-requirement-21"]').text()).toContain('Conformidad conservada')
  })

  it('requires an observation when a client objects', async () => {
    const wrapper = renderForm()
    await wrapper.get('[data-testid="delivery-review-decision-20"]').setValue('objected')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('Describe el motivo de la objeción o rechazo.')
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('keeps an objected requirement out of the current decisions', () => {
    const wrapper = renderForm({ stage: createStage({ requirements: [createRequirement({ review_status: 'objected' })] }) })
    expect(wrapper.find('[data-testid="delivery-review-decision-20"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('El equipo abrirá una nueva ronda')
  })

  it('records the reason for a rejected result', async () => {
    const wrapper = renderForm()
    await wrapper.get('[data-testid="delivery-review-decision-20"]').setValue('rejected')
    await wrapper.get('[data-testid="delivery-review-message-20"]').setValue('Invoice has the wrong total')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].decisions[0]).toEqual(expect.objectContaining({ decision: 'rejected', message: 'Invoice has the wrong total' }))
  })

  it('requires client evidence for a historical approval', async () => {
    const wrapper = renderForm({ historical: true })
    await wrapper.get('[data-testid="delivery-review-decision-20"]').setValue('approved')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('Transcribe la conformidad expresa del cliente')
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('links a selected evidence document to a historical approval', async () => {
    const wrapper = renderForm({ historical: true, documents: [{ id: 8, title: 'Client email approval' }], evidenceMessages: [{ id: 4, subject: 'Conformidad', original_reviewer: 'Client', content: 'Conforme con las facturas.' }] })
    await wrapper.get('[data-testid="delivery-review-decision-20"]').setValue('approved')
    await wrapper.get('[data-testid="delivery-historical-source"]').setValue('4')
    await wrapper.get('[data-testid="delivery-review-report-message"]').setValue('Conforme con las facturas.')
    await wrapper.get('[data-testid="delivery-historical-client-statement"] input').setValue(true)
    await wrapper.findComponent(DeliveryDocumentPicker).get('input').setValue(true)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].evidence_document_ids).toEqual([8])
  })
})
