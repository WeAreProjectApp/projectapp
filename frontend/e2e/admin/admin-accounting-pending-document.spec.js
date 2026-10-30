import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';

test.setTimeout(60_000);
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
const client = { id: 5, name: 'Ana Pérez', email: 'ana@acme.test', company: 'Acme SAS', nit: '901234567', cedula: '', is_email_placeholder: false };
const income = { id: 21, client: 5, client_name: 'Acme SAS', project: 7, project_name: 'Proyecto Aurora',
  concept: 'Trabajo acordado', kind: 'expected', kind_label: 'Esperado', total_amount: '150000.00',
  gustavo_amount: '75000.00', carlos_amount: '75000.00', vat_rate: null,
  paid_amount: '0.00', pending_amount: '150000.00', payment_status: 'pending', collection_account: null };
const pendingContext = () => ({ status: 'document_pending', document_pending: true, version: 1,
  nature: null, contract: null, amendment: null, hosting_id: null, pending_by: 9001, pending_at: '2026-10-29T12:00:00Z' });
const account = (id, context) => ({ id, public_number: `PA-ACME-${String(id).padStart(3, '0')}`, title: 'Trabajo acordado', billing_concept: 'Trabajo acordado',
  client: 5, client_display_name: 'Acme SAS', customer_name: 'Acme SAS', customer_email: client.email,
  project_id: 7, project_name: 'Proyecto Aurora', currency: 'COP', total: '150000.00', vat_rate: null,
  commercial_status: 'issued', commercial_status_label: 'Emitida', origin: 'project', origin_label: 'Proyecto',
  issue_date: '2026-10-29', due_date: null, income_record_id: null, is_overdue: false, context });

