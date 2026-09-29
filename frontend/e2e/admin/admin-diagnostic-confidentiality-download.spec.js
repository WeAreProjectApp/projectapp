/**
 * E2E tests for admin Web App Diagnostics — NDA Download.
 *
 * Covers the `admin-diagnostic-confidentiality-download` flow:
 * - When a diagnostic has a generated NDA attachment, the Documentos tab
 *   shows "Descargar" and "Borrador" links and the "Editar parámetros" button.
 * - When no NDA exists, neither link is present and "No generado" + "Generar
 *   acuerdo" CTA are shown instead.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DIAGNOSTIC_CONFIDENTIALITY_DOWNLOAD } from '../helpers/flow-tags.js';

const DIAG_ID = 79;

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const ndaAttachment = {
  id: 701,
  document_type: 'confidentiality_agreement',
  document_type_display: 'Acuerdo de Confidencialidad',
  title: 'Acuerdo de Confidencialidad',
  file: '/media/diagnostics/79/nda.pdf',
  is_generated: true,
  created_at: '2026-04-14T09:00:00Z',
};

function buildDiagnostic({ withNda = true } = {}) {
  return {
    id: DIAG_ID,
    uuid: 'diag-nda-dl-uuid-7900',
    title: 'Diagnóstico — Gamma SA',
    status: 'negotiating',
    language: 'es',
    client: { id: 66, name: 'Gamma SA', email: 'contact@gamma.co' },
    client_name: 'Gamma SA',
    investment_amount: 9000000,
    currency: 'COP',
    payment_terms: {},
    duration_label: '',
    size_category: '',
    radiography: {},
    view_count: 1,
    last_viewed_at: null,
    sections: [],
    attachments: withNda ? [ndaAttachment] : [],
    confidentiality_params: withNda ? { client_full_name: 'Gamma SA' } : null,
    public_url: `/diagnostic/diag-nda-dl-uuid-7900`,
  };
}

function setupMock(page, diagnostic) {
  return mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authOk;
    if (apiPath === `diagnostics/${DIAG_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/defaults/`) {
      return { status: 200, contentType: 'application/json', body: '{}' };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/history/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], total: 0, page: 1, has_next: false }) };
    }
    return null;
  });
}

test.describe('Admin Diagnostic — NDA Download Links', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9200, role: 'admin', is_staff: true },
    });
  });

  test('shows Descargar and Borrador links when NDA has been generated', {
    tag: [...ADMIN_DIAGNOSTIC_CONFIDENTIALITY_DOWNLOAD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page, buildDiagnostic({ withNda: true }));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByText('Acuerdo de confidencialidad').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('link', { name: /Descargar|Download/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Borrador|Draft/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Editar parámetros/i })).toBeVisible();

    // Links point to the correct API endpoints.
    const downloadHref = await page.getByRole('link', { name: /Descargar|Download/i }).getAttribute('href');
    const draftHref = await page.getByRole('link', { name: /Borrador|Draft/i }).getAttribute('href');
    expect(downloadHref).toContain(`/diagnostics/${DIAG_ID}/confidentiality/pdf/`);
    expect(draftHref).toContain(`/diagnostics/${DIAG_ID}/confidentiality/draft-pdf/`);
  });

  test('shows "No generado" and "Generar acuerdo" CTA when no NDA exists', {
    tag: [...ADMIN_DIAGNOSTIC_CONFIDENTIALITY_DOWNLOAD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page, buildDiagnostic({ withNda: false }));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByText('Acuerdo de confidencialidad').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('No generado')).toBeVisible();
    await expect(page.getByRole('button', { name: /Generar acuerdo/i })).toBeVisible();

    // Neither download link is present.
    await expect(page.getByRole('link', { name: /Descargar|Download/i })).not.toBeVisible();
    await expect(page.getByRole('link', { name: /Borrador|Draft/i })).not.toBeVisible();
  });
});


test.describe('Diagnostic downloads stay in the panel', () => {
  for (const suffix of ['pdf/', 'draft-pdf/']) {
    test(`downloads NDA ${suffix} on the current screen`, {
      tag: [...ADMIN_DIAGNOSTIC_CONFIDENTIALITY_DOWNLOAD, '@role:admin', '@outcome:success'],
    }, async ({ page, context }) => {
      await setAuthLocalStorage(page, { token: 'e2e-admin-token', userAuth: { id: 9200, role: 'admin', is_staff: true } });
      await setupMock(page, buildDiagnostic());
      const bytes = Buffer.from('%PDF-1.4\nConfidencialidad\n%%EOF');
      await page.route(`**/api/diagnostics/${DIAG_ID}/confidentiality/${suffix}`, route => route.fulfill({
        status: 200, contentType: 'application/pdf', body: bytes,
        headers: { 'content-disposition': 'attachment; filename="acuerdo.pdf"' },
      }));
      await page.goto(`/es-co/panel/diagnostics/${DIAG_ID}/edit`, { waitUntil: 'domcontentloaded' });
      await page.getByRole('tab', { name: 'Documentos' }).click();
      await expect(page).toHaveURL(/\?tab=documents$/);
      const before = page.url();
      const downloadPromise = page.waitForEvent('download');

      await page.locator(`a[href="/api/diagnostics/${DIAG_ID}/confidentiality/${suffix}"]`).click();
      const download = await downloadPromise;
      const chunks = [];
      for await (const chunk of await download.createReadStream()) chunks.push(chunk);

      expect(Buffer.concat(chunks)).toEqual(bytes);
      expect(download.suggestedFilename()).toBe('acuerdo.pdf');
      expect(context.pages()).toHaveLength(1);
      expect(page.url()).toBe(before);
    });
  }
});
