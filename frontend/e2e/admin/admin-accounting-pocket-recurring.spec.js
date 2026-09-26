/**
 * E2E tests for the pocket ledger and recurring payments subviews.
 *
 * FLOWS: admin-accounting-pocket, admin-accounting-recurring
 * Covers: pocket balance card, running-balance ledger, linked-movement
 *         editing (ledger prefill + locked direction); recurring totals
 *         cards and the server-owned COP-equivalent preview in the modal.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_ACCOUNTING_POCKET,
  ADMIN_ACCOUNTING_RECURRING,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const POCKET_ROWS = [
  {
    id: 1,
    concept: 'Vastago (Fase 1) - Inicio 40%',
    movement_date: '2026-04-29',
    direction: 'in',
    direction_label: 'Ingreso',
    amount: '2123000.00',
    is_auto_managed: true,
    linked_income_id: 11,
    linked_expense_id: null,
    linked_ledger: 'company',
    notes: '',
    created_at: '2026-04-29T10:00:00Z',
    updated_at: '2026-04-29T10:00:00Z',
  },
  {
    id: 2,
    concept: 'Pago T.C Rappi',
    movement_date: '2026-05-06',
    direction: 'out',
    direction_label: 'Egreso',
    amount: '2272000.00',
    is_auto_managed: false,
    linked_income_id: null,
    linked_expense_id: null,
    linked_ledger: null,
    notes: '',
    created_at: '2026-05-06T10:00:00Z',
    updated_at: '2026-05-06T10:00:00Z',
  },
];

const RECURRING_CATEGORIES = [
  { id: 1, name: 'Suscripciones de IA', slug: 'suscripciones-de-ia', order: 0, payment_count: 2 },
  { id: 2, name: 'Arquitectura e infraestructura', slug: 'infra', order: 1, payment_count: 1 },
];

function recurringRow(overrides) {
  return {
    price: '200.00',
    currency: 'USD',
    cop_equivalent: '800000.00',
    payment_method: 'credit_card',
    payment_method_label: 'T.C',
    frequency: 'monthly',
    frequency_label: 'Mensual',
    billing_day: 8,
    cost_type: 'fixed',
    cost_type_label: 'Fijo',
    monthly_price: '200.00',
    monthly_cop_cost: '800000.00',
    is_active: true,
    is_archived: false,
    archived_at: null,
    cycle_anchor_date: '2026-01-08',
    reminders_muted: false,
    reminders_muted_until: null,
    reminders_effectively_muted: false,
    notes: '',
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
    ...overrides,
  };
}

const FREQUENCY_MONTHS = {
  monthly: 1,
  bimonthly: 2,
  quarterly: 3,
  four_monthly: 4,
  semiannual: 6,
  annual: 12,
  biennial: 24,
  triennial: 36,
};

function deriveRecurring(row, rate = 4000) {
  const months = row.frequency === 'custom'
    ? Number(row.custom_months || 1)
    : (FREQUENCY_MONTHS[row.frequency] || 1);
  const price = Number(row.price || 0);
  const copEquivalent = row.currency === 'USD' ? price * rate : price;
  return {
    ...row,
    price: price.toFixed(2),
    cop_equivalent: copEquivalent.toFixed(2),
    monthly_price: (price / months).toFixed(2),
    monthly_cop_cost: (copEquivalent / months).toFixed(2),
    frequency_label: row.frequency === 'custom'
      ? `Cada ${months} meses`
      : ({
        monthly: 'Mensual', bimonthly: 'Bimestral', quarterly: 'Trimestral',
        four_monthly: 'Cuatrimestral', semiannual: 'Semestral', annual: 'Anual',
        biennial: 'Cada 2 años', triennial: 'Cada 3 años',
      }[row.frequency] || row.frequency_label),
  };
}

// Ordered the way the API returns them: category order, then manual slot.
const RECURRING_ROWS = [
  recurringRow({
    id: 1, name: 'Claude Code 20x', category: 1,
    category_name: 'Suscripciones de IA', order: 0,
  }),
  recurringRow({
    id: 2, name: 'Chat-GPT', category: 1, category_name: 'Suscripciones de IA',
    order: 1, price: '20.00', cop_equivalent: '80000.00',
    monthly_price: '20.00', monthly_cop_cost: '80000.00',
  }),
  // A biennial charge: the raw price and the monthly cost differ by 24x, which
  // is the whole point of the normalized columns.
  recurringRow({
    id: 3, name: 'Hostinger', category: 2,
    category_name: 'Arquitectura e infraestructura', order: 0,
    price: '789600.00', currency: 'COP', cop_equivalent: '789600.00',
    frequency: 'biennial', frequency_label: 'Cada 2 años',
    monthly_price: '32900.00', monthly_cop_cost: '32900.00',
  }),
];

/**
 * One row per shape the monthly columns have to normalize: a plain monthly
 * charge, an every-two-years one, an intermediate cycle from the catalog and a
 * custom "cada N meses". All four are priced so their monthly equivalent is a
 * round number, which makes a wrong divisor impossible to miss.
 */
const MIXED_FREQUENCY_ROWS = [
  recurringRow({
    id: 1, name: 'Claude Code 20x', category: 1,
    category_name: 'Suscripciones de IA', order: 0,
  }),
  recurringRow({
    id: 3, name: 'Hostinger', category: 2,
    category_name: 'Arquitectura e infraestructura', order: 0,
    price: '789600.00', currency: 'COP', cop_equivalent: '789600.00',
    frequency: 'biennial', frequency_label: 'Cada 2 años',
    monthly_price: '32900.00', monthly_cop_cost: '32900.00',
  }),
  recurringRow({
    id: 4, name: 'Figma equipo', category: 2,
    category_name: 'Arquitectura e infraestructura', order: 1,
    price: '300000.00', currency: 'COP', cop_equivalent: '300000.00',
    frequency: 'quarterly', frequency_label: 'Trimestral',
    monthly_price: '100000.00', monthly_cop_cost: '100000.00',
  }),
  recurringRow({
    id: 5, name: 'Mantenimiento servidor', category: 2,
    category_name: 'Arquitectura e infraestructura', order: 2,
    price: '500000.00', currency: 'COP', cop_equivalent: '500000.00',
    frequency: 'custom', frequency_label: 'Cada 5 meses', custom_months: 5,
    monthly_price: '100000.00', monthly_cop_cost: '100000.00',
  }),
];

/**
 * Same rows, but the second one is an outlier in every column that can hold one:
 * a name well above average, an amount with more digits, a payment method wider
 * than the "T.C" every other row shows, a two-digit billing day and "Inactivo"
 * against "Activo". Whatever the table does with these must not move a column.
 */
const OUTLIER_ROWS = [
  recurringRow({
    id: 1, name: 'Claude Code 20x', category: 1,
    category_name: 'Suscripciones de IA', order: 0,
  }),
  recurringRow({
    id: 2, name: 'Google Ads - Empresa Marketing Digital', category: 1,
    category_name: 'Suscripciones de IA', order: 1,
    price: '1234567.00', currency: 'COP', cop_equivalent: '1234567.00',
    monthly_price: '1234567.00', monthly_cop_cost: '1234567.00',
    payment_method: 'cash', payment_method_label: 'Efectivo',
    billing_day: 28, is_active: false,
  }),
];