async function arrange(page, { rejectCompletion = false } = {}) {
  const state = { rows: [account(1, { status: 'pending', version: 0 }), account(42, pendingContext())], calls: [] };
  await setAuthLocalStorage(page, { token: 'e2e-pending-document', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'accounting/settings/') return json({ collection_accounts_view_mode: 'classic', collection_accounts_group_by: 'client' });
    if (apiPath === 'panel/projects/') return json({ results: [{ id: 7, name: 'Proyecto Aurora', client: { name: 'Acme SAS' } }] });
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath.startsWith('proposals/client-profiles/search/')) return json([client]);
    if (apiPath === 'proposals/client-profiles/5/') return json(client);
    if (apiPath === 'accounting/incomes/') return json({ results: [income], meta: {} });
    if (apiPath === 'accounting/incomes/21/') return json(income);
    if (apiPath === 'accounting/incomes/21/detail/') return json({ income, liquid: [], expenses: [] });
    if (apiPath === 'admin/billing-context/projects/7/options/') return json({ project_id: 7, project_name: 'Proyecto Aurora', contracts: [{ id: 10, title: 'Contrato Aurora', amendments: [] }], hosting_id: null, contract_sources: [] });
    if (apiPath === 'admin/billing-context/projects/7/hosting/') return json({ overview: { subscription: null } });
    if (apiPath === 'accounting/collection-accounts/next-number/') return json({ suggested_number: 'PA-ACME-009', billing_code: 'ACME', issuer_city: 'Bogotá' });
    if (apiPath === 'accounting/collection-accounts/preview/' && method === 'POST') {
      const body = route.request().postDataJSON(); state.calls.push({ apiPath, body });
      return json({ subject: 'Cuenta de cobro PA-ACME-009', html_body: '<p>Trabajo acordado: $150.000 COP</p>',
        public_number: 'PA-ACME-009', total: '150000.00', due_date: null, issue_date: '2026-10-29',
        customer_name: 'Acme SAS', customer_email: client.email, project_name: 'Proyecto Aurora', billing_concept: body.billing_concept,
        pdf_url: '/api/accounting/collection-accounts/preview/pending/PA-ACME-009.pdf' });
    }
    if (apiPath === 'accounting/collection-accounts/create/' && method === 'POST') {
      const body = route.request().postDataJSON(); state.calls.push({ apiPath, body });
      const created = { ...account(9, pendingContext()), income_record_id: 21, income_kind: 'expected' };
      state.rows.push(created); return json({ document: created, email_sent: true }, 201);
    }
    const context = apiPath.match(/^admin\/billing-context\/accounts\/(\d+)\/$/);
    if (context) {
      const row = state.rows.find(record => record.id === Number(context[1]));
      if (method === 'GET') return json(row.context);
      const body = route.request().postDataJSON(); state.calls.push({ apiPath, body });
      if (rejectCompletion) return json({ detail: 'El contexto cambió. Actualiza antes de continuar.' }, 409);
      row.context = { ...row.context, status: 'associated', document_pending: false, version: 2, nature: 'contract', contract: { id: 10, title: 'Contrato Aurora' } };
      return json(row.context);
    }
    if (apiPath === 'accounting/collection-accounts/') return json({ results: state.rows, meta: { document_pending_count: state.rows.filter(row => row.context?.document_pending).length } });
    if (apiPath.endsWith('.pdf') || apiPath.endsWith('/pdf/')) return { status: 200, contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF\n' };
    const detail = apiPath.match(/^accounting\/collection-accounts\/(\d+)\/$/);
    if (detail) return json({ ...state.rows.find(record => record.id === Number(detail[1])), items: [], payment_methods: [] });
    if (apiPath === 'panel/dashboard/') return json({ generated_at: '2026-10-29T12:00:00Z', finance: null,
      proposals: { pipeline_value: 0, pipeline_count: 0, total_proposals: 0, by_status: {} },
      operations: { tasks: {}, documents: {}, diagnostics: {}, emails: {}, hour_packages: {} },
      attention: state.rows.filter(row => row.context?.document_pending).length ? [{ type: 'collection_documents_pending', severity: 'warning', count: 1, meta: {} }] : [] });
    if (apiPath.startsWith('panel/dashboard/attention/collection_documents_pending/')) {
      const record = { id: 42, type: 'collection_documents_pending', title: 'PA-ACME-042', client: 'Acme SAS', amount: '150000', currency: 'COP', pending_at: '2026-10-29T12:00:00Z', eligible: true, destination: '/panel/accounting/collections?account=42&radar=1' };
      return json(apiPath.endsWith('/42/') ? record : { results: [record], total: 1, has_next: false, page: 1 });
    }
    return null;
  });
  return state;
}
async function openCollections(page) {
  await page.goto('/en-us/panel/accounting/collections', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByRole('heading', { name: 'Cuentas de cobro', exact: true })).toBeVisible();
  await expect(page.getByTestId('collection-open-42')).toBeVisible();
}
async function fillCreate(page) {
  await page.getByTestId('collection-create-button').click();
  await page.getByTestId('collection-form-client').fill('Acme');
  await page.getByTestId('client-autocomplete-option-5').click();
  await page.getByTestId('collection-form-income').click();
  await page.getByTestId('collection-form-income-option-21').click();
}

