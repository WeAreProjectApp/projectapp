/**
 * E2E tests for the accounting dashboard (superuser-only module).
 *
 * FLOW: admin-accounting-dashboard
 * Covers: stat cards from the summary endpoint, monthly table, subnav
 *         navigation, sidebar visibility for superusers and the gating
 *         redirect for staff non-superusers.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_ACCOUNTING_DASHBOARD,
  ADMIN_ACCOUNTING_RECEIVABLES,
  ADMIN_ACCOUNTING_STATS_MODALS,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const MONTHS = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

const DASHBOARD_SUMMARY = {
  year: 2026,
  expected_total: '95238699.00',
  liquid_total: '59516261.00',
  difference: '-35722438.00',
  expenses_total: '62628212.00',
  expected_utility: '32610487.00',
  liquid_utility: '-3111951.00',
  pocket_balance: '1147378.00',
  partners: {
    gustavo: { expected: '54846399.00', liquid: '37040740.00', expenses: '36771980.00', net: '268760.00' },
    carlos: { expected: '40392300.00', liquid: '22475521.00', expenses: '13452275.00', net: '9023246.00' },
    company: { expected: '0.00', liquid: '0.00', expenses: '12403957.00', net: '0.00' },
  },
  monthly: MONTHS.map((label, index) => ({
    period: `2026-${String(index + 1).padStart(2, '0')}`,
    label: `${label} 2026`,
    expected: index === 1 ? '1160000.00' : '0.00',
    liquid: index === 1 ? '900000.00' : '0.00',
    expenses: index === 2 ? '400000.00' : '0.00',
    expected_utility: index === 1 ? '760000.00' : '0.00',
    utility: index === 1 ? '500000.00' : '0.00',
  })),
  recurring_monthly_cost: '3016059.00',
  ads: { year_total: '1008404.00', current_month_total: '0.00' },
  hostings: { active_count: 6, monthly_income: '288356.00', total_paid: '4574080.00' },
  latest_card_snapshots: [
    {
      card_name: 'T.C 0064',
      snapshot_date: '2026-07-01',
      available_amount: '3849046.00',
      debt_amount: '4150954.00',
    },
  ],
  expected_current_month: { period: '2026-07', label: 'Julio 2026', total: '2500000.00' },
  receivables: {
    high_total: '2000000.00',
    high_count: 1,
    selected_count: 2,
    selected_total: '3000000.00',
    paid_total: '500000.00',
    pending_total: '2500000.00',
    by_confidence: {
      high: {
        count: 1, total_amount: '2000000.00',
        paid_amount: '500000.00', pending_amount: '1500000.00',
      },
      medium: { count: 0, total_amount: '0.00', paid_amount: '0.00', pending_amount: '0.00' },
      low: { count: 0, total_amount: '0.00', paid_amount: '0.00', pending_amount: '0.00' },
      unclassified: {
        count: 1, total_amount: '1000000.00',
        paid_amount: '0.00', pending_amount: '1000000.00',
      },
    },
  },
  card_debt: {
    total: '4150954.00',
    card_count: 1,
    credit_limit_total: '8000000.00',
    utilization_pct: 51.9,
  },
};

const EXPECTED_MONTH_ROWS = [
  {
    id: 71,
    concept: 'Kore v2 (Fase 1) - Inicio 40%',
    period_label: 'Julio 2026',
    client: 10,
    client_name: 'Kore',
    project: 100,
    project_name: 'Kore v2',
    kind: 'expected',
    ledger: 'company',
    total_amount: '2000000.00',
    paid_amount: '500000.00',
    pending_amount: '1500000.00',
    payment_status: 'partial',
    payment_status_label: 'Parcial',
    is_receivable_candidate: true,
    collection_confidence: 'high',
  },
  {
    id: 72,
    concept: 'Hosting anual Acme',
    period_label: '17 Julio 2026',
    client: 20,
    client_name: 'Acme',
    project: null,
    project_name: null,
    kind: 'expected',
    ledger: 'company',
    total_amount: '1000000.00',
    paid_amount: '0.00',
    pending_amount: '1000000.00',
    payment_status: 'pending',
    payment_status_label: 'Pendiente',
    is_receivable_candidate: true,
    collection_confidence: '',
  },
];

const STATS_PAYLOAD = {
  year: 2026,
  income: {
    liquid: {
      count: 12, total: '59516261.00', avg: '4959688.42',
      min: '288356.00', max: '9000000.00',
    },
    expected: {
      count: 15, total: '95238699.00', avg: '6349246.60',
      min: '500000.00', max: '12000000.00',
    },
    lost_total: '1200000.00',
    top_concepts: [
      { concept: 'Kore v2 (Fase 1)', total: '18000000.00', count: 3 },
      { concept: 'Hosting anual Acme', total: '9000000.00', count: 2 },
    ],
  },
  expenses: {
    summary: {
      count: 40, total: '62628212.00', avg: '1565705.30',
      min: '25000.00', max: '8000000.00',
    },
    by_category: [
      { category: 'business', label: 'Negocio', total: '50000000.00', count: 30 },
      { category: 'personal', label: 'Personal', total: '12628212.00', count: 10 },
    ],
    top_concepts: [
      { concept: 'Claude Code 20x', total: '9600000.00', count: 12 },
    ],
    recurring_monthly_cost: '3016059.00',
  },
};

function buildHandler({
  isSuperuser = true,
  calls = [],
  failReceivables = false,
  unselectedHosting = false,
} = {}) {
  let receivableRows = EXPECTED_MONTH_ROWS.map((row) => (
    row.id === 72 && unselectedHosting
      ? { ...row, is_receivable_candidate: false }
      : { ...row }
  ));
  return ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { username: 'admin', is_staff: true, is_superuser: isSuperuser },
        }),
      };
    }
    if (apiPath.startsWith('accounting/stats/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(STATS_PAYLOAD),
      };
    }
    if (apiPath.startsWith('accounting/dashboard/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(DASHBOARD_SUMMARY),
      };
    }
    if (apiPath === 'accounting/receivables/' && method === 'GET') {
      if (failReceivables) {
        return {
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Servicio temporalmente no disponible' }),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: receivableRows,
          summary: DASHBOARD_SUMMARY.receivables,
        }),
      };
    }
    if (/^accounting\/incomes\/\d+\/update\/$/.test(apiPath) && method === 'PATCH') {
      const id = Number(apiPath.split('/')[2]);
      const payload = route.request().postDataJSON();
      calls.push({ method, apiPath, body: payload });
      receivableRows = receivableRows.map((row) => {
        if (row.id !== id) return row;
        return { ...row, ...payload };
      });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(receivableRows.find((row) => row.id === id)),
      };
    }
    if (apiPath.startsWith('accounting/incomes/') && method === 'GET') {
      const url = route.request().url();
      if (url.includes('kind=expected') && url.includes('date_from=2026-07-01')) {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ results: EXPECTED_MONTH_ROWS, meta: {} }),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], meta: {} }),
      };
    }
    if (apiPath.startsWith('accounting/card-snapshots/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            {
              id: 1, card_name: 'T.C 0064', snapshot_date: '2026-06-17',
              available_amount: '413226.00', debt_amount: '7586774.00', notes: '',
            },
            {
              id: 2, card_name: 'T.C 0064', snapshot_date: '2026-07-01',
              available_amount: '3849046.00', debt_amount: '4150954.00', notes: '',
            },
          ],
          meta: {},
        }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

test.describe('Admin Accounting Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('renders stat cards with the summary totals', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // Bug caught: the Contabilidad navigation could stop reaching the dashboard KPI cards.
    await mockApi(page, buildHandler());
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    const summaryLink = page.getByRole('link', { name: 'Resumen', exact: true });
    await expect(summaryLink).toHaveAttribute('href', /\/panel\/accounting$/);
    await summaryLink.click();
    await expect(page).toHaveURL(/\/panel\/accounting$/);

    await expect(
      page.getByRole('heading', { name: 'Resumen', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('accounting-hero-kpi')).toBeVisible();
    await expect(page.getByTestId('accounting-hero-value')).toBeVisible();
    await expect(page.getByTestId('utility-stats-panel')).toBeVisible();
    await expect(page.getByTestId('utility-stats-toggle')).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByTestId('stats-line-chart').locator('.apexcharts-canvas'))
      .toBeVisible({ timeout: 15_000 });
    const receivables = page.getByTestId('accounting-card-receivables');
    await expect(receivables).toContainText('Pendiente por cobrar');
    await expect(receivables).toContainText('$2.000.000 COP');
    await expect(receivables).toContainText('1 ingreso seleccionado en verde');

    const cardDebt = page.getByTestId('accounting-card-debt');
    await expect(cardDebt).toContainText('Deuda tarjetas');
    await expect(cardDebt).toContainText('$4.150.954 COP');
    await expect(cardDebt).toContainText('1 tarjeta · 51.9% del cupo');

    const secondaryIndicators = page.getByTestId('accounting-secondary-indicators');
    await expect(secondaryIndicators).toContainText('Ingresos líquidos');
    await expect(secondaryIndicators).toContainText('$59.516.261 COP');
    await expect(secondaryIndicators).toContainText('Bolsillo ProjectApp');
    await expect(secondaryIndicators).toContainText('$1.147.378 COP');
  });

  test('accounting quick access replaces ads with collection accounts', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockApi(page, buildHandler());
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });

    const navigation = page.getByRole('navigation', { name: 'Navegación del panel' });
    const collections = navigation.getByRole('link', { name: 'Cuentas de cobro', exact: true });
    await expect(collections).toHaveAttribute('href', /\/panel\/accounting\/collections$/);
    await expect(navigation.getByRole('link', { name: 'Ads', exact: true })).toHaveCount(0);

    await collections.click();

    await expect(page).toHaveURL(/\/panel\/accounting\/collections$/);
    await expect(page.getByRole('heading', { name: 'Cuentas de cobro', exact: true }))
      .toBeVisible({ timeout: 25_000 });
  });

  test('receivables card shows the grouped global forecast and its three tabs', {
    tag: [...ADMIN_ACCOUNTING_RECEIVABLES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Bug caught: the Contabilidad navigation could stop reaching the receivables forecast.
    await mockApi(page, buildHandler());
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    const summaryLink = page.getByRole('link', { name: 'Resumen', exact: true });
    await expect(summaryLink).toHaveAttribute('href', /\/panel\/accounting$/);
    await summaryLink.click();
    await expect(page).toHaveURL(/\/panel\/accounting$/);

    const card = page.getByTestId('accounting-card-receivables');
    await expect(card).toBeVisible({ timeout: 25_000 });
    await card.click();

    await expect(page.getByTestId('receivables-modal')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Pendientes por cobrar' }),
    ).toBeVisible();
    await expect(page.getByTestId('receivables-group-high')).toContainText('$2.000.000 COP');
    await expect(page.getByTestId('receivables-group-unclassified')).toContainText('$1.000.000 COP');

    await page.getByRole('tab', { name: /Selección/ }).click();
    await expect(page.getByTestId('receivables-selected-tab')).toContainText('Hosting anual Acme');
    await page.getByRole('tab', { name: /Gestionar candidatos/ }).click();
    await expect(page.getByTestId('receivables-manage-tab')).toBeVisible();
    await expect(page.getByTestId('receivables-manage-tab')).toContainText('Kore v2 (Fase 1) - Inicio 40%');

    await page.getByRole('button', { name: 'Cerrar' }).click();
    await expect(page.getByTestId('receivables-modal')).toHaveCount(0);
  });

  test('receivables management saves a manual candidate change immediately', {
    tag: [...ADMIN_ACCOUNTING_RECEIVABLES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('accounting-card-receivables').click();
    await page.getByRole('tab', { name: /Gestionar candidatos/ }).click();
    await page.getByRole('switch', { name: /Quitar Hosting anual Acme/ }).click();
    await expect(page.getByRole('tab', { name: /Selección/ })).toContainText('1');
    await expect.poll(() => calls.find((call) => (
      call.apiPath === 'accounting/incomes/72/update/'
    ))?.body).toEqual({ is_receivable_candidate: false });
  });

  test('receivables help stays above its modal', {
    tag: [...ADMIN_ACCOUNTING_RECEIVABLES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    // quality: allow-deep-link (dashboard navigation is covered separately; this test isolates the modal floating-layer contract)
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('accounting-card-receivables').click();

    await page.getByTestId('receivable-legend-trigger').hover();

    const tooltip = page.getByRole('tooltip');
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toContainText('Semáforo de cobro');
    await expect.poll(() => tooltip.evaluate((element) => (
      Boolean(element.closest('[data-modal-floating-root]'))
    ))).toBe(true);
  });

  test('candidate management controls its grouping presentation', {
    tag: [...ADMIN_ACCOUNTING_RECEIVABLES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    // quality: allow-deep-link (dashboard navigation is covered separately; this test isolates the receivables grouping controls)
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('accounting-card-receivables').click();
    await page.getByRole('tab', { name: /Gestionar candidatos/ }).click();

    await expect(page.getByTestId('receivables-group-client')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('receivable-candidate-group-10')).toContainText('Kore');
    await expect(page.getByTestId('receivable-candidate-group-total_amount-10'))
      .toContainText('$2.000.000 COP');

    await page.getByTestId('receivables-group-project').click();
    await expect(page.getByTestId('receivable-candidate-group-100')).toContainText('Kore v2');
    await expect(page.getByTestId('receivable-candidate-group-none')).toContainText('Sin proyecto');

    await page.getByTestId('receivables-view-classic').click();
    await expect(page.getByTestId('receivables-group-by')).toHaveCount(0);
    await expect(page.getByTestId('receivables-manage-tab').getByRole('table')).toBeVisible();

    await page.getByRole('button', { name: 'Cerrar' }).click();
    await page.getByTestId('accounting-card-receivables').click();
    await page.getByRole('tab', { name: /Gestionar candidatos/ }).click();
    await expect(page.getByTestId('receivables-group-client')).toHaveAttribute('aria-selected', 'true');
  });

  test('confidence change waits for manual forecast activation', {
    tag: [...ADMIN_ACCOUNTING_RECEIVABLES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: choosing green used to flip the independent candidate switch.
    const calls = [];
    await mockApi(page, buildHandler({ calls, unselectedHosting: true }));
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('accounting-card-receivables').click();
    await page.getByRole('tab', { name: /Gestionar candidatos/ }).click();
    await page.getByRole('combobox', {
      name: 'Probabilidad de cobro de Hosting anual Acme',
    }).selectOption('high');

    await expect.poll(() => calls.find((call) => (
      call.apiPath === 'accounting/incomes/72/update/'
    ))?.body).toEqual({ collection_confidence: 'high' });
    await expect(page.getByRole('switch', { name: /Agregar Hosting anual Acme/ }))
      .toHaveAttribute('aria-checked', 'false');
    await expect(page.getByTestId('accounting-card-receivables')).toContainText('$2.000.000 COP');
    await expect(page.getByRole('tab', { name: /Selección/ })).toContainText('1');

    await page.getByRole('switch', { name: /Agregar Hosting anual Acme/ }).click();

    await expect.poll(() => calls.filter((call) => (
      call.apiPath === 'accounting/incomes/72/update/'
    )).at(-1)?.body).toEqual({ is_receivable_candidate: true });
    await expect(page.getByTestId('accounting-card-receivables')).toContainText('$3.000.000 COP');
    await page.getByRole('tab', { name: /Selección/ }).click();
    await expect(page.getByTestId('receivables-selected-tab')).toContainText('Hosting anual Acme');
  });

  test('receivables modal exposes a retry action when its request fails', {
    tag: [...ADMIN_ACCOUNTING_RECEIVABLES, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ failReceivables: true }));
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('accounting-card-receivables').click();
    await expect(page.getByText('No se pudieron cargar los pendientes por cobrar.'))
      .toBeVisible();
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  });

  test('liquid-income card opens the stats modal with tabbed charts', {
    tag: [...ADMIN_ACCOUNTING_STATS_MODALS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    const card = page.getByTestId('accounting-card-liquid-income');
    await expect(card).toBeVisible({ timeout: 25_000 });
    await card.click();

    const modal = page.getByRole('dialog').filter({ has: page.getByTestId('stats-modal') });
    await expect(modal).toBeVisible();
    await expect(
      modal.getByRole('heading', { name: 'Estadísticas de ingresos 2026' }),
    ).toBeVisible();
    await expect(
      modal.getByTestId('stats-line-chart').locator('.apexcharts-canvas'),
    ).toBeVisible({ timeout: 15_000 });

    await modal.getByRole('tab', { name: 'Top conceptos' }).click();
    await expect(modal.getByText('Ticket promedio')).toBeVisible();
    await expect(modal.getByText('Kore v2 (Fase 1)').first()).toBeVisible();
    await expect(
      modal.getByTestId('stats-bar-chart').locator('.apexcharts-canvas'),
    ).toBeVisible({ timeout: 15_000 });

    await modal.getByRole('button', { name: 'Cerrar' }).click();
    await expect(modal).toHaveCount(0);
  });

  test('renders the 12-month breakdown with a totals row', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Detalle mensual 2026')).toBeVisible({ timeout: 25_000 });
    // Month labels also appear inside the charts' SVG: assert on the cells.
    await expect(page.getByRole('cell', { name: 'Enero 2026' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Diciembre 2026' })).toBeVisible();
    await expect(
      page.getByRole('cell', { name: 'Total', exact: true }),
    ).toBeVisible();
  });

  test('renders the evolution charts and reacts to the month range', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Evolución 2026')).toBeVisible({ timeout: 25_000 });
    const monthlyChart = page.getByTestId('accounting-monthly-chart');
    await expect(monthlyChart.locator('.apexcharts-canvas')).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByTestId('accounting-card-debt-chart').locator('.apexcharts-canvas'),
    ).toBeVisible();

    // Narrow the range to a window without movements: empty state appears.
    await page.getByTestId('accounting-month-from').selectOption('7');
    await page.getByTestId('accounting-month-to').selectOption('8');
    await expect(monthlyChart.getByText('Sin movimientos en el rango')).toBeVisible();
  });

  test('links to the cards history from the Tarjetas table', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('accounting-cards-link')).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('accounting-cards-link').click();
    await expect(page).toHaveURL(/\/panel\/accounting\/cards/);
  });

  test('subnav pill navigates to the incomes subview', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Resumen', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('accounting-subnav-incomes').click();

    await expect(page).toHaveURL(/\/panel\/accounting\/incomes/);
    await expect(page.getByRole('heading', { name: 'Ingresos', exact: true })).toBeVisible();
  });

  test('sidebar shows the Accounting section for superusers', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler());
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Resumen', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(
      page
        .getByRole('navigation', { name: 'Navegación del panel' })
        .getByRole('link', { name: 'Ingresos' }),
    ).toBeVisible();
  });

  test('staff non-superuser is redirected to /panel and sees no Accounting section', {
    tag: [...ADMIN_ACCOUNTING_DASHBOARD, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ isSuperuser: false }));
    await page.goto('/panel/accounting', { waitUntil: 'domcontentloaded' });

    await expect(page).toHaveURL(/\/panel\/?$/, { timeout: 25_000 });
    await expect(
      page
        .getByRole('navigation', { name: 'Navegación del panel' })
        .getByRole('link', { name: 'Ingresos' }),
    ).toHaveCount(0);
  });
});
