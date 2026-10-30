import { mount, flushPromises } from '@vue/test-utils'
import CollectionAccountProjectContext from '../../../../components/accounting/billing/CollectionAccountProjectContext.vue'
import { get_request, create_request } from '../../../../stores/services/request_http'

jest.mock('../../../../stores/services/request_http', () => ({ get_request: jest.fn(), create_request: jest.fn() }))
global.useLocalePath = () => path => path
const options = { contracts: [], delivery_version: 4, contract_sources: [
  { source_type: 'document', id: 31, title: 'Contrato Aurora', origin_label: 'Documento del proyecto' },
] }
const hosting = { overview: { subscription: { associated: false, payments: [] } } }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
let wrappers
function render(modelValue = {}) {
  let wrapper
  wrapper = mount(CollectionAccountProjectContext, {
    props: { projectId: 7, modelValue, 'onUpdate:modelValue': value => wrapper.setProps({ modelValue: value }) },
    global: { stubs: {
      NuxtLink: { template: '<a><slot /></a>' }, BaseFormField: { template: '<div><slot /></div>' },
      BaseSelect: { props: ['modelValue', 'options'], emits: ['update:modelValue'],
        template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option value="">Seleccionar</option><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>' },
      BaseControlGate: { props: ['reasons'], template: '<div><slot :blocked="reasons.length > 0" /></div>' },
      BaseButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
    } },
  })
  wrappers.push(wrapper)
  return wrapper
}
beforeEach(() => {
  wrappers = []
  jest.resetAllMocks()
  get_request.mockImplementation(url => Promise.resolve({ data: url.includes('/options/') ? options : hosting }))
})
afterEach(() => wrappers.forEach(wrapper => wrapper.unmount()))

it('allows an explicit deferral while options are still loading', async () => {
  const response = deferred()
  get_request.mockReturnValue(response.promise)
  const wrapper = render()
  await wrapper.get('[data-testid="billing-document-pending"]').trigger('click')
  expect(wrapper.emitted('valid').at(-1)[0]).toBe(true)
  expect(wrapper.emitted('update:modelValue').at(-1)[0]).toMatchObject({ document_pending: true, billing_nature: null })
})
it('preserves the explicit choice after a failed lookup and restores the blocker when disabled', async () => {
  get_request.mockRejectedValue({ response: { data: { detail: 'Consulta no disponible.' } } })
  const wrapper = render({ document_pending: true })
  await flushPromises()
  expect(wrapper.emitted('valid').at(-1)[0]).toBe(true)
  await wrapper.get('[data-testid="billing-document-pending"]').trigger('click')
  expect(wrapper.emitted('validation-message').at(-1)[0]).toBe('Consulta no disponible.')
})
it('keeps a reviewed deferral when returning from preview', async () => {
  const wrapper = render({ document_pending: true, billing_nature: 'contract' })
  await flushPromises()
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  expect(wrapper.emitted('valid').at(-1)[0]).toBe(true)
  expect(wrapper.find('[data-testid="billing-link-contract-open"]').exists()).toBe(false)
})
