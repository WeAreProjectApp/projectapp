import { test, expect } from '../helpers/test.js'
import { mockCaptchaProvider, captchaCredentials } from '../helpers/captcha.js'
import { ADMIN_LOGIN } from '../helpers/flow-tags.js'

test.describe('Panel CAPTCHA', () => {
  test.setTimeout(60_000)

  async function openLogin(page) {
    await page.goto('/admin/login/?next=/api/auth/check/', { waitUntil: 'domcontentloaded' })
    await page.getByLabel('Username:', { exact: true }).fill(captchaCredentials.email)
    await page.getByLabel('Password:', { exact: true }).fill(captchaCredentials.password)
  }

  test('opens the native challenge from the panel entry on mobile', {
    tag: [...ADMIN_LOGIN, '@outcome:display', '@role:admin'],
  }, async ({ page }, testInfo) => {
    await mockCaptchaProvider(page, testInfo.testId)
    await page.setViewportSize({ width: 360, height: 800 })
    // quality: allow-deep-link (the public panel entry is the start; its real link opens Django login)
    await page.goto('/es-co/panel/login', { waitUntil: 'domcontentloaded' })

    await page.getByRole('link', { name: 'Entrar con contraseña', exact: true }).click()
    await page.getByLabel('Username:', { exact: true }).fill(captchaCredentials.email)
    await page.getByLabel('Password:', { exact: true }).fill(captchaCredentials.password)

    await expect(page).toHaveURL(/\/admin\/login\//)
    await expect(page.getByRole('checkbox', { name: 'No soy un robot (prueba)' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeDisabled()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
  })

  test('recovers the native widget after a failed script load', {
    tag: [...ADMIN_LOGIN, '@outcome:failure', '@role:admin'],
  }, async ({ page }, testInfo) => {
    await mockCaptchaProvider(page, testInfo.testId, { failScript: true })
    await openLogin(page)
    await expect(page.getByRole('status')).toContainText('No pudimos cargar el captcha')
    await page.unroute('https://www.google.com/recaptcha/api.js*')
    await mockCaptchaProvider(page, testInfo.testId)

    await page.getByRole('button', { name: 'Reintentar' }).click()
    await page.getByRole('checkbox', { name: 'No soy un robot (prueba)' }).check()

    await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeEnabled()
  })

  test('creates a staff session after solving the challenge', {
    tag: [...ADMIN_LOGIN, '@outcome:success', '@role:admin'],
  }, async ({ page }, testInfo) => {
    await mockCaptchaProvider(page, testInfo.testId)
    await openLogin(page)
    await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeDisabled()

    await page.getByRole('checkbox', { name: 'No soy un robot (prueba)' }).check()
    await page.getByRole('button', { name: 'Log in', exact: true }).click()

    await expect(page).toHaveURL(/\/api\/auth\/check\/$/)
    const response = await page.request.get('/api/auth/check/')
    expect(response.status()).toBe(200)
  })

  test('rejects an invalid challenge on the server', {
    tag: [...ADMIN_LOGIN, '@outcome:error', '@role:admin'],
  }, async ({ page }, testInfo) => {
    await mockCaptchaProvider(page, testInfo.testId, { mode: 'invalid' })
    await openLogin(page)

    await page.getByRole('checkbox', { name: 'No soy un robot (prueba)' }).check()
    await page.getByRole('button', { name: 'Log in', exact: true }).click()

    await expect(page.getByRole('alert')).toContainText('Verificación de captcha fallida')
    await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeDisabled()
  })

  test('keeps the form available for retry during a provider outage', {
    tag: [...ADMIN_LOGIN, '@outcome:failure', '@role:admin'],
  }, async ({ page }, testInfo) => {
    await mockCaptchaProvider(page, testInfo.testId, { mode: 'unavailable' })
    await openLogin(page)

    await page.getByRole('checkbox', { name: 'No soy un robot (prueba)' }).check()
    await page.getByRole('button', { name: 'Log in', exact: true }).click()

    await expect(page.getByRole('alert')).toContainText('No pudimos verificar el captcha')
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible()
    const response = await page.request.get('/api/auth/check/')
    expect(response.status()).toBe(401)
  })

  test('blocks submission when a solved challenge expires', {
    tag: [...ADMIN_LOGIN, '@outcome:error', '@role:admin'],
  }, async ({ page }, testInfo) => {
    await mockCaptchaProvider(page, testInfo.testId)
    await openLogin(page)

    await page.getByRole('checkbox', { name: 'No soy un robot (prueba)' }).check()
    await page.getByRole('button', { name: 'Expirar verificación (prueba)' }).click()

    await expect(page.getByRole('status')).toContainText('El captcha expiró')
    await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeDisabled()
  })
})
