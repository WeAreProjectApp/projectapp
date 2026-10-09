/** R-accounting-special-01: dense accounting data must retain its decision, CTA and conditional blocks at the profiles where they regress. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { expectCompactModal } from '../helpers/modal-layout.js';
import { RESPONSIVE_PROFILES } from './catalog-scenarios.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const longConcept = 'IngresoSinEspaciosDemasiadoLargoParaLaColumnaPrioritaria20260901';
const income = { id: 1, concept: longConcept, kind: 'expected', kind_label: 'Esperado', origin: 'hosting', client: 1, client_name: 'Cliente con nombre muy largo para confirmar prioridad responsive', project: 1, project_name: 'Proyecto fixture', total_amount: '123456789.00', paid_amount: '0.00', pending_amount: '123456789.00', payment_status: 'pending', payment_status_label: 'Pendiente', has_collection_account: true, collection_account_status: 'issued', collection_account_number: 'CC-RESP-001', can_settle: true, destination: 'partners', destination_label: 'Socios', ledger: 'company', ledger_label: 'Empresa', period_date: '2026-09-01', gustavo_amount: '61728394.50', carlos_amount: '61728394.50', notes: '' };
// Collection creation chooses a different, unbilled income; the issued row
// remains available for liquidation and bulk payments.
const unbilledIncome = {
  ...income, id: 3, has_collection_account: false, collection_account_id: null,
  collection_account_status: null, collection_account_number: null, can_settle: false,
};
const collection = { id: 1, public_number: 'CC-RESP-001', customer_name: income.client_name, billing_concept: longConcept, total: '123456789.00', commercial_status: 'issued', commercial_status_label: 'Emitida', client: 1, client_display_name: income.client_name, project_id: 1, project_name: 'Proyecto fixture', due_date: '2026-10-01', is_overdue: false };
const pocket = { id: 1, concept: longConcept, amount: '123456789.00', movement_date: '2026-09-01', created_at: '2026-09-01T10:00:00Z', direction: 'in', direction_label: 'Ingreso', is_linked: true };
const collectionPreviewPdf = '/api/accounting/collection-accounts/preview/accounting-special/CC-RESP-001.pdf';
const receivableRows = [
  {
    ...income,
    period_label: 'Septiembre 2026',
    is_receivable_candidate: true,
    collection_confidence: 'high',
  },
  {
    ...income,
    id: 2,
    concept: 'Hosting anual sin proyecto',
    client: 2,
    client_name: 'Cliente hosting responsive',
    project: null,
    project_name: null,
    total_amount: '1000000.00',
    pending_amount: '1000000.00',
    period_label: 'Septiembre 2026',
    is_receivable_candidate: true,
    collection_confidence: '',
  },
];
const receivablesSummary = {
  high_total: '123456789.00',
  high_count: 1,
  selected_count: 2,
  selected_total: '124456789.00',
  paid_total: '0.00',
  pending_total: '124456789.00',
  by_confidence: {
    high: { count: 1, total_amount: '123456789.00', paid_amount: '0.00', pending_amount: '123456789.00' },
    medium: { count: 0, total_amount: '0.00', paid_amount: '0.00', pending_amount: '0.00' },
    low: { count: 0, total_amount: '0.00', paid_amount: '0.00', pending_amount: '0.00' },
    unclassified: { count: 1, total_amount: '1000000.00', paid_amount: '0.00', pending_amount: '1000000.00' },
  },
};
const responsiveDashboardSummary = {
  year: 2026,
  expected_total: '124456789.00',
  liquid_total: '0.00',
  liquid_utility: '0.00',
  expenses_total: '0.00',
  pocket_balance: '0.00',
  partners: {},
  monthly: [],
  ads: {},
  hostings: {},
  latest_card_snapshots: [],
  receivables: receivablesSummary,
  card_debt: { total: '0.00', card_count: 0, utilization_pct: 0 },
};

async function setup(page) {
  await setAuthLocalStorage(page, { token: 'accounting-special-responsive-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  const accountingSettings = {
    collection_accounts_view_mode: 'classic',
    collection_accounts_group_by: 'client',
  };
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([{ id: 'expected-only', name: 'Esperados', filters: { kind: 'expected' } }]);
    if (apiPath === 'accounting/settings/' && method === 'GET') return json(accountingSettings);
    if (apiPath === 'accounting/settings/update/' && method === 'PATCH') {
      Object.assign(accountingSettings, route.request().postDataJSON());
      return json(accountingSettings);
    }
    if (apiPath === 'accounting/pocket/' && method === 'GET') return json({ results: [pocket], meta: { balance: '123456789.00' } });
    if (apiPath === 'accounting/incomes/' && method === 'GET') return json({ results: [income, unbilledIncome], meta: { expected_total: '123456789.00', liquid_total: '0.00' } });
    if (apiPath.startsWith('accounting/dashboard/') && method === 'GET') return json(responsiveDashboardSummary);
    if (apiPath === 'accounting/receivables/' && method === 'GET') return json({ results: receivableRows, summary: receivablesSummary });
    if (apiPath.startsWith('accounting/card-snapshots/') && method === 'GET') return json({ results: [], meta: {} });
    if (apiPath === 'accounting/collection-accounts/' && method === 'GET') return json({ results: [collection], meta: { pending_total: '123456789.00' } });
    if (apiPath === 'admin/billing-context/projects/1/options/' && method === 'GET') {
      return json({ project_id: 1, project_name: 'Proyecto fixture', hosting_id: null,
        contracts: [{ id: 10, title: 'Contrato fixture', amendments: [] }] });
    }
    if (apiPath.startsWith('accounting/collection-accounts/next-number/') && method === 'GET') return json({ suggested_number: 'CC-RESP-001', billing_code: 'RESP', issuer_city: 'Bogotá' });
    if (apiPath === 'accounting/collection-accounts/preview/' && method === 'POST') {
      const body = route.request().postDataJSON();
      return json({
        subject: `Cuenta de cobro CC-RESP-001 — ${body.billing_concept}`,
        html_body: `<p>${body.billing_concept}</p>`,
        public_number: 'CC-RESP-001',
        total: body.items[0].amount,
        due_date: '2026-09-09',
        customer_email: body.customer.email,
        pdf_url: collectionPreviewPdf,
      });
    }
    if (apiPath === collectionPreviewPdf.replace(/^\/api\//, '') && method === 'GET') {
      return { status: 200, contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF\n' };
    }
    if (apiPath === 'accounting/incomes/create/' && method === 'POST') return json({ ...income, id: 2 });
    if (apiPath === 'accounting/incomes/1/liquidate/' && method === 'POST') return json({ ...income, payment_status: 'paid', pending_amount: '0.00' });
    if (apiPath === 'accounting/collections/create/' && method === 'POST') return json({ ...collection, id: 2 });
    if (apiPath === 'accounting/collections/1/register-payment/' && method === 'POST') return json({ ...collection, status: 'paid', pending_amount: '0.00' });
    if (apiPath.startsWith('proposals/client-profiles/search/')) return json([{ id: 1, name: income.client_name, email: 'client@fixture.test' }]);
    return null;
  });
}

async function openIncomesFromPanel(page) {
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < 1024) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  await page.getByRole('link', { name: 'Ingresos', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ingresos', exact: true })).toHaveText('Ingresos');
}

test.describe('accounting compact decision special', () => {
  test.use(viewportUse('compact'));
  test('pocket card preserves Saldo después after sorting the long movement', { tag: ['@flow:admin-accounting-pocket', '@outcome:success', '@responsive-special:accounting', '@viewport:compact', '@responsive-batch:accounting-special-1'] }, async ({ page }) => {
    await setup(page);
    // quality: allow-deep-link (the narrow pocket representation is the responsive decision under test)
    await page.goto('/en-us/panel/accounting/pocket', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('pocket-card-sort-concept').click();
    await expect(page.getByTestId('pocket-card-1')).toContainText('Saldo después');
    await expect(page.getByTestId('pocket-running-balance-1')).toHaveText('$123.456.789');
  });
});

test.describe('accounting portrait grouping and filters special', () => {
  test.use(viewportUse('portrait'));
  test('grouped collections restore the client header with the long amount', { tag: ['@flow:admin-accounting-collection-grouping', '@outcome:success', '@responsive-special:accounting', '@viewport:portrait', '@responsive-batch:accounting-special-1'] }, async ({ page }) => {
    await setup(page);
    // quality: allow-deep-link (the special isolates grouped-header touch reachability)
    await page.goto('/en-us/panel/accounting/collections', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('collections-view-classic')).toHaveAttribute('aria-selected', 'true');
    await page.getByTestId('collections-view-grouped').click();
    await expect(page.getByTestId('collections-view-grouped')).toHaveAttribute('aria-selected', 'true');
    await page.getByTestId('collection-group-toggle-1').click();
    await expect(page.getByTestId('collection-group-toggle-1')).toHaveAttribute('aria-expanded', 'false');
    await page.getByTestId('collection-group-toggle-1').click();
    await expect(page.getByTestId('collection-group-1')).toContainText('123.456.789');
  });

  test('saved expected filter remains selectable before the long income row', { tag: ['@flow:admin-accounting-filters', '@outcome:success', '@responsive-special:accounting', '@viewport:portrait', '@responsive-batch:accounting-special-1'] }, async ({ page }) => {
    await setup(page);
    // quality: allow-deep-link (saved filters are a route-owned responsive control)
    await page.goto('/en-us/panel/accounting/incomes', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('filter-tabs-select').selectOption('expected-only');
    await expect(page.getByTestId('filter-tabs-select')).toHaveValue('expected-only');
    await expect(page.getByTestId('accounting-row-1')).toContainText(longConcept);
  });
});

const modalGeometryByProfile = Object.freeze({
  compact: async (page, dialog) => {
    const box = await dialog.boundingBox();
    const viewport = page.viewportSize();
    expect(box.width).toBe(viewport.width);
    expect(box.height).toBe(viewport.height);
  },
  portrait: async (page, dialog) => {
    const box = await dialog.boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize().height);
  },
  landscape: async (page, dialog) => {
    const box = await dialog.boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize().height);
  },
  desktop: async (page, dialog) => {
    const box = await dialog.boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize().height);
  },
  wide: async (page, dialog) => {
    const box = await dialog.boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize().height);
  },
});
const openReceivableManagementByProfile = Object.freeze({
  compact: (dialog) => dialog.getByRole('combobox', { name: 'Secciones de pendientes por cobrar' }).selectOption('manage'),
  portrait: (dialog) => dialog.getByRole('combobox', { name: 'Secciones de pendientes por cobrar' }).selectOption('manage'),
  landscape: (dialog) => dialog.getByRole('tab', { name: /Gestionar candidatos/ }).click(),
  desktop: (dialog) => dialog.getByRole('tab', { name: /Gestionar candidatos/ }).click(),
  wide: (dialog) => dialog.getByRole('tab', { name: /Gestionar candidatos/ }).click(),
});

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`receivables grouping modal · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('candidate grouping controls remain reachable', { tag: ['@flow:admin-accounting-receivables', '@outcome:display', '@responsive-special:accounting', `@viewport:${profile}`, '@responsive-batch:accounting-special-4'] }, async ({ page }) => {
      await setup(page);
      // quality: allow-deep-link (the catalog flow covers panel entry; this special isolates modal controls across responsive profiles)
      await page.goto('/en-us/panel/accounting', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('accounting-card-receivables').click();
      const dialog = page.getByRole('dialog', { name: 'Pendientes por cobrar', exact: true });
      await openReceivableManagementByProfile[profile](dialog);
      await expect(dialog.getByTestId('receivables-group-client')).toHaveAttribute('aria-selected', 'true');
      await dialog.getByTestId('receivables-group-project').click();
      await expect(dialog.getByTestId('receivables-group-project')).toHaveAttribute('aria-selected', 'true');
      await expect(dialog.getByTestId('receivable-candidate-group-none')).toContainText('Sin proyecto');
      const closeButton = dialog.getByRole('button', { name: 'Cerrar', exact: true });
      await assertSpecialModalGeometry(page, profile, dialog, closeButton);
      await closeButton.click();
      await expect(dialog).toHaveCount(0);
    });
  });
}

const longModalFlows = Object.freeze([
  {
    name: 'collection preview advances through both form steps',
    flow: 'admin-accounting-collection-create',
    dialog: (page) => page.getByRole('dialog', { name: 'Revisar antes de enviar', exact: true }),
    open: async (page) => {
      await page.goto('/en-us/panel/accounting/collections', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('collection-create-button').click();
      await page.getByTestId('collection-form-client').fill('Cliente con nombre muy largo');
      await page.getByTestId('client-autocomplete-option-1').click();
      await page.getByTestId('collection-form-income').click();
      await page.getByTestId('collection-form-income-option-3').click();
      await page.getByTestId('billing-nature').selectOption('contract');
      await page.getByTestId('billing-contract').selectOption('10');
      await page.getByTestId('collection-form-amount').fill('123456789');
      await page.getByTestId('collection-form-concept').fill(longConcept);
      await page.getByTestId('collection-form-preview').click();
    },
    assert: (dialog) => expect(dialog.getByTestId('collection-preview-subject')).toContainText(longConcept),
  },
  {
    name: 'liquidate exposes its final CTA',
    flow: 'admin-accounting-income-crud',
    outcome: 'display',
    dialog: (page) => page.getByRole('dialog', { name: 'Liquidar ingreso esperado', exact: true }),
    open: async (page) => {
      await openIncomesFromPanel(page);
      await page.getByTestId('income-actions-1').click();
      await page.getByTestId('income-action-liquidate-1').click();
    },
    assert: (dialog) => expect(dialog.getByTestId('income-liquidate-submit')).toHaveText('Liquidar'),
    // The fixture is a hosting charge with no recorded window, so the period
    // block renders below the payment row.
    layout: (dialog) => ({
      lines: [
        { fields: [dialog.getByTestId('income-liquidate-period'), dialog.getByTestId('income-liquidate-destination')] },
        {
          fields: [
            dialog.getByTestId('income-liquidate-period-cadence'),
            dialog.getByTestId('income-liquidate-period-start'),
            dialog.getByTestId('income-liquidate-period-end'),
          ],
          maxWidth: 210,
        },
      ],
    }),
  },
  {
    name: 'bulk payment shows its allocation breakdown',
    flow: 'admin-accounting-income-bulk-settle',
    dialog: (page) => page.getByRole('dialog', { name: 'Registrar abono', exact: true }),
    open: async (page) => {
      await page.goto('/en-us/panel/accounting/incomes?accounting_incomeTab=all', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('accounting-row-1').getByRole('checkbox').click();
      await page.getByTestId('incomes-bulk-actions').click();
      await page.getByRole('menuitem', { name: 'Registrar abono', exact: true }).click();
    },
    assert: (dialog) => expect(dialog.getByTestId('income-bulk-settle-modal')).toContainText('Registrar abono'),
  },
  {
    name: 'new income exposes its hosting period block',
    flow: 'admin-accounting-income-crud',
    dialog: (page) => page.getByRole('dialog', { name: 'Nuevo Ingreso', exact: true }),
    open: async (page, dialog) => {
      await page.goto('/en-us/panel/accounting/incomes', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('incomes-new-button').click();
      await dialog.getByTestId('income-form-origin').getByRole('tab', { name: 'Hosting', exact: true }).click();
    },
    assert: (dialog) => expect(dialog.getByTestId('income-form-period-cadence')).toBeVisible(),
  },
]);

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`accounting long modals · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    for (const modalFlow of longModalFlows) {
      test(modalFlow.name, { tag: [`@flow:${modalFlow.flow}`, `@outcome:${modalFlow.outcome ?? 'success'}`, '@responsive-special:accounting', `@viewport:${profile}`, '@responsive-batch:accounting-special-2'] }, async ({ page }) => {
        await setup(page);
        // quality: allow-deep-link (each modal is opened from its own catalog list after mounting the responsive surface)
        const dialog = modalFlow.dialog(page);
        await modalFlow.open(page, dialog);
        await expect(dialog).toHaveCount(1);
        await modalFlow.assert(dialog);
        await modalGeometryByProfile[profile](page, dialog);
        if (modalFlow.layout) await expectCompactModal(dialog, page.viewportSize(), modalFlow.layout(dialog));
        await dialog.press('Escape');
        await expect(dialog).toHaveCount(0);
      });
    }
  });
}

const inlineClient = Object.freeze({
  id: 501,
  name: 'Cliente Inline Responsivo',
  email: 'inline@fixture.test',
  phone: '3001234567',
  company: 'Empresa Inline Responsiva',
  nit: '901234567',
  is_email_placeholder: false,
});

function hostingRow(overrides = {}) {
  return {
    id: 99,
    client: inlineClient.id,
    client_display_name: inlineClient.name,
    client_name: inlineClient.company,
    domain_url: 'https://inline-responsive.test',
    monthly_value: '38333.00',
    payment_modality: 'nine_month',
    payment_modality_label: 'Cada 9 meses',
    valid_from: '2026-09-01',
    valid_to: '2027-06-01',
    payment_per_cycle: '345000.00',
    total_paid: '0.00',
    cycles_count: 0,
    is_active: true,
    project: null,
    project_name: null,
    notes: '',
    ...overrides,
  };
}

async function setupHostingSpecial(page) {
  const calls = [];
  const hostings = [hostingRow({ id: 1, client: 1, client_display_name: income.client_name, client_name: income.client_name })];
  await setAuthLocalStorage(page, { token: 'accounting-hosting-special-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'accounting/hostings/' && method === 'GET') return json({ results: hostings, meta: { active_count: hostings.length, monthly_income: String(hostings.reduce((total, row) => total + Number(row.monthly_value), 0)), total_paid: '0.00', without_client_count: 0, without_project_count: hostings.length } });
    if (apiPath === 'accounting/hostings/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, body });
      const created = hostingRow(body);
      hostings.unshift(created);
      return { ...json(created), status: 201 };
    }
    if (apiPath === 'proposals/client-profiles/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, body });
      return { ...json({ ...inlineClient, ...body }), status: 201 };
    }
    if (apiPath.startsWith('proposals/client-profiles/search/')) return json([]);
    if (apiPath.startsWith('accounting/projects/by-client/')) return json([]);
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    return null;
  });
  return { calls };
}

function statementDetail(overrides = {}) {
  return {
    id: 2,
    card_name: 'T.C 0064',
    period: '2026-06',
    period_label: 'Junio 2026',
    status: 'draft',
    status_label: 'Borrador',
    purchases_total: '450000.00',
    previous_balance: '0.00',
    payments_total: '0.00',
    interest_and_fees: '0.00',
    minimum_payment: '45000.00',
    closing_balance: '450000.00',
    due_date: '2026-07-05',
    created_at: '2026-07-01T10:00:00Z',
    pdf_file_url: null,
    category_totals: [{ category: 'business', category_label: 'Negocio', label: 'Negocio', total: '450000.00' }],
    transactions: [{ id: 10, transaction_date: '2026-06-05', raw_description: 'PAGO SERVIDOR HETZNER', merchant_name: 'Hetzner', amount: '450000.00', category: 'business', category_label: 'Negocio', installment_label: '', original_amount: null, original_currency: '', is_identified: true }],
    ...overrides,
  };
}

async function setupStatementSpecial(page) {
  const calls = [];
  const state = { detail: statementDetail() };
  await setAuthLocalStorage(page, { token: 'accounting-statement-special-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath.startsWith('accounting/statements/status/')) return json({ year: 2026, year_options: [2026], months: [{ period: '2026-06', label: 'junio', applies: true, statements: [{ id: 2, card_name: 'T.C 0064', status: 'draft', status_label: 'Borrador' }] }] });
    if (apiPath === 'accounting/statements/2/' && method === 'GET') return json(state.detail);
    if (apiPath === 'accounting/statements/2/update/' && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, body });
      state.detail = statementDetail({ ...state.detail, ...body });
      return json(state.detail);
    }
    if (apiPath === 'accounting/statements/2/transactions/batch/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, body });
      state.detail = statementDetail({
        ...state.detail,
        transactions: [...state.detail.transactions, { id: 99, ...body.transactions[0] }],
      });
      return { ...json({ created: 1 }), status: 201 };
    }
    if (apiPath.startsWith('accounting/merchant-aliases')) return json({ results: [], meta: {} });
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    return null;
  });
  return { calls };
}

async function assertSpecialModalGeometry(page, profile, dialog, cta) {
  await expect(dialog).toHaveCount(1);
  await modalGeometryByProfile[profile](page, dialog);
  await cta.scrollIntoViewIfNeeded();
  const box = await cta.boundingBox();
  expect(box, 'La CTA final del modal debe ser medible').not.toBeNull();
  expect(box.y + box.height, 'La CTA final del modal debe quedar alcanzable').toBeLessThanOrEqual(page.viewportSize().height + 1);
}

const statementActionsByProfile = Object.freeze({
  compact: Object.freeze({
    openHeader: async (page) => {
      await page.getByTestId('statement-actions').click();
      await page.getByRole('menuitem', { name: 'Editar encabezado', exact: true }).click();
    },
    openTransaction: async (page) => {
      await page.getByTestId('statement-actions').click();
      await page.getByRole('menuitem', { name: 'Agregar transacción', exact: true }).click();
    },
  }),
  portrait: Object.freeze({
    openHeader: async (page) => {
      await page.getByTestId('statement-actions').click();
      await page.getByRole('menuitem', { name: 'Editar encabezado', exact: true }).click();
    },
    openTransaction: async (page) => {
      await page.getByTestId('statement-actions').click();
      await page.getByRole('menuitem', { name: 'Agregar transacción', exact: true }).click();
    },
  }),
  landscape: Object.freeze({
    openHeader: (page) => page.getByTestId('statement-edit-header').click(),
    openTransaction: (page) => page.getByTestId('statement-add-tx').click(),
  }),
  desktop: Object.freeze({
    openHeader: (page) => page.getByTestId('statement-edit-header').click(),
    openTransaction: (page) => page.getByTestId('statement-add-tx').click(),
  }),
  wide: Object.freeze({
    openHeader: (page) => page.getByTestId('statement-edit-header').click(),
    openTransaction: (page) => page.getByTestId('statement-add-tx').click(),
  }),
});

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`accounting special forms · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('inline client creation keeps the hosting CTA reachable', { tag: ['@flow:admin-accounting-hostings', '@outcome:success', '@responsive-special:accounting', `@viewport:${profile}`, '@responsive-batch:accounting-special-3'] }, async ({ page }) => {
      const { calls } = await setupHostingSpecial(page);
      // quality: allow-deep-link (the special isolates a long form owned by the hostings list)
      await page.goto('/en-us/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('hostings-new-button').click();
      const dialog = page.getByRole('dialog', { name: 'Nuevo Hosting', exact: true });
      await page.getByTestId('hosting-form-client').fill(inlineClient.name);
      await page.getByTestId('client-autocomplete-create-new').click();
      const inlinePanel = page.getByTestId('hosting-form-inline-client');
      await expect(inlinePanel).toContainText('Crear cliente nuevo');
      await inlinePanel.getByTestId('hosting-form-inline-client-name').fill(inlineClient.name);
      await inlinePanel.getByTestId('hosting-form-inline-client-email').fill(inlineClient.email);
      await inlinePanel.getByTestId('hosting-form-inline-client-company').fill(inlineClient.company);
      await inlinePanel.getByTestId('hosting-form-inline-client-save').click();
      await expect(page.getByTestId('hosting-form-client')).toHaveValue(inlineClient.name);
      await page.getByTestId('hosting-form-client-name').fill(inlineClient.company);
      await page.getByTestId('hosting-form-domain').fill('https://inline-responsive.test');
      await page.getByTestId('hosting-form-monthly').fill('38333');
      await page.getByTestId('hosting-form-modality').selectOption('nine_month');
      await expect(page.getByTestId('hosting-form-modality')).toHaveValue('nine_month');
      await page.getByLabel('Vigente desde', { exact: true }).fill('2026-09-01');
      await page.getByLabel('Vigente hasta', { exact: true }).fill('2027-06-01');
      await page.getByTestId('hosting-form-per-cycle').fill('345000');
      const submit = page.getByTestId('hosting-form-submit');
      await expect(submit).toHaveText('Guardar');
      await assertSpecialModalGeometry(page, profile, dialog, submit);
      await submit.click();
      await expect(dialog).toHaveCount(0);
      await expect(page.getByTestId('accounting-row-99')).toContainText(inlineClient.name);
      expect(calls.find(({ apiPath }) => apiPath === 'proposals/client-profiles/create/').body.name).toBe(inlineClient.name);
      const hostingCall = calls.find(({ apiPath }) => apiPath === 'accounting/hostings/create/');
      expect(hostingCall.body.client_name).toBe(inlineClient.company);
      expect(hostingCall.body.payment_modality).toBe('nine_month');
      expect(hostingCall.body).toMatchObject({
        amount: 345000, amount_mode: 'vat_included', vat_rate: 19,
      });
    });

    test('draft statement preserves the added purchase', { tag: ['@flow:admin-accounting-statements', '@outcome:success', '@responsive-special:accounting', `@viewport:${profile}`, '@responsive-batch:accounting-special-3'] }, async ({ page }) => {
      const { calls } = await setupStatementSpecial(page);
      // quality: allow-deep-link (the special begins at the statements grid, then opens the draft through its chip)
      await page.goto('/en-us/panel/accounting/statements', { waitUntil: 'domcontentloaded' });
      await page.getByTestId('statement-chip-2').click();
      await expect(page.getByTestId('statement-detail')).toContainText('Junio 2026');
      await statementActionsByProfile[profile].openHeader(page);
      const headerDialog = page.getByRole('dialog', { name: 'Editar encabezado del extracto', exact: true });
      const headerSubmit = headerDialog.getByTestId('statement-header-form-submit');
      await headerDialog.getByTestId('statement-header-purchases').fill('500000');
      await expect(headerSubmit).toHaveText('Guardar');
      await assertSpecialModalGeometry(page, profile, headerDialog, headerSubmit);
      await headerSubmit.click();
      await expect(headerDialog).toHaveCount(0);
      await expect(page.getByTestId('statement-detail')).toContainText('500.000');
      await statementActionsByProfile[profile].openTransaction(page);
      const transactionDialog = page.getByRole('dialog', { name: 'Agregar transacción', exact: true });
      const transactionSave = transactionDialog.getByTestId('tx-save');
      await transactionDialog.getByTestId('tx-date-input').fill('2026-06-20');
      await transactionDialog.getByTestId('tx-description-input').fill('COMPRA EXITO CALLE 80');
      await transactionDialog.getByTestId('tx-merchant-input').fill('Éxito');
      await transactionDialog.getByTestId('tx-amount-input').fill('120000');
      await expect(transactionSave).toHaveText('Guardar');
      await assertSpecialModalGeometry(page, profile, transactionDialog, transactionSave);
      await transactionSave.click();
      await expect(transactionDialog).toHaveCount(0);
      await expect(page.getByTestId('statement-tx-99')).toContainText('COMPRA EXITO CALLE 80');
      expect(calls.find(({ apiPath }) => apiPath === 'accounting/statements/2/update/').body.purchases_total).toBe(500000);
      expect(calls.find(({ apiPath }) => apiPath === 'accounting/statements/2/transactions/batch/').body.transactions[0].raw_description).toBe('COMPRA EXITO CALLE 80');
    });
  });
}
