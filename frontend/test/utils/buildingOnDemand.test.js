import {
  buildingOnDemandLanguage,
  buildingOnDemandPath,
  buildingOnDemandPublicUrl,
  buildingOnDemandPdfUrl,
  isBuildingOnDemandProgram,
  priceForTerm,
  estimateRequest,
  estimateWhatsappMessage,
  tierWhatsappUrl,
} from '../../utils/buildingOnDemand'
import { createBuildingOnDemandProgram } from './buildingOnDemandFixture'

const estimateProgram = (program, selection) => estimateRequest({
  tiers: program.tiers.items,
  sizes: program.estimator.sizes,
  tasks: program.estimator.tasks,
  selection,
})

describe('Building on Demand public utilities', () => {
  it.each([['en-us', 'en'], ['es-co', 'es']])('maps locale %s to API language %s', (locale, language) => {
    expect(buildingOnDemandLanguage(locale)).toBe(language)
  })

  it.each([
    ['es', '/es-co/building-on-demand'],
    ['en', '/en-us/building-on-demand'],
  ])('locates the %s public resources', (language, path) => {
    expect({
      path: buildingOnDemandPath(language),
      publicUrl: buildingOnDemandPublicUrl(language),
      pdfUrl: buildingOnDemandPdfUrl(language),
    }).toEqual({
      path,
      publicUrl: `https://projectapp.co${path}`,
      pdfUrl: `/api/building-on-demand/public/pdf/?lang=${language}`,
    })
  })

  it('uses Spanish for an unsupported PDF language', () => {
    expect(buildingOnDemandPdfUrl(undefined)).toBe('/api/building-on-demand/public/pdf/?lang=es')
  })

  it('accepts a usable public program', () => {
    const program = createBuildingOnDemandProgram()

    expect(isBuildingOnDemandProgram(program)).toBe(true)
  })

  it.each([
    ['an absent payload', () => null],
    ['an array payload', () => []],
    ['a blank hero', program => ({ ...program, hero: { title: '   ' } })],
    ['empty tiers', program => ({ ...program, tiers: { items: [] } })],
    ['a missing hour bag', program => ({ ...program, tiers: { items: [{ ...program.tiers.items[0], bag_hours: null }] } })],
    ['an invalid price', program => ({ ...program, tiers: { items: [{ ...program.tiers.items[0], prices: [{}] }] } })],
    ['empty terms', program => ({ ...program, terms: { items: [] } })],
    ['a nonboolean VAT flag', program => ({ ...program, offer: { ...program.offer, prices_include_vat: 'false' } })],
    ['a malformed estimator', program => ({ ...program, estimator: { sizes: [], tasks: {} } })],
  ])('rejects %s', (label, buildPayload) => {
    const payload = buildPayload(createBuildingOnDemandProgram())

    expect(isBuildingOnDemandProgram(payload)).toBe(false)
  })

  it('reads the selected term price supplied by the backend', () => {
    const tier = createBuildingOnDemandProgram().tiers.items[1]

    expect(priceForTerm(tier, 'nine-month')).toEqual({
      term: 'nine-month', months: 9, discount_percent: 20,
      monthly_price: 3360000, total: 30240000, savings: 7560000,
    })
  })

  it('uses the monthly price for an unknown term', () => {
    const tier = createBuildingOnDemandProgram().tiers.items[0]

    expect(priceForTerm(tier, 'unknown')).toBe(tier.prices[0])
  })

  it('uses the first supplied price when monthly is absent', () => {
    const tier = createBuildingOnDemandProgram().tiers.items[0]
    tier.prices = [tier.prices[1]]

    expect(priceForTerm(tier, 'unknown')).toBe(tier.prices[0])
  })

  it('returns no price when backend prices are absent', () => {
    // quality: allow-negation-only (null is the contract when no backend price exists; never synthesize a price)
    expect(priceForTerm(undefined)).toBeNull()
  })
})

