import { enableAutoUnmount, mount } from '@vue/test-utils'
import BagEstimator from '../../components/BuildingOnDemand/BagEstimator.vue'
import messages from '../../locales/buildingOnDemand/es'
import englishMessages from '../../locales/buildingOnDemand/en'
import { createBuildingOnDemandProgram } from '../utils/buildingOnDemandFixture'

enableAutoUnmount(afterEach)
const originalI18n = global.useI18n

function mountEstimator(overrides = {}) {
  return mount(BagEstimator, {
    props: { program: createBuildingOnDemandProgram(), ...overrides },
    global: { stubs: { NuxtLink: true } },
  })
}

async function addTask(wrapper, taskId, quantity = 1) {
  for (let index = 0; index < quantity; index += 1) {
    await wrapper.get(`[data-testid="building-on-demand-task-${taskId}-increase"]`).trigger('click')
  }
}

describe('BuildingOnDemandBagEstimator', () => {
  beforeEach(() => {
    global.useI18n = () => ({
      t: (key, params = {}, options = {}) => {
        const copy = options.locale === 'en-us' ? englishMessages : messages
        return Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), copy[key.split('.').pop()] || key)
      },
    })
  })
  afterAll(() => { global.useI18n = originalI18n })

  it('asks for a task selection before suggesting a tier', () => {
    const wrapper = mountEstimator()

    expect(wrapper.text()).toContain('Elige las tareas que tienes en mente para saber cómo encajan en tu bolsa.')
    expect(wrapper.text()).toContain('XS · 2–7 h')
    expect(wrapper.text()).toContain('Estas horas son una referencia.')
    expect(wrapper.find('[data-testid="building-on-demand-estimate-whatsapp"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').text()).toBe('0')
  })

  it('recalculates the range when a task quantity increases', async () => {
    const wrapper = mountEstimator()

    await addTask(wrapper, 'small-change')

    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').text()).toBe('1')
    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').attributes('aria-live')).toBe('polite')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-range"]').text()).toBe('Entre 2 y 7 horas al mes')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-tier-starter"]').text()).toContain('Cabe')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain('Starter')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain('Por el tiempo estimado de tu solicitud.')
  })

  it('returns to the empty estimate when the final task is removed', async () => {
    const wrapper = mountEstimator()
    await addTask(wrapper, 'small-change')

    await wrapper.get('[data-testid="building-on-demand-task-small-change-decrease"]').trigger('click')

    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').text()).toBe('0')
    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-decrease"]').attributes('disabled')).toBe('')
    expect(wrapper.text()).toContain('Elige las tareas que tienes en mente para saber cómo encajan en tu bolsa.')
    expect(wrapper.find('[data-testid="building-on-demand-estimate-range"]').exists()).toBe(false)
  })

  it('caps a task quantity at ten units', async () => {
    const wrapper = mountEstimator()

    await addTask(wrapper, 'small-change', 11)

    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').text()).toBe('10')
    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-increase"]').attributes('disabled')).toBe('')
    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-increase"]').attributes('title')).toBe('La cantidad máxima es diez.')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-range"]').text()).toBe('Entre 20 y 70 horas al mes')
  })

  it('limits the request description to one thousand characters', async () => {
    const wrapper = mountEstimator()
    const textarea = wrapper.get('[data-testid="building-on-demand-estimator-description"]')

    await textarea.setValue('a'.repeat(1001))

    expect(textarea.element.value).toHaveLength(1000)
    expect(textarea.attributes('maxlength')).toBe('1000')
    expect(wrapper.text()).toContain('1000/1000')
  })

  it('suggests Business for a task that needs its roles', async () => {
    const wrapper = mountEstimator()

    await addTask(wrapper, 'requirements-session')

    expect(wrapper.get('[data-testid="building-on-demand-estimate-range"]').text()).toBe('Entre 7 y 20 horas al mes')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-tier-starter"]').text()).toContain('Requiere los roles de Business o un nivel superior.')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain('Business')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain('Por los roles que necesita tu solicitud.')
  })

  it.each([
    ['feature', 4, 'starter', 'Puede caber', 'Enterprise'],
    ['large-feature', 2, 'starter', 'No cabe en un mes', 'Business'],
    ['large-feature', 4, 'enterprise', 'Puede caber', 'Enterprise'],
  ])('classifies %s at quantity %i against a monthly bag', async (taskId, quantity, tierId, status, suggested) => {
    const wrapper = mountEstimator()

    await addTask(wrapper, taskId, quantity)

    expect(wrapper.get(`[data-testid="building-on-demand-estimate-tier-${tierId}"]`).text()).toContain(status)
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain(suggested)
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain('Por el tiempo estimado de tu solicitud.')
  })

  it('explains the months needed when the highest tier is exceeded', async () => {
    const wrapper = mountEstimator()

    await addTask(wrapper, 'large-feature', 6)

    expect(wrapper.get('[data-testid="building-on-demand-estimate-range"]').text()).toBe('Entre 330 y 540 horas al mes')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-tier-enterprise"]').text()).toContain('No cabe en un mes')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-tier-enterprise"]').text()).toContain('≈ 2 meses')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain('El alcance supera una bolsa mensual; requiere aproximadamente 2 meses.')
  })

  it('adds the hour ranges of distinct selected tasks', async () => {
    const wrapper = mountEstimator()

    await addTask(wrapper, 'small-change', 2)
    await addTask(wrapper, 'feature')

    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-range"]').text()).toBe('Entre 24 y 64 horas al mes')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-suggested"]').text()).toContain('Starter')
  })

  it('sends the visible estimate to WhatsApp for formal review', async () => {
    const wrapper = mountEstimator()

    await wrapper.get('[data-testid="building-on-demand-estimator-description"]').setValue('Mejorar el formulario de contacto')
    await addTask(wrapper, 'small-change', 2)
    const destination = new URL(wrapper.get('[data-testid="building-on-demand-estimate-whatsapp"]').attributes('href'))

    expect(destination.origin).toBe('https://wa.me')
    expect(destination.searchParams.get('text')).toBe('Pedir la estimación formal — Building on Demand\nMejorar el formulario de contacto\n2 × Cambio pequeño\nEntre 4 y 14 horas al mes\nNivel sugerido: Starter')
  })

  it('replaces an unsafe contact URL in the formal estimate link', async () => {
    const program = createBuildingOnDemandProgram()
    program.contact.whatsapp_base_url = 'https://example.com/phishing'
    const wrapper = mountEstimator({ program })

    await addTask(wrapper, 'small-change')
    const destination = new URL(wrapper.get('[data-testid="building-on-demand-estimate-whatsapp"]').attributes('href'))

    expect(destination.origin).toBe('https://wa.me')
    expect(destination.pathname).toBe('/573238122373')
    expect(destination.searchParams.get('text')).toContain('Entre 2 y 7 horas al mes')
  })

  it('uses English estimator chrome in an English preview', async () => {
    const wrapper = mountEstimator({ program: createBuildingOnDemandProgram('en'), language: 'en' })

    await addTask(wrapper, 'small-change')

    expect(wrapper.get('[data-testid="building-on-demand-estimate-range"]').text()).toBe('Between 2 and 7 hours per month')
    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-increase"]').attributes('aria-label')).toBe('Add one unit of Small change')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-whatsapp"]').text()).toBe('Request a formal estimate')
  })

  it('preserves selected quantities while the preview language changes', async () => {
    const wrapper = mountEstimator()
    await addTask(wrapper, 'small-change', 2)

    await wrapper.setProps({ program: createBuildingOnDemandProgram('en'), language: 'en' })

    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="building-on-demand-estimate-range"]').text()).toBe('Between 4 and 14 hours per month')
    expect(new URL(wrapper.get('[data-testid="building-on-demand-estimate-whatsapp"]').attributes('href')).searchParams.get('text')).toContain('2 × Small change')
  })

  it('ignores task references to unknown sizes or tiers', () => {
    const program = createBuildingOnDemandProgram()
    program.estimator.tasks[0].size = 'unknown-size'
    program.estimator.tasks[1].min_tier = 'unknown-tier'
    const wrapper = mountEstimator({ program })

    expect(wrapper.findAll('[data-testid$="-increase"]')).toHaveLength(7)
    expect(wrapper.find('[data-testid="building-on-demand-task-requirements-session-increase"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="building-on-demand-task-screen-design-increase"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="building-on-demand-task-small-change-quantity"]').text()).toBe('0')
  })

  it('keeps the empty state readable when tasks are absent', () => {
    const program = createBuildingOnDemandProgram()
    delete program.estimator.tasks
    const wrapper = mountEstimator({ program })

    expect(wrapper.text()).toContain('¿Cabe en tu bolsa?')
    expect(wrapper.text()).toContain('Elige las tareas que tienes en mente para saber cómo encajan en tu bolsa.')
    expect(wrapper.findAll('[data-testid$="-increase"]')).toHaveLength(0)
  })
})
