import { flushPromises, mount } from '@vue/test-utils'
import EmailRetryAction from '../../../components/emails/EmailRetryAction.vue'

const mockStore = { retryEmail: jest.fn() }

jest.mock('../../../stores/emails', () => ({
  useEmailStore: () => mockStore,
}))

const BaseButtonStub = {
  props: ['loading'],
  emits: ['click'],
  template: '<button v-bind="$attrs" type="button" :disabled="loading" @click="$emit(\'click\')"><slot /></button>',
}

const ConfirmModalStub = {
  props: ['modelValue', 'message'],
  emits: ['confirm', 'cancel'],
  template: `
    <section v-if="modelValue" role="dialog">
      <p data-testid="retry-confirm-message">{{ message }}</p>
      <button data-testid="retry-confirm" type="button" @click="$emit('confirm')">Confirmar</button>
      <button data-testid="retry-cancel" type="button" @click="$emit('cancel')">Cancelar</button>
    </section>
  `,
}

function mountAction(entry, subject = 'Confirmación de pago') {
  global.useI18n = () => ({
    t: (key, values = {}) => ({
      'panelUsability.retry': 'Reintentar envío',
      'panelUsability.retryUnavailable': 'No se puede reintentar este correo.',
      'panelUsability.cancel': 'Cancelar',
      'panelUsability.retryQuestion': `Reintentar ${values.subject} para ${values.recipient}`,
    }[key] || key),
  })
  return mount(EmailRetryAction, {
    props: { entry, subject },
    global: {
      stubs: { BaseButton: BaseButtonStub, ConfirmModal: ConfirmModalStub },
    },
  })
}

describe('EmailRetryAction', () => {
  beforeEach(() => {
    mockStore.retryEmail.mockReset()
  })

  afterEach(() => {
    delete global.useI18n
  })

  it.each([
    [{ success: true, data: { id: 19, status: 'sent' } }],
    [{ success: false, message: 'SMTP no disponible.' }],
  ])('emits the retry result after confirming the original failed email', async (result) => {
    // Fails if confirmation retries a replacement record or hides either outcome from Historial.
    mockStore.retryEmail.mockResolvedValue(result)
    const wrapper = mountAction({ id: 12, status: 'failed', is_retryable: true, recipient: 'cliente@example.com' })

    await wrapper.get('[data-testid="email-history-retry-12"]').trigger('click')
    await wrapper.get('[data-testid="retry-confirm"]').trigger('click')
    await flushPromises()

    expect(mockStore.retryEmail).toHaveBeenCalledTimes(1)
    expect(mockStore.retryEmail).toHaveBeenCalledWith(12)
    expect(wrapper.emitted('attempted')).toEqual([[result]])
  })

  it('does not send a retry after the confirmation is cancelled', async () => {
    // Fails if closing the confirmation still retries the failed email.
    const wrapper = mountAction({ id: 12, status: 'failed', is_retryable: true, recipient: 'cliente@example.com' })

    await wrapper.get('[data-testid="email-history-retry-12"]').trigger('click')
    await wrapper.get('[data-testid="retry-cancel"]').trigger('click')
    await flushPromises()

    expect(mockStore.retryEmail).toHaveBeenCalledTimes(0)
    expect(wrapper.emitted('attempted')).toBeUndefined()
  })

  it('shows the recorded reason when the failed email cannot be retried', () => {
    // Fails if a blocked historical confirmation offers a retry without explaining the missing source data.
    const wrapper = mountAction({
      id: 12,
      status: 'failed',
      is_retryable: false,
      retry_blocked_reason: 'El pago original ya no está disponible.',
    })

    expect(wrapper.get('[data-testid="email-history-retry-blocked-12"]').text()).toBe(
      'El pago original ya no está disponible.',
    )
  })
})
