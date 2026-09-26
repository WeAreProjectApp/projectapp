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
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the send action requires a resolvable recipient and previews it', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the tab is a subnav entry; the flow under
    // test starts at the row's send action, which IS clicked below)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoHostings(page);

    // Row 2 has neither its own email nor a linked client: nothing to send to.
    await openHostingMenu(page, 2);
    const unavailable = page.getByTestId('hosting-send-billing-2');
    await expect(unavailable).toBeDisabled();
    await expect(unavailable).toContainText('Vincula un cliente con correo');
    await page.getByTestId('hosting-actions-modal').getByRole('button', { name: 'Cerrar' }).click();
    await expect(page.getByTestId('hosting-actions-modal')).toHaveCount(0);

    await chooseHostingAction(page, 1, 'send-billing');

    // The confirm previews exactly where it is going before anything is sent.
    await expect(
      page.getByRole('dialog').getByText('german@korehealths.com', { exact: false }),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Cancelar' }).click();
    await expect(
      page.getByRole('heading', { name: 'Enviar cuenta de cobro' }),
    ).toHaveCount(0);
  });

  test('sending the cuenta de cobro confirms, POSTs and shows the badge', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'send-billing');
    await expect(
      page.getByRole('heading', { name: 'Enviar cuenta de cobro' }),
    ).toBeVisible();

    await page.getByRole('button', { name: 'Enviar al cliente' }).click();

    await expect(page.getByText('Cuenta de cobro enviada')).toBeVisible();
    await expect(page.getByText('Cobro enviado')).toBeVisible();
    expect(calls).toContainEqual({
      apiPath: 'accounting/hostings/1/send-collection-account/',
      method: 'POST',
    });
  });

  test('a failed email keeps the document issued and warns the user', {
    tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [], emailSent: false }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'send-billing');
    await page.getByRole('button', { name: 'Enviar al cliente' }).click();

    await expect(
      page.getByText('Cuenta de cobro emitida, pero el correo falló'),
    ).toBeVisible();
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
