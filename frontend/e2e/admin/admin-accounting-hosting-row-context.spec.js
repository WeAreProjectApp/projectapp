import { expect, test } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { chooseHostingAction, gotoHostings, hostingRows } from '../helpers/accounting-hosting-cycles.js';
import { ADMIN_ACCOUNTING_HOSTING_BILLING } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const services = [
  { id: 1, name: 'Alfa', project: 10, client: 71, canonical: 31, payment: 48,
    period: ['2026-04-01', '2026-06-30'], balance: '180000.00', amount: '240000.00', received: '60000.00' },
  { id: 2, name: 'Beta', project: 20, client: 72, canonical: 32, payment: null,
    period: ['2026-07-01', '2026-09-30'], balance: '45000.00', amount: '45000.00', received: '0.00' },
];

function row(service) {
  const email = service.name.toLowerCase() + '@example.invalid';
  return {
    ...hostingRows({ billingSent: false })[0], id: service.id, project: service.project, client: service.client,
    client_name: 'Cliente ' + service.name, client_display_name: 'Cliente ' + service.name,
    project_name: 'Proyecto ' + service.name, display_label: 'Hosting ' + service.name,
    domain_url: service.name.toLowerCase() + '.example.invalid', client_email: email, billing_email: email,
    payment_per_cycle: '999999.00', payment_modality: 'quarterly', payment_modality_label: 'Trimestral',
  };
}

function context(service) {
  return {
    overview: { project_id: service.project, hosting_id: service.canonical, reconciliation_required: false,
      accounting_sources: [{ id: service.id, associated: true, operational: true }] },
    selection: { requires_reconciliation: false, blockers: [] },
    billing_period: {
      project_id: service.project, project_hosting_id: service.canonical, hosting_record_id: service.id,
      client_id: service.client, currency: 'COP', period_start: service.period[0], period_end: service.period[1],
      source: service.payment ? 'subscription' : 'expected_income', hosting_payment_id: service.payment,
      income_id: service.payment ? null : 75, documents: [], amount: service.amount, received: service.received,
      balance: service.balance, state: service.payment ? 'partial' : 'pending', version: 'review-' + service.id,
    },
  };
}

async function openList(page, { conflict = false, wrongClient = false } = {}) {
  const writes = [];
  const json = (data, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(data) });
  await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9001, role: 'admin', is_staff: true } });
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { id: 9001, username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'accounting/hostings/' && method === 'GET') return json({ results: services.map(row), meta: {} });
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    const service = services.find(item => apiPath === `admin/billing-context/projects/${item.project}/hosting/`);
    if (service && method === 'GET') {
      const response = context(service);
      if (wrongClient) response.billing_period.client_id = services[1].client;
      return json(response);
    }
    if (method !== 'GET' && /^(accounting\/hostings\/|admin\/billing-context\/)/.test(apiPath)) {
      writes.push({ apiPath, body: route.request().postDataJSON() });
      if (conflict) return json({ detail: 'El período cambió. Consulta de nuevo el período del servicio.' }, 400);
      return json({ document: { id: 93, public_number: 'DEV-0093' }, email_sent: true }, 201);
    }
    return null;
  });
  await gotoHostings(page);
  await expect(page.getByTestId('accounting-row-2')).toBeVisible();
  return writes;
}

const dialog = page => page.getByRole('dialog', { name: 'Enviar cuenta de cobro' });

async function reviewRow(page, service) {
  await chooseHostingAction(page, service.id, 'send-billing');
  const preview = dialog(page);
  const record = row(service);
  await expect(preview).toContainText(record.project_name);
  await expect(preview).toContainText(record.client_display_name);
  await expect(preview).toContainText(record.domain_url);
  await expect(preview).toContainText(record.billing_email);
  await expect(preview.getByTestId('hosting-period-summary')).toContainText(service.period.join(' — '));
  await expect(preview.getByRole('button', { name: 'Enviar al cliente' })).toBeEnabled();
  await expect(preview).toContainText('PDF adjunto');
  await expect(preview).toContainText('próxima renovación');
  await expect(preview.getByRole('combobox')).toHaveCount(0);
  await expect(preview.getByRole('button', { name: 'Usar este hosting' })).toHaveCount(0);
  await expect(preview).not.toContainText('999.999');
  return preview;
}

test('each hosting row previews only its own account before cancellation', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:display'],
}, async ({ page }, testInfo) => {
  // quality: allow-deep-link (the starting URL is the Spanish Panel home; the operator reaches Hostings through its sidebar link)
  const writes = await openList(page);
  const alfa = await reviewRow(page, services[0]);
  await alfa.screenshot({ path: testInfo.outputPath('fila-alfa.png') });
  await alfa.getByRole('button', { name: 'Cancelar' }).click();
  await expect(alfa).toHaveCount(0);
  const beta = await reviewRow(page, services[1]);
  await expect(beta).not.toContainText('alfa@example.invalid');
  await beta.screenshot({ path: testInfo.outputPath('fila-beta.png') });
  await page.keyboard.press('Escape');
  await expect(beta).toHaveCount(0);
  expect(writes).toEqual([]);
  await expect(page.getByText('Cobro enviado')).toHaveCount(0);
});

test('confirmation posts the decision reviewed for the second row', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const writes = await openList(page);
  await chooseHostingAction(page, 2, 'send-billing');
  await expect(dialog(page)).toContainText('$45.000 COP');
  await dialog(page).getByRole('button', { name: 'Enviar al cliente' }).click();

  await expect(page.getByText('Cuenta de cobro enviada')).toBeVisible();
  expect(writes).toEqual([{ apiPath: 'accounting/hostings/2/send-collection-account/',
    body: { hosting_payment_id: null, period_version: 'review-2' } }]);
});

test('a period changed since preview asks the operator to review it again', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:failure'],
}, async ({ page }) => {
  const writes = await openList(page, { conflict: true });
  await chooseHostingAction(page, 1, 'send-billing');
  await dialog(page).getByRole('button', { name: 'Enviar al cliente' }).click();

  await expect(page.getByText('No se pudo enviar la cuenta de cobro')).toBeVisible();
  await expect(page.getByText('El período cambió. Consulta de nuevo el período del servicio.')).toBeVisible();
  await expect(page.getByText('Cobro enviado')).toHaveCount(0);
  expect(writes).toHaveLength(1);
});

test('a period owned by a different client blocks the row with a correction', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:error'],
}, async ({ page }) => {
  const writes = await openList(page, { wrongClient: true });
  await chooseHostingAction(page, 1, 'send-billing');
  const preview = dialog(page);
  await expect(preview.getByRole('alert')).toContainText('no coinciden');
  await expect(preview.getByRole('button', { name: 'Revisar conciliación del hosting' })).toBeVisible();
  await expect(preview.getByRole('button', { name: 'Enviar al cliente' })).toBeDisabled();
  await expect(preview.getByTestId('hosting-period-summary')).toHaveCount(0);
  await preview.getByRole('button', { name: 'Cancelar' }).click();
  expect(writes).toEqual([]);
});
