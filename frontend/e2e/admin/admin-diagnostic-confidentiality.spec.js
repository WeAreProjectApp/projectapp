/**
 * E2E tests for admin Web App Diagnostics — Acuerdo de Confidencialidad (NDA).
 *
 * Covers the `admin-diagnostic-confidentiality-generate` flow: admin opens the
 * Documentos tab on a diagnostic with no NDA, clicks "Generar acuerdo", fills
 * the ConfidentialityParamsModal, and submits. Happy path: POST succeeds, the
 * section switches to the generated state. Error path: server returns 400, the
 * modal stays open and surfaces the error.
 *
 * Mechanical scope only — PDF content correctness is out of scope here.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DIAGNOSTIC_CONFIDENTIALITY_GENERATE } from '../helpers/flow-tags.js';

const DIAG_ID = 77;

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

function buildDiagnostic(overrides = {}) {
  return {
    id: DIAG_ID,
    uuid: 'diag-nda-uuid-7777',
    title: 'Diagnóstico — Acme Corp',
    status: 'negotiating',
    language: 'es',
    client: { name: 'Acme Corp', email: 'client@acme.test' },
    client_name: 'Acme Corp',
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
    confidentiality_params: null,
    public_url: `/diagnostic/diag-nda-uuid-7777`,
    ...overrides,
  };
}

function baseHandler(diagnostic) {
  return async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authOk;
    if (apiPath === `diagnostics/${DIAG_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(diagnostic) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/attachments/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/defaults/`) {
      return { status: 200, contentType: 'application/json', body: '{}' };
    }
    if (apiPath === `diagnostics/${DIAG_ID}/email/history/`) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], total: 0, page: 1, has_next: false }),
      };
    }
    return null;
  };
}

// The modal is rendered via <Teleport to="body">, outside the page's normal
// DOM tree — scope all modal locators through this root so assertions can't
// collide with the Documentos tab section header (which uses the same phrase
// in different casing: "Acuerdo de confidencialidad" vs modal's "Acuerdo de
// Confidencialidad").
const modalRoot = (page) => page.locator('div.z-\\[9999\\]').filter({
  has: page.getByRole('heading', { level: 2 }),
});

async function openNdaModal(page) {
  await page.goto(`/panel/diagnostics/${DIAG_ID}/edit`);
  await page.getByRole('tab', { name: 'Documentos' }).click();
  // Tab section header (h3).
  await expect(page.getByText('Acuerdo de confidencialidad').first()).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: 'Generar acuerdo' }).click();
  // Modal header (h2).
  await expect(modalRoot(page).locator('h2', { hasText: 'Acuerdo de Confidencialidad' })).toBeVisible();
}

test.describe('Admin Diagnostic — Generar NDA', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9200, role: 'admin', is_staff: true },
    });
  });

  test('submits ConfidentialityParamsModal and switches section to generated state', {
    tag: [...ADMIN_DIAGNOSTIC_CONFIDENTIALITY_GENERATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let capturedPayload = null;
    const generatedAttachment = {
      id: 501,
      document_type: 'confidentiality_agreement',
      document_type_display: 'Acuerdo de Confidencialidad',
      title: 'Acuerdo de Confidencialidad',
      file_url: '/media/diagnostics/77/nda.pdf',
      is_generated: true,
      created_at: '2026-04-16T12:00:00Z',
    };

    await mockApi(page, async ({ apiPath, method, route }) => {
      if (apiPath === `diagnostics/${DIAG_ID}/confidentiality/params/` && method === 'POST') {
        capturedPayload = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            confidentiality_params: capturedPayload.confidentiality_params,
            attachment: generatedAttachment,
          }),
        };
      }
      return baseHandler(buildDiagnostic())({ apiPath, method });
    });

    await openNdaModal(page);

    const modal = modalRoot(page);

    // Consultor section pre-fills Project App SAS.
    const contractorSection = modal.locator('section').filter({ has: page.locator('h3', { hasText: 'Consultor' }) });
    const contractorName = contractorSection.getByLabel('Razón social / Nombre', { exact: true });
    await expect(contractorName).toHaveValue('Project App SAS');

    const contractCity = modal.getByLabel('Ciudad', { exact: true });
    await expect(contractCity).toHaveValue('Medellín');

    const penalClause = modal.getByLabel('Cláusula penal (valor)', { exact: true });
    await expect(penalClause).toHaveValue(
      'CINCUENTA SALARIOS MÍNIMOS MENSUALES LEGALES VIGENTES (50 SMMLV)',
    );

    // Fill client block.
    const clientSection = modal.locator('section').filter({ has: page.locator('h3', { hasText: 'Cliente' }) });
    await clientSection.getByLabel('Razón social / Nombre', { exact: true })
      .fill('Acme Corp SAS');
    await modal.getByLabel('NIT / C.C.', { exact: true })
      .fill('900.123.456-7');

    // The consultant must be identified by one of its two documents; the
    // defaults do not carry either, so the save is gated until one is filled.
    await contractorSection.getByLabel('NIT', { exact: true })
      .fill('1021513348-7');

    await page.getByRole('button', { name: 'Guardar y generar PDF' }).click();

    // Modal closes → generated state renders Descargar / Borrador / Editar parámetros.
    await expect(modal).toBeHidden({ timeout: 10000 });
    await expect(page.getByRole('link', { name: /Descargar|Download/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Borrador|Draft/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Editar parámetros/i })).toBeVisible();

    // Wire payload sanity check: client fields sent, defaults preserved.
    expect(capturedPayload).not.toBeNull();
    expect(capturedPayload.confidentiality_params).toMatchObject({
      client_full_name: 'Acme Corp SAS',
      client_cedula: '900.123.456-7',
      contractor_full_name: 'Project App SAS',
      contractor_nit: '1021513348-7',
      contract_city: 'Medellín',
      contractor_email: 'team@projectapp.co',
    });
  });

  test('blocks the save when the consultant has no NIT and no cédula', {
    tag: [...ADMIN_DIAGNOSTIC_CONFIDENTIALITY_GENERATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    let postCount = 0;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === `diagnostics/${DIAG_ID}/confidentiality/params/` && method === 'POST') {
        postCount += 1;
        return { status: 200, contentType: 'application/json', body: JSON.stringify({}) };
      }
      return baseHandler(buildDiagnostic())({ apiPath, method });
    });

    await openNdaModal(page);

    // Neither consultant document is prefilled by DEFAULTS.
    await page.getByRole('button', { name: 'Guardar y generar PDF' }).click();

    await expect(page.getByText('Indica el NIT o la cédula del consultor')).toBeVisible();
    await expect(modalRoot(page)).toBeVisible();
    expect(postCount).toBe(0);
  });

  test('surfaces server error when POST /confidentiality/params/ returns 400', {
    tag: [...ADMIN_DIAGNOSTIC_CONFIDENTIALITY_GENERATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === `diagnostics/${DIAG_ID}/confidentiality/params/` && method === 'POST') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Datos inválidos para generar el PDF.' }),
        };
      }
      return baseHandler(buildDiagnostic())({ apiPath, method });
    });

    await openNdaModal(page);

    // Satisfy the client-side identity gate so the request actually fires and
    // the server error is what we end up asserting on.
    await modalRoot(page).locator('section')
      .filter({ has: page.locator('h3', { hasText: 'Consultor' }) })
      .getByLabel('NIT', { exact: true })
      .fill('1021513348-7');

    await page.getByRole('button', { name: 'Guardar y generar PDF' }).click();

    // Modal stays open and shows the error text returned by the API.
    await expect(modalRoot(page)).toBeVisible();
    await expect(page.getByText('Datos inválidos para generar el PDF.')).toBeVisible({ timeout: 10000 });
  });
});
