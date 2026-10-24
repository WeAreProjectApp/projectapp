jest.mock('../../components/WebAppDiagnostic/public/SectionHeader.vue', () => ({
  name: 'SectionHeader',
  props: ['index', 'title', 'fallback'],
  template: '<div data-testid="section-header">{{ title }}</div>',
}))

import { mount } from '@vue/test-utils'
import RadiographySection from '../../components/WebAppDiagnostic/public/RadiographySection.vue'
import BaseRichTextContent from '../../components/base/BaseRichTextContent.vue'

function baseContent(overrides = {}) {
  return {
    index: '3',
    title: 'Radiografía del sistema',
    intro: '',
    includes: [],
    classificationRows: [],
    ...overrides,
  }
}

function mountSection(contentOverrides = {}, renderContext = {}) {
  return mount(RadiographySection, {
    props: { content: baseContent(contentOverrides), renderContext },
  })
}

describe('RadiographySection', () => {
  it('renders SectionHeader with the content title', () => {
    const wrapper = mountSection({ title: 'Análisis de sistema' })
    expect(wrapper.find('[data-testid="section-header"]').text()).toBe('Análisis de sistema')
  })

  it('renders intro content when content.intro is provided', () => {
    const wrapper = mountSection({ intro: 'Este diagnóstico evalúa la arquitectura.' })
    expect(wrapper.getComponent(BaseRichTextContent).text()).toBe('Este diagnóstico evalúa la arquitectura.')
  })

  it('hides intro content when content.intro is absent', () => {
    const wrapper = mountSection({ intro: '' })
    expect(wrapper.get('[data-testid="section-header"]').text()).toBe('Radiografía del sistema')
    expect(wrapper.findAllComponents(BaseRichTextContent)).toHaveLength(0)
  })

  it('renders includes list when content.includes has items', () => {
    const wrapper = mountSection({
      includes: [{ title: 'Seguridad', description: 'Análisis de vulnerabilidades' }],
    })
    expect(wrapper.find('ul').exists()).toBe(true)
    expect(wrapper.text()).toContain('Seguridad')
  })

  it('hides includes list when content.includes is empty', () => {
    const wrapper = mountSection({ includes: [] })
    expect(wrapper.find('ul').exists()).toBe(false)
  })

  it('hides includes list when content.includes is undefined', () => {
    const wrapper = mountSection({ includes: undefined })
    expect(wrapper.find('ul').exists()).toBe(false)
  })

  it('renders classification table when content.classificationRows has items', () => {
    const wrapper = mountSection({
      classificationRows: [{ dimension: 'Usuarios', small: '<100', medium: '100-1k', large: '>1k' }],
    })
    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.text()).toContain('Usuarios')
  })

  it('hides classification table when content.classificationRows is empty', () => {
    const wrapper = mountSection({ classificationRows: [] })
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('renders stack section when renderContext has stack_backend_name', () => {
    const wrapper = mountSection({}, { stack_backend_name: 'Django 5' })
    expect(wrapper.text()).toContain('Tecnología del servidor')
    expect(wrapper.text()).toContain('Django 5')
  })

  it('renders stack section when renderContext has stack_frontend_name', () => {
    const wrapper = mountSection({}, { stack_frontend_name: 'Vue 3' })
    expect(wrapper.text()).toContain('Tecnología de la interfaz')
    expect(wrapper.text()).toContain('Vue 3')
  })

  it('hides stack section when renderContext has neither stack name', () => {
    const wrapper = mountSection({}, {})
    expect(wrapper.text()).not.toContain('Tecnología del servidor')
  })

  it('hides stack section when renderContext is the default empty object', () => {
    const wrapper = mount(RadiographySection, { props: { content: baseContent() } })
    expect(wrapper.text()).not.toContain('Stack detectado')
  })
})
