import { test, expect } from './fixtures.js'
import { fillContactForm } from '../helpers/contact-form.js'
import { PUBLIC_CONTACT_SUBMIT } from '../helpers/flow-tags.js'

test('renders the accepted contact receipt in the submitting tab', {
  tag: [...PUBLIC_CONTACT_SUBMIT, '@role:guest', '@outcome:success'],
}, async ({ page }) => {
  const posts = []
  function isSubmission(request) {
    return request.method() === 'POST' && new URL(request.url()).pathname === '/api/new-contact/'
  }
  page.on('request', request => {
    if (isSubmission(request)) posts.push(request)
  })

  const document = await page.goto('/en-us/contact', { waitUntil: 'domcontentloaded' })
  expect(document.status()).toBe(200)
  const form = page.getByTestId('contact-form')
  await fillContactForm(form, 'en', 'contact-case@example.test')
  const accepted = page.waitForResponse(response => isSubmission(response.request()))
  await form.getByRole('button', { name: 'Send message', exact: true }).click()
  expect((await accepted).status()).toBe(201)
  await expect(page).toHaveURL('/en-us/contact-success')
  const heading = page.getByRole('heading', { level: 1 }).and(page.getByTestId('contact-success-heading'))
  await expect(heading).toBeVisible()
  await expect(heading).toContainText(/\p{L}/u)
  await expect(heading).toHaveCSS('opacity', '1')
  await expect(form).toHaveCount(0)
  expect(posts).toHaveLength(1)
})
