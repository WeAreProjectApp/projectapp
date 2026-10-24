import { mount } from '@vue/test-utils'
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'
import RadiographyForm from '../../components/WebAppDiagnostic/admin/sections/RadiographyForm.vue'

const originalUseI18n = global.useI18n
beforeEach(() => { global.useI18n = () => ({ t: (key) => key }) })
afterAll(() => { global.useI18n = originalUseI18n })

async function editIntroSource(wrapper, value) {
  await wrapper.findAll('[role="tab"]').find((tab) => tab.text() === 'richText.source').trigger('click')
  await wrapper.get('[data-testid="rich-text-source-input"]').setValue(value)
}

const baseModel = () => ({
  index: '2',
  title: 'Radiografía',
  intro: 'Texto introductorio.',
  includesTitle: '¿Qué incluye?',
  includes: [],
  classificationTitle: 'Clasificación',
  classificationIntro: 'Intro clasificación',
  classificationRows: [],
})

function mountForm(modelValue = baseModel()) {
  return mount(RadiographyForm, {
    props: { modelValue },
    global: { components: { BaseRichTextEditor, BaseSegmented } },
  })
}

describe('RadiographyForm', () => {
  it('mounts without errors', () => {
    const wrapper = mountForm()
    expect(wrapper.exists()).toBe(true)
  })

  it('renders the index value from modelValue', () => {
    const wrapper = mountForm()
    const inputs = wrapper.findAll('input[type="text"]')
    expect(inputs[0].element.value).toBe('2')
  })

  it('renders the title value from modelValue', () => {
    const wrapper = mountForm()
    const inputs = wrapper.findAll('input[type="text"]')
    expect(inputs[1].element.value).toBe('Radiografía')
  })

  it('emits update:modelValue when title input is changed', async () => {
    const wrapper = mountForm()
    const inputs = wrapper.findAll('input[type="text"]')
    await inputs[1].setValue('Nueva radiografía')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted[emitted.length - 1][0].title).toBe('Nueva radiografía')
  })

  it('emits update:modelValue when intro textarea is changed', async () => {
    const wrapper = mountForm()
    await editIntroSource(wrapper, 'Nuevo intro')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted[emitted.length - 1][0].intro).toBe('Nuevo intro')
  })

  it('clicking Agregar include button appends a new include row', async () => {
    const wrapper = mountForm()
    const agregar = wrapper.findAll('button').find((b) => b.text() === 'Agregar')
    await agregar.trigger('click')
    const inputs = wrapper.findAll('input[placeholder="Título"]')
    expect(inputs.length).toBe(1)
  })

  it('the new include row renders an empty title input', async () => {
    const wrapper = mountForm()
    const agregar = wrapper.findAll('button').find((b) => b.text() === 'Agregar')
    await agregar.trigger('click')
    const titleInput = wrapper.find('input[placeholder="Título"]')
    expect(titleInput.element.value).toBe('')
  })

  it('clicking Quitar remove-include button removes that row', async () => {
    const model = { ...baseModel(), includes: [{ title: 'Del', description: 'Desc' }] }
    const wrapper = mountForm(model)
    const quitarBtn = wrapper.findAll('button').find((b) => b.text().includes('Quitar'))
    await quitarBtn.trigger('click')
    expect(wrapper.find('input[placeholder="Título"]').exists()).toBe(false)
  })

  it('clicking add classification row button appends a new row', async () => {
    const wrapper = mountForm()
    const agrega = wrapper.findAll('button').filter((b) => b.text() === 'Agregar')
    await agrega[agrega.length - 1].trigger('click')
    expect(wrapper.find('input[placeholder="Dimensión"]').exists()).toBe(true)
  })

  it('clicking row remove button removes that classification row', async () => {
    const model = {
      ...baseModel(),
      classificationRows: [{ dimension: 'D', small: 'S', medium: 'M', large: 'L' }],
    }
    const wrapper = mountForm(model)
    const removeBtn = wrapper.find('button[aria-label="Eliminar tecnología"]')
    await removeBtn.trigger('click')
    expect(wrapper.find('input[placeholder="Dimensión"]').exists()).toBe(false)
  })

  it('re-syncs form when modelValue prop changes via setProps', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({ modelValue: { ...baseModel(), title: 'Actualizado' } })
    const inputs = wrapper.findAll('input[type="text"]')
    expect(inputs[1].element.value).toBe('Actualizado')
  })

  it('emits update:modelValue preserving existing fields when only title changes', async () => {
    const wrapper = mountForm()
    const inputs = wrapper.findAll('input[type="text"]')
    await inputs[1].setValue('Solo título')
    const emitted = wrapper.emitted('update:modelValue')
    const last = emitted[emitted.length - 1][0]
    expect(last.intro).toBe('Texto introductorio.')
    expect(last.title).toBe('Solo título')
  })

  it('does not throw when modelValue.includes is undefined', () => {
    const model = { ...baseModel(), includes: undefined, classificationRows: undefined }
    expect(() => mountForm(model)).not.toThrow()
  })
})
