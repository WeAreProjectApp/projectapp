/**
 * E2E tests for the credit-card statement ledger and the card catalog.
 *
 * FLOWS: admin-accounting-statements, admin-accounting-card-catalog
 * Covers: 12-month grid with backend year options and "No aplica" months,
 *         statement detail (stat cards + transactions), manual transaction
 *         add on drafts, finalize lifecycle, bank-PDF delete with confirm;
 *         catalog list + create + cupo edit + reference-blocked delete.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_ACCOUNTING_STATEMENTS,
  ADMIN_ACCOUNTING_CARD_CATALOG,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const CARD = {
  id: 1,
  name: 'T.C 0064',
  credit_limit: '8000000.00',
  is_active: true,
  statements_since: '2026-05-01',
};

function statusPayload() {
  return {
    year: 2026,
    year_options: [2026],
    months: [
      { period: '2026-04', label: 'abril', applies: false, statements: [] },
      {
        period: '2026-05',
        label: 'mayo',
        applies: true,
        statements: [
          { id: 1, card_name: 'T.C 0064', status: 'processed', status_label: 'Procesado' },
        ],
      },
      {
        period: '2026-06',
        label: 'junio',
        applies: true,
        statements: [
          { id: 2, card_name: 'T.C 0064', status: 'draft', status_label: 'Borrador' },
        ],
      },
    ],
  };
}

function makeTx(overrides = {}) {
  return {
    id: 10,
    transaction_date: '2026-06-05',
    raw_description: 'PAGO SERVIDOR HETZNER',
    merchant_name: 'Hetzner',
    amount: '450000.00',
    category: 'business',
    category_label: 'Negocio',
    installment_label: '',
    original_amount: null,
    original_currency: '',
    is_identified: true,
    ...overrides,
  };
}

function makeDetail(overrides = {}) {
  return {
    id: 2,
    card_name: 'T.C 0064',
    period: '2026-06',
    period_label: 'Junio 2026',
    status: 'draft',
    status_label: 'Borrador',
    purchases_total: '450000.00',
    payments_total: '0.00',
    interest_and_fees: '0.00',
    minimum_payment: '45000.00',
    closing_balance: '450000.00',
    due_date: '2026-07-05',
    created_at: '2026-07-01T10:00:00Z',
    pdf_file_url: '/media/statements/extracto.pdf',
    category_totals: [
      { category: 'business', category_label: 'Negocio', label: 'Negocio', total: '450000.00' },
    ],
    transactions: [makeTx()],
    ...overrides,
  };
}

function buildHandler({ calls }) {
  const state = { detail: makeDetail() };
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { username: 'admin', is_staff: true, is_superuser: true },
        }),
      };
    }
    if (apiPath.startsWith('accounting/statements/status/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(statusPayload()),
      };
    }
    if (apiPath === 'accounting/statements/2/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.detail),
      };
    }
    if (
      apiPath === 'accounting/statements/2/transactions/batch/'
      && method === 'POST'
    ) {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      state.detail = makeDetail({
        transactions: [
          makeTx(),
          makeTx({ id: 99, raw_description: body.transactions[0].raw_description }),
        ],
      });
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ created: 1 }),
      };
    }
    if (apiPath === 'accounting/statements/2/finalize/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      state.detail = makeDetail({ status: 'processed', status_label: 'Procesado' });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.detail),
      };
    }
    if (
      apiPath === 'accounting/statements/2/pdf/delete/'
      && method === 'DELETE'
    ) {
      calls.push({ apiPath, method });
      state.detail = makeDetail({ pdf_file_url: null });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.detail),
      };
    }
    if (apiPath === 'accounting/credit-cards/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [CARD], meta: {} }),
      };
    }
    if (apiPath === 'accounting/credit-cards/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...CARD, id: 7, ...body }),
      };
    }
    if (
      apiPath === 'accounting/credit-cards/1/update/'
      && method === 'PATCH'
    ) {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...CARD, ...body }),
      };
    }
    if (
      apiPath === 'accounting/credit-cards/1/delete/'
      && method === 'DELETE'
    ) {
      calls.push({ apiPath, method });
      return {
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'credit_card_referenced',
          detail: 'La tarjeta tiene extractos asociados; desactívala en su lugar.',
        }),
      };
    }
    if (apiPath.startsWith('accounting/merchant-aliases')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], meta: {} }),
      };
    }
    if (apiPath === 'accounting/settings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          notifications_enabled: true,
          card_reminder_enabled: true,
          statement_reminder_enabled: true,
          hosting_expiry_enabled: true,
          usd_exchange_rate: '4000.00',
        }),
      };
    }
    // The settings page also mounts the recipients catalog.
    if (apiPath === 'accounting/notification-recipients/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], meta: {} }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

async function gotoStatements(page) {
  await page.goto('/panel/accounting/statements', { waitUntil: 'domcontentloaded' });
  await expect(
    page.getByRole('heading', { name: 'Extractos de tarjeta' }),
  ).toBeVisible({ timeout: 25_000 });
}

async function openDraftDetail(page) {
  await page.getByTestId('statement-chip-2').click();
  await expect(page.getByTestId('statement-detail')).toBeVisible();
}

test.describe('Admin Accounting Statements', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the grid marks months before statements_since as No aplica', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the 12-month grid marks pre-statements_since months as "No aplica" and shows each statement's status)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoStatements(page);

    await expect(page.getByTestId('statement-month-2026-04')).toContainText('No aplica');
    await expect(page.getByTestId('statement-chip-1')).toContainText('Procesado');
    await expect(page.getByTestId('statement-chip-2')).toContainText('Borrador');
  });

  test('clicking a chip loads the statement detail', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoStatements(page);

    await openDraftDetail(page);

    await expect(page.getByTestId('statement-detail')).toContainText('Junio 2026');
    await expect(page.getByTestId('statement-tx-10')).toContainText('Hetzner');
  });

  test('a manual transaction is added to a draft through the modal', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);
    await openDraftDetail(page);

    await page.getByTestId('statement-add-tx').click();
    await page.getByTestId('tx-date-input').fill('2026-06-20');
    await page.getByTestId('tx-description-input').fill('COMPRA EXITO CALLE 80');
    await page.getByTestId('tx-merchant-input').fill('Éxito');
    await page.getByTestId('tx-amount-input').fill('120000');
    await page.getByTestId('tx-save').click();

    await expect(page.getByTestId('statement-tx-99')).toContainText('COMPRA EXITO CALLE 80');
    const batchCall = calls.find(
      (call) => call.apiPath === 'accounting/statements/2/transactions/batch/',
    );
    expect(batchCall.body.transactions[0].raw_description).toBe('COMPRA EXITO CALLE 80');
    // The currency input emits a number, not the raw typed string.
    expect(batchCall.body.transactions[0].amount).toBe(120000);
  });

  test('finalizing a balanced draft marks it as processed', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);
    await openDraftDetail(page);

    await page.getByTestId('statement-finalize').click();

    await expect(page.getByTestId('statement-reopen')).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/statements/2/finalize/',
      method: 'POST',
      body: { force: false },
    });
  });

  test('deleting the bank PDF asks for confirmation first', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);
    await openDraftDetail(page);

    await expect(page.getByTestId('statement-pdf-view')).toBeVisible();
    await page.getByTestId('statement-pdf-delete').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('statement-pdf-view')).toHaveCount(0);
    expect(calls).toContainEqual({
      apiPath: 'accounting/statements/2/pdf/delete/',
      method: 'DELETE',
    });
  });
});

test.describe('Admin Accounting Card Catalog', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  async function gotoSettings(page) {
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Catálogo de tarjetas' }),
    ).toBeVisible({ timeout: 25_000 });
  }

  test('lists the catalog rows with their cupo', {
    tag: [...ADMIN_ACCOUNTING_CARD_CATALOG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the catalog lists card rows with their cupo; the create/edit/delete interactions are covered below)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoSettings(page);

    await expect(page.getByTestId('card-catalog-row-card-1')).toBeVisible();
    await expect(page.getByTestId('card-catalog-name-card-1')).toHaveValue('T.C 0064');
  });

  test('a new card is created from a draft row', {
    tag: [...ADMIN_ACCOUNTING_CARD_CATALOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoSettings(page);

    await page.getByTestId('card-catalog-add').click();
    await page.getByTestId('card-catalog-name-draft-1').fill('T.C 9911');
    await page.getByTestId('card-catalog-limit-draft-1').fill('5000000');
    await page.getByTestId('card-catalog-save-draft-1').click();

    await expect(page.getByText('Tarjeta agregada.')).toContainText('Tarjeta agregada');
    const createCall = calls.find(
      (call) => call.apiPath === 'accounting/credit-cards/create/',
    );
    expect(createCall.body.name).toBe('T.C 9911');
  });

  test('editing the cupo patches the existing card', {
    tag: [...ADMIN_ACCOUNTING_CARD_CATALOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoSettings(page);

    await page.getByTestId('card-catalog-limit-card-1').fill('9000000');
    await page.getByTestId('card-catalog-save-card-1').click();

    await expect(page.getByText('Tarjeta actualizada.')).toContainText('Tarjeta actualizada');
    const updateCall = calls.find(
      (call) => call.apiPath === 'accounting/credit-cards/1/update/',
    );
    expect(String(updateCall.body.credit_limit)).toContain('9000000');
  });

  test('a referenced card cannot be deleted and explains why', {
    tag: [...ADMIN_ACCOUNTING_CARD_CATALOG, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoSettings(page);

    // A saved card's delete lives in its menu; only drafts discard inline.
    await page.getByTestId('card-catalog-actions-card-1').click();
    await page.getByTestId('card-catalog-action-delete-card-1').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('No se pudo eliminar la tarjeta')).toContainText('No se pudo eliminar la tarjeta');
    expect(calls).toContainEqual({
      apiPath: 'accounting/credit-cards/1/delete/',
      method: 'DELETE',
    });
    await expect(page.getByTestId('card-catalog-row-card-1')).toBeVisible();
  });
});
