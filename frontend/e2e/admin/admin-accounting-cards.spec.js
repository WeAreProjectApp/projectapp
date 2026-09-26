/**
 * E2E tests for the accounting card snapshots subview.
 *
 * FLOW: admin-accounting-cards
 * Covers: list rendering with debt chip, create via modal (date defaults
 *         to today), the leading three-dot menu (detail/history, edit
 *         prefill, delete with confirmation) and notes opened in a modal.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_ACCOUNTING_CARDS } from '../helpers/flow-tags.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

test.setTimeout(60_000);

function snapshotRow(overrides = {}) {
  return {
    id: 1,
    card_name: 'T.C 0064',
    snapshot_date: '2026-06-17',
    available_amount: '413226.00',
    debt_amount: '7586774.00',
    notes: '',
    created_at: '2026-06-17T10:00:00Z',
    updated_at: '2026-06-17T10:00:00Z',
    ...overrides,
  };
}

const DEFAULT_CATALOG = [
  {
    id: 1,
    name: 'T.C 0064',
    credit_limit: '8000000.00',
    is_active: true,
    statements_since: '2026-05-01',
  },
];

function buildHandler({ rows, calls, catalog = DEFAULT_CATALOG, savedTabs = [] }) {
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
    if (apiPath === 'accounting/card-snapshots/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: rows, meta: {} }),
      };
    }
    if (apiPath === 'accounting/credit-cards/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: catalog, meta: {} }),
      };
    }
    if (apiPath === 'accounting/card-snapshots/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ method, apiPath, body });
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(snapshotRow({ id: 99, ...body })),
      };
    }
    if (/^accounting\/card-snapshots\/\d+\/update\/$/.test(apiPath) && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ method, apiPath, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(snapshotRow({ ...rows[0], ...body })),
      };
    }
    if (/^accounting\/card-snapshots\/\d+\/delete\/$/.test(apiPath) && method === 'DELETE') {
      calls.push({ method, apiPath });
      return { status: 204, contentType: 'application/json', body: '' };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(savedTabs),
      };
    }
    return null;
  };
}

async function gotoCards(page) {
  await page.goto('/panel/accounting/cards', { waitUntil: 'domcontentloaded' });
  await expect(
    page.getByRole('heading', { name: 'Tarjetas', exact: true }),
  ).toBeVisible({ timeout: 25_000 });
}

test.describe('Admin Accounting Cards', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('defaults the card filter to the registered catalog cards', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // T.C 0655 exists only in old snapshots — not in the catalog.
    await mockApi(page, buildHandler({
      rows: [
        snapshotRow(),
        snapshotRow({ id: 2, snapshot_date: '2026-07-01', debt_amount: '4150954.00' }),
        snapshotRow({ id: 3, card_name: 'T.C 0655', snapshot_date: '2026-06-20', debt_amount: '1000000.00' }),
      ],
      calls: [],
    }));
    await gotoCards(page);

    // Default view: only the registered card's snapshots, with the filter
    // visible as a removable chip (not a silent cut).
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByTestId('accounting-row-2')).toBeVisible();
    await expect(page.getByTestId('accounting-row-3')).toHaveCount(0);
    await expect(page.getByTestId('accounting-filter-chip')).toHaveText(/T\.C 0064/);
    await expect(page.getByTestId('cards-total-debt')).toContainText('4.150.954');

    // Clearing the filter surfaces the historical card again.
    await page.getByTestId('accounting-filter-reset').click();
    await expect(page.getByTestId('accounting-row-3')).toBeVisible();
    // Latest per card: 4.150.954 (T.C 0064, jul 1) + 1.000.000 (T.C 0655).
    await expect(page.getByTestId('cards-total-debt')).toContainText('5.150.954');
  });

  test('card filter options combine the catalog and historical names', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [snapshotRow({ card_name: 'T.C 0655' })],
      calls: [],
      catalog: [
        ...DEFAULT_CATALOG,
        // Registered but with no snapshots yet: filterable anyway.
        {
          id: 2,
          name: 'T.C 9999',
          credit_limit: '2000000.00',
          is_active: true,
          statements_since: null,
        },
      ],
    }));
    await gotoCards(page);

    await page.getByRole('button', { name: /Filtros/ }).click();
    // ^ anchor: the preselection chips are named "Quitar filtro Tarjeta: …"
    // and would otherwise match too.
    await page
      .getByTestId('accounting-filter-panel')
      .getByRole('button', { name: /^Tarjeta/ })
      .click();

    await expect(page.getByRole('checkbox', { name: 'T.C 0064' })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'T.C 9999' })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'T.C 0655' })).toBeVisible();
  });

  test('a saved tab in the URL wins over the default card filter', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      rows: [
        snapshotRow(),
        snapshotRow({ id: 3, card_name: 'T.C 0655', snapshot_date: '2026-06-20', debt_amount: '1000000.00' }),
      ],
      calls: [],
      savedTabs: [{ id: 7, name: 'Deudas altas', filters: { debtMin: '900000' } }],
    }));
    await page.goto('/panel/accounting/cards?accounting_cardsTab=7', {
      waitUntil: 'domcontentloaded',
    });
    await expect(
      page.getByRole('heading', { name: 'Tarjetas', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    // The tab's own filters apply; the catalog preselection must not
    // overwrite them, so the unregistered card's row stays visible.
    await expect(page.getByTestId('accounting-row-3')).toBeVisible();
    await expect(
      page.getByTestId('accounting-filter-chip').filter({ hasText: 'T.C 0064' }),
    ).toHaveCount(0);
  });

  test('the % column shows each snapshot\'s credit utilization and sorts', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (navigation into Tarjetas is covered by the
    // display specs above; this one pins the weight column inside the tab)
    await mockApi(page, buildHandler({
      rows: [
        snapshotRow({ debt_amount: '7586774.00' }),
        snapshotRow({ id: 2, snapshot_date: '2026-07-01', debt_amount: '4150954.00' }),
      ],
      calls: [],
    }));
    await gotoCards(page);
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();

    // Utilization = row debt / the card's credit limit from the catalog
    // (8.000.000 for T.C 0064): 7.586.774 → 94,8%, 4.150.954 → 51,9%.
    const row1 = page.getByTestId('accounting-row-1');
    const row2 = page.getByTestId('accounting-row-2');
    await expect(row1).toContainText('94,8%');
    await expect(row2).toContainText('51,9%');

    // Sorting by utilization ascending puts the emptier snapshot first.
    await page.getByTestId('accounting-sort-weight_pct').click();
    await page.getByTestId('accounting-sort-weight_pct').click();
    const firstRow = page.locator('[data-testid^="accounting-row-"]').first();
    await expect(firstRow).toHaveAttribute('data-testid', 'accounting-row-2');
  });

  test('creates a snapshot with today as the default date', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [], calls }));
    await gotoCards(page);

    await page.getByTestId('cards-new-button').click();
    await expect(
      page.getByRole('heading', { name: 'Nuevo Registro de Tarjeta' }),
    ).toBeVisible();

    const dateValue = await page.locator('form input[type="date"]').inputValue();
    expect(dateValue).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    // Single catalog card: the dropdown preselects it.
    await expect(page.getByTestId('card-snapshot-card-select')).toHaveValue('T.C 0064');
    await page.locator('form input[inputmode="numeric"]').fill('500000');
    // Debt is server-computed; the form only previews it.
    await expect(page.getByTestId('card-snapshot-debt-preview')).toContainText('7.500.000');
    await page.getByTestId('card-snapshot-form-submit').click();

    await expect(page.getByText('Registro de tarjeta creado')).toBeVisible();
    expect(calls).toHaveLength(1);
    expect(calls[0].body.card_name).toBe('T.C 0064');
    expect(calls[0].body.debt_amount).toBeUndefined();
    expect(Number(calls[0].body.available_amount)).toBe(500000);
  });

  test('edit prefills and PATCHes; delete asks for confirmation', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [snapshotRow()], calls }));
    await gotoCards(page);

    await page.getByTestId('cards-actions-1').click();
    await page.getByTestId('cards-action-edit-1').click();
    await expect(
      page.getByRole('heading', { name: 'Editar Registro de Tarjeta' }),
    ).toBeVisible();
    await expect(page.getByTestId('card-snapshot-card-select')).toHaveValue('T.C 0064');
    await page.locator('form input[inputmode="numeric"]').fill('1000000');
    await page.getByTestId('card-snapshot-form-submit').click();
    await expect(page.getByText('Registro de tarjeta actualizado')).toBeVisible();
    expect(calls[0].method).toBe('PATCH');

    await page.getByTestId('cards-actions-1').click();
    await page.getByTestId('cards-action-delete-1').click();
    await expect(page.getByText('Eliminar registro de tarjeta')).toBeVisible();
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByText('Registro de tarjeta eliminado')).toBeVisible();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(true);
  });

  // The cupo caps the disponible: an edit that exceeds it is refused before
  // anything is sent, with the reason beside the field.
  test('an edit whose disponible exceeds the cupo is refused with its reason', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ rows: [snapshotRow()], calls }));
    await gotoCards(page);

    await page.getByTestId('cards-actions-1').click();
    await page.getByTestId('cards-action-edit-1').click();
    await expect(
      page.getByRole('heading', { name: 'Editar Registro de Tarjeta' }),
    ).toBeVisible();
    await page.locator('form input[inputmode="numeric"]').fill('9000000');

    await expect(page.getByTestId('card-snapshot-debt-preview'))
      .toHaveText('El disponible no puede superar el cupo de la tarjeta.');
    await expect(page.getByTestId('card-snapshot-form-submit')).toBeDisabled();
    expect(calls).toHaveLength(0);
  });

  // Bug caught: the snapshot actions lived in a trailing "Acciones" column,
  // with a loose history button, instead of the panel's leading three-dot menu.
  test('the leading three-dot menu owns every snapshot action', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (navigation into Tarjetas is covered by the
    // display specs above; this one pins the row action contract)
    await mockApi(page, buildHandler({ rows: [snapshotRow()], calls: [] }));
    await gotoCards(page);

    const row = page.getByTestId('accounting-row-1');
    await expect(row).toContainText('T.C 0064');
    // The actions track leads the table and names itself only for assistive tech.
    const actionsHeader = page.getByRole('columnheader', { name: 'Acciones' });
    await expect(actionsHeader).toHaveText('');
    const actionsBox = await actionsHeader.boundingBox();
    const cardBox = await page.getByRole('columnheader', { name: 'Tarjeta' }).boundingBox();
    expect(actionsBox.x).toBeLessThan(cardBox.x);
    await expect(row.getByTestId('accounting-actions-cell-1').getByRole('button')).toHaveCount(1);
    await expect(page.getByTestId('accounting-edit-1')).toHaveCount(0);

    await page.getByTestId('cards-actions-1').click();
    const menu = page.getByTestId('cards-actions-modal');
    await expect(menu).toContainText('T.C 0064');
    await expect(menu.getByRole('button', { name: 'Detalle e historial' })).toBeVisible();
    await expect(menu.getByRole('button', { name: 'Editar' })).toBeVisible();
    await expect(menu.getByRole('button', { name: 'Eliminar' })).toBeVisible();

    await menu.getByRole('button', { name: 'Detalle e historial' }).click();
    await expect(page.getByRole('heading', { name: 'Detalle del registro' })).toBeVisible();
    await expect(page.getByTestId('history-record-modal')).toContainText('7586774');
  });

  // Bug caught: a long note was printed inside its cell and stretched the row.
  test('a long note opens in a modal from its Ver nota button', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (navigation into Tarjetas is covered by the
    // display specs above; this one pins how the notes column renders)
    await mockApi(page, buildHandler({
      rows: [
        snapshotRow({
          notes: 'Pago mínimo cubierto el viernes.\nFalta conciliar la cuota de octubre con el extracto.',
        }),
        snapshotRow({ id: 2, snapshot_date: '2026-07-01', debt_amount: '4150954.00' }),
      ],
      calls: [],
    }));
    await gotoCards(page);

    const withNote = page.getByTestId('accounting-row-1');
    const withoutNote = page.getByTestId('accounting-row-2');
    await expect(withNote).toContainText('T.C 0064');
    await expect(withNote).not.toContainText('Falta conciliar');
    await expect(withoutNote.getByRole('button', { name: /^Ver nota/ })).toHaveCount(0);

    await withNote.getByRole('button', { name: /^Ver nota/ }).click();
    const note = page.getByTestId('accounting-note-body');
    await expect(note).toContainText('Pago mínimo cubierto el viernes.');
    await expect(note).toContainText('Falta conciliar la cuota de octubre con el extracto.');
    await expect(page.getByTestId('accounting-note-modal')).toContainText('T.C 0064');

    await page.getByTestId('accounting-note-modal').getByRole('button', { name: 'Cerrar' }).click();
    await expect(page.getByTestId('accounting-note-modal')).toHaveCount(0);
  });

  // Bug caught: the fixed layout kept the share of the columns a phone hides,
  // so Tarjeta and Deuda stopped short of a blank band on the right.
  test('the cards table leaves no blank band on a phone', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-deep-link (navigation into Tarjetas is covered by the
    // display specs above; this one pins the compact table geometry)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildHandler({ rows: [snapshotRow()], calls: [] }));
    await gotoCards(page);

    const row = page.getByTestId('accounting-row-1');
    await expect(row).toContainText('T.C 0064');
    const table = row.locator('xpath=ancestor::table');
    await expectNoBlankBand(table);
    expect(await table.locator('..').evaluate((element) => element.scrollWidth <= element.clientWidth))
      .toBe(true);
    const kebab = await page.getByTestId('cards-actions-1').boundingBox();
    expect(Math.round(kebab.width)).toBe(44);
    expect(Math.round(kebab.height)).toBe(44);

    await page.getByTestId('cards-actions-1').click();
    await expect(page.getByTestId('cards-actions-modal')).toContainText('T.C 0064');
  });

  test('the cards table leaves no blank band on a portrait tablet', {
    tag: [...ADMIN_ACCOUNTING_CARDS, '@role:admin', '@outcome:display', '@responsive:accounting'],
  }, async ({ page }) => {
    // quality: allow-deep-link (navigation into Tarjetas is covered by the
    // display specs above; this one pins the portrait table geometry)
    await page.setViewportSize({ width: 835, height: 1195 });
    await mockApi(page, buildHandler({ rows: [snapshotRow()], calls: [] }));
    await gotoCards(page);

    const row = page.getByTestId('accounting-row-1');
    await expect(row).toContainText('T.C 0064');
    await expectNoBlankBand(row.locator('xpath=ancestor::table'));

    await page.getByTestId('cards-actions-1').click();
    await expect(page.getByTestId('cards-actions-modal')).toContainText('T.C 0064');
  });
});
