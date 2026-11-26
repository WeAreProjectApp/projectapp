import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import HostingCycleReceiptForm from '~/components/accounting/billing/HostingCycleReceiptForm.vue'
import hostingBilling from '~/locales/hostingBilling/es'
import { create_request, get_request } from '~/stores/services/request_http'

jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn(), create_request: jest.fn() }))
jest.mock('~/utils/hostingReceipt', () => {
  const actual = jest.requireActual('~/utils/hostingReceipt')
  return { ...actual, requestUuid: () => 'b77af3c4-4bbb-4bbb-8bbb-123456789012' }
})

const record = { id: 12, billing_email: 'billing@example.test', payment_modality: 'quarterly', valid_to: '2026-10-31' }
const period = {
  income_id: 41, hosting_record_id: 12, concept: 'Hosting Aurora', period_start: '2026-08-01', period_end: '2026-10-31',
  balance: '0.00', state: 'paid', amount: '233280.00', received: '233280.00', documents: [],
  liquids: [{ id: 77, amount: '233280.00', date: '2026-11-10', destination: 'pocket' }], cycles: [],
}

function mountForm() {
  return mount(HostingCycleReceiptForm, {
    props: { record },
    global: {
      plugins: [createI18n({ legacy: false, locale: 'es', messages: { es: { hostingBilling } } })],
      stubs: {
        BaseFormField: { template: '<div><slot /></div>' },
        BaseFormRow: { template: '<div><slot /></div>' },
        BaseSelect: { props: ['modelValue', 'options'], emits: ['update:modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
        BaseCurrencyInput: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
        BaseInput: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
        BaseToggle: { props: ['modelValue'], emits: ['update:modelValue'], template: '<button type="button" @click="$emit(\'update:modelValue\', !modelValue)"><slot /></button>' },
        BaseButton: { props: ['type', 'disabled', 'loading'], emits: ['click'], template: '<button v-bind="$attrs" :type="type || \'button\'" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>' },
        HostingPeriodSummary: { template: '<div />' },
        HostingReceiptFields: {
          emits: ['update:modelValue'],
          template: '<button type="button" data-testid="existing-liquid" @click="$emit(\'update:modelValue\', { issuer: \'\', reference: \'\', entries: [{ income_id: 41, liquid_id: 77 }] })">Vincular</button>',
        },
      },
    },
  })
}

describe('HostingCycleReceiptForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    jest.clearAllMocks()
    get_request.mockResolvedValue({ data: { incomes: [period] } })
  })

  // Falla si un pago ya acreditado con saldo cero vuelve a bloquear el enlace
  // y obliga a registrar un segundo abono desde la pantalla de Hostings.
  it('reviews and confirms an existing liquid despite a zero displayed balance', async () => {
    const request = {
      income_id: 41, amount: '233280', paid_at: '2026-11-10', destination: 'pocket', notes: '',
      hosting_receipt: { entries: [{ income_id: 41, hosting_record_id: 12, liquid_id: 77 }] },
      advance_validity: true, request_id: 'b77af3c4-4bbb-4bbb-8bbb-123456789012', modality: 'quarterly',
    }
    create_request
      .mockResolvedValueOnce({ data: { preview_hash: 'review-v4', already_registered: true, rows: [{ validity_target: '2027-01-31' }] } })
      .mockResolvedValueOnce({ data: { allocation_id: 501, already_registered: true, period: { ...period, version: 'period-v4', hosting_payment_id: null } } })
    const wrapper = mountForm()
    await flushPromises()

    await wrapper.get('[data-testid="existing-liquid"]').trigger('click')
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(create_request).toHaveBeenCalledWith('accounting/hostings/12/cycle-receipt/?preview=1', request)
    expect(wrapper.get('[data-testid="cycle-receipt-review"]').text()).toContain('Vincular pago registrado')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(create_request).toHaveBeenLastCalledWith('accounting/hostings/12/cycle-receipt/', { ...request, preview_hash: 'review-v4' })
    expect(wrapper.get('[data-testid="cycle-payment-recorded"]').text()).toContain('Pago registrado anteriormente.')
    expect(wrapper.get('[data-testid="cycle-next-income"]').text()).toBe('Crear ingreso esperado del siguiente período')
  })
})
