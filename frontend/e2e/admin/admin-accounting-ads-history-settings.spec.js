/**
 * E2E tests for the ads log, audit history and notification settings.
 *
 * FLOWS: admin-accounting-ads, admin-accounting-history,
 *        admin-accounting-settings
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { chooseRowAction, openRowMenu } from '../helpers/row-actions.js';
import {
  ADMIN_ACCOUNTING_ADS,
  ADMIN_ACCOUNTING_HISTORY,
  ADMIN_ACCOUNTING_SETTINGS,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const ADS_ROWS = [
  {
    id: 1,
    spend_date: '2026-01-17',
    platform: 'facebook',
    platform_label: 'Facebook Ads',
    origin_card: 'T.C 0655',
    amount: '146103.00',
    accumulated: '146103.00',
    notes: '',
    created_at: '2026-01-17T10:00:00Z',
    updated_at: '2026-01-17T10:00:00Z',
  },
  {
    id: 2,
    spend_date: '2026-01-25',
    platform: 'facebook',
    platform_label: 'Facebook Ads',
    origin_card: 'T.C 0656',
    amount: '143820.00',
    accumulated: '289923.00',
    notes: '',
    created_at: '2026-01-25T10:00:00Z',
    updated_at: '2026-01-25T10:00:00Z',
  },
];

const CHANGELOG = {
  results: [
    {
      id: 1,
      entity_type: 'income',
      entity_type_label: 'Ingreso',
      object_id: 5,
      object_repr: 'Kore - Inicio 40%',
      action: 'updated',
      action_label: 'Actualizado',
      changes: [
        {
          field: 'total_amount',
          label: 'Monto total',
          old: '1000000.00',
          new: '1160000.00',
        },
      ],
      actor: 1,
      actor_username: 'gustavo',
      created_at: '2026-07-01T15:30:00Z',
    },
  ],
  count: 25,
  page: 1,
  num_pages: 2,
};

const EMAIL_LOG = {
  results: [
    {
      id: 1,
      template_key: 'accounting_payment_calendar',
      template_label: 'Calendario de cobros y pagos',
      recipient: 'gustavo@projectapp.co',
      subject: '[Contabilidad] Cobros y pagos de hoy',
      status: 'sent',
      status_label: 'Enviado',
      error_message: '',
      sent_at: '2026-07-02T13:30:00Z',
    },
    {
      id: 2,
      template_key: 'payment_status_team',
      template_label: 'Pago de hosting',
      recipient: 'carlos18bp@gmail.com',
      subject: 'Pago aprobado · Mimitos · $900.000 COP',
      status: 'failed',
      status_label: 'Fallido',
      error_message: 'SMTP timeout',
      sent_at: '2026-07-02T14:00:00Z',
    },
  ],
  count: 30,
  page: 1,
  num_pages: 2,
};

function recipientRow(overrides = {}) {
  return {
    id: 1,
    email: 'gustavo@projectapp.co',
    is_active: true,
    notes: '',
    created_at: '2026-07-01T10:00:00Z',
    updated_at: '2026-07-01T10:00:00Z',
    ...overrides,
  };
}

/**
 * @param {object} options
 * @param {Array} options.calls        collected requests, for payload assertions
 * @param {Array} [options.recipients] rows served by the recipients list
 * @param {object} [options.createError] serializer error the create call returns
 * @param {object} [options.adsUpdateError] serializer error the ads edit returns
 */