describe('Building on Demand estimate calculation', () => {
  it('returns an empty result without selected tasks', () => {
    expect(estimateRequest()).toEqual({
      hoursMin: 0, hoursMax: 0, requiredTier: null, suggestedTier: null,
      tierResults: [], selectedTasks: [], hasSelection: false, suggestionReason: null,
    })
  })

  it('adds the size range for each selected quantity', () => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { component: 2, 'small-change': 3 })

    expect(result).toMatchObject({ hoursMin: 20, hoursMax: 61, hasSelection: true })
    expect(result.selectedTasks).toEqual([
      expect.objectContaining({ id: 'small-change', quantity: 3, hoursMin: 6, hoursMax: 21 }),
      expect.objectContaining({ id: 'component', quantity: 2, hoursMin: 14, hoursMax: 40 }),
    ])
  })

  it.each([
    ['feature', 1, 'fits'],
    ['feature', 2, 'may-fit'],
    ['large-feature', 2, 'exceeds'],
  ])('classifies Starter as %s with quantity %s (%s)', (taskId, quantity, status) => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { [taskId]: quantity })

    expect(result.tierResults[0].status).toBe(status)
  })

  it('requires the highest role tier among selected tasks', () => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { 'requirements-session': 1, 'continuous-devops': 1 })

    expect(result.requiredTier.id).toBe('enterprise')
    expect(result.suggestedTier.id).toBe('enterprise')
    expect(result.suggestionReason).toBe('roles')
    expect(result.tierResults.map(entry => entry.eligible)).toEqual([false, false, true])
  })

  it('prefers a tier that fits over a smaller uncertain bag', () => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { feature: 3 })

    expect(result.suggestedTier.id).toBe('business')
    expect(result.suggestionReason).toBe('hours')
  })

  it('suggests the first eligible uncertain bag when none fits', () => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { feature: 6 })

    expect(result.suggestedTier.id).toBe('business')
    expect(result.tierResults[1]).toMatchObject({ status: 'may-fit', monthsNeeded: 2 })
  })

  it('suggests the highest tier when the range exceeds each bag', () => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { 'large-feature': 6 })

    expect(result.suggestedTier.id).toBe('enterprise')
    expect(result.suggestionReason).toBe('months')
    expect(result.tierResults[2]).toMatchObject({ status: 'exceeds', monthsNeeded: 2 })
  })

  it('fits when the maximum exactly equals the bag', () => {
    const program = createBuildingOnDemandProgram()
    program.tiers.items[0].bag_hours = 100

    const result = estimateProgram(program, { feature: 2 })

    expect(result.tierResults[0]).toMatchObject({ status: 'fits', monthsNeeded: 1 })
  })

  it('may fit when the minimum exactly equals the bag', () => {
    const program = createBuildingOnDemandProgram()
    program.tiers.items[0].bag_hours = 40

    const result = estimateProgram(program, { feature: 2 })

    expect(result.tierResults[0]).toMatchObject({ status: 'may-fit', monthsNeeded: 3 })
  })

  it.each([
    ['an unknown size', { id: 'unknown', size: 'xl', min_tier: 'starter' }],
    ['an unknown tier', { id: 'unknown', size: 'xs', min_tier: 'other' }],
    ['an absent task', null],
  ])('ignores %s from a malformed payload', (label, task) => {
    const program = createBuildingOnDemandProgram()
    program.estimator.tasks.push(task)

    const result = estimateProgram(program, { unknown: 10, 'small-change': 1 })

    expect(result).toMatchObject({ hoursMin: 2, hoursMax: 7, hasSelection: true })
    expect(result.selectedTasks).toHaveLength(1)
  })

  it.each([-1, NaN, '2'])('ignores the invalid quantity %p', (quantity) => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { feature: quantity })

    expect(result).toMatchObject({ hoursMin: 0, hoursMax: 0, hasSelection: false, suggestedTier: null })
  })

  it('caps a selected quantity at ten tasks', () => {
    const program = createBuildingOnDemandProgram()

    const result = estimateProgram(program, { 'small-change': 25 })

    expect(result).toMatchObject({ hoursMin: 20, hoursMax: 70 })
    expect(result.selectedTasks[0].quantity).toBe(10)
  })

  it('preserves the input payload during an estimate', () => {
    const program = createBuildingOnDemandProgram()
    const selection = { feature: 2, 'requirements-session': 1 }
    const original = JSON.stringify({ program, selection })

    estimateProgram(program, selection)

    expect(JSON.stringify({ program, selection })).toBe(original)
  })

  it('ignores tasks when the payload has no usable tiers', () => {
    const program = createBuildingOnDemandProgram()
    program.tiers.items = [{ id: 'starter', bag_hours: 0 }]

    const result = estimateProgram(program, { 'small-change': 1 })

    expect(result).toMatchObject({ hasSelection: false, suggestedTier: null, tierResults: [] })
  })
})

