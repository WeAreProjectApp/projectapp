import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import HostingAccountEmissionModal from '../../../../components/accounting/billing/HostingAccountEmissionModal.vue'
import hostingBilling from '../../../../locales/hostingBilling/es'
import { get_request } from '../../../../stores/services/request_http'

jest.mock('../../../../stores/services/request_http', () => ({ get_request: jest.fn() }))

const record = { id: 44, project: 7, domain_url: 'aurora.co' }

function contextData(overrides = {}) {
  return {
    overview: {
      hosting_id: 91,
      reconciliation_required: false,
      subscription: null,
      accounting_sources: [{ id: 44, operational: true }],
      ...overrides.overview,
    },
    selection: { requires_reconciliation: false, ...overrides.selection },
  }
}

function button(wrapper, label) {
  const control = wrapper.findAll('[role="button"]').find(item => item.text() === label)
  expect(control.text()).toBe(label)
  return control
}

async function mountOpen(props = {}) {
  const wrapper = mount(HostingAccountEmissionModal, {
    props: { modelValue: false, record, message: 'Confirma el cobro.', ...props },
    global: {
      plugins: [createI18n({
        legacy: false,
        locale: 'es',
        messages: { es: { hostingBilling } },
      })],
      stubs: {
        BaseModal: {
          props: ['modelValue'],
          template: '<section v-if="modelValue" role="dialog"><slot /></section>',
        },
        BaseButton: {
          props: ['disabled', 'loading'],
          emits: ['click'],
          template: '<button role="button" type="button" :disabled="disabled || loading" @click="!disabled && !loading && $emit(\'click\')"><slot /></button>',
        },
        HostingBillingPicker: {
          props: ['modelValue'],
          emits: ['update:modelValue', 'reconcile'],
          template: `<section role="group">
            <button data-testid="emission-picker-payment" @click="$emit('update:modelValue', { ...modelValue, hosting_payment_id: 8 })">Seleccionar período 8</button>
            <button data-testid="emission-picker-reconcile" @click="$emit('reconcile')">Conciliar</button>
          </section>`,
        },
      },
    },
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

describe('HostingAccountEmissionModal', () => {
  beforeEach(() => jest.clearAllMocks())

  // Falla si un origen pendiente o una selección en conciliación todavía permite enviar al cliente.
  it('blocks sending while the hosting source still needs reconciliation', async () => {
    get_request.mockResolvedValue({ data: contextData({
      overview: { accounting_sources: [{ id: 44, operational: false }] },
      selection: { requires_reconciliation: true },
    }) })
    const wrapper = await mountOpen()
    const confirm = button(wrapper, 'Enviar al cliente')

    expect(confirm.element.disabled).toBe(true)
    await confirm.trigger('click')

    expect(wrapper.emitted('confirm')).toBeUndefined()
    expect(get_request).toHaveBeenCalledWith('admin/billing-context/projects/7/hosting/')
    wrapper.unmount()
  })

  // Falla si un origen operativo sin suscripción exige un período inexistente o emite uno inventado.
  it('confirms an operational source without a subscription using a null payment', async () => {
    get_request.mockResolvedValue({ data: contextData() })
    const wrapper = await mountOpen()
    const confirm = button(wrapper, 'Enviar al cliente')

    expect(confirm.element.disabled).toBe(false)
    await confirm.trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([[{ hosting_payment_id: null }]])
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    wrapper.unmount()
  })

  // Falla si el modal acepta un período ajeno a la suscripción o rechaza uno recuperado del borrador.
  it.each([
    ['a saved subscription payment', 8, false, [[{ hosting_payment_id: 8 }]]],
    ['a foreign subscription payment', 99, true, undefined],
  ])('handles %s by its current payment list', async (_case, paymentId, disabled, expectedConfirm) => {
    get_request.mockResolvedValue({ data: contextData({
      overview: {
        subscription: { associated: true, payments: [{ id: 8, status: 'pending' }] },
      },
    }) })
    const wrapper = await mountOpen({ resumeDraft: { hosting_payment_id: paymentId } })
    const confirm = button(wrapper, 'Enviar al cliente')

    expect(confirm.element.disabled).toBe(disabled)
    await confirm.trigger('click')

    expect(wrapper.emitted('confirm')).toEqual(expectedConfirm)
    wrapper.unmount()
  })

  // Falla si la conciliación pierde el hosting elegido antes de retornar a la emisión.
  it('sends the hosting record with the selected payment to reconciliation', async () => {
    get_request.mockResolvedValue({ data: contextData({
      overview: {
        subscription: { associated: true, payments: [{ id: 8, status: 'pending' }] },
      },
    }) })
    const wrapper = await mountOpen()

    await wrapper.get('[data-testid="emission-picker-payment"]').trigger('click')
    await wrapper.get('[data-testid="emission-picker-reconcile"]').trigger('click')

    expect(wrapper.emitted('reconcile')).toEqual([[
      { record, hosting_payment_id: 8 },
    ]])
    wrapper.unmount()
  })
})
