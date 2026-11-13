/** Browser adapter verification with isolated HTTP fixtures; no production is contacted. */
import fs from 'node:fs'
import path from 'node:path'
import { PUBLIC_HOSTING_PRESENTATION } from '../helpers/flow-tags.js'
import { test, expect } from '../helpers/test.js'

test.setTimeout(60_000)
const assets = path.resolve(process.cwd(), '../backend/hosting_guard/web')

async function setup(page, mode = 'normal') {
  const state = { ready: true, mode, version: 1, target_key: 'fixture', message: { title: 'Pago de prueba', text: 'Contacta al proveedor de prueba.' }, exempt_paths: ['/panel/'] }
  await page.route('**/__hosting/notice.js', route => route.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(assets, 'notice.js'), 'utf8') }))
  await page.route('**/__hosting/notice.css', route => route.fulfill({ contentType: 'text/css', body: fs.readFileSync(path.join(assets, 'notice.css'), 'utf8') }))
  await page.route('**/__hosting/state', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify(state) }))
  await page.route('**/hosting-fixture/**', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/__hosting/notice.css"><script defer src="/__hosting/notice.js"></script></head><body style="margin:0"><header id="site-header" data-hosting-offset="top" style="position:fixed;top:0;left:0;right:0;height:40px"><a href="/hosting-fixture/other">Cabecera del sitio</a></header><main id="product" style="padding-top:60px">Producto disponible <a href="/hosting-fixture/other">Página interna</a><button id="use">Usar producto</button></main></body></html>' }))
  await page.route('**/hosting-entry', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><html><head><meta charset="utf-8"></head><body><a href="/hosting-fixture/deep">Abrir sitio de prueba</a></body></html>' }))
  await page.goto('/hosting-entry', { waitUntil: 'domcontentloaded' })
  return state
}

test('banner preserves an internal navigation', { tag: [...PUBLIC_HOSTING_PRESENTATION, '@outcome:success'] }, async ({ page }) => {
  await setup(page, 'banner')
  await page.getByRole('link', { name: 'Abrir sitio de prueba' }).click()
  await expect(page.locator('#hosting-notice')).toContainText('Pago de prueba')
  await page.getByRole('link', { name: 'Página interna' }).click()
  await expect(page.locator('#product')).toBeVisible()
  await expect(page.locator('#hosting-notice')).toContainText('Contacta al proveedor de prueba.')
})

test('suspension replaces the product after reload', { tag: [...PUBLIC_HOSTING_PRESENTATION, '@outcome:success'] }, async ({ page }) => {
  await setup(page, 'suspended')
  await page.getByRole('link', { name: 'Abrir sitio de prueba' }).click()
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.locator('#hosting-notice')).toContainText('Contacta al proveedor de prueba.')
  await expect(page.locator('#product')).toBeHidden()
})

test('an updated mode restores the open product', { tag: [...PUBLIC_HOSTING_PRESENTATION, '@outcome:success'] }, async ({ page }) => {
  const state = await setup(page, 'suspended')
  await page.getByRole('link', { name: 'Abrir sitio de prueba' }).click()
  await expect(page.locator('#product')).toBeHidden()
  state.mode = 'normal'; state.version = 2
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(page.locator('#product')).toBeVisible()
  await expect(page.locator('#hosting-notice')).toHaveCount(0)
})

test('a disconnected page retains the last received banner', { tag: [...PUBLIC_HOSTING_PRESENTATION, '@outcome:failure'] }, async ({ page }) => {
  await setup(page, 'banner')
  await page.getByRole('link', { name: 'Abrir sitio de prueba' }).click()
  await expect(page.locator('#hosting-notice')).toBeVisible()
  await page.route('**/__hosting/state', route => route.abort('failed'))
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(page.locator('#hosting-notice')).toContainText('Pago de prueba')
})

test('a long mobile notice fits the viewport', { tag: [...PUBLIC_HOSTING_PRESENTATION, '@outcome:display'] }, async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 })
  const state = await setup(page, 'banner')
  await page.getByRole('link', { name: 'Abrir sitio de prueba' }).click()
  state.message.text = 'Mensaje largo de prueba '.repeat(35); state.version = 2
  await page.getByRole('link', { name: 'Página interna' }).click()
  await expect(page.locator('#hosting-notice')).toContainText('Mensaje largo de prueba')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})


test('banner keeps fixed navigation usable', { tag: [...PUBLIC_HOSTING_PRESENTATION, '@outcome:success'] }, async ({ page }) => {
  const state = await setup(page, 'banner')
  await page.getByRole('link', { name: 'Abrir sitio de prueba' }).click()
  await expect(page.locator('#hosting-notice')).toBeVisible()
  await page.getByRole('link', { name: 'Cabecera del sitio' }).click()
  await expect(page).toHaveURL(/hosting-fixture\/other$/)
  await expect(page.locator('#hosting-notice')).toBeVisible()
  const bounds = await page.evaluate(() => ({ notice: document.getElementById('hosting-notice').getBoundingClientRect().bottom, header: document.getElementById('site-header').getBoundingClientRect().top }))
  expect(bounds.header).toBeGreaterThanOrEqual(bounds.notice - 1)
  state.mode = 'normal'; state.version = 2
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(page.locator('#hosting-notice')).toHaveCount(0)
  expect(await page.locator('#site-header').evaluate(element => element.getBoundingClientRect().top)).toBe(0)
})
