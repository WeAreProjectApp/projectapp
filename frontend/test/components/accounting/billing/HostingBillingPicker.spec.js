import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import HostingBillingPicker from '../../../../components/accounting/billing/HostingBillingPicker.vue'
import hostingBilling from '../../../../locales/hostingBilling/es'
import { create_request, get_request } from '../../../../stores/services/request_http'

jest.mock('../../../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
}))

const model = {
  billing_nature: 'hosting', contract_id: null, amendment_id: null,
  project_hosting_id: null, hosting_payment_id: null,
}

const candidate = (overrides = {}) => ({
  project_hosting_id: 91,
  hosting_record_id: null,
  domain_url: 'aurora.co',
  payment_modality: 'quarterly',
  is_active: true,
  historical: false,
  selectable: true,
  requires_association: false,
  ...overrides,
})

const pickerData = (overrides = {}) => ({
  selection: {
    version: 4,
    candidates: [candidate()],
    can_create: false,
    requires_reconciliation: false,
    blockers: [],
    ...overrides.selection,
  },
  overview: {
    hosting_id: 91,
    project_name: 'Proyecto Aurora',
    subscription: { associated: false, payments: [] },
    ...overrides.overview,
  },
  inventory: {
    hosting: { subscription_id: 22, hosting_record_ids: [31] },
    ...overrides.inventory,
  },
})

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

function mountPicker(props = {}) {
  const i18n = createI18n({
    legacy: false,
    locale: 'es',
    messages: { es: { hostingBilling } },
  })
  let wrapper
  wrapper = mount(HostingBillingPicker, {
    props: {
      projectId: 7,
      client: { id: 17, name: 'Cliente Aurora' },
      modelValue: { ...model },
      data: pickerData(),
      ...props,
      'onUpdate:modelValue': value => wrapper.setProps({ modelValue: value }),
    },
    global: {
      plugins: [i18n],
      stubs: {
        BaseButton: {
          emits: ['click'],
          template: '<button v-bind="$attrs" type="button" @click="$emit(\'click\')"><slot /></button>',
        },
        HostingFormModal: {
          props: ['initialContext'],
          emits: ['close', 'submit'],
          template: `<section data-testid="hosting-create-modal">
            <p data-testid="hosting-create-owner">{{ initialContext.client.name }} · {{ initialContext.projectId }}</p>
            <button data-testid="hosting-create-cancel" @click="$emit('close')">Cancelar</button>
            <button data-testid="hosting-create-submit" @click="$emit('submit', { domain_url: 'nuevo.co', payment_modality: 'quarterly' })">Guardar</button>
          </section>`,
        },
      },
    },
  })
  return wrapper
}

