/**
 * E2E for the Historial strip: predefined tabs, own tabs, the URL, and the
 * two diagnosis actions on a row.
 *
 * FLOWS: admin-accounting-history-filters, admin-accounting-history-diagnosis
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_ACCOUNTING_HISTORY_DIAGNOSIS,
  ADMIN_ACCOUNTING_HISTORY_FILTERS,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const SENT_ROW = {
  id: 1,
  template_key: 'accounting_payment_calendar',
  template_label: 'Calendario de cobros y pagos',
  recipient: 'gustavo@projectapp.co',
  subject: '[Contabilidad] Cobros y pagos de hoy',
  status: 'sent',
  status_label: 'Enviado',
  error_message: '',
  origin_action: '',
  sent_at: '2026-07-02T13:30:00Z',
  targets: [
    {
      entity_type: 'hosting',
      entity_type_label: 'Hosting',
      object_id: 4,
      object_repr: 'Kore',
    },
  ],
  has_body: true,
  is_retryable: false,
  retry_blocked_reason: 'Este aviso resume varios registros del día en que salió.',
  retry_of: null,
};

const FAILED_ROW = {
  ...SENT_ROW,
  id: 2,
  template_key: 'accounting_change',
  template_label: 'Cambio contable',
  recipient: 'carlos18bp@gmail.com',
  subject: '[Contabilidad] Hosting eliminado: Kore',
  status: 'failed',
  status_label: 'Fallido',
  error_message: 'SMTP timeout',
  origin_action: 'deleted',
  has_body: false,
  is_retryable: true,
  retry_blocked_reason: '',
};

// A digest that failed: the case where the button exists but must refuse.
const FAILED_DIGEST = {
  ...SENT_ROW,
  id: 3,
  recipient: 'zoe@projectapp.co',
  status: 'failed',
  status_label: 'Fallido',
  error_message: 'SMTP timeout',
  has_body: false,
};

const SEEDED_TABS = [
  {
    id: 11,
    view: 'accounting_history_sends',
    name: 'Recordatorios de cobro',
    filters: { template_key: ['accounting_payment_calendar', 'collection_account_sent'] },
    base_filters: { template_key: ['accounting_payment_calendar', 'collection_account_sent'] },
    order: 0,
    is_seeded: true,
    is_hidden: false,
  },
  {
    id: 12,
    view: 'accounting_history_sends',
    name: 'Eliminaciones',
    filters: { origin_action: ['deleted'] },
    base_filters: { origin_action: ['deleted'] },
    order: 1,
    is_seeded: true,
    is_hidden: false,
  },
];

/**
 * Filters the fixture the way the real endpoint does, so a test can tell a
 * wired-up filter from one that only repaints the same rows.
 */
function filterRows(params) {
  let rows = [SENT_ROW, FAILED_ROW, FAILED_DIGEST];
  if (params.status) {
    const wanted = params.status.split(',');
    rows = rows.filter((row) => wanted.includes(row.status));
  }
  if (params.template_key) {
    const wanted = params.template_key.split(',');
    rows = rows.filter((row) => wanted.includes(row.template_key));
  }
  if (params.origin_action) {
    const wanted = params.origin_action.split(',');
    rows = rows.filter((row) => wanted.includes(row.origin_action));
  }
  if (params.entity_type) {
    rows = rows.filter((row) =>
      row.targets.some((t) => t.entity_type === params.entity_type));
  }
  if (params.object_id) {
    rows = rows.filter((row) =>
      row.targets.some((t) => String(t.object_id) === params.object_id));
  }
  if (params.subject) {
    rows = rows.filter((row) =>
      row.subject.toLowerCase().includes(params.subject.toLowerCase()));
  }
  return rows;
}

