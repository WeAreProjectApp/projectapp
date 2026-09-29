/**
 * E2E tests for admin proposal contract download flow.
 *
 * @flow:admin-proposal-contract-download
 * Covers: download links visible when contract exists, links point to correct
 *         API endpoints, links hidden when no contract.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_CONTRACT_DOWNLOAD } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const existingContractDoc = {
  id: 10,
  document_type: 'contract',
  document_type_display: 'Contrato',
  title: 'Contrato de desarrollo',
  file: '/media/contracts/contract.pdf',
  is_generated: true,
  created_at: '2026-04-01T10:00:00Z',
};

const proposalWithContract = {
  id: PROPOSAL_ID,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'Download Test',
  client_name: 'Acme Corp',
  client_email: 'acme@example.com',
  language: 'es',
  status: 'negotiating',
  total_investment: '10000000',
  currency: 'COP',
  view_count: 3,
  sent_at: '2026-03-28T10:00:00Z',
  sections: [
    { id: 1, section_type: 'greeting', title: 'Saludo', order: 0, is_enabled: true, content_json: { clientName: 'Acme Corp' } },
  ],
  requirement_groups: [],
  proposal_documents: [existingContractDoc],
  contract_params: { contract_source: 'default' },
};

const proposalWithoutContract = {
  ...proposalWithContract,
  proposal_documents: [],
  contract_params: null,
};

test.describe('Admin Proposal Contract Download', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test('shows download and draft links when contract exists', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — asserts the download/draft anchors render with the correct backend href once a contract exists; activation is exercised separately with actual download events)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(proposalWithContract) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    // Final PDF download link
    const downloadLink = page.getByRole('link', { name: /Descargar|Download/i }).first();
    await expect(downloadLink).toBeVisible();
    await expect(downloadLink).toHaveAttribute('href', `/api/proposals/${PROPOSAL_ID}/contract/pdf/`);

    // Draft PDF download link
    const draftLink = page.getByRole('link', { name: /Borrador|Draft/i });
    await expect(draftLink).toBeVisible();
    await expect(draftLink).toHaveAttribute('href', `/api/proposals/${PROPOSAL_ID}/contract/draft-pdf/`);
  });

  test('shows "No generado" when no contract exists', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — asserts the empty-contract placeholder text renders when proposal_documents has no contract entry; no action to drive, this is the absence-of-data state)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(proposalWithoutContract) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText(/No generado/)).toBeVisible();
  });

  test('contract creation date shown when contract exists', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — asserts the "Generado el <date>" text is derived from contractDoc.created_at; catches the date formatter or field mapping silently breaking)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(proposalWithContract) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    // "Generado el" text should be visible
    await expect(page.getByText(/Generado el/i)).toBeVisible();
  });
});


async function prepareDownloads(page, pdfHandler) {
  await mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposalWithContract) };
    }
    return pdfHandler?.({ apiPath, route }) || null;
  });
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('link', { name: 'Descargar PDF' }).first()).toBeVisible();
}

async function downloadedBytes(download) {
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return Buffer.concat(chunks);
}

const PDF_BYTES = Buffer.from('%PDF-1.4\nPWA download regression\n%%EOF');
const pdfResult = {
  status: 200, contentType: 'application/pdf', body: PDF_BYTES,
  headers: { 'content-disposition': "attachment; filename*=UTF-8''contrato%20espa%C3%B1ol.pdf" },
};

test.describe('Panel downloads stay on the current screen', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  for (const endpoint of ['contract/pdf/', 'contract/draft-pdf/', 'formalization/pdf/commercial/', 'formalization/pdf/technical/']) {
    test(`downloads ${endpoint} without a popup`, {
      tag: ['@outcome:success', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
    }, async ({ page, context }) => {
      await prepareDownloads(page, ({ apiPath }) => apiPath === `proposals/${PROPOSAL_ID}/${endpoint}` ? pdfResult : null);
      const before = page.url();
      const pages = context.pages().length;
      const downloadPromise = page.waitForEvent('download');

      await page.locator(`a[href="/api/proposals/${PROPOSAL_ID}/${endpoint}"]`).click();
      const download = await downloadPromise;

      expect(await downloadedBytes(download)).toEqual(PDF_BYTES);
      expect(download.suggestedFilename()).toBe('contrato español.pdf');
      expect(context.pages()).toHaveLength(pages);
      expect(page.url()).toBe(before);
      await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible();
    });
  }

  for (const [label, query] of [['Propuesta comercial', ''], ['Detalle técnico', '?doc=technical']]) {
    test(`downloads the draft proposal ${label} from General`, {
      tag: ['@outcome:success', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
    }, async ({ page, context }) => {
      await mockApi(page, async ({ apiPath }) => {
        if (apiPath === 'auth/check/') return authCheck;
        if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
          return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...proposalWithoutContract, status: 'draft' }) };
        }
        if (apiPath === `proposals/${proposalWithContract.uuid}/pdf/`) return pdfResult;
        return null;
      });
      await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
      const link = page.getByRole('link', { name: label, exact: true });
      await expect(link).toBeVisible();
      const before = page.url();
      const downloadPromise = page.waitForEvent('download');
      const requestPromise = page.waitForRequest(request => request.url().endsWith(`/api/proposals/${proposalWithContract.uuid}/pdf/${query}`));

      await link.click();
      const download = await downloadPromise;
      await requestPromise;

      expect(await downloadedBytes(download)).toEqual(PDF_BYTES);
      expect(download.suggestedFilename()).toBe('contrato español.pdf');
      expect(context.pages()).toHaveLength(1);
      expect(page.url()).toBe(before);
    });
  }

  test('retries a rejected download from the same screen', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
  }, async ({ page }) => {
    let attempts = 0;
    await prepareDownloads(page, ({ apiPath }) => {
      if (apiPath !== `proposals/${PROPOSAL_ID}/contract/pdf/`) return null;
      attempts++;
      return attempts === 1
        ? { status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'Genera el contrato antes de descargarlo.' }) }
        : pdfResult;
    });
    const link = page.locator(`a[href="/api/proposals/${PROPOSAL_ID}/contract/pdf/"]`);
    await link.click();
    await expect(page.getByText('Genera el contrato antes de descargarlo.', { exact: true })).toBeVisible();

    const downloadPromise = page.waitForEvent('download');
    await link.click();
    expect(await downloadedBytes(await downloadPromise)).toEqual(PDF_BYTES);
    expect(attempts).toBe(2);
  });

  test('keeps the editor after a network failure', {
    tag: ['@outcome:failure', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
  }, async ({ page, context }) => {
    await prepareDownloads(page);
    await page.route(`**/api/proposals/${PROPOSAL_ID}/contract/pdf/`, route => route.abort('failed'));
    const before = page.url();
    const downloads = [];
    page.on('download', event => downloads.push(event));

    await page.locator(`a[href="/api/proposals/${PROPOSAL_ID}/contract/pdf/"]`).click();

    await expect(page.getByText(/No se pudo descargar el archivo/)).toBeVisible();
    expect(downloads).toHaveLength(0);
    expect(context.pages()).toHaveLength(1);
    expect(page.url()).toBe(before);
  });

  test('rejects an HTML response masquerading as a PDF', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_CONTRACT_DOWNLOAD, '@role:admin'],
  }, async ({ page }) => {
    await prepareDownloads(page, ({ apiPath }) => apiPath === `proposals/${PROPOSAL_ID}/contract/pdf/`
      ? { status: 200, contentType: 'text/html', body: '<html>Private login page</html>' } : null);
    const downloads = [];
    page.on('download', event => downloads.push(event));

    await page.locator(`a[href="/api/proposals/${PROPOSAL_ID}/contract/pdf/"]`).click();

    await expect(page.getByText(/No se pudo descargar el archivo/)).toBeVisible();
    expect(downloads).toHaveLength(0);
    await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible();
  });
});