function buildHandler({
  calls,
  reorderStatus = 200,
  duplicateStatus = 200,
  rows = RECURRING_ROWS,
}) {
  let currentRows = rows.map((row) => ({ ...row }));
  return async ({ route, apiPath, method }) => {
    if (apiPath.startsWith('accounting/recurring-categories/') && apiPath.endsWith('/delete/')) {
      calls.push({ apiPath, method });
      // The catalog refuses to drop a category still in use.
      return {
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'La categoría tiene 2 pago(s) recurrente(s). '
            + 'Muévelos a otra categoría antes de borrarla.',
          payment_count: 2,
        }),
      };
    }
    if (apiPath === 'accounting/recurring-categories/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: RECURRING_CATEGORIES, meta: {} }),
      };
    }
    if (apiPath === 'accounting/recurring/reorder/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      return {
        status: reorderStatus,
        contentType: 'application/json',
        body: reorderStatus === 200
          ? JSON.stringify({ reordered: 3 })
          : JSON.stringify({ error: 'No se pudo guardar' }),
      };
    }
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
          results: POCKET_ROWS,
          meta: { balance: '-149000.00' },
        }),
      };
    }
    if (apiPath === 'accounting/recurring/' && method === 'GET') {
      const scope = new URL(route.request().url()).searchParams.get('archive_scope') || 'current';
      const scopedRows = currentRows.filter((row) => (
        scope === 'archived' ? row.is_archived : !row.is_archived
      ));
      const monthlyTotal = scopedRows
        .filter((row) => row.is_active && !row.is_archived)
        .reduce((total, row) => total + Number(row.monthly_cop_cost || 0), 0);
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: scopedRows,
          meta: {
            monthly_cop_total: monthlyTotal.toFixed(2),
            usd_exchange_rate: '4000.00',
          },
        }),
      };
    }
    const duplicateMatch = apiPath.match(/^accounting\/recurring\/(\d+)\/duplicate-draft\/$/);
    if (duplicateMatch && method === 'GET') {
      const id = Number(duplicateMatch[1]);
      const original = currentRows.find((row) => row.id === id);
      calls.push({ apiPath, method });
      return {
        status: duplicateStatus,
        contentType: 'application/json',
        body: duplicateStatus === 200 ? JSON.stringify({
          name: original.name,
          price: original.price,
          currency: original.currency,
          payment_method: original.payment_method,
          frequency: original.frequency,
          custom_months: original.custom_months || null,
          billing_day: original.billing_day,
          cycle_anchor_date: '2026-09-08',
          cost_type: original.cost_type,
          category: original.category,
          is_active: true,
          notes: '',
          schedule_requires_anchor: false,
          schedule_notice: 'La fecha de referencia se recalculó con la próxima ocurrencia del original.',
        }) : JSON.stringify({ error: 'No se pudo calcular la próxima fecha.' }),
      };
    }
    const stateMatch = apiPath.match(/^accounting\/recurring\/(\d+)\/state\/$/);
    if (stateMatch && method === 'POST') {
      const id = Number(stateMatch[1]);
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      const updated = {
        ...currentRows.find((row) => row.id === id),
        is_active: body.is_active,
      };
      currentRows = currentRows.map((row) => row.id === id ? updated : row);
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updated) };
    }
    const archiveMatch = apiPath.match(/^accounting\/recurring\/(\d+)\/archive\/$/);
    if (archiveMatch && method === 'POST') {
      const id = Number(archiveMatch[1]);
      calls.push({ apiPath, method });
      const updated = {
        ...currentRows.find((row) => row.id === id),
        is_active: false,
        is_archived: true,
        archived_at: '2026-08-27T12:00:00Z',
      };
      currentRows = currentRows.map((row) => row.id === id ? updated : row);
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updated) };
    }
    const restoreMatch = apiPath.match(/^accounting\/recurring\/(\d+)\/restore\/$/);
    if (restoreMatch && method === 'POST') {
      const id = Number(restoreMatch[1]);
      calls.push({ apiPath, method });
      const updated = {
        ...currentRows.find((row) => row.id === id),
        is_active: false,
        is_archived: false,
        archived_at: null,
      };
      currentRows = currentRows.map((row) => row.id === id ? updated : row);
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updated) };
    }
    const muteMatch = apiPath.match(/^accounting\/recurring\/(\d+)\/reminders\/mute\/$/);
    if (muteMatch && method === 'POST') {
      const id = Number(muteMatch[1]);
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      const updated = {
        ...currentRows.find((row) => row.id === id),
        reminders_muted: body.muted,
        reminders_muted_until: body.muted ? (body.until || null) : null,
        reminders_effectively_muted: body.muted,
      };
      currentRows = currentRows.map((row) => row.id === id ? updated : row);
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updated) };
    }
    if (apiPath === 'accounting/recurring/bulk-action/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      const ids = new Set(body.recurring_ids);
      const results = [];
      currentRows = currentRows.map((row) => {
        if (!ids.has(row.id)) return row;
        const updated = {
          ...row,
          is_active: body.action === 'activate',
          is_archived: body.action === 'archive' ? true : row.is_archived,
          archived_at: body.action === 'archive' ? '2026-08-27T12:00:00Z' : row.archived_at,
        };
        results.push(updated);
        return updated;
      });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ updated: results.length, results }),
      };
    }
    const updateMatch = apiPath.match(/^accounting\/recurring\/(\d+)\/update\/$/);
    if (updateMatch && method === 'PATCH') {
      const id = Number(updateMatch[1]);
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      const current = currentRows.find((row) => row.id === id);
      const updated = deriveRecurring({ ...current, ...body });
      currentRows = currentRows.map((row) => row.id === id ? updated : row);
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(updated),
      };
    }
    if (apiPath === 'accounting/recurring/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      const created = deriveRecurring({ ...RECURRING_ROWS[0], id: 99, ...body });
      currentRows = [created, ...currentRows];
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(created),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

/**
 * Manual mouse drag — sortablejs does not react to Playwright's dragTo.
 *
 * Two things this has to get right:
 * - Scroll first. `page.mouse` takes raw viewport coordinates and does not
 *   auto-scroll the way `locator.click()` does, so a row below the fold
 *   receives no events at all and the drag silently does nothing.
 * - Drop just inside the target's top edge. Sortable only reorders once the
 *   pointer crosses the neighbour's midpoint, and aiming past the element
 *   entirely drops outside the list, which reverts.
 */
async function dragAbove(page, sourceHandle, targetRow) {
  await sourceHandle.scrollIntoViewIfNeeded();
  const sourceBox = await sourceHandle.boundingBox();
  const targetBox = await targetRow.boundingBox();
  const x = targetBox.x + targetBox.width / 2;
  const startX = sourceBox.x + sourceBox.width / 2;
  const startY = sourceBox.y + sourceBox.height / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  // A small first move is what makes sortable enter drag mode.
  await page.mouse.move(startX, startY - 6, { steps: 4 });
  await page.mouse.move(x, targetBox.y + targetBox.height / 2, { steps: 10 });
  // Stay inside the target row, just above its midpoint.
  await page.mouse.move(x, targetBox.y + 3, { steps: 10 });
  await page.mouse.up();
}

/**
 * Reach a subview the way an operator does — through the accounting subnav —
 * rather than deep-linking, so the test also proves the tab is reachable.
 */
async function openSubview(page, key) {
  const entry = key === 'recurring' ? 'pocket' : 'recurring';
  await page.goto(`/panel/accounting/${entry}`, { waitUntil: 'domcontentloaded' });
  await page.getByTestId(`accounting-subnav-${key}`).click();
}

async function chooseRecurringAction(page, id, action) {
  await page.getByTestId(`recurring-actions-${id}`).click();
  await expect(page.getByTestId('recurring-actions-modal')).toBeVisible();
  await page.getByTestId(`recurring-action-${action}-${id}`).click();
}

test.describe('Admin Accounting Pocket & Recurring', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('pocket balance card shows the ledger balance', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await openSubview(page, 'pocket');

    await expect(
      page.getByRole('heading', { name: 'Bolsillo ProjectApp', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('pocket-balance')).toBeVisible();
    await expect(page.getByText('Saldo del bolsillo')).toBeVisible();
  });

  test('ledger renders movements with a running balance column', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await openSubview(page, 'pocket');

    await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });
    await expect(page.getByRole('columnheader', { name: 'Saldo' })).toBeVisible();
    await expect(page.getByText('Pago T.C Rappi')).toBeVisible();
  });

  test('filtering by link relabels the saldo column to the visible cut', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching pocket through the subnav is covered by
    // the display specs above; this one pins the filter behaviour itself)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });

    await page.getByRole('button', { name: /Filtros/ }).click();
    await page.getByRole('group', { name: 'Vínculo' })
      .getByRole('button', { name: 'Sin vincular', exact: true }).click();

    // Only the movement with no mirrored record survives.
    await expect(page.locator('[data-testid^="accounting-row-"]')).toHaveCount(1);
    await expect(page.getByText('Pago T.C Rappi')).toBeVisible();

    // The column stops claiming to be the pocket's balance, and the card says
    // out loud that its own figure is still the untouched total.
    await expect(page.getByRole('columnheader', { name: 'Acumulado' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Saldo' })).toHaveCount(0);
    await expect(page.getByTestId('pocket-filtered-net')).toContainText('1 movimiento');
  });

  test('attribution filter cuts the ledger by partner', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (same rationale as the test above)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });

    await page.getByRole('button', { name: /Filtros/ }).click();
    await page.getByRole('button', { name: /Atribuir a/ }).click();
    await page.getByRole('checkbox', { name: 'Empresa' }).check();

    // The company-attributed income stays; the unlinked egreso has no
    // attribution to match.
    await expect(page.locator('[data-testid^="accounting-row-"]')).toHaveCount(1);
    await expect(page.getByText('Vastago (Fase 1) - Inicio 40%')).toBeVisible();
  });

  test('linked movements open the edit modal with direction locked', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('pocket-actions-1').click();
    await page.getByTestId('pocket-action-edit-1').click();

    const modal = page.getByRole('dialog');
    await expect(
      modal.getByRole('heading', { name: 'Editar Movimiento de bolsillo' }),
    ).toBeVisible();
    await expect(
      modal.getByText('La dirección se fija al crear el movimiento vinculado.'),
    ).toBeVisible();
    await expect(modal.getByTestId('pocket-movement-ledger')).toBeVisible();
    await expect(
      modal.getByRole('tab', { name: 'Empresa', exact: true }),
    ).toHaveAttribute('aria-selected', 'true');
  });

  // Bug caught: "Detalle e historial" sat beside the kebab in the fixed 56 px
  // actions track and spilled over the ledger columns.
  test('the leading three-dots menu owns the record history', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (reaching pocket through the subnav is covered by
    // the display specs above; this one pins the row action track)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });
    const row = page.getByTestId('accounting-row-1');
    await expect(row).toContainText('Vastago (Fase 1) - Inicio 40%', { timeout: 25_000 });

    const actionsCell = row.getByTestId('accounting-actions-cell-1');
    await expect(actionsCell.getByRole('button')).toHaveCount(1);
    const spill = await actionsCell.evaluate((cell) => cell.scrollWidth - cell.clientWidth);
    expect(spill).toBeLessThanOrEqual(0);

    await page.getByTestId('pocket-actions-1').click();
    await expect(page.getByTestId('pocket-actions-modal')).toContainText('Detalle e historial');
    await page.getByTestId('pocket-action-history-1').click();

    await expect(page.getByRole('heading', { name: 'Detalle del registro' })).toBeVisible();
    await expect(page.getByTestId('history-record-modal'))
      .toContainText('Vastago (Fase 1) - Inicio 40%');
    await expect(page.getByTestId('pocket-actions-modal')).toHaveCount(0);
  });

  test('new movement modal opens on Egreso with the attribution selector ready', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the helper lands on a sibling accounting
    // tab and then clicks the subnav, which is the navigation being
    // asserted; there is no pre-auth entry point in these mocked specs)
    await mockApi(page, buildHandler({ calls: [] }));
    await openSubview(page, 'pocket');
    await expect(page.getByTestId('pocket-new-button')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('pocket-new-button').click();
    const modal = page.getByRole('dialog');
    await expect(
      modal.getByRole('heading', { name: 'Nuevo Movimiento de bolsillo' }),
    ).toBeVisible();

    // Egresos are the common case: the toggle and everything that depends on it
    // land ready, so registering one takes no adjustment first.
    await expect(
      modal.getByRole('tab', { name: 'Egreso', exact: true }),
    ).toHaveAttribute('aria-selected', 'true');
    await expect(modal.getByText('Atribuir a')).toBeVisible();
    await modal.getByRole('tab', { name: 'Gustavo', exact: true }).click();
    await expect(
      modal.getByRole('tab', { name: 'Gustavo', exact: true }),
    ).toHaveAttribute('aria-selected', 'true');

    // Switching to Ingreso locks the selector back to the company.
    await modal.getByRole('tab', { name: 'Ingreso', exact: true }).click();
    await expect(
      modal.getByText('Los ingresos al bolsillo siempre son de la empresa.'),
    ).toBeVisible();
    await expect(
      modal.getByRole('tab', { name: 'Empresa', exact: true }),
    ).toHaveAttribute('aria-selected', 'true');
  });

  test('new movement rejects an empty required concept', {
    tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await openSubview(page, 'pocket');
    await page.getByTestId('pocket-new-button').click();

    const modal = page.getByRole('dialog');
    const concept = modal.locator('input[required]').first();
    await page.getByTestId('pocket-movement-form-submit').click();

    await expect(modal).toBeVisible();
    await expect(concept).toHaveValue('');
    await expect(concept).toHaveAttribute('aria-invalid', 'true');
    const errorId = await concept.getAttribute('aria-describedby');
    expect(errorId).toBeTruthy();
    await expect(modal.locator(`[id="${errorId}"]`)).toHaveText('Completa concepto.');
    expect(await concept.evaluate((element) => element.validity.valueMissing))
      .toBe(true);
  });

  test('recurring subview shows monthly cost and the breakdown card', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the helper lands on a sibling accounting
    // tab and then clicks the subnav, which is the navigation being
    // asserted; there is no pre-auth entry point in these mocked specs)
    await mockApi(page, buildHandler({ calls: [] }));
    await openSubview(page, 'recurring');

    await expect(
      page.getByRole('heading', { name: 'Pagos recurrentes', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText('Costo mensual (COP)')).toBeVisible();
    await expect(page.getByText('Desglose mensual')).toBeVisible();
    await expect(page.getByTestId('recurring-breakdown')).toBeVisible();
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
  });

  test('grouped view lists each category with its monthly subtotal', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the helper lands on a sibling accounting
    // tab and then clicks the subnav, which is the navigation being
    // asserted; there is no pre-auth entry point in these mocked specs)
    await mockApi(page, buildHandler({ calls: [] }));
    await openSubview(page, 'recurring');
    await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });

    // Grouped is the default view.
    await expect(page.getByTestId('recurring-group-1')).toContainText('Suscripciones de IA');
    await expect(page.getByTestId('recurring-group-2'))
      .toContainText('Arquitectura e infraestructura');

    // 800.000 + 80.000 in the AI group; the biennial Hostinger contributes its
    // prorated 32.900, not the 789.600 it is charged.
    await expect(page.getByTestId('recurring-group-total-1')).toHaveText('$880.000 COP');
    await expect(page.getByTestId('recurring-group-total-2')).toHaveText('$32.900 COP');
    await expect(page.getByTestId('recurring-monthly-grand-total'))
      .toHaveText('$912.900 COP');
  });

  test('grouped rows and their header share one column grid, outlier included', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the helper lands on a sibling accounting
    // tab and then clicks the subnav, which is the navigation being
    // asserted; there is no pre-auth entry point in these mocked specs)
    await mockApi(page, buildHandler({ calls: [], rows: OUTLIER_ROWS }));
    await openSubview(page, 'recurring');
    // Wait for the grouped grid itself: the pocket tab we come from also has a
    // row 2, so waiting on a row id would measure the previous view.
    await expect(page.getByTestId('recurring-group-1')).toBeVisible({ timeout: 25_000 });
    const gridRows = page.locator('.accounting-grid-row');
    await expect(gridRows).toHaveCount(3); // header + the two rows

    // Measure the boxes instead of the glyphs: font rendering would make a
    // pixel comparison of the text edge flaky, the column box would not.
    const grid = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.accounting-grid-row'));
      return rows.map((row) => Array.from(row.children).map((cell) => {
        const box = cell.getBoundingClientRect();
        return {
          x: Math.round(box.x),
          width: Math.round(box.width),
          align: getComputedStyle(cell).textAlign,
          label: cell.textContent.trim(),
        };
      }));
    });

    const [header, ...bodyRows] = grid;

    // One grid for the whole table: every cell of a column starts and ends on
    // the same axis, no matter how wide that particular row's content is.
    for (let col = 0; col < header.length; col += 1) {
      const cells = [header[col], ...bodyRows.map((row) => row[col])];
      expect(new Set(cells.map((cell) => cell.x)).size,
        `columna ${col} (${header[col].label}) arranca en ejes distintos`).toBe(1);
      expect(new Set(cells.map((cell) => cell.width)).size,
        `columna ${col} (${header[col].label}) tiene anchos distintos`).toBe(1);
      // A value is justified against its own header, not just placed under it.
      expect(new Set(cells.map((cell) => cell.align)).size,
        `columna ${col} (${header[col].label}) se justifica distinto que su encabezado`).toBe(1);
    }

    // And the justification is the one the data type calls for.
    const indexOf = (label) => header.findIndex((cell) => cell.label === label);
    expect(header[indexOf('Nombre')].align).toBe('left');
    expect(header[indexOf('Equiv. COP mensual')].align).toBe('right');
    expect(header[indexOf('Día')].align).toBe('center');
  });

  test('monthly columns normalize every billing cycle, custom ones included', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the helper lands on a sibling accounting
    // tab and then clicks the subnav, which is the navigation being
    // asserted; there is no pre-auth entry point in these mocked specs)
    await mockApi(page, buildHandler({ calls: [], rows: MIXED_FREQUENCY_ROWS }));
    await openSubview(page, 'recurring');
    await expect(page.getByTestId('accounting-row-3')).toBeVisible({ timeout: 25_000 });

    await expect(page.getByRole('columnheader', { name: 'Precio mensual' })).toBeVisible();
    await expect(
      page.getByRole('columnheader', { name: 'Equiv. COP mensual' }),
    ).toBeVisible();

    // Every row shows what it is charged next to what it costs per month.
    const hostinger = page.getByTestId('accounting-row-3');
    await expect(hostinger).toContainText('Cada 2 años');
    await expect(hostinger).toContainText('$789.600 COP');
    await expect(hostinger).toContainText('$32.900 COP');

    const figma = page.getByTestId('accounting-row-4');
    await expect(figma).toContainText('Trimestral');
    await expect(figma).toContainText('$300.000 COP');
    await expect(figma).toContainText('$100.000 COP');

    // A custom cycle names its length instead of a generic "Personalizada".
    const maintenance = page.getByTestId('accounting-row-5');
    await expect(maintenance).toContainText('Cada 5 meses');
    await expect(maintenance).toContainText('$500.000 COP');
    await expect(maintenance).toContainText('$100.000 COP');

    // The subtotal adds the prorated figures, not the raw charges.
    await expect(page.getByTestId('recurring-group-total-2')).toHaveText('$232.900 COP');
  });

  test('switching to the classic view restores sorting and pagination', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (subnav navigation into Recurrentes is
    // covered by the display specs above; this one pins behavior inside
    // the tab)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recurring-group-1')).toBeVisible({ timeout: 25_000 });

    await page.getByRole('tab', { name: 'Clásico', exact: true }).click();

    // No group headers; a sortable column header instead.
    await expect(page.getByTestId('recurring-group-1')).toHaveCount(0);
    await expect(page.getByTestId('accounting-sort-monthly_cop_cost')).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Categoría' })).toBeVisible();
  });

  test('drag handles disappear while a filter narrows the list', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (subnav navigation into Recurrentes is
    // covered by the display specs above; this one pins behavior inside
    // the tab)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recurring-drag-handle-1')).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recurring-search-input').fill('Hostinger');

    await expect(page.getByTestId('recurring-reorder-hint')).toBeVisible();
    await expect(page.getByTestId('recurring-drag-handle-3')).toHaveCount(0);
  });

  test('dragging a row persists the new manual order', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (the interaction is a manual mouse drag —
    // sortablejs ignores Playwright's dragTo, so this drives mouse.down/move/up,
    // which the detector's call list does not recognize)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recurring-drag-handle-2')).toBeVisible({ timeout: 25_000 });

    // Chat-GPT (id 2) is the second row of its category; drag it above
    // Claude Code 20x (id 1).
    await dragAbove(
      page,
      page.getByTestId('recurring-drag-handle-2'),
      page.getByTestId('accounting-row-1'),
    );

    await expect
      .poll(() => calls.filter((c) => c.apiPath === 'accounting/recurring/reorder/').length)
      .toBeGreaterThan(0);
    const body = calls.find((c) => c.apiPath === 'accounting/recurring/reorder/').body;
    // Chat-GPT now leads its category; every item carries its category so a
    // cross-group move would persist too.
    expect(body.items).toEqual([
      { id: 2, category: 1, order: 0 },
      { id: 1, category: 1, order: 1 },
      { id: 3, category: 2, order: 0 },
    ]);
  });

  test('weight sort is a temporary view: drag pauses and the manual order returns', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (subnav navigation into Recurrentes is
    // covered by the display specs above; this one pins behavior inside
    // the tab)
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recurring-drag-handle-1')).toBeVisible({ timeout: 25_000 });

    // Group headers carry their weight over the active monthly total
    // (880.000 and 32.900 over 912.900), rounded to sum exactly 100.0.
    await expect(page.getByTestId('recurring-group-weight-1')).toContainText('96,4%');
    await expect(page.getByTestId('recurring-group-weight-2')).toContainText('3,6%');
    // And each row carries its own share (Claude: 800.000 / 912.900).
    await expect(page.getByTestId('recurring-weight-1')).toHaveText('87,6%');

    // First click: descending — handles hidden, hint explains why.
    await page.getByTestId('recurring-grouped-sort-weight').click();
    await expect(page.getByTestId('recurring-weight-sort-hint')).toBeVisible();
    await expect(page.getByTestId('recurring-drag-handle-1')).toHaveCount(0);

    // Second click: ascending — the lightest group and rows come first.
    await page.getByTestId('recurring-grouped-sort-weight').click();
    const firstRow = page.locator('[data-testid^="accounting-row-"]').first();
    await expect(firstRow).toHaveAttribute('data-testid', 'accounting-row-3');
    const groupHeaders = page.locator('[data-testid^="recurring-group-toggle-"]');
    await expect(groupHeaders.first()).toContainText('Arquitectura e infraestructura');

    // Third click: off — the untouched manual order and the handles return.
    await page.getByTestId('recurring-grouped-sort-weight').click();
    await expect(firstRow).toHaveAttribute('data-testid', 'accounting-row-1');
    await expect(page.getByTestId('recurring-drag-handle-1')).toBeVisible();
    await expect(page.getByTestId('recurring-weight-sort-hint')).toHaveCount(0);

    // The whole cycle was a reading, never a write: reorder was not called.
    expect(calls.filter((c) => c.apiPath === 'accounting/recurring/reorder/')).toEqual([]);
  });

  test('a failed reorder warns and snaps the row back', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (manual mouse drag; see the success case)
    const calls = [];
    await mockApi(page, buildHandler({ calls, reorderStatus: 500 }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recurring-drag-handle-2')).toBeVisible({ timeout: 25_000 });

    await dragAbove(
      page,
      page.getByTestId('recurring-drag-handle-2'),
      page.getByTestId('accounting-row-1'),
    );

    await expect(page.getByText('No se pudo guardar el nuevo orden')).toBeVisible();
    // Restored: Claude Code 20x is the first row of its group again.
    const firstRow = page.locator('[data-testid^="accounting-row-"]').first();
    await expect(firstRow).toHaveAttribute('data-testid', 'accounting-row-1');
  });

  test('the categories modal lists the catalog with its usage count', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (subnav navigation into Recurrentes is
    // covered by the display specs above; this one pins behavior inside
    // the tab)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recurring-manage-categories'))
      .toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recurring-manage-categories').click();

    const modal = page.getByRole('dialog');
    await expect(
      modal.getByRole('heading', { name: 'Categorías de recurrentes' }),
    ).toBeVisible();
    await expect(modal.getByTestId('recurring-category-row-1')).toContainText('2 pagos');
    await expect(modal.getByTestId('recurring-category-row-2')).toContainText('1 pago');
  });

  test('deleting a category still in use is refused with the reason', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('recurring-manage-categories'))
      .toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recurring-manage-categories').click();
    await page.getByTestId('recurring-category-delete-1').click();

    // Confirm the destructive action, then the backend refuses it.
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('No se pudo eliminar la categoría')).toBeVisible();
    await expect(
      page.getByText('Muévelos a otra categoría antes de borrarla', { exact: false }),
    ).toBeVisible();
    expect(calls.some((c) => c.apiPath.endsWith('/delete/'))).toBe(true);
  });

  test('the modal previews the server-owned COP equivalent', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    // quality: allow-deep-link (accounting subnav navigation is covered by
    // admin-accounting-filters; this display test targets the modal preview)
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Pagos recurrentes', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recurring-new-button').click();
    await expect(
      page.getByRole('heading', { name: 'Nuevo pago recurrente' }),
    ).toBeVisible();

    const preview = page.getByTestId('recurring-payment-cop-preview');
    await expect(preview).toContainText('En COP, el equivalente toma el precio automáticamente.');

    await page.getByRole('tab', { name: 'USD' }).click();
    await expect(preview).toContainText('Tasa vigente: $4.000 COP/USD');
  });

  test.describe('recurring row actions', () => {
    test.describe.configure({ mode: 'serial' });

    test('the leading three-dots menu owns every current-row action', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      // quality: allow-deep-link (accounting subnav navigation is covered by
      // admin-accounting-filters; this test targets the consolidated row menu)
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('recurring-actions-1')).toBeVisible({ timeout: 25_000 });

      await page.getByTestId('recurring-actions-1').click();

      const modal = page.getByTestId('recurring-actions-modal');
      await expect(modal).toContainText('Detalle e historial');
      await expect(modal).toContainText('Editar');
      await expect(modal).toContainText('Duplicar');
      await expect(modal).toContainText('Desactivar');
      await expect(modal).toContainText('Silenciar avisos');
      await expect(modal).toContainText('Archivar');
      await expect(page.getByTestId('accounting-edit-1')).toHaveCount(0);
      await expect(page.getByTestId('accounting-delete-1')).toHaveCount(0);
      // The history button used to sit beside the kebab and overflow its track.
      await expect(page.getByTestId('accounting-actions-cell-1').getByRole('button')).toHaveCount(1);
    });

    test('duplicate opens a recalculated draft and creates only after review', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('recurring-actions-1')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 1, 'duplicate');

      const dialog = page.getByRole('dialog');
      await expect(dialog.getByRole('heading', { name: 'Duplicar pago recurrente' })).toBeVisible();
      const nameInput = dialog.locator('form input[type="text"]').first();
      await expect(nameInput).toHaveValue('Claude Code 20x');
      await expect(page.getByTestId('recurring-payment-form-cycle-anchor-date'))
        .toHaveValue('2026-09-08');
      await expect(page.getByTestId('recurring-duplicate-schedule-notice'))
        .toContainText('se recalculó');

      await nameInput.fill('Claude Code equipo B');
      await page.getByTestId('recurring-payment-form-submit').click();

      await expect(page.getByText('Pago recurrente duplicado')).toBeVisible();
      expect(calls.some((call) => (
        call.method === 'GET' && call.apiPath.endsWith('/duplicate-draft/')
      ))).toBe(true);
      const createCall = calls.find((call) => call.apiPath === 'accounting/recurring/create/');
      expect(createCall.body.name).toBe('Claude Code equipo B');
      expect(createCall.body.cycle_anchor_date).toBe('2026-09-08');
    });

    test('a failed duplicate draft leaves the row untouched and explains the failure', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:failure'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls, duplicateStatus: 503 }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('recurring-actions-1')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 1, 'duplicate');

      await expect(page.getByText('No se pudo preparar el duplicado')).toBeVisible();
      await expect(page.getByText('No se pudo calcular la próxima fecha.')).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Duplicar pago recurrente' }))
        .toHaveCount(0);
      expect(calls.filter((call) => call.method === 'POST')).toEqual([]);
    });

    test('deactivate removes the row from totals without opening the form', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('recurring-actions-1')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 1, 'deactivate');

      await expect(page.getByText('Pago recurrente desactivado')).toBeVisible();
      await expect(page.getByTestId('accounting-row-1')).toContainText('Inactivo');
      await expect(page.getByTestId('recurring-monthly-cop-total'))
        .toContainText('$112.900 COP');
      const stateCall = calls.find((call) => call.apiPath.endsWith('/state/'));
      expect(stateCall.body).toEqual({ is_active: false });
    });

    test('archive moves a payment into the preserved archived scope', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('recurring-actions-1')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 1, 'archive');
      await page.getByTestId('confirm-modal-confirm').click();

      await expect(page.getByText('Pago recurrente archivado')).toBeVisible();
      await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
      await page.getByRole('tab', { name: 'Archivados', exact: true }).click();
      await expect(page.getByTestId('accounting-row-1')).toContainText('Archivado');
      expect(calls.some((call) => call.apiPath.endsWith('/archive/'))).toBe(true);
    });

    test('restore returns an archived payment as inactive', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const calls = [];
      const rows = [recurringRow({
        ...RECURRING_ROWS[0],
        is_active: false,
        is_archived: true,
        archived_at: '2026-08-01T10:00:00Z',
      })];
      await mockApi(page, buildHandler({ calls, rows }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByRole('tab', { name: 'Archivados', exact: true }))
        .toBeVisible({ timeout: 25_000 });
      await page.getByRole('tab', { name: 'Archivados', exact: true }).click();
      await expect(page.getByTestId('recurring-actions-1')).toBeVisible();

      await chooseRecurringAction(page, 1, 'restore');

      await expect(page.getByText('Pago recurrente restaurado como inactivo')).toBeVisible();
      await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
      await page.getByRole('tab', { name: 'Vigentes', exact: true }).click();
      await expect(page.getByTestId('accounting-row-1')).toContainText('Inactivo');
      expect(calls.some((call) => call.apiPath.endsWith('/restore/'))).toBe(true);
    });

    test('mute can silence reminders indefinitely from the row', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('recurring-actions-1')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 1, 'mute');
      await page.getByRole('tab', { name: 'Indefinidamente', exact: true }).click();
      await page.getByTestId('recurring-mute-submit').click();

      await expect(page.getByText('Avisos silenciados')).toBeVisible();
      await page.getByTestId('recurring-actions-1').click();
      await expect(page.getByTestId('recurring-action-unmute-1')).toBeVisible();
      const muteCall = calls.find((call) => call.apiPath.endsWith('/reminders/mute/'));
      expect(muteCall.body).toEqual({ muted: true, until: null });
    });

    test('bulk selection deactivates several visible payments atomically', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('accounting-select-1')).toBeVisible({ timeout: 25_000 });

      await page.getByTestId('accounting-select-1').check();
      await page.getByTestId('accounting-select-2').check();
      await expect(page.getByTestId('recurring-bulk-bar')).toContainText('2 seleccionados');
      await page.getByTestId('recurring-bulk-actions').click();
      await page.getByText('Desactivar seleccionados', { exact: true }).click();
      await page.getByTestId('confirm-modal-confirm').click();

      await expect(page.getByText('Pagos recurrentes desactivados')).toBeVisible();
      await expect(page.getByTestId('recurring-monthly-cop-total'))
        .toContainText('$32.900 COP');
      await expect(page.getByTestId('recurring-bulk-bar')).toHaveCount(0);
      const bulkCall = calls.find((call) => call.apiPath === 'accounting/recurring/bulk-action/');
      expect(bulkCall.body).toEqual({ recurring_ids: [1, 2], action: 'deactivate' });
    });
  });

  test.describe('derived recurring values', () => {
    // Three cold navigations compiling the same Nuxt route in parallel can
    // starve one another before the first row mounts. The behaviors remain
    // isolated, but this small group runs sequentially for deterministic UI
    // readiness.
    test.describe.configure({ mode: 'serial' });

    test('editing only the price refreshes every recurring projection', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('accounting-row-2')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 2, 'edit');
      await page.getByTestId('recurring-payment-form-price').fill('200');
      await expect(page.getByTestId('recurring-payment-cop-preview'))
        .toContainText('$800.000 COP');
      await page.getByTestId('recurring-payment-form-submit').click();

      await expect(page.getByTestId('accounting-row-2')).toContainText('$800.000 COP');
      await expect(page.getByTestId('recurring-group-total-1')).toHaveText('$1.600.000 COP');
      await expect(page.getByTestId('recurring-monthly-cop-total'))
        .toContainText('$1.632.900 COP');
      expect(calls.find((call) => call.method === 'PATCH').body.price).toBe(200);
    });

    test('editing only the currency refreshes every recurring projection', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('accounting-row-2')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 2, 'edit');
      await page.getByRole('dialog').getByRole('tab', { name: 'COP', exact: true }).click();
      await expect(page.getByTestId('recurring-payment-cop-preview')).toContainText('$20 COP');
      await page.getByTestId('recurring-payment-form-submit').click();

      await expect(page.getByTestId('accounting-row-2')).toContainText('$20 COP');
      await expect(page.getByTestId('recurring-group-total-1')).toHaveText('$800.020 COP');
      await expect(page.getByTestId('recurring-monthly-cop-total')).toContainText('$832.920 COP');
    });

    test('editing only the frequency refreshes every recurring projection', {
      tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('accounting-row-2')).toBeVisible({ timeout: 25_000 });

      await chooseRecurringAction(page, 2, 'edit');
      await page.getByTestId('recurring-payment-form-frequency').selectOption('annual');
      await expect(page.getByTestId('recurring-payment-cop-preview')).toContainText('$6.667 COP');
      await page.getByTestId('recurring-payment-form-submit').click();

      await expect(page.getByTestId('accounting-row-2')).toContainText('$6.667 COP');
      await expect(page.getByTestId('recurring-group-total-1')).toHaveText('$806.667 COP');
      await expect(page.getByTestId('recurring-monthly-cop-total')).toContainText('$839.567 COP');
    });
  });

  test('creates a recurring payment through the modal', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Pagos recurrentes', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recurring-new-button').click();
    await page.locator('form input[type="text"]').first().fill('Netflix');
    await page.locator('form input[inputmode="numeric"]').first().fill('39800');
    await page.getByTestId('recurring-payment-form-submit').click();

    await expect(page.getByText('Pago recurrente creado')).toBeVisible();
    expect(calls).toHaveLength(1);
    expect(calls[0].body.name).toBe('Netflix');
  });

  test('the charts modal distributes the monthly COP cost by category', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (subnav navigation into Recurrentes is covered
    // by the display specs above; this one pins the charts modal)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Pagos recurrentes', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    await page.getByTestId('recurring-charts-button').click();

    // Same base as the table's group headers: 880.000 and 32.900 over 912.900.
    const legend = page.getByTestId('recurring-chart-legend');
    await expect(legend).toContainText('Suscripciones de IA');
    await expect(legend).toContainText('$880.000 COP');
    await expect(legend).toContainText('96,4%');
    await expect(legend).toContainText('$32.900 COP');
    await expect(legend).toContainText('3,6%');
  });

  test('drilling into a category from the legend narrows the item ranking', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Pagos recurrentes', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('recurring-charts-button').click();

    await page.getByTestId('recurring-chart-legend-item-2').click();

    // The header names what the charts are scoped to, and the note names the
    // lone payment so a donut of one color reads as the real breakdown.
    await expect(page.getByTestId('recurring-charts-drill-header'))
      .toContainText('Arquitectura e infraestructura');
    await expect(page.getByTestId('recurring-charts-single-item')).toContainText('Hostinger');

    // Scoped to the modal: the page's breakdown card is a BaseSegmented, which
    // also renders role="tab" buttons.
    await page.getByTestId('stats-modal').getByRole('tab', { name: 'Ítems' }).click();

    // Only the infrastructure payment survives the drill-down.
    const items = page.getByTestId('stats-bar-chart');
    await expect(items).toContainText('Hostinger');
    await expect(items).not.toContainText('Chat-GPT');
  });

  test('drilling into a category splits the donut by its payments, not into one slice', {
    tag: [...ADMIN_ACCOUNTING_RECURRING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (subnav navigation into Recurrentes is covered
    // by the display specs above; this one pins the donut's drilled state)
    await mockApi(page, buildHandler({ calls: [] }));
    await page.goto('/panel/accounting/recurring', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Pagos recurrentes', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await page.getByTestId('recurring-charts-button').click();

    await page.getByTestId('recurring-chart-legend-item-1').click();

    // 800.000 and 80.000 over the category's 880.000 — the question the reader
    // is asking once they picked a category, not "how much is this category".
    const legend = page.getByTestId('recurring-chart-legend');
    await expect(legend).toContainText('Claude Code 20x');
    await expect(legend).toContainText('90,9%');
    await expect(legend).toContainText('Chat-GPT');
    await expect(legend).toContainText('9,1%');
    // And the second base, over everything: 800.000 of 912.900.
    await expect(legend).toContainText('87,6% del total general');
    await expect(legend).not.toContainText('Arquitectura e infraestructura');

    // Back to comparing categories without reopening the modal.
    await page.getByTestId('recurring-charts-back').click();
    await expect(legend).toContainText('Arquitectura e infraestructura');
  });

  /**
   * La navegación del módulo en un celular.
   *
   * Las doce secciones envolvían en cuatro filas de pastillas y ocupaban casi
   * media pantalla: al entrar al Bolsillo lo primero que se veía era la
   * navegación y el saldo — el dato por el que se entró — quedaba debajo del
   * pliegue. La medida de éxito del requerimiento es esa, y es lo que afirma el
   * primer test.
  */
  test.describe('en un celular', () => {
    test.use({ viewport: { width: 412, height: 915 } });

    test('el saldo del bolsillo se ve sin desplazarse', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (mide lo que se ve al llegar; interactuar movería el scroll que se está midiendo)
      // quality: allow-deep-link (entrar a la vista ES el escenario, no el camino hasta ella)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      const balance = page.getByTestId('pocket-balance');
      await expect(balance).toBeVisible({ timeout: 25_000 });
      await expect(balance).toHaveText('$-149.000');

      // Sin haber scrolleado, el saldo entra entero en la primera pantalla.
      const scrolled = await page.evaluate(() => window.scrollY);
      expect(scrolled).toBe(0);
      const box = await balance.boundingBox();
      expect(box.y + box.height).toBeLessThanOrEqual(915);

      // Y entra holgado, que es lo que de verdad mide el cambio: el tope deja
      // aire para un subtítulo más largo, pero no permite que vuelva una
      // parrilla de cuatro filas sin poner el test rojo.
      expect(box.y).toBeLessThanOrEqual(420);
    });

    test('cada movimiento se representa como una tarjeta completa', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (verifica la lectura compacta al llegar)
      // quality: allow-deep-link (la vista es el escenario)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      const card = page.getByTestId('pocket-card-1');
      const runningBalance = page.getByTestId('pocket-running-balance-1');
      await expect(card).toBeVisible({ timeout: 25_000 });
      await expect(runningBalance).toBeVisible({ timeout: 25_000 });
      await expect(card).toContainText('Vastago (Fase 1) - Inicio 40%');
      await expect(card).toContainText('Saldo después');
      await expect(page.getByTestId('pocket-amount-1')).toHaveText('$2.123.000');
      await expect(page.getByTestId('pocket-date-1')).toContainText('29 abr 2026');
      await expect(page.getByTestId('pocket-direction-1')).toHaveText('Ingreso');
      await expect(runningBalance).toHaveText('$2.123.000');
      await expect(page.getByRole('table')).toHaveCount(0);

      expect(await page.evaluate(() => (
        document.documentElement.scrollWidth <= document.documentElement.clientWidth
      ))).toBe(true);
      expect(await page.getByTestId('pocket-card-list').evaluate((element) => (
        element.scrollWidth <= element.clientWidth
      ))).toBe(true);
      expect(await card.evaluate((element) => {
        const action = element.querySelector('[data-testid="pocket-actions-1"]');
        const concept = element.querySelector('h2');
        const actionBox = action.getBoundingClientRect();
        const conceptBox = concept.getBoundingClientRect();
        const cardBox = element.getBoundingClientRect();
        return actionBox.width >= 44
          && actionBox.height >= 44
          && actionBox.left >= cardBox.left
          && actionBox.right <= cardBox.right
          && actionBox.right <= conceptBox.left;
      })).toBe(true);
    });

    test('el orden por concepto reordena las tarjetas', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-fragile-selector (el orden posicional es el resultado observado)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await page.getByTestId('pocket-card-sort-concept').click();

      const cards = page.getByTestId('pocket-card-list').locator('article');
      await expect(cards).toHaveCount(2);
      await expect(cards.nth(0))
        .toHaveAttribute('data-testid', 'pocket-card-2');
      await expect(cards.nth(1))
        .toHaveAttribute('data-testid', 'pocket-card-1');
    });

    test('los distintivos compactos conservan palabras enteras', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (the chip geometry is the outcome)
      // quality: allow-deep-link (la vista es el escenario)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      const linked = page.getByTestId('pocket-linked-1');
      const income = page.getByTestId('pocket-direction-1');
      const expense = page.getByTestId('pocket-direction-2');
      await expect(linked).toBeVisible({ timeout: 25_000 });
      await expect(linked).toHaveText('Vinculado');
      await expect(income).toHaveText('Ingreso');
      await expect(expense).toHaveText('Egreso');
      await expect(linked).toHaveCSS('white-space', 'nowrap');
      await expect(income).toHaveCSS('white-space', 'nowrap');
      await expect(expense).toHaveCSS('white-space', 'nowrap');
      expect(await linked.evaluate((element) => element.scrollWidth <= element.clientWidth))
        .toBe(true);
    });

    test('la acción inicial abre la edición del movimiento', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await page.getByTestId('pocket-actions-1').click();
      await expect(page.getByTestId('pocket-actions-modal')).toBeVisible();
      await page.getByTestId('pocket-action-edit-1').click();

      await expect(
        page.getByRole('heading', { name: 'Editar Movimiento de bolsillo' }),
      ).toBeVisible();
    });

    test('la acción inicial alcanza la confirmación de borrado', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await page.getByTestId('pocket-actions-2').click();
      await page.getByTestId('pocket-action-delete-2').click();

      await expect(page.getByRole('heading', { name: 'Eliminar movimiento' }))
        .toBeVisible();
    });

    test('el acumulado filtrado parte de los movimientos visibles', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (la entrada por el subnav se cubre en su escenario dedicado)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await page.getByRole('button', { name: /Filtros/ }).click();
      await page.getByRole('group', { name: 'Vínculo' })
        .getByRole('button', { name: 'Sin vincular', exact: true }).click();

      const card = page.getByTestId('pocket-card-2');
      await expect(card).toBeVisible();
      await expect(card).toContainText('Acumulado filtrado');
      await expect(page.getByTestId('pocket-running-balance-2')).toHaveText('$-2.272.000');
      await expect(page.getByTestId('pocket-balance')).toHaveText('$-149.000');
      await expect(page.getByTestId('pocket-card-1')).toHaveCount(0);
    });

    test('la sección se cambia desde el selector, sin la parrilla de tabs', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      const nav = page.getByTestId('accounting-subnav-select');
      await expect(nav).toBeVisible({ timeout: 25_000 });
      // Las pastillas siguen en el DOM pero no ocupan lugar: eso es lo que le
      // devuelve la pantalla al contenido.
      await expect(page.getByTestId('accounting-subnav-incomes')).toBeHidden();
      // El activo viene marcado al abrir, sin tener que elegir nada.
      await expect(nav).toHaveValue('pocket');

      await nav.selectOption('incomes');

      await expect(page).toHaveURL(/\/panel\/accounting\/incomes/);
    });

    test('el selector de sección no se confunde con el de filtros guardados', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (los dos quedan contiguos; lo que se afirma es que se distinguen antes de tocarlos)
      // quality: allow-deep-link (la vista es el escenario, no el camino hasta ella)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      const nav = page.getByTestId('accounting-subnav-select');
      const filters = page.getByTestId('filter-tabs-select');
      await expect(nav).toBeVisible({ timeout: 25_000 });
      await expect(filters).toBeVisible();

      // Cada uno dice qué hace, y no dicen lo mismo.
      await expect(nav).toHaveAttribute('aria-label', 'Sección de contabilidad');
      await expect(filters).toHaveAttribute('aria-label', 'Filtro guardado');
    });
  });

  test.describe('en tableta vertical', () => {
    test.use({ viewport: { width: 835, height: 1195 } });

    test('mantiene los dos selectores y no recupera la parrilla de doce tabs', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (el resultado es el layout de llegada)
      // quality: allow-deep-link (la vista es el escenario)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await expect(page.getByTestId('accounting-subnav-select'))
        .toBeVisible({ timeout: 25_000 });
      await expect(page.getByTestId('filter-tabs-select')).toBeVisible();
      await expect(page.getByTestId('accounting-subnav-incomes')).toBeHidden();
      await expect(page.getByTestId('accounting-row-1'))
        .toContainText('Vastago (Fase 1) - Inicio 40%');
      expect(await page.evaluate(() => (
        document.documentElement.scrollWidth <= document.documentElement.clientWidth
      ))).toBe(true);
    });
  });

  test.describe('en tableta horizontal', () => {
    test.use({ viewport: { width: 1195, height: 835 } });

    test('recupera las tiras y la columna independiente de saldo', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (el resultado es el layout de llegada)
      // quality: allow-deep-link (la vista es el escenario)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await expect(page.getByTestId('accounting-subnav-incomes'))
        .toBeVisible({ timeout: 25_000 });
      await expect(page.getByTestId('accounting-subnav-select')).toBeHidden();
      await expect(page.getByRole('columnheader', { name: 'Saldo', exact: true })).toBeVisible();
      await expect(page.getByTestId('pocket-running-balance-1')).toHaveCount(0);
      expect(await page.evaluate(() => (
        document.documentElement.scrollWidth <= document.documentElement.clientWidth
      ))).toBe(true);
    });
  });

  test.describe('en portátil', () => {
    test.use({ viewport: { width: 1440, height: 900 } });

    test('conserva la representación ancha sin desbordar', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (el resultado es el layout de llegada)
      // quality: allow-deep-link (la vista es el escenario)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await expect(page.getByTestId('accounting-subnav-incomes'))
        .toBeVisible({ timeout: 25_000 });
      await expect(page.getByTestId('accounting-subnav-select')).toBeHidden();
      await expect(page.getByRole('columnheader', { name: 'Saldo', exact: true })).toBeVisible();
      expect(await page.evaluate(() => (
        document.documentElement.scrollWidth <= document.documentElement.clientWidth
      ))).toBe(true);
    });
  });

  test.describe('en monitor de 27 pulgadas', () => {
    test.use({ viewport: { width: 2560, height: 1440 } });

    test('limita el contenido general a 1400 píxeles', {
      tag: [...ADMIN_ACCOUNTING_POCKET, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-no-interaction (mide el tope del layout al llegar)
      // quality: allow-deep-link (la vista es el escenario)
      await mockApi(page, buildHandler({ calls: [] }));
      await page.goto('/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });

      await expect(page.getByTestId('accounting-subnav-incomes'))
        .toBeVisible({ timeout: 25_000 });
      const shellWidths = await page.getByTestId('panel-content-shell')
        .evaluateAll((elements) => elements.map((element) => (
          element.getBoundingClientRect().width
        )));
      expect(Math.max(...shellWidths)).toBeLessThanOrEqual(1401);
      await expect(page.getByTestId('accounting-row-1'))
        .toContainText('Vastago (Fase 1) - Inicio 40%');
    });
  });
});
