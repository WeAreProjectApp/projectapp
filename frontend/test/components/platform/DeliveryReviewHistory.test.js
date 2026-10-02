import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import DeliveryReviewHistory from '../../../components/platform/delivery/DeliveryReviewHistory.vue'
import spanish from '../../../locales/platformDelivery/es'

// Matches the review DTO from accounts.services.delivery_workflow.overview.
const createReview = (overrides = {}) => ({
  id: 1, decision: 'objected', message: 'The invoice total is incorrect.',
  environment: 'Test site', is_external: false, actor_name: 'Administrator',
  original_reviewer: 'Client tester', reviewed_at: '2026-09-28T12:00:00Z',
  recorded_at: '2026-09-30T14:00:00Z', version: 2, publication_id: 9,
  client_statement: '', actor_id: 7, requirement_id: 20,
  evidence_channel: 'platform', source_message_id: null, evidence_document_ids: [],
  ...overrides,
})
const createEvidenceDocument = (overrides = {}) => ({
  id: 12, review_id: 1, document_id: 8, title: 'Client approval email',
  pdf_url: '/api/accounts/projects/7/delivery/reviews/1/evidence/12/pdf/',
  sha256: 'a'.repeat(64), created_at: '2026-09-30T14:00:00Z', ...overrides,
})
const translate = (key, values) => (key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key).replace('{version}', values?.version || '')

describe('Requirement review evidence', () => {
  const wrappers = []
  beforeEach(() => { global.useI18n = () => ({ t: translate, locale: ref('es-CO') }) })
  afterEach(() => { wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0; delete global.useI18n })
  const renderHistory = (review) => {
    const wrapper = mount(DeliveryReviewHistory, {
      props: { reviews: [review] },
      global: { stubs: { NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } },
    })
    wrappers.push(wrapper)
    return wrapper
  }

  it('shows the reason against the reviewed version', () => {
    const wrapper = renderHistory(createReview())
    expect(wrapper.text()).toContain('The invoice total is incorrect.')
    expect(wrapper.text()).toContain('Versión 2')
    expect(wrapper.text()).toContain('Test site')
  })

  it('distinguishes the client approver from the external evidence recorder', () => {
    const wrapper = renderHistory(createReview({ decision: 'approved', is_external: true, evidence_channel: 'email' }))
    expect(wrapper.text()).toContain('Conformidad externa')
    expect(wrapper.text()).toContain('Client tester')
    expect(wrapper.text()).toContain('Registrado porAdministrator')
    expect(wrapper.text()).toContain('Correo')
  })

  it('shows the incoming client statement from the review DTO', () => {
    const wrapper = renderHistory(createReview({
      decision: 'approved', is_external: true, evidence_channel: 'email',
      source_message_id: 4, client_statement: 'Confirmo que las facturas funcionan como acordamos.',
    }))

    expect(wrapper.text()).toContain('Evidencia expresa del cliente')
    expect(wrapper.text()).toContain('Confirmo que las facturas funcionan como acordamos.')
  })

  it('downloads evidence offered by the backend', async () => {
    const document = createEvidenceDocument()
    const wrapper = renderHistory(createReview({
      evidence_document_ids: [8], evidence_documents: [document],
    }))

    await wrapper.get('[data-testid="delivery-document-download-12"]').trigger('click')

    expect(wrapper.text()).toContain('Client approval email')
    expect(wrapper.emitted('download')[0][0]).toEqual(document)
  })

  it('keeps document IDs without metadata outside download actions', () => {
    const wrapper = renderHistory(createReview({ evidence_document_ids: [8] }))

    expect(wrapper.find('[data-testid="delivery-documents"]').exists()).toBe(false)
    expect(wrapper.emitted('download')).toBeUndefined()
  })

  it('ignores metadata outside the recorded evidence IDs', () => {
    const wrapper = renderHistory(createReview({
      evidence_document_ids: [8], evidence_documents: [createEvidenceDocument({ document_id: 99 })],
    }))

    expect(wrapper.text()).not.toContain('Client approval email')
    expect(wrapper.find('[data-testid="delivery-document-download-12"]').exists()).toBe(false)
  })

  it('shows an evidence title without synthesizing a download URL', () => {
    const wrapper = renderHistory(createReview({
      evidence_document_ids: [8], evidence_documents: [createEvidenceDocument({ pdf_url: undefined })],
    }))

    expect(wrapper.text()).toContain('Client approval email')
    expect(wrapper.find('[data-testid="delivery-document-download-12"]').exists()).toBe(false)
  })
})
