/**
 * E2E tests for admin Web App Diagnostics — Correos tab (email composer)
 * and Documentos tab (attachment management).
 *
 * Covers: email tab renders composer + history; documents tab renders upload
 * form and send-to-client button behaviour.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_DIAGNOSTIC_EMAIL,
  ADMIN_DIAGNOSTIC_DOCUMENTS,
} from '../helpers/flow-tags.js';

const DIAG_ID = 11;

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const emailDefaults = {
  recipient_email: 'client@example.com',
  subject: 'TechCorp, seguimiento de tu diagnóstico — Project App',
  greeting: 'Hola TechCorp',
  sections: [''],
  footer: 'Quedamos atentos a tus comentarios.',
};

const emptyHistory = { results: [], total: 0, page: 1, has_next: false };

function buildDiagnostic(overrides = {}) {
  return {
    id: DIAG_ID,
    uuid: 'diag-email-test-uuid-1234',
    title: 'Diagnóstico — TechCorp',
    status: 'negotiating',
    language: 'es',
    client: { name: 'TechCorp', email: 'client@example.com' },
    client_name: 'TechCorp',
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
    public_url: `/diagnostic/diag-email-test-uuid-1234`,
    ...overrides,
  };
}

function baseHandler(diagnostic, extra = {}) {
  return async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return authOk;
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/defaults/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emailDefaults) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/history/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emptyHistory) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/attachments/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    for (const [path, response] of Object.entries(extra)) {
      if (apiPath === path && (!response.method || response.method === method)) {
        return response;
      }
    }
    return null;
  };
}

// ── Email composer tab ────────────────────────────────────────────────────────

test.describe('Admin Diagnostic — Correos tab', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9100, role: 'admin', is_staff: true },
    });
  });

  test('Correos tab is visible on the edit page', {
    tag: [...ADMIN_DIAGNOSTIC_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await expect(page.getByRole('tab', { name: 'Correos' })).toBeVisible({ timeout: 15000 });
  });

  test('email composer renders recipient, subject, and sections fields', {
    tag: [...ADMIN_DIAGNOSTIC_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();

    await expect(page.getByTestId('diagnostic-email-to')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('input[placeholder*="Asunto"]')).toBeVisible();
    await expect(page.getByText('Secciones del correo')).toBeVisible();
    await expect(page.getByText('Agregar sección')).toBeVisible();
  });

  test('email defaults populate recipient and subject on mount', {
    tag: [...ADMIN_DIAGNOSTIC_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();

    await expect(page.getByTestId('diagnostic-email-to-field')).toContainText(
      'TechCorp · client@example.com',
      { timeout: 10000 },
    );
  });

  test('email history section renders after tab loads', {
    tag: [...ADMIN_DIAGNOSTIC_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();

    await expect(page.getByText('Historial de correos')).toBeVisible({ timeout: 10000 });
  });

  test('send button is disabled when sections textarea is empty', {
    tag: [...ADMIN_DIAGNOSTIC_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Correos' }).click();

    await expect(page.getByRole('button', { name: /Enviar correo/i })).toBeDisabled({ timeout: 10000 });
  });

  test('POST to email/send/ is called when form is filled and send is clicked', {
    tag: [...ADMIN_DIAGNOSTIC_EMAIL, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let sendCalled = false;
    let sendBody = '';
    await mockApi(page, async ({ apiPath, method, route }) => {
      const base = await baseHandler(buildDiagnostic())({ apiPath, method });
      if (base) return base;
      if (apiPath === `diagnostics/${DIAG_ID}/email/send/` && method === 'POST') {
        sendCalled = true;
        sendBody = route.request().postData() || '';
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'sent' }) };
      }
      return null;
    });

    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Correos' }).click();

    const toInput = page.getByTestId('diagnostic-email-to');
    await toInput.fill('stakeholder@example.com');
    await toInput.press('Enter');
    await page.getByTestId('diagnostic-email-show-cc').click();
    const ccInput = page.getByTestId('diagnostic-email-cc');
    await ccInput.fill('copy@example.com');
    await ccInput.press('Enter');
    await page.getByPlaceholder('Escribe el contenido de esta sección...').fill('Este es el cuerpo del correo de seguimiento.');
    await page.getByRole('button', { name: /Enviar correo/i }).click();

    await expect(() => expect(sendCalled).toBe(true)).toPass({ timeout: 5000 });
    expect(sendBody).toContain('client@example.com');
    expect(sendBody).toContain('stakeholder@example.com');
    expect(sendBody).toContain('copy@example.com');
  });

  test('recipient validation rejects an address repeated between To and CC', {
    tag: [...ADMIN_DIAGNOSTIC_EMAIL, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Correos' }).click();

    await page.getByTestId('diagnostic-email-show-cc').click();
    const ccInput = page.getByTestId('diagnostic-email-cc');
    await ccInput.fill('client@example.com');
    await ccInput.press('Enter');

    await expect(page.getByText('client@example.com ya está agregado en otro campo.')).toBeVisible();
    await expect(page.getByTestId('diagnostic-email-recipient-count')).toHaveText('1/10 destinatarios entre Para y CC');
  });

});

// ── Documents tab ─────────────────────────────────────────────────────────────

test.describe('Admin Diagnostic — Documentos tab', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9100, role: 'admin', is_staff: true },
    });
  });

  test('Documentos tab is visible on the edit page', {
    tag: [...ADMIN_DIAGNOSTIC_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible({ timeout: 15000 });
  });

  test('documents tab renders Documentos list and uploader', {
    tag: [...ADMIN_DIAGNOSTIC_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic()));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);

    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByRole('heading', { name: 'Documentos', exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: 'Documentos adjuntos' })).toBeVisible();
  });

  test('NDA row offers "Generar acuerdo" when none has been generated', {
    tag: [...ADMIN_DIAGNOSTIC_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(buildDiagnostic({ attachments: [] })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByText('Acuerdo de confidencialidad')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('PDF · No generado')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Generar acuerdo' })).toBeVisible();
    await expect(page.getByRole('link', { name: /Descargar PDF|Download PDF/ })).toBeHidden();
  });

  test('a generated NDA exposes download, draft and edit-params actions', {
    tag: [...ADMIN_DIAGNOSTIC_DOCUMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const ndaAttachment = {
      id: 77,
      file_name: 'acuerdo-confidencialidad.pdf',
      document_type: 'confidentiality_agreement',
      is_generated: true,
      created_at: '2026-05-02T10:00:00Z',
      file_url: '/media/diagnostics/acuerdo.pdf',
    };
    await mockApi(page, baseHandler(buildDiagnostic({ attachments: [ndaAttachment] })));
    await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByText('Acuerdo de confidencialidad')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: /Descargar PDF|Download PDF/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Borrador|Draft/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Editar parámetros' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Generar acuerdo' })).toBeHidden();
  });
});
