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

  test('a rejected cycle registration keeps the form retryable', {
    // Bug this catches: a failed cycle create being presented as success or
    // leaving the administrator unable to correct the form and retry.
    tag: [...ADMIN_ACCOUNTING_HOSTING_CYCLES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({
      calls,
      cycles: [BACKFILL_CYCLE],
      createCycleError: {
        status: 400,
        detail: 'El monto debe ser mayor a cero.',
      },
    }));
    await gotoHostings(page);

    await chooseHostingAction(page, 1, 'cycles');
    const cycleSubmit = page.getByTestId('cycle-submit');
    await expect(cycleSubmit).toBeEnabled();
    await cycleSubmit.click();

    await expect(
      page.getByText('No se pudo registrar el ciclo', { exact: true }),
    ).toBeVisible();
    await expect(cycleSubmit).toBeEnabled();
    expect(calls).toEqual([expect.objectContaining({
      apiPath: 'accounting/hostings/1/cycles/create/',
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
