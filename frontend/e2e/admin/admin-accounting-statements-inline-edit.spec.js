/**
 * E2E tests for inline editing of statement transaction rows.
 *
 * FLOWS: admin-accounting-statements
 * Covers: single-click inline merchant edit on a draft statement (PATCH body +
 *         updated cell), learning the merchant alias afterwards, the structured
 *         cuota validation, negative amounts, a backend 400, editing a
 *         processed statement through the reopen confirmation, and inline
 *         editing of the learned merchants table.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { chooseRowAction, openRowMenu } from '../helpers/row-actions.js';
import { ADMIN_ACCOUNTING_STATEMENTS } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

function statusPayload() {
  return {
    year: 2026,
    year_options: [2026],
    months: [
      {
        period: '2026-05',
        label: 'mayo',
        applies: true,
        statements: [
          { id: 1, card_name: 'T.C 0064', status: 'processed', status_label: 'Procesado' },
        ],
      },
      {
        period: '2026-06',
        label: 'junio',
        applies: true,
        statements: [
          { id: 2, card_name: 'T.C 0064', status: 'draft', status_label: 'Borrador' },
        ],
      },
    ],
  };
}

function makeTx(overrides = {}) {
  return {
    id: 10,
    transaction_date: '2026-06-05',
    raw_description: 'PAGO SERVIDOR HETZNER',
    merchant_name: 'Hetzner',
    amount: '450000.00',
    category: 'software',
    category_label: 'Software y suscripciones',
    installment_label: '',
    installment_number: null,
    installments_total: null,
    original_amount: null,
    original_currency: '',
    is_identified: true,
    ...overrides,
  };
}

const REFUND_TX = makeTx({
  id: 11,
  raw_description: 'DEVOLUCION HETZNER',
  amount: '-120000.00',
});

function makeDetail(overrides = {}) {
  return {
    id: 2,
    card_name: 'T.C 0064',
    period: '2026-06',
    period_label: 'Junio 2026',
    status: 'draft',
    status_label: 'Borrador',
    purchases_total: '450000.00',
    payments_total: '0.00',
    interest_and_fees: '0.00',
    minimum_payment: '45000.00',
    closing_balance: '450000.00',
    due_date: '2026-07-05',
    created_at: '2026-07-01T10:00:00Z',
    pdf_file_url: null,
    category_totals: [],
    transactions: [makeTx()],
    ...overrides,
  };
}

function processedDetail(transactions) {
  return makeDetail({
    id: 1,
    period: '2026-05',
    period_label: 'Mayo 2026',
    status: 'processed',
    status_label: 'Procesado',
    ...(transactions ? { transactions } : {}),
  });
}

/**
 * @param calls      collector for every PATCH/POST the page issues
 * @param patchError Spanish message the PATCH should fail with
 * @param aliases    merchant catalog served to the combobox
 * @param extraTx    extra rows appended to the draft statement
 * @param aliasError Spanish message the alias PATCH should fail with
 */
