/** Public PDF downloads, including expiry and recoverable failures. */
import { readFile } from 'node:fs/promises';
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_DOWNLOAD_PDF } from '../helpers/flow-tags.js';

test.describe.configure({ timeout: 60_000 });
const UUID = 'dddddddd-dddd-dddd-dddd-dddddddddddd';
const pdfBytes = '%PDF-1.4 download fixture';
const proposal = {
  id: 1, uuid: UUID, title: 'PDF Test', client_name: 'Client', status: 'sent',
  language: 'es', total_investment: '100000', currency: 'COP', created_at: '2026-03-01T12:00:00Z',
  sections: [
    { id: 1, section_type: 'greeting', title: 'Hola', order: 0, is_enabled: true, content_json: { clientName: 'Client' } },
    { id: 2, section_type: 'technical_document', title: 'Detalle técnico', order: 1, is_enabled: true, content_json: { purpose: 'Scope of the technical document', stack: [{ layer: 'Backend', technology: 'Django' }] } },
  ],
  requirement_groups: [],
};
const expiredMessage = 'Esta propuesta está vencida. Solicita una versión actualizada para descargar el PDF.';

async function openProposal(page, mode, data = proposal, pdfStatus = 200) {
  await page.addInitScript(() => localStorage.setItem('proposal_onboarding_seen', 'true'));
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === `proposals/${UUID}/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(data) };
    }
    if (apiPath.startsWith(`proposals/${UUID}/pdf/`)) {
      return { status: pdfStatus, contentType: pdfStatus === 200 ? 'application/pdf' : 'application/json', body: pdfStatus === 200 ? pdfBytes : '{"code":"proposal_expired"}' };
    }
    return null;
  });
  await page.goto(`/en-us/proposal/${UUID}?mode=${mode}`, { waitUntil: 'domcontentloaded' });
}

for (const [mode, prefix] of [['detailed', 'Propuesta_Comercial'], ['technical', 'Detalle_Tecnico']]) {
  test(`downloads the ${mode} PDF file`, {
    tag: [...PROPOSAL_DOWNLOAD_PDF, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await openProposal(page, mode);
    const filePromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Descargar PDF', exact: true }).click();
    const file = await filePromise;

    expect(file.suggestedFilename()).toContain(prefix);
    expect(await readFile(await file.path(), 'utf8')).toBe(pdfBytes);
  });

  test(`explains why an expired ${mode} PDF is unavailable`, {
    tag: [...PROPOSAL_DOWNLOAD_PDF, '@role:guest', '@outcome:error'],
  }, async ({ page }) => {
    await openProposal(page, mode, { ...proposal, status: 'expired', expired_meta: { expired_at: '2026-09-25T00:00:00Z' } });
    await page.getByRole('button', { name: 'Descargar PDF', exact: true }).hover();

    await expect(page.getByRole('button', { name: 'Descargar PDF', exact: true })).toBeDisabled();
    await expect(page.getByRole('status')).toHaveText(expiredMessage);
  });
}

test('explains expiry received after opening the proposal', {
  tag: [...PROPOSAL_DOWNLOAD_PDF, '@role:guest', '@outcome:error'],
}, async ({ page }) => {
  await openProposal(page, 'detailed', proposal, 410);

  await page.getByRole('button', { name: 'Descargar PDF', exact: true }).click();

  await expect(page.getByRole('status')).toHaveText(expiredMessage);
  await expect(page.getByRole('button', { name: 'Descargar PDF', exact: true })).toBeDisabled();
});

test('retries a failed PDF download', {
  tag: [...PROPOSAL_DOWNLOAD_PDF, '@role:guest', '@outcome:failure'],
}, async ({ page }) => {
  await openProposal(page, 'detailed', proposal, 500);
  await page.getByRole('button', { name: 'Descargar PDF', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('No se pudo descargar el PDF. Inténtalo nuevamente.');
  await page.route(`**/api/proposals/${UUID}/pdf/`, route => route.fulfill({ contentType: 'application/pdf', body: pdfBytes }));

  const filePromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Descargar PDF', exact: true }).click();
  const file = await filePromise;

  expect(await readFile(await file.path(), 'utf8')).toBe(pdfBytes);
  await expect(page.getByRole('status')).toHaveCount(0);
});
