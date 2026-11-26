/**
 * E2E tests for the hosting row actions on /panel/accounting/hostings.
 *
 * FLOWS: admin-accounting-hosting-billing, admin-accounting-hosting-cycles
 * Covers: the row menu's cuenta de cobro send (email gate, confirm preview,
 *         success + email-failure toasts, "Cobro enviado" badge) and the
 *         cycles modal (history with backfill badge, register payment,
 *         delete cycle with confirm).
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { openHostingBillingList } from '../helpers/accounting-hosting-row-billing.js';
import {
  ADMIN_ACCOUNTING_HOSTING_BILLING,
  ADMIN_ACCOUNTING_HOSTING_CYCLES,
} from '../helpers/flow-tags.js';
import {
  BACKFILL_CYCLE,
  buildHandler,
  chooseHostingAction,
  gotoHostings,
  openHostingMenu,
} from '../helpers/accounting-hosting-cycles.js';

test.setTimeout(60_000);

test.describe('Admin Accounting Hosting Billing', () => {
  test('the send action shows the reviewed period before emission', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the locale-prefixed Panel home is test setup; the user enters Hostings through its sidebar)
    const writes = await openHostingBillingList(page);

    await openHostingMenu(page, 3);
    const unavailable = page.getByTestId('hosting-send-billing-3');
    await expect(unavailable).toBeDisabled();
    await expect(unavailable).toContainText('Vincula un cliente con correo');
    const dialog = page.getByRole('dialog').filter({ has: page.getByTestId('hosting-actions-modal') });
    await dialog.getByRole('button', { name: 'Cerrar' }).click();
    await expect(page.getByTestId('hosting-actions-modal')).toHaveCount(0);

    await chooseHostingAction(page, 1, 'send-billing');

    // The confirm previews exactly where it is going before anything is sent.
    await expect(
      page.getByRole('dialog').getByText('alfa@example.invalid', { exact: false }),
    ).toBeVisible();
    await expect(page.getByTestId('hosting-period-summary')).toContainText('2026-04-01 — 2026-06-30');
    await page.getByRole('dialog').getByRole('button', { name: /^(Cancelar|Cancel)$/ }).click();
    await expect(
      page.getByRole('heading', { name: 'Enviar cuenta de cobro' }),
    ).toHaveCount(0);
    expect(writes).toEqual([]);
  });

  test('sending the cuenta de cobro confirms, POSTs and shows the badge', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const writes = await openHostingBillingList(page);

    await chooseHostingAction(page, 1, 'send-billing');
    await expect(
      page.getByRole('heading', { name: 'Enviar cuenta de cobro' }),
    ).toBeVisible();

    await page.getByRole('button', { name: 'Enviar al cliente' }).click();

    await expect(page.getByText('Cuenta de cobro enviada')).toBeVisible();
    await expect(page.getByText('Cobro enviado')).toBeVisible();
    expect(writes).toEqual([{
      apiPath: 'accounting/hostings/1/send-collection-account/',
      method: 'POST',
      body: { hosting_payment_id: 48, period_version: 'review-1' },
    }]);
  });

  test('a failed email keeps the document issued and warns the user', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await openHostingBillingList(page, { emailSent: false });

    await chooseHostingAction(page, 1, 'send-billing');
    await page.getByRole('button', { name: 'Enviar al cliente' }).click();

    await expect(
      page.getByText('Cuenta de cobro emitida, pero el correo falló'),
    ).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toContainText('Cobro enviado');
  });
});

test.describe('Admin Accounting Hosting Cycles', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('opens the history with the reconciled period summary', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(
      page,
      buildHandler({ calls: [], cycles: [BACKFILL_CYCLE] }),
    );
    // quality: allow-deep-link (the authenticated panel is test setup; this
    // display flow navigates to Hostings through the visible sidebar below)
    await gotoHostings(page);

    await openHostingMenu(page, 1);
    await page.getByTestId('hosting-cycles-1').click();

    await expect(
      page.getByRole('heading', { name: 'Ciclos de pago — German — Kore' }),
    ).toBeVisible();
    await expect(page.getByText('histórico × 3')).toBeVisible();
    await expect(page.getByText('Extender vigencia')).toBeVisible();
    await expect(page.getByTestId('hosting-period-summary')).toContainText('2026-09-03 — 2027-03-02');
  });

  test('registers an evidenced cycle payment after review', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, cycles: [BACKFILL_CYCLE] }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'cycles');
    // Bug this catches: creating an economic effect before the operator reviews
    // the selected expected income and its stable receipt reference.
    await page.getByTestId('cycle-income').selectOption('301');
    await page.getByTestId('cycle-amount').fill('600000');
    await page.getByTestId('hosting-receipt-issuer').fill('Banco de prueba');
    await page.getByTestId('hosting-receipt-reference').fill('TRX-600000');
    await page.getByTestId('cycle-submit').click();

    await expect(page.getByTestId('cycle-receipt-review')).toContainText('Confirmar registro del pago');
    await expect(page.getByTestId('cycle-submit')).toHaveText('Confirmar pago');
    await page.getByTestId('cycle-submit').click();
    await expect(page.getByRole('row', { name: /2026-11-26.*\$600\.000 COP/ })).toBeVisible();
    const receiptCalls = calls.filter((call) => call.apiPath === 'accounting/hostings/1/cycle-receipt/');
    expect(receiptCalls).toHaveLength(2);
    expect(receiptCalls[1].body).toEqual(expect.objectContaining({
      amount: '600000', advance_validity: true, preview_hash: 'receipt-preview-v1',
      hosting_receipt: expect.objectContaining({ issuer: 'Banco de prueba', reference: 'TRX-600000' }),
    }));
  });

  test('cancels the receipt review without registering a payment', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'cycles');
    await page.getByTestId('cycle-income').selectOption('301');
    await page.getByTestId('hosting-receipt-issuer').fill('Banco de prueba');
    await page.getByTestId('hosting-receipt-reference').fill('TRX-cancelado');
    await page.getByTestId('cycle-submit').click();
    await page.getByRole('button', { name: 'Cancelar revisión' }).click();

    await expect(page.getByTestId('cycle-submit')).toHaveText('Revisar pago de ciclo');
    expect(calls.filter((call) => call.apiPath === 'accounting/hostings/1/cycle-receipt/')).toHaveLength(1);
  });

  test('cancels next expected income after a payment without removing that payment', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, cycles: [BACKFILL_CYCLE] }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'cycles');
    await page.getByTestId('cycle-income').selectOption('301');
    await page.getByTestId('hosting-receipt-issuer').fill('Banco de prueba');
    await page.getByTestId('hosting-receipt-reference').fill('TRX-a-cancelar');
    await page.getByTestId('cycle-submit').click();
    await page.getByTestId('cycle-submit').click();
    await expect(page.getByRole('row', { name: /2026-11-26.*\$550\.002 COP/ })).toBeVisible();

    // Bug this catches: dismissing the next-income proposal after recording
    // the receipt must not create the income or remove the payment itself.
    await page.getByTestId('cycle-next-income').click();
    await expect(page.getByTestId('hosting-next-income')).toContainText('2027-03-03 — 2027-09-02');
    await page.getByRole('button', { name: 'Cancelar', exact: true }).click();

    expect(calls.filter((call) => call.apiPath === 'accounting/hostings/1/next-income/')).toHaveLength(0);
    await chooseHostingAction(page, 1, 'cycles');
    await expect(page.getByRole('row', { name: /2026-11-26.*\$550\.002 COP/ })).toBeVisible();
  });

  test('creates the next expected income from the hosting menu', {
    tag: ['@flow:admin-accounting-hosting-next-income', '@module:admin', '@priority:P2', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoHostings(page);

    // Bug this catches: using the calendar day or a second click to create a
    // duplicate instead of the next contractual period shown for this service.
    await chooseHostingAction(page, 1, 'next-income');
    await expect(page.getByTestId('hosting-next-income')).toContainText('2027-03-03 — 2027-09-02');
    await page.getByTestId('hosting-next-confirm').click();

    await expect(page.getByText('Ingreso esperado registrado #302.', { exact: true })).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/hostings/1/next-income/', method: 'POST', body: { version: 'next-income-v1' },
    });
  });

  test('blocks next expected income when the reconciled period is not eligible', {
    tag: ['@flow:admin-accounting-hosting-next-income', '@module:admin', '@priority:P2', '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      nextIncomeError: {
        status: 409,
        detail: 'El período acreditado aún no permite crear el siguiente ingreso.',
      },
    }));
    await gotoHostings(page);

    // Bug this catches: exposing a second expected income when the prior
    // reconciled period has a business blocker.
    await chooseHostingAction(page, 1, 'next-income');

    await expect(page.getByRole('alert')).toContainText(
      'El período acreditado aún no permite crear el siguiente ingreso.',
    );
    await expect(page.getByTestId('hosting-next-confirm')).toHaveCount(0);
    expect(calls.filter((call) => call.apiPath === 'accounting/hostings/1/next-income/')).toHaveLength(0);
  });

  test('deletes a cycle after the confirm warns about recalculation', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, cycles: [BACKFILL_CYCLE] }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'cycles');
    await page.getByLabel('Eliminar ciclo').click();
    await expect(
      page.getByRole('heading', { name: 'Eliminar ciclo' }),
    ).toBeVisible();

    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Ciclo eliminado')).toBeVisible();
    await expect(
      page.getByText('Sin ciclos registrados todavía.'),
    ).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/hostings/1/cycles/10/delete/',
      method: 'DELETE',
    });
  });
});
