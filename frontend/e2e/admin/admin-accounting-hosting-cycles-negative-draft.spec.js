/**
 * E2E coverage for failure outcomes in the admin hosting-cycle journey.
 * First live validation: GitHub CI run 32582448655 (2026-08-22).
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_ACCOUNTING_HOSTING_CYCLES } from '../helpers/flow-tags.js';
import {
  BACKFILL_CYCLE,
  buildHandler,
  chooseHostingAction,
  gotoHostings,
  openHostingMenu,
} from '../helpers/accounting-hosting-cycles.js';

test.setTimeout(60_000);

test.describe('Admin Accounting Hosting Cycles — negative outcomes', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('a rejected receipt review keeps the payment form retryable', {
    // Bug this catches: a rejected receipt review being presented as a payment
    // or leaving the administrator unable to correct the reference and retry.
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      cycleReceiptError: {
        status: 409,
        detail: 'La referencia ya corresponde a otra imputación.',
      },
    }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'cycles');
    const cycleSubmit = page.getByTestId('cycle-submit');
    await page.getByTestId('cycle-income').selectOption('301');
    await page.getByTestId('hosting-receipt-issuer').fill('Banco de prueba');
    await page.getByTestId('hosting-receipt-reference').fill('TRX-repetida');
    await cycleSubmit.click();

    await expect(
      page.getByRole('alert'),
    ).toBeVisible();
    await expect(page.getByRole('alert')).toContainText('La referencia ya corresponde a otra imputación.');
    await expect(cycleSubmit).toBeEnabled();
    expect(calls).toEqual([expect.objectContaining({
      apiPath: 'accounting/hostings/1/cycle-receipt/',
      method: 'POST',
    })]);
  });

  test('a history-load server failure is surfaced to the administrator', {
    // Bug this catches: a 500 history response rendered as an empty cycle
    // history, hiding an operational failure from the administrator.
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      calls: [],
      loadCyclesError: {
        status: 500,
        detail: 'No fue posible consultar el historial.',
      },
    }));
    await gotoHostings(page);

    await openHostingMenu(page, 1);
    await page.getByTestId('hosting-cycles-1').click();

    await expect(
      page.getByText('No se pudieron cargar los ciclos', { exact: true }),
    ).toBeVisible();
  });
});
