import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'

import BaseAlert from '../../components/base/BaseAlert.vue'
import BaseBadge from '../../components/base/BaseBadge.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'
import FinancingProgramView from '../../components/Financing/ProgramView.vue'

enableAutoUnmount(afterEach)


global.useI18n = jest.fn(() => ({
  t: (key, params = {}) => `${key}${params.count ? `:${params.count}` : ''}${params.title ? `:${params.title}` : ''}`,
}))

const program = {
  hero: {
    eyebrow: 'Financiación de largo plazo',
    title: 'Construimos hoy',
    subtitle: 'Compartimos el riesgo del producto.',
    trust_note: 'Una oportunidad se convierte en producto.',
  },
  eligibility: {
    badge: 'Aprobación previa',
    title: 'Sujeto a evaluación',
    summary: 'La propuesta define el saldo aprobado.',
  },
  options: [
    {
      id: 'five-year', name: 'Alianza a 5 años', badge: 'Recomendada',
      summary: 'Incluye continuidad y capacidad mensual.', exclusivity_years: 5,
      recommended: true, hour_package_included: true, financing_cycles: 2,
      highlights: ['Hasta dos ciclos de financiación'],
    },
    {
      id: 'three-year', name: 'Alianza a 3 años', badge: 'Alternativa',
      summary: 'Conserva financiación sin paquete.', exclusivity_years: 3,
      recommended: false, hour_package_included: false, financing_cycles: 1,
      highlights: ['Requerimientos cotizados aparte'],
    },
  ],
  conditions: [
    {
      id: 'financing', number: '01', icon: '↗', title: '12 meses',
      summary: 'Financia el saldo aprobado.', commercial_reason: 'Libera capital inicial.',
      highlights: ['Interés ordinario 0%'],
    },
    {
      id: 'exclusivity', number: '02', icon: '◇', title: 'Exclusividad',
      summary: 'Una sola casa desarrolladora.', commercial_reason: 'Protege el contexto.',
      highlights: ['Custodia segura'],
    },
    {
      id: 'calculator', number: '03', icon: '◎', title: 'Calculadora',
      summary: 'Anticipa esfuerzo.', commercial_reason: 'Hace visible el rango.',
      highlights: ['Resultado orientativo'],
    },
    {
      id: 'requirement-package', number: '04', icon: '◷', title: 'Cupos mensuales',
      summary: 'Capacidad mensual por talla.', commercial_reason: 'Mantiene la evolución.',
      highlights: ['No acumula cupos'],
    },
    {
      id: 'payment-discipline', number: '05', icon: '%', title: 'Pagos claros',
      summary: 'Las cuotas vencen en los primeros cinco días.', commercial_reason: 'Cubre el riesgo.',
      highlights: ['Cada mora aumenta 2% el Hosting vigente'],
    },
  ],
  calculator: {
    eyebrow: 'Transparencia',
    title: 'De una necesidad a un rango',
    summary: 'Recibe lenguaje natural.',
    input: { title: 'Qué se ingresa', items: ['Descripción del cambio'] },
    output: { title: 'Qué se obtiene', items: ['Esfuerzo, tiempo y precio'] },
    disclaimer: 'La cotización formal prevalece.',
  },
  package: {
    name: 'Paquete Pro', xs_count: 4, s_count: 2, m_count: 1, included_label: 'Incluido',
    title: 'Capacidad mensual', summary: 'Para requerimientos acotados.',
    renewal_label: 'Se renueva cada mes', rollover_label: 'Los cupos no se acumulan',
    availability_label: 'Desde producción',
  },
  legal_terms: [
    {
      id: 'approval', title: 'Saldo aprobado', summary: 'Requiere evaluación.',
      items: ['Sólo cubre fases aprobadas.'],
    },
  ],
  cta: {
    eyebrow: 'Conversemos', title: 'Solicita una evaluación',
    body: 'Cuéntanos sobre el producto.', button: 'Hablar por WhatsApp',
    whatsapp_url: 'https://wa.me/573238122373?text=financing',
  },
  disclaimer: 'Información comercial de referencia.',
}

