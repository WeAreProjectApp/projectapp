/**
 * E2E tests for the Cuentas de cobro center at /panel/accounting/collections.
 *
 * FLOWS: admin-accounting-collections, admin-accounting-collection-create
 * Covers: status counters from list meta, the segmented Vencidas filter with
 *         the is_overdue badge, mark-paid and cancel behind ConfirmModal,
 *         resend to the client, the create modal with its mandatory income
 *         link and email/PDF preview step, and the Liquidar routing when
 *         marking an expected-linked cuenta as paid, grouped totals by client
 *         or project, and server-persisted view preferences.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';
import {
  ADMIN_ACCOUNTING_COLLECTIONS,
  ADMIN_ACCOUNTING_COLLECTION_GROUPING,
  ADMIN_ACCOUNTING_COLLECTION_CREATE,
  ADMIN_ACCOUNTING_COLLECTION_DETAIL,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

function makeRows() {
  return [
    {
      id: 1,
      public_number: 'PA-2026-0001',
      origin: 'hosting',
      origin_label: 'Hosting',
      // The snapshot the PDF printed: person and brand fused, which is the
      // defect the two columns below exist to separate.
      customer_name: 'German - Kore',
      client: 101,
      client_display_name: 'Germán Franco',
      project_name: 'Kore',
      total: '550002.00',
      issue_date: '2026-06-01',
      due_date: '2026-06-15',
      commercial_status: 'issued',
      commercial_status_label: 'Emitida',
      is_overdue: true,
      // The backend resolves the delete rule: these three left for the client,
      // so none of them can be removed until they are annulled.
      can_delete: false,
      // Internal: written in the create form, never sent to the client.
      notes: 'Acordado por WhatsApp\nPagan el 15, no antes.',
    },
    {
      id: 2,
      public_number: 'PA-2026-0002',
      origin: 'hosting',
      origin_label: 'Hosting',
      // The snapshot the PDF printed: person and brand fused, which is the
      // defect the two columns below exist to separate.
      customer_name: 'Nestor - Xpandia',
      client: 102,
      client_display_name: 'Néstor Franco',
      project_name: 'Xpandia',
      total: '550002.00',
      issue_date: '2026-07-10',
      due_date: '2026-07-30',
      commercial_status: 'issued',
      commercial_status_label: 'Emitida',
      is_overdue: false,
      can_delete: false,
    },
    {
      id: 3,
      public_number: 'PA-2026-0003',
      origin: 'hosting',
      origin_label: 'Hosting',
      // The snapshot the PDF printed: person and brand fused, which is the
      // defect the two columns below exist to separate.
      customer_name: 'Laura - Mi Huella',
      client: 103,
      client_display_name: 'Laura Gómez',
      project_name: 'Mi Huella',
      total: '550002.00',
      issue_date: '2026-05-01',
      due_date: '2026-05-15',
      commercial_status: 'paid',
      commercial_status_label: 'Pagada',
      is_overdue: false,
      can_delete: false,
    },
  ];
}

function makeGroupingRows() {
  const base = makeRows()[0];
  return [
    {
      ...base,
      id: 11,
      client: 101,
      client_display_name: 'Germán Franco',
      project_id: 10,
      project_name: 'Kore',
      total: '600.00',
      commercial_status: 'issued',
      is_overdue: true,
    },
    {
      ...base,
      id: 12,
      client: 101,
      client_display_name: 'Germán Franco',
      project_id: 11,
      project_name: 'Xpandia',
      total: '400.00',
      commercial_status: 'issued',
      is_overdue: false,
    },
    {
      ...base,
      id: 13,
      client: 101,
      client_display_name: 'Germán Franco',
      project_id: 10,
      project_name: 'Kore',
      total: '300.00',
      commercial_status: 'paid',
      commercial_status_label: 'Pagada',
      is_overdue: false,
    },
    {
      ...base,
      id: 14,
      client: 102,
      client_display_name: 'Néstor Franco',
      project_id: null,
      project_name: 'Proyecto legado',
      total: '900.00',
      commercial_status: 'draft',
      commercial_status_label: 'Borrador',
      is_overdue: false,
    },
    {
      ...base,
      id: 15,
      client: 102,
      client_display_name: 'Néstor Franco',
      project_id: null,
      project_name: '',
      total: '200.00',
      commercial_status: 'cancelled',
      commercial_status_label: 'Anulada',
      is_overdue: false,
    },
    {
      ...base,
      id: 16,
      client: null,
      client_display_name: null,
      customer_name: 'Cliente del documento',
      project_id: null,
      project_name: '',
      total: '1000.00',
      commercial_status: 'issued',
      is_overdue: false,
    },
  ];
}

/**
 * The list endpoint's meta, derived from the rows the way the backend derives
 * it. Computed rather than frozen so the counters keep telling the truth after
 * a row is deleted — a constant would have hidden exactly that.
 */
function computeMeta(rows) {
  const sum = (status) => rows
    .filter((row) => row.commercial_status === status)
    .reduce((acc, row) => acc + Number(row.total), 0)
    .toFixed(2);
  const count = (status) => rows
    .filter((row) => row.commercial_status === status).length;
  return {
    issued_count: count('issued'),
    issued_total: sum('issued'),
    paid_count: count('paid'),
    paid_total: sum('paid'),
    cancelled_count: count('cancelled'),
  };
}

const META = computeMeta(makeRows());

const CLIENT_WITHOUT_EMAIL = {
  id: 6,
  name: 'Bruno Díaz',
  email: 'client-6@placeholder.projectapp.local',
  phone: '',
  company: 'Brújula SAS',
  nit: '900555444',
  cedula: '',
  is_email_placeholder: true,
};

const CLIENT_SEARCH_RESULT = [{
  id: 5,
  name: 'Ana Pérez',
  email: 'ana@acme.co',
  phone: '',
  company: 'Acme Soluciones',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
}, CLIENT_WITHOUT_EMAIL];

const ELIGIBLE_INCOME = {
  id: 8,
  client: null,
  client_name: null,
  concept: 'Desarrollo módulo de reportes',
  kind: 'expected',
  kind_label: 'Esperado',
  payment_status: 'pending',
  total_amount: '1490000.00',
  pending_amount: '1490000.00',
  has_collection_account: false,
  collection_account_id: null,
  collection_account_number: null,
};

/** Rows where #2 carries an income link, so the detail modal has a history.
 *  Overridden locally rather than in makeRows(): the plain mark-paid test
 *  depends on the base rows NOT routing through Liquidar. */
