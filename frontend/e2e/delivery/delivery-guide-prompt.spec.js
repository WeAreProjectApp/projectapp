import { test, expect } from '../helpers/test.js'
import { assertTouchAction, authenticate, fixture, openWorkspace } from './helpers.js'
import { guidePayload, preparePrompt } from './prompt-helpers.js'
import { viewportUse } from '../helpers/viewports.js'
import { batchForScenario } from '../responsive/catalog-scenarios.js'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'

const tags = ['@module:platform', '@priority:P1', '@role:platform-admin']
test.setTimeout(60_000)

test('admin applies a guide draft with verified contractual citations', {
  tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
  const context = await preparePrompt(page)
  await page.getByTestId('delivery-prompt-json').fill(JSON.stringify(guidePayload(context, data.contract_id)))
  await page.getByTestId('delivery-prompt-preview').click()
  await expect(page.getByTestId('delivery-prompt-apply')).toBeEnabled()
  await page.getByTestId('delivery-prompt-apply').click()
  await expect(page.getByTestId('delivery-prompt-workbench')).toHaveCount(0)
  await expect(page.getByTestId('delivery-workspace')).toContainText('Alcance preparado con sus fuentes')
})

test('admin must select a contract before creating a prompt', {
  tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await expect(page.getByTestId('delivery-prompt-contract')).toBeVisible()
  await page.getByTestId('delivery-prompt-prepare').click()
  await expect(page.getByTestId('delivery-prompt-contract')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByTestId('delivery-prompt-sources')).toHaveCount(0)
})

test('admin retains contractual citations when correcting a drafted guide', {
  tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
  const context = await preparePrompt(page)
  const payload = guidePayload(context, data.contract_id)
  await page.getByTestId('delivery-prompt-json').fill(JSON.stringify(payload))
  await page.getByTestId('delivery-prompt-preview').click()
  await expect(page.getByTestId('delivery-prompt-apply')).toBeEnabled()
  const appliedPromise = page.waitForResponse((response) => response.url().endsWith('/delivery/import/apply/'))
  await page.getByTestId('delivery-prompt-apply').click()
  const applied = await (await appliedPromise).json()
  const requirement = applied.scopes.find((scope) => scope.key === 'source-based-scope').phases[0].stages[0].requirements[0]
  await page.getByTestId('delivery-edit-requirement-' + requirement.id).click()
  await page.getByLabel('Qué debe pasar', { exact: true }).fill('Se muestran los datos del registro preparado.')
  await expect(page.getByTestId('delivery-authoring-save')).toBeDisabled()
  await page.getByTestId('delivery-guide-human-reviewed').getByRole('checkbox').check()
  const correctedPromise = page.waitForResponse((response) => response.url().endsWith('/delivery/requirements/' + requirement.id + '/') && response.request().method() === 'PATCH')
  await page.getByTestId('delivery-authoring-save').click()
  const correctedResponse = await correctedPromise
  expect(correctedResponse.status()).toBe(200)
  const corrected = await correctedResponse.json()
  const saved = corrected.scopes.find((scope) => scope.key === 'source-based-scope').phases[0].stages[0].requirements[0]
  expect(saved.context_id).toBe(context.id)
  expect(saved.source_references).toEqual(payload.scopes[0].phases[0].stages[0].requirements[0].source_references)
  await expect(page.getByTestId('delivery-authoring-form')).toHaveCount(0)
  await expect(page.getByTestId('delivery-workspace')).toContainText('Se muestran los datos del registro preparado.')
})

test('admin downloads the exact retained contractual source', {
  tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
  const context = await preparePrompt(page)
  const source = context.sources.find((item) => item.role === 'contract')
  const downloadPromise = page.waitForEvent('download')
  await page.getByTestId('delivery-prompt-source-' + source.source_key).getByRole('button', { name: 'Descargar la copia conservada' }).click()
  const download = await downloadPromise
  const bytes = await readFile(await download.path())
  expect(download.suggestedFilename()).toBe(source.filename)
  expect(createHash('sha256').update(bytes).digest('hex')).toBe(source.sha256)
})

test('server rejects a fabricated contractual quote before applying a guide', {
  tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:failure'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
  const context = await preparePrompt(page)
  const payload = guidePayload(context, data.contract_id)
  payload.scopes[0].phases[0].stages[0].requirements[0].source_references[0].quote = 'Cláusula inventada que no existe en ninguna fuente.'
  await page.getByTestId('delivery-prompt-json').fill(JSON.stringify(payload))
  await page.getByTestId('delivery-prompt-preview').click()
  await expect(page.getByTestId('delivery-prompt-error')).toContainText('El localizador o la cita no existe')
  await expect(page.getByTestId('delivery-prompt-apply')).toBeDisabled()
  await expect(page.getByTestId('delivery-workspace').getByText('Alcance preparado con sus fuentes', { exact: true })).toHaveCount(0)
})

test('admin sees a missing annex in the retained source list', {
  tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:display'],
}, async ({ page, request }, testInfo) => {
  // quality: allow-deep-link (Authenticated Projects is the entry point; the project and Entregas are opened through visible UI links.)
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
  await page.getByTestId('delivery-prompt-missing').fill('Anexo técnico firmado de inventario')
  await preparePrompt(page)
  await expect(page.getByTestId('delivery-prompt-sources')).toContainText('Anexo técnico firmado de inventario')
  await expect(page.getByTestId('delivery-prompt-incomplete')).toContainText('Hay fuentes incompletas')
})

test('admin retrieves a previous prompt from the source history', {
  tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:display'],
}, async ({ page, request }, testInfo) => {
  // quality: allow-deep-link (Authenticated Projects is the entry point; the project and Entregas are opened through visible UI links.)
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
  const context = await preparePrompt(page)
  await page.getByRole('dialog').getByRole('button', { name: 'Cancelar', exact: true }).click()
  await page.getByTestId('delivery-prompt-history').click()
  const row = page.getByTestId('delivery-prompt-history-' + context.id)
  await expect(row).toContainText('Crear guías')
  await row.getByRole('button', { name: 'Consultar las fuentes conservadas' }).click()
  await expect(page.getByTestId('delivery-prompt-sources')).toContainText(context.sources[0].title)
  await expect(page.getByTestId('delivery-prompt-sources')).toContainText(context.sources[0].sha256)
})

for (const name of ['portrait', 'compact', 'landscape', 'desktop', 'wide']) {
  test.describe(`delivery guide sources ${name}`, () => {
    test.use(viewportUse(name))
    test('guide source controls remain usable at ' + name + ' width', {
      tag: ['@flow:platform-delivery-guide-prompt', ...tags, '@outcome:success', '@responsive:clients', '@responsive-scenario:frontend/pages/platform/projects/[id]/delivery.vue', `@responsive-batch:${batchForScenario('frontend/pages/platform/projects/[id]/delivery.vue')}`, '@viewport:' + name],
    }, async ({ page, request }, testInfo) => {
      const data = await fixture(request, testInfo)
      await authenticate(page, request, data, 'admin')
      await openWorkspace(page, data)
      await page.getByTestId('delivery-create-guides').click()
      await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
      await preparePrompt(page)
      await page.getByTestId('delivery-prompt-json').scrollIntoViewIfNeeded()
      await assertTouchAction(page, page.getByTestId('delivery-prompt-copy'), name, testInfo)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow).toBeLessThanOrEqual(1)
      await page.getByRole('dialog').getByRole('button', { name: 'Cancelar', exact: true }).click()
      await expect(page.getByTestId('delivery-prompt-workbench')).toHaveCount(0)
    })
  })
}
