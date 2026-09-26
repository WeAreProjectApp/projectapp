/**
 * E2E tests for the accounting incomes subview.
 *
 * FLOWS: admin-accounting-income-crud, admin-accounting-collection-create,
 *        admin-accounting-income-client, admin-accounting-income-reminder-mute
 * Covers: list rendering, create via modal with automatic 50/50 partner
 *         split, HTML5 validation, edit prefill, duplicate from both the row
 *         menu and the detail modal (seeded form, always expected, failing
 *         draft), delete with confirmation (confirm and cancel), API-error
 *         surfacing, and the cuenta de cobro entry point (generate icon opens
 *         the preselected modal; linked rows swap to Ver cuenta de cobro
 *         navigation).
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { bulkAction, bulkMenuItem, openBulkMenu } from '../helpers/bulk-actions.js';
import { viewportUse } from '../helpers/viewports.js';
import {
  ADMIN_ACCOUNTING_COLLECTION_CREATE,
  ADMIN_ACCOUNTING_INCOME_CLIENT,
  ADMIN_ACCOUNTING_INCOME_CRUD,
  ADMIN_ACCOUNTING_INCOME_REMINDER_MUTE,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

function incomeRow(overrides = {}) {
  return {
    id: 1,
    concept: 'Kore - Inicio 40%',
    kind: 'expected',
    kind_label: 'Esperado',
    period: '2026-02',
    period_label: 'Febrero 2026',
    period_date: '2026-02-01',
    destination: 'partners',
    destination_label: 'Socios',
    ledger: 'company',
    ledger_label: 'Empresa',
    total_amount: '1160000.00',
    gustavo_amount: '580000.00',
    carlos_amount: '580000.00',
    company_amount: '0.00',
    expected_income: null,
    pocket_movement: null,
    paid_amount: '0.00',
    pending_amount: '1160000.00',
    payment_status: 'pending',
    payment_status_label: 'Pendiente',
    is_receivable_candidate: false,
    collection_confidence: '',
    collection_confidence_label: '',
    reminders_muted: false,
    reminders_muted_until: null,
    client: null,
    client_name: null,
    origin: '',
    origin_label: '',
    notes: '',
    created_at: '2026-02-01T10:00:00Z',
    updated_at: '2026-02-01T10:00:00Z',
    ...overrides,
  };
}

const INCOME_INDICATOR_META = {
  expected_total: '3000000.00',
  liquid_total: '1800000.00',
  lost_total: '200000.00',
  received_pct: 60,
  current_month_liquid: '800000.00',
  top_income: { concept: 'Ingreso líquido principal', amount: '1000000.00' },
  without_client_count: 1,
  without_project_count: 1,
};

const INCOME_INDICATOR_ROWS = [
  incomeRow({
    id: 1,
    concept: 'Ingreso esperado anual',
    kind: 'expected',
    kind_label: 'Esperado',
    period: '2026-03',
    period_label: 'Marzo 2026',
    period_date: '2026-03-01',
    client: 5,
    client_name: 'Ana Pérez',
    project: 10,
    project_name: 'Kore',
  }),
  incomeRow({
    id: 2,
    concept: 'Ingreso líquido principal',
    kind: 'liquid',
    kind_label: 'Líquido',
    period: '2026-08',
    period_label: 'Agosto 2026',
    period_date: '2026-08-15',
    total_amount: '1000000.00',
    payment_status: null,
    payment_status_label: null,
    client: 5,
    client_name: 'Ana Pérez',
    project: 10,
    project_name: 'Kore',
  }),
  incomeRow({
    id: 3,
    concept: 'Ingreso perdido anual',
    kind: 'lost',
    kind_label: 'Perdido',
    period: '2026-05',
    period_label: 'Mayo 2026',
    period_date: '2026-05-01',
    total_amount: '200000.00',
    payment_status: null,
    payment_status_label: null,
    client: 5,
    client_name: 'Ana Pérez',
    project: 10,
    project_name: 'Kore',
  }),
  incomeRow({ id: 4, concept: 'Pendiente de cliente', project: null }),
  incomeRow({
    id: 5,
    concept: 'Pendiente de proyecto',
    client: 5,
    client_name: 'Ana Pérez',
    project: null,
    project_name: null,
  }),
];

function buildHandler({
  rows, calls, createStatus = 201, meta = {}, listFetches = { count: 0 },
  savedTabs = [], duplicateDraftStatus = 200,
  muteStatus = 200,
  // Landing mode the mocked backend setting dictates. Production defaults to
  // 'grouped'; the mock pins 'classic' because almost every test in this file
  // exercises the classic presentation or its pagination — without this
  // branch mockApi's empty fallback would leave
  // the page grouped and break them all.
  incomeViewMode = 'classic',
  // Non-empty makes the bulk endpoint answer 409 records_not_found, the way
  // the server does when part of the batch was deleted while the
  // confirmation was open.
  bulkAssignMissingIds = [],
  // The window a create proposes when the origin turns to Hosting: the day
  // after the client's last recorded period. Pinned so the dates under test
  // do not move with the calendar.
  periodSuggestion = { previous_period_end: '2026-08-31', suggested_start: '2026-09-01' },
  // What the duplicate draft says its window is counted from. The default is
  // the resolvable case (the client's hosting says annual, so the draft can
  // already propose a date); tests that need the everyday one — no recorded
  // window and an ambiguous hosting — pass the `original_date` anchor instead.
  duplicateDraftPeriod = {
    period_date: '2027-02-01',
    period_date_source: 'hosting_cycle',
    period_anchor: {
      source: 'hosting_cycle',
      start: '2027-02-01',
      origin_start: null,
      origin_end: null,
      origin_date: '2026-02-01',
    },
  },
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
    if (apiPath === 'accounting/settings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ income_default_view_mode: incomeViewMode }),
      };
    }
    if (apiPath === 'accounting/incomes/period-suggestion/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(periodSuggestion),
      };
    }
    if (apiPath === 'accounting/incomes/' && method === 'GET') {
      listFetches.count += 1;
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: rows, meta }),
      };
    }
    if (apiPath === 'accounting/receivables/' && method === 'GET') {
      const candidates = rows.filter((row) => (
        row.kind === 'expected'
        && row.ledger === 'company'
        && ['pending', 'partial'].includes(row.payment_status)
      ));
      const green = candidates.filter((row) => (
        row.is_receivable_candidate && row.collection_confidence === 'high'
      ));
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: candidates,
          summary: {
            high_total: green.reduce((sum, row) => sum + Number(row.total_amount), 0),
            high_count: green.length,
            selected_count: candidates.filter((row) => row.is_receivable_candidate).length,
            by_confidence: {},
          },
        }),
      };
    }
    const settleMatch = apiPath.match(/^accounting\/incomes\/(\d+)\/settle\/$/);
    if (settleMatch && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ method, apiPath, body });
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
        body: JSON.stringify({
          income: incomeRow({ id: Number(settleMatch[1]) }),
          liquid: incomeRow({ id: 99, kind: 'liquid' }),
          expenses: (body.deductions || []).map((d, index) => ({
            id: 200 + index, concept: 'Comisión', deduction_type: d.type,
          })),
          expected_incomes: (body.expected_incomes || []).map((e, index) => (
            incomeRow({ id: 300 + index, concept: e.concept })
          )),
        }),
      };
    }
    const detailMatch = apiPath.match(/^accounting\/incomes\/(\d+)\/detail\/$/);
    if (detailMatch && method === 'GET') {
      const source = rows.find((row) => row.id === Number(detailMatch[1]));
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          income: source, liquid: [], expenses: [], collection_account: null,
        }),
      };
    }
    // The duplicate draft is server-built (it resolves the hosting cycle) and
    // writes nothing: the panel only opens its form on the response.
    const draftMatch = apiPath.match(/^accounting\/incomes\/(\d+)\/duplicate-draft\/$/);
    if (draftMatch && method === 'GET') {
      calls.push({ method, apiPath });
      if (duplicateDraftStatus !== 200) {
        return {
          status: duplicateDraftStatus,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Fallo del servidor', code: 'server_error' }),
        };
      }
      const source = rows.find((row) => row.id === Number(draftMatch[1]));
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          concept: source.concept,
          kind: 'expected',
          ...duplicateDraftPeriod,
          // Counted from the original's 2026-02-01, so the operator can
          // override the proposal without working the date out by hand.
          cycle_options: [
            { months: 1, date: '2026-03-01' },
            { months: 3, date: '2026-05-01' },
            { months: 6, date: '2026-08-01' },
            { months: 12, date: '2027-02-01' },
          ],
          destination: 'partners',
          ledger: source.ledger,
          client: source.client,
          client_name: source.client_name,
          project: null,
          project_name: null,
          origin: source.origin,
          total_amount: source.total_amount,
          gustavo_amount: source.gustavo_amount,
          carlos_amount: source.carlos_amount,
          notes: source.notes,
        }),
      };
    }
    if (apiPath === 'accounting/incomes/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ method, apiPath, body });
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
        body: JSON.stringify(incomeRow({ id: 99, ...body })),
      };
    }
    if (/^accounting\/incomes\/\d+\/update\/$/.test(apiPath) && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ method, apiPath, body });
      const id = Number(apiPath.split('/')[2]);
      const target = rows.find((row) => row.id === id) || rows[0];
      const updated = { ...target, ...body };
      Object.assign(target, updated);
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(incomeRow(updated)),
      };
    }
    const muteMatch = apiPath.match(/^accounting\/incomes\/(\d+)\/mute\/$/);
    if (muteMatch && method === 'POST') {
      const body = route.request().postDataJSON();
      const id = Number(muteMatch[1]);
      calls.push({ method, apiPath, body });
      if (muteStatus !== 200) {
        return {
          status: muteStatus,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'No se pudo actualizar el seguimiento.',
            code: 'server_error',
          }),
        };
      }
      const row = rows.find((item) => item.id === id);
      Object.assign(row, {
        reminders_muted: body.muted,
        reminders_muted_until: body.muted ? (body.until || null) : null,
      });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(row),
      };
    }
    if (/^accounting\/incomes\/\d+\/delete\/$/.test(apiPath) && method === 'DELETE') {
      calls.push({ method, apiPath });
      // The page refetches after every mutation (a row's payment state is
      // computed from other rows), so the mock has to drop it like the
      // server would, or the refetch would resurrect it.
      const id = Number(apiPath.split('/')[2]);
      const index = rows.findIndex((row) => row.id === id);
      if (index !== -1) rows.splice(index, 1);
      return { status: 204, contentType: 'application/json', body: '' };
    }
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      const url = new URL(route.request().url());
      const query = (url.searchParams.get('q') || '').trim().toLocaleLowerCase('es');
      const order = url.searchParams.get('order') || 'name';
      const offset = Number(url.searchParams.get('offset') || 0);
      const limit = Number(url.searchParams.get('limit') || 20);
      const matchingClients = CLIENT_SEARCH_RESULT
        .filter((client) => [client.name, client.company, client.email]
          .some((value) => value.toLocaleLowerCase('es').includes(query)))
        .sort((left, right) => left.name.localeCompare(right.name, 'es', { sensitivity: 'base' }));
      if (order === '-name') matchingClients.reverse();
      return {
        status: 200,
        contentType: 'application/json',
        headers: { 'X-Total-Count': String(matchingClients.length) },
        body: JSON.stringify(matchingClients.slice(offset, offset + limit)),
      };
    }
    if (apiPath === 'accounting/incomes/bulk-assign-client/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ method, apiPath, body });
      if (bulkAssignMissingIds.length) {
        return {
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            error: `${bulkAssignMissingIds.length} de los ingresos seleccionados ya no existe.`,
            code: 'records_not_found',
            hint: 'La lista se actualizó. Revisa la selección y vuelve a intentarlo.',
            missing_ids: bulkAssignMissingIds,
          }),
        };
      }
      const assigned = body.income_ids.map((id) => {
        const row = rows.find((item) => item.id === id) || incomeRow({ id });
        Object.assign(row, {
          client: body.client,
          client_name: body.client ? 'Ana Pérez' : null,
        });
        return row;
      });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ updated: assigned.length, results: assigned }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(savedTabs),
      };
    }
    return null;
  };
}

const CLIENT_SEARCH_RESULT = [
  { id: 5, name: 'Ana Pérez', email: 'ana@acme.co', company: 'Acme Soluciones' },
  { id: 6, name: 'Beatriz Torres', email: 'torres@acme.co', company: 'Torres SAS' },
  { id: 7, name: 'Camila Rojas', email: 'rojas@acme.co', company: 'Rojas SAS' },
  { id: 8, name: 'Diana Gómez', email: 'gomez@acme.co', company: 'Gómez SAS' },
  { id: 9, name: 'Elena Martínez', email: 'martinez@acme.co', company: 'Martínez SAS' },
  { id: 10, name: 'Fernanda Suárez', email: 'suarez@acme.co', company: 'Suárez SAS' },
].map((client) => ({
  phone: '',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
  ...client,
}));

// The view lands on the "Solo esperados" builtin tab, so the CRUD tests ask
// for the unfiltered baseline explicitly; the landing tab has its own test.
async function gotoIncomes(page, query = '?accounting_incomeTab=all') {
  await page.goto(`/panel/accounting/incomes${query}`, { waitUntil: 'domcontentloaded' });
  await expect(
    page.getByRole('heading', { name: 'Ingresos', exact: true }),
  ).toBeVisible({ timeout: 40_000 });
}

async function visibleIncomeIds(page) {
  return page.locator('[data-testid^="accounting-row-"]').evaluateAll((rows) =>
    rows.map((row) => Number(row.getAttribute('data-testid').replace('accounting-row-', ''))));
}

async function openIncomeMute(page, incomeId = 1) {
  await page.getByTestId(`income-actions-${incomeId}`).click();
  await page.getByTestId(`income-action-toggle-mute-${incomeId}`).click();
}

async function navigateToIncomesFromPanel(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < 1024) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  // The desktop sidebar names its navigation landmark; the compact drawer
  // exposes the same semantic link inside an unnamed dialog navigation.
  await page.getByRole('link', { name: 'Ingresos', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Ingresos', exact: true }),
  ).toBeVisible({ timeout: 25_000 });
}

async function openBulkClientAssignment(page) {
  await page.getByTestId('accounting-select-1').check();
  await page.getByTestId('accounting-select-2').check();
  await page.getByTestId('accounting-select-3').check();
  await page.getByTestId('accounting-select-4').check();
  await bulkAction(page, 'incomes', 'Asignar cliente');
}

const INCOME_INDICATOR_VIEWPORTS = [
  { alias: 'compact', compact: true },
  { alias: 'portrait', compact: true },
  { alias: 'landscape', compact: false },
  { alias: 'desktop', compact: false },
  { alias: 'wide', compact: false },
];

for (const viewport of INCOME_INDICATOR_VIEWPORTS) {
  test.describe(`Income indicator header — ${viewport.alias}`, () => {
    test.use(viewportUse(viewport.alias));

    test.beforeEach(async ({ page }) => {
      await setAuthLocalStorage(page, {
        token: 'e2e-token',
        userAuth: { id: 9001, role: 'admin', is_staff: true },
      });
    });

    test('keeps the indicator set compact at its reference width', {
      tag: [
        ...ADMIN_ACCOUNTING_INCOME_CRUD,
        '@role:admin',
        '@outcome:display',
        '@responsive:accounting',
      ],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({
        rows: INCOME_INDICATOR_ROWS,
        calls: [],
        meta: INCOME_INDICATOR_META,
      }));
      await navigateToIncomesFromPanel(page);

      const group = page.getByTestId(
        viewport.compact ? 'income-indicators-compact' : 'income-indicators-expanded',
      );
      const cards = group.locator('article');
      await expect(cards).toHaveCount(viewport.compact ? 2 : 4);
      const heights = await cards.evaluateAll((elements) => (
        elements.map((card) => Math.round(card.getBoundingClientRect().height))
      ));
      expect(new Set(heights).size).toBe(1);
      await expect(group.locator('button[aria-label^="Ayuda"]'))
        .toHaveCount(viewport.compact ? 2 : 4);

      const firstRow = await page.getByTestId('accounting-row-1').boundingBox();
      expect(firstRow.y).toBeLessThan(page.viewportSize().height);
    });
  });
}

test.describe('Income indicator actions', () => {
  test.use(viewportUse('compact'));

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('filters the list from the annual summary detail', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_CRUD,
      '@role:admin',
      '@outcome:success',
      '@responsive:accounting',
    ],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: INCOME_INDICATOR_ROWS,
      calls: [],
      meta: INCOME_INDICATOR_META,
    }));
    await page.clock.install({ time: new Date('2026-06-15T12:00:00Z') });
    await navigateToIncomesFromPanel(page);

    await page.getByTestId('income-stat-result-summary').click();
    await page.getByTestId('income-indicator-detail-liquid').click();

    await expect(page.getByTestId('accounting-row-2')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
    await expect(page).toHaveURL(/kind=liquid/);
    await expect(page).toHaveURL(/periodAfter=2026-01-01/);
  });

  test('selects the no-project quick filter from operational detail', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_CRUD,
      '@role:admin',
      '@outcome:success',
      '@responsive:accounting',
    ],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: INCOME_INDICATOR_ROWS,
      calls: [],
      meta: INCOME_INDICATOR_META,
    }));
    await navigateToIncomesFromPanel(page);

    await page.getByTestId('income-stat-operational-summary').click();
    await expect(page.locator('[data-testid^="income-indicator-detail-"]')).toHaveCount(4);
    await page.getByTestId('income-indicator-detail-no-project').click();

    await expect(page).toHaveURL(/accounting_incomeTab=no-project/);
    await expect(page.getByTestId('accounting-row-5')).toBeVisible();
    await expect(page.getByTestId('accounting-row-2')).toHaveCount(0);
  });
});

test.describe('Admin Accounting Incomes CRUD', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('renders the mocked income rows', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [incomeRow(), incomeRow({ id: 2, concept: 'Tendalux - Inicio 40%' })],
      calls,
    }));
    await gotoIncomes(page);

    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByTestId('accounting-row-2')).toBeVisible();
    await expect(page.getByText('Kore - Inicio 40%')).toBeVisible();
  });

  test('assigning a collection color preserves the manual switch', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await page.getByRole('combobox', {
      name: 'Probabilidad de cobro de Kore - Inicio 40%',
    }).selectOption('high');

    await expect(page.getByRole('switch', {
      name: 'Agregar Kore - Inicio 40% de pendientes por cobrar',
    })).not.toBeChecked();
    await expect.poll(() => calls.find((call) => (
      call.apiPath === 'accounting/incomes/1/update/'
    ))?.body).toEqual({ collection_confidence: 'high' });
  });

  test('the income form saves an unselected confidence classification', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await page.getByTestId('income-form-concept').fill('Soporte mensual Acme');
    await page.getByRole('tab', { name: 'Desarrollo' }).click();
    await page.getByTestId('income-form-period').fill('2026-09-04');
    await page.getByTestId('partner-split-total').fill('800000');
    await page.getByTestId('income-form-confidence').selectOption('medium');

    await expect(page.getByTestId('income-form-candidate')).not.toBeChecked();
    await page.getByTestId('income-form-submit').click();

    const created = calls.find((call) => call.apiPath === 'accounting/incomes/create/');
    expect(created.body.collection_confidence).toBe('medium');
    expect(created.body.is_receivable_candidate).toBe(false);
  });

  test('the income detail shows confidence outside the active forecast', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [incomeRow({ collection_confidence: 'low' })],
      calls: [],
    }));
    await navigateToIncomesFromPanel(page);

    await page.getByTestId('income-open-1').click();

    const forecast = page.getByTestId('income-detail-receivable');
    await expect(forecast).toContainText('Alto riesgo de pérdida');
    await expect(forecast).toContainText('Fuera de la previsión');
  });

  test('renders the classic leading menu control track', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display contract: control order, blank heading and fixed width are the observable outcome)
    // quality: allow-deep-link (the accounting subnav path is covered elsewhere; this test isolates table layout)
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls: [] }));
    await gotoIncomes(page);

    const actionsHeader = page.getByTestId('accounting-actions-header');
    const leadingHeaders = await actionsHeader.evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 3).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
        hasCheckbox: Boolean(cell.querySelector('input[type="checkbox"]')),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: null, label: null, text: '', hasCheckbox: true },
      { testId: 'accounting-actions-header', label: 'Acciones', text: '', hasCheckbox: false },
      { testId: null, label: null, text: 'Concepto', hasCheckbox: false },
    ]);
    await expect(actionsHeader).toHaveCSS('width', '56px');
    // The kebab keeps the same 44px target as every other accounting table.
    const kebab = await page.getByTestId('income-actions-1').boundingBox();
    expect(Math.round(kebab.width)).toBe(44);
    expect(Math.round(kebab.height)).toBe(44);
  });

  test('the classic income table fits the compact viewport', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (the arrival geometry is the outcome)
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls: [] }));
    await gotoIncomes(page);

    const row = page.getByTestId('accounting-row-1');
    const table = row.locator('xpath=ancestor::table');
    const scroller = table.locator('..');
    const action = page.getByTestId('income-actions-1');
    const kind = page.getByTestId('income-kind-1').filter({ visible: true });

    expect(await scroller.evaluate((element) => element.scrollWidth <= element.clientWidth))
      .toBe(true);
    await expect(action).toBeVisible();
    await expect(kind).toHaveCSS('white-space', 'nowrap');
    expect(await action.evaluate((element) => {
      const button = element.matches('button') ? element : element.querySelector('button');
      const box = button.getBoundingClientRect();
      const rowBox = element.closest('[data-testid^="accounting-row-"]').getBoundingClientRect();
      return box.left >= rowBox.left && box.right <= rowBox.right;
    })).toBe(true);
  });

  test('creates an income with automatic 50/50 split', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await expect(page.getByRole('heading', { name: 'Nuevo ingreso' })).toBeVisible();

    await page.getByTestId('income-form-concept').fill('Vastago (Fase 1) - Inicio 40%');
    // Required: the line of business is what decides the shape of the record.
    await page.getByRole('tab', { name: 'Desarrollo' }).click();
    // The period asks for the exact date by default.
    await page.getByTestId('income-form-period').fill('2026-04-15');
    await page.getByTestId('partner-split-total').fill('2123000');
    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('Ingreso creado')).toBeVisible();
    expect(calls).toHaveLength(1);
    expect(calls[0].body.concept).toBe('Vastago (Fase 1) - Inicio 40%');
    expect(Number(calls[0].body.gustavo_amount)).toBe(1061500);
    expect(Number(calls[0].body.carlos_amount)).toBe(1061500);
  });

  test('creates an income with a month-only period via the toggle', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await page.getByTestId('income-form-concept').fill('Hosting Acme, Abril');
    await page.getByRole('tab', { name: 'Otro' }).click();
    // Only the month is known: downgrade the exact-date default.
    await page.getByTestId('income-form-exact-date').click();
    await page.getByTestId('income-form-period').fill('2026-04');
    await page.getByTestId('partner-split-total').fill('86400');
    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('Ingreso creado')).toBeVisible();
    expect(calls).toHaveLength(1);
    expect(calls[0].body.period_date).toBe('2026-04');
  });

  test('creates a personal-ledger income with a single value field', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await expect(page.getByRole('heading', { name: 'Nuevo ingreso' })).toBeVisible();

    await page.getByTestId('income-form-concept').fill('Universidad Nacional');
    await page.getByRole('tab', { name: 'Diagnóstico' }).click();
    await page.getByTestId('income-form-period').fill('2026-02-10');
    await page.getByRole('tab', { name: 'Personal Gustavo' }).click();

    // Personal ledger swaps the partner split for a single value input.
    await expect(page.getByTestId('partner-split-total')).toHaveCount(0);
    await page.locator('form input[inputmode="numeric"]').fill('1400000');
    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('Ingreso creado')).toBeVisible();
    expect(calls).toHaveLength(1);
    expect(calls[0].body.ledger).toBe('gustavo');
    expect(Number(calls[0].body.total_amount)).toBe(1400000);
    expect(calls[0].body.gustavo_amount).toBeUndefined();
    expect(calls[0].body.carlos_amount).toBeUndefined();
  });

  test('empty required fields block the POST via HTML5 validation', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await page.getByTestId('income-form-submit').click();

    // The native required validation keeps the form open and fires no POST.
    await expect(page.getByRole('heading', { name: 'Nuevo ingreso' })).toBeVisible();
    expect(calls).toHaveLength(0);
  });

  test('edit prefills the record and PATCHes the change', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    const rows = [incomeRow()];
    await mockApi(page, buildHandler({ rows, calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-edit-1').click();
    await expect(page.getByRole('heading', { name: 'Editar ingreso' })).toBeVisible();
    await expect(page.getByTestId('income-form-concept')).toHaveValue('Kore - Inicio 40%');

    await page.getByTestId('partner-split-total').fill('2000000');
    // The row predates the origin, and the form asks for it before saving:
    // that is how the book gets classified, one edited record at a time.
    await page.getByRole('tab', { name: 'Desarrollo' }).click();
    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('Ingreso actualizado')).toBeVisible();
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe('PATCH');
    expect(Number(calls[0].body.total_amount)).toBe(2000000);
    expect(calls[0].body.origin).toBe('development');
  });

  test('duplicating a collected income opens the next period and POSTs it', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    const rows = [incomeRow({
      kind: 'liquid', kind_label: 'Líquido', origin: 'hosting',
      concept: 'Kore - Hosting anual',
    })];
    await mockApi(page, buildHandler({ rows, calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-duplicate-1').click();

    await expect(page.getByRole('heading', { name: 'Duplicar ingreso' })).toBeVisible();
    await expect(page.getByTestId('income-form-concept'))
      .toHaveValue('Kore - Hosting anual');
    // A hosting duplicate opens on the window block: the proposed date lands
    // on the start, labelled with where it came from.
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('2027-02-01');
    await expect(page.getByTestId('income-form-period-hint'))
      .toContainText('hosting');

    // The shortcut writes the cadence selector and the inclusive end follows.
    await page.getByTestId('income-form-cycle-12').click();
    await expect(page.getByTestId('income-form-period-cadence')).toHaveValue('annual');
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2028-01-31');

    await page.getByTestId('income-form-submit').click();

    // Named as a duplicate, so it reads apart from a manual alta in the
    // notification history.
    await expect(page.getByText('Ingreso duplicado')).toBeVisible();
    const created = calls.find((call) => call.apiPath === 'accounting/incomes/create/');
    expect(created.method).toBe('POST');
    expect(created.body.concept).toBe('Kore - Hosting anual');
    // Born pending whatever the original was — the point of the action.
    expect(created.body.kind).toBe('expected');
    // The window travels; period_date is the backend's to derive.
    expect(created.body.period_start).toBe('2027-02-01');
    expect(created.body.period_end).toBe('2028-01-31');
    expect(created.body.period_cadence).toBe('annual');
    expect(created.body.period_date).toBeUndefined();
  });

  test('a duplicate opens on the original business line, date block included', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the list is reached from the sidebar, covered by
    // the navigation flow; every test in this file opens it through gotoIncomes)
    //
    // The origin is not one more copied field: it decides whether the form
    // asks for a covered window or a single date. A duplicate that lost it
    // would open configured as a different kind of income than the original.
    const rows = [incomeRow({ origin: 'hosting', concept: 'Kore - Hosting anual' })];
    await mockApi(page, buildHandler({ rows, calls: [] }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-duplicate-1').click();

    await expect(page.getByRole('heading', { name: 'Duplicar ingreso' })).toBeVisible();
    await expect(
      page.getByTestId('income-form-origin').getByRole('tab', { name: 'Hosting' }),
    ).toHaveAttribute('aria-selected', 'true');
    // The window block, which only a hosting origin brings up.
    await expect(page.getByTestId('income-form-period-cadence')).toBeVisible();
    await expect(page.getByTestId('income-form-origin-notice')).toHaveCount(0);
  });

  test('duplicating an unclassified income says so and refuses to save', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Most of the book predates the field. The copy is faithful — it carries
    // the blank — and saying so is what keeps it from reading as a copy that
    // failed, which is how it was reported.
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow({ origin: '' })], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-duplicate-1').click();

    await expect(page.getByRole('heading', { name: 'Duplicar ingreso' })).toBeVisible();
    await expect(page.getByTestId('income-form-origin-notice'))
      .toContainText('El ingreso original no tiene origen registrado');
    // And it is not a suggestion: saving without one is refused in the form.
    await page.getByTestId('income-form-submit').click();
    await expect(page.getByText('Elige la línea de negocio del ingreso.')).toBeVisible();
    expect(calls.some((call) => call.apiPath === 'accounting/incomes/create/'))
      .toBe(false);
  });

  test('duplicating an income with no recorded window counts from the original', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // The everyday case until every hosting income carries its window: the
    // original has none and its client holds several hostings, so the catalog
    // cannot decide either. The draft proposes nothing, but it still says what
    // to count from — the original's own date — and the form chains on that
    // instead of opening the window on today, which continues nothing.
    const calls = [];
    const rows = [incomeRow({
      kind: 'liquid', kind_label: 'Líquido', origin: 'hosting',
      concept: 'Kore - Hosting',
    })];
    await mockApi(page, buildHandler({
      rows,
      calls,
      duplicateDraftPeriod: {
        period_date: null,
        period_date_source: null,
        period_anchor: {
          source: 'original_date',
          start: null,
          origin_start: null,
          origin_end: null,
          origin_date: '2026-02-01',
        },
      },
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-duplicate-1').click();

    await expect(page.getByRole('heading', { name: 'Duplicar ingreso' })).toBeVisible();
    // Nothing to prefill: only the cadence can say how long that period was.
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('');
    const notice = page.getByTestId('income-form-anchor-notice');
    await expect(notice).toContainText('1 feb 2026');
    await expect(notice).toContainText('periodicidad');

    // Counted from the original's date, not from today: three months after
    // 1 feb 2026 the period it covered would have closed, so this one opens.
    await page.getByTestId('income-form-period-cadence').selectOption('quarterly');
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('2026-05-01');
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2026-07-31');

    // With no recorded end, the length just chosen is what decides where the
    // original's period closed, so the whole window moves with it.
    await page.getByTestId('income-form-period-cadence').selectOption('annual');
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('2027-02-01');
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2028-01-31');

    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('Ingreso duplicado')).toBeVisible();
    const created = calls.find((call) => call.apiPath === 'accounting/incomes/create/');
    expect(created.body.period_start).toBe('2027-02-01');
    expect(created.body.period_end).toBe('2028-01-31');
    expect(created.body.period_cadence).toBe('annual');
  });

  test('a hosting income asks for the period it covers and submits it', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await page.getByTestId('income-form-concept').fill('Hosting Acme anual');

    // Turning the origin to Hosting swaps the single date for the window.
    await page.getByRole('tab', { name: 'Hosting' }).click();
    await expect(page.getByTestId('income-form-period')).toHaveCount(0);
    await page.getByTestId('income-form-period-start').fill('2026-08-15');
    await page.getByTestId('income-form-period-cadence').selectOption('semiannual');
    // Inclusive end proposed from start + cadence, still editable.
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2027-02-14');

    await page.getByTestId('partner-split-total').fill('550000');
    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('Ingreso creado')).toBeVisible();
    expect(calls[0].body.period_start).toBe('2026-08-15');
    expect(calls[0].body.period_end).toBe('2027-02-14');
    expect(calls[0].body.period_cadence).toBe('semiannual');
  });

  test('picking a periodicity opens the window on the period after the last one', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await page.getByTestId('income-form-concept').fill('Hosting Acme');
    await page.getByRole('tab', { name: 'Hosting' }).click();

    // Nothing typed: the periodicity is chosen first and the dates follow it.
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('');
    await page.getByTestId('income-form-period-cadence').selectOption('quarterly');
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('2026-09-01');
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2026-11-30');
    await expect(page.getByTestId('income-form-period-hint'))
      .toContainText('El período anterior terminó');

    // Moving the start carries the end with it, cadence intact.
    await page.getByTestId('income-form-period-start').fill('2026-10-01');
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2026-12-31');
    await expect(page.getByTestId('income-form-period-cadence')).toHaveValue('quarterly');

    // Writing the end by hand is what makes the window custom: the selector
    // must never claim a periodicity the dates no longer describe.
    await page.getByTestId('income-form-period-end').fill('2027-01-20');
    await expect(page.getByTestId('income-form-period-cadence')).toHaveValue('custom');

    await page.getByTestId('partner-split-total').fill('300000');
    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('Ingreso creado')).toBeVisible();
    expect(calls[0].body.period_start).toBe('2026-10-01');
    expect(calls[0].body.period_end).toBe('2027-01-20');
    expect(calls[0].body.period_cadence).toBe('custom');
  });

  test('a shortcut re-lengthens the proposed window instead of walking past it', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ rows: [], calls: [] }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await page.getByRole('tab', { name: 'Hosting' }).click();

    await page.getByTestId('income-form-cycle-12').click();
    await expect(page.getByTestId('income-form-period-cadence')).toHaveValue('annual');
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('2026-09-01');
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2027-08-31');

    // Same window, different length — the start stays on the antecedent.
    await page.getByTestId('income-form-cycle-3').click();
    await expect(page.getByTestId('income-form-period-start')).toHaveValue('2026-09-01');
    await expect(page.getByTestId('income-form-period-end')).toHaveValue('2026-11-30');
  });

  test('a cadence shortcut overrides the proposed date before saving', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-duplicate-1').click();
    await expect(page.getByTestId('income-form-period')).toHaveValue('2027-02-01');

    // The proposal is annual; this charge is really quarterly.
    await page.getByTestId('income-form-cycle-3').click();

    await expect(page.getByTestId('income-form-period')).toHaveValue('2026-05-01');
    // Picking a date the hosting cycle did not produce retires its hint.
    await expect(page.getByTestId('income-form-period-hint')).toHaveCount(0);

    await page.getByRole('tab', { name: 'Otro' }).click();
    await page.getByTestId('income-form-submit').click();

    const created = calls.find((call) => call.apiPath === 'accounting/incomes/create/');
    expect(created.body.period_date).toBe('2026-05-01');
  });

  // Antes el detalle sólo existía detrás del kebab y no tenía dirección: no se
  // podía compartir, ni recargar dentro de él, ni — el motivo de fondo —
  // publicarlo en el enlace de la fila.
  test('el concepto enlaza al detalle y la dirección sobrevive una recarga', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls: [] }));
    await gotoIncomes(page);

    await expect(page.getByTestId('income-open-1')).toHaveAttribute('href', /income=1/);

    await page.getByTestId('income-open-1').click();

    await expect(page.getByTestId('income-detail-modal')).toBeVisible();
    await expect(page).toHaveURL(/income=1/);

    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('income-detail-modal')).toBeVisible({ timeout: 25_000 });
  });

  test('duplicating from the detail modal opens the same seeded form', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-detail-1').click();
    await expect(page.getByTestId('income-detail-modal')).toBeVisible();

    await page.getByTestId('income-detail-duplicate').click();

    // The detail closes and the seeded form takes its place.
    await expect(page.getByTestId('income-detail-modal')).toHaveCount(0);
    await expect(page.getByTestId('income-form-concept'))
      .toHaveValue('Kore - Inicio 40%');
  });

  test('a failing draft surfaces the error and opens no form', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [incomeRow()], calls, duplicateDraftStatus: 500,
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-duplicate-1').click();

    await expect(page.getByText('No se pudo preparar el duplicado')).toBeVisible();
    await expect(page.getByTestId('income-form-concept')).toHaveCount(0);
  });

  test('delete asks for confirmation and removes the row', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-delete-1').click();
    await expect(page.getByText('Eliminar ingreso')).toBeVisible();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Ingreso eliminado')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
    expect(calls.some((call) => call.method === 'DELETE')).toBe(true);
  });

  test('cancelling the confirmation fires no DELETE', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-delete-1').click();
    await expect(page.getByText('Eliminar ingreso')).toBeVisible();
    await page.getByRole('button', { name: 'Cancelar' }).click();

    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false);
  });

  test('a 400 on create surfaces the backend error and keeps the modal open', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls, createStatus: 400 }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-new-button').click();
    await page.getByTestId('income-form-concept').fill('Ingreso inválido');
    await page.getByRole('tab', { name: 'Desarrollo' }).click();
    await page.getByTestId('income-form-period').fill('2026-04-15');
    await page.getByTestId('partner-split-total').fill('100');
    await page.getByTestId('income-form-submit').click();

    await expect(page.getByText('No se pudo guardar')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Nuevo ingreso' })).toBeVisible();
  });
});

test.describe('Admin Accounting Income Reminder Mute', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
    await page.clock.install({ time: new Date('2026-09-01T12:00:00Z') });
  });

  test('shows a dated silence on the income row', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_REMINDER_MUTE,
      '@role:admin',
      '@outcome:display',
    ],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [incomeRow({
        reminders_muted: true,
        reminders_muted_until: '2026-09-30',
      })],
      calls: [],
    }));

    await navigateToIncomesFromPanel(page);

    const badge = page.getByTestId('income-muted-1').filter({ visible: true });
    await expect(badge).toHaveText('Silenciado hasta 30 sep');
    await expect(badge).toHaveAttribute(
      'title', 'Los avisos se reanudan el Mié, 30 sep 2026',
    );
  });

  test('silences income reminders until the chosen date', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_REMINDER_MUTE,
      '@role:admin',
      '@outcome:success',
    ],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await openIncomeMute(page);
    await page.getByTestId('income-mute-date').fill('2026-09-30');
    await page.getByTestId('income-mute-submit').click();

    await expect(page.getByText('Avisos silenciados')).toBeVisible();
    await expect(page.getByTestId('income-muted-1').filter({ visible: true }))
      .toHaveText('Silenciado hasta 30 sep');
    const call = calls.find((item) => item.apiPath.endsWith('/mute/'));
    expect(call.body).toEqual({ muted: true, until: '2026-09-30' });
  });

  test('silences income reminders indefinitely', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_REMINDER_MUTE,
      '@role:admin',
      '@outcome:success',
    ],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await openIncomeMute(page);
    await page.getByRole('tab', { name: 'Indefinidamente', exact: true }).click();
    await page.getByTestId('income-mute-submit').click();

    await expect(page.getByTestId('income-muted-1').filter({ visible: true }))
      .toHaveText('Silenciado');
    const call = calls.find((item) => item.apiPath.endsWith('/mute/'));
    expect(call.body).toEqual({ muted: true, until: null });
  });

  test('reactivates reminders from a silenced income', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_REMINDER_MUTE,
      '@role:admin',
      '@outcome:success',
    ],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [incomeRow({ reminders_muted: true })], calls,
    }));
    await gotoIncomes(page);

    await openIncomeMute(page);

    await expect(page.getByText('Avisos reactivados')).toBeVisible();
    await expect(page.getByTestId('income-muted-1')).toHaveCount(0);
    const call = calls.find((item) => item.apiPath.endsWith('/mute/'));
    expect(call.body).toEqual({ muted: false });
  });

  test('blocks a resume date that is not in the future', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_REMINDER_MUTE,
      '@role:admin',
      '@outcome:error',
    ],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await openIncomeMute(page);
    await page.getByTestId('income-mute-date').fill('2026-09-01');

    await expect(page.getByText('Elige una fecha posterior a hoy.')).toBeVisible();
    await expect(page.getByTestId('income-mute-submit')).toBeDisabled();
    expect(calls.some((item) => item.apiPath.endsWith('/mute/'))).toBe(false);
  });

  test('keeps the reminder state when the API rejects the mute', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_REMINDER_MUTE,
      '@role:admin',
      '@outcome:failure',
    ],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [incomeRow()], calls: [], muteStatus: 500,
    }));
    await gotoIncomes(page);

    await openIncomeMute(page);
    await page.getByTestId('income-mute-date').fill('2026-09-30');
    await page.getByTestId('income-mute-submit').click();

    await expect(page.getByText('No se pudieron silenciar los avisos')).toBeVisible();
    await expect(page.getByTestId('income-mute-modal')).toBeVisible();
    await expect(page.getByTestId('income-muted-1')).toHaveCount(0);
  });
});

test.describe('Admin Accounting Incomes: liquidation, write-off and paid state', () => {
  const paidRow = (overrides = {}) => incomeRow({
    id: 10,
    concept: 'Kore - Pagado',
    paid_amount: '1160000.00',
    pending_amount: '0.00',
    payment_status: 'paid',
    payment_status_label: 'Pagado',
    ...overrides,
  });

  const partialRow = () => incomeRow({
    id: 11,
    concept: 'Kore - Parcial',
    total_amount: '1000000.00',
    paid_amount: '400000.00',
    pending_amount: '600000.00',
    payment_status: 'partial',
    payment_status_label: 'Parcial',
  });

  const lostRow = () => incomeRow({
    id: 12,
    concept: 'Catherine Ruiz Candles',
    kind: 'lost',
    kind_label: 'Perdido',
    total_amount: '460000.00',
    paid_amount: null,
    pending_amount: null,
    payment_status: null,
    payment_status_label: null,
  });

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('tints paid and partial rows and shows what is still missing', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [incomeRow(), paidRow(), partialRow()],
      calls: [],
    }));
    await gotoIncomes(page);

    await expect(page.getByTestId('accounting-row-10')).toHaveClass(/bg-success-soft/);
    await expect(page.getByTestId('accounting-row-11')).toHaveClass(/bg-warning-soft/);
    // Pending rows stay neutral.
    await expect(page.getByTestId('accounting-row-1')).toHaveClass(/bg-surface/);

    await expect(page.getByTestId('income-payment-10').filter({ visible: true })).toContainText('Pagado');
    await expect(page.getByTestId('income-payment-11').filter({ visible: true })).toContainText('Parcial');
    await expect(page.getByTestId('income-payment-11').filter({ visible: true })).toContainText('600.000');
  });

  test('lands on Esperados por cobrar, keeping the partials and dropping the paid', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching /panel/accounting/incomes through the
    // subnav is exercised by the accounting navigation specs; this test pins
    // the landing tab, which only exists on a bare URL)
    await mockApi(page, buildHandler({
      rows: [incomeRow(), paidRow(), partialRow()],
      calls: [],
      savedTabs: [
        {
          id: 501, view: 'accounting_income', name: 'Todos los esperados',
          filters: { kind: ['expected'] }, order: 0,
        },
      ],
    }));
    // No query param: the view must open already filtered.
    await gotoIncomes(page, '');

    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByTestId('accounting-row-10')).toHaveCount(0);
    // The partially paid one STAYS. This assertion used to read `toHaveCount(0)`
    // and that was the bug: an esperado with an abono is still por cobrar, and
    // hiding it here is what made a just-registered abono look like it had
    // never been created.
    await expect(page.getByTestId('accounting-row-11')).toBeVisible();
    await expect(page.getByTestId('income-payment-11').filter({ visible: true })).toContainText('Parcial');

    // The saved "Todos los esperados" tab widens it back to every expected row,
    // the collected one included.
    await page.getByTestId('filter-tabs-tab-501').click();
    await expect(page.getByTestId('accounting-row-10')).toBeVisible();
    await expect(page.getByTestId('accounting-row-11')).toBeVisible();
  });

  test('the Hosting esperados tab narrows the uncollected rows by concept', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching /panel/accounting/incomes through the
    // subnav is exercised by the accounting navigation specs; this test pins
    // the builtin hosting tab)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow(),
        incomeRow({ id: 3, concept: 'Hosting anual acme.com' }),
        paidRow({ id: 13, concept: 'Hosting anual kore.co' }),
      ],
      calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('filter-tabs-tab-hosting-expected').click();

    // Only the uncollected hosting row survives: the non-hosting concept is
    // filtered out by the search term, the paid one by the payment status.
    await expect(page.getByTestId('accounting-row-3')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
    await expect(page.getByTestId('accounting-row-13')).toHaveCount(0);
    await expect(page.getByTestId('incomes-search-input')).toHaveValue('hosting');
  });

  test('shows written-off income in Todos and isolates it with the Perdidos tab', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching /panel/accounting/incomes through the
    // subnav is exercised by the accounting navigation specs; this test pins
    // the written-off row data under Todos and the builtin Perdidos tab)
    await mockApi(page, buildHandler({
      rows: [incomeRow(), lostRow()],
      calls: [],
      meta: { lost_total: '460000.00' },
    }));
    await gotoIncomes(page);

    // "Todos" really shows everything, written-off rows included.
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByTestId('accounting-row-12')).toBeVisible();
    await expect(page.getByTestId('incomes-total-lost')).toContainText('460.000');

    // The builtin quick tab isolates the lost rows.
    await page.getByTestId('filter-tabs-tab-lost').click();

    await expect(page.getByTestId('accounting-row-12')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
  });

  test('liquidating prefills the pending amount and keeps the expected row', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    const listFetches = { count: 0 };
    await mockApi(page, buildHandler({
      rows: [partialRow()], calls, listFetches,
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    await expect(
      page.getByRole('heading', { name: 'Liquidar ingreso esperado' }),
    ).toBeVisible();
    // Defaults to what is still owed, not the full projection.
    await expect(page.getByTestId('partner-split-total')).toHaveValue('600.000');

    // The period input asks for the exact payment date by default.
    await page.getByTestId('income-liquidate-period').fill('2026-11-17');
    await page.getByTestId('income-liquidate-submit').click();

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length)
      .toBe(1);
    const call = calls.find((c) => c.method === 'POST');
    // The parent is identified by the URL; kind/ledger are derived server-side.
    expect(call.apiPath).toBe('accounting/incomes/11/settle/');
    expect(call.body.period_date).toBe('2026-11-17');
    // Liquidated money defaults into the pocket.
    expect(call.body.destination).toBe('pocket');
    // Nothing allocated → behaves exactly like the old plain liquidation.
    expect(call.body.deductions).toEqual([]);
    expect(call.body.expected_incomes).toEqual([]);

    // The parent's paid state is server-computed, so the list must refetch.
    await expect.poll(() => listFetches.count).toBeGreaterThan(1);
    await expect(page.getByTestId('accounting-row-11')).toBeVisible();
  });

  test('books the shortfall of a settlement as a deduction expense', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [partialRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    // 600.000 pending, 592.000 received → an 8.000 gateway fee.
    await page.getByTestId('partner-split-total').fill('592000');
    await page.getByTestId('income-liquidate-period').fill('2026-11-17');

    await expect(page.getByTestId('income-liquidate-shortfall')).toBeVisible();
    // The deductions group auto-expands the moment the shortfall appears.
    await expect(page.getByTestId('income-liquidate-deduction-0')).toBeVisible();
    // The concept starts unselected ("Seleccionar concepto") on purpose.
    await page.getByTestId('deduction-type-0').selectOption('gateway_fee');
    await page.getByTestId('deduction-amount-0').fill('8000');
    await expect(page.getByTestId('income-liquidate-remaining'))
      .toContainText('queda cerrado');
    await page.getByTestId('income-liquidate-submit').click();

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length)
      .toBe(1);
    const { body } = calls.find((c) => c.method === 'POST');
    expect(body.deductions).toEqual([
      { type: 'gateway_fee', detail: '', amount: 8000 },
    ]);
  });

  test('resolves the full pending as a deduction without registering a payment', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // The stuck-residual case: an old partial collection left a fee that
    // will never arrive, and there is no new payment to register.
    const calls = [];
    await mockApi(page, buildHandler({ rows: [partialRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    await page.getByTestId('partner-split-total').fill('0');
    await page.getByTestId('income-liquidate-period').fill('2026-11-17');

    await expect(page.getByTestId('income-liquidate-shortfall')).toBeVisible();
    // The deductions group auto-expands the moment the shortfall appears.
    await expect(page.getByTestId('income-liquidate-deduction-0')).toBeVisible();
    await page.getByTestId('deduction-type-0').selectOption('gateway_fee');
    await page.getByTestId('deduction-amount-0').fill('600000');
    await expect(page.getByTestId('income-liquidate-remaining'))
      .toContainText('queda cerrado');
    await page.getByTestId('income-liquidate-submit').click();

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length)
      .toBe(1);
    const { body } = calls.find((c) => c.method === 'POST');
    expect(Number(body.total_amount)).toBe(0);
    expect(body.deductions).toEqual([
      { type: 'gateway_fee', detail: '', amount: 600000 },
    ]);
  });

  test('reschedules the shortfall as a new expected income', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [partialRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    await page.getByTestId('partner-split-total').fill('500000');
    await page.getByTestId('income-liquidate-period').fill('2026-11-17');

    await page.getByTestId('income-liquidate-followups-toggle').click();
    await page.getByTestId('followup-concept-0').fill('Kore - saldo diciembre');
    await page.getByTestId('followup-period-0').fill('2026-12');
    await page.getByTestId('followup-amount-0').fill('100000');
    await page.getByTestId('income-liquidate-submit').click();

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length)
      .toBe(1);
    const { body } = calls.find((c) => c.method === 'POST');
    expect(body.expected_incomes).toEqual([
      {
        concept: 'Kore - saldo diciembre',
        period_date: '2026-12',
        amount: 100000,
      },
    ]);
  });

  test('surfaces a backend rejection of the settlement and keeps the modal open', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [partialRow()], calls, createStatus: 400,
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    await page.getByTestId('income-liquidate-period').fill('2026-11-17');
    await page.getByTestId('income-liquidate-submit').click();

    await expect(page.getByText('No se pudo liquidar')).toBeVisible();
    // The modal stays open so the user can correct the amounts.
    await expect(
      page.getByRole('heading', { name: 'Liquidar ingreso esperado' }),
    ).toBeVisible();
  });

  test('blocks a settlement that allocates more than the shortfall', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [partialRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    await page.getByTestId('partner-split-total').fill('592000');
    await page.getByTestId('income-liquidate-period').fill('2026-11-17');
    // The deductions group auto-expands the moment the shortfall appears.
    await expect(page.getByTestId('income-liquidate-deduction-0')).toBeVisible();
    await page.getByTestId('deduction-type-0').selectOption('gateway_fee');
    await page.getByTestId('deduction-amount-0').fill('50000');

    await expect(page.getByTestId('income-liquidate-remaining'))
      .toContainText('Te pasaste');
    // The offending line is flagged with the excess, keeping what was typed.
    await expect(page.getByTestId('deduction-error-0'))
      .toContainText('supera el saldo');
    await expect(page.getByTestId('deduction-amount-0')).toHaveValue('50.000');
    await expect(page.getByTestId('income-liquidate-submit-reason'))
      .toContainText('supera el saldo por resolver');
    await expect(page.getByTestId('income-liquidate-submit')).toBeDisabled();
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(0);
  });

  test('requires picking a deduction concept before liquidating', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [partialRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    await page.getByTestId('partner-split-total').fill('592000');
    await page.getByTestId('income-liquidate-period').fill('2026-11-17');
    await expect(page.getByTestId('income-liquidate-deduction-0')).toBeVisible();
    await page.getByTestId('deduction-amount-0').fill('8000');

    await expect(page.getByTestId('deduction-error-0'))
      .toHaveText('Selecciona el concepto.');
    await expect(page.getByTestId('income-liquidate-submit-reason'))
      .toContainText('líneas de gasto incompletas');
    await expect(page.getByTestId('income-liquidate-submit')).toBeDisabled();

    // Picking the concept clears the flag and unlocks the submit.
    await page.getByTestId('deduction-type-0').selectOption('gateway_fee');
    await expect(page.getByTestId('deduction-error-0')).toHaveCount(0);
    await expect(page.getByTestId('income-liquidate-submit')).toBeEnabled();
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(0);
  });

  test('suggests the remaining amount inside the deduction line', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (same gotoIncomes harness as every settle spec
    // in this file; the flow under test is the settle modal's suggestion, not
    // the view entry)
    const calls = [];
    await mockApi(page, buildHandler({ rows: [partialRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-11').click();
    await page.getByTestId('income-action-liquidate-11').click();
    await page.getByTestId('partner-split-total').fill('592000');
    await expect(page.getByTestId('income-liquidate-deduction-0')).toBeVisible();
    await expect(page.getByTestId('income-liquidate-remaining'))
      .toContainText('Sin asignar');

    // The empty line offers exactly what is left to allocate…
    await expect(page.getByTestId('deduction-amount-0'))
      .toHaveAttribute('placeholder', '8.000');
    // …and clicking the empty field adopts it, ready to be overtyped.
    await page.getByTestId('deduction-amount-0').click();
    await expect(page.getByTestId('deduction-amount-0')).toHaveValue('8.000');
    await expect(page.getByTestId('income-liquidate-remaining'))
      .toContainText('queda cerrado');
  });

  test('writes off a pending expected income', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow()], calls }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-write-off-1').click();
    await page.getByRole('button', { name: 'Marcar como perdido' }).last().click();

    await expect.poll(() => calls.filter((c) => c.method === 'PATCH').length)
      .toBe(1);
    const body = calls.find((c) => c.method === 'PATCH').body;
    expect(body.kind).toBe('lost');
    expect(body.destination).toBe('partners');
  });

  test('offers no write-off on an already collected income', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // The server rejects writing off a row with liquidations, so the
    // action must not be offered for paid or partial rows.
    await mockApi(page, buildHandler({
      rows: [paidRow(), partialRow()], calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-10').click();
    await expect(page.getByTestId('income-action-liquidate-10')).toBeVisible();
    await page.keyboard.press('Escape');
    await page.getByTestId('income-actions-10').click();
    await expect(page.getByTestId('income-action-write-off-10')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await page.getByTestId('income-actions-11').click();
    await expect(page.getByTestId('income-action-write-off-11')).toHaveCount(0);
    await page.keyboard.press('Escape');
  });

  test('shows no row actions on a written-off income', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — a written-off row must offer no
    // liquidate/write-off actions; since Jul 2026 it is visible under Todos,
    // so there is no filter to click before asserting)
    // quality: allow-deep-link (same subnav-entry rationale as above)
    await mockApi(page, buildHandler({ rows: [lostRow()], calls: [] }));
    await gotoIncomes(page);

    // Lost rows are visible in the default "Todos" view.
    await expect(page.getByTestId('accounting-row-12')).toBeVisible();
    await page.getByTestId('income-actions-12').click();
    await expect(page.getByTestId('income-action-liquidate-12')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await page.getByTestId('income-actions-12').click();
    await expect(page.getByTestId('income-action-write-off-12')).toHaveCount(0);
    await page.keyboard.press('Escape');
  });
});

test.describe('Admin Accounting Incomes — cuenta de cobro entry point', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the generate action opens the create modal with the income locked', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [incomeRow({ has_collection_account: false })], calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-generate-collection-1').click();

    await expect(
      page.getByRole('heading', { name: 'Nueva cuenta de cobro' }),
    ).toBeVisible();
    await expect(page.getByTestId('collection-form-income-locked'))
      .toContainText('Kore - Inicio 40%');
    await expect(page.getByTestId('collection-form-concept'))
      .toHaveValue('Kore - Inicio 40%');
  });

  test('a linked income swaps to Ver cuenta de cobro and navigates focused', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [incomeRow({
        has_collection_account: true,
        collection_account_id: 33,
        collection_account_number: 'PA-KORE-001',
      })],
      calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-actions-1').click();
    await expect(page.getByTestId('income-action-generate-collection-1')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-view-collection-1').click();

    // `focus` viaja en el salto y la vista de destino lo suelta al montar: es
    // una acción de una sola vez, no un estado de la vista.
    await page.waitForURL('**/panel/accounting/collections?focus=33');
    await expect(page).toHaveURL(/\/panel\/accounting\/collections/);
  });
});


