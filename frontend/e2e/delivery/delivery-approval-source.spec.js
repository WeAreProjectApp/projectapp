// qa: draft-unvalidated (2026-10-07 — combined runtime pending)
// Catches package selection that invents a signature, keeps a previous source,
// publishes the new private contract, or converts an original non-PDF download.
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { test, expect } from '../helpers/test.js'
import { authenticate, fixture, frontendUrl, openWorkspace } from './helpers.js'

const tags = ['@module:platform', '@priority:P1', '@role:platform-admin']
const variants = [
  { format: 'DOCX', mode: 'approval-source-docx' },
  { format: 'PNG', mode: 'approval-source-png' },
]

test.setTimeout(60_000)

async function openContractForm(page, title) {
  await page.getByRole('button', { name: 'Agregar contrato', exact: true }).click()
  const form = page.getByTestId('delivery-authoring-form')
  await form.getByTestId('delivery-author-key').fill('confirmed-package')
  await form.getByTestId('delivery-author-title').fill(title)
  return form
}

async function saveContract(page) {
  const savedPromise = page.waitForResponse((response) =>
    response.url().endsWith('/delivery/contracts/') && response.request().method() === 'POST',
  )
  await page.getByTestId('delivery-authoring-save').click()
  const response = await savedPromise
  expect(response.ok()).toBeTruthy()
  const workspace = await response.json()
  await expect(page.getByTestId('delivery-authoring-form')).toHaveCount(0)
  return workspace.contracts.find((contract) => contract.id === workspace.result.id)
}

for (const variant of variants) {
  test.describe(`confirmed ${variant.format} package source`, () => {
    test(`admin registers the ${variant.format} package as a private unsigned contract`, {
      tag: ['@flow:platform-delivery-authoring', ...tags, '@outcome:success'],
    }, async ({ page, request, browser }, testInfo) => {
      // Catches a package filename being mistaken for signature evidence or client permission.
      const data = await fixture(request, testInfo, variant.mode)
      await authenticate(page, request, data, 'admin')
      await openWorkspace(page, data)
      const title = `Contrato privado desde ${variant.format}`
      const form = await openContractForm(page, title)
      await form.getByTestId('delivery-author-approval-file').selectOption(String(data.approval_source.id))
      await expect(form.getByTestId('delivery-approval-private')).toHaveText(
        'Se guardará en privado y sin firma registrada. Después podrás habilitar su consulta y acreditar la firma por separado.',
      )

      const contract = await saveContract(page)

      expect(contract).toMatchObject({
        title, document_id: null, proposal_document_id: null,
        approval_file_id: data.approval_source.id, client_visible: false,
        signature_status: 'unsigned', signed_at: null, signature_evidence: [],
      })
      await expect(page.getByTestId(`delivery-contract-${contract.id}`)).toContainText('Pendiente de firma')
      const clientContext = await browser.newContext({ baseURL: frontendUrl })
      try {
        const clientPage = await clientContext.newPage()
        await authenticate(clientPage, request, data)
        await openWorkspace(clientPage, data)
        await expect(clientPage.getByTestId('delivery-workspace')).toContainText('Traslado entre sucursales')
        await expect(clientPage.getByTestId(`delivery-contract-${contract.id}`)).toHaveCount(0)
      } finally {
        await clientContext.close()
      }
    })

    test(`choosing a document replaces the previous ${variant.format} package selection`, {
      tag: ['@flow:platform-delivery-authoring', ...tags, '@outcome:success'],
    }, async ({ page, request }, testInfo) => {
      // Catches source switching that submits both document_id and approval_file_id.
      const data = await fixture(request, testInfo, variant.mode)
      await authenticate(page, request, data, 'admin')
      await openWorkspace(page, data)
      const title = `Contrato elegido desde documento ${variant.format}`
      const form = await openContractForm(page, title)
      await form.getByTestId('delivery-author-approval-file').selectOption(String(data.approval_source.id))
      await form.getByLabel('Documento del contrato', { exact: true }).selectOption(String(data.contract_document_id))

      await expect(form.getByTestId('delivery-author-approval-file')).toHaveValue('')
      const contract = await saveContract(page)

      expect(contract).toMatchObject({
        title, document_id: data.contract_document_id,
        proposal_document_id: null, approval_file_id: null,
      })
      await expect(page.getByTestId(`delivery-contract-${contract.id}`).getByRole('heading', { level: 3 })).toHaveText(title)
    })

    test(`admin downloads the selected ${variant.format} original without conversion`, {
      tag: ['@flow:platform-delivery-authoring', ...tags, '@outcome:success', '@outcome:display'],
    }, async ({ page, request }, testInfo) => {
      // Catches a wrong source, a regenerated PDF, a changed hash, or a PDF MIME on original bytes.
      // quality: allow-deep-link (the authenticated projects index is setup; the project row and Entregas link are clicked before creating the contract and downloading its source)
      const data = await fixture(request, testInfo, variant.mode)
      await authenticate(page, request, data, 'admin')
      await openWorkspace(page, data)
      const form = await openContractForm(page, `Contrato original ${variant.format}`)
      await form.getByLabel('Documento del contrato', { exact: true }).selectOption(String(data.contract_document_id))
      await form.getByTestId('delivery-author-approval-file').selectOption(String(data.approval_source.id))
      const contract = await saveContract(page)
      const downloadedPromise = page.waitForEvent('download')
      const sourceResponsePromise = page.waitForResponse((response) =>
        response.url().endsWith(`/delivery/contracts/${contract.id}/source/`),
      )

      await page.getByTestId(`delivery-contract-source-${contract.id}`).click()
      const download = await downloadedPromise
      const response = await sourceResponsePromise
      const bytes = await readFile(await download.path())

      expect(contract).toMatchObject({ document_id: null, approval_file_id: data.approval_source.id })
      expect(response.status()).toBe(200)
      expect(response.headers()['content-type']).toBe(data.approval_source.content_type)
      expect(download.suggestedFilename()).toBe(data.approval_source.filename)
      expect(bytes).toEqual(Buffer.from(data.approval_source.original_base64, 'base64'))
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(data.approval_source.sha256)
    })
  })
}