function buildHandler({ calls, recipients, createError, adsUpdateError }) {
  const recipientRows = recipients ?? [recipientRow()];
  return async ({ route, apiPath, method }) => {
    const url = new URL(route.request().url());
    if (apiPath === 'accounting/notification-recipients/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: recipientRows, meta: {} }),
      };
    }
    if (apiPath === 'accounting/notification-recipients/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (createError) {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify(createError),
        };
      }
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(recipientRow({ id: 99, ...body })),
      };
    }
    if (apiPath.startsWith('accounting/notification-recipients/') && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...recipientRows[0], ...body }),
      };
    }
    if (apiPath.startsWith('accounting/notification-recipients/') && method === 'DELETE') {
      calls.push({ apiPath, method });
      return { status: 204, contentType: 'application/json', body: '' };
    }
    if (apiPath === 'accounting/email-log/' && method === 'GET') {
      const params = Object.fromEntries(url.searchParams.entries());
      calls.push({ apiPath, method, params });
      // Filtering server-side, like the real endpoint, so a test can tell a
      // wired-up filter from one that only repaints the same rows.
      const results = params.recipient
        ? EMAIL_LOG.results.filter((row) => row.recipient.includes(params.recipient))
        : EMAIL_LOG.results;
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...EMAIL_LOG,
          results,
          count: params.recipient ? results.length : EMAIL_LOG.count,
          num_pages: params.recipient ? 1 : EMAIL_LOG.num_pages,
        }),
      };
    }
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { username: 'admin', is_staff: true, is_superuser: true },
        }),
      };
    }
    if (apiPath === 'accounting/ads/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: ADS_ROWS, meta: {} }),
      };
    }
    if (apiPath === 'accounting/ads/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...ADS_ROWS[0], id: 99, ...body }),
      };
    }
    if (/^accounting\/ads\/\d+\/update\/$/.test(apiPath) && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (adsUpdateError) {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify(adsUpdateError),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...ADS_ROWS[0], ...body }),
      };
    }
    if (apiPath === 'accounting/change-logs/' && method === 'GET') {
      calls.push({
        apiPath,
        method,
        params: Object.fromEntries(url.searchParams.entries()),
      });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(CHANGELOG),
      };
    }
    if (apiPath === 'accounting/settings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          notifications_enabled: true,
          card_reminder_enabled: true,
          hosting_expiry_reminder_enabled: true,
          payment_calendar_enabled: true,
          overdue_reminder_frequency: 'biweekly',
          usd_exchange_rate: '4000.00',
          income_default_view_mode: 'grouped',
          collection_accounts_view_mode: 'grouped',
          collection_accounts_group_by: 'client',
          updated_at: '2026-07-01T00:00:00Z',
        }),
      };
    }
    if (apiPath === 'accounting/settings/update/' && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...body,
          notifications_enabled: body.notifications_enabled ?? true,
          updated_at: '2026-07-02T00:00:00Z',
        }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

