import { test, expect } from '../helpers/test.js'
import { addRequirement, assertTouchAction, authenticate, fixture, openWorkspace, publish } from './helpers.js'
import { preparePrompt, roleGuidePayload } from './prompt-helpers.js'
import { viewportUse } from '../helpers/viewports.js'
import { batchForScenario } from '../responsive/catalog-scenarios.js'

const tags = ['@module:platform', '@priority:P1', '@role:platform-admin']
test.setTimeout(60_000)

test('admin publishes a prepared internal stage', {
  tag: ['@flow:platform-delivery-authoring', ...tags, '@outcome:success'],
}, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await addRequirement(page, data, 'Validar el resumen del inventario')
  await publish(page, data.hidden_stage_id)
  const context = await browser.newContext()
  const clientPage = await context.newPage()
  await authenticate(clientPage, request, data)
  await openWorkspace(clientPage, data)
  await expect(clientPage.getByTestId(`delivery-stage-${data.hidden_stage_id}`)).toContainText('Validar el resumen del inventario')
  await context.close()
})

// Fails if publication discards a sourced role-guide draft after its completeness error,
// or if the completed guide is announced without becoming visible to the client.
test('admin completes a sourced role guide after publication rejects its blocked case', {
  tag: ['@flow:platform-delivery-authoring', ...tags, '@outcome:error', '@outcome:success'],
}, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo, 'role-guide')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-create-guides').click()
  await page.getByTestId('delivery-prompt-contract').selectOption(String(data.contract_id))
  const context = await preparePrompt(page)
  const payload = roleGuidePayload(context, data.contract_id)
  delete payload.scopes[0].phases[0].stages[0].requirements[0].guide.blocked_result
  await page.getByTestId('delivery-prompt-json').fill(JSON.stringify(payload))
  await page.getByTestId('delivery-prompt-preview').click()
  await expect(page.getByTestId('delivery-prompt-apply')).toBeEnabled()
  const importedPromise = page.waitForResponse((response) => response.url().endsWith('/delivery/import/apply/'))
  await page.getByTestId('delivery-prompt-apply').click()
  const imported = await (await importedPromise).json()
  const stage = imported.scopes.find((scope) => scope.key === 'source-based-scope').phases[0].stages[0]
  const requirement = stage.requirements[0]
  await expect(page.getByTestId(`delivery-stage-${stage.id}`)).toContainText('Etapa de inventario por rol')
  await page.getByTestId(`delivery-publish-${stage.id}`).click()
  await page.getByTestId('delivery-confirm-action').click()
  await expect(page.getByRole('alert').filter({ hasText: 'Completa el resultado esperado del caso bloqueado' })).toBeVisible()
  await expect(page.getByTestId(`delivery-stage-${stage.id}`)).toContainText('Validar el inventario por rol')
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
  await page.getByTestId(`delivery-edit-requirement-${requirement.id}`).click()
  await page.getByTestId('delivery-author-blocked_result').fill('La modificación permanece bloqueada.')
  await page.getByTestId('delivery-guide-human-reviewed').getByRole('checkbox').check()
  await page.getByTestId('delivery-authoring-save').click()
  await expect(page.getByTestId('delivery-authoring-form')).toHaveCount(0)
  await publish(page, stage.id)
  const clientContext = await browser.newContext()
  const clientPage = await clientContext.newPage()
  await authenticate(clientPage, request, data)
  await openWorkspace(clientPage, data)
  await expect(clientPage.getByTestId(`delivery-stage-${stage.id}`)).toContainText('Validar el inventario por rol')
  await clientContext.close()
})

