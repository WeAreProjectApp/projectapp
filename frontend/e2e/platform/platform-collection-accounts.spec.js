/**
 * Billing centre journeys. These tests catch a regression that would turn the
 * client-facing account and hosting entries back into the old project redirect.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js';

test.setTimeout(60_000);

const project = { id: 1, name: 'Proyecto Aurora', status: 'active', progress: 50 };
const contractAccount = {
  id: 42, title: 'Implementación fase dos', public_number: 'PA-AUR-001',
  commercial_status: 'issued', currency: 'COP', total: '120000.00', due_date: '2026-10-15',
  project_id: 1, project_name: project.name, is_overdue: false,
  context: { nature: 'contract', contract: { id: 10, title: 'Contrato Aurora' }, amendment: { id: 11, title: 'Otrosí fase dos' } },
};
const hostingAccount = {
  id: 43, title: 'Hosting octubre', public_number: 'PA-AUR-H-002',
  commercial_status: 'issued', currency: 'COP', total: '55000.00', due_date: '2026-10-20',
  project_id: 1, project_name: project.name, is_overdue: false,
  context: { nature: 'hosting', contract: null, amendment: null },
};
const pendingAccount = {
  id: 44, title: 'Cuenta histórica', public_number: 'PA-AUR-LEG-003',
  commercial_status: 'paid', currency: 'COP', total: '30000.00', due_date: '2026-09-01',
  project_id: 1, project_name: project.name, is_overdue: false, context: null,
};

function detail(row) {
  return {
    ...row, issue_date: '2026-10-01', subtotal: row.total, discount_total: '0.00', tax_total: '0.00',
    terms_and_conditions: 'Pago dentro del plazo acordado.',
    collection_account: { billing_concept: row.title, observations: 'Documento emitido.' },
    items: [{ id: row.id, description: row.title, quantity: 1, unit_price: row.total, line_total: row.total, period_start: null, period_end: null }],
    payment_methods: [],
  };
}

function json(body, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

async function arrangePlatform(page, {
  listFailure = false, pdfFailure = false, missingDetail = false,
  projectListFailure = false, hostingContextFailure = false,
} = {}) {
  let listAttempts = 0;
  let projectListAttempts = 0;
  let hostingContextAttempts = 0;
  await setPlatformAuth(page, { user: mockPlatformClient });
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(mockPlatformClient);
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') return json({ unread_count: 0 });
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project]);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(project);
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') return json([]);
    if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') return json(null);
    if (apiPath === 'accounts/projects/1/billing-options/' && method === 'GET') {
      return json({ project_id: 1, project_name: project.name, hosting_id: 7, contracts: [{ id: 10, title: 'Contrato Aurora', amendments: [{ id: 11, title: 'Otrosí fase dos' }] }] });
    }
    if (apiPath === 'accounts/hosting/' && method === 'GET') return json([project]);
    if (apiPath === 'accounts/projects/1/hosting-context/' && method === 'GET') {
      hostingContextAttempts += 1;
      if (hostingContextFailure && hostingContextAttempts === 1) return json({ detail: 'No se pudo cargar el contexto de hosting.' }, 500);
      return json({
        has_hosting: true, reconciliation_required: true,
        subscription: { status: 'active', plan: 'semiannual', billing_amount: '330000.00', payments: [] },
        accounting_sources: [{ id: 30, domain_url: 'aurora.test', operational: true, associated: true, valid_from: '2026-10-01', valid_to: '2027-04-01', payment_modality: 'semiannual', payment_per_cycle: '330000.00', cycles: [{ id: 301, paid_at: '2026-10-01', period_to: '2027-04-01', amount: '330000.00' }] }],
        evidence_groups: [],
      });
    }
    if (apiPath === 'accounts/collection-accounts/' && method === 'GET') {
      listAttempts += 1;
      const params = new URL(route.request().url()).searchParams;
      if (listFailure && listAttempts === 1) return json({ detail: 'No se pudieron cargar las cuentas.' }, 500);
      if (params.get('project_id')) {
        projectListAttempts += 1;
        if (projectListFailure && projectListAttempts === 1) return json({ detail: 'No se pudieron cargar las cuentas del proyecto.' }, 500);
      }
      if (params.get('nature') === 'hosting') return json([hostingAccount]);
      if (params.get('nature') === 'pending') return json([]);
      if (params.get('amendment_id') === '11') return json([contractAccount]);
      return json([contractAccount, hostingAccount, pendingAccount]);
    }
    if (apiPath === 'accounts/collection-accounts/42/' && method === 'GET') return json(detail(contractAccount));
    if (apiPath === 'accounts/collection-accounts/43/' && method === 'GET') {
      return missingDetail ? json({ detail: 'Not found.' }, 404) : json(detail(hostingAccount));
    }
    if (apiPath === 'accounts/collection-accounts/42/pdf/' && method === 'GET') {
      if (pdfFailure) return json({ detail: 'El PDF emitido no está disponible.' }, 500);
      return { status: 200, contentType: 'application/pdf', headers: { 'content-disposition': 'attachment; filename="PA-AUR-001.pdf"' }, body: '%PDF-1.4 account' };
    }
    return null;
  });
}

async function enterAccountCentre(page) {
  await page.goto('/en-us/platform/projects', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Collection accounts' }).click();
  await expect(page).toHaveURL(/\/en-us\/platform\/collection-accounts$/);
}

async function enterProjectBilling(page, destination) {
  await page.goto('/en-us/platform', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Proyectos' }).click();
  await expect(page).toHaveURL(/\/en-us\/platform\/projects$/);
  const row = page.getByTestId('project-row-1');
  await expect(row).toHaveCount(1);
  await row.getByText(project.name, { exact: true }).click();
  await expect(page).toHaveURL(/\/en-us\/platform\/projects\/1$/);
  const projectPath = `/en-us/platform/projects/1/${destination === 'Hosting' ? 'payments' : 'collection-accounts'}`;
  const destinationLinks = page.getByRole('link', { name: destination, exact: true });
  await expect.poll(
    () => destinationLinks.evaluateAll((links) => links.map((link) => link.getAttribute('href'))),
    `No se encontró el enlace de ${destination} del proyecto`,
  ).toContain(projectPath);
  const hrefs = await destinationLinks.evaluateAll((links) => links.map((link) => link.getAttribute('href')));
  await destinationLinks.nth(hrefs.indexOf(projectPath)).click();
  await expect(page).toHaveURL(new RegExp(`${projectPath}$`));
}

test.describe('Platform billing centre', () => {
  test('client reaches the collection-account list from navigation and sees an issued account', {
    tag: ['@flow:platform-collection-accounts-list', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the navigation entry opens an empty or stale receivables list.
    // quality: allow-deep-link (the localized platform shell is the authenticated entry; the visible Collection accounts link opens the billing list).
    await arrangePlatform(page);
    await enterAccountCentre(page);
    await expect(page.getByRole('link', { name: 'PA-AUR-001', exact: true })).toHaveCount(1);
  });

  test('client filters its project contract amendment and opens the issued account detail', {
    tag: ['@flow:platform-collection-accounts-list', '@flow:platform-collection-account-detail', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where contract/amendment filters stop scoping the client's visible account row.
    await arrangePlatform(page);
    await enterAccountCentre(page);
    await page.getByLabel('Project').selectOption('1');
    await page.getByRole('combobox', { name: 'Contract', exact: true }).selectOption('10');
    await page.getByRole('combobox', { name: 'Amendment', exact: true }).selectOption('11');
    await expect(page.getByRole('link', { name: 'PA-AUR-001', exact: true })).toHaveCount(1);
    await page.getByRole('link', { name: 'PA-AUR-001', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'PA-AUR-001', exact: true })).toHaveText('PA-AUR-001');
    await expect(page.getByText('Contrato Aurora · Otrosí fase dos', { exact: true })).toHaveCount(1);
  });

  test('client downloads the canonical issued PDF from its account detail', {
    tag: ['@flow:platform-collection-account-detail', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where a billing download drops the server's canonical consecutivo filename.
    await arrangePlatform(page);
    await enterAccountCentre(page);
    await page.getByRole('link', { name: 'PA-AUR-001', exact: true }).click();
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download PDF' }).click();
    expect((await download).suggestedFilename()).toBe('PA-AUR-001.pdf');
  });

  test('client opens an account detail and sees its immutable line item', {
    tag: ['@flow:platform-collection-account-detail', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where a visible account row opens a detail without the issued financial line.
    // quality: allow-deep-link (the localized platform shell is the authenticated entry; the visible account row opens this immutable detail).
    await arrangePlatform(page);
    await enterAccountCentre(page);
    await page.getByRole('link', { name: 'PA-AUR-001', exact: true }).click();
    await expect(page.getByText('Documento emitido.', { exact: true })).toHaveCount(1);
  });

  test('client sees an empty pending-association filter without losing the list', {
    tag: ['@flow:platform-collection-accounts-list', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where an empty pending-context filter renders stale financial rows.
    await arrangePlatform(page);
    await enterAccountCentre(page);
    await page.getByLabel('Nature').selectOption('pending');
    await expect(page.getByTestId('billing-accounts-empty')).toHaveText('No collection accounts match these filters.');
  });

  test('client retries a failed account list request from the visible error state', {
    tag: ['@flow:platform-collection-accounts-list', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a transient account-list failure leaves no retry action for the client.
    await arrangePlatform(page, { listFailure: true });
    await enterAccountCentre(page);
    await expect(page.getByRole('alert').getByText('No se pudieron cargar las cuentas.', { exact: true })).toHaveCount(1);
    await page.getByRole('button', { name: 'Retry' }).click();
    await expect(page.getByRole('link', { name: 'PA-AUR-001', exact: true })).toHaveCount(1);
  });

  test('client sees a missing account detail as an isolated 404 error', {
    tag: ['@flow:platform-collection-account-detail', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a missing account leaks another project's financial detail.
    await arrangePlatform(page, { missingDetail: true });
    await enterAccountCentre(page);
    await page.getByRole('link', { name: 'PA-AUR-H-002', exact: true }).click();
    await expect(page.getByRole('alert').getByText('Not found.', { exact: true })).toHaveCount(1);
  });

  test('client sees an unavailable issued PDF as a recoverable error', {
    tag: ['@flow:platform-collection-account-detail', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where an unavailable issued PDF does not explain the failure to the client.
    await arrangePlatform(page, { pdfFailure: true });
    await enterAccountCentre(page);
    await page.getByRole('link', { name: 'PA-AUR-001', exact: true }).click();
    await page.getByRole('button', { name: 'Download PDF' }).click();
    await expect(page.getByRole('alert').getByText('El PDF emitido no está disponible.', { exact: true })).toHaveCount(1);
  });

  test('client opens the project collection-account link and filters its hosting accounts', {
    tag: ['@flow:platform-project-collection-accounts', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where the project's collection-account link is disabled or loses the hosting filter.
    await arrangePlatform(page);
    await enterProjectBilling(page, 'Collection accounts');
    await expect(page.getByTestId('billing-account-list').getByRole('heading', { name: 'Collection accounts', exact: true })).toHaveCount(1);
    await page.getByLabel('Nature').selectOption('hosting');
    await expect(page.getByRole('link', { name: 'PA-AUR-H-002', exact: true })).toHaveCount(1);
  });

  test('client sees the project-scoped collection account before filtering it', {
    tag: ['@flow:platform-project-collection-accounts', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the project route opens but omits the project's issued account.
    // quality: allow-deep-link (the localized platform shell is the authenticated entry; visible project and collection-account links reach this scoped list).
    await arrangePlatform(page);
    await enterProjectBilling(page, 'Collection accounts');
    await expect(page.getByRole('link', { name: 'PA-AUR-001', exact: true })).toHaveCount(1);
  });

  test('client retries a failed project-scoped collection-account read', {
    tag: ['@flow:platform-project-collection-accounts', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a project list error offers no recovery while the global list still works.
    await arrangePlatform(page, { projectListFailure: true });
    await enterProjectBilling(page, 'Collection accounts');
    await expect(page.getByRole('alert').getByText('No se pudieron cargar las cuentas del proyecto.', { exact: true })).toHaveCount(1);
    await page.getByRole('button', { name: 'Retry' }).click();
    await expect(page.getByRole('link', { name: 'PA-AUR-001', exact: true })).toHaveCount(1);
  });

  test('client sees a project with hosting in the global hosting list', {
    tag: ['@flow:platform-hosting-project-list', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the global hosting page renders without its project row.
    // quality: allow-deep-link (the localized platform shell is the authenticated entry; the visible Hosting link opens this independent project list).
    await arrangePlatform(page);
    await page.goto('/en-us/platform', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Hosting', exact: true }).first().click();
    await expect(page.getByTestId('billing-hosting-list').getByRole('link', { name: project.name, exact: true })).toHaveCount(1);
  });

  test('client opens global hosting and follows its project context through the UI', {
    tag: ['@flow:platform-hosting-project-list', '@flow:platform-project-hosting-context', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where global hosting returns to a redirect instead of the project's independent hosting context.
    await arrangePlatform(page);
    await page.goto('/en-us/platform', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Hosting', exact: true }).first().click();
    await expect(page.getByTestId('billing-hosting-list').getByRole('link', { name: project.name, exact: true })).toHaveCount(1);
    await page.getByTestId('billing-hosting-list').getByRole('link', { name: project.name, exact: true }).click();
    await expect(page.getByTestId('project-hosting-context').getByText('One hosting per project, independent of its contracts.')).toHaveCount(1);
    await expect(page.getByTestId('project-hosting-context').getByText(/aurora\.test/)).toHaveCount(1);
    await expect(page.getByTestId('project-hosting-context').getByText(/^2026-10-01 — 2027-04-01 · Semiannual/)).toHaveCount(1);
    await page.getByTestId('project-hosting-context').getByRole('link', { name: 'View hosting accounts' }).click();
    await expect(page.getByRole('link', { name: 'PA-AUR-H-002', exact: true })).toHaveCount(1);
  });

  test('client sees the project hosting source and subscription data', {
    tag: ['@flow:platform-project-hosting-context', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the project hosting context loses the operational accounting source.
    // quality: allow-deep-link (the localized platform shell is the authenticated entry; visible project and Hosting links reach this context).
    await arrangePlatform(page);
    await enterProjectBilling(page, 'Hosting');
    await expect(page.getByTestId('project-hosting-context').getByText(/Semiannual/)).toHaveCount(1);
    await expect(page.getByTestId('project-hosting-context').getByText('Operational source', { exact: true })).toHaveCount(1);
  });

  test('client retries a failed project hosting context read', {
    tag: ['@flow:platform-project-hosting-context', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a hosting context error traps the client without retrying its isolated read.
    await arrangePlatform(page, { hostingContextFailure: true });
    await enterProjectBilling(page, 'Hosting');
    await expect(page.getByTestId('project-hosting-context').getByRole('alert').getByText('No se pudo cargar el contexto de hosting.', { exact: true })).toHaveCount(1);
    await page.getByTestId('project-hosting-context').getByRole('button', { name: 'Retry' }).click();
    await expect(page.getByTestId('project-hosting-context').getByText('Operational source', { exact: true })).toHaveCount(1);
  });

  test('client retries a failed global hosting list request', {
    tag: ['@flow:platform-hosting-project-list', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a failed global hosting read leaves no retry for the client.
    let attempts = 0;
    await arrangePlatform(page);
    await page.route(/^https?:\/\/[^/]+\/api\/accounts\/hosting\/$/, async route => {
      attempts += 1;
      if (attempts === 1) return route.fulfill(json({ detail: 'No se pudo cargar el hosting.' }, 500));
      return route.fulfill(json([project]));
    });
    await page.goto('/en-us/platform/projects', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Hosting', exact: true }).first().click();
    await expect(page.getByRole('alert').getByText('No se pudo cargar el hosting.', { exact: true })).toHaveCount(1);
    await page.getByRole('button', { name: 'Retry' }).click();
    await expect(page.getByTestId('billing-hosting-list').getByRole('link', { name: project.name, exact: true })).toHaveCount(1);
  });
});
