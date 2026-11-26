import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import HostingAccountEmissionModal from '../../../../components/accounting/billing/HostingAccountEmissionModal.vue'
import hostingBilling from '../../../../locales/hostingBilling/es'
import { get_request } from '../../../../stores/services/request_http'

jest.mock('../../../../stores/services/request_http', () => ({ get_request: jest.fn() }))

const alfa = {
  id: 44, client: 17, client_display_name: 'Cliente Alfa', project: 7, project_name: 'Proyecto Alfa',
  domain_url: 'alfa.example.invalid', billing_email: 'alfa@example.invalid', payment_per_cycle: '999999',
}
const beta = {
  id: 45, client: 18, client_display_name: 'Cliente Beta', project: 8, project_name: 'Proyecto Beta',
  domain_url: 'beta.example.invalid', billing_email: 'beta@example.invalid',
}

function decision(record = alfa, period = {}) {
  return {
    overview: {
      project_id: record.project, hosting_id: 91, reconciliation_required: false,
      accounting_sources: [{ id: record.id, associated: true, operational: true }],
    },
    selection: { requires_reconciliation: false, blockers: [] },
    billing_period: {
      project_id: record.project, project_hosting_id: 91, hosting_record_id: record.id, client_id: record.client,
      source: 'subscription', hosting_payment_id: 8, income_id: null, documents: [],
      period_start: '2026-04-01', period_end: '2026-06-30', currency: 'COP',
      amount: '240000', received: '60000', balance: '180000', state: 'partial', version: 'review-alfa', ...period,
    },
  }
}