test.describe('Admin Accounting Ads, History & Settings', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('ads list shows the accumulated column', {
    tag: [...ADMIN_ACCOUNTING_ADS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — ads list renders rows with the accumulated column; the create interaction is covered below)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/ads', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Ads', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(
      page.getByTestId('accounting-row-2').getByText('$289.923').filter({ visible: true }),
    ).toBeVisible();
  });

  test('creates an ads spend through the modal', {
    tag: [...ADMIN_ACCOUNTING_ADS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/ads', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Ads', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('ads-new-button').click();
    await expect(
      page.getByRole('heading', { name: 'Nuevo gasto en Ads' }),
    ).toBeVisible();
    // quality: allow-fragile-selector (the ads modal's inputs have no testids; positional/attribute select is intentional)
    await page.locator('form input[type="date"]').fill('2026-07-01');
    // quality: allow-fragile-selector (numeric input has no testid; positional select is intentional)
    await page.locator('form input[inputmode="numeric"]').first().fill('120000');
    await page.getByTestId('ad-spend-form-submit').click();

    await expect(page.getByText('Gasto en Ads creado')).toContainText('Gasto en Ads creado');
    const create = calls.find((call) => call.method === 'POST');
    expect(create.body.spend_date).toBe('2026-07-01');
  });

  // Bug caught: Ads kept a trailing «Acciones» column with a loose history
  // button beside the edit and delete icons.
  test('an ads spend is edited from its row menu', {
    tag: [...ADMIN_ACCOUNTING_ADS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the edit starts at
    // the row's kebab, which IS driven below)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/ads', { waitUntil: 'domcontentloaded' });
    const row = page.getByTestId('accounting-row-1');
    await expect(row).toBeVisible({ timeout: 25_000 });
    await expect(row.getByTestId('accounting-actions-cell-1').getByRole('button')).toHaveCount(1);

    await openRowMenu(page, { kebab: 'ads-actions-1', menu: 'ads-actions-modal' });
    await expect(page.getByTestId('ads-action-history-1')).toBeVisible();
    await page.getByTestId('ads-action-edit-1').click();
    await expect(page.getByRole('heading', { name: 'Editar Gasto en Ads' })).toBeVisible();
    await page.getByTestId('ad-spend-form-submit').click();

    await expect(page.getByText('Gasto en Ads actualizado')).toBeVisible();
    const update = calls.find((call) => call.method === 'PATCH');
    expect(update.apiPath).toBe('accounting/ads/1/update/');
  });

  test('a rejected ads edit keeps the form open and says why', {
    tag: [...ADMIN_ACCOUNTING_ADS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the edit starts at
    // the row's kebab, which IS driven below)
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      adsUpdateError: { amount: ['El valor debe ser mayor a cero.'] },
    }));
    await page.goto('/panel/accounting/ads', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });

    await chooseRowAction(page, {
      kebab: 'ads-actions-1',
      menu: 'ads-actions-modal',
      action: 'ads-action-edit-1',
    });
    await page.getByTestId('ad-spend-form-submit').click();

    await expect(page.getByText('No se pudo actualizar el gasto en Ads')).toBeVisible();
    // Nothing was lost: the form is still there to correct and retry.
    await expect(page.getByRole('heading', { name: 'Editar Gasto en Ads' })).toBeVisible();
    expect(calls.filter((call) => call.method === 'PATCH')).toHaveLength(1);
  });

  test('history renders audit rows and expands the field diff', {
    tag: [...ADMIN_ACCOUNTING_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/history', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Historial', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('changelog-row-1')).toBeVisible();

    await page.getByTestId('changelog-row-1').click();
    await expect(page.getByTestId('changelog-detail-1')).toBeVisible();
    await expect(page.getByText('Monto total')).toBeVisible();
    await expect(page.getByText('1000000.00')).toBeVisible();
    await expect(page.getByText('1160000.00')).toBeVisible();
  });

  test('history entity filter refires the fetch with entity_type', {
    tag: [...ADMIN_ACCOUNTING_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-render-only (contract test — asserts the entity filter refires the fetch with entity_type=expense; the mock returns a fixed dataset so there is no distinct rendered result to assert)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/history', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('changelog-row-1')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('history-filter-toggle').click();
    await page.getByRole('button', { name: 'Entidad' }).click();
    await page.getByRole('checkbox', { name: 'Gasto' }).check();

    await expect
      .poll(() => calls.some((call) => call.params?.entity_type === 'expense'))
      .toBe(true);
  });

  test('history shows the server-side pagination summary', {
    tag: [...ADMIN_ACCOUNTING_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — history renders the server-side pagination summary)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/history', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('history-page-info')).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('history-page-info')).toContainText('Página 1 de 2');
    await expect(page.getByTestId('history-page-info')).toContainText('25 cambios');
  });

  test('the recipients list shows each address with its state and signup date', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display flow — the list is what the
    // operator reads to know who is registered; state and fecha de alta are
    // asserted by concrete content, and every action on it has its own test)
    // quality: allow-deep-link (/panel/accounting/settings is a subnav tab of
    // the accounting module, reached the same way from every other tab)
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      recipients: [
        recipientRow(),
        recipientRow({ id: 2, email: 'carlos18bp@gmail.com', is_active: false }),
      ],
    }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Configuración', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await expect(page.getByTestId('recipients-email-1')).toHaveText('gustavo@projectapp.co');
    await expect(page.getByTestId('recipients-state-1')).toHaveText('Activo');
    await expect(page.getByTestId('recipients-email-2')).toHaveText('carlos18bp@gmail.com');
    await expect(page.getByTestId('recipients-state-2')).toHaveText('Pausado');
    await expect(page.getByTestId('recipients-row-1')).toContainText('Alta');
  });

  test('adding a recipient posts it and clears the field', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recipients-new-email')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recipients-new-email').fill('carlos18bp@gmail.com');
    await page.getByTestId('recipients-add').click();

    await expect(page.getByText('Destinatario agregado.')).toBeVisible();
    await expect(page.getByTestId('recipients-new-email')).toHaveValue('');
    const post = calls.find((call) => call.method === 'POST');
    expect(post.body).toEqual({ email: 'carlos18bp@gmail.com' });
  });

  test('a duplicate address is rejected inline and nothing is added', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      createError: { email: ['Ese correo ya está en la lista.'] },
    }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recipients-new-email')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recipients-new-email').fill('GUSTAVO@projectapp.co');
    await page.getByTestId('recipients-add').click();

    await expect(page.getByText('Ese correo ya está en la lista.')).toBeVisible();
    // The typed value survives so it can be corrected.
    await expect(page.getByTestId('recipients-new-email')).toHaveValue('GUSTAVO@projectapp.co');
  });

  test('pausing a recipient persists it without removing the row', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recipients-toggle-1')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recipients-toggle-1').click();

    await expect(page.getByText('no recibirá avisos')).toBeVisible();
    await expect(page.getByTestId('recipients-row-1')).toBeVisible();
    const patch = calls.find(
      (call) => call.apiPath.startsWith('accounting/notification-recipients/')
        && call.method === 'PATCH',
    );
    expect(patch.body).toEqual({ is_active: false });
  });

  test('removing a recipient asks for confirmation first', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recipients-actions-1')).toBeVisible({ timeout: 25_000 });

    // Quitar lives in the row's menu, after the recipient's history.
    await openRowMenu(page, { kebab: 'recipients-actions-1', menu: 'recipients-actions-modal' });
    await expect(page.getByTestId('recipients-action-history-1')).toBeVisible();
    await page.getByTestId('recipients-action-remove-1').click();

    // The confirmation spells out what stops arriving before anything is lost.
    await expect(page.getByText('Dejará de recibir los avisos')).toBeVisible();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false);

    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Destinatario eliminado.')).toBeVisible();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(true);
  });

  test('pausing the last active recipient warns nobody gets notified', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recipients-toggle-1')).toBeVisible({ timeout: 25_000 });
    // Nothing to warn about yet: this one is still active.
    await expect(page.getByTestId('recipients-none-active-warning')).toHaveCount(0);

    await page.getByTestId('recipients-toggle-1').click();

    await expect(page.getByTestId('recipients-none-active-warning')).toContainText(
      'la automatización está apagada de hecho',
    );
  });

  test('turning the master switch off warns nothing goes out at all', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('settings-notifications-toggle')).toBeVisible({
      timeout: 25_000,
    });

    await page.getByTestId('settings-notifications-toggle').click();

    await expect(page.getByTestId('recipients-master-off-warning')).toBeVisible();
    // The active recipient stops mattering: the master warning replaces it.
    await expect(page.getByTestId('recipients-none-active-warning')).toHaveCount(0);
  });

  test('settings persists the card-debt reminder toggle', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByText('Recordatorio de deuda de tarjetas'),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('settings-card-reminder-toggle').click();
    await page.getByTestId('settings-save-button').click();

    await expect(page.getByText('Configuración guardada')).toBeVisible();
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch.body.card_reminder_enabled).toBe(false);
  });

  test('settings switches the overdue reminder to weekly and saves it', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Calendario de cobros y pagos' }),
    ).toBeVisible({ timeout: 25_000 });
    // The mock serves 'biweekly', so the segmented control lands there.
    await expect(
      page.getByTestId('settings-overdue-frequency').getByRole('tab', { name: 'Quincenal' }),
    ).toHaveAttribute('aria-selected', 'true');

    await page
      .getByTestId('settings-overdue-frequency')
      .getByRole('tab', { name: 'Semanal' })
      .click();
    await page.getByTestId('settings-save-button').click();

    await expect(page.getByText('Configuración guardada')).toBeVisible();
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch.body.overdue_reminder_frequency).toBe('weekly');
  });

  test('turning the calendar off locks the frequency but keeps its value', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });

    await expect(
      page.getByRole('heading', { name: 'Calendario de cobros y pagos' }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('settings-payment-calendar-toggle').click();

    // Disabled rather than hidden: the operator has to be able to see what
    // will happen when the calendar is switched back on.
    await expect(
      page.getByTestId('settings-overdue-frequency').getByRole('tab', { name: 'Semanal' }),
    ).toBeDisabled();
    await expect(
      page.getByText('El calendario está apagado'),
    ).toBeVisible();

    await page.getByTestId('settings-save-button').click();
    await expect(page.getByText('Configuración guardada')).toBeVisible();
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch.body.payment_calendar_enabled).toBe(false);
    expect(patch.body.overdue_reminder_frequency).toBe('biweekly');
  });

  test('settings persists the default incomes view mode', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Vista de ingresos')).toBeVisible({ timeout: 25_000 });
    // The mock serves 'grouped', so the segmented control lands there.
    await expect(
      page.getByTestId('settings-income-view-mode').getByRole('tab', { name: 'Agrupado' }),
    ).toHaveAttribute('aria-selected', 'true');

    await page.getByTestId('settings-income-view-mode')
      .getByRole('tab', { name: 'Clásico' }).click();
    await page.getByTestId('settings-save-button').click();

    await expect(page.getByText('Configuración guardada')).toBeVisible();
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch.body.income_default_view_mode).toBe('classic');
  });

  test('settings persists collection account view preferences', {
    tag: [...ADMIN_ACCOUNTING_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/settings', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Vista de cuentas de cobro')).toBeVisible({ timeout: 25_000 });
    await expect(
      page.getByTestId('settings-collections-view-mode')
        .getByRole('tab', { name: 'Agrupado' }),
    ).toHaveAttribute('aria-selected', 'true');
    await page.getByTestId('settings-collections-view-mode')
      .getByRole('tab', { name: 'Clásico' }).click();
    await page.getByTestId('settings-collections-group-by')
      .getByRole('tab', { name: 'Proyecto' }).click();
    await page.getByTestId('settings-save-button').click();

    await expect(page.getByText('Configuración guardada')).toBeVisible();
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch.body.collection_accounts_view_mode).toBe('classic');
    expect(patch.body.collection_accounts_group_by).toBe('project');
  });

  test('the sends tab lists who each notice reached, with its state', {
    tag: [...ADMIN_ACCOUNTING_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/accounting/history is a subnav tab of
    // the accounting module, reached the same way from every other tab)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/history', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('history-tab-sends')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('history-tab-sends').click();

    await expect(page.getByTestId('email-log-row-1')).toContainText('gustavo@projectapp.co');
    await expect(page.getByTestId('email-log-row-1')).toContainText(
      'Calendario de cobros y pagos',
    );
    await expect(page.getByTestId('email-log-row-2')).toContainText('carlos18bp@gmail.com');
    await expect(page.getByTestId('email-log-row-2')).toContainText('Fallido');
    await expect(page.getByTestId('history-page-info')).toContainText('30 envíos');
  });

  test('a failed send reveals the reason it did not arrive', {
    tag: [...ADMIN_ACCOUNTING_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/accounting/history is a subnav tab of
    // the accounting module, reached the same way from every other tab)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/history', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('history-tab-sends')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('history-tab-sends').click();
    await expect(page.getByTestId('email-log-row-2')).toBeVisible();
    await page.getByTestId('email-log-row-2').click();

    await expect(page.getByTestId('email-log-detail-2')).toContainText('SMTP timeout');
  });

  test('the sends tab filters by recipient', {
    tag: [...ADMIN_ACCOUNTING_HISTORY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/history', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('history-tab-sends')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('history-tab-sends').click();
    await expect(page.getByTestId('email-log-row-1')).toBeVisible();
    await page.getByTestId('history-filter-toggle').click();
    await page.getByTestId('accounting-filter-text-recipient').fill('carlos18bp');

    // The filter goes to the server, so the other recipient's row is gone.
    await expect(page.getByTestId('email-log-row-2')).toContainText('carlos18bp@gmail.com');
    await expect(page.getByTestId('email-log-row-1')).toHaveCount(0);
    await expect(page.getByTestId('history-page-info')).toContainText('1 envío');
  });
});
