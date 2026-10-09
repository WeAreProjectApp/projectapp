import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import BaseAlert from '../../components/base/BaseAlert.vue'
import BaseBadge from '../../components/base/BaseBadge.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'
import ProgramView from '../../components/BuildingWithUs/ProgramView.vue'
import messages from '../../locales/buildingWithUs/es'

enableAutoUnmount(afterEach)

const originalI18n = global.useI18n
const originalFetch = global.fetch
const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
const originalShare = Object.getOwnPropertyDescriptor(navigator, 'share')

function createProgram(overrides = {}) {
  return {
    language: 'es', version: 1, updated_at: '2026-10-09T00:00:00Z',
    canonical_path: '/es-co/building-with-us', alternate_path: '/en-us/building-with-us',
    pdf_path: '/api/building-with-us/public/pdf/?lang=es',
    seo: { title: 'Building with Us | Project App.', description: 'Incubamos productos con expertos de negocio.' },
    hero: {
      eyebrow: 'Alianza de producto', title: 'Construye con nosotros',
      subtitle: 'Construimos para ti.', note: 'La participación se gana con compromisos verificables.',
    },
    origin: {
      title: 'Partimos de un problema real', summary: 'Tu industria conoce la necesidad.',
      industries: ['Logística', 'Salud'], points: ['Impacto económico comprobable'],
    },
    contribution: {
      title: 'La cadena completa de producción', summary: 'ProjectApp lleva el producto hasta su operación.',
      items: [
        { id: 'requirements', title: 'Requerimientos', summary: 'Convertimos el problema en alcance verificable.' },
        { id: 'design', title: 'Diseño', summary: 'Prototipos que validamos con usuarios.' },
        { id: 'development', title: 'Desarrollo', summary: 'Construcción del producto.' },
        { id: 'quality', title: 'Calidad', summary: 'Pruebas del comportamiento acordado.' },
        { id: 'operations', title: 'Operación', summary: 'Publicación, infraestructura y continuidad.' },
      ],
    },
    expert_profile: {
      title: 'Un experto comprometido', summary: 'Experiencia y acceso al mercado.',
      items: [{ id: 'industry', title: 'Conocimiento de la industria', summary: 'Contacto directo con usuarios reales.' }],
    },
    participation_models: {
      title: 'Formas de participar', summary: 'Las cifras se pactan en privado.',
      items: [
        {
          id: 'monthly-investment', name: 'Inversión mensual', badge: 'Compromiso continuo',
          summary: 'Apoya la incubación durante el periodo acordado.', ideal_for: 'Expertos con capacidad de invertir.',
          expert_contributes: ['Experiencia de negocio', 'Inversión mensual acordada'],
          projectapp_contributes: ['Diseño y desarrollo', 'Infraestructura y operación'],
        },
        {
          id: 'shared-investment', name: 'Inversión compartida', badge: 'Aportes complementarios',
          summary: 'Cada parte asume compromisos definidos.', ideal_for: 'Equipos que comparten recursos.',
          expert_contributes: ['Acceso al mercado'], projectapp_contributes: ['Capacidad de producción'],
        },
        {
          id: 'expert-dedication', name: 'Dedicación del experto', badge: 'Experiencia aplicada',
          summary: 'La dedicación se demuestra con resultados.', ideal_for: 'Expertos disponibles para validar el producto.',
          expert_contributes: ['Validación con usuarios'], projectapp_contributes: ['Construcción del producto'],
        },
      ],
    },
    incubation_periods: {
      title: 'Tiempo para incubar', summary: 'El horizonte depende del alcance.',
      items: [
        { id: 'three-months', months: 3, title: 'Tres meses', summary: 'Validación inicial.' },
        { id: 'six-months', months: 6, title: 'Seis meses', summary: 'Primera versión utilizable.' },
        { id: 'nine-months', months: 9, title: 'Nueve meses', summary: 'Evolución con usuarios.' },
        { id: 'twelve-months', months: 12, title: 'Doce meses', summary: 'Consolidación del producto.' },
      ],
    },
    scope: {
      title: 'Un alcance definido', summary: 'Acordamos qué incluye la incubación.',
      items: [{ id: 'deliverables', title: 'Entregables verificables', summary: 'Cada entrega tiene criterios de aceptación.' }],
    },
    milestones: {
      title: 'Participación ganada por hitos', summary: 'Los resultados hacen visible el compromiso.',
      items: [{ id: 'validation', title: 'Validación del problema', summary: 'Evidencia de usuarios de la industria.' }],
      note: 'La participación no se obtiene automáticamente por el paso del tiempo.',
    },
    agreement: {
      title: 'Reglas del contrato', summary: 'La alianza se formaliza antes de construir.',
      items: [{ id: 'intellectual-property', title: 'Propiedad intelectual', summary: 'Titularidad y uso quedan pactados.' }],
    },
    process: {
      title: 'Cómo comenzamos',
      items: [{ id: 'conversation', title: 'Conversemos', summary: 'Presenta el problema y su impacto económico.' }],
    },
    faq: {
      title: 'Preguntas frecuentes',
      items: [{ id: 'participation', question: '¿Cuándo se gana la participación?', answer: 'Al cumplir los hitos pactados y demostrar los resultados.' }],
    },
    cta: {
      title: 'Hablemos de tu industria', body: 'Cuéntanos el problema que quieres resolver.',
      button_label: 'Hablar por WhatsApp', whatsapp_url: 'https://wa.me/573238122373?text=Building',
    },
    legal: { disclaimer: 'La propuesta y el contrato definen las condiciones de cada alianza.' },
    ...overrides,
  }
}

