// qa: draft-unvalidated (2026-11-06 — app not running)
/**
 * PA-230 — linking a hosting while preparing a collection account.
 *
 * These journeys catch the regression where a hosting income exposed only an
 * empty selector, or sent the operator to an opaque reconciliation page that
 * discarded the collection-account draft.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';

test.setTimeout(60_000);

const client = {
  id: 5,
  name: 'Ana Pérez',
  company: 'Acme Soluciones',
  email: 'ana@acme.test',
  phone: '',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
};

const income = {
  id: 1,
  concept: 'Hosting Aurora noviembre',
  kind: 'expected',
  kind_label: 'Esperado',
  period: '2026-11',
  period_label: 'Noviembre 2026',
  period_date: '2026-11-01',
  destination: 'company',
  destination_label: 'Empresa',
  ledger: 'company',
  ledger_label: 'Empresa',
  total_amount: '120000.00',
  gustavo_amount: '0.00',
  carlos_amount: '0.00',
  company_amount: '120000.00',
  expected_income: null,
  pocket_movement: null,
  paid_amount: '0.00',
  pending_amount: '120000.00',
  payment_status: 'pending',
  payment_status_label: 'Pendiente',
  is_receivable_candidate: false,
  collection_confidence: '',
  collection_confidence_label: '',
  reminders_muted: false,
  reminders_muted_until: null,
  client: client.id,
  client_name: client.name,
  project: 10,
  project_name: 'Proyecto Aurora',
  origin: 'hosting',
  origin_label: 'Hosting',
  notes: '',
  has_collection_account: false,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T10:00:00Z',
};

function json(body, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

function linkedCandidate(id = 70, domain = 'aurora.test') {
  return {
    project_hosting_id: id,
    hosting_record_id: null,
    domain_url: domain,
    payment_modality: 'quarterly',
    is_active: true,
    historical: false,
    selectable: true,
    requires_association: false,
  };
}

function unlinkedCandidate() {
  return {
    project_hosting_id: null,
    hosting_record_id: 31,
    domain_url: 'pendiente.aurora.test',
    payment_modality: 'semiannual',
    is_active: true,
    historical: false,
    selectable: true,
    requires_association: true,
  };
}

function hostingResponse(state) {
  const linked = state.mode === 'linked';
  const candidates = state.mode === 'unlinked' ? [unlinkedCandidate()]
    : state.mode === 'linked' ? [linkedCandidate(state.hostingId, state.domain)] : [];
  const blockers = state.mode === 'contradictory'
    ? [{ message: 'El dominio pendiente.aurora.test contradice el registro operativo del proyecto.' }]
    : [];
  return {
    inventory: {
      version: state.version,
      project_name: 'Proyecto Aurora',
      hosting: linked ? { id: state.hostingId, subscription_id: null, hosting_record_ids: [31], operational_record_id: 31 } : { subscription_id: null, hosting_record_ids: [], operational_record_id: null },
      subscriptions: [],
      accounting_sources: [{ id: 31, domain_url: 'pendiente.aurora.test', payment_modality: 'semiannual', payment_per_cycle: '240000.00', mapped_hosting_id: linked ? state.hostingId : null, conflicts: [] }],
      pending_account_ids: [],
      hosting_accounts: [],
      events: [],
    },
    overview: {
      hosting_id: linked ? state.hostingId : null,
      subscription: null,
      accounting_sources: [{ id: 31, cycles: [] }],
      evidence_groups: [],
    },
    selection: {
      version: state.version,
      candidates,
      blockers,
      can_create: state.mode === 'empty',
      requires_reconciliation: state.mode === 'contradictory',
    },
  };
}

async function arrange(page, { mode = 'linked', failReview = false } = {}) {
  const state = { mode, hostingId: 70, domain: 'aurora.test', version: 4, failedReview: false };
  const calls = [];
  await setAuthLocalStorage(page, {
    token: 'e2e-panel-token',
    userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { id: 1, username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'accounting/settings/' && method === 'GET') return json({ income_default_view_mode: 'classic' });
    if (apiPath === 'accounting/incomes/' && method === 'GET') return json({ results: [income], meta: {} });
    if (apiPath === 'accounting/incomes/1/' && method === 'GET') return json(income);
    if (apiPath === 'proposals/client-profiles/5/' && method === 'GET') return json(client);
    if (apiPath.startsWith('accounting/collection-accounts/next-number/') && method === 'GET') {
      return json({ suggested_number: 'PA-AUR-001', billing_code: 'AUR', issuer_city: 'Bogotá' });
    }
    if (apiPath === 'admin/billing-context/projects/10/options/' && method === 'GET') {
      return json({ project_id: 10, project_name: 'Proyecto Aurora', hosting_id: state.mode === 'linked' ? state.hostingId : null, contracts: [], contract_sources: [], delivery_version: state.version });
    }
    if (apiPath === 'admin/billing-context/projects/10/hosting/' && method === 'GET') return json(hostingResponse(state));
    if (apiPath === 'admin/billing-context/projects/10/hosting/' && method === 'POST') {
      const body = route.request().postDataJSON();
      const preview = new URL(route.request().url()).searchParams.get('preview');
      calls.push({ apiPath, method, preview, body });
      if (preview === '1') {
        if (failReview && !state.failedReview) {
          state.failedReview = true;
          return json({ detail: 'No se pudo revisar el vínculo. Inténtalo de nuevo.' }, 503);
        }
        return json({ proposal: { ...body } });
      }
      state.mode = 'linked';
      state.hostingId = 70;
      state.domain = 'pendiente.aurora.test';
      return json({ id: state.hostingId });
    }
    if (apiPath === 'accounting/hostings/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      state.mode = 'linked';
      state.hostingId = 77;
      state.domain = body.domain_url;
      return json({ id: state.hostingId, ...body }, 201);
    }
    if (apiPath === 'accounting/collection-accounts/preview/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return json({
        subject: 'Cuenta de cobro PA-AUR-001 — Hosting Aurora noviembre',
        customer_email: client.email,
        public_number: 'PA-AUR-001',
        total: '120000.00',
        pdf_url: '/api/accounting/collection-accounts/preview/e2e/PA-AUR-001.pdf',
        html_body: '<p>Cuenta de cobro de prueba</p>',
      });
    }
    return null;
  });
  return { calls, state };
}

async function openIncomeAccount(page) {
  await page.goto('/es-co/panel/accounting/incomes?accounting_incomeTab=all', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByRole('heading', { name: 'Ingresos', exact: true })).toHaveText('Ingresos');
  await page.getByTestId('income-actions-1').click();
  await page.getByTestId('income-action-generate-collection-1').click();
  await expect(page.getByRole('heading', { name: 'Nueva cuenta de cobro', exact: true })).toHaveText('Nueva cuenta de cobro');
  await page.getByTestId('billing-nature').selectOption('hosting');
}

async function chooseHosting(page, value) {
  await page.getByTestId('billing-hosting-choice').selectOption(value);
  await page.getByTestId('billing-hosting-review').click();
}

test.describe('PA-230 hosting link from a collection account', () => {
  test('navigating from accounting to income billing shows the recognizable linked hosting', {
    tag: ['@flow:admin-accounting-hosting-link', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the hosting selector is empty even when the project already has a linked hosting.
    await arrange(page);
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await waitForNuxtApp(page);
    await page.locator('aside').getByRole('link', { name: 'Resumen', exact: true }).click();
    await page.getByTestId('accounting-subnav-incomes').click();
    await expect(page.getByRole('heading', { name: 'Ingresos', exact: true })).toHaveText('Ingresos');
    await page.getByTestId('income-actions-1').click();
    await page.getByTestId('income-action-generate-collection-1').click();
    await page.getByTestId('billing-nature').selectOption('hosting');
    await expect(page.getByTestId('billing-hosting-choice').getByRole('option', { name: 'aurora.test · Trimestral · Activo' }))
      .toHaveCount(1);
  });

  test('confirming an eligible hosting record unlocks the collection preview', {
    tag: ['@flow:admin-accounting-hosting-link', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where a reviewed existing record never becomes the selected project hosting for the account.
    const { calls } = await arrange(page, { mode: 'unlinked' });
    await openIncomeAccount(page);
    await chooseHosting(page, 'record:31');
    await expect(page.getByTestId('billing-hosting-link-preview')).toContainText('pendiente.aurora.test · Semestral · Activo');
    await page.getByTestId('billing-hosting-confirm').click();
    await expect(page.getByTestId('billing-hosting-confirmed')).toHaveText('Hosting confirmado para esta cuenta.');
    await page.getByTestId('collection-form-preview').click();
    await expect(page.getByTestId('collection-preview-subject')).toContainText('PA-AUR-001');
    expect(calls.filter((call) => call.apiPath === 'admin/billing-context/projects/10/hosting/'))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ preview: '1', body: expect.objectContaining({ hosting_record_ids: [31], operational_record_id: 31, expected_version: 4 }) }),
        expect.objectContaining({ preview: null, body: expect.objectContaining({ hosting_record_ids: [31], operational_record_id: 31, expected_version: 4 }) }),
      ]));
    expect(calls.find((call) => call.apiPath === 'accounting/collection-accounts/preview/').body)
      .toMatchObject({ billing_nature: 'hosting', project_hosting_id: 70, income_record_id: 1 });
  });

  test('creating a missing hosting preserves the account draft for selection', {
    tag: ['@flow:admin-accounting-hosting-link', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where opening or cancelling hosting creation loses the account’s income, client, or typed fields.
    const { calls } = await arrange(page, { mode: 'empty' });
    await openIncomeAccount(page);
    await page.getByTestId('collection-form-concept').fill('Hosting Aurora personalizado');
    await page.getByTestId('collection-form-description').fill('Periodo noviembre con soporte ampliado');
    await expect(page.getByTestId('billing-hosting-empty')).toHaveText('Este proyecto no tiene hosting registrado. Crea uno para continuar con la cuenta de cobro.');
    await page.getByTestId('billing-hosting-create').click();
    await expect(page.getByTestId('hosting-form-context')).toHaveText('Cliente: Ana Pérez · Proyecto: Proyecto Aurora');
    const hostingDialog = page.getByRole('dialog').filter({ has: page.getByRole('heading', { name: 'Nuevo Hosting', exact: true }) });
    await hostingDialog.getByRole('button', { name: 'Cancelar', exact: true }).click();
    await expect(page.getByTestId('collection-form-concept')).toHaveValue('Hosting Aurora personalizado');
    await expect(page.getByTestId('collection-form-description')).toHaveValue('Periodo noviembre con soporte ampliado');
    await page.getByTestId('billing-hosting-create').click();
    await page.getByTestId('hosting-form-domain').fill('nuevo.aurora.test');
    await page.getByTestId('hosting-form-monthly').fill('40000');
    await page.getByTestId('hosting-form-submit').click();
    await expect(page.getByTestId('billing-hosting-choice').getByRole('option', { name: 'nuevo.aurora.test · Trimestral · Activo' })).toHaveCount(1);
    await chooseHosting(page, 'hosting:77');
    await expect(page.getByTestId('billing-hosting-confirmed')).toHaveText('Hosting confirmado para esta cuenta.');
    expect(calls.find((call) => call.apiPath === 'accounting/hostings/create/').body)
      .toMatchObject({ client: 5, project: 10, domain_url: 'nuevo.aurora.test' });
  });

  test('a contradictory hosting returns the reconciled draft to preview', {
    tag: ['@flow:admin-accounting-hosting-link', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where reconciliation hides the contradiction or discards the collection account fields on return.
    await arrange(page, { mode: 'contradictory' });
    await openIncomeAccount(page);
    await page.getByTestId('collection-form-concept').fill('Hosting Aurora conciliado');
    await page.getByTestId('collection-form-description').fill('Conservar esta descripción al conciliar');
    await page.getByTestId('collection-form-amount').fill('120000');
    await expect(page.getByTestId('billing-hosting-blockers')).toHaveText('El dominio pendiente.aurora.test contradice el registro operativo del proyecto.');
    await page.getByTestId('billing-hosting-reconcile').click();
    await expect(page).toHaveURL(/returnDraft=/);
    await expect(page.getByTestId('hosting-reconciliation-blockers')).toContainText('El dominio pendiente.aurora.test');
    await page.getByRole('checkbox', { name: '#31 · pendiente.aurora.test', exact: true }).check();
    await page.getByLabel('Origen contable operativo').selectOption('31');
    await page.getByLabel('Razón').first().fill('Se verificó la contradicción con el cliente');
    await page.getByRole('button', { name: 'Previsualizar asociación' }).click();
    await expect(page.getByTestId('hosting-decision-summary')).toContainText('Registros contables que se asociarán');
    await page.getByRole('button', { name: 'Aplicar conciliación' }).click();
    await expect(page.getByRole('status')).toHaveText('Asociación guardada. Ya puedes volver a la cuenta de cobro.');
    await page.getByRole('link', { name: 'Volver a la cuenta de cobro' }).click();
    await expect(page).toHaveURL(/\/es-co\/panel\/accounting\/incomes(?:\?|$)/);
    await expect(page.getByRole('heading', { name: 'Nueva cuenta de cobro', exact: true })).toHaveText('Nueva cuenta de cobro');
    await expect(page.getByTestId('collection-form-concept')).toHaveValue('Hosting Aurora conciliado');
    await expect(page.getByTestId('collection-form-description')).toHaveValue('Conservar esta descripción al conciliar');
    await expect(page.getByTestId('collection-form-amount')).toHaveValue('120.000');
    await expect(page.getByTestId('collection-form-client-locked')).toContainText('Ana Pérez');
    await expect(page.getByTestId('collection-form-income-locked')).toContainText('Hosting Aurora noviembre');
    await chooseHosting(page, 'hosting:70');
    await page.getByTestId('collection-form-preview').click();
    await expect(page.getByTestId('collection-preview-subject')).toContainText('PA-AUR-001');
  });

  test('a failed hosting review preserves the account draft for retry', {
    tag: ['@flow:admin-accounting-hosting-link', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where a network failure clears the choice or leaves no recovery action before preview.
    const { calls } = await arrange(page, { mode: 'unlinked', failReview: true });
    await openIncomeAccount(page);
    await chooseHosting(page, 'record:31');
    await expect(page.getByTestId('billing-hosting-error')).toHaveText('No se pudo revisar el vínculo. Inténtalo de nuevo.');
    await page.getByTestId('billing-hosting-refresh').click();
    await chooseHosting(page, 'record:31');
    await expect(page.getByTestId('billing-hosting-link-preview')).toContainText('pendiente.aurora.test · Semestral · Activo');
    expect(calls.filter((call) => call.preview === '1')).toHaveLength(2);
  });
});
