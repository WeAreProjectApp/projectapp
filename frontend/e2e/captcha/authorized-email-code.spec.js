import { test, expect } from '../helpers/test.js'
import { mockCaptchaProvider, prepareLocallyDeliveredCode } from '../helpers/captcha.js'
import { AUTHORIZED_LOGIN } from '../helpers/flow-tags.js'

// The browser receives a one-time code from the disposable mailer.
test.use({ trace: 'off', screenshot: 'off', video: 'off' })

test('authenticates staff through the accessible email code fields', {
  tag: [...AUTHORIZED_LOGIN, '@outcome:success', '@role:admin'],
}, async ({ page }, testInfo) => {
  await mockCaptchaProvider(page, testInfo.testId)
  const destination = '/api/auth/check/?format=json'
  // quality: allow-deep-link (the public Panel login is the start of this flow)
  await page.goto(`/es-co/panel/login?${new URLSearchParams({ next: destination })}`, { waitUntil: 'domcontentloaded' })
  const verify = await prepareLocallyDeliveredCode(page, 'panel')
  const [staffSession] = await Promise.all([
    page.waitForResponse(response =>
      response.request().isNavigationRequest() && new URL(response.url()).pathname === '/api/auth/check/'),
    verify.click(),
  ])

  await expect(page).toHaveURL(url => url.pathname + url.search === destination)
  expect(staffSession.status()).toBe(200)
  expect((await staffSession.json()).user).toMatchObject({
    username: 'browser-panel-code@example.test',
    is_staff: true,
  })
})

test('keeps the client session from the accessible email code fields', {
  tag: [...AUTHORIZED_LOGIN, '@outcome:success', '@role:platform-client'],
}, async ({ page }, testInfo) => {
  await mockCaptchaProvider(page, testInfo.testId)
  await page.goto('/en-us/platform/login', { waitUntil: 'domcontentloaded' })
  const verify = await prepareLocallyDeliveredCode(page, 'platform')
  await verify.click()

  await expect(page).toHaveURL(/\/en-us\/platform\/documents$/)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/en-us\/platform\/documents$/)
  await expect(page.getByRole('heading', { name: 'Mis documentos', exact: true })).toBeVisible()
})