test.describe('Admin Accounting Incomes — cliente del ingreso', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the client column shows the linked client and "Sin cliente" isolates the rest', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; what is under
    // test is the Sin cliente tab, which IS clicked below)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, client: 5, client_name: 'Ana Pérez' }),
        incomeRow({ id: 2, concept: 'Reembolso banco' }),
      ],
      calls: [],
    }));
    await gotoIncomes(page);

    await expect(page.getByTestId('accounting-row-1')).toContainText('Ana Pérez');
    // The unassigned row wears the completion pill instead of an empty cell.
    await expect(page.getByTestId('income-unlinked-2').filter({ visible: true })).toContainText('sin vincular');

    // The builtin tab is the completion group: only the unassigned survive.
    await page.getByTestId('filter-tabs-tab-no-client').click();

    await expect(page.getByTestId('accounting-row-2')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
  });

  test('the bulk assignment keeps its complete review visible', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Bug caught: a short modal clipped the client results and hid the records
    // the operator must review before confirming the mass assignment.
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
        incomeRow({ id: 3, concept: 'Kore - Integración 20%' }),
        incomeRow({ id: 4, concept: 'Kore - Cierre 10%' }),
      ],
      calls,
    }));
    await navigateToIncomesFromPanel(page);
    await openBulkClientAssignment(page);

    const modal = page.getByTestId('incomes-bulk-assign-modal');
    await expect(modal).toContainText('4 ingresos seleccionados');
    await expect(page.getByTestId('incomes-bulk-client')).toBeFocused();

    const initialScope = page.getByTestId('incomes-bulk-selection-review');
    expect(await initialScope.evaluate((element) => ({
      hasEveryRecord: [
        'Kore - Inicio 40%',
        'Kore - Entrega 30%',
        'Kore - Integración 20%',
        'Kore - Cierre 10%',
      ].every((label) => element.textContent.includes(label)),
      fitsWithoutScroll: element.scrollHeight <= element.clientHeight + 1,
    }))).toEqual({ hasEveryRecord: true, fitsWithoutScroll: true });

    const catalog = page.getByRole('grid', { name: 'Clientes disponibles' });
    const scroller = page.getByTestId('client-catalog-scroll');
    await expect(catalog).toBeVisible();
    const fifthOption = page.getByTestId('client-autocomplete-option-9');
    await expect(fifthOption).toBeVisible();
    const listBounds = await scroller.boundingBox();
    const fifthBounds = await fifthOption.boundingBox();
    expect(fifthBounds.y + fifthBounds.height).toBeLessThanOrEqual(
      listBounds.y + listBounds.height + 1,
    );

    const modalBounds = await modal.boundingBox();
    await scroller.hover();
    await page.mouse.wheel(0, 600);
    await expect.poll(() => scroller.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(0);
    expect((await modal.boundingBox()).y).toBe(modalBounds.y);
    expect(await modal.locator('..').evaluate((panel) => (
      panel.scrollHeight <= panel.clientHeight + 1
    ))).toBe(true);

    await page.getByTestId('client-autocomplete-option-5').click();
    await expect(catalog).toBeVisible();
    const scope = page.getByTestId('client-bulk-summary-list');
    expect(await scope.evaluate((element) => ({
      hasEveryRecord: [
        'Kore - Inicio 40%',
        'Kore - Entrega 30%',
        'Kore - Integración 20%',
        'Kore - Cierre 10%',
      ].every((label) => element.textContent.includes(label)),
      fitsWithoutScroll: element.scrollHeight <= element.clientHeight + 1,
    }))).toEqual({ hasEveryRecord: true, fitsWithoutScroll: true });
    expect(calls.some(
      (call) => call.apiPath === 'accounting/incomes/bulk-assign-client/',
    )).toBe(false);
  });

  test('the client catalog fills the compact assignment modal', {
    tag: [
      ...ADMIN_ACCOUNTING_INCOME_CLIENT,
      '@role:admin',
      '@outcome:display',
      '@responsive:accounting',
    ],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
        incomeRow({ id: 3, concept: 'Kore - Integración 20%' }),
        incomeRow({ id: 4, concept: 'Kore - Cierre 10%' }),
      ],
      calls: [],
    }));
    // quality: allow-deep-link (the compact viewport isolates full-screen modal geometry; panel navigation is covered by the desktop catalog flow)
    await gotoIncomes(page);
    await openBulkClientAssignment(page);

    const modal = page.getByTestId('incomes-bulk-assign-modal');
    const panel = modal.locator('..');
    const panelBounds = await panel.boundingBox();
    expect(panelBounds).toMatchObject({ x: 0, y: 0, width: 412, height: 915 });

    const scroller = page.getByTestId('client-catalog-scroll');
    await scroller.hover();
    await page.mouse.wheel(0, 600);
    await expect.poll(() => scroller.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(0);
    expect(await panel.evaluate((element) => (
      element.scrollHeight <= element.clientHeight + 1
    ))).toBe(true);

    await page.getByTestId('client-autocomplete-option-5').click();
    await expect(page.getByTestId('client-bulk-summary-list')).toContainText('Kore - Cierre 10%');
    expect(await panel.evaluate((element) => (
      element.scrollHeight <= element.clientHeight + 1
    ))).toBe(true);
  });

  test('the client name order persists between assignment modal openings', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
        incomeRow({ id: 3, concept: 'Kore - Integración 20%' }),
        incomeRow({ id: 4, concept: 'Kore - Cierre 10%' }),
      ],
      calls: [],
    }));
    await navigateToIncomesFromPanel(page);
    await openBulkClientAssignment(page);

    const firstOption = page.locator('[data-testid^="client-autocomplete-option-"]').first();
    await expect(firstOption).toContainText('Ana Pérez');
    await page.getByTestId('client-catalog-sort-name').click();
    await expect(firstOption).toContainText('Fernanda Suárez');
    await page.getByTestId('incomes-bulk-assign-cancel').click();

    await bulkAction(page, 'incomes', 'Asignar cliente');

    await expect(firstOption).toContainText('Fernanda Suárez');
  });

  test('assigning a client in bulk updates every selected row', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
        incomeRow({ id: 3, concept: 'Kore - Integración 20%' }),
        incomeRow({ id: 4, concept: 'Kore - Cierre 10%' }),
      ],
      calls,
    }));
    await gotoIncomes(page);
    await openBulkClientAssignment(page);
    await page.getByTestId('incomes-bulk-client').fill('Ana');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('incomes-bulk-assign').click();

    await expect(page.getByTestId('accounting-row-1')).toContainText('Ana Pérez');
    await expect(page.getByTestId('accounting-row-2')).toContainText('Ana Pérez');
    await expect(page.getByTestId('accounting-row-3')).toContainText('Ana Pérez');
    await expect(page.getByTestId('accounting-row-4')).toContainText('Ana Pérez');
    await expect(page.getByTestId('incomes-bulk-bar')).toHaveCount(0);
    const bulk = calls.find(
      (call) => call.apiPath === 'accounting/incomes/bulk-assign-client/',
    );
    expect(bulk.body).toEqual({ income_ids: [1, 2, 3, 4], client: 5 });
  });

  test('assigning stays blocked, with the reason on screen, until a client is picked', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [incomeRow({ id: 1, concept: 'Kore - Inicio 40%' })],
      calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-1').check();

    // Nothing selected has a client, so the menu does not offer to unlink one
    // — and the menu has to be OPEN for that absence to mean anything.
    await openBulkMenu(page, 'incomes');
    await expect(bulkMenuItem(page, 'Desvincular cliente')).toHaveCount(0);
    await bulkMenuItem(page, 'Asignar cliente').click();

    // An empty picker no longer means "unlink": the action is simply off.
    await expect(page.getByTestId('incomes-bulk-assign')).toBeDisabled();
    await expect(page.getByTestId('incomes-bulk-hint')).toContainText(
      'Elige un cliente para poder asignar',
    );
  });

  test('unlinking is its own action and names the client the rows are leaving', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%', client: 5, client_name: 'Ana Pérez' }),
        incomeRow({ id: 2, concept: 'Reembolso banco' }),
      ],
      calls,
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-1').check();
    await page.getByTestId('accounting-select-2').check();
    await bulkAction(page, 'incomes', 'Desvincular cliente');

    await expect(page.getByRole('dialog')).toContainText(
      '1 ingreso quedará sin cliente: 1 de Ana Pérez.',
    );
    // Solo la fila enlazada entra en el alcance; la suelta no aparece.
    await expect(page.getByTestId('client-bulk-summary-list')).toContainText('Kore - Inicio 40%');
    await expect(page.getByTestId('client-bulk-summary-list')).not.toContainText('Reembolso banco');

    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('incomes-bulk-bar')).toHaveCount(0);
    const bulk = calls.find(
      (call) => call.apiPath === 'accounting/incomes/bulk-assign-client/',
    );
    // Only the linked row travels — the unassigned one had nothing to lose.
    expect(bulk.body).toEqual({ income_ids: [1], client: null });
  });

  test('the totals modal breaks the filtered incomes down by client', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the flow under
    // test starts at the Totales por cliente button, which IS clicked)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({
          id: 1, client: 5, client_name: 'Ana Pérez',
          total_amount: '1000000.00', pending_amount: '1000000.00',
        }),
        incomeRow({ id: 2, concept: 'Reembolso banco', total_amount: '500000.00', pending_amount: '500000.00' }),
      ],
      calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('incomes-client-totals-button').click();

    await expect(page.getByTestId('income-client-row-5')).toContainText('Ana Pérez');
    await expect(page.getByTestId('income-client-row-none')).toContainText('Sin cliente');
    await expect(page.getByTestId('income-client-billed-sum')).toContainText('1.500.000');
  });

  test('deleting one of the selected incomes drops it from the bar and keeps the rest', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%', total_amount: '1000000.00' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%', total_amount: '1000000.00' }),
        incomeRow({ id: 3, concept: 'Kore - Cierre 30%', total_amount: '1000000.00' }),
      ],
      calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-1').check();
    await page.getByTestId('accounting-select-2').check();
    await page.getByTestId('accounting-select-3').check();
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('3 seleccionados');

    await page.getByTestId('income-actions-2').click();
    await page.getByTestId('income-action-delete-2').click();
    await page.getByTestId('confirm-modal-confirm').click();

    // The deleted id leaves the selection on its own — only that one.
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('2 seleccionados');
    await expect(page.getByTestId('accounting-row-2')).toHaveCount(0);
    // And it must not come back disguised as a filtered-out row.
    await expect(page.getByTestId('incomes-bulk-outside')).toHaveCount(0);
    // Header totals recompute with no reload: 3.000.000 minus the deleted row.
    await expect(page.getByTestId('incomes-total-expected')).toContainText('2.000.000');
  });

  test('the bar leaves when the only selected income is deleted', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
      ],
      calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-1').check();
    await expect(page.getByTestId('incomes-bulk-bar')).toBeVisible();

    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-delete-1').click();
    await page.getByTestId('confirm-modal-confirm').click();

    // No reload, no Cancelar: with nothing left to assign, the bar goes.
    await expect(page.getByTestId('incomes-bulk-bar')).toHaveCount(0);
  });

  test('a mass selection shrinks with the dataset instead of counting ghosts', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
        incomeRow({ id: 3, concept: 'Kore - Cierre 30%' }),
      ],
      calls: [],
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-1').check();
    await page.getByTestId('incomes-select-all-filtered').click();
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('3 seleccionados');

    await page.getByTestId('income-actions-3').click();
    await page.getByTestId('income-action-delete-3').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('2 seleccionados');
    // The two survivors are still the whole filtered set, so the offer to
    // select them all stays away.
    await expect(page.getByTestId('incomes-select-all-filtered')).toHaveCount(0);
  });

  test('a bulk assign over a record deleted elsewhere reports it and reconciles', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // The window the frontend cannot close on its own: the confirmation
    // freezes the plan when it opens, and another session can delete a row
    // while it is up. The server refuses the batch and names what vanished.
    const listFetches = { count: 0 };
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
      ],
      calls: [],
      listFetches,
      bulkAssignMissingIds: [2],
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-1').check();
    await page.getByTestId('accounting-select-2').check();
    await bulkAction(page, 'incomes', 'Asignar cliente');
    await page.getByTestId('incomes-bulk-client').fill('Ana');
    await page.getByTestId('client-autocomplete-option-5').click();
    const fetchesBefore = listFetches.count;
    await page.getByTestId('incomes-bulk-assign').click();

    await expect(page.getByText('1 de los ingresos seleccionados ya no existe.'))
      .toBeVisible();
    // Nothing was written, and the vanished id left the selection.
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('1 seleccionado');
    expect(listFetches.count).toBeGreaterThan(fetchesBefore);
  });
});

