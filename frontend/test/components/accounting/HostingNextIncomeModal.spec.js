import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import HostingNextIncomeModal from '~/components/accounting/HostingNextIncomeModal.vue'
import { create_request, get_request } from '~/stores/services/request_http'
import hostingBilling from '~/locales/hostingBilling/es'

jest.mock('~/stores/services/request_http', () => ({
  get_request: jest.fn(), create_request: jest.fn(),
}))

const record = { id: 12 }
const plan = (overrides = {}) => ({
  version: 'period-v4', client_name: 'Aurora', project_name: 'Portal', service: 'aurora.co',
  fields: { concept: 'Hosting Aurora', period_start: '2026-11-01', period_end: '2027-01-31', total_amount: '233280.00' },
  ...overrides,
})

function mountModal(props = {}) {
  return mount(HostingNextIncomeModal, {
    props: { record, ...props },
    global: { plugins: [createI18n({ legacy: false, locale: 'es', messages: { es: { hostingBilling } } })], stubs: {
      BaseModal: { props: ['modelValue'], template: '<section v-if="modelValue"><slot /><slot name="footer" /></section>' },
      BaseModalActions: { template: '<div><slot /></div>' },
      BaseButton: { props: ['disabled', 'loading'], emits: ['click'], template: '<button v-bind="$attrs" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>' },
    } },
  })
}

describe('HostingNextIncomeModal', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    get_request.mockResolvedValue({ data: plan() })
  })

  // Falla si la confirmación crea el esperado con una versión distinta de la
  // que el operador revisó para el siguiente período contractual.
  it('creates the reviewed next period with its version and returns its income id', async () => {
    create_request.mockResolvedValue({ data: plan({ existing_income_id: 94 }) })
    const wrapper = mountModal({ referenceIncomeId: 41 })
    await flushPromises()

    expect(wrapper.text()).toContain('2026-11-01 — 2027-01-31')
    await wrapper.get('[data-testid="hosting-next-confirm"]').trigger('click')
    await flushPromises()

    expect(create_request).toHaveBeenCalledWith('accounting/hostings/12/next-income/', {
      version: 'period-v4', reference_income_id: 41,
    })
    expect(wrapper.emitted('created')).toEqual([[94]])
  })

  // Falla si el reingreso muestra una segunda confirmación pese a que el
  // servidor ya encontró el único esperado del período siguiente.
  it('shows an existing next income without offering another creation', async () => {
    get_request.mockResolvedValue({ data: plan({ existing_income_id: 94 }) })
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Ingreso esperado registrado #94.')
    expect(wrapper.find('[data-testid="hosting-next-confirm"]').exists()).toBe(false)
    expect(create_request).not.toHaveBeenCalled()
  })
})
