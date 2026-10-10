/**
 * E2E tests for the bulk abono flow on the incomes subview.
 *
 * FLOWS: admin-accounting-income-bulk-settle
 * Covers: registering one payment distributed across the selected expected
 *         incomes — the partial single case, the exact multi cover riding
 *         the prefill, the Kore case (two full + one partial through ONE
 *         POST), the excess turning into saldo a favor, the mixed-client
 *         excess block, the backend rejection keeping the modal open, and
 *         the reparto readable from the pocket movement.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { bulkAction } from '../helpers/bulk-actions.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';
import {
  ADMIN_ACCOUNTING_INCOME_BULK_SETTLE,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

function incomeRow(overrides = {}) {
  return {
    id: 1,
    concept: 'Kore - Fase 2 Entrega',
    kind: 'expected',
    kind_label: 'Esperado',
    period: '2026-05',
    period_label: 'Mayo 2026',
    period_date: '2026-05-01',
    destination: 'partners',
    destination_label: 'Socios',
    ledger: 'company',
    ledger_label: 'Empresa',
    total_amount: '1000000.00',
    gustavo_amount: '500000.00',
    carlos_amount: '500000.00',
    company_amount: '0.00',
    expected_income: null,
    pocket_movement: null,
    paid_amount: '0.00',
    pending_amount: '1000000.00',
    payment_status: 'pending',
    payment_status_label: 'Pendiente',
    client: null,
    client_name: null,
    origin: '',
    origin_label: '',
    notes: '',
    created_at: '2026-05-01T10:00:00Z',
    updated_at: '2026-05-01T10:00:00Z',
    ...overrides,
  };
}

const STATUS_LABELS = { paid: 'Pagado', partial: 'Parcial', pending: 'Pendiente' };

/** Mirror of the backend arithmetic, so the refetched list shows the new states. */
function applySettle(rows, body) {
  for (const entry of body.allocations) {
    const row = rows.find((candidate) => candidate.id === entry.income_id);
    const paid = Number(row.paid_amount) + entry.amount;
    const pending = Number(row.total_amount) - paid;
    row.paid_amount = paid.toFixed(2);
    row.pending_amount = pending.toFixed(2);
    row.payment_status = pending <= 0 ? 'paid' : 'partial';
    row.payment_status_label = STATUS_LABELS[row.payment_status];
  }
  const allocated = body.allocations.reduce((acc, entry) => acc + entry.amount, 0);
  const excess = body.total_amount - allocated;
  if (excess > 0) {
    const owner = rows.find((row) => row.client_name)?.client_name;
    rows.push(incomeRow({
      id: 900,
      concept: owner ? `Saldo a favor ${owner}` : 'Saldo a favor',
      kind: 'liquid',
      kind_label: 'Líquido',
      destination: 'pocket',
      destination_label: 'Bolsillo ProjectApp',
      total_amount: excess.toFixed(2),
      paid_amount: null,
      pending_amount: null,
      payment_status: null,
      payment_status_label: null,
      pocket_movement: 70,
    }));
  }
  return rows.filter((row) => row.kind === 'expected' || row.id === 900);
}

function buildHandler({
  rows, calls, settleStatus = 201, requireCollectionAccountOnPaid = false,
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
        body: JSON.stringify({ income_default_view_mode: 'classic' }),
      };
    }
    if (apiPath === 'accounting/incomes/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: rows, meta: {} }),
      };
    }
    if (apiPath === 'accounting/incomes/bulk-settle/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ method, apiPath, body });
      if (settleStatus !== 201) {
        return {
          status: settleStatus,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'El valor supera lo pendiente de la selección.',
          }),
        };
      }
      const results = applySettle(rows, body);
      if (requireCollectionAccountOnPaid) {
        rows.filter((row) => row.payment_status === 'paid').forEach((row) => {
          row.requires_collection_account = true;
        });
      }
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          updated: body.allocations.length,
          results,
          movement: { id: 70, amount: String(body.total_amount) },
        }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      };
    }
    return null;
  };
}