function mountProgram(props = {}) {
  return mount(FinancingProgramView, {
    props: {
      program,
      downloadUrl: '/api/financing/public/pdf/?lang=es',
      language: 'es',
      ...props,
    },
    global: {
      components: { BaseAlert, BaseBadge, BaseSegmented },
      stubs: {
        Teleport: true,
        NuxtLink: { template: '<a><slot /></a>' },
        FinancingOnboarding: {
          template: '<div data-testid="financing-onboarding-stub" />',
          methods: { start() {}, forceStart() {} },
        },
        ExplainerVideoCard: {
          props: ['video', 'variant', 'testId'],
          template: '<div :data-testid="`${testId}-card`" :data-variant="variant" :data-video-id="video.id" :data-language="video.language" />',
        },
      },
    },
  })
}

describe('FinancingProgramView', () => {
  beforeEach(() => {
    window.localStorage.clear()
    global.fetch = jest.fn()
    URL.createObjectURL = jest.fn(() => 'blob:financing')
    URL.revokeObjectURL = jest.fn()
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: jest.fn().mockResolvedValue(undefined) },
    })
    Object.defineProperty(navigator, 'share', {
      configurable: true,
      value: undefined,
    })
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('renders both partnership options', () => {
    const wrapper = mountProgram()

    expect(wrapper.get('[data-testid="financing-option-five-year"]').text()).toContain('Alianza a 5 años')
    expect(wrapper.get('[data-testid="financing-option-three-year"]').text()).toContain('Alianza a 3 años')
  })

  it('renders the calculator input and output', () => {
    const wrapper = mountProgram()

    const calculator = wrapper.get('[data-testid="financing-calculator-input-output"]')
    expect(calculator.text()).toContain('Descripción del cambio')
    expect(calculator.text()).toContain('Esfuerzo, tiempo y precio')
  })

  it('renders the late-payment Hosting consequence', () => {
    const wrapper = mountProgram()

    expect(wrapper.get('[data-testid="financing-condition-payment-discipline"]').text())
      .toContain('Cada mora aumenta 2% el Hosting vigente')
  })

  it('renders the second-cycle benefit in the recommended option', () => {
    const wrapper = mountProgram()

    expect(wrapper.get('[data-testid="financing-option-five-year"]').text())
      .toContain('Hasta dos ciclos de financiación')
  })

  // Falla si la Alianza vuelve a prometer horas o pierde la combinación mensual de tallas.
  it('shows the five-year monthly allowance with renewal and no rollover', () => {
    const wrapper = mountProgram()

    expect(wrapper.get('[data-testid="financing-package-facts"]').text())
      .toBe('financing.packageFactsSe renueva cada mesLos cupos no se acumulanDesde producción')
    expect(wrapper.get('[data-testid="financing-package-facts"]').element.parentElement.textContent)
      .toContain('4 XS · 2 S · 1 M')
  })

  // Falla si la opción de tres años comunica que incluye el beneficio exclusivo de la alianza de cinco años.
  it('keeps the three-year option outside the monthly allowance benefit', () => {
    const wrapper = mountProgram()

    expect(wrapper.get('[data-testid="financing-option-three-year"]').text())
      .toContain('financing.packageNotIncluded')
  })

  it('reveals an agreement rule from its accordion', async () => {
    const wrapper = mountProgram()
    const trigger = wrapper.get('[data-testid="financing-term-trigger-approval"]')

    await trigger.trigger('click')

    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('[data-testid="financing-term-approval"]').text()).toContain('Sólo cubre fases aprobadas.')
  })

  it('emits the requested language', async () => {
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="financing-language-en"]').trigger('click')

    expect(wrapper.emitted('change-language')).toEqual([['en']])
  })

  it('shows a visible error when the PDF request fails', async () => {
    global.fetch.mockRejectedValue(new Error('offline'))
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="financing-download-pdf"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('financing.pdfError')
  })

  it('copies the current URL when native sharing is unavailable', async () => {
    window.history.replaceState({}, '', '/es-co/partnership-program')
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="financing-share"]').trigger('click')
    await wrapper.get('[data-testid="financing-copy-link"]').trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost/es-co/partnership-program')
  })

  it('shows a visible error when clipboard sharing fails', async () => {
    navigator.clipboard.writeText.mockRejectedValue(new Error('blocked'))
    const wrapper = mountProgram()

    await wrapper.get('[data-testid="financing-share"]').trigger('click')
    await wrapper.get('[data-testid="financing-copy-link"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('financing.copyFailed')
  })
})

