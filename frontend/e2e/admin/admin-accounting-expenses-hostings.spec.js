/**
 * E2E tests for the accounting expenses and hostings subviews.
 *
 * FLOWS: admin-accounting-expenses-crud, admin-accounting-hostings
 * Covers: expense list + create + category badge; hosting list + meta
 *         stat cards + create + estado badge.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { bulkAction, bulkMenuItem, openBulkMenu } from '../helpers/bulk-actions.js';
import { chooseRowAction, openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';
import {
  ADMIN_ACCOUNTING_EXPENSES_CRUD,
  ADMIN_ACCOUNTING_HOSTINGS,
  ADMIN_ACCOUNTING_HOSTING_CLIENT,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const EXPENSE_ROW = {
  id: 1,
  concept: 'Claude Code 20x',
  period: '2026-03',
  period_label: 'Marzo 2026',
  period_date: '2026-03-01',
  category: 'business',
  category_label: 'Negocio',
  total_amount: '400000.00',
  gustavo_amount: '200000.00',
  carlos_amount: '200000.00',
  company_amount: '0.00',
  notes: '',
  created_at: '2026-03-01T10:00:00Z',
  updated_at: '2026-03-01T10:00:00Z',
};

// Settle-born deductions: typed, linked to their origin income and served
// only to the tests that opt in (extra rows would break the exact-text
// assertions of the older display tests).
const DEDUCTION_ROWS = [
  {
    ...EXPENSE_ROW,
    id: 2,
    concept: 'Comisión plataforma de pago — Hosting Jimmy Junio',
    period: '2026-06',
    period_label: 'Junio 2026',
    period_date: '2026-06-01',
    deduction_type: 'gateway_fee',
    deduction_type_label: 'Comisión plataforma de pago',
    source_income: 134,
    source_income_concept: 'Hosting Jimmy Junio',
    total_amount: '4854.00',
    gustavo_amount: '2427.00',
    carlos_amount: '2427.00',
  },
  {
    ...EXPENSE_ROW,
    id: 3,
    concept: 'Retención en la fuente — Kore Fase 4',
    period: '2026-07',
    period_label: 'Julio 2026',
    period_date: '2026-07-01',
    deduction_type: 'withholding',
    deduction_type_label: 'Retención en la fuente',
    source_income: 150,
    source_income_concept: 'Kore Fase 4',
    total_amount: '70000.00',
    gustavo_amount: '35000.00',
    carlos_amount: '35000.00',
  },
];

const CLIENT_SEARCH_RESULT = [{
  id: 5,
  name: 'Germán Franco',
  email: 'german@korehealths.com',
  phone: '',
  company: 'Kore',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
}];

const HOSTING_ROWS = [
  {
    id: 1,
    client: null,
    client_display_name: null,
    billing_email: '',
    client_name: 'German - Kore',
    domain_url: 'https://korehealths.com/',
    monthly_value: '91667.00',
    payment_modality: 'semiannual',
    payment_modality_label: 'Semestral',
    benefit: '',
    valid_from: '2026-03-02',
    valid_to: '2026-09-02',
    cycles_count: 1,
    payment_per_cycle: '550002.00',
    total_paid: '1100000.00',
    is_active: true,
    notes: '',
    created_at: '2026-03-02T10:00:00Z',
    updated_at: '2026-03-02T10:00:00Z',
  },
  {
    id: 2,
    client: null,
    client_display_name: null,
    billing_email: '',
    client_name: 'Nestor - Xpandia',
    domain_url: 'https://xpandia.global/',
    monthly_value: '19000.00',
    payment_modality: 'nine_month',
    payment_modality_label: 'Cada 9 meses',
    benefit: '',
    valid_from: '2026-07-01',
    valid_to: '2027-07-01',
    cycles_count: 1,
    payment_per_cycle: '228000.00',
    total_paid: '228000.00',
    is_active: false,
    notes: '',
    created_at: '2026-07-01T10:00:00Z',
    updated_at: '2026-07-01T10:00:00Z',
  },
];

function buildHandler({
  calls,
  createStatus = 201,
  expenses = [EXPENSE_ROW],
  expensesMeta = {},
  hostings = HOSTING_ROWS,
  hostingsMeta = { active_count: 1, monthly_income: '91667.00' },
}) {
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
    if (apiPath === 'accounting/expenses/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: expenses, meta: expensesMeta }),
      };
    }
    if (apiPath === 'accounting/expenses/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (createStatus !== 201) {
        return {
          status: createStatus,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Monto inválido', code: 'invalid_amount' }),
        };
      }
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...EXPENSE_ROW, id: 99, ...body }),
      };
    }
    if (/^accounting\/expenses\/\d+\/update\/$/.test(apiPath) && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...expenses[0], ...body }),
      };
    }
    if (apiPath === 'accounting/hostings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: hostings, meta: hostingsMeta }),
      };
    }
    if (apiPath === 'accounting/hostings/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...HOSTING_ROWS[0], id: 99, ...body }),
      };
    }
    if (/^accounting\/hostings\/\d+\/delete\/$/.test(apiPath) && method === 'DELETE') {
      calls.push({ apiPath, method });
      // The page refetches after every mutation, so the mock has to drop the
      // row like the server would or the reload would bring it back.
      const id = Number(apiPath.split('/')[2]);
      const index = hostings.findIndex((row) => row.id === id);
      if (index !== -1) hostings.splice(index, 1);
      return { status: 204, contentType: 'application/json', body: '' };
    }
    if (apiPath === 'accounting/hostings/bulk-assign-client/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      const updated = body.hosting_ids.map((id) => ({
        ...(hostings.find((row) => row.id === id) || HOSTING_ROWS[0]),
        id,
        client: body.client,
        client_display_name: body.client ? 'Germán Franco' : null,
      }));
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ updated: updated.length, results: updated }),
      };
    }
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(CLIENT_SEARCH_RESULT),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

test.describe('Admin Accounting Expenses & Hostings', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('expenses list renders rows with the category badge', {
    tag: [...ADMIN_ACCOUNTING_EXPENSES_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — expenses list renders rows with the category badge; the create interaction is covered below)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/expenses', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Gastos', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByText('Claude Code 20x')).toBeVisible();
    await expect(
      page.getByText('Negocio', { exact: true }).filter({ visible: true }),
    ).toBeVisible();
  });

  test('deductions carry a typed pill and can be isolated with their totals', {
    tag: [...ADMIN_ACCOUNTING_EXPENSES_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching /panel/accounting/expenses through
    // the subnav is exercised by the accounting navigation specs; this test
    // pins the deduction pill, the type filter and the totals)
    await mockApi(page, buildHandler({
      calls: [],
      expenses: [EXPENSE_ROW, ...DEDUCTION_ROWS],
      expensesMeta: {
        deductions_total: '74854.00',
        deductions_by_type: {
          gateway_fee: '4854.00',
          withholding: '70000.00',
        },
      },
    }));
    await page.goto('/panel/accounting/expenses', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Gastos', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    // The typed pill names its origin income in the tooltip.
    const pill = page.getByTestId('expense-deduction-pill-2');
    await expect(pill).toContainText('Comisión plataforma de pago');
    await expect(pill).toHaveAttribute('title', /origen: Hosting Jimmy Junio/);

    // The KPI card totalizes the year deductions with the type breakdown.
    await expect(page.getByTestId('expenses-deductions-card')).toContainText('74.854');

    // Filtering by type isolates the withholding row and splits the chips.
    await page.getByRole('button', { name: /Filtros/ }).click();
    await page.getByRole('button', { name: 'Tipo de deducción' }).click();
    await page.getByRole('checkbox', { name: 'Retención en la fuente' }).check();

    await expect(page.getByTestId('accounting-row-3')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
    await expect(page.getByTestId('accounting-row-2')).toHaveCount(0);
    await expect(page.getByTestId('expenses-total-deductions')).toContainText('70.000');
  });

  test('creates an expense through the modal', {
    tag: [...ADMIN_ACCOUNTING_EXPENSES_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/expenses', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Gastos', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('expenses-new-button').click();
    await expect(page.getByRole('heading', { name: 'Nuevo gasto' })).toBeVisible();

    // quality: allow-fragile-selector (the expense modal's inputs have no testids; positional/attribute select is intentional)
    await page.locator('form input[type="text"]').first().fill('Windsurf Julio');
    // The period asks for the exact date by default.
    await page.getByTestId('expense-form-period').fill('2026-07-15');
    await page.getByTestId('partner-split-total').fill('3000000');
    await expect(page.getByTestId('expense-register-in-pocket')).toBeVisible();
    await page.getByTestId('expense-form-submit').click();

    await expect(page.getByText('Gasto creado')).toContainText('Gasto creado');
    expect(calls).toHaveLength(1);
    expect(calls[0].body.concept).toBe('Windsurf Julio');
    expect(Number(calls[0].body.gustavo_amount)).toBe(1500000);
    // The pocket toggle defaults to on: the new expense mirrors to the pocket.
    expect(calls[0].body.register_in_pocket).toBe(true);
  });

  test('a 400 on expense create surfaces the backend error and keeps the modal open', {
    tag: [...ADMIN_ACCOUNTING_EXPENSES_CRUD, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, createStatus: 400 }));
    await page.goto('/panel/accounting/expenses', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Gastos', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('expenses-new-button').click();
    // quality: allow-fragile-selector (the expense modal's concept input has no testid; attribute select is intentional)
    await page.locator('form input[type="text"]').first().fill('Gasto inválido');
    await page.getByTestId('expense-form-period').fill('2026-07-15');
    await page.getByTestId('partner-split-total').fill('100');
    await page.getByTestId('expense-form-submit').click();

    await expect(page.getByText('No se pudo guardar')).toBeVisible();
    // The modal stays open so the user can correct the input.
    await expect(page.getByRole('heading', { name: 'Nuevo gasto' })).toBeVisible();
  });

  // Bug caught: Gastos kept a trailing «Acciones» column with a loose
  // Detalle e historial button squeezed beside the edit and delete icons.
  test('the expense row menu owns every expense action', {
    tag: [...ADMIN_ACCOUNTING_EXPENSES_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; this test pins the
    // row action contract, driven through the kebab below)
    await mockApi(page, buildHandler({
      calls: [],
      expenses: [{ ...EXPENSE_ROW, notes: 'Plan anual pagado con la tarjeta de la empresa.' }],
    }));
    await page.goto('/panel/accounting/expenses', { waitUntil: 'domcontentloaded' });
    const row = page.getByTestId('accounting-row-1');
    await expect(row).toContainText('Claude Code 20x', { timeout: 25_000 });

    await expect(page.getByRole('columnheader', { name: 'Acciones' })).toHaveText('');
    await expect(row.getByTestId('accounting-actions-cell-1').getByRole('button')).toHaveCount(1);
    await expect(page.getByTestId('accounting-edit-1')).toHaveCount(0);

    await openRowMenu(page, { kebab: 'expense-actions-1', menu: 'expense-actions-modal' });
    const menu = page.getByTestId('expense-actions-modal');
    await expect(menu).toContainText('Claude Code 20x');
    await expect(menu.getByRole('button', { name: 'Detalle e historial' })).toBeVisible();
    await expect(menu.getByRole('button', { name: 'Editar' })).toBeVisible();
    await expect(menu.getByRole('button', { name: 'Eliminar' })).toBeVisible();

    await menu.getByRole('button', { name: 'Ver nota' }).click();
    await expect(page.getByTestId('accounting-note-body'))
      .toContainText('Plan anual pagado con la tarjeta de la empresa.');
  });

  test('an expense is edited from its row menu', {
    tag: [...ADMIN_ACCOUNTING_EXPENSES_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the edit starts at
    // the row's kebab, which IS driven below)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/expenses', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('accounting-row-1'))
      .toContainText('Claude Code 20x', { timeout: 25_000 });

    await chooseRowAction(page, {
      kebab: 'expense-actions-1',
      menu: 'expense-actions-modal',
      action: 'expense-action-edit-1',
    });
    await expect(page.getByRole('heading', { name: 'Editar Gasto' })).toBeVisible();
    await page.getByTestId('expense-form-submit').click();

    await expect(page.getByText('Gasto actualizado')).toBeVisible();
    // The form arrived prefilled with the row the menu was opened from.
    const update = calls.find((call) => call.method === 'PATCH');
    expect(update.apiPath).toBe('accounting/expenses/1/update/');
    expect(update.body.concept).toBe('Claude Code 20x');
  });

  test('hostings list renders meta stat cards', {
    tag: [...ADMIN_ACCOUNTING_HOSTINGS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — hostings list renders its meta stat cards)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText('Hostings activos', { exact: true })).toBeVisible();
    await expect(page.getByText('Ingreso mensual', { exact: true })).toBeVisible();
    // Valor/mes also renders in the phone's grouped details, hidden here.
    await expect(page.getByText('$91.667 COP').filter({ visible: true }).first()).toBeVisible();
  });

  test('hostings table shows domain and estado badge per row', {
    tag: [...ADMIN_ACCOUNTING_HOSTINGS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the hostings table renders each row's domain and status)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText('German - Kore')).toBeVisible();
    // Estado is now an inline status select reflecting each row's state.
    const statusSelects = page.getByTestId('accounting-status-select');
    // quality: allow-fragile-selector (asserts each row's status by its position in the table order)
    await expect(statusSelects.nth(0)).toHaveValue('true');
    // quality: allow-fragile-selector (asserts each row's status by its position in the table order)
    await expect(statusSelects.nth(1)).toHaveValue('false');
  });

  // Bug caught: below 1024px a hosting's history could not be opened at all
  // (its narrow menu lacked it), and above it the history was a loose button
  // among five icons in a trailing «Acciones» column.
  test('the hosting row menu starts with its record history on a phone', {
    tag: [...ADMIN_ACCOUNTING_HOSTINGS, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; this test pins the
    // row menu at phone width, driven through the kebab below)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    const row = page.getByTestId('accounting-row-1');
    await expect(row).toBeVisible({ timeout: 25_000 });

    const table = row.locator('xpath=ancestor::table');
    await expectNoBlankBand(table);
    // Valor/mes groups under Cliente on a phone, so the row fits without a
    // horizontal scroll and the Estado select stays whole.
    expect(await table.locator('..').evaluate((element) => element.scrollWidth <= element.clientWidth))
      .toBe(true);
    await expect(row.getByTestId('accounting-actions-cell-1').getByRole('button')).toHaveCount(1);

    await openRowMenu(page, { kebab: 'hosting-actions-1', menu: 'hosting-actions-modal' });
    const history = page.getByTestId('hosting-history-1');
    const cycles = page.getByTestId('hosting-cycles-1');
    expect((await history.boundingBox()).y).toBeLessThan((await cycles.boundingBox()).y);

    await history.click();
    await expect(page.getByRole('heading', { name: 'Detalle del registro' })).toBeVisible();
    await expect(page.getByTestId('history-record-modal')).toContainText('korehealths.com');
  });

  test('creates a hosting through the modal', {
    tag: [...ADMIN_ACCOUNTING_HOSTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('hostings-new-button').click();
    await expect(page.getByRole('heading', { name: 'Nuevo hosting' })).toBeVisible();

    // Every hosting belongs to a client, so the picker comes first.
    await page.getByTestId('hosting-form-client').fill('Kore');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('hosting-form-client-name').fill('Katerin Ruiz - Senses Candles');
    await page.getByTestId('hosting-form-monthly').fill('38333');
    await page.getByTestId('hosting-form-modality').selectOption('nine_month');
    await page.getByTestId('hosting-form-submit').click();

    await expect(page.getByText('Hosting creado')).toContainText('Hosting creado');
    expect(calls).toHaveLength(1);
    expect(calls[0].body.client).toBe(5);
    expect(calls[0].body.client_name).toBe('Katerin Ruiz - Senses Candles');
    expect(calls[0].body.payment_modality).toBe('nine_month');
  });
});


test.describe('Admin Accounting Hostings — errores de creación', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('missing hosting client is reported beside its field', {
    tag: [...ADMIN_ACCOUNTING_HOSTINGS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('hostings-new-button').click();
    await page.getByTestId('hosting-form-client-name').fill('Sin cliente asignado');
    await page.getByTestId('hosting-form-monthly').fill('38333');
    await page.getByTestId('hosting-form-submit').click();

    const client = page.getByTestId('hosting-form-client');
    await expect(client).toHaveAttribute('aria-invalid', 'true');
    const errorId = await client.getAttribute('aria-describedby');
    expect(errorId).toBeTruthy();
    await expect(page.locator(`[id="${errorId}"]`)).toHaveText('Elige o crea un cliente.');
    expect(calls.filter((call) => (
      call.apiPath === 'accounting/hostings/create/'
    ))).toHaveLength(0);
  });
});

test.describe('Admin Accounting Hostings — cliente del hosting', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('unlinked hostings are flagged and the "Sin cliente" tab isolates them', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      hostings: [
        { ...HOSTING_ROWS[0], client: 5, client_display_name: 'Germán Franco' },
        HOSTING_ROWS[1],
      ],
      hostingsMeta: { active_count: 1, monthly_income: '91667.00', without_client_count: 1 },
      calls: [],
    }));
    // quality: allow-deep-link (the tab is a subnav entry; what is under
    // test is the Sin cliente tab, which IS clicked below)
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await expect(page.getByTestId('hosting-unlinked-2')).toBeVisible();
    await expect(page.getByTestId('hosting-unlinked-1')).toHaveCount(0);

    await page.getByTestId('filter-tabs-tab-no-client').click();

    await expect(page.getByTestId('accounting-row-2')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
  });

  test('assigning a client in bulk confirms the scope, then links every selected hosting', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('accounting-select-1').check();
    await expect(page.getByTestId('hostings-bulk-bar')).toContainText('1 seleccionado');

    await bulkAction(page, 'hostings', 'Asignar cliente');
    await page.getByTestId('hostings-bulk-client').fill('Kore');
    await page.getByTestId('client-autocomplete-option-5').click();

    // The mass edit names its scope before it runs, not after.
    await expect(page.getByTestId('hostings-bulk-hint')).toContainText(
      'Cliente enlazado: Germán Franco',
    );
    await expect(page.getByTestId('client-bulk-summary-list')).toContainText('korehealths.com');
    expect(calls.some((c) => c.apiPath === 'accounting/hostings/bulk-assign-client/')).toBe(false);

    await page.getByTestId('hostings-bulk-assign').click();

    await expect(page.getByTestId('hostings-bulk-bar')).toHaveCount(0);
    const bulk = calls.find(
      (call) => call.apiPath === 'accounting/hostings/bulk-assign-client/',
    );
    expect(bulk.body).toEqual({ hosting_ids: [1], client: 5 });
  });

  test('assigning stays blocked, with the reason on screen, until a client is picked', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CLIENT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('accounting-select-1').check();

    // Nothing selected has a client, so the menu does not offer to unlink one
    // — and the menu has to be OPEN for that absence to mean anything.
    await openBulkMenu(page, 'hostings');
    await expect(bulkMenuItem(page, 'Desvincular cliente')).toHaveCount(0);
    await bulkMenuItem(page, 'Asignar cliente').click();

    // An empty picker no longer means "unlink": the action is simply off.
    await expect(page.getByTestId('hostings-bulk-assign')).toBeDisabled();
    await expect(page.getByTestId('hostings-bulk-hint')).toContainText(
      'Elige un cliente para poder asignar',
    );
  });

  test('unlinking is its own action and names the client the hostings are leaving', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      hostings: [
        { ...HOSTING_ROWS[0], client: 5, client_display_name: 'Germán Franco' },
        HOSTING_ROWS[1],
      ],
    }));
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('accounting-select-1').check();
    await page.getByTestId('accounting-select-2').check();
    await bulkAction(page, 'hostings', 'Desvincular cliente');

    await expect(page.getByRole('dialog')).toContainText(
      '1 hosting quedará sin cliente: 1 de Germán Franco.',
    );
    // Solo la fila enlazada entra en el alcance; la suelta no aparece.
    await expect(page.getByTestId('client-bulk-summary-list')).toContainText('korehealths.com');
    await expect(page.getByTestId('client-bulk-summary-list')).not.toContainText('xpandia');

    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('hostings-bulk-bar')).toHaveCount(0);
    const bulk = calls.find(
      (call) => call.apiPath === 'accounting/hostings/bulk-assign-client/',
    );
    // Only the linked row travels — the unassigned one had nothing to lose.
    expect(bulk.body).toEqual({ hosting_ids: [1], client: null });
  });

  test('deleting a selected hosting drops it from the bar and keeps the rest', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Hostings and incomes share the bar and now share the selection
    // composable too. This is the spec that catches a fix applied to only one
    // of the two pages.
    await mockApi(page, buildHandler({
      hostings: [HOSTING_ROWS[0], HOSTING_ROWS[1]],
      calls: [],
    }));
    // quality: allow-deep-link (the tab is a subnav entry; what is under test
    // is the selection surviving a row delete, which IS driven below)
    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('accounting-select-1').check();
    await page.getByTestId('accounting-select-2').check();
    await expect(page.getByTestId('hostings-bulk-bar')).toContainText('2 seleccionados');

    await chooseRowAction(page, {
      kebab: 'hosting-actions-2',
      menu: 'hosting-actions-modal',
      action: 'hosting-delete-2',
    });
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('accounting-row-2')).toHaveCount(0);
    await expect(page.getByTestId('hostings-bulk-bar')).toContainText('1 seleccionado');
    await expect(page.getByTestId('hostings-bulk-outside')).toHaveCount(0);
  });
});