test('a draft requires a name before saving', {
  tag: ['@flow:platform-delivery-authoring', ...tags, '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId(`delivery-add-requirement-${data.hidden_stage_id}`).click()
  await page.getByTestId('delivery-author-key').fill('unnamed-case')
  await page.getByTestId('delivery-authoring-save').click()
  await expect(page.getByTestId('delivery-author-title')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByTestId('delivery-authoring-form')).toContainText('Completa este campo.')
})

test('a stale author cannot overwrite a saved guide', {
  tag: ['@flow:platform-delivery-authoring', ...tags, '@outcome:failure'],
}, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId(`delivery-edit-requirement-${data.requirement_ids[1]}`).click()
  await page.getByLabel('Qué debe pasar', { exact: true }).fill('Una guía desactualizada.')
  const context = await browser.newContext()
  const currentPage = await context.newPage()
  await authenticate(currentPage, request, data, 'admin')
  await openWorkspace(currentPage, data)
  await currentPage.getByTestId(`delivery-edit-requirement-${data.requirement_ids[1]}`).click()
  await currentPage.getByLabel('Qué debe pasar', { exact: true }).fill('Guía guardada desde otra sesión.')
  await currentPage.getByTestId('delivery-authoring-save').click()
  await expect(currentPage.getByTestId('delivery-authoring-form')).toHaveCount(0)
  await page.getByTestId('delivery-authoring-save').click()
  await expect(page.getByTestId('delivery-authoring-form')).toContainText('El contenido cambió mientras lo revisabas.')
  await expect(page.getByLabel('Qué debe pasar', { exact: true })).toHaveValue('Una guía desactualizada.')
  await context.close()
})

test('the import editor rejects malformed JSON', {
  tag: ['@flow:platform-delivery-import', '@module:platform', '@priority:P1', '@role:platform-admin', '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-import').click()
  await page.getByTestId('delivery-import-json').fill('{')
  await page.getByTestId('delivery-import-preview').click()
  await expect(page.getByRole('dialog')).toContainText('El texto no es un JSON válido.')
  await expect(page.getByTestId('delivery-import-apply')).toBeDisabled()
})

test('the server rejects imported approval states', {
  tag: ['@flow:platform-delivery-import', '@module:platform', '@priority:P1', '@role:platform-admin', '@outcome:failure'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-import').click()
  await page.getByTestId('delivery-import-json').fill(JSON.stringify({
    schema_version: 1, scopes: [{ key: 'fake-approval', title: 'Conformidad falsa', contract_id: data.contract_id, review_status: 'approved', phases: [] }],
  }))
  await page.getByTestId('delivery-import-preview').click()
  await expect(page.getByRole('dialog')).toContainText('No importes estados, firmas ni aprobaciones.')
  await expect(page.getByTestId('delivery-import-apply')).toBeDisabled()
})

test('admin previews the JSON before applying drafts', {
  tag: ['@flow:platform-delivery-import', '@module:platform', '@priority:P1', '@role:platform-admin', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await page.getByTestId('delivery-import').click()
  await page.getByTestId('delivery-import-json').fill(JSON.stringify({
    schema_version: 1, scopes: [{ key: 'future-scope', title: 'Alcance preparado para después', contract_id: data.contract_id, phases: [{ key: 'new-phase', title: 'Fase preparada', stages: [] }] }],
  }))
  await expect(page.getByTestId('delivery-import-apply')).toBeDisabled()
  await page.getByTestId('delivery-import-preview').click()
  await expect(page.getByRole('dialog')).toContainText('El JSON es válido.')
  await page.getByTestId('delivery-import-apply').click()
  await expect(page.getByTestId('delivery-import-json')).toHaveCount(0)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('delivery-workspace')).toContainText('Alcance preparado para después')
})

for (const name of ['portrait', 'compact', 'landscape', 'desktop', 'wide']) {
  test.describe(`delivery review ${name}`, () => {
    test.use(viewportUse(name))
    test(`review controls remain usable at ${name} width`, {
      tag: ['@flow:platform-delivery-review', '@module:platform', '@priority:P1', '@role:platform-client', '@outcome:success', '@responsive:clients', '@responsive-scenario:frontend/pages/platform/projects/[id]/delivery.vue', `@responsive-batch:${batchForScenario('frontend/pages/platform/projects/[id]/delivery.vue')}`, `@viewport:${name}`],
    }, async ({ page, request }, testInfo) => {
      const data = await fixture(request, testInfo)
      await authenticate(page, request, data)
      await openWorkspace(page, data)
      await page.getByTestId(`delivery-review-open-${data.stage_id}`).click()
      await page.getByTestId(`delivery-review-decision-${data.requirement_ids[0]}`).selectOption('approved')
      await page.getByTestId('delivery-review-submit').scrollIntoViewIfNeeded()
      await assertTouchAction(page, page.getByTestId('delivery-review-submit'), name, testInfo)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow).toBeLessThanOrEqual(1)
      await page.getByTestId('delivery-review-submit').click()
      await expect(page.getByTestId('delivery-review-form')).toHaveCount(0)
      await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[0]}`)).toContainText('Aprobado')
    })
  })
}