test.describe('Admin Accounting Incomes — vista agrupada por cliente', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('lands grouped when the backend setting says so', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (the contract under test is the LANDING
    // state itself — what renders before any interaction; the toggle path is
    // exercised by the session-only test right below)
    // quality: allow-deep-link (the tab is a subnav entry; what is under
    // test is the landing mode the backend setting dictates)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, client: 5, client_name: 'Ana Pérez' }),
        incomeRow({
          id: 2, concept: 'Reembolso banco',
          total_amount: '500000.00', pending_amount: '500000.00',
        }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    // The setting, not a device preference, decides the landing mode.
    await expect(
      page.getByTestId('incomes-view-mode').getByRole('tab', { name: 'Agrupado' }),
    ).toHaveAttribute('aria-selected', 'true');

    await expect(page.getByTestId('income-group-5')).toContainText('Ana Pérez');
    await expect(page.getByTestId('income-group-billed-5')).toContainText('1.160.000');
    // Every figure is its own labelled block, grouped next to the client name,
    // so the header reads as facts about that client and not as stray columns.
    await expect(page.getByTestId('income-group-pending-5')).toContainText('1.160.000');
    await expect(page.getByTestId('income-group-5')).toContainText('Facturado');
    await expect(page.getByTestId('income-group-5')).toContainText('Pendiente');
    // The share declares what it is: this group's part of the billed total.
    await expect(page.getByTestId('income-group-5')).toContainText('Participación en lo facturado');
    // The unassigned bucket closes the list, flagged as completion work.
    await expect(page.getByTestId('income-group-none')).toContainText('por completar');
    await expect(page.getByTestId('income-grouped-billed-total')).toContainText('1.660.000');
    const leadingHeaders = await page.getByTestId('accounting-actions-header')
      .evaluate((header) => Array.from(header.parentElement.children).slice(0, 3).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        text: cell.textContent.trim(),
        hasCheckbox: Boolean(cell.querySelector('input[type="checkbox"]')),
      })));
    expect(leadingHeaders).toEqual([
      { testId: null, text: '', hasCheckbox: true },
      { testId: 'accounting-actions-header', text: '', hasCheckbox: false },
      { testId: null, text: 'Concepto', hasCheckbox: false },
    ]);
    // The rows keep their actions inside the group.
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await page.getByTestId('income-actions-1').click();
    await expect(page.getByTestId('income-action-liquidate-1')).toBeVisible();
    await page.keyboard.press('Escape');
  });

  test('opens with the newest income month first', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (the default sort before any action is
    // the behavior under test; the interactive cycle is covered below)
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({
          id: 1, period: '2026-01', period_label: 'Enero 2026', period_date: '2026-01-01',
          client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 2, period: '2026-03', period_label: 'Marzo 2026', period_date: '2026-03-01',
          client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 3, period: '2026-02', period_label: 'Febrero 2026', period_date: '2026-02-01',
          client: 5, client_name: 'Ana Pérez',
        }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));

    await gotoIncomes(page);

    await expect(page.getByTestId('accounting-sort-period_label')).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Mes' }))
      .toHaveAttribute('aria-sort', 'descending');
    expect(await visibleIncomeIds(page)).toEqual([2, 3, 1]);
  });

  test('toggles Month between oldest and newest', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({
          id: 1, period: '2026-01', period_label: 'Enero 2026', period_date: '2026-01-01',
          client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 2, period: '2026-03', period_label: 'Marzo 2026', period_date: '2026-03-01',
          client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 3, period: '2026-02', period_label: 'Febrero 2026', period_date: '2026-02-01',
          client: 5, client_name: 'Ana Pérez',
        }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    const monthSort = page.getByTestId('accounting-sort-period_label');
    await monthSort.click();
    await expect(page.getByRole('columnheader', { name: 'Mes' }))
      .toHaveAttribute('aria-sort', 'ascending');
    expect(await visibleIncomeIds(page)).toEqual([1, 3, 2]);

    await monthSort.click();
    await expect(page.getByRole('columnheader', { name: 'Mes' }))
      .toHaveAttribute('aria-sort', 'descending');
    expect(await visibleIncomeIds(page)).toEqual([2, 3, 1]);
  });

  test('cycles Total back to the default month order', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({
          id: 1, period_date: '2026-01-01', total_amount: '300.00',
          client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 2, period_date: '2026-03-01', total_amount: '100.00',
          client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 3, period_date: '2026-02-01', total_amount: '200.00',
          client: 5, client_name: 'Ana Pérez',
        }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    const totalSort = page.getByTestId('accounting-sort-total_amount');
    await totalSort.click();
    await expect(page.getByRole('columnheader', { name: 'Total' }))
      .toHaveAttribute('aria-sort', 'descending');
    expect(await visibleIncomeIds(page)).toEqual([1, 3, 2]);

    await totalSort.click();
    await expect(page.getByRole('columnheader', { name: 'Total' }))
      .toHaveAttribute('aria-sort', 'ascending');
    expect(await visibleIncomeIds(page)).toEqual([2, 3, 1]);

    await totalSort.click();
    await expect(page.getByRole('columnheader', { name: 'Mes' }))
      .toHaveAttribute('aria-sort', 'descending');
    expect(await visibleIncomeIds(page)).toEqual([2, 3, 1]);
  });

  test('sorts rows inside each client without changing group order', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, total_amount: '300.00', client: 5, client_name: 'Ana Pérez' }),
        incomeRow({ id: 2, total_amount: '100.00', client: 5, client_name: 'Ana Pérez' }),
        incomeRow({ id: 3, total_amount: '700.00', client: null, client_name: null }),
        incomeRow({ id: 4, total_amount: '500.00', client: 6, client_name: 'Beta SAS' }),
        incomeRow({ id: 5, total_amount: '900.00', client: 6, client_name: 'Beta SAS' }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-sort-total_amount').click();

    const groupOrder = await page
      .getByTestId(/^income-group-(?:5|6|none)$/)
      .evaluateAll((groups) => groups.map((group) => group.getAttribute('data-testid')));
    expect(groupOrder).toEqual(['income-group-6', 'income-group-5', 'income-group-none']);
    expect(await visibleIncomeIds(page.getByTestId('income-group-body-6'))).toEqual([5, 4]);
    expect(await visibleIncomeIds(page.getByTestId('income-group-body-5'))).toEqual([1, 2]);
    expect(await visibleIncomeIds(page.getByTestId('income-group-body-none'))).toEqual([3]);
  });

  test('persists the selected order across income view changes', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({
          id: 1, kind: 'liquid', kind_label: 'Líquido', payment_status: null,
          payment_status_label: null, total_amount: '300.00',
          client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 2, total_amount: '100.00', client: 5, client_name: 'Ana Pérez',
        }),
        incomeRow({
          id: 3, total_amount: '200.00', client: 5, client_name: 'Ana Pérez',
        }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-sort-total_amount').click();
    await page.getByTestId('accounting-sort-total_amount').click();
    expect(await visibleIncomeIds(page)).toEqual([2, 3, 1]);

    await page.getByTestId('filter-tabs-tab-expected-pending').click();
    expect(await visibleIncomeIds(page)).toEqual([2, 3]);

    await page.getByTestId('incomes-view-mode')
      .getByRole('tab', { name: 'Clásico' }).click();
    await expect(page.getByRole('columnheader', { name: 'Total' }))
      .toHaveAttribute('aria-sort', 'ascending');
    expect(await visibleIncomeIds(page)).toEqual([2, 3]);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Ingresos', exact: true }))
      .toBeVisible({ timeout: 40_000 });
    await expect(page.getByRole('columnheader', { name: 'Total' }))
      .toHaveAttribute('aria-sort', 'ascending');
    expect(await visibleIncomeIds(page)).toEqual([2, 3]);
  });

  test('the grouped income menu stays reachable on a compact viewport', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({
      rows: [incomeRow({ id: 1, client: 5, client_name: 'Ana Pérez' })],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    const row = page.getByTestId('accounting-row-1');
    const grid = row.locator('xpath=ancestor::div[contains(@class, "accounting-grid-scroll")]');
    const action = page.getByTestId('income-actions-1');
    const kind = page.getByTestId('income-kind-1').filter({ visible: true });

    expect(await grid.evaluate((element) => element.scrollWidth <= element.clientWidth))
      .toBe(true);
    await expect(page.getByTestId('accounting-actions-header')).toBeVisible();
    await expect(kind).toHaveCSS('white-space', 'nowrap');
    await action.click();
    await expect(page.getByTestId('income-actions-modal')).toBeVisible();
  });

  test('the in-page toggle is session-only: classic appears, nothing persists', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const settingsWrites = [];
    page.on('request', (request) => {
      if (request.url().includes('accounting/settings') && request.method() !== 'GET') {
        settingsWrites.push(request.method());
      }
    });
    await mockApi(page, buildHandler({
      rows: [incomeRow({ id: 1, client: 5, client_name: 'Ana Pérez' })],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);
    await expect(page.getByTestId('income-group-5')).toBeVisible();

    await page.getByTestId('incomes-view-mode')
      .getByRole('tab', { name: 'Clásico' }).click();

    // The classic table takes over: the groups disappear and Cliente returns
    // as a sortable column (the grouped header already names the client).
    await expect(page.getByTestId('income-group-5')).toHaveCount(0);
    await expect(page.getByTestId('accounting-sort-client_name')).toBeVisible();
    // …and the switch wrote nothing: the landing mode belongs to the setting.
    expect(settingsWrites).toEqual([]);
  });

  test('assigns a client in bulk from the grouped view, group checkbox and all', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, client: 5, client_name: 'Ana Pérez' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
        incomeRow({ id: 3, concept: 'Kore - Cierre 30%' }),
      ],
      calls,
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    // One click on the bucket that names the pending work takes its two rows.
    await page.getByTestId('income-group-select-none').check();
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('2 seleccionados');
    await expect(page.getByTestId('accounting-select-2')).toBeChecked();
    await expect(page.getByTestId('accounting-select-3')).toBeChecked();
    // The row that already has a client is in another group and stays out.
    await expect(page.getByTestId('accounting-select-1')).not.toBeChecked();

    await bulkAction(page, 'incomes', 'Asignar cliente');
    await page.getByTestId('incomes-bulk-client').fill('Ana');
    await page.getByTestId('client-autocomplete-option-5').click();
    await expect(page.getByTestId('incomes-bulk-hint')).toContainText(
      'Cliente enlazado: Ana Pérez',
    );
    await page.getByTestId('incomes-bulk-assign').click();

    // The completion path closes: the bucket the grouping exposed is empty.
    await expect(page.getByTestId('income-group-none')).toHaveCount(0);
    await expect(page.getByTestId('income-group-5')).toContainText('(3)');
    const bulk = calls.find(
      (call) => call.apiPath === 'accounting/incomes/bulk-assign-client/',
    );
    expect(bulk.body).toEqual({ income_ids: [2, 3], client: 5 });
  });

  test('a partly selected group reads indeterminate and says so once collapsed', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; what is under test
    // is the tri-state the grouping shows once rows are ticked, and the test
    // does drive it — the landing path has its own spec above)
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, client: 5, client_name: 'Ana Pérez' }),
        incomeRow({
          id: 2, client: 5, client_name: 'Ana Pérez', concept: 'Kore - Entrega 30%',
        }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-1').check();

    await expect(page.getByTestId('income-group-select-5'))
      .toBeChecked({ indeterminate: true });
    await expect(page.getByTestId('accounting-select-all'))
      .toBeChecked({ indeterminate: true });

    // Collapsing hides the ticked row, so the header has to own up to it.
    await page.getByTestId('income-group-toggle-5').click();

    await expect(page.getByTestId('income-group-selected-5'))
      .toHaveText('1 seleccionado');
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('1 seleccionado');
  });

  test('the selection survives switching from grouped to classic', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, concept: 'Kore - Inicio 40%' }),
        incomeRow({ id: 2, concept: 'Kore - Entrega 30%' }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-group-select-none').check();
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('2 seleccionados');

    await page.getByTestId('incomes-view-mode')
      .getByRole('tab', { name: 'Clásico' }).click();

    // Same ids, other table: changing view must not cost the work done.
    await expect(page.getByTestId('accounting-sort-client_name')).toBeVisible();
    await expect(page.getByTestId('accounting-select-1')).toBeChecked();
    await expect(page.getByTestId('accounting-select-2')).toBeChecked();
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('2 seleccionados');
  });

  test('deleting a grouped income leaves its group and the bar count with it', {
    tag: [...ADMIN_ACCOUNTING_INCOME_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // The group badge already shed a deleted row while the bar went on
    // counting it — two counters, one truth. Both are asserted here so a
    // regression cannot fix one and leave the other.
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 1, client: 5, client_name: 'Ana Pérez' }),
        incomeRow({
          id: 2, client: 5, client_name: 'Ana Pérez', concept: 'Kore - Entrega 30%',
        }),
        incomeRow({
          id: 3, client: 5, client_name: 'Ana Pérez', concept: 'Kore - Cierre 30%',
        }),
      ],
      calls: [],
      incomeViewMode: 'grouped',
    }));
    await gotoIncomes(page);

    await page.getByTestId('income-group-select-5').check();
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('3 seleccionados');

    await page.getByTestId('income-actions-2').click();
    await page.getByTestId('income-action-delete-2').click();
    await page.getByTestId('confirm-modal-confirm').click();

    // The row leaves its group, the group recounts, and the bar agrees.
    await expect(page.getByTestId('accounting-row-2')).toHaveCount(0);
    await expect(page.getByTestId('income-group-5')).toContainText('(2)');
    await expect(page.getByTestId('incomes-bulk-bar')).toContainText('2 seleccionados');

    await page.getByTestId('income-group-toggle-5').click();

    await expect(page.getByTestId('income-group-selected-5'))
      .toHaveText('2 seleccionados');
  });
});
