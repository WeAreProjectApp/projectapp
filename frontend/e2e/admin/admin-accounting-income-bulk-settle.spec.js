/**
 * E2E coverage for the single settlement modal used by one or many incomes.
 * Bug caught: grouped payments used to bypass deductions and partner amounts
 * through a second modal, so the reviewed distribution never reached the API.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { bulkAction } from '../helpers/bulk-actions.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';
import { ADMIN_ACCOUNTING_INCOME_BULK_SETTLE } from '../helpers/flow-tags.js';
import { vatBreakdown } from '../../utils/accountingVat.js';

test.setTimeout(60_000);

function incomeRow(overrides = {}) {
  return {
    id: 1, concept: 'Kore - Fase 2 Entrega', kind: 'expected', kind_label: 'Esperado',
    period: '2026-05', period_label: 'Mayo 2026', period_date: '2026-05-01',
    destination: 'partners', destination_label: 'Socios', ledger: 'company',
    ledger_label: 'Empresa', total_amount: '100000.00', pending_amount: '100000.00',
    paid_amount: '0.00', payment_status: 'pending', payment_status_label: 'Pendiente',
    gustavo_amount: '50000.00', carlos_amount: '50000.00', client: 5,
    client_name: 'Kore SAS', vat_rate: '19.00', origin: '', notes: '',
    created_at: '2026-05-01T10:00:00Z', updated_at: '2026-05-01T10:00:00Z',
    ...overrides,
  };
}

function previewFor(body, rows, { sendable = false } = {}) {
  const allocations = body.allocations ?? rows.map((row) => ({ income_id: row.id, amount: Number(row.pending_amount) }));
  return {
    preview_hash: 'preview-e2e-hash', total_amount: body.total_amount, pending_after: '0.00',
    rows: allocations.map((allocation) => {
      const row = rows.find((candidate) => candidate.id === allocation.income_id);
      const rate = body.vat_updates?.find((entry) => entry.income_id === allocation.income_id)?.vat_rate ?? row?.vat_rate ?? null;
      return {
        income_id: allocation.income_id, concept: row?.concept ?? 'Ingreso', amount: allocation.amount,
        deducted: 0, reexpected: 0, pending_after: 0,
        vat_rate: rate, ...vatBreakdown(allocation.amount, rate),
        vat_editable: !row?.vat_blocked_reason, vat_blocked_reason: row?.vat_blocked_reason || '',
        confirmation: sendable
          ? { can_send: true, recipient: 'pagos@kore.co', collection_account_number: 'PA-KORE-001', blocked_reason: '' }
          : { can_send: false, recipient: '', collection_account_number: '', blocked_reason: 'No hay cuenta de cobro emitida.' },
      };
    }),
  };
}

function buildHandler({ rows, calls, previewStatus = 200, settleStatus = 201, sendable = false }) {
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true, is_superuser: true } }) };
    if (apiPath === 'accounting/settings/' && method === 'GET') return { status: 200, contentType: 'application/json', body: JSON.stringify({ income_default_view_mode: 'classic' }) };
    if (apiPath === 'accounting/incomes/' && method === 'GET') return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: rows, meta: {} }) };
    if (apiPath === 'accounting/incomes/settlement-preview/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (previewStatus !== 200) return { status: previewStatus, contentType: 'application/json', body: JSON.stringify({ detail: 'No se pudo revisar la liquidación.' }) };
      return { status: 200, contentType: 'application/json', body: JSON.stringify(previewFor(body, rows, { sendable })) };
    }
    if (apiPath === 'accounting/incomes/bulk-settle/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (settleStatus !== 201) return { status: settleStatus, contentType: 'application/json', body: JSON.stringify({ detail: 'La liquidación cambió mientras la revisabas.' }) };
      return { status: 201, contentType: 'application/json', body: JSON.stringify({ updated: body.income_ids.length, results: rows, payment_confirmations: [] }) };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    return null;
  };
}

async function gotoIncomes(page) {
  await page.goto('/en-us/panel/accounting/incomes?accounting_incomeTab=all', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByRole('heading', { name: 'Ingresos', exact: true })).toHaveText('Ingresos');
}

async function openBulkSettlement(page, ids) {
  for (const id of ids) await page.getByTestId(`accounting-select-${id}`).check();
  await bulkAction(page, 'incomes', 'Liquidar');
  await expect(page.getByTestId('income-liquidate-form')).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText(`${ids.length} ${ids.length === 1 ? 'ingreso seleccionado' : 'ingresos seleccionados'}`);
}

async function openDifference(page) {
  const toggle = page.getByTestId('income-liquidate-difference-toggle');
  if (await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click();
}

test.describe('Admin Accounting Income Bulk Settle', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9001, role: 'admin', is_staff: true } });
  });

  test('keeps manual allocations, participation and a proportional deduction in one settlement dialog', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    const rows = [incomeRow({ id: 11 }), incomeRow({ id: 12, concept: 'Kore - Fase 3 Inicio', period_date: '2026-06-01' })];
    await mockApi(page, buildHandler({ rows, calls }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11, 12]);
    const dialog = page.getByRole('dialog');
    await expect(dialog).toHaveCount(1);
    await page.getByTestId('income-liquidate-paid').fill('180000');
    await page.getByTestId('income-bulk-settle-amount-11').fill('80000');
    await page.getByTestId('income-bulk-settle-amount-12').fill('80000');
    await page.getByTestId('income-liquidate-participations-toggle').click();
    await expect(page.getByTestId('partner-split-gustavo')).toHaveValue('90.000');
    await expect(page.getByTestId('partner-split-carlos')).toHaveValue('90.000');
    await page.getByTestId('partner-split-auto').click();
    await page.getByTestId('partner-split-gustavo').fill('100000');
    await page.getByTestId('partner-split-carlos').fill('80000');
    await openDifference(page);
    await page.getByTestId('income-liquidate-add-deduction').click();
    await page.getByTestId('deduction-type-0').selectOption('gateway_fee');
    await page.getByTestId('deduction-amount-0').fill('20000');
    await expect(page.getByTestId('income-liquidate-summary')).toContainText('Cubierto: $180.000 COP');
    await page.getByTestId('income-liquidate-submit').click();
    await expect.poll(() => calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/').length).toBe(1);
    const settle = calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/').body;
    expect(settle).toMatchObject({
      income_ids: [11, 12], allocations: [{ income_id: 11, amount: 80000 }, { income_id: 12, amount: 80000 }],
      gustavo_amount: 100000, carlos_amount: 80000,
      deductions: [{ type: 'gateway_fee', amount: 20000, detail: '' }], preview_hash: 'preview-e2e-hash',
    });
    expect(calls.filter((call) => call.apiPath === 'accounting/incomes/settlement-preview/')).toHaveLength(2);
  });

  // Bug caught: a preview failure used to discard the operator's amount and hide the correction path.
  test('keeps the entered form open when the settlement preview fails', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow({ id: 11 })], calls, previewStatus: 500 }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11]);
    await page.getByTestId('income-liquidate-paid').fill('75000');
    await page.getByTestId('income-liquidate-submit').click();
    await expect(page.getByRole('alert')).toHaveText('No se pudo revisar la liquidación.');
    await expect(page.getByTestId('income-liquidate-paid')).toHaveValue('75.000');
    expect(calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/')).toHaveLength(0);
  });

  // Bug caught: a stale final confirmation used to close the dialog and lose the editable settlement.
  test('keeps the reviewed settlement editable after a stale final conflict', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow({ id: 11 })], calls, settleStatus: 409, sendable: true }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11]);
    await page.getByTestId('income-liquidate-paid').fill('90000');
    await page.getByTestId('income-liquidate-submit').click();
    await expect(page.getByTestId('income-liquidate-review')).toContainText('pagos@kore.co');
    await page.getByTestId('income-liquidate-confirm').click();
    await expect(page.getByRole('alert')).toContainText('La liquidación cambió mientras la revisabas.');
    await expect(page.getByTestId('income-liquidate-review')).toContainText('Valor recibido');
    expect(calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/')).toHaveLength(1);
  });

  // Bug caught: switching IVA off hid its values without setting the source rate to zero.
  test('sets Sin IVA from the header switch without changing the received total', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      rows: [incomeRow({
        id: 11, total_amount: '119000.00', pending_amount: '119000.00',
        gustavo_amount: '59500.00', carlos_amount: '59500.00', vat_rate: '19.00',
      })],
      calls,
    }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11]);
    await page.getByTestId('income-liquidate-paid').fill('119000');
    await expect(page.getByTestId('income-liquidate-apply-vat-11')).toBeVisible();
    await page.getByTestId('income-liquidate-vat-toggle-11').click();
    await expect(page.getByTestId('vat-total')).toHaveText('$119.000 COP');
    await expect(page.getByTestId('vat-tax')).toHaveText('$19.000 COP');
    await page.getByTestId('income-liquidate-apply-vat-11').click();
    await expect(page.getByTestId('vat-tax')).toHaveText('$0 COP');
    await expect(page.getByTestId('vat-base')).toHaveText('$119.000 COP');
    await expect(page.getByTestId('income-liquidate-paid')).toHaveValue('119.000');
    await page.getByTestId('income-liquidate-submit').click();
    await expect.poll(() => calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/').length).toBe(1);
    const settle = calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/').body;
    expect(settle).toMatchObject({ total_amount: 119000, preview_hash: 'preview-e2e-hash' });
    expect(settle.vat_updates).toEqual([{ income_id: 11, vat_rate: 0 }]);
  });

  // Bug caught: a historical income could neither record its VAT nor capture the payment before tax.
  test('configures an unknown rate before capturing the payment base', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow({ id: 11, vat_rate: null, total_amount: '238000.00', pending_amount: '238000.00' })], calls }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11]);
    await page.getByTestId('income-liquidate-apply-vat-11').click();
    const section = page.getByTestId('income-liquidate-vat-11');
    await section.getByTestId('vat-rate').fill('19');
    await section.getByRole('button', { name: 'Antes de IVA', exact: true }).click();
    await page.getByTestId('income-liquidate-vat-amount-11').fill('100000');
    await expect(section.getByTestId('vat-base')).toHaveText('$100.000 COP');
    await expect(section.getByTestId('vat-tax')).toHaveText('$19.000 COP');
    await expect(page.getByTestId('income-liquidate-paid')).toHaveValue('119.000');
    await page.getByTestId('income-liquidate-submit').click();
    await expect.poll(() => calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/').length).toBe(1);
    expect(calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/').body).toMatchObject({
      total_amount: 119000, allocations: [{ income_id: 11, amount: 119000 }],
      vat_updates: [{ income_id: 11, vat_rate: '19', amount: 100000, amount_mode: 'before_vat' }],
    });
  });

  // Bug caught: one header switch could silently overwrite another income's fiscal terms.
  test('preserves the other income rate when disabling VAT in a mixed selection', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    const rows = [incomeRow({ id: 11 }), incomeRow({ id: 12, concept: 'Otro servicio', vat_rate: '5.00' })];
    await mockApi(page, buildHandler({ rows, calls }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11, 12]);
    await page.getByTestId('income-liquidate-apply-vat-11').click();
    await expect(page.getByTestId('income-liquidate-vat-status-12')).toHaveText('5.00 %');
    await page.getByTestId('income-liquidate-submit').click();
    await expect.poll(() => calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/').length).toBe(1);
    expect(calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/').body.vat_updates)
      .toEqual([{ income_id: 11, vat_rate: 0 }]);
  });

  // Bug caught: fiscal protections were either missing or also disabled the received amount.
  test('explains the issued-account lock while keeping the payment editable', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow({ id: 11, vat_blocked_reason: 'Anula la cuenta emitida antes de cambiar el importe o el IVA del ingreso.' })], calls }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11]);
    await page.getByTestId('income-liquidate-vat-toggle-11').click();
    await expect(page.getByTestId('income-liquidate-apply-vat-11')).toBeDisabled();
    await expect(page.getByTestId('income-liquidate-vat-lock-11')).toContainText('Anula la cuenta emitida');
    await expect(page.getByTestId('income-liquidate-vat-11').getByTestId('vat-rate')).toBeDisabled();
    await page.getByTestId('income-liquidate-vat-amount-11').fill('50000');
    await expect(page.getByTestId('income-liquidate-paid')).toHaveValue('50.000');
  });

  // Bug caught: a mixed-client excess used to reach the final request and create a credit for the wrong client.
  test('blocks a mixed-client excess before the final settlement request', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    const rows = [
      incomeRow({ id: 11, client: 5, client_name: 'Kore SAS' }),
      incomeRow({ id: 12, concept: 'Globex - Inicio', client: 6, client_name: 'Globex SAS', period_date: '2026-06-01' }),
    ];
    await mockApi(page, buildHandler({ rows, calls }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11, 12]);
    await page.getByTestId('income-liquidate-paid').fill('200001');
    await expect(page.getByTestId('income-liquidate-submit-reason'))
      .toContainText('Con clientes mezclados el excedente no se puede asignar como saldo a favor.');
    await expect(page.getByTestId('income-liquidate-submit')).toBeDisabled();
    expect(calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/')).toHaveLength(0);
  });

  // Bug caught: reviewing client confirmations used to open a separate dialog and discard typed notes on return.
  test('reviews one email recipient per income in the same dialog and keeps edits when returning', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    const rows = [incomeRow({ id: 11 }), incomeRow({ id: 12, concept: 'Kore - Fase 3 Inicio', period_date: '2026-06-01' })];
    await mockApi(page, buildHandler({ rows, calls, sendable: true }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11, 12]);
    await page.getByTestId('income-liquidate-notes').fill('Abono conciliado con el cliente');
    await page.getByTestId('income-liquidate-submit').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toHaveCount(1);
    await expect(page.getByTestId('income-liquidate-review-recipient')).toHaveCount(2);
    await page.getByTestId('income-liquidate-review-back').click();
    await expect(page.getByTestId('income-liquidate-notes')).toHaveValue('Abono conciliado con el cliente');
    await page.getByTestId('income-liquidate-submit').click();
    await page.getByTestId('income-liquidate-confirm').click();
    await expect.poll(() => calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/').length).toBe(1);
  });

  // Bug caught: a zero-cash row could still ask to email a payment, blocking a fee plus reprogrammed remainder.
  test('settles a zero-cash deduction and follow-up without requesting a confirmation', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [incomeRow({ id: 11 })], calls, sendable: true }));
    await gotoIncomes(page);
    await openBulkSettlement(page, [11]);
    await page.getByTestId('income-liquidate-paid').fill('0');
    await openDifference(page);
    await page.getByTestId('income-liquidate-add-deduction').click();
    await page.getByTestId('deduction-type-0').selectOption('bank_fee');
    await page.getByTestId('deduction-amount-0').fill('40000');
    await page.getByTestId('income-liquidate-add-followup').click();
    await page.getByTestId('followup-concept-0').fill('Kore - saldo junio');
    await page.getByTestId('followup-period-0').fill('2026-06');
    await page.getByTestId('followup-amount-0').fill('60000');
    await expect(page.getByTestId('income-liquidate-confirmation-11')).toBeDisabled();
    await page.getByTestId('income-liquidate-submit').click();
    await expect.poll(() => calls.filter((call) => call.apiPath === 'accounting/incomes/bulk-settle/').length).toBe(1);
    const settle = calls.find((call) => call.apiPath === 'accounting/incomes/bulk-settle/').body;
    expect(settle).toMatchObject({ total_amount: 0, confirmation_income_ids: [], send_payment_confirmation: false });
    expect(settle.expected_incomes).toEqual([{ income_id: 11, concept: 'Kore - saldo junio', period_date: '2026-06', amount: 60000 }]);
  });
  test('opens the abono allocations from its pocket movement', {
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
      if (apiPath === 'accounting/pocket/70/' && method === 'GET') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 70, concept: 'Abono Kore SAS', movement_date: '2026-08-15',
            direction: 'in', direction_label: 'Ingreso', amount: '900000.00',
            linked_ledger: 'company', linked_record_detail: null,
            running_balance: '900000.00', notes: '',
            allocation_details: [
              { income_id: 101, expected_income_id: 11, concept: 'Kore - Fase 2 Entrega', amount: '500000.00', pending_amount: '0.00', is_credit: false },
              { income_id: 102, expected_income_id: 12, concept: 'Kore - Fase 3 Inicio', amount: '300000.00', pending_amount: '0.00', is_credit: false },
              { income_id: 103, expected_income_id: 13, concept: 'Kore - Fase 3 Diseño', amount: '100000.00', pending_amount: '200000.00', is_credit: false },
            ],
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

    await page.goto('/es-co/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await waitForNuxtApp(page);
    await page.getByTestId('accounting-subnav-pocket').click();
    await expect(
      page.getByRole('heading', { name: 'Bolsillo ProjectApp', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('pocket-allocations-70').click();

    const modal = page.getByTestId('pocket-detail-modal');
    await expect(modal).toContainText('Abono Kore SAS');
    await expect(modal.getByTestId('pocket-allocation-detail-row')).toHaveCount(3);
    await expect(modal).toContainText('Kore - Fase 3 Diseño');
    await expect(modal.getByTestId('pocket-allocation-detail-total')).toContainText('900.000');
  });

  test('opens sibling allocations from an income payment', {
    tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the incomes list is reached from the accounting subnav, covered by admin-accounting-income-crud; the flow under test starts at the row link below)
    const parent = incomeRow({
      id: 11,
      concept: 'Kore - Fase 2 Entrega',
      total_amount: '1000000.00',
      gustavo_amount: '500000.00',
      carlos_amount: '500000.00',
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

const MODAL_PROFILES = ['compact', 'portrait', 'landscape', 'desktop', 'wide'];
for (const profile of MODAL_PROFILES) {
  test.describe(`unified settlement modal at ${profile}`, () => {
    test.use(viewportUse(profile));
    // Bug caught: the accordion made partner values or the primary action overflow off screen at this width.
    test('keeps its summary, accordions and primary action within the dialog', {
      tag: [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:display', '@responsive-special:accounting', `@viewport:${profile}`],
    }, async ({ page }) => {
      // quality: allow-deep-link (the accounting subnav entry is covered by navigation specs; this responsive contract isolates the modal geometry after a real row-selection action)
      const calls = [];
      await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9001, role: 'admin', is_staff: true } });
      await mockApi(page, buildHandler({ rows: [incomeRow({ id: 11 })], calls }));
      await gotoIncomes(page);
      await openBulkSettlement(page, [11]);
      await page.getByTestId('income-liquidate-paid').fill('90000');
      await page.getByTestId('income-liquidate-participations-toggle').click();
      await openDifference(page);
      await expect(page.getByTestId('income-liquidate-apply-vat-11')).toBeVisible();
      await page.getByTestId('income-liquidate-vat-toggle-11').click();
      const dialog = page.getByRole('dialog');
      await expect(dialog.getByTestId('income-liquidate-summary')).toContainText('Falta: $10.000 COP');
      await expect(dialog.getByTestId('partner-split-gustavo')).toHaveValue('45.000');
      await expect(dialog.getByTestId('income-liquidate-submit')).toHaveText('Liquidar');
      expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
      expect(await dialog.getByTestId('income-liquidate-submit').evaluate((element) => element.getBoundingClientRect().bottom <= window.innerHeight)).toBe(true);
    });
  });
}
