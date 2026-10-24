import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue'
import BaseRichTextListEditor from '../../components/base/BaseRichTextListEditor.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'
import PurposeForm from '../../components/WebAppDiagnostic/admin/sections/PurposeForm.vue'

const originalUseI18n = global.useI18n
beforeEach(() => { global.useI18n = () => ({ t: (key) => key }) })
afterAll(() => { global.useI18n = originalUseI18n })

function defaultValue(overrides = {}) {
  return {
    index: '1',
    title: 'Propósito del diagnóstico',
    paragraphsText: 'Párrafo inicial.',
    scopeNote: 'Nota de alcance.',
    severityTitle: 'Severidad',
    severityIntro: 'Intro de severidad',
    severityLevels: [],
    ...overrides,
  }
}

function mountForm(propsOverrides = {}) {
  return mount(PurposeForm, {
    props: { modelValue: defaultValue(), ...propsOverrides },
    global: { components: { BaseRichTextEditor, BaseRichTextListEditor, BaseSegmented } },
  })
}

describe('PurposeForm', () => {
  it('renders index input with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ index: '2' }) })
    expect(wrapper.findAll('input[type="text"]')[0].element.value).toBe('2')
  })

  it('renders title input with value from modelValue', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ title: 'Mi propósito' }) })
    expect(wrapper.findAll('input[type="text"]')[1].element.value).toBe('Mi propósito')
  })

  it('renders paragraphs textarea with value from modelValue', async () => {
    const wrapper = mountForm({ modelValue: defaultValue({ paragraphsText: 'Línea 1\nLínea 2' }) })
    await nextTick()
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]').slice(0, 2).map((editor) => editor.element.value)).toEqual(['Línea 1', 'Línea 2'])
  })

  it('renders scope note textarea with value from modelValue', async () => {
    const wrapper = mountForm({ modelValue: defaultValue({ scopeNote: 'Solo backend' }) })
    await nextTick()
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]')[1].element.value).toBe('Solo backend')
  })

  it('shows empty state message when severityLevels is empty', () => {
    const wrapper = mountForm({ modelValue: defaultValue({ severityLevels: [] }) })
    expect(wrapper.text()).toContain('Sin niveles configurados.')
  })

  it('hides empty state message when severityLevels has items', () => {
    const wrapper = mountForm({
      modelValue: defaultValue({ severityLevels: [{ level: 'Crítico', meaning: 'Falla total' }] }),
    })
    expect(wrapper.text()).not.toContain('Sin niveles configurados.')
  })

  it('renders existing severity levels from modelValue', async () => {
    const wrapper = mountForm({
      modelValue: defaultValue({
        severityLevels: [
          { level: 'Alto', meaning: 'Impacto alto' },
          { level: 'Medio', meaning: 'Impacto parcial' },
        ],
      }),
    })
    await nextTick()
    // index, title, severityTitle, severityIntro = 4 base inputs; levels add more
    const textInputs = wrapper.findAll('input[type="text"]')
    expect(textInputs[4].element.value).toBe('Alto')
    expect(textInputs[5].element.value).toBe('Medio')
    expect(wrapper.findAll('[data-testid="rich-text-source-input"]')[2].element.value).toBe('Impacto alto')
  })

  it('clicking add button appends an empty severity level row', async () => {
    const wrapper = mountForm()
    const addBtn = wrapper.findAll('button').find((button) => button.text() === 'Agregar')
    await addBtn.trigger('click')
    await nextTick()
    expect(wrapper.findAll('input[type="text"]').length).toBeGreaterThan(4)
    expect(wrapper.text()).not.toContain('Sin niveles configurados.')
  })

  it('emits update:modelValue with one new level after clicking add', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('button').find((button) => button.text() === 'Agregar').trigger('click')
    await nextTick()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    const emitted = wrapper.emitted('update:modelValue')[0][0]
    expect(emitted.severityLevels).toHaveLength(1)
    expect(emitted.severityLevels[0]).toEqual({ level: '', meaning: '' })
  })

  it('clicking remove button removes the severity level at the given index', async () => {
    const wrapper = mountForm({
      modelValue: defaultValue({
        severityLevels: [
          { level: 'Crítico', meaning: 'Caída total' },
          { level: 'Bajo', meaning: 'Sin impacto' },
        ],
      }),
    })
    const removeBtn = wrapper.findAll('button').find((button) => button.text() === 'Quitar')
    await removeBtn.trigger('click')
    await nextTick()
    const textInputs = wrapper.findAll('input[type="text"]')
    // Only 1 level remains (base 4 + 1 = 5 text inputs)
    expect(textInputs).toHaveLength(5)
    expect(textInputs[4].element.value).toBe('Bajo')
  })

  it('emits update:modelValue with the remaining levels after removing one', async () => {
    const wrapper = mountForm({
      modelValue: defaultValue({
        severityLevels: [
          { level: 'Alto', meaning: 'Impacto alto' },
          { level: 'Bajo', meaning: 'Sin impacto' },
        ],
      }),
    })
    await wrapper.findAll('button').find((button) => button.text() === 'Quitar').trigger('click')
    await nextTick()
    const emittedLevels = wrapper.emitted('update:modelValue').at(-1)[0].severityLevels
    expect(emittedLevels).toHaveLength(1)
    expect(emittedLevels[0].level).toBe('Bajo')
  })

  it('emits update:modelValue when index input changes', async () => {
    const wrapper = mountForm()
    await wrapper.findAll('input[type="text"]')[0].setValue('1.2')
    expect(wrapper.emitted('update:modelValue')[0][0]).toMatchObject({ index: '1.2' })
  })

  it('syncs form when modelValue prop is updated externally', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({ modelValue: defaultValue({ index: '5', title: 'Nuevo propósito' }) })
    expect(wrapper.findAll('input[type="text"]')[0].element.value).toBe('5')
    expect(wrapper.findAll('input[type="text"]')[1].element.value).toBe('Nuevo propósito')
  })
})