async function mockWithLinkedIncome(page, calls = []) {
  const handler = buildHandler({ calls });
  await mockApi(page, async (ctx) => {
    if (ctx.apiPath === 'accounting/collection-accounts/' && ctx.method === 'GET') {
      const rows = makeRows();
      rows[1].income_record_id = 8;
      rows[1].income_kind = 'expected';
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: rows, meta: META }),
      };
    }
    return handler(ctx);
  });
}

/** Already assigned to Acme (client 5): the "De {cliente}" group. It also
 *  carries Acme's project, so the create flow can pin that the cuenta
 *  inherits it (F7). */
const OWN_INCOME = {
  ...ELIGIBLE_INCOME,
  id: 21,
  client: 5,
  client_name: 'Acme Soluciones',
  concept: 'Acme - Soporte trimestral',
  kind: 'liquid',
  kind_label: 'Líquido',
  payment_status: null,
  project: 7,
  project_name: 'Vastago',
};

/** Someone else's money: reachable only from the "Todos" alcance. */
const OTHER_CLIENT_INCOME = {
  ...ELIGIBLE_INCOME,
  id: 22,
  client: 7,
  client_name: 'Torrios SAS',
  concept: 'Torrios - Hosting anual',
};

const INCOME_POOL = [ELIGIBLE_INCOME, OWN_INCOME, OTHER_CLIENT_INCOME];

/**
 * The concept search the backend applies. The client scoping is no longer a
 * query param — the modal asks for the whole eligible set and narrows it on
 * the page — so `q` is all that reaches the endpoint.
 */
function filterIncomes(requestUrl) {
  const search = (new URL(requestUrl).searchParams.get('q') || '').toLowerCase();
  if (!search) return INCOME_POOL;
  return INCOME_POOL.filter(
    (row) => row.concept.toLowerCase().includes(search),
  );
}

const PREVIEW_PDF_URL =
  '/api/accounting/collection-accounts/preview/tok-e2e/PA-ACME-001.pdf';

function buildHandler({
  calls,
  incomeDetail = null,
  previewPdfStatus = 200,
  rows = null,
  collectionViewMode = 'classic',
  collectionGroupBy = 'client',
  settingsPatchStatus = 200,
}) {
  const state = {
    rows: rows || makeRows(),
    settings: {
      collection_accounts_view_mode: collectionViewMode,
      collection_accounts_group_by: collectionGroupBy,
    },
  };
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
        body: JSON.stringify(state.settings),
      };
    }
    if (apiPath === 'accounting/settings/update/' && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (settingsPatchStatus !== 200) {
        return {
          status: settingsPatchStatus,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'No fue posible guardar la preferencia.' }),
        };
      }
      state.settings = { ...state.settings, ...body };
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state.settings),
      };
    }
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(CLIENT_SEARCH_RESULT),
      };
    }
    if (apiPath === 'proposals/client-profiles/6/update/' && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...CLIENT_WITHOUT_EMAIL,
          email: body.email,
          is_email_placeholder: false,
        }),
      };
    }
    if (apiPath === 'proposals/client-profiles/7/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 7,
          name: 'Luis Torres',
          company: 'Torrios SAS',
          email: 'luis@torrios.co',
          nit: '900111222',
          cedula: '',
          is_email_placeholder: false,
        }),
      };
    }
    if (/^accounting\/collection-accounts\/\d+\/$/.test(apiPath) && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          items: [{
            id: 1,
            description: 'Servicio de hosting kore.com.co',
            period_start: '2026-06-01',
            period_end: '2026-08-31',
            line_total: '550002.00',
          }],
          payment_methods: [],
          notes: '',
        }),
      };
    }
    // Must precede the incomes catch-all below, which would otherwise answer
    // /detail/ with the LIST shape.
    if (/^accounting\/incomes\/\d+\/detail\/$/.test(apiPath) && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          income: {
            ...ELIGIBLE_INCOME,
            concept: 'Hosting: Trimestral',
            period_label: 'Agosto 2026',
            gustavo_amount: '116640.00',
            carlos_amount: '116640.00',
            company_amount: '0.00',
          },
          liquid: [{
            id: 51, concept: 'Abono 1',
            total_amount: '88000.00', period_date: '2026-08-05',
          }],
          expenses: [{
            id: 61, concept: 'Comisión pasarela',
            total_amount: '12000.00', period_date: '2026-08-06',
            deduction_type_label: 'Comisión de pasarela',
          }],
          collection_account: null,
        }),
      };
    }
    if (/^accounting\/incomes\/\d+\/$/.test(apiPath) && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(incomeDetail || ELIGIBLE_INCOME),
      };
    }
    if (apiPath.startsWith('accounting/incomes/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: filterIncomes(route.request().url()),
          meta: {},
        }),
      };
    }
    if (apiPath.startsWith('accounting/collection-accounts/next-number/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          suggested_number: 'PA-ACME-001',
          billing_code: 'ACME',
          issuer_city: 'Bogotá',
        }),
      };
    }
    if (apiPath === 'accounting/collection-accounts/preview/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          subject: 'Cuenta de cobro PA-ACME-001 — ProjectApp',
          html_body: '<p>Valor a pagar: $1\'490.000 COP</p>',
          public_number: 'PA-ACME-001',
          total: '1490000.00',
          due_date: '2026-08-13',
          customer_email: body.customer.email,
          pdf_url: PREVIEW_PDF_URL,
        }),
      };
    }
    // The preview PDF is served, not built from base64 in the browser: a
    // blob: URL has no name and Chrome's viewer fell back to the blob UUID.
    if (apiPath === PREVIEW_PDF_URL.replace(/^\/api\//, '') && method === 'GET') {
      if (previewPdfStatus !== 200) {
        return {
          status: previewPdfStatus,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'La previsualización expiró.' }),
        };
      }
      return {
        status: 200,
        contentType: 'application/pdf',
        headers: { 'Content-Disposition': 'inline; filename="PA-ACME-001.pdf"' },
        body: '%PDF-1.4\n%%EOF\n',
      };
    }
    if (apiPath === 'accounting/collection-accounts/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      // The cuenta inherits the income's project and the column reads the
      // live FK (F7) — the response mirrors what the backend answers.
      const fromOwnIncome = body.income_record_id === OWN_INCOME.id;
      const created = {
        id: 9,
        public_number: 'PA-ACME-001',
        origin: 'income',
        origin_label: 'Ingreso',
        customer_name: 'Acme Soluciones',
        client: 110,
        client_display_name: 'Ana Pérez',
        project_id: fromOwnIncome ? OWN_INCOME.project : null,
        project_name: fromOwnIncome ? OWN_INCOME.project_name : '',
        total: '1490000.00',
        issue_date: '2026-08-05',
        due_date: '2026-08-13',
        commercial_status: 'issued',
        commercial_status_label: 'Emitida',
        is_overdue: false,
        income_record_id: body.income_record_id,
        income_kind: fromOwnIncome ? 'liquid' : 'expected',
      };
      state.rows = [created, ...state.rows];
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ document: created, email_sent: true }),
      };
    }
    if (apiPath.startsWith('accounting/collection-accounts/') && method === 'POST') {
      const match = apiPath.match(
        /^accounting\/collection-accounts\/(\d+)\/(mark-paid|cancel|resend)\/$/,
      );
      if (match) {
        const [, id, action] = match;
        calls.push({ apiPath, method });
        const row = state.rows.find((item) => item.id === Number(id));
        if (action === 'mark-paid') {
          Object.assign(row, {
            commercial_status: 'paid',
            commercial_status_label: 'Pagada',
            is_overdue: false,
          });
        }
        if (action === 'cancel') {
          Object.assign(row, {
            commercial_status: 'cancelled',
            commercial_status_label: 'Anulada',
            is_overdue: false,
            // Anular is what opens the door to eliminar: the client has been
            // told it stopped counting, so the row can now be removed.
            can_delete: true,
          });
        }
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(row),
        };
      }
    }
    if (apiPath.startsWith('accounting/collection-accounts/') && method === 'DELETE') {
      const match = apiPath.match(
        /^accounting\/collection-accounts\/(\d+)\/delete\/$/,
      );
      if (match) {
        calls.push({ apiPath, method });
        state.rows = state.rows.filter(
          (item) => item.id !== Number(match[1]),
        );
        return { status: 204, contentType: 'application/json', body: '' };
      }
    }
    if (apiPath.startsWith('accounting/collection-accounts/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: state.rows,
          meta: computeMeta(state.rows),
        }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

async function gotoCollections(page, expectedRowId = 1) {
  await page.goto('/panel/accounting/collections', { waitUntil: 'domcontentloaded' });
  await expect(
    page.getByRole('heading', { name: 'Cuentas de cobro', exact: true }),
  ).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId(`accounting-row-${expectedRowId}`)).toBeVisible();
}