async function gotoIncomes(page, { hydrationTimeout } = {}) {
  await page.goto('/en-us/panel/accounting/incomes?accounting_incomeTab=all', {
    waitUntil: 'domcontentloaded',
  });
  await waitForNuxtApp(page, hydrationTimeout ? { timeout: hydrationTimeout } : undefined);
  await expect(
    page.getByRole('heading', { name: 'Ingresos', exact: true }),
  ).toBeVisible({ timeout: 15_000 });
}

async function openSettleModal(page, ids) {
  for (const id of ids) {
    await page.getByTestId(`accounting-select-${id}`).check();
  }
  await bulkAction(page, 'incomes', 'Liquidar');
  await expect(page.getByTestId('income-bulk-settle-modal')).toBeVisible();
}

test.describe('Admin Accounting Income Bulk Settle', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('an abono below the pending leaves the income Parcial with the missing amount', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow({ id: 11 })], calls }));
    await gotoIncomes(page);

    await openSettleModal(page, [11]);
    await page.getByTestId('income-bulk-settle-total').fill('400000');
    await page.getByTestId('income-bulk-settle-submit').click();

    await expect(page.getByTestId('accounting-row-11')).toContainText('Parcial');
    await expect(page.getByTestId('accounting-row-11')).toContainText('faltan');
    await expect(page.getByTestId('accounting-row-11')).toContainText('600.000');
    const settle = calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/');
    expect(settle.body.total_amount).toBe(400000);
    expect(settle.body.allocations).toEqual([{ income_id: 11, amount: 400000 }]);
    await expect(page.getByTestId('incomes-bulk-bar')).toHaveCount(0);
  });

  // Bug caught: accounts that were not emitted used to hide a received payment
  // and make the selected balance look like the original invoice value.
  test('a client row without an emitted account shows both totals and accepts its abono', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({
          id: 11, client: 5, client_name: 'Kore SAS', has_collection_account: true,
          collection_account_status: 'draft', collection_account_number: 'CC-DRAFT-001',
          total_amount: '1000000.00', paid_amount: '200000.00', pending_amount: '800000.00',
          payment_status: 'partial', payment_status_label: 'Parcial',
        }),
        incomeRow({
          id: 12, concept: 'Kore - cuenta emitida', period: '2026-06',
          period_label: 'Junio 2026', period_date: '2026-06-01',
          client: 5, client_name: 'Kore SAS', has_collection_account: true,
          collection_account_status: 'issued', collection_account_number: 'CC-ISSUED-001',
        }),
      ],
      calls,
    }));
    await gotoIncomes(page);

    await page.getByTestId('accounting-select-11').check();
    await page.getByTestId('accounting-select-12').check();
    await expect(page.getByTestId('incomes-selected-total')).toHaveText(
      'Valor total seleccionado: $2.000.000 COP',
    );
    await expect(page.getByTestId('incomes-selected-pending')).toHaveText(
      'Saldo pendiente seleccionado: $1.800.000 COP',
    );
    await bulkAction(page, 'incomes', 'Liquidar');
    await expect(page.getByTestId('income-bulk-settle-modal')).toContainText('Kore - Fase 2 Entrega');
    await expect(page.getByTestId('income-bulk-settle-modal')).toContainText('Kore - cuenta emitida');
    await page.getByTestId('income-bulk-settle-submit').click();

    await expect.poll(() => calls.filter((call) => (
      call.apiPath === 'accounting/incomes/bulk-settle/'
    )).length).toBe(1);
    expect(calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/').body)
      .toMatchObject({ allocations: [
        { income_id: 11, amount: 800000 },
        { income_id: 12, amount: 1000000 },
      ] });
  });

  // Bug caught: after receiving all the money, the list said only "Pagado"
  // and hid the next operational step: emit the collection account.
  test('a completed client income shows its pending collection account', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [incomeRow({
        id: 11, client: 5, client_name: 'Kore SAS', has_collection_account: false,
        collection_account_status: null, total_amount: '500000.00', pending_amount: '500000.00',
      })],
      calls, requireCollectionAccountOnPaid: true,
    }));
    await gotoIncomes(page);

    await openSettleModal(page, [11]);
    await page.getByTestId('income-bulk-settle-submit').click();

    await expect.poll(() => calls.filter((call) => (
      call.apiPath === 'accounting/incomes/bulk-settle/'
    )).length).toBe(1);
    await expect(page.getByTestId('income-payment-11').filter({ visible: true }))
      .toContainText('Pagado');
    await expect(page.getByTestId('income-account-pending-11').filter({ visible: true })).toHaveText(
      'Cuenta pendiente de emitir',
    );
  });

  test('the prefilled valor covers several incomes exactly and all turn Pagado', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 11, total_amount: '500000.00', pending_amount: '500000.00' }),
        incomeRow({
          id: 12, concept: 'Kore - Fase 3 Inicio', period: '2026-06',
          period_label: 'Junio 2026', period_date: '2026-06-01',
          total_amount: '300000.00', pending_amount: '300000.00',
        }),
      ],
      calls,
    }));
    await gotoIncomes(page);

    await openSettleModal(page, [11, 12]);
    // Nothing typed: the prefill (Σ pendientes) must carry the exact cover.
    await expect(page.getByTestId('income-bulk-settle-summary'))
      .toContainText('Cobro cubierto por completo');
    await page.getByTestId('income-bulk-settle-submit').click();

    await expect(page.getByTestId('accounting-row-11')).toContainText('Pagado');
    await expect(page.getByTestId('accounting-row-12')).toContainText('Pagado');
    await expect(
      page.getByRole('alert').filter({ hasText: '2 ingresos quedaron pagados.' }),
    ).toBeVisible({ timeout: 10_000 });
    const settle = calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/');
    expect(settle.body.allocations).toEqual([
      { income_id: 11, amount: 500000 },
      { income_id: 12, amount: 300000 },
    ]);
  });

  test('one payment covers two incomes fully and a third partially', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({ id: 11, total_amount: '500000.00', pending_amount: '500000.00' }),
        incomeRow({
          id: 12, concept: 'Kore - Fase 3 Inicio', period: '2026-06',
          period_label: 'Junio 2026', period_date: '2026-06-01',
          total_amount: '300000.00', pending_amount: '300000.00',
        }),
        incomeRow({
          id: 13, concept: 'Kore - Fase 3 Diseño', period: '2026-07',
          period_label: 'Julio 2026', period_date: '2026-07-01',
          total_amount: '400000.00', pending_amount: '400000.00',
        }),
      ],
      calls,
    }));
    await gotoIncomes(page);

    await openSettleModal(page, [11, 12, 13]);
    await page.getByTestId('income-bulk-settle-total').fill('900000');
    await expect(page.getByTestId('income-bulk-settle-coverage'))
      .toHaveText('Quedan pagados: 2 · parciales: 1 · sin abono: 0');
    await page.getByTestId('income-bulk-settle-submit').click();

    await expect(page.getByTestId('accounting-row-11')).toContainText('Pagado');
    await expect(page.getByTestId('accounting-row-12')).toContainText('Pagado');
    await expect(page.getByTestId('accounting-row-13')).toContainText('Parcial');
    await expect(
      page.getByRole('alert').filter({
        hasText: '2 ingresos quedaron pagados y 1 quedó parcial.',
      }),
    ).toBeVisible({ timeout: 10_000 });
    // The whole point: one payment, ONE request, one pocket movement.
    expect(
      calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/'),
    ).toHaveLength(1);
  });

  test('an excess valor announces the saldo a favor and lands it in the list', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [incomeRow({
        id: 11, total_amount: '500000.00', pending_amount: '500000.00',
        client: 5, client_name: 'Kore SAS', has_collection_account: true,
        collection_account_status: 'issued',
      })],
      calls,
    }));
    await gotoIncomes(page);

    await openSettleModal(page, [11]);
    await page.getByTestId('income-bulk-settle-total').fill('700000');
    await expect(page.getByTestId('income-bulk-settle-summary'))
      .toContainText('quedará como saldo a favor de Kore SAS.');
    await page.getByTestId('income-bulk-settle-submit').click();

    await expect(page.getByTestId('accounting-row-11')).toContainText('Pagado');
    await expect(page.getByTestId('accounting-row-900'))
      .toContainText('Saldo a favor Kore SAS');
    const settle = calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/');
    expect(settle.body.total_amount).toBe(700000);
    expect(settle.body.allocations).toEqual([{ income_id: 11, amount: 500000 }]);
  });

  test('a mixed-client excess stays blocked inside the modal', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [
        incomeRow({
          id: 11, total_amount: '500000.00', pending_amount: '500000.00',
          client: 5, client_name: 'Kore SAS', has_collection_account: true,
          collection_account_status: 'issued',
        }),
        incomeRow({
          id: 12, concept: 'Globex - Fase 1', period: '2026-06',
          period_label: 'Junio 2026', period_date: '2026-06-01',
          total_amount: '300000.00', pending_amount: '300000.00',
          client: 9, client_name: 'Globex', has_collection_account: true,
          collection_account_status: 'issued',
        }),
      ],
      calls,
    }));
    await gotoIncomes(page);

    await openSettleModal(page, [11, 12]);
    await page.getByTestId('income-bulk-settle-total').fill('900000');

    await expect(page.getByTestId('income-bulk-settle-submit-reason'))
      .toContainText('Con clientes mezclados el excedente no se puede asignar como saldo a favor: ajusta el valor.');
    await expect(page.getByTestId('income-bulk-settle-submit')).toBeDisabled();
    expect(
      calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/'),
    ).toHaveLength(0);
  });

  test('a backend rejection keeps the modal open with the Spanish message', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [incomeRow({ id: 11 })], calls, settleStatus: 400,
    }));
    await gotoIncomes(page);

    await openSettleModal(page, [11]);
    await page.getByTestId('income-bulk-settle-submit').click();

    await expect(
      page.getByRole('alert').filter({ hasText: 'No se pudo registrar el abono' }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByRole('alert').filter({
        hasText: 'El valor supera lo pendiente de la selección.',
      }),
    ).toBeVisible();
    await expect(page.getByTestId('income-bulk-settle-modal')).toBeVisible();
  });

  test('the pocket movement opens the reparto of the abono', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the pocket ledger is reached from the accounting subnav, covered by admin-accounting-pocket)
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            user: { username: 'admin', is_staff: true, is_superuser: true },
          }),
        };
      }
      if (apiPath === 'accounting/pocket/' && method === 'GET') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [{
              id: 70,
              concept: 'Abono Kore SAS',
              movement_date: '2026-08-15',
              direction: 'in',
              direction_label: 'Ingreso',
              amount: '900000.00',
              is_auto_managed: true,
              linked_income_id: null,
              linked_expense_id: null,
              linked_ledger: 'company',
              allocations: [
                { income_id: 101, expected_income_id: 11, concept: 'Kore - Fase 2 Entrega', amount: '500000.00' },
                { income_id: 102, expected_income_id: 12, concept: 'Kore - Fase 3 Inicio', amount: '300000.00' },
                { income_id: 103, expected_income_id: 13, concept: 'Kore - Fase 3 Diseño', amount: '100000.00' },
              ],
              notes: '',
              created_at: '2026-08-15T10:00:00Z',
              updated_at: '2026-08-15T10:00:00Z',
            }],
            meta: { balance: '900000.00' },
          }),
        };
      }
      if (apiPath.startsWith('accounts/saved-filter-tabs')) {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        };
      }
      return null;
    });

    await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Bolsillo ProjectApp', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('pocket-allocations-70').click();

    const modal = page.getByTestId('pocket-allocations-modal');
    await expect(modal).toContainText('Abono Kore SAS');
    await expect(modal.getByTestId('pocket-allocation-row')).toHaveCount(3);
    await expect(modal).toContainText('Kore - Fase 3 Diseño');
    await expect(modal.getByTestId('pocket-allocations-total')).toContainText('900.000');
  });

  test('the income itself names the abono that paid it and opens its reparto', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the incomes list is reached from the accounting subnav, covered by admin-accounting-income-crud; the flow under test starts at the row link below)
    const parent = incomeRow({
      id: 11,
      concept: 'Kore - Fase 2 Entrega',
      paid_amount: '500000.00',
      pending_amount: '500000.00',
      payment_status: 'partial',
      payment_status_label: 'Parcial',
    });
    await mockApi(page, async (ctx) => {
      if (ctx.apiPath === 'accounting/incomes/11/detail/' && ctx.method === 'GET') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            income: parent,
            liquid: [{
              id: 101,
              concept: 'Abono Kore SAS',
              kind: 'liquid',
              total_amount: '500000.00',
              period_date: '2026-08-15',
              movement: {
                id: 70,
                concept: 'Abono Kore SAS',
                movement_date: '2026-08-15',
                amount: '900000.00',
                is_shared: true,
                allocation_count: 3,
                allocations: [
                  { income_id: 101, concept: 'Kore - Fase 2 Entrega', amount: '500000.00' },
                  { income_id: 102, concept: 'Kore - Fase 3 Inicio', amount: '300000.00' },
                  { income_id: 103, concept: 'Kore - Fase 3 Diseño', amount: '100000.00' },
                ],
              },
            }],
            expenses: [],
            collection_account: null,
          }),
        };
      }
      return buildHandler({ rows: [parent], calls: [] })(ctx);
    });
    await gotoIncomes(page);

    await page.getByTestId('income-open-11').click();

    // The settlement stops reading as an ordinary liquidación...
    const detail = page.getByTestId('income-detail-modal');
    await expect(detail).toContainText('Abono');
    await expect(page.getByTestId('income-detail-movement-101'))
      .toContainText('Abono · 3 ingresos');

    await page.getByTestId('income-detail-movement-101').click();

    // ...and the reparto names the siblings this income pays nothing to and
    // could not see from here before, plus the whole transfer it came from.
    const reparto = page.getByTestId('pocket-allocations-modal');
    await expect(reparto.getByTestId('pocket-allocation-row')).toHaveCount(3);
    await expect(reparto).toContainText('Kore - Fase 3 Diseño');
    await expect(reparto.getByTestId('pocket-allocations-total')).toContainText('900.000');
  });
});

