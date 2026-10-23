/**
 * E2E tests for admin Diagnostic — Adjuntar desde Documentos flow.
 *
 * @flow:admin-diagnostic-attach-from-documents
 * Covers: button visible in Correos tab, modal lists templates and attachments,
 * NDA items appear when generated NDA exists, selection adds ref badges to
 * composer, POST body includes doc_refs.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS } from '../helpers/flow-tags.js';
import { fillRichTextSource, richTextEditorByPlaceholder } from '../helpers/editorial.js';

const DIAG_ID = 12;

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const generatedNda = {
  id: 20,
  document_type: 'confidentiality_agreement',
  document_type_display: 'Acuerdo de confidencialidad',
  title: 'Acuerdo de confidencialidad — DiagClient',
  is_generated: true,
  file: '/media/nda/nda.pdf',
};

const uploadedAttachment = {
  id: 21,
  document_type: 'other',
  document_type_display: 'Otro',
  title: 'Informe técnico adjunto',
  is_generated: false,
  file: '/media/attachments/informe.pdf',
};

const diagnosticTemplates = [
  { slug: 'diagnostico-aplicacion', title: 'Diagnóstico de Aplicación', filename: 'diagnostico-aplicacion.md' },
  { slug: 'diagnostico-tecnico',    title: 'Diagnóstico Técnico',        filename: 'diagnostico-tecnico.md' },
];

const emailDefaults = {
  recipient_email: 'client@diag.com',
  subject: 'Diagnóstico — DiagClient',
  greeting: 'Hola DiagClient',
  sections: [''],
  footer: '',
};

const emptyHistory = { results: [], total: 0, page: 1, has_next: false };

function makeDiagnostic(overrides = {}) {
  return {
    id: DIAG_ID,
    uuid: 'attach-docs-diag-uuid',
    title: 'Attach Docs Diagnostic',
    status: 'sent',
    language: 'es',
    client: { name: 'DiagClient', email: 'client@diag.com' },
    client_name: 'DiagClient',
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
    public_url: '/diagnostic/attach-docs-diag-uuid',
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
    if (apiPath === 'diagnostic-templates/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnosticTemplates) };
    }
    return null;
  };
}

test.describe('Admin Diagnostic — Adjuntar desde Documentos', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 1020, role: 'admin', is_staff: true },
    });
  });

  test('"Adjuntar desde Documentos" button is visible in the Correos tab', {
    tag: [...ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();

    await expect(page.getByRole('button', { name: /Adjuntar desde Documentos/i }))
      .toBeVisible({ timeout: 15000 });
  });

  test('clicking the button opens the AttachFromDocumentsModal', {
    tag: [...ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await expect(page.getByText('Adjuntar desde Documentos').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: /Adjuntar \(/i })).toBeVisible();
  });

  test('modal shows diagnostic template items loaded from API', {
    tag: [...ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await expect(page.getByText('Diagnóstico de Aplicación')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Diagnóstico Técnico')).toBeVisible();
  });

  test('modal shows NDA items when a generated NDA attachment exists', {
    tag: [...ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const diagnostic = makeDiagnostic({ attachments: [generatedNda] });
    await mockApi(page, baseHandler(diagnostic));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await expect(page.getByText('Acuerdo de confidencialidad (PDF)')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Acuerdo de confidencialidad (borrador)')).toBeVisible();
  });

  test('modal shows uploaded attachment items', {
    tag: [...ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const diagnostic = makeDiagnostic({ attachments: [uploadedAttachment] });
    await mockApi(page, baseHandler(diagnostic));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await expect(page.getByText('Informe técnico adjunto')).toBeVisible({ timeout: 5000 });
  });

  test('selecting a document and confirming adds a ref badge to the composer', {
    tag: [...ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await page.getByLabel('Diagnóstico de Aplicación').check();

    const confirmBtn = page.getByRole('button', { name: /Adjuntar \(1\)/i });
    await expect(confirmBtn).toBeEnabled();
    await confirmBtn.click();

    // The dialog should close (the button with the same label stays visible).
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 3000 });
    // A "Documento" badge label appears inside the doc_ref attachment chip
    await expect(page.locator('span', { hasText: 'Documento' }).first()).toBeVisible();
  });

  test('POST to email/send/ includes doc_refs when a ref is selected', {
    tag: [...ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let capturedDocRefs = null;

    await mockApi(page, async ({ apiPath, method, route }) => {
      const base = await baseHandler(makeDiagnostic())({ apiPath, method, route });
      if (base) return base;
      if (apiPath === `diagnostics/${DIAG_ID}/email/send/` && method === 'POST') {
        const body = await route.request().postData();
        capturedDocRefs = body && body.includes('doc_refs') ? body : null;
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'sent' }) };
      }
      return null;
    });

    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Correos' }).click();

    // Fill section text before opening modal to avoid reactivity race on close
    await fillRichTextSource(
      richTextEditorByPlaceholder(page, 'Escribe el contenido de esta sección...'),
      'Contenido del correo de prueba.',
    );

    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();
    await page.getByLabel('Diagnóstico de Aplicación').check();
    await page.getByRole('button', { name: /Adjuntar \(1\)/i }).click();

    await page.getByRole('button', { name: /Enviar correo/i }).click();

    await expect(() => expect(capturedDocRefs).toBeTruthy()).toPass({ timeout: 5000 });
  });
});