describe('Building on Demand WhatsApp messages', () => {
  it('describes the selected request in Spanish', () => {
    const program = createBuildingOnDemandProgram()

    const message = estimateWhatsappMessage({ program, selection: { 'requirements-session': 2 }, description: '  Ordenar mi herramienta  ', language: 'es' })

    expect(message).toBe('Pedir la estimación formal — Building on Demand\nOrdenar mi herramienta\n2 × Sesión de requerimientos\nTu pedido: entre 14 y 40 horas\nNivel sugerido: Business')
  })

  it('describes the selected request in English', () => {
    const program = createBuildingOnDemandProgram('en')

    const message = estimateWhatsappMessage({ program, selection: { 'small-change': 1 }, description: 'Improve my tool', language: 'en' })

    expect(message).toBe('Request a formal estimate — Building on Demand\nImprove my tool\n1 × Small change\nYour request: between 2 and 7 hours\nSuggested tier: Starter')
  })

  it('uses the program language when no language is passed', () => {
    const program = createBuildingOnDemandProgram('en')

    const message = estimateWhatsappMessage({ program, selection: {} })

    expect(message).toBe('Request a formal estimate — Building on Demand')
  })

  it('omits invented estimates when no tasks are selected', () => {
    const program = createBuildingOnDemandProgram()

    const message = estimateWhatsappMessage({ program, selection: {}, description: 'Quiero mejorar mi producto' })

    expect(message).toBe('Pedir la estimación formal — Building on Demand\nQuiero mejorar mi producto')
  })

  it('limits the request description to one thousand characters', () => {
    const program = createBuildingOnDemandProgram()

    const message = estimateWhatsappMessage({ program, description: 'a'.repeat(1200), selection: {} })

    expect(message.split('\n')[1]).toBe('a'.repeat(1000))
  })

  it('uses the task id when its label is absent', () => {
    const program = createBuildingOnDemandProgram()
    delete program.estimator.tasks[2].label

    const message = estimateWhatsappMessage({ program, selection: { 'small-change': 1 } })

    expect(message).toContain('1 × small-change')
  })

  it('uses the tier id when its name is absent', () => {
    const program = createBuildingOnDemandProgram()
    delete program.tiers.items[0].name

    const message = estimateWhatsappMessage({ program, selection: { 'small-change': 1 } })

    expect(message).toContain('Nivel sugerido: starter')
  })

  it('preserves the WhatsApp conversation parameters', () => {
    const url = tierWhatsappUrl('https://api.whatsapp.com/send?phone=573238122373', 'Hola, quiero Business (3 meses)')

    expect(new URL(url).searchParams.get('phone')).toBe('573238122373')
    expect(new URL(url).searchParams.get('text')).toBe('Hola, quiero Business (3 meses)')
  })

  it.each(['javascript:alert(1)', 'https://wa.me.example.com/redirect'])('uses the safe fallback for %s', (baseUrl) => {
    const url = tierWhatsappUrl(baseUrl, 'Hola')

    expect(new URL(url).hostname).toBe('wa.me')
    expect(new URL(url).pathname).toBe('/573238122373')
    expect(new URL(url).searchParams.get('text')).toBe('Hola')
  })

  it('replaces the existing WhatsApp message', () => {
    const url = tierWhatsappUrl('https://wa.me/573238122373?text=Viejo', 'Nuevo mensaje\n2 × Componente')

    expect(new URL(url).searchParams.getAll('text')).toEqual(['Nuevo mensaje\n2 × Componente'])
  })

  it('keeps the fallback link usable without a message', () => {
    const url = tierWhatsappUrl(undefined)

    expect(new URL(url).pathname).toBe('/573238122373')
    expect(new URL(url).searchParams.get('text')).toBe('')
  })
})