function buildHandler({
  calls, patchError = null, aliases = [], extraTx = [], aliasError = null,
}) {
  const state = {
    detail: makeDetail({ transactions: [makeTx(), ...extraTx] }),
    // Reopening flips statement 1 to draft, exactly like the backend does.
    statement1Status: 'processed',
    aliases: [...aliases],
  };
  const json = (body) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return json({
        user: { username: 'admin', is_staff: true, is_superuser: true },
      });
    }
    if (apiPath.startsWith('accounting/statements/status/')) {
      return json(statusPayload());
    }
    if (apiPath === 'accounting/statements/1/' && method === 'GET') {
      const detail = processedDetail();
      detail.status = state.statement1Status;
      detail.status_label = state.statement1Status === 'draft' ? 'Borrador' : 'Procesado';
      return json(detail);
    }
    if (apiPath === 'accounting/statements/1/reopen/' && method === 'POST') {
      calls.push({ apiPath, method, body: {} });
      state.statement1Status = 'draft';
      const detail = processedDetail();
      detail.status = 'draft';
      detail.status_label = 'Borrador';
      return json(detail);
    }
    if (apiPath === 'accounting/statements/2/' && method === 'GET') {
      return json(state.detail);
    }

    const patchMatch = apiPath.match(
      /^accounting\/statements\/(\d+)\/transactions\/(\d+)\/update\/$/,
    );
    if (patchMatch && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (patchError) {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: patchError }),
        };
      }
      const txId = Number(patchMatch[2]);
      const rows = state.detail.transactions.map(
        (tx) => (tx.id === txId ? { ...tx, ...body } : tx),
      );
      state.detail = makeDetail({ transactions: rows });
      return json(rows.find((tx) => tx.id === txId));
    }

    if (apiPath === 'accounting/merchant-aliases/learn/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      return json({
        alias: { id: 5, match_text: 'PAGO SERVIDOR HETZNER', merchant_name: 'Hetzner Cloud' },
        applied: 0,
        warning: '',
      });
    }
    const aliasMatch = apiPath.match(
      /^accounting\/merchant-aliases\/(\d+)\/update\/$/,
    );
    if (aliasMatch && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (aliasError) {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ match_text: [aliasError] }),
        };
      }
      const aliasId = Number(aliasMatch[1]);
      // The backend answers with the stored record, so `match_text` comes back
      // normalized regardless of what was typed.
      const updated = {
        ...state.aliases.find((alias) => alias.id === aliasId),
        ...body,
        ...(body.match_text ? { match_text: body.match_text.toUpperCase() } : {}),
      };
      state.aliases = state.aliases.map(
        (alias) => (alias.id === aliasId ? updated : alias),
      );
      return json(updated);
    }
    const aliasDelete = apiPath.match(/^accounting\/merchant-aliases\/(\d+)\/delete\/$/);
    if (aliasDelete && method === 'DELETE') {
      calls.push({ apiPath, method });
      state.aliases = state.aliases.filter((alias) => alias.id !== Number(aliasDelete[1]));
      return { status: 204, contentType: 'application/json', body: '' };
    }
    if (apiPath.startsWith('accounting/merchant-aliases')) {
      return json({ results: state.aliases, meta: {} });
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

async function gotoStatements(page) {
  await page.goto('/panel/accounting/statements', { waitUntil: 'domcontentloaded' });
  await expect(
    page.getByRole('heading', { name: 'Extractos de tarjeta' }),
  ).toBeVisible({ timeout: 25_000 });
}

async function openDraft(page) {
  await page.getByTestId('statement-chip-2').click();
  await expect(page.getByTestId('statement-detail')).toBeVisible();
}

test.describe('Admin Accounting Statements: inline row editing', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  // Bug caught: Detalle e historial, Editar and Eliminar were loose text
  // buttons in a trailing column without a header.
  test('a transaction opens its full editor from its row menu', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; this test pins the
    // transaction row menu, driven through the kebab below)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoStatements(page);
    await openDraft(page);

    const row = page.getByTestId('statement-tx-10');
    await expect(row.locator('[data-field="actions"]').getByRole('button')).toHaveCount(1);

    await openRowMenu(page, { kebab: 'statement-tx-actions-10', menu: 'statement-tx-actions-modal' });
    await expect(page.getByTestId('statement-tx-action-history-10')).toBeVisible();
    await expect(page.getByTestId('statement-tx-action-delete-10')).toBeVisible();
    await page.getByTestId('statement-tx-action-edit-10').click();

    await expect(page.getByRole('heading', { name: 'Editar transacción' })).toBeVisible();
  });

  // Bug caught: in the phone card the amount's inline editor laid out 8px
  // narrower than it measured and broke "$450.000" across two lines.
  test('a transaction card on a phone keeps its amount on one line', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; this test pins the
    // phone card of a transaction, whose menu is opened below)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoStatements(page);
    await openDraft(page);

    const amount = page.getByTestId('tx-cell-amount-10');
    await expect(amount).toContainText('$450.000');
    const lines = await amount.getByTestId('inline-cell-display').evaluate((display) => {
      const value = display.querySelector('span');
      return Math.round(
        value.getBoundingClientRect().height / parseFloat(getComputedStyle(value).lineHeight),
      );
    });
    expect(lines).toBe(1);

    await page.getByTestId('statement-tx-actions-10').click();
    await expect(page.getByTestId('statement-tx-actions-modal')).toContainText('Hetzner');
  });

  test('a single click edits the merchant of a draft row and PATCHes it', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);
    await openDraft(page);

    const cell = page.getByTestId('tx-cell-merchant_name-10');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('Hetzner Cloud');
    await input.press('Enter');

    // The save offers to remember the merchant; decline it here.
    await expect(page.getByText('Recordar este comercio')).toBeVisible();
    await page.getByRole('button', { name: 'No, solo esta vez' }).click();

    await expect(cell).toContainText('Hetzner Cloud');
    const patchCall = calls.find(
      (call) => call.apiPath === 'accounting/statements/2/transactions/10/update/',
    );
    expect(patchCall.body).toEqual({
      merchant_name: 'Hetzner Cloud',
      is_identified: true,
    });
  });

  test('accepting the prompt learns the merchant alias for future statements', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);
    await openDraft(page);

    const cell = page.getByTestId('tx-cell-merchant_name-10');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('Hetzner Cloud');
    await input.press('Enter');

    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Comercio recordado')).toBeVisible();
    const learnCall = calls.find(
      (call) => call.apiPath === 'accounting/merchant-aliases/learn/',
    );
    expect(learnCall.body).toEqual({
      raw_description: 'PAGO SERVIDOR HETZNER',
      merchant_name: 'Hetzner Cloud',
      category: 'software',
      statement_id: 2,
    });
  });

  test('picking a catalog merchant fills the category of an "other" row', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      aliases: [{
        id: 3,
        match_text: 'TERPEL',
        merchant_name: 'Terpel',
        default_category: 'fuel',
        default_category_label: 'Gasolina',
      }],
      extraTx: [makeTx({
        id: 12,
        raw_description: 'COMPRA TERPEL 4471',
        merchant_name: '',
        category: 'other',
        category_label: 'Otros',
        is_identified: false,
      })],
    }));
    await gotoStatements(page);
    await openDraft(page);

    const cell = page.getByTestId('tx-cell-merchant_name-12');
    await cell.getByTestId('inline-cell-display').click();
    await cell.getByTestId('merchant-input-option-0').click();

    const patchCall = calls.find(
      (call) => call.apiPath === 'accounting/statements/2/transactions/12/update/',
    );
    expect(patchCall.body).toEqual({
      merchant_name: 'Terpel',
      is_identified: true,
      category: 'fuel',
    });
  });

  test('an invalid cuota shows an error and sends no PATCH', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);
    await openDraft(page);

    const cell = page.getByTestId('tx-cell-installment_label-10');
    await cell.getByTestId('inline-cell-display').click();
    await cell.getByTestId('inline-cell-installment-number').fill('5');
    await cell.getByTestId('inline-cell-installment-total').fill('3');
    await cell.getByTestId('inline-cell-installment-number').press('Enter');

    await expect(page.getByText('Cuota inválida')).toBeVisible();
    expect(calls).toHaveLength(0);
  });

  test('a valid cuota PATCHes the structured installment pair', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);
    await openDraft(page);

    const cell = page.getByTestId('tx-cell-installment_label-10');
    await cell.getByTestId('inline-cell-display').click();
    await cell.getByTestId('inline-cell-installment-number').fill('3');
    await cell.getByTestId('inline-cell-installment-total').fill('12');
    await cell.getByTestId('inline-cell-installment-number').press('Enter');

    const patchCall = calls.find(
      (call) => call.apiPath === 'accounting/statements/2/transactions/10/update/',
    );
    expect(patchCall.body).toEqual({
      installment_number: 3,
      installments_total: 12,
    });
  });

  test('a negative amount stays negative when edited inline', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, extraTx: [REFUND_TX] }));
    await gotoStatements(page);
    await openDraft(page);

    const cell = page.getByTestId('tx-cell-amount-11');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await expect(input).toHaveValue('-120.000');

    await input.fill('-150000');
    await input.press('Enter');

    const patchCall = calls.find(
      (call) => call.apiPath === 'accounting/statements/2/transactions/11/update/',
    );
    expect(patchCall.body).toEqual({ amount: -150000 });
  });

  test('a backend 400 on the inline PATCH surfaces the Spanish error', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      patchError: 'El extracto ya está procesado. Reábrelo antes de modificar sus transacciones.',
    }));
    await gotoStatements(page);
    await openDraft(page);

    const cell = page.getByTestId('tx-cell-merchant_name-10');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('Otro comercio');
    await input.press('Enter');

    await expect(page.getByText(/ya está procesado/)).toBeVisible();
    // The row keeps its original value.
    await expect(cell).toContainText('Hetzner');
  });

  test('editing a processed statement asks to reopen it first', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching /panel/accounting/statements through
    // the subnav is exercised by the accounting navigation specs; this test
    // pins the reopen-to-edit gate on the transaction cells)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);

    await page.getByTestId('statement-chip-1').click();
    await expect(page.getByTestId('statement-detail')).toBeVisible();

    const cell = page.getByTestId('tx-cell-merchant_name-10');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('Hetzner Cloud');
    await input.press('Enter');

    await expect(page.getByText('Extracto finalizado')).toBeVisible();
    await page.getByRole('button', { name: 'Reabrir y editar' }).click();

    // Reopen and PATCH are chained, so wait for the save to land before
    // asserting the order instead of racing the request chain.
    await expect(page.getByText('Recordar este comercio')).toBeVisible();

    // Reopening happens before the edit is applied.
    expect(calls.map((call) => call.apiPath)).toEqual([
      'accounting/statements/1/reopen/',
      'accounting/statements/1/transactions/10/update/',
    ]);
  });

  test('cancelling the reopen prompt leaves the processed row untouched', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoStatements(page);

    await page.getByTestId('statement-chip-1').click();
    await expect(page.getByTestId('statement-detail')).toBeVisible();

    const cell = page.getByTestId('tx-cell-merchant_name-10');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('Hetzner Cloud');
    await input.press('Enter');

    await page.getByRole('button', { name: 'Cancelar' }).click();

    expect(calls).toHaveLength(0);
    await expect(cell).toContainText('Hetzner');
  });
});

