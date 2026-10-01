/**
 * Administrative project billing context journeys. They protect explicit
 * reconciliation from registering money movements or mixing project links.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';

test.setTimeout(60_000);

const account = { id: 42, public_number: 'PA-AUR-LEG-042', total: '120000.00', currency: 'COP', commercial_status: 'issued', project_id: 7 };
const options = {
  project_id: 7, project_name: 'Proyecto Aurora', hosting_id: 70,
  contracts: [
    { id: 10, title: 'Contrato Aurora', amendments: [{ id: 11, title: 'Otrosí permitido' }] },
    { id: 12, title: 'Contrato ajeno', amendments: [{ id: 22, title: 'Otrosí ajeno' }] },
  ],
};
const inventory = {
  version: 4, project_name: 'Proyecto Aurora', hosting: { subscription_id: null, hosting_record_ids: [], operational_record_id: null },
  subscriptions: [{ id: 90, plan: 'semiannual', status: 'active', billing_amount: '330000.00' }],
  accounting_sources: [{ id: 30, domain_url: 'aurora.test', payment_modality: 'semiannual', payment_per_cycle: '330000.00', mapped_hosting_id: null, conflicts: [] }],
  pending_account_ids: [42], hosting_accounts: [{ id: 42, public_number: account.public_number, total: account.total, commercial_status: 'issued' }], events: [],
};
const overview = { subscription: { associated: false, payments: [] }, accounting_sources: [{ id: 30, cycles: [] }], evidence_groups: [] };

function json(body, status = 200) { return { status, contentType: 'application/json', body: JSON.stringify(body) }; }

async function arrangePanel(page, { rejectApply = false, rejectContext = false } = {}) {
  let applyAttempts = 0;
  let contextAttempts = 0;
  const calls = [];
  await setAuthLocalStorage(page, { token: 'e2e-panel-token', userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ route, apiPath, method }) => {
    const call = { apiPath, method };
    calls.push(call);
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'accounting/collection-accounts/42/' && method === 'GET') return json(account);
    if (apiPath === 'admin/billing-context/accounts/42/' && method === 'GET') return json({ version: 3, nature: 'contract', contract: { id: 10, title: 'Contrato Aurora' }, amendment: { id: 11, title: 'Otrosí permitido' }, hosting_id: null });
    if (apiPath === 'admin/billing-context/projects/7/options/' && method === 'GET') return json(options);
    if (apiPath === 'admin/billing-context/projects/7/hosting/' && method === 'GET') return json({ inventory, overview });
    if (apiPath === 'admin/billing-context/accounts/42/' && method === 'PATCH') {
      contextAttempts += 1; call.body = JSON.parse(route.request().postData());
      if (rejectContext && contextAttempts === 1) return json({ detail: 'La asociación cambió en otra sesión.' }, 409);
      return json({ version: 4, nature: 'contract', contract: { id: 10, title: 'Contrato Aurora' }, amendment: { id: 11, title: 'Otrosí permitido' }, hosting_id: null });
    }
    if (apiPath === 'admin/billing-context/projects/7/hosting/' && method === 'POST') {
      applyAttempts += 1; call.preview = new URL(route.request().url()).searchParams.get('preview'); call.body = JSON.parse(route.request().postData());
      if (new URL(route.request().url()).searchParams.get('preview') === '1') return json({ decision: 'ready', selected: [90, 30] });
      if (rejectApply && applyAttempts === 2) return json({ detail: 'El inventario cambió; actualiza antes de aplicar.' }, 409);
      return json({ decision: 'applied', selected: [90, 30] });
    }
    return null;
  });
  return calls;
}

async function openPanel(page, path, heading) {
  await page.goto(`/en-us${path}`, { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByRole('heading', { name: heading, exact: true })).toHaveText(heading);
}

test.describe('Panel project billing context', () => {
  test('admin saves an exclusive contractual account context with a reason', {
    tag: ['@flow:admin-accounting-collection-context', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where the Panel can save a foreign amendment or omit the reconciliation reason.
    const calls = await arrangePanel(page);
    await openPanel(page, '/panel/accounting/collection-context/42', 'Asociación de cuenta de cobro');
    await page.getByRole('combobox', { name: 'Naturaleza', exact: true }).selectOption('contract');
    await page.getByRole('combobox', { name: 'Contrato', exact: true }).selectOption('10');
    await expect(page.getByRole('combobox', { name: 'Otrosí (opcional)', exact: true }).getByRole('option')).toHaveCount(2);
    await expect(page.getByRole('combobox', { name: 'Otrosí (opcional)', exact: true })).not.toContainText('Otrosí ajeno');
    await page.getByRole('combobox', { name: 'Otrosí (opcional)', exact: true }).selectOption('11');
    await page.getByLabel('Razón de la asociación o corrección').fill('Verificado contra contrato firmado');
    await page.getByRole('button', { name: 'Guardar asociación' }).click();
    await expect(page.getByRole('status')).toHaveText('Asociación guardada. El PDF y el snapshot financiero se conservan.');
    expect(calls.filter(call => call.method === 'PATCH')[0].body).toMatchObject({ billing_nature: 'contract', contract_id: 10, amendment_id: 11, project_hosting_id: null, expected_version: 3, reason: 'Verificado contra contrato firmado' });
  });

  test('admin retries a stale collection context after the server rejects its version', {
    tag: ['@flow:admin-accounting-collection-context', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a 409 silently overwrites a concurrent administrative association.
    await arrangePanel(page, { rejectContext: true });
    await openPanel(page, '/panel/accounting/collection-context/42', 'Asociación de cuenta de cobro');
    await page.getByLabel('Razón de la asociación o corrección').fill('Corrección auditada');
    await page.getByRole('button', { name: 'Guardar asociación' }).click();
    await expect(page.getByRole('alert')).toHaveText('La asociación cambió en otra sesión.');
    await page.getByRole('button', { name: 'Actualizar' }).click();
    await page.getByLabel('Razón de la asociación o corrección').fill('Corrección auditada tras actualizar');
    await page.getByRole('button', { name: 'Guardar asociación' }).click();
    await expect(page.getByRole('status')).toHaveText('Asociación guardada. El PDF y el snapshot financiero se conservan.');
  });

  test('admin cannot submit an association with no selected nature', {
    tag: ['@flow:admin-accounting-collection-context', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where the Panel submits an ambiguous project billing context with no nature.
    const calls = await arrangePanel(page);
    await openPanel(page, '/panel/accounting/collection-context/42', 'Asociación de cuenta de cobro');
    await expect(page.getByRole('combobox', { name: 'Contrato', exact: true })).toHaveValue('10');
    await expect(page.getByRole('combobox', { name: 'Otrosí (opcional)', exact: true })).toHaveValue('11');
    await page.getByRole('combobox', { name: 'Naturaleza', exact: true }).selectOption('');
    await expect(page.getByRole('button', { name: 'Guardar asociación' })).toBeDisabled();
    await page.getByLabel('Razón de la asociación o corrección').fill('Intento sin naturaleza');
    await expect(page.getByRole('button', { name: 'Guardar asociación' })).toBeDisabled();
    expect(calls.filter(call => call.method === 'PATCH')).toHaveLength(0);
  });

  test('admin cannot submit a coherent association with an empty reason', {
    tag: ['@flow:admin-accounting-collection-context', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where a valid contract association is written without its mandatory audit reason.
    const calls = await arrangePanel(page);
    await openPanel(page, '/panel/accounting/collection-context/42', 'Asociación de cuenta de cobro');
    await page.getByRole('combobox', { name: 'Naturaleza', exact: true }).selectOption('contract');
    await page.getByRole('combobox', { name: 'Contrato', exact: true }).selectOption('10');
    await page.getByRole('combobox', { name: 'Otrosí (opcional)', exact: true }).selectOption('11');
    await expect(page.getByRole('button', { name: 'Guardar asociación' })).toBeDisabled();
    expect(calls.filter(call => call.method === 'PATCH')).toHaveLength(0);
  });

  test('admin displays the current contract context before changing it', {
    tag: ['@flow:admin-accounting-collection-context', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the context route loses the current contract and amendment labels.
    await arrangePanel(page);
    await openPanel(page, '/panel/accounting/collection-context/42', 'Asociación de cuenta de cobro');
    await page.getByRole('button', { name: 'Actualizar' }).click();
    await expect(page.getByRole('combobox', { name: 'Contrato', exact: true })).toHaveValue('10');
    await expect(page.getByRole('combobox', { name: 'Otrosí (opcional)', exact: true })).toHaveValue('11');
  });

  test('admin previews and applies only selected hosting identities without payment endpoints', {
    tag: ['@flow:admin-accounting-project-hosting-reconciliation', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where reconciliation applies unselected records or invokes payment automation.
    const calls = await arrangePanel(page);
    await openPanel(page, '/panel/accounting/project-hosting/7', 'Conciliación del hosting del proyecto');
    await page.getByLabel('Suscripción de plataforma').selectOption('90');
    await page.getByRole('checkbox', { name: /#30 · aurora\.test/ }).check();
    await page.getByLabel('Origen contable operativo').selectOption('30');
    await page.getByLabel('Razón').first().fill('Se verificó el origen operativo');
    await page.getByRole('button', { name: 'Previsualizar asociación' }).click();
    await expect(page.getByTestId('hosting-reconciliation-preview').getByText('"decision": "ready"')).toHaveCount(1);
    await page.getByRole('button', { name: 'Aplicar conciliación' }).click();
    await expect(page.getByRole('heading', { name: 'Conciliación del hosting del proyecto', exact: true })).toHaveText('Conciliación del hosting del proyecto');
    const apply = calls.find(call => call.method === 'POST' && call.preview === null);
    expect(apply.body).toMatchObject({ subscription_id: 90, hosting_record_ids: [30], operational_record_id: 30, expected_version: 4, reason: 'Se verificó el origen operativo' });
    expect(calls.some(call => /(?:payments|charge|wompi|cycles|register-payment)/i.test(call.apiPath))).toBe(false);
  });

  test('admin previews a hosting identity without applying a financial mutation', {
    tag: ['@flow:admin-accounting-project-hosting-reconciliation', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where previewing a hosting identity writes the decision or starts a payment action.
    const calls = await arrangePanel(page);
    await openPanel(page, '/panel/accounting/project-hosting/7', 'Conciliación del hosting del proyecto');
    await page.getByLabel('Suscripción de plataforma').selectOption('90');
    await page.getByRole('checkbox', { name: /#30 · aurora\.test/ }).check();
    await page.getByLabel('Origen contable operativo').selectOption('30');
    await page.getByLabel('Razón').first().fill('Solo revisar asociación');
    await page.getByRole('button', { name: 'Previsualizar asociación' }).click();
    await expect(page.getByTestId('hosting-reconciliation-preview').getByText('"decision": "ready"')).toHaveCount(1);
    const posts = calls.filter(call => call.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(posts[0]).toMatchObject({ apiPath: 'admin/billing-context/projects/7/hosting/', preview: '1' });
  });

  test('admin sees a stale hosting reconciliation error and can preview again', {
    tag: ['@flow:admin-accounting-project-hosting-reconciliation', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a 409 reconciliation applies stale references after another administrator changes inventory.
    await arrangePanel(page, { rejectApply: true });
    await openPanel(page, '/panel/accounting/project-hosting/7', 'Conciliación del hosting del proyecto');
    await page.getByLabel('Suscripción de plataforma').selectOption('90');
    await page.getByRole('checkbox', { name: /#30 · aurora\.test/ }).check();
    await page.getByLabel('Origen contable operativo').selectOption('30');
    await page.getByLabel('Razón').first().fill('Primera revisión');
    await page.getByRole('button', { name: 'Previsualizar asociación' }).click();
    await page.getByRole('button', { name: 'Aplicar conciliación' }).click();
    await expect(page.getByRole('alert')).toHaveText('El inventario cambió; actualiza antes de aplicar.');
    await page.getByLabel('Razón').first().fill('Revisión actualizada');
    await page.getByRole('button', { name: 'Previsualizar asociación' }).click();
    await expect(page.getByTestId('hosting-reconciliation-preview').getByText('"decision": "ready"')).toHaveCount(1);
  });

  test('admin displays the hosting inventory without reconciling it', {
    tag: ['@flow:admin-accounting-project-hosting-reconciliation', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the reconciliation page hides a pending account or accounting source before a decision.
    await arrangePanel(page);
    await openPanel(page, '/panel/accounting/project-hosting/7', 'Conciliación del hosting del proyecto');
    await page.getByRole('button', { name: 'Actualizar inventario' }).click();
    await expect(page.getByText('Proyecto Aurora · versión 4', { exact: true })).toHaveCount(1);
    await expect(page.getByRole('checkbox', { name: '#30 · aurora.test', exact: true })).toHaveCount(1);
    await expect(page.getByRole('link', { name: 'Cuenta #42', exact: true })).toHaveCount(1);
  });

  test('admin cannot preview a hosting decision without its reason', {
    tag: ['@flow:admin-accounting-project-hosting-reconciliation', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where reconciliation accepts selected sources without audit evidence.
    const calls = await arrangePanel(page);
    await openPanel(page, '/panel/accounting/project-hosting/7', 'Conciliación del hosting del proyecto');
    await page.getByLabel('Suscripción de plataforma').selectOption('90');
    await page.getByRole('checkbox', { name: /#30 · aurora\.test/ }).check();
    await page.getByLabel('Origen contable operativo').selectOption('30');
    await page.getByRole('button', { name: 'Previsualizar asociación' }).click();
    await expect(page.getByRole('checkbox', { name: '#30 · aurora.test', exact: true })).toBeChecked();
    await expect(page.getByTestId('hosting-reconciliation-preview')).toHaveCount(0);
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(0);
  });
});
