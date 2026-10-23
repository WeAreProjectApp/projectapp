import { mount } from '@vue/test-utils'
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue'
import BaseRichTextListEditor from '../../components/base/BaseRichTextListEditor.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'
import ExecutiveSummaryForm from '../../components/WebAppDiagnostic/admin/sections/ExecutiveSummaryForm.vue'

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
    title: 'Resumen ejecutivo',
    intro: 'Introducción breve.',
    severityCounts: { critico: 0, alto: 0, medio: 0, bajo: 0 },
    narrative: 'Narrativa inicial.',
    highlightsText: '',
    ...overrides,
  }
}

function mountForm(propsOverrides = {}) {
  return mount(ExecutiveSummaryForm, {
    props: { modelValue: defaultValue(), ...propsOverrides },
    global: { components: { BaseRichTextEditor, BaseRichTextListEditor, BaseSegmented } },
  })
}

describe('ExecutiveSummaryForm', () => {
  it('renders index input with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ index: '2.1' }) })
    const inputs = wrapper.findAll('input[type="text"]')
    expect(inputs[0].element.value).toBe('2.1')
  })

  it('renders title input with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ title: 'Mi resumen' }) })
    const inputs = wrapper.findAll('input[type="text"]')
    expect(inputs[1].element.value).toBe('Mi resumen')
  })

  it('renders intro textarea with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ intro: 'Texto de intro' }) })
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]')[0].element.value).toBe('Texto de intro')
  })

  it('renders narrative textarea with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ narrative: 'Texto narrativo' }) })
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]')[1].element.value).toBe('Texto narrativo')
  })

  it('renders highlights textarea with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ highlightsText: 'Punto 1\nPunto 2' }) })
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]').slice(2).map((editor) => editor.element.value)).toEqual(['Punto 1', 'Punto 2'])
  })

  it('emits update:modelValue when index input changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="text"]')[0].setValue('3.2')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0][0]).toMatchObject({ index: '3.2' })
  })

  it('emits update:modelValue when title input changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="text"]')[1].setValue('Nuevo título')
    expect(wrapper.emitted('update:modelValue')[0][0]).toMatchObject({ title: 'Nuevo título' })
  })

  it('emits update:modelValue when intro textarea changes', async () => {
    const wrapper = mountForm()
    await editSource(wrapper, 0, 'Intro actualizada')
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toMatchObject({ intro: 'Intro actualizada' })
  })

  it('emits update:modelValue when severityCounts.critico changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="number"]')[0].setValue('3')
    expect(wrapper.emitted('update:modelValue')[0][0].severityCounts.critico).toBe(3)
  })

  it('emits update:modelValue when severityCounts.alto changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="number"]')[1].setValue('5')
    expect(wrapper.emitted('update:modelValue')[0][0].severityCounts.alto).toBe(5)
  })

  it('emits update:modelValue when severityCounts.medio changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="number"]')[2].setValue('7')
    expect(wrapper.emitted('update:modelValue')[0][0].severityCounts.medio).toBe(7)
  })

  it('emits update:modelValue when severityCounts.bajo changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="number"]')[3].setValue('2')
    expect(wrapper.emitted('update:modelValue')[0][0].severityCounts.bajo).toBe(2)
  })

  it('emits update:modelValue when narrative textarea changes', async () => {
    const wrapper = mountForm()
    await editSource(wrapper, 1, 'Nueva narrativa')
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toMatchObject({ narrative: 'Nueva narrativa' })
  })

  it('emits update:modelValue when highlights textarea changes', async () => {
    const wrapper = mountForm()
    await editSource(wrapper, 2, 'Highlight A\nHighlight B')
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toMatchObject({ highlightsText: '<p>Highlight A&#10;Highlight B</p>&#10;' })
  })

  it('syncs form state when modelValue prop is updated externally', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({ modelValue: defaultValue({ index: '9.9', title: 'Actualizado' }) })
    expect(wrapper.findAll('input[type="text"]')[0].element.value).toBe('9.9')
    expect(wrapper.findAll('input[type="text"]')[1].element.value).toBe('Actualizado')
  })

  it('syncs severityCounts when modelValue.severityCounts is updated externally', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({
      modelValue: defaultValue({ severityCounts: { critico: 4, alto: 3, medio: 2, bajo: 1 } }),
    })
    expect(wrapper.findAll('input[type="number"]')[0].element.value).toBe('4')
    expect(wrapper.findAll('input[type="number"]')[1].element.value).toBe('3')
  })
})
