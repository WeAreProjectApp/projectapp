import { enableAutoUnmount, mount } from '@vue/test-utils'
import TierCard from '../../components/BuildingOnDemand/TierCard.vue'
import TermSelector from '../../components/BuildingOnDemand/TermSelector.vue'
import messages from '../../locales/buildingOnDemand/es'
import englishMessages from '../../locales/buildingOnDemand/en'
import { createBuildingOnDemandProgram } from '../utils/buildingOnDemandFixture'

enableAutoUnmount(afterEach)
const originalI18n = global.useI18n

function mountTier(tierId = 'starter', overrides = {}, language = 'es') {
  const program = createBuildingOnDemandProgram(language)
  return mount(TierCard, {
    props: {
      tier: program.tiers.items.find(tier => tier.id === tierId),
      term: program.terms.items[0],
      offer: program.offer,
      whatsappBaseUrl: program.contact.whatsapp_base_url,
      language,
      ...overrides,
    },
    global: { stubs: { NuxtLink: true } },
  })
}

function mountTerms(overrides = {}) {
  return mount(TermSelector, {
    props: { terms: createBuildingOnDemandProgram().terms, ...overrides },
  })
}

describe('BuildingOnDemandTierCard', () => {
  beforeEach(() => {
    global.useI18n = () => ({
      t: (key, params = {}, options = {}) => {
        const copy = options.locale === 'en-us' ? englishMessages : messages
        return Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), copy[key.split('.').pop()] || key)
      },
    })
  })
  afterAll(() => { global.useI18n = originalI18n })

  it.each([
    ['business', 'true', 'Recomendado', '192 horas al mes'],
    ['starter', 'false', 'Para empezar', '96 horas al mes'],
  ])('identifies the recommendation on the %s card', (tierId, recommended, badge, bag) => {
    const wrapper = mountTier(tierId)

    expect(wrapper.get(`[data-testid="building-on-demand-tier-${tierId}"]`).attributes('data-recommended')).toBe(recommended)
    expect(wrapper.text()).toContain(badge)
    expect(wrapper.text()).toContain(bag)
  })

  it.each([
    ['quarterly', '$1.710.000 COP', '$5.130.000 COP', '5 % de descuento', '$270.000 COP'],
    ['semiannual', '$1.620.000 COP', '$9.720.000 COP', '10 % de descuento', '$1.080.000 COP'],
    ['nine-month', '$1.530.000 COP', '$13.770.000 COP', '15 % de descuento', '$2.430.000 COP'],
  ])('shows the backend prices for the %s term', (termId, monthly, total, discount, savings) => {
    const program = createBuildingOnDemandProgram()
    const wrapper = mountTier('starter', { term: program.terms.items.find(term => term.id === termId) })

    expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toContain(monthly)
    expect(wrapper.get('[data-testid="building-on-demand-total-starter"]').text()).toContain(total)
    expect(wrapper.text()).toContain(discount)
    expect(wrapper.text()).toContain(savings)
  })

  it('reads changed term amounts directly from the payload', () => {
    const program = createBuildingOnDemandProgram()
    const tier = program.tiers.items[0]
    Object.assign(tier.prices[1], { monthly_price: 1710111, total: 5130333, savings: 269667 })
    const wrapper = mountTier('starter', { tier, term: program.terms.items[1] })

    expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toContain('$1.710.111 COP')
    expect(wrapper.get('[data-testid="building-on-demand-total-starter"]').text()).toContain('$5.130.333 COP')
    expect(wrapper.text()).toContain('$269.667 COP')
  })

  it('presents the monthly bag without an hourly price', () => {
    const wrapper = mountTier()

    expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toMatch(/^\$1\.800\.000 COP\s*\/ mes\s*\+ IVA$/)
    expect(wrapper.text()).toContain('4 h diarias · 6 días a la semana')
    expect(wrapper.text()).toContain('Se reanuda cada mes · no se acumula · no se transfiere')
    expect(wrapper.text()).toContain('QA en cada entrega')
    expect(wrapper.text()).toContain('Servidor VPS · 4 GB de RAM')
    expect(wrapper.find('[data-testid="building-on-demand-total-starter"]').exists()).toBe(false)
    expect(wrapper.text()).not.toMatch(/por hora|per hour|COP\s*\/\s*h\b/i)
  })

  it('omits the VAT suffix for tax-inclusive prices', () => {
    const program = createBuildingOnDemandProgram()
    program.offer.prices_include_vat = true
    const wrapper = mountTier('starter', { offer: program.offer })

    expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toMatch(/^\$1\.800\.000 COP\s*\/ mes$/)
  })

  it('includes the selected term in the WhatsApp inquiry', () => {
    const program = createBuildingOnDemandProgram()
    const wrapper = mountTier('business', { term: program.terms.items[1] })
    const link = wrapper.get('[data-testid="building-on-demand-tier-cta-business"]')

    expect(new URL(link.attributes('href')).searchParams.get('text')).toBe('Hola, quiero el plan Business de Building on Demand (3 meses)')
    expect(link.text()).toBe('Quiero Business')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
  })

  it('localizes preview labels using the language prop', () => {
    const wrapper = mountTier('business', {}, 'en')
    const link = wrapper.get('[data-testid="building-on-demand-tier-cta-business"]')

    expect(wrapper.get('[data-testid="building-on-demand-price-business"]').text()).toMatch(/^\$4\.200\.000 COP\s*\/ month\s*\+ VAT$/)
    expect(wrapper.text()).toContain('192 hours per month')
    expect(new URL(link.attributes('href')).searchParams.get('text')).toBe('Hello, I want the Business plan from Building on Demand (Monthly)')
  })

  it('replaces an unsafe WhatsApp destination', () => {
    const wrapper = mountTier('starter', { whatsappBaseUrl: 'javascript:alert(1)' })
    const destination = new URL(wrapper.get('[data-testid="building-on-demand-tier-cta-starter"]').attributes('href'))

    expect(destination.origin).toBe('https://wa.me')
    expect(destination.pathname).toBe('/573238122373')
    expect(destination.searchParams.get('text')).toBe('Hola, quiero el plan Starter de Building on Demand (Mensual)')
  })

  it('offers a pricing inquiry when price entries are absent', () => {
    const program = createBuildingOnDemandProgram()
    program.tiers.items[0].prices = []
    const wrapper = mountTier('starter', { tier: program.tiers.items[0] })

    expect(wrapper.text()).toContain('Consulta el precio de este nivel')
    expect(wrapper.get('[data-testid="building-on-demand-tier-cta-starter"]').text()).toBe('Quiero Starter')
    expect(wrapper.find('[data-testid="building-on-demand-price-starter"]').exists()).toBe(false)
  })

  it('keeps the bag visible if server details are absent', () => {
    const program = createBuildingOnDemandProgram()
    delete program.tiers.items[0].server
    const wrapper = mountTier('starter', { tier: program.tiers.items[0] })

    expect(wrapper.text()).toContain('96 horas al mes')
    expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toContain('$1.800.000 COP')
    expect(wrapper.text()).not.toContain('Servidor VPS')
  })

  it('defaults a standalone card to the monthly inquiry', () => {
    const program = createBuildingOnDemandProgram()
    const wrapper = mount(TierCard, {
      props: { tier: program.tiers.items[0] },
      global: { stubs: { NuxtLink: true } },
    })
    const destination = new URL(wrapper.get('[data-testid="building-on-demand-tier-cta-starter"]').attributes('href'))

    expect(wrapper.get('[data-testid="building-on-demand-price-starter"]').text()).toMatch(/^\$1\.800\.000 COP\s*\/ mes$/)
    expect(destination.searchParams.get('text')).toBe('Hola, quiero el plan Starter de Building on Demand (Mensual)')
  })

  it('defaults the term selector to monthly billing', () => {
    const wrapper = mountTerms()

    expect(wrapper.get('[data-testid="building-on-demand-term-monthly"]').attributes('aria-selected')).toBe('true')
    expect(wrapper.get('[data-testid="building-on-demand-term-quarterly"]').text()).toBe('3 meses')
    expect(wrapper.text()).not.toContain('Aunque anticipes varios meses')
  })

  it('emits the term chosen by the visitor', async () => {
    const wrapper = mountTerms()

    await wrapper.get('[data-testid="building-on-demand-term-quarterly"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['quarterly']])
  })

  it.each(['quarterly', 'semiannual', 'nine-month'])('explains monthly bag renewal for the %s term', (termId) => {
    const wrapper = mountTerms({ modelValue: termId })

    expect(wrapper.get(`[data-testid="building-on-demand-term-${termId}"]`).attributes('aria-selected')).toBe('true')
    expect(wrapper.text()).toContain('Aunque anticipes varios meses, la bolsa se reanuda cada mes y no se acumula.')
  })
})
