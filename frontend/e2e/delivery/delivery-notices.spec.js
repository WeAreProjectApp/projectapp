// qa: draft-unvalidated (2026-10-07 — combined runtime pending)
// Catches notices that misreport stored data, send during preview, ignore the
// reviewed retry manifest, duplicate a stale retry, or present SMTP rejection as sent.
import { test, expect } from '../helpers/test.js'
import { authenticate, backendUrl, fixture, frontendUrl, openWorkspace } from './helpers.js'

const tags = ['@module:platform', '@priority:P1', '@role:platform-admin']

test.setTimeout(60_000)

function noticeRow(page, data) {
  return page.getByTestId('delivery-notice-history').getByRole('article').filter({ hasText: data.notice.subject })
}

async function probe(request, data) {
  const response = await request.post(`${backendUrl}/__delivery_fixture_probe__`, {
    data: { key: data.fixture_key },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function prepareRetry(page, data) {
  const previewPromise = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/delivery/notices/${data.notice.id}/retry-preview/`),
  )
  await noticeRow(page, data).getByRole('button', { name: 'Revisar reintento', exact: true }).click()
  const response = await previewPromise
  expect(response.status()).toBe(200)
  await expect(page.getByTestId('delivery-notice-retry-preview')).toContainText(data.notice.subject)
  return response.json()
}

async function confirmRetry(page, data) {
  const retryPromise = page.waitForResponse((response) =>
    response.url().endsWith(`/delivery/notices/${data.notice.id}/retry/`) && response.request().method() === 'POST',
  )
  await page.getByTestId('delivery-notice-retry-preview').getByRole('button', { name: 'Confirmar reintento', exact: true }).click()
  return retryPromise
}

test('administrator reaches the stored failed notice through project delivery navigation', {
  tag: ['@flow:platform-delivery-notices', ...tags, '@outcome:display'],
}, async ({ page, request }, testInfo) => {
  // Catches an unreachable history or subject, recipient and status from another event.
  // quality: allow-deep-link (the authenticated projects index is setup; the project row and Entregas link are clicked to reach the real notice history)
  const data = await fixture(request, testInfo, 'notice-failed')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)

  const row = noticeRow(page, data)

  await expect(row.getByText(data.notice.subject, { exact: true })).toHaveText('Etapa disponible: Etapa de validación')
  await expect(row.getByText(data.client.email, { exact: true })).toHaveText(data.client.email)
  await expect(row.getByText('Fallido', { exact: true })).toHaveText('Fallido')
})

test('opening the failed notice preview preserves its single rejected attempt', {
  tag: ['@flow:platform-delivery-notices', ...tags, '@outcome:display'],
}, async ({ page, request }, testInfo) => {
  // Catches a retry preview that starts SMTP before the administrator confirms it.
  // quality: allow-deep-link (the authenticated projects index is setup; project and Entregas navigation reaches the notice before its preview is opened)
  const data = await fixture(request, testInfo, 'notice-failed')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)

  await prepareRetry(page, data)

  await expect(page.getByTestId('delivery-notice-retry-preview').getByText(data.client.email, { exact: true })).toHaveText(data.client.email)
  await expect(page.getByTestId('delivery-notice-retry-preview').getByRole('button', { name: 'Confirmar reintento', exact: true })).toHaveText('Confirmar reintento')
  await expect(page.getByTestId('delivery-notice-retry-preview').getByText(data.notice.text_body, { exact: true })).toHaveText(data.notice.text_body)
  const stored = await probe(request, data)
  expect(stored.notices).toHaveLength(1)
  expect(stored.notices[0]).toMatchObject({ status: 'failed', version: data.notice.version, attempt_count: 1 })
  expect(stored.notice_outbox_count).toBe(0)
})

test('confirming the reviewed manifest sends one notice retry', {
  tag: ['@flow:platform-delivery-notices', ...tags, '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  // Catches omission of the reviewed version/hash or a retry that sends more than one copy.
  const data = await fixture(request, testInfo, 'notice-failed')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  const preview = await prepareRetry(page, data)

  const response = await confirmRetry(page, data)

  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON()).toMatchObject({
    expected_version: preview.version, preview_sha256: preview.preview_sha256,
  })
  await expect(noticeRow(page, data).getByText('Enviado', { exact: true })).toHaveText('Enviado')
  const stored = await probe(request, data)
  expect(stored.notices[0]).toMatchObject({ status: 'sent', attempt_count: 2, recipients: [data.client.email] })
  expect(stored.notices[0].attempts[1]).toMatchObject({ status: 'sent', preview_sha256: preview.preview_sha256 })
  expect(stored.notice_outbox_count).toBe(1)
})

test('an obsolete retry preview is rejected after another administrator sends it', {
  tag: ['@flow:platform-delivery-notices', ...tags, '@outcome:error'],
}, async ({ page, request, browser }, testInfo) => {
  // Catches stale optimistic locking that queues a second SMTP copy after a real retry.
  const data = await fixture(request, testInfo, 'notice-failed')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  const originalPreview = await prepareRetry(page, data)
  const currentContext = await browser.newContext({ baseURL: frontendUrl })
  try {
    const currentPage = await currentContext.newPage()
    await authenticate(currentPage, request, data, 'admin')
    await openWorkspace(currentPage, data)
    await prepareRetry(currentPage, data)
    await confirmRetry(currentPage, data)
    await expect(noticeRow(currentPage, data).getByText('Enviado', { exact: true })).toHaveText('Enviado')

    const response = await confirmRetry(page, data)

    expect(response.status()).toBe(409)
    expect(response.request().postDataJSON()).toMatchObject({ expected_version: originalPreview.version })
    await expect(page.getByTestId('delivery-notice-history').getByRole('alert')).toHaveText('El seguimiento cambió. Actualiza antes de continuar.')
    const stored = await probe(request, data)
    expect(stored.notices[0]).toMatchObject({ status: 'sent', attempt_count: 2 })
    expect(stored.notice_outbox_count).toBe(1)
  } finally {
    await currentContext.close()
  }
})

test('an SMTP rejection remains visible as a failed retry', {
  tag: ['@flow:platform-delivery-notices', ...tags, '@outcome:failure'],
}, async ({ page, request }, testInfo) => {
  // Catches a transport rejection being labelled sent or losing the persisted second attempt.
  const data = await fixture(request, testInfo, 'notice-smtp-failure')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await prepareRetry(page, data)

  const response = await confirmRetry(page, data)

  expect(response.status()).toBe(200)
  await expect(page.getByTestId('delivery-notice-retry-preview')).toHaveCount(0)
  await expect(noticeRow(page, data).getByText('Fallido', { exact: true })).toHaveText('Fallido')
  const stored = await probe(request, data)
  expect(stored.notices[0]).toMatchObject({ status: 'failed', error_code: 'transport_rejected', attempt_count: 2 })
  expect(stored.notices[0].attempts[1]).toMatchObject({ status: 'failed', error_code: 'transport_rejected' })
  expect(stored.notice_outbox_count).toBe(0)
})