async function expectDescribedError(page, testId, message) {
  const control = page.getByTestId(testId);
  await expect(control).toHaveAttribute('aria-invalid', 'true');
  const errorId = await control.getAttribute('aria-describedby');
  expect(errorId).toBeTruthy();
  await expect(page.locator(`[id="${errorId}"]`)).toHaveText(message);
}

async function chooseCollectionAction(page, rowId, actionId) {
  await page.getByTestId(`collection-actions-${rowId}`).click();
  const action = page.getByTestId(`collection-${actionId}-${rowId}`);
  await expect(action).toBeVisible();
  await action.click();
}

test.describe('Admin Accounting Collections', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the status counters combine list meta and overdue rows', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    await expect(page.getByTestId('accounting-stat-value')).toHaveText([
      '1', '2', '1', '0',
    ]);
    await expect(page.getByText('Por cobrar: $1.100.004')).toBeVisible();
    await expect(page.getByText('Recaudado: $550.002')).toBeVisible();
  });

  test('the classic collection table fits the compact viewport', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (the arrival geometry is the outcome)
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    const row = page.getByTestId('accounting-row-1');
    const table = row.locator('xpath=ancestor::table');
    const scroller = table.locator('..');
    const action = page.getByTestId('collection-actions-1');
    const status = page.getByTestId('collection-status-1');

    expect(await scroller.evaluate((element) => element.scrollWidth <= element.clientWidth))
      .toBe(true);
    // Fitting is not enough: the visible columns must also reach the edge.
    await expectNoBlankBand(table);
    await expect(page.getByTestId('accounting-actions-header')).toBeVisible();
    await expect(action).toBeVisible();
    await expect(status).toHaveCSS('white-space', 'nowrap');
    expect(await action.evaluate((element) => {
      const button = element.matches('button') ? element : element.querySelector('button');
      const box = button.getBoundingClientRect();
      const rowBox = element.closest('[data-testid^="accounting-row-"]').getBoundingClientRect();
      return box.left >= rowBox.left && box.right <= rowBox.right;
    })).toBe(true);
  });

  test('grouped view shows client amounts and the five status counts', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_GROUPING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (la navegación del módulo pertenece al flujo del subnav; este caso aísla la lectura, colapso y totales agrupados)
    await mockApi(page, buildHandler({
      calls: [],
      rows: makeGroupingRows(),
      collectionViewMode: 'grouped',
    }));
    await gotoCollections(page, 11);

    const clientToggle = page.getByTestId('collection-group-toggle-101');
    await clientToggle.click();
    await expect(clientToggle).toHaveAttribute('aria-expanded', 'false');
    await expect(page.getByTestId('accounting-row-11')).toBeHidden();
    await clientToggle.click();
    await expect(page.getByTestId('accounting-row-11')).toBeVisible();
    await expect(page.getByTestId('collections-view-grouped'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('collection-group-101'))
      .toContainText('Germán Franco');
    await expect(page.getByTestId('collection-group-101')).toContainText('(3)');
    await expect(page.getByTestId('collection-group-emitted-101'))
      .toContainText('$1.300 COP');
    await expect(page.getByTestId('collection-group-pending-101'))
      .toContainText('$1.000 COP');
    await expect(page.getByTestId('collection-group-status-issued-101'))
      .toHaveText('Emitidas2');
    await expect(page.getByTestId('collection-group-status-overdue-101'))
      .toHaveText('Vencidas1');
    await expect(page.getByTestId('collection-group-status-paid-101'))
      .toHaveText('Pagadas1');
    await expect(page.getByTestId('collection-grouped-pending-total'))
      .toContainText('$2.000 COP');
    await expect(page.getByTestId('collection-grouped-cancelled-total'))
      .toContainText('$200 COP');
  });

  test('the grouped collection menu stays reachable on a compact viewport', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_GROUPING, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the accounting subnav is covered elsewhere)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({
      calls: [],
      rows: makeGroupingRows(),
      collectionViewMode: 'grouped',
    }));
    await gotoCollections(page, 11);

    const row = page.getByTestId('accounting-row-11');
    const grid = row.locator('xpath=ancestor::div[contains(@class, "accounting-grid-scroll")]');
    const action = page.getByTestId('collection-actions-11');

    expect(await grid.evaluate((element) => element.scrollWidth <= element.clientWidth))
      .toBe(true);
    await expect(page.getByTestId('accounting-actions-header')).toBeVisible();
    await expect(action).toBeVisible();
    await action.click();
    await expect(page.getByTestId('collection-actions-modal')).toBeVisible();
  });

  test('grouped view switches to ordered project groups with historical separation', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_GROUPING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      rows: makeGroupingRows(),
      collectionViewMode: 'grouped',
    }));
    await gotoCollections(page, 11);

    await page.getByTestId('collections-group-project').click();

    await expect(page.getByTestId('collection-group-historical:Proyecto legado'))
      .toContainText('Proyecto legado (histórico)');
    await expect(page.getByTestId('collection-group-none')).toContainText('Sin proyecto');
    await expect(page.getByTestId('collection-group-none')).toContainText('por completar');
    const headers = page.locator(
      '[role="rowgroup"] > [data-testid^="collection-group-"]:not([data-testid^="collection-group-body-"])',
    );
    await expect(headers).toHaveCount(4);
    expect(await headers.evaluateAll((nodes) => nodes.map((node) => node.dataset.testid)))
      .toEqual([
        'collection-group-10',
        'collection-group-11',
        'collection-group-historical:Proyecto legado',
        'collection-group-none',
      ]);
    const patch = calls.find(
      (call) => call.apiPath === 'accounting/settings/update/',
    );
    expect(patch.body).toEqual({
      collection_accounts_view_mode: 'grouped',
      collection_accounts_group_by: 'project',
    });
  });

  test('grouped view change to classic persists after reload', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_GROUPING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      collectionViewMode: 'grouped',
      collectionGroupBy: 'project',
    }));
    await gotoCollections(page);

    await page.getByTestId('collections-view-classic').click();
    await expect(page.getByTestId('accounting-sort-project_name')).toBeVisible();
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByTestId('collections-view-classic'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('collections-group-by')).toHaveCount(0);
    expect(calls.find((call) => call.apiPath === 'accounting/settings/update/').body)
      .toEqual({
        collection_accounts_view_mode: 'classic',
        collection_accounts_group_by: 'project',
      });
  });

  test('grouped view restores its criterion when persistence fails', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_GROUPING, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      calls: [],
      collectionViewMode: 'grouped',
      settingsPatchStatus: 503,
    }));
    await gotoCollections(page);

    await page.getByTestId('collections-group-project').click();

    await expect(page.getByText('No se pudo guardar la agrupación')).toBeVisible();
    await expect(page.getByTestId('collections-group-client'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('collection-group-101')).toBeVisible();
  });

  test('the Vencidas filter keeps only overdue rows with their badge', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    await page.getByRole('group', { name: 'Estado' })
      .getByRole('button', { name: 'Vencidas', exact: true }).click();

    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByTestId('accounting-row-2')).toHaveCount(0);
    await expect(
      page.getByTestId('accounting-row-1').getByText('Vencida', { exact: true }),
    ).toBeVisible();
  });

  test('a cuenta with no plazo shows no vencimiento and cannot read as vencida', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; what is under test
    // is how a cuenta with no vencimiento renders and filters, reached by
    // clicking the Vencidas tab)
    const handler = buildHandler({ calls: [] });
    await mockApi(page, async (ctx) => {
      if (ctx.apiPath === 'accounting/collection-accounts/' && ctx.method === 'GET') {
        const rows = makeRows();
        // What the backend now returns for a pago-inmediato cuenta: no
        // deadline at all, so there is nothing to fall overdue against.
        rows[0].due_date = null;
        rows[0].is_overdue = false;
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: rows, meta: META }),
        };
      }
      return handler(ctx);
    });
    await gotoCollections(page);

    const row = page.getByTestId('accounting-row-1');
    await expect(row).toBeVisible();
    // The Vence cell is empty rather than repeating the emisión date.
    await expect(row).not.toContainText('2026-06-15');
    await expect(row.getByText('Vencida', { exact: true })).toHaveCount(0);
    await expect(row.getByText('Emitida', { exact: true })).toBeVisible();

    // And the tab that used to sweep it up no longer does.
    await page.getByRole('group', { name: 'Estado' })
      .getByRole('button', { name: 'Vencidas', exact: true }).click();
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
  });

  test('marking an issued account as paid confirms and updates the badge', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'mark-paid');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(
      page.getByTestId('accounting-row-2').getByText('Pagada', { exact: true }),
    ).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/collection-accounts/2/mark-paid/',
      method: 'POST',
    });
  });

  test('cancelling an issued account confirms and shows Anulada', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'cancel');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(
      page.getByTestId('accounting-row-2').getByText('Anulada', { exact: true }),
    ).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/collection-accounts/2/cancel/',
      method: 'POST',
    });
  });

  test('a cuenta the client already received offers no delete, only anular', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab's own entry navigation is covered by the counters test; this one asserts which affordances the rows carry)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    // Emitida y enviada: borrarla del sistema no la borra de su bandeja.
    await page.getByTestId('collection-actions-1').click();
    await expect(page.getByTestId('collection-delete-1')).toHaveCount(0);
    await expect(page.getByTestId('collection-cancel-1')).toBeVisible();
    await page.getByTestId('collection-actions-modal').getByRole('button', { name: 'Cerrar' }).click();
    // Pagada: callejón cerrado, ni anular ni eliminar.
    await page.getByTestId('collection-actions-3').click();
    await expect(page.getByTestId('collection-delete-3')).toHaveCount(0);
    await expect(page.getByTestId('collection-cancel-3')).toHaveCount(0);
  });

  test('an annulled cuenta is deleted after typing ELIMINAR and the counters drop', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'cancel');
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(
      page.getByTestId('accounting-row-2').getByText('Anulada', { exact: true }),
    ).toBeVisible();

    await chooseCollectionAction(page, 2, 'delete');

    // The confirmation names the document before asking for the word.
    const detail = page.getByTestId('confirm-modal-detail');
    await expect(detail).toContainText('PA-2026-0002');
    await expect(detail).toContainText('Néstor Franco');
    await expect(detail).toContainText('$550.002');

    // Irreversible: the button stays shut until the word is typed.
    await expect(page.getByTestId('confirm-modal-confirm')).toBeDisabled();
    await page.getByTestId('confirm-type-input').fill('ELIMINAR');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('accounting-row-2')).toHaveCount(0);
    expect(calls).toContainEqual({
      apiPath: 'accounting/collection-accounts/2/delete/',
      method: 'DELETE',
    });
    // Emitidas 2→1 and Anuladas back to 0, without a reload.
    await expect(page.getByTestId('accounting-stat-value')).toHaveText([
      '1', '1', '1', '0',
    ]);
  });

  test('a refused delete keeps the row and says to anular instead', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // The race the hidden button cannot prevent: the cuenta leaves for the
    // client from somewhere else while this tab still shows it as deletable.
    const handler = buildHandler({ calls: [] });
    await mockApi(page, async (ctx) => {
      if (/^accounting\/collection-accounts\/\d+\/delete\/$/.test(ctx.apiPath)) {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Esta cuenta de cobro ya se envió al cliente. Anúlala en vez de eliminarla.',
          }),
        };
      }
      return handler(ctx);
    });
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'cancel');
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(
      page.getByTestId('accounting-row-2').getByText('Anulada', { exact: true }),
    ).toBeVisible();

    await chooseCollectionAction(page, 2, 'delete');
    await page.getByTestId('confirm-type-input').fill('ELIMINAR');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('ya se envió al cliente')).toBeVisible();
    // The row survives its own failed deletion.
    await expect(page.getByTestId('accounting-row-2')).toBeVisible();
  });

  test('resending a paid account asks for confirmation naming the recipient', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await chooseCollectionAction(page, 3, 'resend');

    // One click used to email a client outright. It now confirms first, and
    // the message says who is about to receive it.
    await expect(page.getByText('Reenviar cuenta de cobro')).toBeVisible();
    await page.getByRole('button', { name: 'Reenviar', exact: true }).click();

    await expect(
      page.getByText('Cuenta de cobro reenviada al cliente'),
    ).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/collection-accounts/3/resend/',
      method: 'POST',
    });
  });

  test('a failed resend surfaces the server error to the operator', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    const handler = buildHandler({ calls });
    await mockApi(page, async (ctx) => {
      if (/^accounting\/collection-accounts\/\d+\/resend\/$/.test(ctx.apiPath)) {
        return {
          status: 502,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'No se pudo enviar el correo; revisa los logs e inténtalo de nuevo.',
          }),
        };
      }
      return handler(ctx);
    });
    await gotoCollections(page);

    await chooseCollectionAction(page, 3, 'resend');
    await page.getByRole('button', { name: 'Reenviar', exact: true }).click();

    await expect(page.getByText('No se pudo reenviar')).toBeVisible();
    // The row keeps its state — nothing was mutated by the failed send.
    await expect(
      page.getByTestId('accounting-row-3').getByText('Pagada', { exact: true }),
    ).toBeVisible();
  });

  test('creating a cuenta walks through the email preview before sending', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();

    // Client from the clients module → snapshot + suggested consecutivo.
    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();
    await expect(page.getByTestId('collection-form-number')).toHaveValue('PA-ACME-001');
    await expect(page.getByTestId('collection-form-customer-email')).toHaveValue('ana@acme.co');

    // Mandatory income link via the searchable combobox. The one being billed
    // has no client yet, so the alcance has to be widened to reach it.
    await page.getByTestId('collection-form-income').click();
    await page.getByTestId('collection-form-income-scope-all').click();
    await page.getByTestId('collection-form-income-option-8').click();
    await expect(page.getByTestId('collection-form-concept'))
      .toHaveValue('Desarrollo módulo de reportes');

    // The concepto corto heads the document; what was actually done goes in
    // its own field, several lines long, and only reaches the PDF.
    await page.getByTestId('collection-form-description').fill(
      'Requerimientos atendidos:\n\n- Formulario de cotización\n- Reporte por asesor',
    );
    await page.getByTestId('collection-form-notes').fill('Cobrar antes del 15');

    await page.getByTestId('collection-form-preview').click();

    // Step 2: the real email + PDF the client will receive.
    await expect(page.getByTestId('collection-preview-subject'))
      .toContainText('PA-ACME-001');
    await expect(page.getByTestId('collection-preview-email')).toBeVisible();
    await expect(page.getByTestId('collection-preview-open-pdf')).toBeVisible();
    await expect(page.getByTestId('collection-preview-download-pdf')).toBeVisible();
    // Served, not a blob: the viewer's own download button and "Save to Drive"
    // read the name off this URL and its Content-Disposition.
    await expect(page.getByTestId('collection-preview-pdf'))
      .toHaveAttribute('src', PREVIEW_PDF_URL);

    // Email and PDF reviewable at the same time, each scrolling on its own:
    // the modal panel must not add a scrollbar nesting inside theirs, and the
    // summary and the send button must be reachable without scrolling.
    await expect(page.getByTestId('collection-preview-pdf')).toBeVisible();
    await expect(page.getByTestId('collection-preview-split-handle')).toBeVisible();
    await expect(page.getByTestId('collection-preview-subject')).toBeInViewport();
    await expect(page.getByTestId('collection-form-confirm')).toBeInViewport();
    const panelOverflow = await page
      .locator('[role="dialog"] > div:nth-child(2)')
      .evaluate((el) => el.scrollHeight - el.clientHeight);
    expect(panelOverflow).toBeLessThanOrEqual(1);

    await page.getByTestId('collection-form-confirm').click();

    await expect(page.getByText('Cuenta de cobro enviada')).toBeVisible();
    await expect(page.getByTestId('accounting-row-9')).toBeVisible();
    const createCall = calls.find(
      (call) => call.apiPath === 'accounting/collection-accounts/create/',
    );
    expect(createCall.body.income_record_id).toBe(8);
    expect(createCall.body.client_profile_id).toBe(5);
    // Untouched suggestion → the payload lets the backend allocate.
    expect(createCall.body.public_number).toBeUndefined();
    // Concepto and descripción travel apart, and the note stays internal.
    expect(createCall.body.billing_concept).toBe('Desarrollo módulo de reportes');
    expect(createCall.body.items[0].description).toContain('- Reporte por asesor');
    expect(createCall.body.notes).toBe('Cobrar antes del 15');
  });

  test('preview blockers are reported beside their fields', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();
    await page.getByTestId('collection-form-client').fill('Brújula');

    const clientOption = page.getByTestId('client-autocomplete-option-6');
    await expect(clientOption).toContainText('Sin correo');
    await clientOption.click();

    await expect(page.getByTestId('collection-form-client-email-warning'))
      .toContainText('Este cliente no tiene correo');
    const preview = page.getByTestId('collection-form-preview');
    await expect(preview).toBeEnabled();
    await preview.click();

    await expectDescribedError(
      page,
      'collection-form-client',
      'Agrega y guarda el correo del cliente.',
    );
    await expectDescribedError(
      page,
      'collection-form-income',
      'Selecciona un ingreso vinculado.',
    );
    await expectDescribedError(
      page,
      'collection-form-amount',
      'Ingresa un valor mayor a cero.',
    );
    await expectDescribedError(
      page,
      'collection-form-concept',
      'Escribe el concepto del servicio.',
    );
    await expect(page.getByTestId('collection-form-preview-gate-reasons')).toHaveCount(0);

    await page.getByTestId('collection-form-client-email-repair').fill('correo inválido');
    await page.getByTestId('collection-form-client-email-save').click();
    await expect(page.getByTestId('collection-form-client-email-error'))
      .toContainText('Escribe un correo válido');
  });

  test('saving a missing client email preserves the collection draft', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();
    await page.getByTestId('collection-form-client').fill('Brújula');
    await page.getByTestId('client-autocomplete-option-6').click();
    await page.getByTestId('collection-form-income').click();
    await page.getByTestId('collection-form-income-scope-all').click();
    await page.getByTestId('collection-form-income-option-8').click();
    await page.getByTestId('collection-form-description').fill('Detalle ya diligenciado');
    await page.getByTestId('collection-form-notes').fill('Conservar esta nota');

    await page.getByTestId('collection-form-client-email-repair').fill('billing@brujula.co');
    await page.getByTestId('collection-form-client-email-save').click();

    await expect(page.getByText('Correo guardado en el cliente')).toBeVisible();
    await expect(page.getByTestId('collection-form-client-email-warning')).toHaveCount(0);
    await expect(page.getByTestId('collection-form-customer-email'))
      .toHaveValue('billing@brujula.co');
    await expect(page.getByTestId('collection-form-description'))
      .toHaveValue('Detalle ya diligenciado');
    await expect(page.getByTestId('collection-form-notes')).toHaveValue('Conservar esta nota');
    await expect(page.getByTestId('collection-form-preview')).toBeEnabled();

    await page.getByTestId('collection-form-preview').click();

    const emailUpdate = calls.find(
      call => call.apiPath === 'proposals/client-profiles/6/update/',
    );
    expect(emailUpdate.body).toEqual({ email: 'billing@brujula.co' });
    const previewCall = calls.find(
      call => call.apiPath === 'accounting/collection-accounts/preview/',
    );
    expect(previewCall.body.customer.email).toBe('billing@brujula.co');
  });

  test('a cuenta raised from a project-linked income lands showing that project', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();
    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('collection-form-income').click();
    // A liquid link is the exception, so the test opts into it explicitly.
    await page.getByTestId('collection-form-income-kind-liquid').click();
    await page.getByTestId('collection-form-income-option-21').click();
    await page.getByTestId('collection-form-preview').click();
    await page.getByTestId('collection-form-confirm').click();

    await expect(page.getByText('Cuenta de cobro enviada')).toBeVisible();
    // The draft inherited the income's project and the column reads the
    // live FK (F7): the new row lands with its project visible, no reload.
    const newRow = page.getByTestId('accounting-row-9');
    await expect(newRow).toContainText('Vastago');
    await expect(
      page.getByTestId('collection-project-space-9').filter({ visible: true }),
    ).toBeVisible();
  });

  test('the income list follows the chosen client through to the send', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();

    // Before choosing a client the expected ledger is on offer globally.
    await page.getByTestId('collection-form-income').click();
    await expect(page.getByTestId('collection-form-income-option-22'))
      .toBeInViewport({ ratio: 1 });

    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();
    await expect(page.getByTestId('collection-form-number')).toHaveValue('PA-ACME-001');

    // Now it is Acme's expected ledger. Acme only has a liquid income in this
    // fixture, so the stable default explains the empty result instead of
    // mixing it with Torrios or the unassigned rows.
    await page.getByTestId('collection-form-income').click();
    await expect(page.getByTestId('collection-form-income-scope-client'))
      .toContainText('Del cliente (0)');
    await expect(page.getByTestId('collection-form-income-kind-expected'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('collection-form-income-empty'))
      .toContainText('Acme Soluciones no tiene ingresos esperados.');
    await expect(page.getByTestId('collection-form-income-option-21')).toHaveCount(0);
    await expect(page.getByTestId('collection-form-income-option-22')).toHaveCount(0);
    await expect(page.getByTestId('collection-form-income-option-8')).toHaveCount(0);

    // Widening reaches the unassigned ones, selectable on purpose: issuing
    // adopts the client onto them.
    await page.getByTestId('collection-form-income-scope-all').click();
    await expect(page.getByTestId('collection-form-income-group-orphan'))
      .toContainText('Sin cliente (1)');
    await page.getByTestId('collection-form-income-option-8').click();
    await expect(page.getByTestId('collection-form-income-orphan-notice'))
      .toContainText('al emitir quedará asignado a Acme Soluciones');
    await expect(page.getByTestId('collection-form-concept'))
      .toHaveValue('Desarrollo módulo de reportes');

    await page.getByTestId('collection-form-preview').click();
    await expect(page.getByTestId('collection-preview-subject'))
      .toContainText('PA-ACME-001');
    await page.getByTestId('collection-form-confirm').click();

    await expect(page.getByText('Cuenta de cobro enviada')).toBeVisible();
    await expect(page.getByTestId('accounting-row-9')).toBeVisible();
    const createCall = calls.find(
      (call) => call.apiPath === 'accounting/collection-accounts/create/',
    );
    expect(createCall.body.client_profile_id).toBe(5);
    expect(createCall.body.income_record_id).toBe(8);
  });

  test('the income filters count what they hold and never drop the cursor', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the filters under
    // test live in the create modal, which IS opened by clicking)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();
    await page.getByTestId('collection-form-income').click();

    // Before a client there is nothing to scope to, so expected rows are global
    // and 'Del cliente' says so by being unavailable.
    await expect(page.getByTestId('collection-form-income-scope-client')).toBeDisabled();
    await expect(page.getByTestId('collection-form-income-kind-all')).toContainText('Todos (3)');
    await expect(page.getByTestId('collection-form-income-kind-expected'))
      .toContainText('Esperados (2)');
    await expect(page.getByTestId('collection-form-income-kind-liquid'))
      .toContainText('Líquidos (1)');
    await expect(page.getByTestId('collection-form-income-kind-expected'))
      .toHaveAttribute('aria-selected', 'true');

    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('collection-form-income').click();

    // Acme holds one liquid income. The default expected cut names that empty
    // state and offers every kind for Acme without widening to other owners.
    await expect(page.getByTestId('collection-form-income-empty'))
      .toContainText('Acme Soluciones no tiene ingresos esperados.');
    await expect(page.getByTestId('collection-form-income')).toBeFocused();

    // The way out keeps the client scope and does not issue another request.
    await page.getByTestId('collection-form-income-see-all').click();
    await expect(page.getByTestId('collection-form-income-scope-client'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('collection-form-income-kind-all'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('collection-form-income-option-21')).toBeVisible();
    await expect(page.getByTestId('collection-form-income-option-8')).toHaveCount(0);
    await expect(page.getByTestId('collection-form-income-option-22')).toHaveCount(0);

    // Alcance remains independently reversible when a global search is needed.
    await page.getByTestId('collection-form-income-scope-all').click();
    await expect(page.getByTestId('collection-form-income-option-8')).toBeVisible();
    await expect(page.getByTestId('collection-form-income-client-22')).toHaveText('Torrios SAS');

    // Filters combine with the search rather than being replaced by it.
    await page.getByTestId('collection-form-income').fill('Torrios');
    await expect(page.getByTestId('collection-form-income-option-22')).toBeVisible();
    await expect(page.getByTestId('collection-form-income-option-8')).toHaveCount(0);

    // Clicking away dismisses the list: picking a row is no longer its only
    // exit, which matters now that it also renders on zero results. The target
    // is the modal title, above the field — anything below it sits under the
    // dropdown itself.
    await page.locator('#collection-form-title').click();
    await expect(page.getByTestId('collection-form-income-option-22')).toHaveCount(0);
  });

  test('a broken PDF viewer explains itself and keeps the download exits', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // The step exists to review the document before it reaches the client.
    // When the served PDF cannot render, the panel must say so in the app's
    // own words — not the browser's connection-refused page — and leave
    // Descargar / Abrir PDF as the way to review; the send is not blocked.
    await mockApi(page, buildHandler({ calls: [], previewPdfStatus: 500 }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();
    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('collection-form-income').click();
    await page.getByTestId('collection-form-income-scope-all').click();
    await page.getByTestId('collection-form-income-option-8').click();
    await page.getByTestId('collection-form-preview').click();

    await expect(page.getByTestId('collection-preview-subject'))
      .toContainText('PA-ACME-001');
    await expect(page.getByTestId('collection-preview-pdf-error'))
      .toContainText('No pudimos mostrar la previsualización');
    await expect(page.getByTestId('collection-preview-pdf')).toHaveCount(0);
    await expect(page.getByTestId('collection-preview-download-pdf')).toBeVisible();
    await expect(page.getByTestId('collection-preview-open-pdf')).toBeVisible();
    await expect(page.getByTestId('collection-form-confirm')).toBeEnabled();
  });

  test('an income of another client is refused before the preview is spent', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();

    // Income first: it locks in its own client, Torrios.
    await page.getByTestId('collection-form-income').click();
    await page.getByTestId('collection-form-income-option-22').click();
    await expect(page.getByTestId('collection-form-client-locked'))
      .toContainText('Torrios SAS');

    // Released and pointed at another client, the pair stops adding up.
    await page.getByTestId('collection-form-change-client').click();
    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();

    await expect(page.getByTestId('collection-form-income-conflict'))
      .toContainText('Este ingreso es de Torrios SAS, no de Acme Soluciones');
    const preview = page.getByTestId('collection-form-preview');
    await expect(preview).toBeEnabled();
    await preview.click();
    await expectDescribedError(
      page,
      'collection-form-income',
      'Resuelve el conflicto con el cliente del ingreso.',
    );
    expect(calls.filter((call) => (
      call.apiPath === 'accounting/collection-accounts/preview/'
    ))).toHaveLength(0);

    // Adopting the income's client settles it and unblocks the step.
    await page.getByTestId('collection-form-use-income-client').click();
    await expect(page.getByTestId('collection-form-income-conflict')).toHaveCount(0);
    await expect(page.getByTestId('collection-form-preview')).toBeEnabled();
  });

  test('internal notes are readable back from the list, never sent', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; what is under test
    // is the note the row hands back, reached by clicking its action)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    // The component test pins that rows without notes omit this entry; the
    // browser test follows the positive path all the way to the saved copy.
    await chooseCollectionAction(page, 1, 'notes');

    // The shared note dialog of the accounting menus, plus who can read it.
    const body = page.getByTestId('accounting-note-body');
    await expect(body).toBeVisible();
    await expect(body).toContainText('Acordado por WhatsApp');
    // The line break the operator typed survives the round trip.
    await expect(body).toContainText('Pagan el 15, no antes.');
    await expect(page.getByTestId('accounting-note-hint'))
      .toContainText('no se muestran al cliente');
  });

  test('the preview swaps email and PDF behind tabs when the window is too narrow', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the layout under
    // test lives in the create modal, which IS opened by clicking)
    //
    // Below 1024px two columns leave neither panel legible, so they collapse
    // into tabs. Only a real browser can prove it: jsdom has no layout.
    await page.setViewportSize({ width: 820, height: 900 });
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoCollections(page);

    await page.getByTestId('collection-create-button').click();
    await page.getByTestId('collection-form-client').fill('Acme');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('collection-form-income').click();
    await page.getByTestId('collection-form-income-kind-liquid').click();
    // Acme's own income: this test is about the preview layout, so it takes the
    // shortest route to it rather than widening the alcance.
    await page.getByTestId('collection-form-income-option-21').click();
    await page.getByTestId('collection-form-preview').click();

    await expect(page.getByTestId('collection-preview-subject')).toBeVisible();
    // Stacked: no divider to drag, and the email leads on a tablet.
    await expect(page.getByTestId('collection-preview-split-handle')).toHaveCount(0);
    await expect(page.getByTestId('collection-preview-email')).toBeVisible();
    await expect(page.getByTestId('collection-preview-pdf')).toBeHidden();

    await page.getByTestId('collection-preview-tab-pdf').click();

    await expect(page.getByTestId('collection-preview-pdf')).toBeVisible();
    await expect(page.getByTestId('collection-preview-email')).toBeHidden();
    // Reviewing the document never costs the operator the send decision.
    await expect(page.getByTestId('collection-form-confirm')).toBeInViewport();
  });

  test('marking an expected-linked cuenta as paid opens the Liquidar modal', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the routing under
    // test starts at the row's Marcar pagada action, which IS clicked)
    const calls = [];
    const handler = buildHandler({
      calls,
      incomeDetail: { ...ELIGIBLE_INCOME, payment_status: 'partial' },
    });
    await mockApi(page, async (ctx) => {
      if (ctx.apiPath === 'accounting/collection-accounts/' && ctx.method === 'GET') {
        const rows = makeRows();
        rows[1].income_record_id = 8;
        rows[1].income_kind = 'expected';
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: rows, meta: META }),
        };
      }
      return handler(ctx);
    });
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'mark-paid');

    // Never a silent mark-paid: the Liquidar modal takes over.
    await expect(
      page.getByRole('heading', { name: 'Liquidar ingreso esperado' }),
    ).toBeVisible();
    await expect(page.getByTestId('confirm-modal-confirm')).toBeHidden();
    expect(calls.some(
      (call) => call.apiPath.endsWith('/mark-paid/'),
    )).toBe(false);
  });

  test('a hosting cuenta with no period completes it from the Liquidar modal', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the flow under test
    // starts at the row's Marcar pagada action, which IS clicked)
    const handler = buildHandler({
      calls: [],
      incomeDetail: {
        ...ELIGIBLE_INCOME,
        concept: 'Vastago (Hosting) - Semestre 1',
        origin: 'hosting',
        // A charge from before the period fields existed: the block shows up
        // for it, proposes the window on the charge's own date, and never
        // holds up the settlement.
        period_date: '2026-10-01',
        period_start: null,
        period_end: null,
        period_cadence: '',
      },
    });
    let settled = null;
    await mockApi(page, async (ctx) => {
      if (ctx.apiPath === 'accounting/incomes/8/settle/' && ctx.method === 'POST') {
        settled = ctx.route.request().postDataJSON();
        return {
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            income: ELIGIBLE_INCOME,
            liquid: null,
            expenses: [],
            expected_incomes: [],
          }),
        };
      }
      if (ctx.apiPath === 'accounting/collection-accounts/' && ctx.method === 'GET') {
        const rows = makeRows();
        rows[1].income_record_id = 8;
        rows[1].income_kind = 'expected';
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: rows, meta: META }),
        };
      }
      return handler(ctx);
    });
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'mark-paid');
    await expect(page.getByTestId('income-liquidate-period-start'))
      .toHaveValue('2026-10-01');

    // One choice completes the window: the end follows from the periodicity.
    await page.getByTestId('income-liquidate-period-cadence')
      .selectOption('semiannual');
    await expect(page.getByTestId('income-liquidate-period-end'))
      .toHaveValue('2027-03-31');

    await page.getByTestId('income-liquidate-submit').click();

    await expect(
      page.getByRole('heading', { name: 'Liquidar ingreso esperado' }),
    ).toBeHidden();
    expect(settled.period).toEqual({
      period_start: '2026-10-01',
      period_end: '2027-03-31',
      period_cadence: 'semiannual',
    });
  });

  test('Cliente and Proyecto are separate columns, each sortable on its own', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_DETAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the behaviour under
    // test is the column sort, which IS clicked below)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoCollections(page);

    // The fixture carries the old `Persona - Marca` snapshot in
    // customer_name; the columns must show the two halves apart.
    const row = page.getByTestId('accounting-row-1');
    await expect(row).toContainText('Germán Franco');
    await expect(row).toContainText('Kore');

    // Sorting by Proyecto alone is what "filtrables y ordenables por
    // separado" actually means — a shared column could not do this.
    await page.getByTestId('accounting-sort-project_name').click();

    const projects = page.locator('[data-testid^="accounting-row-"]');
    await expect(projects.first()).toContainText('Kore');
    await expect(projects.last()).toContainText('Xpandia');
  });

  test('two cuentas of one client each tell their own project truth, also after reload', {
    tag: [...ADMIN_ACCOUNTING_COLLECTIONS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the coherence
    // under test is exercised by clicking the Proyecto filter below)
    // The reported evidence case: same client, one cuenta with the live
    // relation and one with neither FK nor snapshot. The cell answers the
    // live FK (snapshot only as fallback), the filter agrees with the cell,
    // and a reload tells the same truth.
    const rows = makeRows();
    rows[1] = {
      ...rows[1],
      customer_name: 'Daniel Felipe Corredor',
      client_display_name: 'Daniel Felipe Corredor',
      project_id: 9,
      project_name: 'Mimittos',
    };
    rows[2] = {
      ...rows[2],
      public_number: 'PA-DEIVISRI-001',
      customer_name: 'Daniel Felipe Corredor',
      client: rows[1].client,
      client_display_name: 'Daniel Felipe Corredor',
      project_id: null,
      project_name: '',
      commercial_status: 'issued',
      commercial_status_label: 'Emitida',
    };
    const handler = buildHandler({ calls: [] });
    await mockApi(page, async (ctx) => {
      if (ctx.apiPath === 'accounting/collection-accounts/' && ctx.method === 'GET') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: rows, meta: META }),
        };
      }
      return handler(ctx);
    });
    await gotoCollections(page);

    await expect(page.getByTestId('accounting-row-2')).toContainText('Mimittos');
    await expect(
      page.getByTestId('collection-no-project-3').filter({ visible: true }),
    ).toHaveText('—');

    // The filter keys off the same live FK the cell shows: picking the
    // project keeps the linked cuenta and drops the blank sibling.
    await page.getByRole('button', { name: /Filtros/ }).click();
    await page.getByTestId('accounting-filter-panel')
      .getByRole('button', { name: /^Proyecto/ }).click();
    await page.getByLabel('Mimittos').check();
    await expect(page.locator('[data-testid^="accounting-row-"]')).toHaveCount(1);
    await expect(page.getByTestId('accounting-row-2')).toBeVisible();

    // Requisito 18: the same truth after a reload (filters are ephemeral,
    // both rows return, each with its own cell).
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('accounting-row-2')).toContainText('Mimittos');
    await expect(
      page.getByTestId('collection-no-project-3').filter({ visible: true }),
    ).toHaveText('—');
  });

  test('opening the detail shows the linked income and its settlement history', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_DETAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the behaviour under
    // test is the detail modal, which IS opened by clicking the row action)
    await mockWithLinkedIncome(page);
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'view-detail');

    const modal = page.getByTestId('collection-detail-modal');
    await expect(modal).toBeVisible();
    await expect(page.getByTestId('collection-detail-client'))
      .toHaveText('Néstor Franco');
    await expect(page.getByTestId('collection-detail-project'))
      .toHaveText('Xpandia');
    // The history the panel could not reach before this branch.
    await expect(
      page.getByTestId('collection-detail-settlement-row'),
    ).toHaveCount(2);
    await expect(modal).toContainText('Abono 1');
    await expect(modal).toContainText('Comisión de pasarela');
  });

  test('the Documento tab embeds the PDF instead of downloading it', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_DETAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the behaviour under
    // test is the Documento tab, reached by clicking the row action then the tab)
    await mockWithLinkedIncome(page);
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'view-detail');
    await page.getByRole('tab', { name: 'Documento' }).click();

    await expect(page.getByTestId('collection-detail-pdf')).toHaveAttribute(
      'src', '/api/accounting/collection-accounts/2/pdf/?inline=1',
    );
  });

  test('going to the income lands on a tab that does not filter it out', {
    tag: [...ADMIN_ACCOUNTING_COLLECTION_DETAIL, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the behaviour under
    // test is the exit link inside the modal, which IS clicked)
    await mockWithLinkedIncome(page);
    await gotoCollections(page);

    await chooseCollectionAction(page, 2, 'view-detail');
    await page.getByTestId('collection-detail-go-to-income').click();

    // El salto entrega los dos params. `focus` sólo destaca la fila una vez y
    // la vista lo suelta al montar, así que se comprueba en el hand-off.
    await page.waitForURL(/focus=8/);
    // El tab sí describe lo que se está viendo y se queda: sin él Ingresos
    // aterriza en su builtin "Solo esperados", que filtra la fila destacada
    // fuera de su propia lista.
    await expect(page).toHaveURL(/accounting_incomeTab=all/);
  });
});