function buildHandler({ calls, savedTabs, retryStatus = 201 }) {
  const tabs = savedTabs ?? SEEDED_TABS;
  return async ({ route, apiPath, method }) => {
    const url = new URL(route.request().url());

    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { username: 'admin', is_staff: true, is_superuser: true },
        }),
      };
    }
    if (apiPath === 'accounting/email-log/' && method === 'GET') {
      const params = Object.fromEntries(url.searchParams.entries());
      calls.push({ apiPath, method, params });
      const rows = filterRows(params);
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: rows, count: rows.length, page: 1, num_pages: 1,
        }),
      };
    }
    if (apiPath === 'accounting/change-logs/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], count: 0, page: 1, num_pages: 1 }),
      };
    }
    if (apiPath === 'accounting/history/tab-counts/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      const counts = {};
      for (const spec of body.tabs) {
        const params = {};
        for (const [key, value] of Object.entries(spec.filters || {})) {
          params[key] = Array.isArray(value) ? value.join(',') : value;
        }
        counts[String(spec.id)] = body.scope === 'sends'
          ? filterRows(params).length
          : 0;
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ counts }),
      };
    }
    if (apiPath.startsWith('accounting/email-log/') && apiPath.endsWith('/body/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          subject: SENT_ROW.subject,
          recipient: SENT_ROW.recipient,
          sent_at: SENT_ROW.sent_at,
          html: '<p data-testid="body-marker">Cobros y pagos de hoy</p>',
          text: 'Cobros y pagos de hoy',
        }),
      };
    }
    if (apiPath.startsWith('accounting/email-log/') && apiPath.endsWith('/retry/')) {
      calls.push({ apiPath, method });
      if (retryStatus !== 201) {
        return {
          status: retryStatus,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'El reintento tampoco salió: SMTP down' }),
        };
      }
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...FAILED_ROW, id: 99, status: 'sent', retry_of: 2 }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(url.searchParams.get('view') === 'accounting_history_sends' ? tabs : []),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs') && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 55, order: 9, is_seeded: false, is_hidden: false, ...body,
          base_filters: body.filters,
        }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '{}' };
    }
    if (apiPath === 'proposals/client-profiles/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [{ id: 3, name: 'Kore SAS' }], meta: {} }),
      };
    }
    if (apiPath.startsWith('projects/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [{ id: 8, name: 'KORE' }],
          meta: { total: 1, active: 1, archived: 0, clients_without_projects: 0 },
        }),
      };
    }
    return null;
  };
}

