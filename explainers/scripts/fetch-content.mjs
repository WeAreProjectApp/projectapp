#!/usr/bin/env node
/**
 * Descarga el contenido público (catálogo de módulos adicionales y programa de
 * financiación) desde la API de producción y lo congela en content/<video>.<lang>.js
 * para que los renders sean reproducibles sin acceso a la base de datos.
 *
 *   node scripts/fetch-content.mjs --lang es [--origin https://projectapp.co]
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { EDITION, CONTENT_DIR, FRONTEND_ROOT, parseArgs, requireLanguage } from './lib/paths.mjs'

const CONDITION_IDS = ['financing', 'exclusivity', 'calculator', 'hour-package', 'payment-discipline']

const options = parseArgs(process.argv.slice(2), { defaults: { origin: 'https://projectapp.co' } })
const language = requireLanguage(options)
const origin = options.origin.replace(/\/$/, '')

async function fetchJson(path) {
  const url = `${origin}${path}`
  const response = await fetch(url, { headers: { accept: 'application/json' } })
  if (!response.ok) throw new Error(`${url} respondió ${response.status}`)
  return response.json()
}

async function loadLocale(namespace) {
  const file = resolve(FRONTEND_ROOT, 'locales', namespace, `${language}.js`)
  const module = await import(pathToFileURL(file).href)
  return module.default
}

function pick(source, keys) {
  return Object.fromEntries(keys.map((key) => [key, source?.[key] ?? null]))
}

function serialize(payload) {
  return `window.EXPLAINER_CONTENT = ${JSON.stringify(payload, null, 2)};\n`
}

// Refresh this source independently; producing a Scrum explainer must not
// rewrite the already-published catalog or partnership reference snapshots.
if (options.video === 'building-on-demand') {
  if (EDITION !== 'brag-v2') throw new Error('building-on-demand requires --edition brag-v2')
  const program = await fetchJson(`/api/building-on-demand/public/?lang=${language}`)
  const snapshot = pick(program, ['language', 'version', 'hero', 'cell', 'bag', 'hosting'])
  snapshot.tiers = {
    title: program.tiers.title,
    items: program.tiers.items.map(item => pick(item, ['id', 'name', 'bag_hours', 'recommended', 'roles'])),
  }
  mkdirSync(CONTENT_DIR, { recursive: true })
  writeFileSync(resolve(CONTENT_DIR, `building-on-demand.${language}.js`), serialize(snapshot))
  console.log('building-on-demand: public source refreshed; review the script before rendering.')
  process.exit(0)
}

const [catalog, program, catalogLocale, financingLocale] = await Promise.all([
  fetchJson(`/api/additional-modules/public/?lang=${language}`),
  fetchJson(`/api/financing/public/?lang=${language}`),
  loadLocale('additionalModules'),
  loadLocale('financing'),
])

if (EDITION === 'brag-v2') {
  mkdirSync(CONTENT_DIR, { recursive: true })
  writeFileSync(resolve(CONTENT_DIR, `additional-modules.${language}.js`), serialize(catalog))
  writeFileSync(resolve(CONTENT_DIR, `financing.${language}.js`), serialize(program))
  writeFileSync(resolve(CONTENT_DIR, `manifest.${language}.json`), JSON.stringify({
    generatedAt: new Date().toISOString(), origin, language, edition: EDITION,
    note: 'Review editorial copy against the integration branch before regenerating; production may lag behind it.',
  }, null, 2) + '\n')
  console.log('brag-v2: public source snapshots refreshed; review the scripts before rendering.')
  process.exit(0)
}

const additionalModules = {
  language,
  generatedAt: new Date().toISOString(),
  totalModules: catalog.total_modules,
  categories: catalog.categories.map((category) => ({
    slug: category.slug,
    name: category.name,
    count: category.modules.length,
    modules: category.modules.map((module) => pick(module, ['slug', 'icon', 'name', 'summary'])),
  })),
  locale: pick(catalogLocale, [
    'eyebrow', 'title', 'subtitle', 'noPriceNotice', 'moduleCount',
    'whatIs', 'purpose', 'problemsSolved', 'integrations', 'requirements', 'downloadPdf',
  ]),
}

const conditions = program.conditions
  .filter((condition) => CONDITION_IDS.includes(condition.id))
  .map((condition) => pick(condition, ['id', 'number', 'icon', 'title']))

const financing = {
  language,
  generatedAt: new Date().toISOString(),
  hero: pick(program.hero, ['eyebrow', 'title', 'subtitle', 'trust_note']),
  eligibility: pick(program.eligibility, ['badge', 'title']),
  conditions,
  options: program.options.map((option) => pick(option, [
    'id', 'badge', 'name', 'recommended', 'exclusivity_years', 'financing_cycles', 'hour_package_included',
  ])),
  package: pick(program.package, ['name', 'hours']),
  cta: pick(program.cta, ['eyebrow', 'title', 'button']),
  financingMonths: program.financing_months,
  ordinaryInterestRate: program.ordinary_interest_rate,
  locale: pick(financingLocale, ['optionsTitle', 'optionsIntro', 'conditionsTitle', 'years', 'downloadPdf']),
}

mkdirSync(CONTENT_DIR, { recursive: true })
writeFileSync(resolve(CONTENT_DIR, `additional-modules.${language}.js`), serialize(additionalModules))
writeFileSync(resolve(CONTENT_DIR, `financing.${language}.js`), serialize(financing))

const manifest = {
  generatedAt: new Date().toISOString(),
  origin,
  language,
  additionalModules: {
    categories: additionalModules.categories.length,
    modules: additionalModules.totalModules,
  },
  financing: {
    conditions: conditions.length,
    options: financing.options.length,
    financingMonths: financing.financingMonths,
  },
}
writeFileSync(resolve(CONTENT_DIR, `manifest.${language}.json`), `${JSON.stringify(manifest, null, 2)}\n`)

console.log(`content/additional-modules.${language}.js → ${manifest.additionalModules.categories} categorías, ${manifest.additionalModules.modules} módulos`)
console.log(`content/financing.${language}.js → ${manifest.financing.conditions} condiciones, ${manifest.financing.options} opciones, ${manifest.financing.financingMonths} meses`)
