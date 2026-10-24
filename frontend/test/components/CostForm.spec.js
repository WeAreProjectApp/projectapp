import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue'
import BaseRichTextListEditor from '../../components/base/BaseRichTextListEditor.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'
import CostForm from '../../components/WebAppDiagnostic/admin/sections/CostForm.vue'

const originalUseI18n = global.useI18n
beforeEach(() => { global.useI18n = () => ({ t: (key) => key }) })
afterAll(() => { global.useI18n = originalUseI18n })

async function editSource(wrapper, index, value) {
  await wrapper.findAll('[role="tab"]').filter((tab) => tab.text() === 'richText.source')[index].trigger('click')
  await wrapper.findAll('[data-testid="rich-text-source-input"]')[index].setValue(value)
}

function defaultValue(overrides = {}) {
  return {
    index: '1',
    title: 'Costo y pago',
    intro: 'Descripción del costo.',
    paymentDescription: [],
    note: '',
    ...overrides,
  }
}

function mountForm(propsOverrides = {}) {
  return mount(CostForm, {
    props: { modelValue: defaultValue(), ...propsOverrides },
    global: { components: { BaseRichTextEditor, BaseRichTextListEditor, BaseSegmented } },
  })
}

describe('CostForm', () => {
  it('renders index input with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ index: '4' }) })
    expect(wrapper.findAll('input[type="text"]')[0].element.value).toBe('4')
  })

  it('renders title input with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ title: 'Precio del proyecto' }) })
    expect(wrapper.findAll('input[type="text"]')[1].element.value).toBe('Precio del proyecto')
  })

  it('renders intro textarea with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ intro: 'El costo total es...' }) })
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]')[0].element.value).toBe('El costo total es...')
  })

  it('renders note textarea with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ note: 'IVA incluido.' }) })
    const editors = wrapper.findAll('[data-testid="rich-text-source-input"]')
    expect(editors[editors.length - 1].element.value).toBe('IVA incluido.')
  })

  it('renders existing payment description items', () => {
    const wrapper = mountForm({
      modelValue: defaultValue({
        paymentDescription: [
          { label: 'Inicial', detail: '50% al inicio' },
          { label: 'Final', detail: '50% al entregar' },
        ],
      }),
    })
    // base: index, title = 2 text inputs; each item adds one label input
    const textInputs = wrapper.findAll('input[type="text"]')
    expect(textInputs[2].element.value).toBe('Inicial')
    expect(textInputs[3].element.value).toBe('Final')
  })

  it('clicking add button appends an empty payment item', async () => {
    const wrapper = mountForm()
    const addBtn = wrapper.findAll('button').find((button) => button.text() === 'Agregar')
    await addBtn.trigger('click')
    await nextTick()
    const textInputs = wrapper.findAll('input[type="text"]')
    expect(textInputs).toHaveLength(3) // base 2 + 1 new label input
  })

  it('emits update:modelValue with one new item after clicking add', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('button').find((button) => button.text() === 'Agregar').trigger('click')
    await nextTick()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    const emitted = wrapper.emitted('update:modelValue')[0][0]
    expect(emitted.paymentDescription).toHaveLength(1)
    expect(emitted.paymentDescription[0]).toEqual({ label: '', detail: '' })
  })

  it('clicking delete button removes the payment item', async () => {
    const wrapper = mountForm({
      modelValue: defaultValue({
        paymentDescription: [
          { label: 'Cuota 1', detail: 'Primer pago' },
          { label: 'Cuota 2', detail: 'Segundo pago' },
        ],
      }),
    })
    await wrapper.get('button[aria-label="Eliminar descripción"]').trigger('click')
    await nextTick()
    const textInputs = wrapper.findAll('input[type="text"]')
    expect(textInputs).toHaveLength(3) // base 2 + 1 remaining
    expect(textInputs[2].element.value).toBe('Cuota 2')
  })

  it('emits update:modelValue when index input changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="text"]')[0].setValue('2')
    expect(wrapper.emitted('update:modelValue')[0][0]).toMatchObject({ index: '2' })
  })

  it('emits update:modelValue when intro textarea changes', async () => {
    const wrapper = mountForm()
    await editSource(wrapper, 0, 'Nuevo intro de costo')
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toMatchObject({ intro: 'Nuevo intro de costo' })
  })

  it('emits update:modelValue when note textarea changes', async () => {
    const wrapper = mountForm()
    const sourceInputs = wrapper.findAll('[data-testid="rich-text-source-input"]')
    await editSource(wrapper, sourceInputs.length - 1, 'Nota actualizada')
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toMatchObject({ note: 'Nota actualizada' })
  })

  it('syncs form when modelValue prop is updated externally', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({ modelValue: defaultValue({ index: '7', title: 'Costo final' }) })
    expect(wrapper.findAll('input[type="text"]')[0].element.value).toBe('7')
    expect(wrapper.findAll('input[type="text"]')[1].element.value).toBe('Costo final')
  })

  it('syncs paymentDescription when modelValue is updated externally', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({
      modelValue: defaultValue({
        paymentDescription: [{ label: 'Entrega', detail: 'Al finalizar' }],
      }),
    })
    expect(wrapper.findAll('input[type="text"]')[2].element.value).toBe('Entrega')
  })
})