test('creates an explicitly pending account, filters it and completes it without closing the detail', {
  tag: ['@flow:admin-accounting-collection-create', '@flow:admin-accounting-collection-context', '@outcome:success'],
}, async ({ page }) => {
  const state = await arrange(page);
  await openCollections(page);
  await fillCreate(page);
  await page.getByRole('switch', { name: 'Dejar documento pendiente' }).click();
  await page.getByTestId('collection-form-preview').click();
  await expect(page.getByTestId('collection-preview-subject')).toContainText('PA-ACME-009');
  await page.getByTestId('collection-form-confirm').click();
  await page.getByTestId('confirm-modal-confirm').click();
  await expect(page.getByTestId('collection-open-9')).toBeVisible();
  const creation = state.calls.find(call => call.apiPath.endsWith('/create/')).body;
  expect(creation.document_pending).toBe(true);
  expect(creation.billing_nature).toBeNull();
  expect(creation.contract_id).toBeNull();
  await page.getByRole('button', { name: 'Documento pendiente', exact: true }).click();
  await expect(page.getByTestId('collection-open-1')).toHaveCount(0);
  await page.getByTestId('collection-open-9').click();
  const modal = page.getByTestId('collection-detail-modal');
  await expect(modal.getByRole('heading', { name: 'Completar documento vinculado' })).toBeVisible();
  await modal.getByTestId('billing-nature').selectOption('contract');
  await modal.getByTestId('billing-contract').selectOption('10');
  await modal.getByRole('textbox', { name: 'Razón de la asociación o corrección' }).fill('Contrato recibido y revisado.');
  await modal.getByRole('button', { name: 'Guardar asociación', exact: true }).click();
  await expect(modal.getByTestId('pending-billing-document-icon')).toHaveCount(0);
  await expect(modal).toBeVisible();
  await modal.getByRole('button', { name: 'Cerrar', exact: true }).click();
  await expect(page.getByTestId('collection-open-9')).toHaveCount(0);
  await expect(page.getByTestId('collection-open-42')).toBeVisible();
});

test('requires an explicit decision when the project document is missing', {
  tag: ['@flow:admin-accounting-collection-create', '@outcome:error'],
}, async ({ page }) => {
  const state = await arrange(page);
  await openCollections(page);
  await fillCreate(page);
  await page.getByTestId('collection-form-preview').click();
  await expect(page.getByTestId('collection-form-project-context-error')).toContainText('elige si cobras');
  expect(state.calls.filter(call => call.apiPath.endsWith('/preview/'))).toHaveLength(0);
});

test('retains the pending marker when completing a stale context fails', {
  tag: ['@flow:admin-accounting-collection-context', '@outcome:failure'],
}, async ({ page }) => {
  await arrange(page, { rejectCompletion: true });
  await openCollections(page);
  await page.getByTestId('collection-open-42').click();
  const modal = page.getByTestId('collection-detail-modal');
  await modal.getByTestId('billing-nature').selectOption('contract');
  await modal.getByTestId('billing-contract').selectOption('10');
  await modal.getByRole('textbox', { name: 'Razón de la asociación o corrección' }).fill('Contrato recibido.');
  await modal.getByRole('button', { name: 'Guardar asociación', exact: true }).click();
  await expect(modal.getByRole('alert')).toContainText('El contexto cambió');
  await expect(modal.getByTestId('pending-billing-document-icon')).toBeVisible();
});

test('opens the exact pending account from the financial radar', {
  tag: ['@flow:admin-dashboard-attention-radar', '@flow:admin-accounting-collection-context', '@outcome:success'],
}, async ({ page }) => {
  await arrange(page);
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await page.getByTestId('attention-item-collection_documents_pending').click();
  await page.getByTestId('radar-record-collection_documents_pending-42').click();
  await expect(page.getByTestId('radar-detail-modal')).toContainText('PA-ACME-042');
  await page.getByTestId('radar-detail-destination').click();
  await expect(page.getByTestId('collection-detail-modal')).toContainText('PA-ACME-042');
  await expect(page.getByRole('heading', { name: 'Completar documento vinculado' })).toBeVisible();
});

for (const width of [390, 640, 768, 1024, 1440]) {
  test(`pending status tooltip responds to focus and touch at ${width}px`, {
    tag: ['@flow:admin-accounting-collections', '@outcome:success'],
  }, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await arrange(page);
    await openCollections(page);
    const marker = page.getByTestId('accounting-row-42').getByRole('button', { name: 'Hace falta el documento vinculado' });
    await marker.focus();
    await expect(page.getByRole('tooltip')).toContainText('Hace falta el documento vinculado');
    await marker.press('Escape');
    await expect(page.getByRole('tooltip')).toHaveCount(0);
    await marker.click();
    await expect(page.getByRole('tooltip')).toContainText('Hace falta el documento vinculado');
  });
}
