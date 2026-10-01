import { test, expect } from '../helpers/test.js'
import { authenticate, fixture, openWorkspace } from './helpers.js'
import { preparePrompt, previewReply, replyPayload } from './prompt-helpers.js'

const tags = ['@module:platform', '@priority:P1', '@role:platform-admin']
test.setTimeout(60_000)

test('admin sends a reviewed response draft without an attached document', {
  tag: ['@flow:platform-delivery-reply-prompt', ...tags, '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-prepare-reply-' + data.stage_id).click()
  const context = await preparePrompt(page)
  await previewReply(page, context)
  await page.getByTestId('delivery-prompt-use-reply').click()
  await page.getByTestId('delivery-report-message').fill('Revisamos las fuentes y atenderemos las pruebas pactadas.')
  await page.getByTestId('delivery-reply-human-reviewed').getByRole('checkbox').check()
  await page.getByTestId('delivery-report-submit').click()
  await expect(page.getByTestId('delivery-report-message')).toHaveCount(0)
  await expect(page.getByTestId('delivery-stage-' + data.stage_id)).toContainText('Revisamos las fuentes y atenderemos las pruebas pactadas.')
})

test('editing a reviewed reply requires reviewing the final text again', {
  tag: ['@flow:platform-delivery-reply-prompt', ...tags, '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-prepare-reply-' + data.stage_id).click()
  const context = await preparePrompt(page)
  await previewReply(page, context)
  await page.getByTestId('delivery-prompt-use-reply').click()
  await page.getByTestId('delivery-reply-human-reviewed').getByRole('checkbox').check()
  await page.getByTestId('delivery-report-message').fill('Texto final pendiente de otra revisión.')
  await page.getByTestId('delivery-report-submit').click()
  await expect(page.getByRole('dialog')).toContainText('Revisa la respuesta final')
  await expect(page.getByTestId('delivery-report-message')).toHaveValue('Texto final pendiente de otra revisión.')
})

test('an incomplete contractual context cannot justify an outside scope reply', {
  tag: ['@flow:platform-delivery-reply-prompt', ...tags, '@outcome:failure'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-prepare-reply-' + data.stage_id).click()
  await expect(page.getByTestId('delivery-prompt-missing')).toBeVisible()
  await page.getByTestId('delivery-prompt-missing').fill('Anexo comercial firmado por confirmar')
  const context = await preparePrompt(page)
  await page.getByTestId('delivery-prompt-json').fill(JSON.stringify(replyPayload(context, 'outside_scope')))
  await page.getByTestId('delivery-prompt-preview').click()
  await expect(page.getByTestId('delivery-prompt-error')).toContainText('Las fuentes están incompletas')
  await expect(page.getByTestId('delivery-prompt-use-reply')).toBeDisabled()
})

test('response prompt includes the public stage conversation', {
  tag: ['@flow:platform-delivery-reply-prompt', ...tags, '@outcome:display'],
}, async ({ page, request }, testInfo) => {
  // quality: allow-deep-link (Each role starts at authenticated Projects; the project and Entregas are opened through visible UI links.)
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await page.getByTestId('delivery-report-open-' + data.stage_id).click()
  await page.getByTestId('delivery-report-message').fill('Necesitamos revisar el resultado del inventario por sucursal.')
  await page.getByTestId('delivery-report-submit').click()
  await expect(page.getByTestId('delivery-report-message')).toHaveCount(0)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-prepare-reply-' + data.stage_id).click()
  await preparePrompt(page)
  await page.getByText('Ver el prompt preparado', { exact: true }).click()
  await expect(page.getByTestId('delivery-prompt-text')).toContainText('Necesitamos revisar el resultado del inventario por sucursal.')
})