test.describe('Admin Accounting History — filters and diagnosis', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the strip counts every tab, the empty one included', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_FILTERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the badges have to be right on arrival; interacting would test selection, which the next test covers)
    // quality: allow-deep-link (the send subtab is reached by URL by design — that is the shared-link contract this flow adds)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-1')).toBeVisible({ timeout: 25_000 });

    // Three rows, two of them failures, one born of a deletion. The counts
    // are asked of the server because there are no loaded rows to count.
    await expect(page.getByTestId('filter-tabs-count-all')).toHaveText('(3)');
    await expect(page.getByTestId('filter-tabs-count-failed')).toHaveText('(2)');
    await expect(page.getByTestId('filter-tabs-count-12')).toHaveText('(1)');
  });

  test('a tab that matches nothing shows the zero rather than no badge', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_FILTERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the honest (0) is what is being pinned, and it is only visible before anything is selected)
    // quality: allow-deep-link (the send subtab is reached by URL by design)
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      savedTabs: [{
        ...SEEDED_TABS[0],
        id: 21,
        name: 'Cuentas de cobro',
        filters: { template_key: ['collection_account_sent'] },
        base_filters: { template_key: ['collection_account_sent'] },
      }],
    }));

    await page.goto('/panel/accounting/history?tab=sends', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-1')).toBeVisible({ timeout: 25_000 });

    await expect(page.getByTestId('filter-tabs-count-21')).toHaveText('(0)');
  });

  test('a predefined tab filters the list and lands in the URL', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_FILTERS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-1')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('filter-tabs-tab-failed').click();

    await expect(page.getByTestId('email-log-row-2')).toBeVisible();
    await expect(page.getByTestId('email-log-row-1')).toHaveCount(0);
    await expect(page).toHaveURL(/status=failed/);
    await expect(page).toHaveURL(/sendsTab=failed/);
  });

  test('a shared link reopens the same query', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_FILTERS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (the link IS the interaction — opening a shared URL is the behaviour under test)
    // quality: allow-deep-link (the whole point: a bookmarked query has to reopen filtered)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends&status=failed', {
      waitUntil: 'domcontentloaded',
    });

    await expect(page.getByTestId('email-log-row-2')).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('email-log-row-1')).toHaveCount(0);
    // The filter reached the server, not just the controls.
    const listCalls = calls.filter((c) => c.apiPath === 'accounting/email-log/');
    expect(listCalls.at(-1).params.status).toBe('failed');
  });

  test('arriving from a record lands already narrowed to it', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_FILTERS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (arriving pre-filtered is the behaviour; the click that produces this URL lives in the hostings flow)
    // quality: allow-deep-link (this URL is exactly what the record's row action opens)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto(
      '/panel/accounting/history?tab=sends&entity_type=hosting&object_id=4',
      { waitUntil: 'domcontentloaded' },
    );

    await expect(page.getByTestId('email-log-row-1')).toBeVisible({ timeout: 25_000 });
    const listCalls = calls.filter((c) => c.apiPath === 'accounting/email-log/');
    expect(listCalls.at(-1).params).toMatchObject({
      entity_type: 'hosting', object_id: '4',
    });
  });

  test('clearing the filters deselects the tab', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_FILTERS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends&sendsTab=failed&status=failed', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-2')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('accounting-filter-reset').click();

    await expect(page.getByTestId('email-log-row-1')).toBeVisible();
    await expect(page).not.toHaveURL(/status=failed/);
  });

  test('the active filters can be saved as an own tab', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_FILTERS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends&status=failed', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-2')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('filter-tabs-create').click();
    await page.getByTestId('filter-tabs-input').fill('Lo que falló');
    await page.getByTestId('filter-tabs-confirm').click();

    await expect
      .poll(() => calls.filter((c) => c.method === 'POST'
        && c.apiPath.startsWith('accounts/saved-filter-tabs')).length)
      .toBeGreaterThan(0);
    const saved = calls.find((c) => c.method === 'POST'
      && c.apiPath.startsWith('accounts/saved-filter-tabs'));
    expect(saved.body).toMatchObject({
      view: 'accounting_history_sends', name: 'Lo que falló',
    });
    expect(saved.body.filters.status).toEqual(['failed']);
  });

  test('the row menu opens the message that was delivered', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_DIAGNOSIS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-1')).toBeVisible({ timeout: 25_000 });

    // The kebab leads the row; the message is an entry of its menu.
    await page.getByTestId('email-log-actions-1').click();
    await page.getByTestId('email-log-view-body-1').click();

    await expect(page.getByTestId('email-body-modal')).toBeVisible();
    const frame = page.frameLocator('[data-testid="email-body-frame"]');
    await expect(frame.getByTestId('body-marker')).toHaveText('Cobros y pagos de hoy');
  });

  test('a failed send can be retried from its own row', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_DIAGNOSIS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (landing on the failures is what the "Fallidos" tab produces; getting there is covered by the filters flow)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends&status=failed', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-2')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('email-log-actions-2').click();
    await page.getByTestId('email-log-retry-2').click();

    await expect
      .poll(() => calls.filter((c) => c.apiPath.endsWith('/retry/')).length)
      .toBe(1);
    // The retry targets that row, not the notice in general.
    expect(calls.find((c) => c.apiPath.endsWith('/retry/')).apiPath)
      .toBe('accounting/email-log/2/retry/');
    await expect(page.getByText(/Salió de nuevo a carlos18bp@gmail\.com/))
      .toBeVisible();
    // The list reloads so the new attempt is on screen with the original.
    await expect(page.getByTestId('email-log-row-2'))
      .toContainText('carlos18bp@gmail.com');
  });

  test('a retry that fails again says why', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_DIAGNOSIS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, retryStatus: 400 }));

    await page.goto('/panel/accounting/history?tab=sends&status=failed', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-2')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('email-log-actions-2').click();
    await page.getByTestId('email-log-retry-2').click();

    await expect(page.getByText('No se pudo reintentar el envío')).toBeVisible();
    await expect(page.getByText(/SMTP down/)).toBeVisible();
  });

  test('a failed digest shows the retry disabled, carrying its reason', {
    tag: [...ADMIN_ACCOUNTING_HISTORY_DIAGNOSIS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the send subtab is reached by URL by design)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));

    await page.goto('/panel/accounting/history?tab=sends', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.getByTestId('email-log-row-3')).toBeVisible({ timeout: 25_000 });

    // Disabled and explained rather than absent: a missing entry reads as
    // "this failure cannot be acted on" without saying why.
    await page.getByTestId('email-log-actions-3').click();
    const menu = page.getByTestId('email-log-actions-modal');
    const retry = menu.getByTestId('email-log-retry-3');
    await expect(retry).toBeDisabled();
    await expect(retry).toContainText('resume varios registros');
    await menu.getByRole('button', { name: 'Cerrar' }).click();
    await expect(menu).toHaveCount(0);

    // A send that worked offers no retry at all, only its message.
    await page.getByTestId('email-log-actions-1').click();
    await expect(page.getByTestId('email-log-view-body-1')).toBeVisible();
    await expect(page.getByTestId('email-log-retry-1')).toHaveCount(0);
  });
});
