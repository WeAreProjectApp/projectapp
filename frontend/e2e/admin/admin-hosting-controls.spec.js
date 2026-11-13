import { ADMIN_HOSTING_CONTROLS } from '../helpers/flow-tags.js'
import { test, expect } from '../helpers/test.js'
import { setupHostingControls as setup } from '../helpers/hosting-controls.js'

test.setTimeout(60_000)

test('switching mode replaces the previous selection', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success'] }, async ({ page }) => {
  await setup(page)
  await page.getByTestId('hosting-switch-suspended').click()
  await expect(page.getByTestId('hosting-switch-suspended')).toHaveAttribute('aria-checked', 'true')
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-switch-suspended')).toHaveAttribute('aria-checked', 'false')
  await expect(page.getByTestId('hosting-switch-banner')).toHaveAttribute('aria-checked', 'true')
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-configured-mode')).toContainText('Funcionamiento normal')
})

test('editing the banner leaves suspension text intact', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success'] }, async ({ page }) => {
  const state = await setup(page)
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-configured-mode')).toContainText('Banner de aviso')
  await page.getByTestId('hosting-title-banner').fill('Aviso actualizado de prueba')
  await page.getByTestId('hosting-save-banner').click()
  await expect.poll(() => state.banner_title).toBe('Aviso actualizado de prueba')
  expect(state.suspension_text).toBe('Gestiona la reactivación con tu proveedor.')
  expect(state.mode).toBe('banner')
})

test('a stale message keeps the operator draft', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:error'] }, async ({ page }) => {
  await setup(page, { conflict: true })
  await page.getByTestId('hosting-title-banner').fill('Borrador que conservar')
  await page.getByTestId('hosting-save-banner').click()
  await expect(page.getByTestId('hosting-error')).toContainText('Otra edición')
  await expect(page.getByTestId('hosting-title-banner')).toHaveValue('Borrador que conservar')
})

test('a failed mode change retains its configured state', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:failure'] }, async ({ page }) => {
  await setup(page, { failure: true })
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-error')).toContainText('Fallo de prueba')
  await expect(page.getByTestId('hosting-switch-banner')).toHaveAttribute('aria-checked', 'false')
})

test('production receipt is shown separately from configured mode', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:display'] }, async ({ page }) => {
  await setup(page, { throughProjects: true })
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-status-fixture')).toContainText('Pendiente de aplicación')
  await expect(page.getByText('https://fixture.example', { exact: true })).toBeVisible()
})

test('phone layout retains both message editors', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success'] }, async ({ page }) => {
  await page.setViewportSize({ width: 412, height: 915 })
  await setup(page)
  await page.getByTestId('hosting-text-banner').fill('Mensaje móvil de prueba.')
  await page.getByTestId('hosting-save-banner').click()
  await expect(page.getByTestId('hosting-text-banner')).toHaveValue('Mensaje móvil de prueba.')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
