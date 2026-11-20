import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';

const june = ['2026-06-01', '2026-06-30'];
const recurring = Array.from({ length: 5 }, (_, index) => ({
  id: index + 1, name: index === 0 ? 'Claude Code 20x' : 'Pago recurrente ' + (index + 1),
  price: '200.00', currency: 'USD', monthly_price: '200.00', monthly_cop_cost: '720000.00',
  cop_equivalent: '720000.00', frequency: 'monthly', frequency_label: 'Mensual',
  category: 2, category_name: 'Suscripciones', payment_method: 'credit_card',
  payment_method_label: 'T.C.', cost_type: 'fixed', is_active: true, is_archived: false,
}));
const pocket = Array.from({ length: 13 }, (_, index) => {
  const id = index + 1;
  return {
    id, concept: 'Movimiento QA ' + id, movement_date: '2026-06-12',
    direction: [7, 10].includes(id) ? 'out' : 'in',
    direction_label: [7, 10].includes(id) ? 'Egreso' : 'Ingreso',
    amount: id === 10 ? '163000.00' : '123000.00', allocations: [],
  };
});
const ads = Array.from({ length: 10 }, (_, index) => {
  const id = index + 1;
  const amount = { 4: '80000.00', 6: '76000.00', 7: '62000.00' }[id];
  return {
    id, platform: amount ? 'facebook' : 'google', platform_label: amount ? 'Facebook Ads' : 'Google Ads',
    amount: amount || '10000.00', spend_date: '2026-06-12', origin_card: 'Visa, empresa',
  };
});
const account = {
  id: 1, title: 'Borrador QA', billing_concept: 'Borrador QA', public_number: '',
  commercial_status: 'draft', commercial_status_label: 'Borrador', total: '125000.00',
  currency: 'COP', issue_date: '2026-06-12', items: [],
};
const hostings = Array.from({ length: 10 }, (_, index) => {
  const id = index + 1;
  const quarterly = id === 2 || id === 10;
  return {
    id, client: quarterly ? 12 : 14, client_name: 'Cliente QA ' + id,
    display_label: 'Hosting QA ' + id, domain_url: 'https://hosting-' + id + '.example.test/',
    monthly_value: '67000.00', total_paid: id === 2 ? '201000.00' : '0.00',
    payment_per_cycle: '201000.00', cycles_count: id === 2 ? 1 : 0,
    payment_modality: quarterly ? 'quarterly' : 'monthly',
    payment_modality_label: quarterly ? 'Trimestral' : 'Mensual',
    valid_from: '2026-05-01', valid_to: '2027-05-01', is_active: true,
  };
});
const income = {
  id: 1, concept: 'Diagnóstico técnico - Cobro único', kind: 'expected', kind_label: 'Esperado',
  ledger: 'company', period_date: '2025-11-01', period_label: 'Noviembre 2025',
  total_amount: '999999999999.99', paid_amount: '0.00', pending_amount: '999999999999.99',
};
const cycle = {
  id: 1, paid_at: '2026-06-12', modality: 'quarterly', modality_label: 'Trimestral',
  amount: '201000.00', period_from: '2026-06-01', period_to: '2026-08-31',
};
const records = (results, meta = {}) => ({ results, meta });
const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

const replies = {
  'auth/check/': { user: { username: 'staff-qa', is_staff: true, is_superuser: true } },
  'accounting/recurring/': records(recurring),
  'accounting/recurring/1/': recurring[0],
  'accounting/recurring-categories/': records([{ id: 2, name: 'Suscripciones' }]),
  'accounting/pocket/': records(pocket, { balance: '0.00' }),
  'accounting/pocket/10/': pocket[9],
  'accounting/ads/': records(ads),
  'accounting/ads/4/': ads[3],
  'accounting/collection-accounts/': records([account], { issued_total: '0.00' }),
  'accounting/collection-accounts/1/': account,
  'accounting/hostings/': records(hostings),
  'accounting/hostings/2/cycles/': records([cycle]),
  'accounting/incomes/': records([
    income, { ...income, id: 8, concept: 'Ingreso QA 8', total_amount: '125000.00' },
    { ...income, id: 9, concept: 'Diciembre QA', period_date: '2025-12-01', total_amount: '1000.00' },
  ]),
  'accounting/incomes/1/detail/': { income, liquid: [], expenses: [], collection_account: null },
  'accounting/settings/': { collection_accounts_view_mode: 'classic', incomes_view_mode: 'table' },
};

