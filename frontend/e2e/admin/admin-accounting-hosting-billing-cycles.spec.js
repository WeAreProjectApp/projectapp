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

  test('opens the history with the consolidated backfill badge', {
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
  });

  test('registers a cycle payment from the prefilled form', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, cycles: [BACKFILL_CYCLE] }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'cycles');
    await expect(page.getByTestId('cycle-modality')).toHaveValue('semiannual');
    await expect(page.getByTestId('cycle-modality').locator('option')).toHaveText([
      'Trimestral', 'Semestral', 'Cada 9 meses',
    ]);
    await page.getByTestId('cycle-amount').fill('600000');
    await page.getByTestId('cycle-submit').click();

    await expect(page.getByText('Pago de ciclo registrado')).toBeVisible();
    await expect(page.getByText('$600.000')).toBeVisible();
    const createCall = calls.find(
      (call) => call.apiPath === 'accounting/hostings/1/cycles/create/',
    );
    expect(createCall.body.advance_validity).toBe(true);
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
