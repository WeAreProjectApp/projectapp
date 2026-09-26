import { mount } from '@vue/test-utils'
import CollectionActionsModal from '~/components/accounting/CollectionActionsModal.vue'

const RECORD = {
  id: 14,
  public_number: 'PA-0014',
  client_display_name: 'Acme',
  total: '2500000.00',
  commercial_status: 'issued',
  income_kind: 'expected',
  notes: 'Llamar antes de enviar.',
  can_delete: true,
}

function mountModal(record = RECORD, props = {}) {
  return mount(CollectionActionsModal, {
    props: { open: true, record, ...props },
    global: {
      stubs: {
        BaseModal: {
          props: ['modelValue', 'kind'],
          emits: ['close'],
          template: '<div><slot /></div>',
        },
        BaseButton: {
          emits: ['click'],
          template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

describe('CollectionActionsModal', () => {
  it('shows all applicable actions for an issued expected account', () => {
    const wrapper = mountModal()

    expect(wrapper.findAll('[data-testid^="collection-"]')
      .map((node) => node.attributes('data-testid'))).toEqual(expect.arrayContaining([
      'collection-view-detail-14',
      'collection-notes-14',
      'collection-download-pdf-14',
      'collection-emails-14',
      'collection-resend-14',
      'collection-mark-paid-14',
      'collection-cancel-14',
      'collection-delete-14',
    ]))
  })

  it('uses the liquidation wording when the linked income is expected', () => {
    const wrapper = mountModal()

    expect(wrapper.get('[data-testid="collection-mark-paid-14"]').text())
      .toBe('Registrar pago (liquidar)')
  })

  it('drops status-dependent actions once the account is cancelled', () => {
    const wrapper = mountModal({
      ...RECORD, commercial_status: 'cancelled', notes: '', can_delete: false,
    })

    expect(wrapper.find('[data-testid="collection-notes-14"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="collection-resend-14"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="collection-mark-paid-14"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="collection-cancel-14"]').exists()).toBe(false)
  })

  it('emits the selected action with its row and closes the menu', async () => {
    const wrapper = mountModal()

    await wrapper.get('[data-testid="collection-download-pdf-14"]').trigger('click')

    expect(wrapper.emitted('download')[0]).toEqual([RECORD])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  // The detail modal carries the account's history, like every accounting
  // menu's first entry, so it reads the same as on the other tabs.
  it('names the detail entry as the account history', () => {
    const wrapper = mountModal()

    expect(wrapper.get('[data-testid="collection-view-detail-14"]').text())
      .toBe('Detalle e historial')
  })
})