async function setup(page, override = () => undefined) {
  await setAuthLocalStorage(page, {
    token: 'accounting-qa',
    userAuth: { id: 11, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockApi(page, (request) => {
    const data = override(request) ?? replies[request.apiPath];
    return json(data ?? records([]));
  });
}

function rowIds(page) {
  return page.getByTestId(/^accounting-row-\d+$/).evaluateAll((rows) => (
    rows.map((row) => Number(row.dataset.testid.split('-').at(-1))).sort((left, right) => left - right)
  ));
}

function query(page) {
  return Object.fromEntries(new URL(page.url()).searchParams);
}

const scenarios = [
  {
    view: 'recurring', flow: '@flow:admin-accounting-recurring', key: 'recurringDetail', id: '1',
    filters: { category: '2' }, ids: [1, 2, 3, 4, 5],
    menu: 'recurring-actions-1', action: 'recurring-action-history-1',
    detail: 'history-record-modal', proof: 'Claude Code 20x',
  },
  {
    view: 'pocket', flow: '@flow:admin-accounting-pocket', key: 'movement', id: '10',
    filters: { dateAfter: june[0], dateBefore: june[1], direction: 'out' }, ids: [7, 10],
    applyDirection: true,
    link: 'pocket-open-10', detail: 'pocket-detail-modal', proof: 'Movimiento QA 10',
    total: 'pocket-filtered-net', sum: '-286.000',
  },
  {
    view: 'ads', flow: '@flow:admin-accounting-ads', key: 'ads', id: '4',
    filters: { spend_from: june[0], spend_to: june[1], platform: 'facebook' }, ids: [4, 6, 7],
    menu: 'ads-actions-4', action: 'ads-action-history-4',
    detail: 'history-record-modal', proof: '80000.00', sum: '$218.000 COP',
  },
  {
    view: 'collections', flow: '@flow:admin-accounting-collection-detail', key: 'account', id: '1',
    filters: { totalMin: '125000', totalMax: '125000' }, ids: [1],
    link: 'collection-open-1', detail: 'collection-detail-modal', proof: 'Borrador',
    sum: 'Por cobrar: $0 COP',
  },
  {
    view: 'hostings', flow: '@flow:admin-accounting-hosting-cycles', key: 'hosting', id: '2',
    filters: { modalities: 'quarterly' }, ids: [2, 10],
    link: 'hosting-open-cycles-2', heading: 'Ciclos de pago — Hosting QA 2', proof: '$201.000 COP',
  },
];

test.setTimeout(60_000);

for (const scenario of scenarios) {
  test(`retains the ${scenario.view} query after a detail reload`, {
    tag: [scenario.flow, '@flow:admin-accounting-record-history', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (opening a saved filtered address is the behaviour under test)
    await setup(page);
    const initialFilters = { ...scenario.filters };
    if (scenario.applyDirection) delete initialFilters.direction;
    const url = '/es-co/panel/accounting/' + scenario.view + '?' + new URLSearchParams(initialFilters);
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    if (scenario.applyDirection) {
      await page.getByTestId('accounting-filter-panel').getByRole('button', { name: 'Egreso', exact: true }).click();
    }
    await expect.poll(() => rowIds(page)).toEqual(scenario.ids);

    if (scenario.menu) {
      await page.getByTestId(scenario.menu).click();
      await page.getByTestId(scenario.action).click();
    } else {
      await page.getByTestId(scenario.link).filter({ visible: true }).click();
    }
    const detail = scenario.heading
      ? page.getByRole('dialog', { name: scenario.heading })
      : page.getByTestId(scenario.detail);
    await expect(detail).toContainText(scenario.proof);
    await expect.poll(() => query(page)).toEqual({ ...scenario.filters, [scenario.key]: scenario.id });

    if (scenario.applyDirection) {
      await page.goBack();
      await expect(detail).toBeHidden();
      await expect.poll(() => query(page)).toEqual(scenario.filters);
      await page.goForward();
      await expect(detail).toContainText(scenario.proof);
    }
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(detail).toContainText(scenario.proof);
    await page.keyboard.press('Escape');

    await expect(detail).toBeHidden();
    await expect.poll(() => query(page)).toEqual(scenario.filters);
    await expect.poll(() => rowIds(page)).toEqual(scenario.ids);
    if (scenario.total) {
      await expect(page.getByTestId(scenario.total)).toContainText(scenario.sum);
    } else if (scenario.sum) {
      await expect(page.getByText(scenario.sum, { exact: true })).toBeVisible();
    }
  });
}

test('preserves the Radar focus through a recurring details visit', {
  tag: ['@flow:admin-accounting-recurring', '@flow:admin-dashboard-attention-radar', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  // quality: allow-deep-link (the delivery of the Radar URL is covered by the dashboard spec)
  await setup(page);
  await page.goto('/es-co/panel/accounting/recurring?recurring=1&radar=1&category=2', { waitUntil: 'domcontentloaded' });
  await expect.poll(() => rowIds(page)).toEqual([1]);

  await page.getByRole('link', { name: 'Claude Code 20x', exact: true }).click();
  const detail = page.getByTestId('history-record-modal');
  await expect(detail).toContainText('Claude Code 20x');
  await page.keyboard.press('Escape');
  await expect(detail).toBeHidden();

  await expect.poll(() => query(page)).toEqual({ recurring: '1', radar: '1', category: '2' });
  await page.getByTestId('recurring-radar-focus').getByRole('button').click();
  await expect.poll(() => rowIds(page)).toEqual([1, 2, 3, 4, 5]);
  await expect.poll(() => query(page)).toEqual({ category: '2' });
});

test('loads archived recurring payments on the first list request', {
  tag: ['@flow:admin-accounting-recurring', '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  // quality: allow-no-interaction (the scope of the first API read is determined by the direct address)
  // quality: allow-deep-link (starts from an archived address to verify the first list request)
  const scopes = [];
  await setup(page, ({ apiPath, route }) => {
    if (apiPath !== 'accounting/recurring/') return undefined;
    scopes.push(new URL(route.request().url()).searchParams.get('archive_scope'));
    return records([{ ...recurring[0], is_archived: true }]);
  });
  await page.goto('/es-co/panel/accounting/recurring?scope=archived', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);

  await expect(page.getByTestId('accounting-row-1')).toBeVisible();
  expect(scopes).toEqual(['archived']);
});

test('preserves cents on a reloaded income detail', {
  tag: ['@flow:admin-accounting-income-crud', '@flow:admin-accounting-record-history', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  // quality: allow-deep-link (sets the saved list context before opening the exact income)
  await setup(page);
  const filters = { accounting_incomeTab: 'all', periodAfter: '2025-11-01', periodBefore: '2025-11-30', kind: 'expected' };
  await page.goto('/es-co/panel/accounting/incomes?' + new URLSearchParams(filters), { waitUntil: 'domcontentloaded' });
  await expect.poll(() => rowIds(page)).toEqual([1, 8]);
  await expect(page.getByTestId('accounting-row-1')).toContainText('999.999.999.999,99');

  await page.getByRole('link', { name: income.concept, exact: true }).click();
  await expect(page.getByTestId('income-detail-total')).toHaveText('$999.999.999.999,99 COP');
  await page.reload({ waitUntil: 'domcontentloaded' });

  await expect(page.getByTestId('income-detail-total')).toHaveText('$999.999.999.999,99 COP');
  await page.keyboard.press('Escape');
  await expect.poll(() => query(page)).toEqual(filters);
  await expect.poll(() => rowIds(page)).toEqual([1, 8]);
});
