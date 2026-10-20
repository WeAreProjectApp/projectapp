/**
 * Pocket detail and attribution E2E coverage.
 *
 * Bug coverage: the ledger could hide a movement's owner, while the detail
 * could render raw amounts/dates and lose an allocation, linked record, or
 * its retryable error state.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { ADMIN_ACCOUNTING_POCKET } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const POCKET_ROWS = [
  {
    id: 71,
    concept: 'Abono Kore fase 2',
    movement_date: '2026-10-07',
    direction: 'in',
    direction_label: 'Ingreso',
    amount: '176120.00',
    running_balance: '900000.00',
    is_auto_managed: true,
    linked_income_id: null,
    linked_expense_id: null,
    linked_ledger: 'company',
    allocations: [{ income_id: 501 }, { income_id: 502 }, { income_id: 503 }],
    notes: 'Abono recibido para las fases dos y tres de Kore.',
    created_at: '2026-10-07T10:00:00Z',
    updated_at: '2026-10-07T10:00:00Z',
  },
  {
    id: 72,
    concept: 'Retiro operativo Gustavo',
    movement_date: '2026-10-08',
    direction: 'out',
    direction_label: 'Egreso',
    amount: '90000.00',
    running_balance: '810000.00',
    is_auto_managed: true,
    linked_income_id: null,
    linked_expense_id: 801,
    linked_ledger: 'gustavo',
    notes: 'Pago personal registrado contra gasto.',
    created_at: '2026-10-08T10:00:00Z',
    updated_at: '2026-10-08T10:00:00Z',
  },
  {
    id: 73,
    concept: 'Retiro operativo Carlos',
    movement_date: '2026-10-09',
    direction: 'out',
    direction_label: 'Egreso',
    amount: '50000.00',
    running_balance: '760000.00',
    is_auto_managed: true,
    linked_income_id: null,
    linked_expense_id: 802,
    linked_ledger: 'carlos',
    notes: '',
    created_at: '2026-10-09T10:00:00Z',
    updated_at: '2026-10-09T10:00:00Z',
  },
  {
    id: 74,
    concept: 'Movimiento histórico sin espejo',
    movement_date: '2026-10-10',
    direction: 'out',
    direction_label: 'Egreso',
    amount: '10000.00',
    running_balance: '750000.00',
    is_auto_managed: false,
    linked_income_id: null,
    linked_expense_id: null,
    linked_ledger: null,
    notes: '',
    created_at: '2026-10-10T10:00:00Z',
    updated_at: '2026-10-10T10:00:00Z',
  },
];

const DETAILS = {
  71: {
    ...POCKET_ROWS[0],
    linked_record_detail: null,
    allocation_details: [
      { income_id: 501, expected_income_id: 501, concept: 'Kore · Entrega fase 2', amount: '100000.00', pending_amount: '0.00', is_credit: false },
      { income_id: 502, expected_income_id: 502, concept: 'Kore · Inicio fase 3', amount: '50000.00', pending_amount: '26120.00', is_credit: false },
      { income_id: 503, expected_income_id: null, concept: 'Saldo a favor Kore', amount: '26120.00', pending_amount: null, is_credit: true },
    ],
  },
  72: {
    ...POCKET_ROWS[1],
    linked_record_detail: {
      type: 'expense', id: 801, concept: 'Retiro operativo Gustavo', category_label: 'Personal',
    },
    allocation_details: [],
  },
  73: {
    ...POCKET_ROWS[2],
    linked_record_detail: {
      type: 'expense', id: 802, concept: 'Retiro operativo Carlos', category_label: 'Personal',
    },
    allocation_details: [],
  },
  74: { ...POCKET_ROWS[3], linked_record_detail: null, allocation_details: [] },
};

const HISTORY = {
  count: 1,
  num_pages: 1,
  results: [{
    id: 901, number: 2, action: 'updated', actor: 'Admin E2E',
    occurred_at: '2026-10-07T15:30:00Z', source: 'panel', complete: true,
    fields: [{ label: 'Valor' }],
  }],
  latest_change: { occurred_at: '2026-10-07T15:30:00Z', actor: 'Admin E2E' },
};

function json(body, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

function buildHandler({ detailFailures = 0, missing = false } = {}) {
  let remainingFailures = detailFailures;
  return async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'accounting/pocket/' && method === 'GET') return json({ results: POCKET_ROWS, meta: { balance: '750000.00' } });
    if (apiPath === 'accounting/pocket/71/' && method === 'GET') {
      if (missing) return json({ detail: 'Not found' }, 404);
      if (remainingFailures > 0) {
        remainingFailures -= 1;
        return json({ detail: 'Detail temporarily unavailable' }, 503);
      }
      return json(DETAILS[71]);
    }
    if (/^accounting\/pocket\/(72|73|74)\/$/.test(apiPath) && method === 'GET') {
      const id = Number(apiPath.match(/\d+/)[0]);
      return json(DETAILS[id]);
    }
    if (apiPath === 'entity-history/pocket/71/' && method === 'GET') return json(HISTORY);
    if (apiPath === 'accounting/incomes/' && method === 'GET') return json({
      results: [{ id: 501, concept: 'Kore · Entrega fase 2', expected_amount: '100000.00', pending_amount: '0.00' }],
      meta: { expected_total: '100000.00', liquid_total: '100000.00' },
    });
    if (apiPath === 'accounting/incomes/501/detail/' && method === 'GET') return json({
      income: {
        id: 501, concept: 'Kore · Entrega fase 2', kind: 'expected', ledger: 'company',
        total_amount: '100000.00', paid_amount: '100000.00', pending_amount: '0.00',
        gustavo_amount: '0.00', carlos_amount: '0.00', company_amount: '100000.00', notes: '',
      },
      liquid: [], collection_account: null,
    });
    if (apiPath === 'accounting/expenses/' && method === 'GET') return json({
      results: [], meta: { year_total: '0.00', current_month_total: '0.00', deductions_total: '0.00', business_total: '0.00', personal_total: '0.00' },
    });
    if (apiPath === 'accounting/expenses/801/' && method === 'GET') return json({
      id: 801, concept: 'Retiro operativo Gustavo', period_date: '2026-10-08', category_label: 'Personal', total_amount: '90000.00', notes: '',
    });
    return null;
  };
}

async function prepare(page, options) {
  await setAuthLocalStorage(page, {
    token: 'pocket-detail-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockApi(page, buildHandler(options));
}

async function openPocketFromSubnav(page) {
  await page.goto('/es-co/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < 1024) {
    await page.getByTestId('accounting-subnav-select').selectOption('pocket');
  } else {
    await page.getByTestId('accounting-subnav-pocket').click();
  }
  await expect(page.getByRole('heading', { name: 'Bolsillo ProjectApp', exact: true })).toHaveText('Bolsillo ProjectApp');
}

async function openDetail(page, id) {
  const link = page.getByRole('link', { name: DETAILS[id].concept, exact: true });
  await expect(link).toHaveText(DETAILS[id].concept);
  await link.click();
  await expect(page).toHaveURL(new RegExp(`movement=${id}`));
  await expect(page.getByTestId('pocket-detail-modal')).toBeVisible();
}

test.describe('admin pocket ownership and detail', () => {
  test('renders the owner of every movement in the ledger', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated setup starts in Recurring; Pocket is reached through accounting subnavigation)
    await prepare(page);
    await openPocketFromSubnav(page);

    await expect(page.getByRole('columnheader', { name: 'Pertenece a' })).toHaveText('Pertenece a');
    await expect(page.getByRole('row', { name: /Abono Kore fase 2/ })).toContainText('Empresa');
    await expect(page.getByRole('row', { name: /Retiro operativo Gustavo/ })).toContainText('Gustavo');
    await expect(page.getByRole('row', { name: /Retiro operativo Carlos/ })).toContainText('Carlos');
    await expect(page.getByRole('row', { name: /Movimiento histórico sin espejo/ })).toContainText('Sin vincular');
  });

  test('renders a pocket detail with ledger-format values', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated setup starts in Recurring; Pocket is reached through accounting subnavigation)
    await prepare(page);
    await openPocketFromSubnav(page);

    await openDetail(page, 71);
    const modal = page.getByTestId('pocket-detail-modal');
    await expect(modal.getByTestId('pocket-detail-amount')).toHaveText('$176.120');
    await expect(modal).toContainText('Mié, 7 oct 2026');
    await expect(modal).toContainText('Ingreso');
    await expect(modal.getByTestId('pocket-detail-balance')).toHaveText('$900.000');
    await expect(modal.getByTestId('pocket-detail-attribution')).toHaveText('Empresa');
    await expect(modal.getByTestId('pocket-detail-notes')).toHaveText('Abono recibido para las fases dos y tres de Kore.');
  });

  test('renders each allocation with its current balance', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated setup starts in Recurring; Pocket is reached through accounting subnavigation)
    await prepare(page);
    await openPocketFromSubnav(page);
    await openDetail(page, 71);
    const modal = page.getByTestId('pocket-detail-modal');
    await expect(modal.getByTestId('pocket-allocation-detail-row')).toHaveCount(3);
    await expect(
      modal.getByTestId('pocket-allocation-detail-row').filter({ hasText: 'Kore · Inicio fase 3' })
        .getByTestId('pocket-allocation-pending'),
    ).toHaveText('$26.120');
    await expect(modal.getByTestId('pocket-allocation-detail-total')).toHaveText('$176.120');
    await expect(modal).toContainText('Saldo a favor Kore');
  });

  test('retains a linked expense detail through browser navigation', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await prepare(page);
    await openPocketFromSubnav(page);
    await openDetail(page, 72);
    await page.reload({ waitUntil: 'domcontentloaded' });

    const modal = page.getByTestId('pocket-detail-modal');
    await expect(modal.getByTestId('pocket-detail-linked-record')).toHaveText('Retiro operativo Gustavo');
    await expect(modal).toContainText('Personal');
    await modal.getByTestId('pocket-detail-linked-record').click();
    await expect(page).toHaveURL(/\/panel\/accounting\/expenses\?expense=801/);
    await expect(page.getByRole('heading', { name: 'Gastos', exact: true })).toHaveText('Gastos');
    await expect(page.getByTestId('history-record-modal')).toContainText('Retiro operativo Gustavo');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('history-record-modal')).toContainText('Retiro operativo Gustavo');
    await page.goBack();
    await expect(page).toHaveURL(/\/panel\/accounting\/pocket\?movement=72/);
    await expect(page.getByTestId('pocket-detail-modal')).toBeVisible();
  });

  test('opens an allocated income as an addressable detail', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await prepare(page);
    await openPocketFromSubnav(page);
    await openDetail(page, 71);

    await page.getByRole('link', { name: 'Kore · Entrega fase 2', exact: true }).click();
    await expect(page).toHaveURL(/\/panel\/accounting\/incomes\?income=501/);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Ingresos', exact: true })).toHaveText('Ingresos');
    await expect(page.getByTestId('income-detail-modal')).toContainText('Kore · Entrega fase 2');
  });

  test('retries a failed detail read instead of leaving the user in a blank modal', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await prepare(page, { detailFailures: 1 });
    await openPocketFromSubnav(page);
    await page.getByTestId('pocket-open-71').click();

    const modal = page.getByTestId('pocket-detail-modal');
    await expect(modal.getByText('No se pudo cargar el movimiento.', { exact: true })).toHaveText('No se pudo cargar el movimiento.');
    await modal.getByRole('button', { name: 'Reintentar' }).click();
    await expect(modal.getByTestId('pocket-detail-amount')).toHaveText('$176.120');
  });

  test('explains when a requested movement no longer exists without offering a futile retry', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await prepare(page, { missing: true });
    await openPocketFromSubnav(page);
    await page.getByTestId('pocket-open-71').click();

    const modal = page.getByTestId('pocket-detail-modal');
    await expect(modal.getByText('Este movimiento ya no existe.', { exact: true })).toHaveText('Este movimiento ya no existe.');
    await expect(modal.getByRole('button', { name: 'Reintentar' })).toHaveCount(0);
  });

  test('keeps the movement history available from the compact detail', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated setup starts in Recurring; Pocket is reached through accounting subnavigation)
    await prepare(page);
    await openPocketFromSubnav(page);
    await page.getByTestId('pocket-actions-71').click();
    await page.getByTestId('pocket-action-history-71').click();

    await expect(page.getByTestId('pocket-detail-modal')).toContainText('Abono Kore fase 2');
    await page.getByTestId('entity-history-tabs').getByRole('tab', { name: 'Historial', exact: true }).click();
    await expect(page.getByTestId('history-entry-901')).toContainText('Valor');
  });
});

for (const [profile, expectedOwner] of [
  ['compact', 'Empresa'], ['portrait', 'Empresa'], ['landscape', 'Empresa'], ['desktop', 'Empresa'], ['wide', 'Empresa'],
]) {
  test.describe(`pocket detail at ${profile}`, () => {
    test.use(viewportUse(profile));

    // quality: allow-duplicate (per-viewport contract: admin-accounting-pocket detail at each reference width)
    test('preserves compact detail geometry at the reference width', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display', `@viewport:${profile}`],
    }, async ({ page }) => {
      // quality: allow-deep-link (authenticated setup starts in Recurring; Pocket is reached through accounting subnavigation)
      await prepare(page);
      await openPocketFromSubnav(page);
      await openDetail(page, 71);

      const modal = page.getByTestId('pocket-detail-modal');
      await expect(modal.getByTestId('pocket-detail-attribution')).toHaveText(expectedOwner);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);
      // quality: allow-fragile-selector (BaseModal exposes data-modal-kind as its stable geometry hook)
      const panel = page.getByRole('dialog').locator('[data-modal-kind="detail-compact"]');
      const box = await panel.boundingBox();
      expect(box.width).toBeLessThanOrEqual(Math.min(page.viewportSize().width, 768) + 0.5);
    });
  });
}
