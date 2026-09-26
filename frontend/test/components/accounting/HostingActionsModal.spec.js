import { mount } from '@vue/test-utils'
import HostingActionsModal from '~/components/accounting/HostingActionsModal.vue'

const RECORD = {
  id: 8,
  domain_url: 'acme.co',
  client_name: 'Acme',
  billing_email: 'tesoreria@acme.co',
}

function mountModal(record = RECORD, props = {}) {
  return mount(HostingActionsModal, {
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

function entryIds(wrapper) {
  return wrapper.findAll('li button').map((node) => node.attributes('data-testid'))
}

describe('HostingActionsModal', () => {
  // Bug caught: below 1024px the history of a hosting could not be opened at
  // all, and above it the history sat as a loose button beside five icons.
  it('opens with the record history, then the hosting actions', () => {
    const wrapper = mountModal()

    expect(entryIds(wrapper)).toEqual([
      'hosting-history-8',
      'hosting-cycles-8',
      'hosting-send-billing-8',
      'hosting-emails-8',
      'hosting-edit-8',
      'hosting-delete-8',
    ])
  })

  it('offers the note right after the history when the hosting has one', async () => {
    const withNote = { ...RECORD, notes: 'Renueva el dominio en marzo' }
    const wrapper = mountModal(withNote)

    expect(entryIds(wrapper).slice(0, 2)).toEqual(['hosting-history-8', 'hosting-notes-8'])
    await wrapper.get('[data-testid="hosting-notes-8"]').trigger('click')

    expect(wrapper.emitted('notes')[0]).toEqual([withNote])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('explains why billing is unavailable when the hosting has no email', () => {
    const wrapper = mountModal({ ...RECORD, billing_email: '' })
    const action = wrapper.get('[data-testid="hosting-send-billing-8"]')

    expect(action.attributes('disabled')).toBe('')
    expect(action.text()).toContain('Vincula un cliente con correo')
  })

  it('locks billing while the request is in flight', () => {
    const wrapper = mountModal(RECORD, { billingBusy: true })

    expect(wrapper.get('[data-testid="hosting-send-billing-8"]')
      .attributes('disabled')).toBe('')
  })

  it('emits the selected action with the hosting and closes the menu', async () => {
    const wrapper = mountModal()

    await wrapper.get('[data-testid="hosting-cycles-8"]').trigger('click')

    expect(wrapper.emitted('cycles')[0]).toEqual([RECORD])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