function mountProgram(props = {}) {
  return mount(ProgramView, {
    props: { program: createProgram(), downloadUrl: '/api/building-with-us/public/pdf/?lang=es', ...props },
    global: {
      components: { BaseAlert, BaseBadge, BaseSegmented },
      stubs: {
        Teleport: true,
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        BuildingWithUsOnboarding: {
          template: '<div data-testid="building-with-us-onboarding-stub" />',
          methods: { start() {}, forceStart() {} },
        },
      },
    },
  })
}

function mockPdf(disposition = '') {
  global.fetch.mockResolvedValue({
    ok: true, headers: { get: () => disposition },
    blob: jest.fn().mockResolvedValue(new Blob(['PDF'], { type: 'application/pdf' })),
  })
}

describe('BuildingWithUsProgramView', () => {
  beforeEach(() => {
    window.localStorage.clear()
    global.useI18n = () => ({ t: (key) => messages[key.split('.').pop()] || key })
    global.fetch = jest.fn()
    URL.createObjectURL = jest.fn(() => 'blob:building-with-us')
    URL.revokeObjectURL = jest.fn()
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: jest.fn().mockResolvedValue(undefined) } })
    Object.defineProperty(navigator, 'share', { configurable: true, value: undefined })
  })

  afterEach(() => {
    jest.restoreAllMocks()
    window.localStorage.clear()
    window.history.replaceState({}, '', '/')
  })

  afterAll(() => {
    global.useI18n = originalI18n
    global.fetch = originalFetch
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
    delete navigator.clipboard
    delete navigator.share
    if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard)
    if (originalShare) Object.defineProperty(navigator, 'share', originalShare)
  })

  it('renders the contributions of each party in a model', () => {
    const wrapper = mountProgram()

    const model = wrapper.get('[data-testid="building-with-us-model-monthly-investment"]')
    expect(model.text()).toContain('Aporta el experto')
    expect(model.text()).toContain('Experiencia de negocio')
    expect(model.text()).toContain('Aporta ProjectApp')
    expect(model.text()).toContain('Diseño y desarrollo')
  })

  it.each([
    ['origin', 'Partimos de un problema real', 'Impacto económico comprobable'],
    ['contribution', 'La cadena completa de producción', 'Publicación, infraestructura y continuidad.'],
    ['expert', 'Un experto comprometido', 'Contacto directo con usuarios reales.'],
    ['scope', 'Un alcance definido', 'Cada entrega tiene criterios de aceptación.'],
    ['milestones', 'Participación ganada por hitos', 'La participación no se obtiene automáticamente por el paso del tiempo.'],
    ['agreement', 'Reglas del contrato', 'Titularidad y uso quedan pactados.'],
    ['process', 'Cómo comenzamos', 'Presenta el problema y su impacto económico.'],
  ])('renders the public content of %s', (section, title, detail) => {
    const wrapper = mountProgram()

    const content = wrapper.get(`[data-testid="building-with-us-${section}"]`)
    expect(content.text()).toContain(title)
    expect(content.text()).toContain(detail)
  })

  it('shows the incubation horizons', () => {
    const wrapper = mountProgram()

    const periods = wrapper.findAll('[data-testid^="building-with-us-period-"]')
    expect(periods.map((period) => period.get('p').text())).toEqual(['3', '6', '9', '12'])
  })

  it('omits a section without data', () => {
    const wrapper = mountProgram({ program: createProgram({ origin: undefined }) })

    expect(wrapper.find('[data-testid="building-with-us-origin"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="building-with-us-contribution"]').text()).toContain('La cadena completa de producción')
  })

  it('expands a FAQ answer', async () => {
    const wrapper = mountProgram()
    const trigger = wrapper.get('[data-testid="building-with-us-faq-trigger-0"]')

    await trigger.trigger('click')

    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('[data-testid="building-with-us-faq-panel-0"]').isVisible()).toBe(true)
    expect(wrapper.get('[data-testid="building-with-us-faq-panel-0"]').text()).toBe('Al cumplir los hitos pactados y demostrar los resultados.')
  })

  it('emits a requested language change', async () => {
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="building-with-us-language-en"]').trigger('click')

    expect(wrapper.emitted('change-language')).toEqual([['en']])
  })

  it('shows a PDF download error', async () => {
    global.fetch.mockRejectedValue(new Error('offline'))
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="building-with-us-download-pdf"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('No pudimos descargar el PDF. Vuelve a intentarlo.')
  })

  it.each(['es', 'en'])('uses the %s fallback PDF filename', async (language) => {
    mockPdf()
    let filename
    jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { filename = this.download })
    const wrapper = mountProgram({ language })

    await wrapper.get('[data-testid="building-with-us-download-pdf"]').trigger('click')
    await flushPromises()

    expect(filename).toBe(`building-with-us-${language}.pdf`)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:building-with-us')
  })

  it('uses the filename supplied by the PDF response', async () => {
    mockPdf('attachment; filename="alianza-producto.pdf"')
    let filename
    jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { filename = this.download })
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="building-with-us-download-pdf-floating"]').trigger('click')
    await flushPromises()

    expect(filename).toBe('alianza-producto.pdf')
  })

  it('replaces an unsafe WhatsApp destination', () => {
    const program = createProgram()
    program.cta.whatsapp_url = 'javascript:alert(1)'
    const wrapper = mountProgram({ program })

    expect(wrapper.get('[data-testid="building-with-us-whatsapp-cta"]').attributes('href')).toBe('https://wa.me/573238122373')
    expect(wrapper.get('[data-testid="building-with-us-whatsapp-hero"]').attributes('href')).toBe('https://wa.me/573238122373')
  })

  it('presents the program without a video element', () => {
    const wrapper = mountProgram()

    expect(wrapper.find('video').exists()).toBe(false)
    expect(wrapper.get('h1').text()).toBe('Construye con nosotros')
  })

  it('keeps the guide out of a panel preview', () => {
    const wrapper = mountProgram({ floatingActions: false })

    expect(wrapper.find('[data-testid="building-with-us-onboarding-stub"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="building-with-us-guide-restart"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="building-with-us-theme-toggle"]').attributes('aria-pressed')).toBe('false')
  })

  it('copies the public link through the sharing control', async () => {
    window.history.replaceState({}, '', '/es-co/building-with-us')
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="building-with-us-share"]').trigger('click')
    await wrapper.get('[data-testid="building-with-us-copy-link"]').trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost/es-co/building-with-us')
    expect(wrapper.text()).toContain('Enlace copiado')
  })
})
