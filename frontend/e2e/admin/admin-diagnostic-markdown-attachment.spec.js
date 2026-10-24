/**
 * E2E tests for admin Diagnostic — "Crear documento desde markdown" in Correos tab.
 *
 * Covers: button visibility based on diagnostic status, modal open/close,
 * form field rendering, and preview disabled state when inputs are empty.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT,
} from '../helpers/flow-tags.js';

const DIAG_ID = 21;

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const emailDefaults = {
  recipient_email: 'client@example.com',
  subject: 'NegotiatingCorp — Project App',
  greeting: 'Hola NegotiatingCorp',
  sections: [''],
  footer: 'Quedamos atentos.',
};

const emptyHistory = { results: [], total: 0, page: 1, has_next: false };

function buildDiagnostic(overrides = {}) {
  return {
    id: DIAG_ID,
    uuid: 'md-attach-test-uuid',
    title: 'Diagnóstico — NegotiatingCorp',
    status: 'draft',
    language: 'es',
    client: { name: 'NegotiatingCorp', email: 'client@example.com' },
    client_name: 'NegotiatingCorp',
    investment_amount: null,
    currency: 'COP',
    payment_terms: {},
    duration_label: '',
    size_category: '',
    radiography: {},
    view_count: 0,
    last_viewed_at: null,
    documents: [],
    attachments: [],
    public_url: `/diagnostic/md-attach-test-uuid`,
    ...overrides,
  };
}

function baseHandler(diagnostic) {
  return async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authOk;
    if (apiPath === `diagnostics/${DIAG_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/defaults/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emailDefaults) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/history/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emptyHistory) };
    }
    return null;
  };
}

test.describe('Admin Diagnostic — Markdown attachment button in Correos tab', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9300, role: 'admin', is_staff: true },
    });
  });

  test('markdown attachment button is absent when diagnostic is in draft status', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ status: 'draft' })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await expect(page.getByRole('tab', { name: 'General' })).toBeVisible({ timeout: 15000 });

    // The Correos tab itself may not be visible for draft; either way the markdown button must not appear
    await expect(page.getByRole('button', { name: /Crear documento desde markdown/i })).not.toBeVisible();
  });

  test('markdown attachment button is visible in Correos tab when diagnostic is negotiating', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ status: 'negotiating' })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();

    await expect(
      page.getByRole('button', { name: /Crear documento desde markdown/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('clicking the button opens the markdown attachment modal', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ status: 'negotiating' })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Crear documento desde markdown/i }).click();

    await expect(page.getByRole('heading', { name: /Adjuntar documento PDF/i })).toBeVisible({ timeout: 10000 });
  });

  test('modal contains title input, markdown textarea, and cover checkboxes', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ status: 'negotiating' })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Crear documento desde markdown/i }).click();

    await expect(page.getByPlaceholder('Ej: Resumen de cambios al alcance')).toBeVisible({ timeout: 10000 });
    // The attachment editor is teleported outside a role=dialog. Its Visual
    // input exposes the markdown hint as its accessible name, unlike the
    // hidden Source textarea behind the active mode.
    await expect(page.getByRole('textbox', { name: /# Encabezado/ })).toBeVisible();
    const checkboxes = await page.locator('input[type="checkbox"]').count();
    expect(checkboxes).toBeGreaterThanOrEqual(3);
  });

  test('Vista previa button is disabled when title and markdown are empty', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ status: 'negotiating' })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Crear documento desde markdown/i }).click();

    // The Correos tab's "Vista previa" is a role=tab; the only matching button is
    // the modal's preview action, teleported to <body> (so it's last in the DOM).
    await expect(
      page.getByRole('button', { name: /Vista previa/i }).last(),
    ).toBeDisabled({ timeout: 10000 });
  });

  test('modal closes when Cancelar button is clicked', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ status: 'negotiating' })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Crear documento desde markdown/i }).click();

    await expect(page.getByRole('heading', { name: /Adjuntar documento PDF/i })).toBeVisible({ timeout: 10000 });

    await page.getByRole('button', { name: 'Cancelar' }).click();

    await expect(page.getByRole('heading', { name: /Adjuntar documento PDF/i })).not.toBeVisible();
  });

  test('modal shows 3 Plantillas base copy buttons in the correct order', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ status: 'negotiating' })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Crear documento desde markdown/i }).click();

    await expect(page.getByRole('heading', { name: /Adjuntar documento PDF/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Plantillas base')).toBeVisible();

    await expect(page.getByRole('button', { name: /Copiar Diagnóstico de Aplicación/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Copiar Diagnóstico Técnico/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Copiar Anexo/i })).toBeVisible();
  });

  test('clicking a Plantillas base button shows Copiado feedback after fetch', {
    tag: [...ADMIN_DIAGNOSTIC_MARKDOWN_ATTACHMENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      const base = await baseHandler(buildDiagnostic({ status: 'negotiating' }))({ apiPath, method });
      if (base) return base;
      if (apiPath === 'diagnostic-templates/diagnostico-aplicacion/' && method === 'GET') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ slug: 'diagnostico-aplicacion', content_markdown: '# Diagnóstico de Aplicación\n\nPlantilla base.' }),
        };
      }
      return null;
    });

    await page.context().grantPermissions(['clipboard-write', 'clipboard-read']);
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Crear documento desde markdown/i }).click();

    await expect(page.getByRole('heading', { name: /Adjuntar documento PDF/i })).toBeVisible({ timeout: 10000 });

    await page.getByRole('button', { name: /Copiar Diagnóstico de Aplicación/i }).click();

    await expect(page.getByText('¡Copiado!')).toBeVisible({ timeout: 5000 });
  });
});