describe('HostingBillingPicker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    jest.clearAllMocks()
    get_request.mockResolvedValue({ data: pickerData() })
  })

  // Falla si un hosting ya vinculado pierde su dominio, periodicidad o selección explícita.
  it('selects an existing hosting without writing an association', async () => {
    const wrapper = mountPicker()
    const choice = wrapper.get('[data-testid="billing-hosting-choice"]')

    expect(choice.findAll('option')[1].text()).toBe('aurora.co · Trimestral · Activo')
    await choice.setValue('hosting:91')
    await wrapper.get('[data-testid="billing-hosting-review"]').trigger('click')

    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({
      billing_nature: 'hosting', contract_id: null, amendment_id: null,
      project_hosting_id: 91, hosting_payment_id: null,
    })
    expect(create_request).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  // Falla si la confirmación aplica un payload distinto del que el operador revisó.
  it('confirms an eligible record with the previewed association payload', async () => {
    const data = pickerData({
      selection: { candidates: [candidate({ project_hosting_id: null, hosting_record_id: 33, requires_association: true })] },
    })
    const wrapper = mountPicker({ data })
    const payload = {
      expected_version: 4,
      subscription_id: 22,
      hosting_record_ids: [31, 33],
      operational_record_id: 33,
      reason: 'Vínculo confirmado explícitamente desde la cuenta de cobro.',
    }
    create_request
      .mockResolvedValueOnce({ data: { proposal: { operational_record_id: 33 } } })
      .mockResolvedValueOnce({ data: { id: 124 } })

    await wrapper.get('[data-testid="billing-hosting-choice"]').setValue('record:33')
    await wrapper.get('[data-testid="billing-hosting-review"]').trigger('click')
    await flushPromises()

    expect(create_request).toHaveBeenCalledWith(
      'admin/billing-context/projects/7/hosting/?preview=1', payload,
    )
    expect(wrapper.get('[data-testid="billing-hosting-link-preview"]').text())
      .toContain('aurora.co · Trimestral · Activo')
    await wrapper.get('[data-testid="billing-hosting-confirm"]').trigger('click')
    await flushPromises()

    expect(create_request).toHaveBeenLastCalledWith(
      'admin/billing-context/projects/7/hosting/', payload,
    )
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({
      billing_nature: 'hosting', contract_id: null, amendment_id: null,
      project_hosting_id: 124, hosting_payment_id: null,
    })
    wrapper.unmount()
  })

  // Falla si la previsualización del proyecto anterior se muestra tras cambiar de contexto.
  it('discards a late association preview after changing project', async () => {
    const latePreview = deferred()
    const data = pickerData({
      selection: { candidates: [candidate({ project_hosting_id: null, hosting_record_id: 33, requires_association: true })] },
    })
    create_request.mockReturnValue(latePreview.promise)
    const wrapper = mountPicker({ data })

    await wrapper.get('[data-testid="billing-hosting-choice"]').setValue('record:33')
    await wrapper.get('[data-testid="billing-hosting-review"]').trigger('click')
    await wrapper.setProps({ projectId: 8 })
    latePreview.resolve({ data: { proposal: { operational_record_id: 33 } } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Confirmar el hosting del cobro')
    expect(wrapper.emitted('update:modelValue')).toEqual([[
      { ...model, project_hosting_id: null, hosting_payment_id: null },
    ]])
    wrapper.unmount()
  })

  // Falla si cambiar los datos de la cuenta acepta una revisión calculada para el contexto anterior.
  it('discards a late association preview after changing the account context', async () => {
    const latePreview = deferred()
    const data = pickerData({
      selection: { candidates: [candidate({ project_hosting_id: null, hosting_record_id: 33, requires_association: true })] },
    })
    create_request.mockReturnValue(latePreview.promise)
    const wrapper = mountPicker({ data })

    await wrapper.get('[data-testid="billing-hosting-choice"]').setValue('record:33')
    await wrapper.get('[data-testid="billing-hosting-review"]').trigger('click')
    await wrapper.setProps({ modelValue: { ...model, document_pending: true } })
    latePreview.resolve({ data: { proposal: { operational_record_id: 33 } } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Confirmar el hosting del cobro')
    expect(wrapper.emitted('update:modelValue')).toEqual([[
      { ...model, project_hosting_id: null, hosting_payment_id: null },
    ]])
    wrapper.unmount()
  })

  // Falla si una respuesta en vuelo escribe en una cuenta ya cerrada.
  it('ignores a late association preview after the picker closes', async () => {
    const latePreview = deferred()
    const data = pickerData({
      selection: { candidates: [candidate({ project_hosting_id: null, hosting_record_id: 33, requires_association: true })] },
    })
    create_request.mockReturnValue(latePreview.promise)
    const wrapper = mountPicker({ data })

    await wrapper.get('[data-testid="billing-hosting-choice"]').setValue('record:33')
    await wrapper.get('[data-testid="billing-hosting-review"]').trigger('click')
    wrapper.unmount()
    latePreview.resolve({ data: { proposal: { operational_record_id: 33 } } })
    await flushPromises()

    expect(wrapper.emitted('update:modelValue')).toEqual([[
      { ...model, project_hosting_id: null, hosting_payment_id: null },
    ]])
  })

  // Falla si crear un hosting pierde el cliente, proyecto o datos de la cuenta en curso.
  it('creates a hosting with the account owners while preserving the account model', async () => {
    const accountModel = { ...model, document_pending: true, notes: 'Conservar esta cuenta' }
    const wrapper = mountPicker({
      modelValue: accountModel,
      data: pickerData({ selection: { candidates: [], can_create: true } }),
    })
    create_request.mockResolvedValue({ data: { id: 331, domain_url: 'nuevo.co' } })

    await wrapper.get('[data-testid="billing-hosting-create"]').trigger('click')
    expect(wrapper.get('[data-testid="hosting-create-owner"]').text()).toBe('Cliente Aurora · 7')
    await wrapper.get('[data-testid="hosting-create-submit"]').trigger('click')
    await flushPromises()

    expect(create_request).toHaveBeenCalledWith('accounting/hostings/create/', {
      domain_url: 'nuevo.co', payment_modality: 'quarterly', client: 17, project: 7,
    })
    expect(wrapper.props('modelValue')).toEqual(accountModel)
    expect(wrapper.emitted('refreshed').at(-1)[0]).toEqual(pickerData())
    wrapper.unmount()
  })

  // Falla si cancelar el alta descarta los datos que ya se habían escrito en la cuenta de cobro.
  it('keeps the account model when the nested hosting form is cancelled', async () => {
    const accountModel = { ...model, document_pending: true, notes: 'Conservar esta cuenta' }
    const wrapper = mountPicker({
      modelValue: accountModel,
      data: pickerData({ selection: { candidates: [], can_create: true } }),
    })

    await wrapper.get('[data-testid="billing-hosting-create"]').trigger('click')
    expect(wrapper.get('[data-testid="hosting-create-owner"]').text()).toBe('Cliente Aurora · 7')
    await wrapper.get('[data-testid="hosting-create-cancel"]').trigger('click')

    expect(wrapper.props('modelValue')).toEqual(accountModel)
    expect(wrapper.text()).not.toContain('Cliente Aurora · 7')
    wrapper.unmount()
  })

  // Falla si un caso contradictorio permite crear un hosting o esconde el camino de conciliación.
  it('shows blockers and sends conflicting records to reconciliation', async () => {
    const wrapper = mountPicker({
      data: pickerData({
        selection: {
          candidates: [candidate({ selectable: false })],
          can_create: false,
          requires_reconciliation: true,
          blockers: [{ message: 'El dominio ya pertenece a otro proyecto.' }],
        },
      }),
    })

    expect(wrapper.get('[data-testid="billing-hosting-blockers"]').text())
      .toBe('El dominio ya pertenece a otro proyecto.')
    expect(wrapper.text()).not.toContain('Crear hosting')
    await wrapper.get('[data-testid="billing-hosting-reconcile"]').trigger('click')

    expect(wrapper.emitted('reconcile')).toEqual([[]])
    wrapper.unmount()
  })
})
