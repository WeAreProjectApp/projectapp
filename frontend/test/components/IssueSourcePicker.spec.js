import { mount } from '@vue/test-utils'
import IssueSourcePicker from '../../components/platform/issues/IssueSourcePicker.vue'

const requirements = [
  { id: 41, title: 'RequerimientoExtremoSinEspacios'.padEnd(300, 'X'), contract_title: 'Alcance vigente', stage_title: 'Etapa 1: revisión del cliente' },
  { id: 42, title: 'Segundo requerimiento de la misma etapa', contract_title: 'Alcance vigente', stage_title: 'Etapa 1: revisión del cliente' },
]
const wrappers = []
let originalUseI18n

function renderPicker(props = {}) {
  const wrapper = mount(IssueSourcePicker, {
    props: { id: 'bug-source', options: requirements, ...props },
  })
  wrappers.push(wrapper)
  return wrapper
}

describe('IssueSourcePicker', () => {
  beforeEach(() => {
    originalUseI18n = global.useI18n
    global.useI18n = () => ({ t: (key) => key })
  })

  afterEach(() => {
    wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    global.useI18n = originalUseI18n
  })

  it('shows the complete preselected requirement below the closed control', () => {
    const wrapper = renderPicker({ modelValue: 41 })

    expect(wrapper.get('[data-testid="issue-source-title"]').text()).toBe(requirements[0].title)
    expect(wrapper.get('[data-testid="issue-source-selection"]').text()).toContain(requirements[0].stage_title)
    expect(wrapper.get('[data-testid="issue-source"]').attributes('aria-describedby')).toBe('bug-source-selection')
  })

  it('starts each choice with the requirement name', () => {
    const wrapper = renderPicker()

    expect(wrapper.get('option[value="41"]').text()).toBe(
      `${requirements[0].title} · ${requirements[0].contract_title} · ${requirements[0].stage_title}`,
    )
  })

  it('reports the numeric identifier when a different requirement is chosen', async () => {
    const wrapper = renderPicker({ modelValue: 41 })

    await wrapper.get('[data-testid="issue-source"]').setValue('42')

    expect(wrapper.emitted('update:modelValue')).toEqual([[42]])
  })

  it('replaces the summary after the selected requirement changes', async () => {
    const wrapper = renderPicker({ modelValue: 41 })

    await wrapper.setProps({ modelValue: 42 })

    expect(wrapper.get('[data-testid="issue-source-title"]').text()).toBe(requirements[1].title)
  })

  it('clears the summary when the optional source is reset', async () => {
    const wrapper = renderPicker({ modelValue: 41 })

    await wrapper.get('[data-testid="issue-source"]').setValue('')
    await wrapper.setProps({ modelValue: null })

    expect(wrapper.emitted('update:modelValue')).toEqual([[null]])
    expect(wrapper.find('[data-testid="issue-source-selection"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="issue-source"]').attributes('aria-describedby')).toBeUndefined()
  })

  it('resolves a preselection after the requirements arrive', async () => {
    const wrapper = renderPicker({ modelValue: 41, options: [] })

    await wrapper.setProps({ options: requirements })

    expect(wrapper.get('[data-testid="issue-source-title"]').text()).toBe(requirements[0].title)
  })

  it('removes an obsolete summary when its requirement is no longer available', async () => {
    const wrapper = renderPicker({ modelValue: 41, required: true })

    await wrapper.setProps({ options: [requirements[1]] })

    expect(wrapper.find('[data-testid="issue-source-selection"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="issue-source"]').attributes('required')).toBeDefined()
  })
})
