import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import NotificationRecipients from '../../../components/accounting/NotificationRecipients.vue'
import BaseAlert from '../../../components/base/BaseAlert.vue'
import BaseButton from '../../../components/base/BaseButton.vue'
import BaseFormField from '../../../components/base/BaseFormField.vue'
import BaseInput from '../../../components/base/BaseInput.vue'
import BaseToggle from '../../../components/base/BaseToggle.vue'
import { useAccountingStore } from '../../../stores/accounting'
import { usePanelNotify } from '../../../composables/usePanelNotify'

jest.mock('../../../composables/usePanelNotify', () => {
  const notify = { success: jest.fn(), error: jest.fn() }
  return { usePanelNotify: jest.fn(() => notify) }
})

// The real modal traps focus and teleports; the stub keeps the confirm
// callback reachable so the delete path stays testable.
const ConfirmModalStub = {
  props: ['modelValue', 'message'],
  emits: ['confirm', 'cancel'],
  template: '<div v-if="modelValue" data-testid="confirm-stub" @click="$emit(\'confirm\')">{{ message }}</div>',
}

const recipient = (overrides = {}) => ({
  id: 1,
  email: 'team@projectapp.co',
  is_active: true,
  notes: '',
  created_at: '2026-08-13T10:00:00Z',
  ...overrides,
})