const SELECTED_SUMMARY_PROFILES = [
  { profile: 'compact', hydrationTimeout: undefined, slow: false },
  { profile: 'portrait', hydrationTimeout: undefined, slow: false },
  { profile: 'landscape', hydrationTimeout: undefined, slow: false },
  { profile: 'desktop', hydrationTimeout: undefined, slow: false },
  { profile: 'wide', hydrationTimeout: 90_000, slow: true },
];

for (const { profile, hydrationTimeout, slow } of SELECTED_SUMMARY_PROFILES) {
  test.describe(`selected abono summary at ${profile}`, () => {
    test.use(viewportUse(profile));

    // Bug caught: at a narrow width the selected totals could overflow the
    // action bar and leave the payment action unreachable.
    test('wraps both selected totals and keeps Liquidar reachable', {
      tag: [
        ...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE,
        '@role:admin',
        '@outcome:success',
        '@responsive-special:accounting',
        `@viewport:${profile}`,
      ],
    }, async ({ page }) => {
      test.slow(slow);
      const rows = [
        incomeRow({ id: 11, total_amount: '500000.00', pending_amount: '500000.00' }),
        incomeRow({ id: 12, total_amount: '300000.00', pending_amount: '300000.00' }),
      ];
      await setAuthLocalStorage(page, {
        token: 'e2e-token', userAuth: { id: 9001, role: 'admin', is_staff: true },
      });
      await mockApi(page, buildHandler({ rows, calls: [] }));
      await gotoIncomes(page, { hydrationTimeout });

      await page.getByTestId('accounting-select-11').check();
      await page.getByTestId('accounting-select-12').check();
      const summary = page.getByTestId('incomes-bulk-bar');
      await expect(page.getByTestId('incomes-selected-total')).toHaveText(
        'Valor total seleccionado: $800.000 COP',
      );
      await expect(page.getByTestId('incomes-selected-pending')).toHaveText(
        'Saldo pendiente seleccionado: $800.000 COP',
      );
      expect(await summary.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);

      await bulkAction(page, 'incomes', 'Liquidar');
      await expect(page.getByTestId('income-bulk-settle-modal')).toContainText('Kore - Fase 2 Entrega');
    });
  });
}
