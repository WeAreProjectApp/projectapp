import { mount } from '@vue/test-utils'
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue'
import BaseRichTextListEditor from '../../components/base/BaseRichTextListEditor.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'

import ScopeForm from '../../components/WebAppDiagnostic/admin/sections/ScopeForm.vue'

const originalUseI18n = global.useI18n
beforeEach(() => { global.useI18n = () => ({ t: (key) => key }) })
afterAll(() => { global.useI18n = originalUseI18n })

function mountForm(modelValue = MODEL) {
  return mount(ScopeForm, {
    props: { modelValue: { ...modelValue } },
    global: { components: { BaseRichTextEditor, BaseRichTextListEditor, BaseSegmented } },
  })
}

async function editConsiderationsSource(wrapper, value) {
  await wrapper.findAll('[role="tab"]').find((tab) => tab.text() === 'richText.source').trigger('click')
  await wrapper.get('[data-testid="rich-text-source-input"]').setValue(value)
}

const MODEL = {
  index: '07',
  title: 'Alcance',
  considerationsText: 'Solo web\nSin migración',
}

describe('WebAppDiagnostic admin ScopeForm', () => {
  it('prefills the fields from the model value', () => {
    const wrapper = mountForm()
    const inputs = wrapper.findAll('input')
    expect(inputs[0].element.value).toBe('07')
    expect(inputs[1].element.value).toBe('Alcance')
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]').map((input) => input.element.value)).toEqual(['Solo web', 'Sin migración'])
  })

  it('emits the updated model when editing the title', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input')[1].setValue('Alcance ajustado')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted.at(-1)[0].title).toBe('Alcance ajustado')
  })

  it('emits the updated model when editing the considerations text', async () => {
    const wrapper = mountForm()
    await editConsiderationsSource(wrapper, 'Nueva línea')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted.at(-1)[0].considerationsText).toBe('<p>Nueva línea</p>&#10;\nSin migración')
  })

  it('syncs external model changes into the form', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({ modelValue: { ...MODEL, title: 'Desde afuera' } })
    expect(wrapper.findAll('input')[1].element.value).toBe('Desde afuera')
  })
})