function mountRecipients({
  rows = [recipient()],
  results = {},
  notificationsEnabled = true,
} = {}) {
  const store = useAccountingStore()
  store.notificationRecipients = rows
  store.fetchRecords = jest.fn().mockResolvedValue({ success: true })
  store.createRecord = jest.fn().mockResolvedValue(results.create ?? { success: true })
  store.updateRecord = jest.fn().mockResolvedValue(
    results.update ?? { success: true, data: { is_active: false } },
  )
  store.deleteRecord = jest.fn().mockResolvedValue(results.delete ?? { success: true })
  const wrapper = mount(NotificationRecipients, {
    props: { notificationsEnabled },
    global: {
      components: { BaseAlert, BaseButton, BaseFormField, BaseInput, BaseToggle },
      stubs: {
        ConfirmModal: ConfirmModalStub,
        NuxtLink: { template: '<a><slot /></a>' },
        // The row menu is a BaseModal; inline so its entries can be clicked.
        BaseModal: {
          props: ['modelValue'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /></div>',
        },
      },
    },
  })
  return { wrapper, store, notify: usePanelNotify() }
}

async function chooseRemove(wrapper, id = 1) {
  await wrapper.get(`[data-testid="recipients-actions-${id}"]`).trigger('click')
  await wrapper.get(`[data-testid="recipients-action-remove-${id}"]`).trigger('click')
  await flushPromises()
}

describe('NotificationRecipients', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    jest.clearAllMocks()
  })

  it('loads the list on mount and shows each address with its state and signup date', async () => {
    const { wrapper, store } = mountRecipients({
      rows: [recipient(), recipient({ id: 2, email: 'ana@test.com', is_active: false })],
    })
    await flushPromises()

    expect(store.fetchRecords).toHaveBeenCalledWith('notificationRecipients')
    expect(wrapper.get('[data-testid="recipients-email-1"]').text()).toBe('team@projectapp.co')
    expect(wrapper.get('[data-testid="recipients-state-1"]').text()).toBe('Activo')
    expect(wrapper.get('[data-testid="recipients-state-2"]').text()).toBe('Pausado')
    expect(wrapper.text()).toContain('Alta')
  })

  describe('adding', () => {
    it('creates the recipient and clears the field', async () => {
      const { wrapper, store, notify } = mountRecipients()
      await flushPromises()

      await wrapper.get('[data-testid="recipients-new-email"]').setValue('ana@test.com')
      await wrapper.get('[data-testid="recipients-add"]').trigger('click')
      await flushPromises()

      expect(store.createRecord).toHaveBeenCalledWith(
        'notificationRecipients', { email: 'ana@test.com' },
      )
      expect(notify.success).toHaveBeenCalledWith('Destinatario agregado.')
      expect(wrapper.get('[data-testid="recipients-new-email"]').element.value).toBe('')
    })

    it('shows a duplicate rejection inline instead of as a toast', async () => {
      const { wrapper, notify } = mountRecipients({
        results: {
          create: {
            success: false,
            message: 'Ese correo ya está en la lista.',
            fieldErrors: { email: 'Ese correo ya está en la lista.' },
          },
        },
      })
      await flushPromises()

      await wrapper.get('[data-testid="recipients-new-email"]').setValue('TEAM@projectapp.co')
      await wrapper.get('[data-testid="recipients-add"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Ese correo ya está en la lista.')
      expect(notify.error).not.toHaveBeenCalled()
      // The typed value stays so the user can correct it.
      expect(wrapper.get('[data-testid="recipients-new-email"]').element.value)
        .toBe('TEAM@projectapp.co')
    })

    it('does not call the API on an empty field', async () => {
      const { wrapper, store } = mountRecipients()
      await flushPromises()

      await wrapper.get('[data-testid="recipients-add"]').trigger('click')
      await flushPromises()

      expect(store.createRecord).not.toHaveBeenCalled()
      expect(wrapper.text()).toContain('Escribe un correo.')
    })
  })

  describe('pausing', () => {
    it('persists the new state through the API', async () => {
      const { wrapper, store, notify } = mountRecipients()
      await flushPromises()

      await wrapper.get('[data-testid="recipients-toggle-1"]').trigger('click')
      await flushPromises()

      expect(store.updateRecord).toHaveBeenCalledWith(
        'notificationRecipients', 1, { is_active: false },
      )
      expect(notify.success).toHaveBeenCalledWith(
        'team@projectapp.co queda pausado: no recibirá avisos.',
      )
    })

    it('reports a failure without claiming the state changed', async () => {
      const { wrapper, store, notify } = mountRecipients({
        results: { update: { success: false, message: 'timeout' } },
      })
      await flushPromises()

      await wrapper.get('[data-testid="recipients-toggle-1"]').trigger('click')
      await flushPromises()

      expect(store.updateRecord).toHaveBeenCalled()
      expect(notify.error).toHaveBeenCalledWith({
        title: 'No se pudo cambiar el estado',
        detail: 'timeout',
      })
      expect(notify.success).not.toHaveBeenCalled()
    })
  })

  describe('removing', () => {
    it('asks for confirmation before deleting and names what stops arriving', async () => {
      const { wrapper, store } = mountRecipients()
      await flushPromises()

      await chooseRemove(wrapper)

      // Nothing is deleted until the modal is confirmed.
      expect(store.deleteRecord).not.toHaveBeenCalled()
      const modal = wrapper.get('[data-testid="confirm-stub"]')
      expect(modal.text()).toContain('team@projectapp.co')
      expect(modal.text()).toContain(
        'cambios contables, la deuda de tarjetas, los extractos, el calendario ' +
        'de cobros y pagos y los pagos de hosting',
      )

      await modal.trigger('click')
      await flushPromises()

      expect(store.deleteRecord).toHaveBeenCalledWith('notificationRecipients', 1)
    })

    it('does not promise the cuentas de cobro, which go to the client', async () => {
      // send_collection_account_email addresses extension.customer_email, not
      // active_recipient_emails(), so removing a recipient changes nothing
      // there. Listing it would send the operator hunting in the wrong place.
      const { wrapper } = mountRecipients()
      await flushPromises()

      await chooseRemove(wrapper)

      // The neighbouring item proves the enumeration rendered, so the absence
      // below is a surgical removal and not an empty modal.
      const message = wrapper.get('[data-testid="confirm-stub"]').text()
      expect(message).toContain('los pagos de hosting')
      expect(message).not.toContain('cuentas de cobro')
    })
  })

  describe('the automation reaching nobody', () => {
    it('warns when every recipient is paused', async () => {
      const { wrapper } = mountRecipients({
        rows: [recipient({ is_active: false })],
      })
      await flushPromises()

      const warning = wrapper.get('[data-testid="recipients-none-active-warning"]')
      expect(warning.text()).toContain('Ningún destinatario activo')
    })

    it('warns about the master switch instead when it is off', async () => {
      const { wrapper } = mountRecipients({
        rows: [recipient({ is_active: false })],
        notificationsEnabled: false,
      })
      await flushPromises()

      expect(wrapper.find('[data-testid="recipients-none-active-warning"]').exists()).toBe(false)
      expect(wrapper.get('[data-testid="recipients-master-off-warning"]').text())
        .toContain('no sale ningún correo del módulo')
    })

    it('stays quiet while at least one recipient is active', async () => {
      const { wrapper } = mountRecipients()
      await flushPromises()

      expect(wrapper.find('[data-testid="recipients-none-active-warning"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="recipients-master-off-warning"]').exists()).toBe(false)
    })

    it('shows the empty state when the list has no rows at all', async () => {
      const { wrapper } = mountRecipients({ rows: [] })
      await flushPromises()

      expect(wrapper.get('[data-testid="recipients-empty"]').text())
        .toBe('Sin destinatarios registrados.')
    })
  })

  describe('row menu', () => {
    // Bug caught: the history was a loose text button squeezed between the
    // switch and the remove icon.
    it('leads each recipient with a kebab whose menu opens with its history', async () => {
      const { wrapper } = mountRecipients()
      await flushPromises()

      await wrapper.get('[data-testid="recipients-actions-1"]').trigger('click')

      expect(wrapper.findAll('[data-testid="recipients-actions-modal"] li button')
        .map((button) => button.attributes('data-testid')))
        .toEqual(['recipients-action-history-1', 'recipients-action-remove-1'])
      // The switch is the recipient's state, so it stays in the row.
      expect(wrapper.get('[data-testid="recipients-row-1"]')
        .find('[data-testid="recipients-toggle-1"]').exists()).toBe(true)
    })
  })
})
