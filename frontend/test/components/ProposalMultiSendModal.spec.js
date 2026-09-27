import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ProposalMultiSendModal from '../../components/BusinessProposal/admin/ProposalMultiSendModal.vue'
import BaseButton from '../../components/base/BaseButton.vue'
import { useProposalStore } from '../../stores/proposals'

const BaseModalStub = {
  props: ['modelValue'],
  template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
}

const currentProposal = {
  id: 1,
  client: { id: 55 },
  client_name: 'ACME Corp',
  client_email: 'acme@test.com',
  email_intro: 'La primera fase resuelve el registro manual de ACME.',
}

const proposal = (overrides = {}) => ({
  id: 2,
  title: 'Fase 2',
  status: 'draft',
  total_investment: '5000000',
  currency: 'COP',
  expires_at: null,
  is_expired: false,
  days_remaining: null,
  email_intro: 'Esta fase resuelve el siguiente cuello de botella de ACME.',
  ...overrides,
})

const CANDIDATES = [
  proposal({ id: 1, title: 'Fase 1', status: 'sent' }),
  proposal({ id: 2, title: 'Fase 2', status: 'draft' }),
  proposal({ id: 3, title: 'Fase 3', status: 'expired', is_expired: true }),
]

function mountModal({ candidates = CANDIDATES, sendResult = { success: true } } = {}) {
  const store = useProposalStore()
  store.fetchProposalsByClient = jest.fn().mockResolvedValue({ success: true, data: candidates })
  store.sendMultiProposal = jest.fn().mockResolvedValue(sendResult)
  const wrapper = mount(ProposalMultiSendModal, {
    props: { visible: false, currentProposal },
    global: {
      components: { BaseButton },
      stubs: { BaseModal: BaseModalStub },
    },
  })
  return { wrapper, store }
}

async function open(wrapper) {
  await wrapper.setProps({ visible: true })
  await flushPromises()
}

describe('ProposalMultiSendModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads the client candidates when it opens', async () => {
    const { wrapper, store } = mountModal()
    await open(wrapper)
    expect(store.fetchProposalsByClient).toHaveBeenCalledWith(55)
    expect(wrapper.text()).toContain('Fase 1')
    expect(wrapper.text()).toContain('Fase 3')
  })

  it('groups the candidates by status bucket', async () => {
    const { wrapper } = mountModal()
    await open(wrapper)
    const text = wrapper.text()
    expect(text).toContain('Borradores')
    expect(text).toContain('Enviadas / Vistas / Negociación')
    expect(text).toContain('Expiradas')
  })

  it('preselects the current proposal and keeps its checkbox disabled', async () => {
    const { wrapper } = mountModal()
    await open(wrapper)
    const current = wrapper.get('[data-testid="proposal-multi-send-option-1"]')
    expect(current.element.checked).toBe(true)
    expect(current.attributes('disabled')).toBeDefined()
  })

  it('keeps send disabled until a second proposal is selected', async () => {
    const { wrapper } = mountModal()
    await open(wrapper)
    const confirm = wrapper.get('[data-testid="proposal-multi-send-confirm"]')
    expect(confirm.attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="proposal-multi-send-option-2"]').setValue(true)

    expect(wrapper.get('[data-testid="proposal-multi-send-confirm"]').attributes('disabled')).toBeUndefined()
  })

  it('blocks the selected set when one proposal has no personalized message', async () => {
    const { wrapper, store } = mountModal({
      candidates: [
        ...CANDIDATES.filter((item) => item.id !== 2),
        proposal({ id: 2, title: 'Fase sin mensaje', email_intro: '   ' }),
      ],
    })
    await open(wrapper)

    await wrapper.get('[data-testid="proposal-multi-send-option-2"]').setValue(true)

    expect(wrapper.get('[data-testid="proposal-multi-send-missing-message"]').text()).toContain('1 propuesta seleccionada')
    expect(wrapper.get('[data-testid="proposal-multi-send-confirm"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Completar en Correos')
    expect(store.sendMultiProposal).not.toHaveBeenCalled()
  })

  it('filters out terminal statuses from the candidate list', async () => {
    const { wrapper } = mountModal({
      candidates: [
        ...CANDIDATES,
        proposal({ id: 9, title: 'Ya aceptada', status: 'accepted' }),
      ],
    })
    await open(wrapper)
    expect(wrapper.text()).not.toContain('Ya aceptada')
  })

  it('caps the selection at ten proposals', async () => {
    const many = Array.from({ length: 12 }, (_, i) =>
      proposal({ id: i + 1, title: `Fase ${i + 1}`, status: 'draft' }))
    const { wrapper } = mountModal({ candidates: many })
    await open(wrapper)

    for (let id = 2; id <= 12; id += 1) {
      await wrapper.get(`[data-testid="proposal-multi-send-option-${id}"]`).setValue(true)
    }

    // 1 (current, locked) + 9 more = 10; the 11th toggle is ignored.
    expect(wrapper.text()).toContain('10 propuestas seleccionadas')
  })

  it('sends the selected ids and emits sent with the count', async () => {
    const { wrapper, store } = mountModal()
    await open(wrapper)
    await wrapper.get('[data-testid="proposal-multi-send-option-2"]').setValue(true)

    await wrapper.get('[data-testid="proposal-multi-send-confirm"]').trigger('click')
    await flushPromises()

    expect(store.sendMultiProposal).toHaveBeenCalledWith(1, [1, 2])
    expect(wrapper.emitted('sent')[0][0].count).toBe(2)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits the error payload when the send fails', async () => {
    const { wrapper } = mountModal({ sendResult: { success: false, errors: { detail: 'boom' } } })
    await open(wrapper)
    await wrapper.get('[data-testid="proposal-multi-send-option-2"]').setValue(true)

    await wrapper.get('[data-testid="proposal-multi-send-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('sent')[0][0].error).toEqual({ detail: 'boom' })
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('surfaces a retry hint when the candidates fail to load', async () => {
    const store = useProposalStore()
    store.fetchProposalsByClient = jest.fn().mockResolvedValue({ success: false })
    store.sendMultiProposal = jest.fn()
    const wrapper = mount(ProposalMultiSendModal, {
      props: { visible: false, currentProposal },
      global: { components: { BaseButton }, stubs: { BaseModal: BaseModalStub } },
    })
    await open(wrapper)

    expect(wrapper.text()).toContain('Reintenta en unos segundos.')
  })

  it('emits close from the cancel button', async () => {
    const { wrapper } = mountModal()
    await open(wrapper)
    await wrapper.get('[data-testid="proposal-multi-send-cancel"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