function open(record = alfa) {
  return mount(HostingAccountEmissionModal, {
    props: { modelValue: true, record },
    global: {
      plugins: [createI18n({ legacy: false, locale: 'es', messages: { es: { hostingBilling } } })],
      stubs: {
        BaseModal: { props: ['modelValue'], template: '<section role="dialog" v-if="modelValue"><slot /></section>' },
        BaseButton: {
          props: ['disabled', 'loading'], emits: ['click'],
          template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

function button(wrapper, label) {
  return wrapper.findAll('button').find(item => item.text() === label)
}
const send = wrapper => button(wrapper, 'Enviar al cliente')

describe('HostingAccountEmissionModal', () => {
  beforeEach(() => get_request.mockReset())

  it('shows the row identity alongside the shared summary of the outstanding balance', async () => {
    const context = decision()
    get_request.mockResolvedValue({ data: context })
    const wrapper = open()
    await flushPromises()

    expect(get_request).toHaveBeenCalledWith('admin/billing-context/projects/7/hosting/')
    expect(wrapper.get('dl').text()).toContain('Proyecto Alfa')
    expect(wrapper.get('dl').text()).toContain('Cliente Alfa')
    expect(wrapper.get('dl').text()).toContain(alfa.domain_url)
    expect(wrapper.get('dl').text()).toContain(alfa.billing_email)
    expect(wrapper.getComponent({ name: 'HostingPeriodSummary' }).props('period')).toEqual(context.billing_period)
    expect(wrapper.text()).toContain('PDF adjunto')
    expect(wrapper.text()).toContain('próxima renovación')
    expect(wrapper.text()).toContain('$180.000 COP')
    expect(wrapper.text()).not.toContain('999.999')
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'HostingBillingPicker' }).exists()).toBe(false)
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it.each([
    ['subscription', { hosting_payment_id: 8 }],
    ['expected_income', { hosting_payment_id: null, income_id: 31 }],
  ])('submits the reviewed %s once on explicit confirmation', async (source, identity) => {
    get_request.mockResolvedValue({ data: decision(alfa, { source, ...identity }) })
    const wrapper = open()
    await flushPromises()
    send(wrapper).element.click()
    send(wrapper).element.click()

    expect(wrapper.emitted('confirm')).toEqual([[{
      hosting_payment_id: identity.hosting_payment_id, period_version: 'review-alfa',
    }]])
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('ignores a late read after canceling and opening a different hosting', async () => {
    let finishAlfa
    get_request.mockImplementationOnce(() => new Promise(resolve => { finishAlfa = resolve }))
    get_request.mockResolvedValueOnce({ data: decision(beta, {
      period_start: '2026-07-01', period_end: '2026-09-30', balance: '45000', version: 'review-beta', hosting_payment_id: 12,
    }) })
    const wrapper = open()
    expect(send(wrapper).element.disabled).toBe(true)
    await button(wrapper, 'Cancelar').trigger('click')
    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true, record: beta })
    await flushPromises()
    finishAlfa({ data: decision() })
    await flushPromises()

    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toBeUndefined()
    expect(wrapper.text()).toContain(beta.billing_email)
    expect(wrapper.text()).toContain('2026-07-01')
    expect(wrapper.text()).not.toContain(alfa.billing_email)
    expect(wrapper.text()).not.toContain('2026-04-01')
    await send(wrapper).trigger('click')
    expect(wrapper.emitted('confirm')).toEqual([[{ hosting_payment_id: 12, period_version: 'review-beta' }]])
  })

  it.each([
    ['project', { project: null }, 'proyecto'],
    ['client', { client: null }, 'cliente'],
    ['recipient', { billing_email: '' }, 'correo'],
  ])('gives the correction for a missing %s before reading the period', async (_field, missing, correction) => {
    const wrapper = open({ ...alfa, ...missing })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text().toLowerCase()).toContain(correction)
    expect(send(wrapper).element.disabled).toBe(true)
    expect(get_request).not.toHaveBeenCalled()
  })

  it.each([
    ['client', { client_id: beta.client }], ['project', { project_id: beta.project }],
    ['service', { project_hosting_id: 32 }], ['row', { hosting_record_id: beta.id }],
  ])('withholds another %s’s decision from the dialog', async (_field, changed) => {
    get_request.mockResolvedValue({ data: decision(alfa, changed) })
    const wrapper = open()
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/coincid/i)
    expect(wrapper.find('[data-testid="hosting-period-summary"]').exists()).toBe(false)
    expect(send(wrapper).element.disabled).toBe(true)
  })

  it('opens reconciliation for a historical row without selecting any other service', async () => {
    const data = decision()
    data.overview.accounting_sources[0].operational = false
    get_request.mockResolvedValue({ data })
    const wrapper = open()
    await flushPromises()

    expect(send(wrapper).element.disabled).toBe(true)
    await button(wrapper, 'Revisar conciliación del hosting').trigger('click')
    expect(wrapper.emitted('reconcile')).toEqual([[{ record: alfa, hosting_payment_id: null }]])
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it.each([
    'No hay un período pendiente. Revisa las obligaciones del hosting.',
    'El pago y el ciclo tienen fechas distintas. Revisa los límites en conciliación.',
    'El período ya tiene cuenta. Consulta su referencia antes de enviar otra.',
  ])('displays the resolver’s correction: %s', async blocker => {
    const data = decision()
    data.billing_period = { state: 'blocked', blocker }
    get_request.mockResolvedValue({ data })
    const wrapper = open()
    await flushPromises()

    expect(wrapper.get('[data-testid="hosting-period-summary"] [role="alert"]').text()).toBe(blocker)
    expect(send(wrapper).element.disabled).toBe(true)
  })

  it('explains ambiguous service ownership before sending', async () => {
    const data = decision()
    const message = 'Hay varios registros pendientes. Revisa cuál se usará para cobrar.'
    data.selection = { requires_reconciliation: true, blockers: [{ message }] }
    get_request.mockResolvedValue({ data })
    const wrapper = open()
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe(message)
    expect(send(wrapper).element.disabled).toBe(true)
  })

  it('shows how to retry a failed read without enabling emission', async () => {
    get_request.mockRejectedValue(new Error('offline'))
    const wrapper = open()
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/vuelve a abrir/i)
    expect(send(wrapper).element.disabled).toBe(true)
  })

  it('reads the decision again when a reconciled row reopens', async () => {
    get_request.mockResolvedValueOnce({ data: decision() })
    get_request.mockResolvedValueOnce({ data: decision(alfa, { hosting_payment_id: 57, version: 'after-review' }) })
    const wrapper = open()
    await flushPromises()
    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    await send(wrapper).trigger('click')

    expect(get_request).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('confirm')).toEqual([[{ hosting_payment_id: 57, period_version: 'after-review' }]])
  })
})
