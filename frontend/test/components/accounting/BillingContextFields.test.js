import { mount } from '@vue/test-utils'
import BillingContextFields from '../../../components/accounting/billing/BillingContextFields.vue'

const options = {
  project_name: 'Proyecto Aurora',
  hosting_id: 71,
  contracts: [
    {
      id: 11,
      title: 'Contrato Aurora',
      amendments: [{ id: 111, title: 'Otrosí Aurora' }],
    },
    {
      id: 12,
      title: 'Contrato Boreal',
      amendments: [{ id: 121, title: 'Otrosí Boreal' }],
    },
  ],
}

function mountFields(modelValue, props = {}) {
  return mount(BillingContextFields, {
    props: { modelValue, options, ...props },
  })
}

describe('BillingContextFields', () => {
  it('records an explicit deferral and discards every link while keeping the chosen nature', async () => {
    const wrapper = mountFields({ billing_nature: 'contract', contract_id: 11, amendment_id: 111 })
    await wrapper.get('[data-testid="billing-document-pending"]').trigger('click')
    const deferred = wrapper.emitted('update:modelValue')[0][0]
    expect(deferred).toEqual({ billing_nature: 'contract', document_pending: true,
      contract_id: null, amendment_id: null, project_hosting_id: null, hosting_payment_id: null })
    await wrapper.setProps({ modelValue: deferred })
    expect(wrapper.find('[data-testid="billing-contract"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="billing-document-pending-help"]').text()).toContain('quién')
    await wrapper.get('[data-testid="billing-nature"]').setValue('')
    expect(wrapper.emitted('update:modelValue')[1][0]).toMatchObject({ billing_nature: null, document_pending: true })
  })

  it('requires selecting links again after turning off the deferral', async () => {
    const wrapper = mountFields({ billing_nature: 'contract', document_pending: true })
    await wrapper.get('[data-testid="billing-document-pending"]').trigger('click')
    const context = wrapper.emitted('update:modelValue')[0][0]
    await wrapper.setProps({ modelValue: context })
    expect(context.document_pending).toBe(false)
    expect(wrapper.get('[data-testid="billing-contract"]').element.value).toBe('')
  })

  it('offers completion without a deferral switch in the administrative editor', () => {
    const wrapper = mountFields({ billing_nature: 'contract' }, { allowPending: false })
    expect(wrapper.find('[data-testid="billing-document-pending"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="billing-contract"]').exists()).toBe(true)
  })

  it('clears every association when the nature changes', async () => {
    // Falla si un cobro cambia de naturaleza y conserva relaciones incompatibles.
    const wrapper = mountFields({
      billing_nature: 'contract',
      contract_id: 11,
      amendment_id: 111,
      project_hosting_id: 71,
      hosting_payment_id: 910,
    })

    await wrapper.get('[data-testid="billing-nature"]').setValue('hosting')

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      billing_nature: 'hosting',
      contract_id: null,
      amendment_id: null,
      project_hosting_id: null,
      hosting_payment_id: null,
    })
  })

  it('clears the amendment when the contract changes', async () => {
    // Falla si un otrosí queda asociado al contrato que se acaba de reemplazar.
    const wrapper = mountFields({
      billing_nature: 'contract',
      contract_id: 11,
      amendment_id: 111,
      project_hosting_id: null,
      hosting_payment_id: null,
    })

    await wrapper.get('[data-testid="billing-contract"]').setValue('12')

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      billing_nature: 'contract',
      contract_id: 12,
      amendment_id: null,
      project_hosting_id: null,
      hosting_payment_id: null,
    })
  })

  it('lists only amendments from the selected contract', () => {
    // Falla si se ofrece un otrosí perteneciente a otro contrato del proyecto.
    const wrapper = mountFields({
      billing_nature: 'contract',
      contract_id: 12,
      amendment_id: null,
      project_hosting_id: null,
      hosting_payment_id: null,
    })

    const amendmentOptions = Array.from(wrapper.get('[data-testid="billing-amendment"]').element.options)
      .map((option) => `${option.value}:${option.text}`)

    expect(amendmentOptions).toEqual([':Sin otrosí', '121:Otrosí Boreal'])
  })

  it('emits the selected hosting identifier explicitly', async () => {
    // Falla si el formulario marca hosting sin registrar cuál hosting fue elegido.
    const wrapper = mountFields({
      billing_nature: 'hosting',
      contract_id: null,
      amendment_id: null,
      project_hosting_id: null,
      hosting_payment_id: null,
    })

    const hosting = wrapper.get('[data-testid="billing-hosting"]')
    expect(hosting.element.value).toBe('')

    await hosting.setValue('71')

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      billing_nature: 'hosting',
      contract_id: null,
      amendment_id: null,
      project_hosting_id: 71,
      hosting_payment_id: null,
    })
  })
})