describe('FinancingProgramView explainer video', () => {
  it('shows the Spanish explainer inside the hero, before the actions', () => {
    const wrapper = mountProgram({ language: 'es' })

    const card = wrapper.get('[data-testid="financing-explainer-card"]')
    expect(card.attributes('data-variant')).toBe('hero')
    expect(card.attributes('data-video-id')).toBe('financing')
    expect(card.attributes('data-language')).toBe('es')

    const heading = wrapper.get('h1').element
    const whatsapp = wrapper.get('[data-testid="financing-whatsapp-hero"]').element
    expect(heading.compareDocumentPosition(card.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(card.element.compareDocumentPosition(whatsapp) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('lets the panel preview disable the explainer', () => {
    const wrapper = mountProgram({ language: 'es', showExplainer: false })

    expect(wrapper.find('[data-testid="financing-explainer-card"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="financing-option-five-year"]').exists()).toBe(true)
  })

  it('hides the explainer while no English render exists', () => {
    const wrapper = mountProgram({ language: 'en' })

    expect(wrapper.get('h1').text()).toContain('Construimos hoy')
    expect(wrapper.find('[data-testid="financing-explainer-card"]').exists()).toBe(false)
  })

  it('hides the Spanish explainer when the panel switch turns it off', () => {
    const wrapper = mountProgram({
      language: 'es',
      program: { ...program, show_explainer_video: false },
    })

    expect(wrapper.find('[data-testid="financing-explainer-card"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="financing-whatsapp-hero"]').exists()).toBe(true)
  })
})

describe('FinancingProgramView PDF filename', () => {
  beforeEach(() => {
    URL.createObjectURL = jest.fn(() => 'blob:financing')
    URL.revokeObjectURL = jest.fn()
  })

  it.each([
    ['es', 'programa-de-alianza.pdf'],
    ['en', 'partnership-program.pdf'],
  ])('names the %s download after the Partnership Program when the server omits it', async (language, filename) => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => '' },
      blob: jest.fn().mockResolvedValue(new Blob(['%PDF'])),
    })
    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountProgram({ language })

    await wrapper.get('[data-testid="financing-download-pdf"]').trigger('click')
    await flushPromises()

    expect(clickSpy.mock.instances[0].download).toBe(filename)
    clickSpy.mockRestore()
  })
})

describe('FinancingProgramView guided tour', () => {
  it('mounts the tour and its restart control on the public view', () => {
    const wrapper = mountProgram({ language: 'es' })

    expect(wrapper.find('[data-testid="financing-onboarding-stub"]').exists()).toBe(true)
    const restart = wrapper.get('[data-testid="financing-guide-restart"]')
    expect(restart.attributes('aria-label')).toBe('financing.restartGuide')
    expect(restart.classes()).toContain('financing-restart-guide')
  })

  it('leaves the tour out of the panel preview', () => {
    const wrapper = mountProgram({ language: 'es', floatingActions: false })

    expect(wrapper.find('[data-testid="financing-onboarding-stub"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="financing-guide-restart"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="financing-option-five-year"]').exists()).toBe(true)
  })

  it('marks the tour targets on the conditions index and the rules list', () => {
    const wrapper = mountProgram({ language: 'es' })

    expect(wrapper.get('[data-testid="financing-term-approval"]').text()).toContain('Saldo aprobado')
    expect(wrapper.get('[data-testid="financing-term-trigger-approval"]').attributes('aria-controls'))
      .toBe('financing-term-panel-approval')
  })
})
