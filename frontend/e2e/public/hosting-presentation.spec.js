/** Browser adapter verification with isolated HTTP fixtures; no production is contacted. */
import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '../helpers/test.js'

test.setTimeout(60_000)
const tags = ['@flow:public-hosting-presentation', '@module:public', '@priority:P1']
const assets = path.resolve(process.cwd(), '../backend/hosting_guard/web')

async function setup(page, mode = 'normal') {
  const state = { ready: true, mode, version: 1, target_key: 'fixture', message: { title: 'Pago de prueba', text: 'Contacta al proveedor de prueba.' }, exempt_paths: ['/panel/'] }
  await page.route('**/__hosting/notice.js', route => route.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(assets, 'notice.js'), 'utf8') }))
  await page.route('**/__hosting/notice.css', route => route.fulfill({ contentType: 'text/css', body: fs.readFileSync(path.join(assets, 'notice.css'), 'utf8') }))
  await page.route('**/__hosting/state', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify(state) }))
  await page.route('**/hosting-fixture/**', route => route.fulfill({ contentType: 'text/html', body: '<html><head><link rel="stylesheet" href="/__hosting/notice.css"><script defer src="/__hosting/notice.js"></script></head><body><main id="product">Producto disponible <a href="/hosting-fixture/other">Página interna</a><button id="use">Usar producto</button></main></body></html>' }))
  await page.goto('/hosting-fixture/deep', { waitUntil: 'domcontentloaded' })
  return state
}

test('banner preserves an internal navigation', { tag: [...tags, '@outcome:success'] }, async ({ page }) => {
  await setup(page, 'banner')
  await expect(page.locator('#hosting-notice')).toContainText('Pago de prueba')
  await page.getByRole('link', { name: 'Página interna' }).click()
  await expect(page.locator('#product')).toBeVisible()
  await expect(page.locator('#hosting-notice')).toContainText('Contacta al proveedor de prueba.')
})

test('suspension replaces the product after reload', { tag: [...tags, '@outcome:success'] }, async ({ page }) => {
  await setup(page, 'suspended')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.locator('#hosting-notice')).toBeVisible()
  await expect(page.locator('#product')).toBeHidden()
})

test('an updated mode restores the open product', { tag: [...tags, '@outcome:success'] }, async ({ page }) => {
  const state = await setup(page, 'suspended')
  await expect(page.locator('#product')).toBeHidden()
  state.mode = 'normal'; state.version = 2
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(page.locator('#product')).toBeVisible()
  await expect(page.locator('#hosting-notice')).toHaveCount(0)
})

test('a disconnected page retains the last received banner', { tag: [...tags, '@outcome:failure'] }, async ({ page }) => {
  await setup(page, 'banner')
  await expect(page.locator('#hosting-notice')).toBeVisible()
  await page.route('**/__hosting/state', route => route.abort('failed'))
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(page.locator('#hosting-notice')).toContainText('Pago de prueba')
})

test('a long mobile notice fits the viewport', { tag: [...tags, '@outcome:display'] }, async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 })
  const state = await setup(page, 'banner')
  state.message.text = 'Mensaje largo de prueba '.repeat(35); state.version = 2
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(page.locator('#hosting-notice')).toContainText('Mensaje largo de prueba')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
