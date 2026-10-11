import { listOf, safeWhatsappUrl } from '~/utils/buildingWithUs'
import esMessages from '~/locales/buildingOnDemand/es'
import enMessages from '~/locales/buildingOnDemand/en'

const isRecord = value => Boolean(value && typeof value === 'object' && !Array.isArray(value))
const isText = value => typeof value === 'string' && Boolean(value.trim())
const isPositiveNumber = value => typeof value === 'number' && Number.isFinite(value) && value > 0
const isNonnegativeNumber = value => typeof value === 'number' && Number.isFinite(value) && value >= 0

const isPrice = price => isRecord(price)
  && isText(price.term)
  && isPositiveNumber(price.months)
  && isPositiveNumber(price.monthly_price)
  && isPositiveNumber(price.total)
  && isNonnegativeNumber(price.discount_percent)
  && isNonnegativeNumber(price.savings)

export function buildingOnDemandLanguage(locale) {
  return String(locale || '').startsWith('en') ? 'en' : 'es'
}

export function buildingOnDemandPath(lang) {
  return lang === 'en' ? '/en-us/building-on-demand' : '/es-co/building-on-demand'
}

export function buildingOnDemandPublicUrl(lang) {
  return `https://projectapp.co${buildingOnDemandPath(lang)}`
}

export function buildingOnDemandPdfUrl(lang) {
  return `/api/building-on-demand/public/pdf/?lang=${buildingOnDemandLanguage(lang)}`
}

export function isBuildingOnDemandProgram(payload) {
  if (!isRecord(payload) || !isText(payload.hero?.title)) return false

  const tiers = listOf(payload.tiers?.items)
  const terms = listOf(payload.terms?.items)

  return tiers.length > 0 && tiers.every(tier => isRecord(tier)
    && isText(tier.id)
    && isPositiveNumber(tier.bag_hours)
    && isPositiveNumber(tier.monthly_price)
    && listOf(tier.prices).length > 0
    && tier.prices.every(isPrice))
    && terms.length > 0 && terms.every(term => isRecord(term)
      && isText(term.id) && isText(term.label) && isPositiveNumber(term.months))
    && isRecord(payload.offer)
    && payload.offer.currency === 'COP'
    && typeof payload.offer.prices_include_vat === 'boolean'
    && isPositiveNumber(payload.offer.days_per_week)
    && isPositiveNumber(payload.offer.weeks_per_month)
    && isRecord(payload.estimator)
    && Array.isArray(payload.estimator.sizes)
    && Array.isArray(payload.estimator.tasks)
}

export function priceForTerm(tier, termId = 'monthly') {
  const prices = listOf(tier?.prices).filter(isPrice)
  return prices.find(price => price.term === termId)
    || prices.find(price => price.term === 'monthly')
    || prices[0]
    || null
}

export function estimateRequest({ tiers, sizes, tasks, selection } = {}) {
  const validTiers = listOf(tiers).filter(tier => isRecord(tier)
    && isText(tier.id) && isPositiveNumber(tier.bag_hours))
  const tierIndexes = new Map(validTiers.map((tier, index) => [tier.id, index]))
  const sizeRanges = new Map(listOf(sizes)
    .filter(size => isRecord(size) && isText(size.id)
      && isPositiveNumber(size.hours_min) && isPositiveNumber(size.hours_max)
      && size.hours_min < size.hours_max)
    .map(size => [size.id, size]))
  const quantities = isRecord(selection) ? selection : {}
  const selectedTasks = listOf(tasks).flatMap(task => {
    if (!isRecord(task) || !isText(task.id)) return []
    const size = sizeRanges.get(task.size)
    const quantity = typeof quantities[task.id] === 'number' && Number.isFinite(quantities[task.id])
      ? Math.min(10, Math.max(0, Math.trunc(quantities[task.id])))
      : 0
    if (!size || !tierIndexes.has(task.min_tier) || quantity === 0) return []

    return [{ ...task, quantity, hoursMin: quantity * size.hours_min, hoursMax: quantity * size.hours_max }]
  })
  const hoursMin = selectedTasks.reduce((sum, task) => sum + task.hoursMin, 0)
  const hoursMax = selectedTasks.reduce((sum, task) => sum + task.hoursMax, 0)

  if (selectedTasks.length === 0) {
    return {
      hoursMin, hoursMax, requiredTier: null, suggestedTier: null,
      tierResults: [], selectedTasks, hasSelection: false, suggestionReason: null,
    }
  }

  const requiredIndex = selectedTasks.reduce((highest, task) => Math.max(highest, tierIndexes.get(task.min_tier)), 0)
  const requiredTier = validTiers[requiredIndex]
  const tierResults = validTiers.map((tier, index) => ({
    tier,
    status: hoursMax <= tier.bag_hours ? 'fits' : hoursMin <= tier.bag_hours ? 'may-fit' : 'exceeds',
    monthsNeeded: Math.max(1, Math.ceil(hoursMax / tier.bag_hours)),
    eligible: index >= requiredIndex,
  }))
  const suggestedResult = tierResults.find(result => result.eligible && result.status === 'fits')
    || tierResults.find(result => result.eligible && result.status === 'may-fit')
    || tierResults[tierResults.length - 1]
  const rolesDetermineTier = suggestedResult.tier.id === requiredTier.id
    && tierResults.some(result => !result.eligible && result.status !== 'exceeds')
  const suggestionReason = suggestedResult.status === 'exceeds' ? 'months' : rolesDetermineTier ? 'roles' : 'hours'

  return {
    hoursMin, hoursMax, requiredTier, suggestedTier: suggestedResult.tier,
    tierResults, selectedTasks, hasSelection: true, suggestionReason,
  }
}

export function estimateWhatsappMessage({ program, selection, description, language } = {}) {
  const lang = buildingOnDemandLanguage(language || program?.language)
  const messages = lang === 'en' ? enMessages : esMessages
  const estimate = estimateRequest({
    tiers: program?.tiers?.items,
    sizes: program?.estimator?.sizes,
    tasks: program?.estimator?.tasks,
    selection,
  })
  const requestDescription = typeof description === 'string' ? description.trim().slice(0, 1000) : ''
  const range = messages.estimateRange.replace('{min}', String(estimate.hoursMin)).replace('{max}', String(estimate.hoursMax))

  return [
    `${messages.estimateWhatsapp} — Building on Demand`,
    requestDescription,
    ...estimate.selectedTasks.map(task => `${task.quantity} × ${task.label || task.id}`),
    estimate.hasSelection ? range : '',
    estimate.suggestedTier ? `${messages.suggestedTierLabel}: ${estimate.suggestedTier.name || estimate.suggestedTier.id}` : '',
  ].filter(Boolean).join('\n')
}

export function tierWhatsappUrl(baseUrl, message) {
  const url = new URL(safeWhatsappUrl(baseUrl))
  url.searchParams.set('text', typeof message === 'string' ? message : '')
  return url.toString()
}