const LEARNED_ALIAS = {
  id: 3,
  match_text: 'TERPEL',
  merchant_name: 'Terpel',
  default_category: 'fuel',
  default_category_label: 'Gasolina',
};

async function openLearnedMerchants(page) {
  await page.getByTestId('statements-aliases-toggle').click();
  await expect(page.getByTestId('statement-alias-3')).toBeVisible();
}

test.describe('Admin Accounting Statements: learned merchants inline editing', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('a learned merchant is deleted from its row menu after confirming', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, aliases: [LEARNED_ALIAS] }));
    await gotoStatements(page);
    await openLearnedMerchants(page);

    await chooseRowAction(page, {
      kebab: 'statement-alias-actions-3',
      menu: 'statement-alias-actions-modal',
      action: 'statement-alias-action-delete-3',
    });
    await expect(page.getByRole('heading', { name: 'Eliminar alias' })).toBeVisible();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Alias eliminado.')).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/merchant-aliases/3/delete/',
      method: 'DELETE',
    });
  });

  test('renaming a learned merchant PATCHes it and updates the row', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, aliases: [LEARNED_ALIAS] }));
    await gotoStatements(page);
    await openLearnedMerchants(page);

    const cell = page.getByTestId('alias-cell-merchant_name-3');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('Terpel Colombia');
    await input.press('Enter');

    await expect(page.getByText('Comercio actualizado')).toBeVisible();
    await expect(cell).toContainText('Terpel Colombia');
    expect(calls).toEqual([{
      apiPath: 'accounting/merchant-aliases/3/update/',
      method: 'PATCH',
      body: { merchant_name: 'Terpel Colombia' },
    }]);
  });

  test('the descriptor comes back normalized by the backend', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, aliases: [LEARNED_ALIAS] }));
    await gotoStatements(page);
    await openLearnedMerchants(page);

    const cell = page.getByTestId('alias-cell-match_text-3');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('primax estacion');
    await input.press('Enter');

    await expect(cell).toContainText('PRIMAX ESTACION');
    expect(calls[0].body).toEqual({ match_text: 'primax estacion' });
  });

  test('changing the default category PATCHes the option value', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, aliases: [LEARNED_ALIAS] }));
    await gotoStatements(page);
    await openLearnedMerchants(page);

    const cell = page.getByTestId('alias-cell-default_category-3');
    await expect(cell).toContainText('Gasolina');
    await cell.getByTestId('inline-cell-display').click();
    await cell.locator('select').selectOption('travel');

    expect(calls[0].body).toEqual({ default_category: 'travel' });
  });

  test('clearing the merchant name shows an error and sends no PATCH', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, aliases: [LEARNED_ALIAS] }));
    await gotoStatements(page);
    await openLearnedMerchants(page);

    const cell = page.getByTestId('alias-cell-merchant_name-3');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('  ');
    await input.press('Enter');

    await expect(page.getByText('El comercio no puede quedar vacío')).toBeVisible();
    expect(calls).toHaveLength(0);
  });

  test('a duplicated descriptor surfaces the backend error and keeps the row', {
    tag: [...ADMIN_ACCOUNTING_STATEMENTS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      aliases: [LEARNED_ALIAS],
      aliasError: 'Ya existe un alias para ese texto.',
    }));
    await gotoStatements(page);
    await openLearnedMerchants(page);

    const cell = page.getByTestId('alias-cell-match_text-3');
    await cell.getByTestId('inline-cell-display').click();
    const input = cell.locator('input');
    await input.fill('NETFLIX');
    await input.press('Enter');

    await expect(page.getByText('Ya existe un alias para ese texto')).toBeVisible();
    await expect(cell).toContainText('TERPEL');
  });
});
