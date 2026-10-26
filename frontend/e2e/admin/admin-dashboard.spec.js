/**
 * E2E tests for the redesigned global admin dashboard (/panel).
 *
 * The page consumes the consolidated GET /api/panel/dashboard/ payload:
 * pulse tiles (finance/pipeline/attention), the attention radar, and the
 * finance / proposals / operations sections. Finance renders only when
 * the payload carries it (superuser); staff receive finance: null.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_ADDITIONAL_MODULES_QUICK_ACCESS,
  ADMIN_DASHBOARD,
  ADMIN_DASHBOARD_ATTENTION_RADAR,
  ADMIN_DASHBOARD_ERROR_RETRY,
  ADMIN_DASHBOARD_FINANCE_GATE,
  ADMIN_DASHBOARD_PIPELINE_VALUE,
  ADMIN_DASHBOARD_QUICK_CREATE,
  ADMIN_DASHBOARD_STATS_MODALS,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true, is_superuser: true } }),
};

const financeBlock = {
  year: 2026,
  expected_total: 150000000,
  liquid_total: 120000000,
  expenses_total: 40000000,
  expected_utility: 110000000,
  liquid_utility: 80000000,
  pocket_balance: 12000000,
  expected_current_month: { period: '2026-07', label: 'Julio 2026', total: 9000000 },
  card_debt: { total: 3000000, card_count: 2, credit_limit_total: 10000000, utilization_pct: 30 },
  recurring_monthly_cost: 2500000,
  hostings: { active_count: 14, monthly_income: 1200000, total_paid: 34000000 },
  monthly: [],
};

const summaryFixture = {
  generated_at: '2026-07-16T10:00:00-05:00',
  finance: financeBlock,
  proposals: {
    total_proposals: 10,
    by_status: { draft: 2, sent: 3, viewed: 2, accepted: 2, finished: 0, rejected: 1, expired: 0 },
    conversion_rate: 40,
    pipeline_value: 45000000,
    pipeline_count: 3,
    monthly_trend: [],
    recent: [{ id: 1, title: 'Sitio ACME', client_name: 'ACME Corp', status: 'sent' }],
  },
  additional_modules: {
    active_module_count: 23,
    active_share_count: 4,
    unopened_active_share_count: 2,
    last_viewed_at: '2026-07-15T15:30:00Z',
  },
  operations: {
    tasks: { open: 5, overdue: 2, overdue_high: 1, blocked: 0, high_priority_open: 2 },
    documents: {
      by_status: { draft: 1, published: 3, archived: 0 },
      collection_accounts: { issued_count: 3, overdue_issued: 1, outstanding_total: 5000000 },
    },
    diagnostics: { by_status: {}, active_pipeline: 2, accepted_value: 8000000 },
    emails: {
      total_30d: 42,
      sent_count: 40,
      failed_count: 2,
      success_rate: 95.2,
      daily_trend: [
        { date: '2026-07-15', total: 3, failed: 0 },
        { date: '2026-07-16', total: 2, failed: 1 },
      ],
    },
    hour_packages: { active_count: 6 },
  },
  attention: [
    { type: 'documents_overdue', severity: 'danger', count: 1, meta: {} },
    { type: 'tasks_overdue', severity: 'danger', count: 2, meta: { high_priority: 1 } },
  ],
};

const proposalsDashboardFixture = {
  total_proposals: 10,
  by_status: { draft: 2, sent: 3, viewed: 2, negotiating: 0, accepted: 2, finished: 0, rejected: 1, expired: 0 },
  conversion_rate: 40,
  pipeline_value: 45000000,
  pipeline_count: 3,
  monthly_trend: [
    { month: '2026-05-01', created: 4, sent: 3, accepted: 1, finished: 0, rejected: 1 },
    { month: '2026-06-01', created: 3, sent: 2, accepted: 1, finished: 0, rejected: 0 },
  ],
  avg_value_by_status: { accepted: 12000000, rejected: 6000000, sent: 8000000, viewed: 0, finished: 0, expired: 0 },
};

function jsonResponse(body) {
  return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
}

async function mockDashboard(page, summary, { authBody = authCheck } = {}) {
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authBody;
    if (apiPath === 'panel/dashboard/') return jsonResponse(summary);
    return null;
  });
}

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8400, role: 'admin', is_staff: true } });
  });

  test('renders pulse, radar and module sections for a superuser payload', {
    tag: [...ADMIN_DASHBOARD, '@role:admin', '@outcome:display', '@responsive:dashboard'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (dashboard-composition smoke; the dashboard's interactions are covered by the stats-modal, quick-create and error-retry tests)
    await mockDashboard(page, summaryFixture);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.waitForResponse((res) => res.url().includes('/api/panel/dashboard/'));

    await expect(page.getByTestId('dashboard-pulse')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Utilidad líquida 2026').first()).toBeVisible();
    await expect(page.getByTestId('attention-radar-list')).toBeVisible();
    await expect(page.getByTestId('dashboard-finance-section')).toBeVisible();
    await expect(page.getByTestId('dashboard-proposals-section')).toBeVisible();
    await expect(page.getByTestId('dashboard-additional-modules-section')).toBeVisible();
    await expect(page.getByTestId('dashboard-operations-section')).toBeVisible();
  });

  test('opens a tracked client selection from the commercial resource summary', {
    tag: [...ADMIN_ADDITIONAL_MODULES_QUICK_ACCESS, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'panel/dashboard/') return jsonResponse(summaryFixture);
      if (apiPath === 'additional-modules/admin/') {
        return jsonResponse({ revision: 'r1', categories: [], modules: [] });
      }
      if (apiPath === 'additional-modules/admin/shares/') return jsonResponse([]);
      if (apiPath === 'proposals/client-profiles/') return jsonResponse([]);
      return null;
    });
    // quality: allow-deep-link (the dashboard itself is the entry point whose cross-route action is under test)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    const resources = page.getByTestId('dashboard-additional-modules-section');

    await expect(resources.getByTestId('additional-modules-active-count')).toHaveText('23');
    await expect(resources.getByTestId('additional-modules-unopened-count')).toHaveText('2');
    await resources.getByTestId('additional-modules-create-share').click();

    await expect(page).toHaveURL(/\/es-co\/panel\/additional-modules\?action=share$/);
    await expect(page.getByRole('heading', { name: 'Preparar enlace compartible' })).toBeVisible();
  });

  test('pulse tiles open the finance and proposals stats modals', {
    tag: [...ADMIN_DASHBOARD_STATS_MODALS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'panel/dashboard/') return jsonResponse(summaryFixture);
      if (apiPath === 'proposals/dashboard/') return jsonResponse(proposalsDashboardFixture);
      return null;
    });
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.waitForResponse((res) => res.url().includes('/api/panel/dashboard/'));

    // Proposals modal: lazy proposals/dashboard/ fetch on first open.
    await page.getByTestId('dashboard-pipeline-tile').click();
    await expect(page.getByTestId('stats-modal')).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByRole('heading', { name: 'Estadísticas de propuestas' }),
    ).toBeVisible();
    await expect(page.getByText('3 en curso')).toBeVisible();

    await page.getByRole('tab', { name: 'Embudo' }).click();
    await expect(
      page.getByTestId('stats-bar-chart').locator('.apexcharts-canvas'),
    ).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: 'Cerrar' }).click();
    await expect(page.getByTestId('stats-modal')).toHaveCount(0);

    // Finance modal (superuser-gated tile).
    await page.getByTestId('dashboard-finance-tile').click();
    await expect(
      page.getByRole('heading', { name: 'Estadísticas financieras 2026' }),
    ).toBeVisible();
    await page.getByRole('tab', { name: 'Deuda y compromisos' }).click();
    await expect(
      page.getByTestId('stats-summary-strip').getByText('Por cobrar este mes'),
    ).toBeVisible();
    await expect(
      page.getByTestId('stats-radial-chart').locator('.apexcharts-canvas'),
    ).toBeVisible({ timeout: 15000 });
  });

  test('renders the pipeline pulse tile with value and count', {
    tag: [...ADMIN_DASHBOARD_PIPELINE_VALUE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — the pipeline tile renders its value/count from the dashboard payload)
    await mockDashboard(page, summaryFixture);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.waitForResponse((res) => res.url().includes('/api/panel/dashboard/'));

    await expect(page.getByText('Pipeline activo')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/3 propuestas en curso/)).toBeVisible();
  });

  test('pipeline tile shows a dash when pipeline_value is null', {
    tag: [...ADMIN_DASHBOARD_PIPELINE_VALUE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — asserts the null-value dash rendering via toHaveText)
    const noPipeline = {
      ...summaryFixture,
      proposals: { ...summaryFixture.proposals, pipeline_value: null, pipeline_count: 0 },
    };
    await mockDashboard(page, noPipeline);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.waitForResponse((res) => res.url().includes('/api/panel/dashboard/'));

    const pipelineTile = page.getByTestId('dashboard-pipeline-tile');
    await expect(pipelineTile).toBeVisible({ timeout: 10000 });
    await expect(pipelineTile.getByTestId('dashboard-stat-value')).toHaveText('—');
  });

  test('hides the finance section for staff without finance data', {
    tag: [...ADMIN_DASHBOARD_FINANCE_GATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (permission-gated display — asserts the finance section is withheld for non-superuser staff, by absence)
    const staffAuth = {
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user: { username: 'staff', is_staff: true, is_superuser: false } }),
    };
    const staffSummary = {
      ...summaryFixture,
      finance: null,
      attention: summaryFixture.attention.filter((item) => item.type !== 'recurring_due'),
    };
    await mockDashboard(page, staffSummary, { authBody: staffAuth });
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.waitForResponse((res) => res.url().includes('/api/panel/dashboard/'));

    await expect(page.getByTestId('dashboard-proposals-section')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('dashboard-finance-section')).not.toBeVisible();
    await expect(page.getByText('Utilidad líquida 2026')).not.toBeVisible();
  });

  test('attention radar renders collapsible severity summaries', {
    tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — asserts the radar renders each attention item's copy and module link from the payload)
    await mockDashboard(page, summaryFixture);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.waitForResponse((res) => res.url().includes('/api/panel/dashboard/'));

    const docsItem = page.getByTestId('attention-item-documents_overdue');
    await expect(docsItem).toBeVisible({ timeout: 10000 });
    await expect(docsItem).toContainText('1 cuenta de cobro vencida');
    const tasksItem = page.getByTestId('attention-item-tasks_overdue');
    await expect(tasksItem).toContainText('2 tareas vencidas');
    await expect(tasksItem).toHaveAttribute('aria-expanded', 'false');
  });

  test('shows the positive empty radar when nothing needs attention', {
    tag: [...ADMIN_DASHBOARD_ATTENTION_RADAR, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — asserts the empty-radar state when the attention payload is empty)
    await mockDashboard(page, { ...summaryFixture, attention: [] });
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.waitForResponse((res) => res.url().includes('/api/panel/dashboard/'));

    await expect(page.getByTestId('attention-radar-empty')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Nada requiere tu atención. Todo al día.')).toBeVisible();
  });

  test('recovers from a failed load with the retry button', {
    tag: [...ADMIN_DASHBOARD_ERROR_RETRY, '@role:admin', '@outcome:failure', '@outcome:display'],
  }, async ({ page }) => {
    let calls = 0;
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'panel/dashboard/') {
        calls += 1;
        if (calls === 1) {
          return { status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'boom' }) };
        }
        return jsonResponse(summaryFixture);
      }
      return null;
    });
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });

    const errorState = page.getByTestId('dashboard-error');
    await expect(errorState).toBeVisible({ timeout: 10000 });
    await errorState.getByRole('button', { name: 'Reintentar' }).click();

    await expect(page.getByTestId('dashboard-pulse')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('dashboard-error')).not.toBeVisible();
  });

  test('the quick-create menu lists the four destinations', {
    tag: [...ADMIN_DASHBOARD_QUICK_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockDashboard(page, summaryFixture);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('dashboard-pulse')).toBeVisible({ timeout: 10000 });

    await page.getByRole('button', { name: 'Crear' }).click();

    const menu = page.getByRole('menu');
    await expect(menu.getByRole('menuitem')).toHaveCount(4);
    await expect(menu.getByRole('menuitem', { name: 'Propuesta' })).toHaveAttribute(
      'href', /\/panel\/proposals\/create/,
    );
    await expect(menu.getByRole('menuitem', { name: 'Documento' })).toHaveAttribute(
      'href', /\/panel\/documents/,
    );
    await expect(menu.getByRole('menuitem', { name: 'Tarea' })).toHaveAttribute(
      'href', /\/panel\/tasks/,
    );
    await expect(menu.getByRole('menuitem', { name: 'Gasto' })).toHaveAttribute(
      'href', /\/panel\/accounting\/expenses/,
    );
  });

  test('choosing Gasto navigates to the accounting expenses page', {
    tag: [...ADMIN_DASHBOARD_QUICK_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'panel/dashboard/') return jsonResponse(summaryFixture);
      if (apiPath === 'accounting/expenses/') {
        return jsonResponse({ results: [], meta: {} });
      }
      if (apiPath.startsWith('accounts/saved-filter-tabs')) {
        return { status: 200, contentType: 'application/json', body: '[]' };
      }
      return null;
    });
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('dashboard-pulse')).toBeVisible({ timeout: 10000 });

    await page.getByRole('button', { name: 'Crear' }).click();
    await page.getByRole('menuitem', { name: 'Gasto' }).click();

    await expect(page).toHaveURL(/\/panel\/accounting\/expenses/);
    await expect(
      page.getByRole('heading', { name: 'Gastos', exact: true }),
    ).toBeVisible({ timeout: 15_000 });
  });
});
