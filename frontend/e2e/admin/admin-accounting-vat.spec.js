/**
 * E2E coverage for IVA capture in accounting forms and collection previews.
 *
 * FLOWS: admin-accounting-income-crud, admin-accounting-expenses-crud,
 *        admin-accounting-collection-create
 *
 * The preview boundary deliberately returns the exact email/PDF totals that
 * the server calculates. This spec drives the panel form and verifies that it
 * carries the selected IVA contract through to that server-owned preview.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_ACCOUNTING_COLLECTION_CREATE,
  ADMIN_ACCOUNTING_EXPENSES_CRUD,
  ADMIN_ACCOUNTING_INCOME_CRUD,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const CLIENT = {
  id: 5,
  name: 'Ana Pérez',
  email: 'ana@acme.test',
  phone: '',
  company: 'Acme Soluciones',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
};

const VAT_INCOME = {
  id: 8,
  concept: 'Implementación con IVA',
  kind: 'expected',
  kind_label: 'Esperado',
  period: '2026-10',
  period_label: 'Octubre 2026',
  period_date: '2026-10-01',
  destination: 'partners',
  destination_label: 'Socios',
  ledger: 'company',
  ledger_label: 'Empresa',
  total_amount: '1190000.00',
  vat_rate: '19.00',
  gustavo_amount: '595000.00',
  carlos_amount: '595000.00',
  company_amount: '0.00',
  paid_amount: '0.00',
  pending_amount: '1190000.00',
  payment_status: 'pending',
  payment_status_label: 'Pendiente',
  client: 5,
  client_name: 'Ana Pérez',
  project: null,
  project_name: null,
  origin: 'development',
  origin_label: 'Desarrollo',
  notes: '',
};

const PREVIEW_PDF_URL = '/api/accounting/collection-accounts/preview/vat-e2e/PA-ACME-001.pdf';
const PANEL_PATH = '/es-co/panel/accounting';

function accountingHandler(calls, { incomeCreateStatus = 201 } = {}) {
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { username: 'admin', is_staff: true, is_superuser: true } }),
      };
    }
    if (apiPath === 'accounting/settings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ income_default_view_mode: 'classic' }),
      };
    }
    if (apiPath === 'accounting/receivables/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], summary: {} }) };
    }
    if (apiPath === 'accounting/incomes/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [VAT_INCOME], meta: {} }),
      };
    }
    if (apiPath === 'accounting/incomes/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (incomeCreateStatus !== 201) {
        return {
          status: incomeCreateStatus,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'El IVA no es válido.', code: 'invalid_vat' }),
        };
      }
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...VAT_INCOME, id: 99, ...body }),
      };
    }
    if (apiPath === 'accounting/expenses/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], meta: {} }) };
    }
    if (apiPath === 'accounting/expenses/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return { status: 201, contentType: 'application/json', body: JSON.stringify({ id: 77, ...body }) };
    }
    if (apiPath.startsWith('proposals/client-profiles/search/') && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([CLIENT]) };
    }
    if (apiPath.startsWith('proposals/client-profiles/5/projects/') && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    if (apiPath.startsWith('accounting/collection-accounts/next-number/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ suggested_number: 'PA-ACME-001', billing_code: 'ACME', issuer_city: 'Bogotá' }),
      };
    }
    if (apiPath === 'accounting/collection-accounts/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], meta: { issued_count: 0, issued_total: '0.00', paid_count: 0, paid_total: '0.00', cancelled_count: 0 } }),
      };
    }
    if (apiPath === 'accounting/collection-accounts/preview/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          subject: 'Cuenta de cobro PA-ACME-001 — Implementación con IVA',
          customer_email: CLIENT.email,
          public_number: 'PA-ACME-001',
          total: '1190000.00',
          pdf_url: PREVIEW_PDF_URL,
          html_body: [
            '<main>',
            '<p>Valor antes de IVA: $1.000.000 COP</p>',
            '<p>IVA (19%): $190.000 COP</p>',
            '<p>Total a pagar: $1.190.000 COP</p>',
            '</main>',
          ].join(''),
        }),
      };
    }
    if (apiPath === PREVIEW_PDF_URL.replace(/^\/api\//, '') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/pdf',
        headers: { 'Content-Disposition': 'inline; filename="PA-ACME-001.pdf"' },
        body: '%PDF-1.4\n%%EOF\n',
      };
    }
    return null;
  };
}

async function authenticate(page) {
  await setAuthLocalStorage(page, {
    token: 'e2e-vat-token',
    userAuth: { id: 9001, role: 'admin', is_staff: true },
  });
  await page.addInitScript(() => localStorage.setItem('preferred_locale', 'es-co'));
}

test.describe('Admin accounting VAT', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
  });

  // Bug caught: a company income could silently treat a pre-tax value as a total,
  // understating both its total payable and partner distribution.
  test('income converts a before-VAT amount into its total', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, accountingHandler(calls));
    await page.goto(`${PANEL_PATH}/incomes?accounting_incomeTab=all`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Ingresos', exact: true })).toBeVisible();

    await page.getByTestId('incomes-new-button').click();
    await expect(page.getByRole('heading', { name: 'Nuevo ingreso' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Total con IVA' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('vat-rate')).toHaveValue('19');

    await page.getByTestId('income-form-concept').fill('Desarrollo octubre con IVA');
    await page.getByRole('tab', { name: 'Desarrollo' }).click();
    await page.getByTestId('income-form-period').fill('2026-10-01');
    await page.getByRole('tab', { name: 'Antes de IVA' }).click();
    await page.getByTestId('partner-split-total').fill('1000000');

    await expect(page.getByTestId('vat-base')).toHaveText('$1.000.000 COP');
    await expect(page.getByTestId('vat-tax')).toHaveText('$190.000 COP');
    await expect(page.getByTestId('vat-total')).toHaveText('$1.190.000 COP');

    await page.getByTestId('income-form-submit').click();
    await expect(page.getByText('Ingreso creado')).toContainText('Ingreso creado');
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toMatchObject({ amount: 1000000, amount_mode: 'before_vat', vat_rate: 19 });
  });

  // Bug caught: a zero-rate expense could become an unknown tax state and stop
  // accounting users from distinguishing an explicit Sin IVA expense.
  test('expense keeps its zero VAT choice on save', {
    tag: [...ADMIN_ACCOUNTING_EXPENSES_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, accountingHandler(calls));
    await page.goto(`${PANEL_PATH}/expenses`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Gastos', exact: true })).toBeVisible();

    await page.getByTestId('expenses-new-button').click();
    await expect(page.getByRole('heading', { name: 'Nuevo gasto' })).toBeVisible();
    await expect(page.getByTestId('vat-rate')).toHaveValue('0');

    // quality: allow-fragile-selector (the expense concept input has no test id or accessible label)
    await page.locator('form input[type="text"]').first().fill('Servicio sin IVA');
    await page.getByTestId('expense-form-period').fill('2026-10-01');
    await page.getByTestId('partner-split-total').fill('500000');

    await expect(page.getByTestId('vat-base')).toHaveText('$500.000 COP');
    await expect(page.getByTestId('vat-tax')).toHaveText('$0 COP');
    await page.getByTestId('expense-form-submit').click();

    await expect(page.getByText('Gasto creado')).toContainText('Gasto creado');
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toMatchObject({ amount: 500000, amount_mode: 'vat_included', vat_rate: 0 });
  });

  // Bug caught: the pre-send review could omit the IVA breakdown even though
  // the customer email and PDF are generated from an IVA-bearing account.
  test('collection preview shows the taxable email breakdown', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, accountingHandler(calls));
    await page.goto(`${PANEL_PATH}/collections`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Cuentas de cobro', exact: true })).toBeVisible();

    await page.getByTestId('collection-create-button').click();
    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('collection-form-income').click();
    await page.getByTestId('collection-form-income-option-8').click();
    await expect(page.getByTestId('collection-form-amount')).toHaveValue('1.190.000');
    await expect(page.getByTestId('vat-rate')).toHaveValue('19.00');

    await page.getByTestId('collection-form-preview').click();
    await expect(page.getByTestId('collection-preview-subject')).toContainText('PA-ACME-001');
    const email = page.frameLocator('[data-testid="collection-preview-email"]');
    await expect(email.getByText('Valor antes de IVA: $1.000.000 COP')).toBeVisible();
    await expect(email.getByText('IVA (19%): $190.000 COP')).toBeVisible();
    await expect(email.getByText('Total a pagar: $1.190.000 COP')).toBeVisible();
    await expect(page.getByTestId('collection-preview-pdf')).toHaveAttribute('src', PREVIEW_PDF_URL);

    const previewCall = calls.find((call) => call.apiPath === 'accounting/collection-accounts/preview/');
    expect(previewCall.body).toMatchObject({
      income_record_id: 8,
      vat_rate: '19.00',
      items: [{ amount: '1190000', amount_mode: 'vat_included' }],
    });
  });
});
