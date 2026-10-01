/**
 * R-clients-01: a platform view can render its heading while a narrow shell
 * hides its concrete client/project record or makes navigation hover-only.
 * Each catalog cell opens an authenticated fixture, performs an actual control
 * interaction, then asserts route-specific data before responsive geometry.
 */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { setPlatformAuth, setPlatformVerificationState, mockPlatformAdmin, mockPlatformClient, mockPlatformClientIncompleteProfile } from '../helpers/platform-auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
const platformProject = { id: 1, name: 'Portal de clientes responsive', description: 'Proyecto de prueba con datos concretos', status: 'active', status_label: 'Activo', progress: 65, client_id: 9002, client_name: 'Client E2E', client_email: 'client@e2e.test', client_company: 'ACME Corp', production_url: 'https://portal-responsive.test', staging_url: 'https://staging-responsive.test', repository_url: 'https://git.test/projectapp/portal', credentials: [{ label: 'Administración', username: 'ana', password: 'secreto-visible' }] };
const projectAccessDetail = { project: { id: 1, name: platformProject.name, client_name: platformProject.client_name }, repository_url: platformProject.repository_url, environments: [{ environment: 'production', label: 'Producción', site_url: platformProject.production_url, admin_url: 'https://portal-responsive.test/admin/', admin_username: 'ana', has_password: true }, { environment: 'staging', label: 'Staging', site_url: platformProject.staging_url, admin_url: 'https://staging-responsive.test/admin/', admin_username: 'ana-stage', has_password: true }], notes: [{ id: 1, title: 'Soporte', content: 'Contactar al equipo de operaciones', has_content: true, is_sensitive: false, updated_by: 'Admin' }], legacy_access: null };
const projectPhase = { id: 1, order: 1, hosting_start_date: null, hosting_activated_at: null, proposal: { id: 1, title: 'Fase de diseño responsive', total_amount: '5000000.00', status: 'accepted', deliverable_id: null }, hosting_tiers: [] };
const clientRow = { user_id: 9002, first_name: 'Client', last_name: 'E2E', email: 'client@e2e.test', company_name: 'ACME Corp', phone: '+57 300 000 0002', is_active: true, is_onboarded: true, created_at: '2026-01-01T00:00:00Z' };
const clientFixture = { id: 101, name: 'Kore Healths', email: 'kore@test.com', phone: '+57 300 111 1111', company: 'Kore', is_onboarded: true, is_email_placeholder: false, total_proposals: 1, projects_count: 1, diagnostics_count: 1, is_orphan: false, is_archived: false, hostings_count: 2, active_hostings_count: 1, active_projects_count: 1, documents_count: 3, documents_no_project_count: 1, created_at: '2026-01-01T00:00:00Z' };
const secondClientFixture = { ...clientFixture, id: 102, name: 'Mimittos SAS', email: 'mimittos@test.com', company: 'Mimittos', total_proposals: 0, hostings_count: 0, active_hostings_count: 0, documents_count: 0 };
const proposalFixture = { id: 1, title: 'Propuesta Alpha', status: 'sent', total_investment: 5000000, currency: 'COP', view_count: 5 };
const deliveryRequirement = { id: 11, key: 'save-record', title: 'Guardar un registro', version: 1, stage_id: 21, review_status: 'in_review', guide: { role: 'Cliente', environment: 'Staging', preparation: 'Usar la cuenta de validación.', data: 'Un registro preparado para la prueba.', steps: ['Abrir el registro preparado.', 'Guardar los cambios.'], expected_result: 'Los cambios aparecen al volver a abrir el registro.', failure_signals: 'El formulario pierde los datos.' }, documents: [], reviews: [] };
const deliveryWorkspace = {
  version: 1, is_admin: false, project: { ...platformProject, documents: [] },
  contracts: [{ id: 1, key: 'implementation', title: 'Contrato de implementación firmado', signature_status: 'external', signer_name: 'Client E2E', documents: [], amendments: [] }],
  scopes: [{ id: 2, key: 'agreed-scope', title: 'Alcance acordado', contract_id: 1, is_current: true, status: 'in_review', documents: [], phases: [{ id: 3, key: 'initial-phase', title: 'Primera fase de validación', status: 'in_review', documents: [], stages: [{ id: 21, key: 'record-stage', title: 'Revisar el guardado de registros', editorial_status: 'published', publication_id: 1, status: 'in_review', requirements: [deliveryRequirement], documents: [], messages: [] }] }] }],
};
const bugFixture = { id: 31, title: 'El botón no guarda', status: 'open', description: 'El formulario pierde la acción principal.', requirement_id: 11, created_at: '2026-08-20T00:00:00Z' };
const changeFixture = { id: 41, title: 'Agregar reporte de auditoría', status: 'pending', description: 'El cliente puede pedir cambios desde la plataforma.', requirement_id: 11, created_at: '2026-08-21T00:00:00Z' };
const notificationFixture = { id: 51, title: 'Entrega publicada', body: 'Manual de marca disponible.', is_read: false, created_at: '2026-08-22T00:00:00Z', route: '/platform/projects/1/deliverables' };
const documentFixture = { id: 61, title: 'Contrato de implementación', status: 'pending_signature', signed: false, created_at: '2026-08-23T00:00:00Z', file_url: '/files/contract.pdf' };
const deliverableFixture = { id: 71, title: 'Manual de marca', description: 'Guía para el equipo del cliente.', category: 'documents', file_name: 'manual-marca.pdf', file_size: 2048, current_version: 1, uploaded_by_name: 'ProjectApp', updated_at: '2026-08-24T00:00:00Z', created_at: '2026-08-24T00:00:00Z', versions: [] };
const collectionFixture = { id: 81, title: 'Implementación responsive', public_number: 'CC-001', commercial_status: 'Emitida', status: 'issued', total: '1200000.00', issued_at: '2026-08-25T00:00:00Z' };
const subscriptionFixture = { id: 91, plan: 'quarterly', plan_display: 'Trimestral', status: 'active', status_display: 'Activa', start_date: '2026-08-01', next_billing_date: '2026-11-01', billing_amount: '1200000.00', has_payment_source: false, payments: [] };

function platformHandler(user = mockPlatformAdmin) {
  return async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(user);
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([platformProject]);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(platformProject);
    if (apiPath === 'accounts/projects/1/access/' && method === 'GET') return json(projectAccessDetail);
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') return json([projectPhase]);
    if (apiPath === 'accounts/projects/1/requirements/' && method === 'GET') return json([deliveryRequirement]);
    if (apiPath === 'accounts/projects/1/delivery/' && method === 'GET') return json(deliveryWorkspace);
    if (apiPath === 'accounts/projects/1/bug-reports/' && method === 'GET') return json([bugFixture]);
    if (apiPath === 'accounts/projects/1/change-requests/' && method === 'GET') return json([changeFixture]);
    if (apiPath === 'accounts/projects/1/collection-accounts/' && method === 'GET') return json([collectionFixture]);
    if (apiPath === 'accounts/projects/1/data-model-entities/' && method === 'GET') return json([{ id: 1, name: 'Cliente', description: 'Entidad principal del portal.' }]);
    if (apiPath === 'accounts/projects/1/deliverables/' && method === 'GET') return json([deliverableFixture]);
    if (apiPath === 'accounts/projects/1/subscription/' && method === 'GET') return json(subscriptionFixture);
    if (apiPath === 'accounts/notifications/' && method === 'GET') return json([notificationFixture]);
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') return json({ unread_count: 1 });
    if (apiPath === 'accounts/documents/' && method === 'GET') return json({ documents: [documentFixture], email: 'client@e2e.test', email_verified: true });
    if (apiPath === 'accounts/clients/' && method === 'GET') return json([clientRow]);
    if (apiPath === 'accounts/clients/1/' && method === 'GET') return json({ ...clientRow, user_id: 1 });
    if (apiPath === 'accounts/clients/9002/' && method === 'GET') return json(clientRow);
    if (apiPath === 'accounts/profile/' && method === 'PATCH') return json({ ...mockPlatformClient, first_name: 'Ana Responsive' });
    if (apiPath === 'accounts/password-reset/request/' && method === 'POST') return json({ reset_request_token: 'responsive-reset-request' });
    if (apiPath === 'accounts/password-reset/verify-code/' && method === 'POST') return json({ reset_verified_token: 'responsive-reset-verified' });
    return null;
  };
}

async function setupPlatform(page, user = mockPlatformAdmin) {
  await setPlatformAuth(page, { user });
  await mockApi(page, platformHandler(user));
}

async function setupPanelClients(page) {
  let proposalClientId = clientFixture.id;
  await setAuthLocalStorage(page, { token: 'responsive-clients-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'proposals/client-profiles/status-counts/') return json({ all: 2, active: 2, orphans: 0, archived: 0 });
    if (apiPath === 'proposals/client-profiles/search/' && method === 'GET') {
      const query = new URL(route.request().url()).searchParams;
      const isMimittosAutocomplete = query.get('q') === 'Mimittos'
        && query.get('limit') === '20'
        && query.get('offset') === '0';
      return json(isMimittosAutocomplete ? [secondClientFixture] : []);
    }
    if (apiPath === 'proposals/client-profiles/') {
      const search = new URL(route.request().url()).searchParams.get('search') || '';
      const clients = [clientFixture, secondClientFixture];
      return json(search ? clients.filter((item) => item.name.includes(search)) : clients);
    }
    if (apiPath === 'proposals/client-profiles/101/') return json({ ...clientFixture, proposals: proposalClientId === 101 ? [proposalFixture] : [], diagnostics: [{ id: 5, title: 'Diagnóstico Web Kore', status: 'draft' }], documents: [documentFixture], documents_total: 1 });
    if (apiPath === 'proposals/client-profiles/102/') return json({ ...secondClientFixture, proposals: proposalClientId === 102 ? [proposalFixture] : [], diagnostics: [], documents: [], documents_total: 0 });
    if (apiPath === 'proposals/1/update/' && method === 'PATCH') {
      const payload = JSON.parse(route.request().postData() || '{}');
      proposalClientId = Number(payload.client_id);
      return json({ ...proposalFixture, client_id: proposalClientId });
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath === 'accounting/hostings/') return json({ results: [{ id: 1, client: 101, client_name: 'Kore Healths', domain_url: 'https://kore.test' }], meta: {} });
    return null;
  });
}

const visualKeys = [
  'frontend/pages/panel/clients/index.vue',
  'frontend/pages/platform/documents/index.vue',
  'frontend/pages/platform/login.vue',
  'frontend/pages/platform/verify.vue',
  'frontend/pages/platform/complete-profile.vue',
  'frontend/pages/platform/notifications.vue',
  'frontend/pages/platform/profile.vue',
  'frontend/pages/platform/projects/index.vue',
  'frontend/pages/platform/projects/[id]/index.vue',
  'frontend/pages/platform/projects/[id]/delivery.vue',
  'frontend/pages/platform/projects/[id]/bugs.vue',
  'frontend/pages/platform/projects/[id]/changes.vue',
  'frontend/pages/platform/projects/[id]/data-model.vue',
  'frontend/pages/platform/projects/[id]/deliverables/index.vue',
  'frontend/pages/platform/clients/index.vue',
  'frontend/pages/platform/clients/[id].vue',
  'frontend/pages/platform/projects/[id]/access.vue',
  'frontend/pages/platform/forgot-password.vue',
  'frontend/pages/platform/reset-password.vue',
  'frontend/pages/platform/verify-code.vue',
].map((key) => getResponsiveScenario(key));

const flowForScenario = Object.freeze({
  'frontend/pages/panel/clients/index.vue': 'admin-mini-crm-clients',
  'frontend/pages/platform/documents/index.vue': 'platform-client-document-portal',
  'frontend/pages/platform/login.vue': 'platform-login',
  'frontend/pages/platform/verify.vue': 'platform-verify-onboarding',
  'frontend/pages/platform/complete-profile.vue': 'platform-complete-profile',
  'frontend/pages/platform/notifications.vue': 'platform-notifications',
  'frontend/pages/platform/profile.vue': 'platform-profile-edit',
  'frontend/pages/platform/projects/index.vue': 'platform-project-list',
  'frontend/pages/platform/projects/[id]/index.vue': 'platform-project-detail',
  'frontend/pages/platform/projects/[id]/delivery.vue': 'platform-delivery-review',
  'frontend/pages/platform/projects/[id]/bugs.vue': 'platform-bug-reports',
  'frontend/pages/platform/projects/[id]/changes.vue': 'platform-change-requests',
  'frontend/pages/platform/projects/[id]/collection-accounts.vue': 'platform-project-collection-accounts',
  'frontend/pages/platform/projects/[id]/data-model.vue': 'platform-project-data-model',
  'frontend/pages/platform/projects/[id]/deliverables/index.vue': 'platform-deliverables',
  'frontend/pages/platform/projects/[id]/payments.vue': 'platform-hosting-subscription',
  'frontend/pages/platform/clients/index.vue': 'platform-admin-client-list',
  'frontend/pages/platform/clients/[id].vue': 'platform-admin-client-detail',
  'frontend/pages/platform/projects/[id]/access.vue': 'platform-project-access-detail',
  'frontend/pages/platform/forgot-password.vue': 'platform-password-reset',
  'frontend/pages/platform/reset-password.vue': 'platform-password-reset',
  'frontend/pages/platform/verify-code.vue': 'platform-password-reset',
});

async function exercisePlatformSidebarToggle(page, initialName, toggledName) {
  const toggle = page.getByRole('button', { name: initialName, exact: true });
  await expect(toggle).toBeVisible();
  await toggle.click();
  const toggled = page.getByRole('button', { name: toggledName, exact: true });
  await expect(toggled).toBeVisible();
}

const platformNavigationByProfile = Object.freeze({
  compact: async (page) => {
    await page.getByRole('button', { name: 'Abrir navegación' }).click();
    const drawer = page.locator('aside').filter({ has: page.getByRole('button', { name: 'Cerrar navegación' }) });
    await expect(drawer).toBeVisible();
    const projects = drawer.getByRole('link', { name: 'Proyectos', exact: true });
    await expect(projects).toHaveText('Proyectos');
    await drawer.getByRole('button', { name: 'Cerrar navegación' }).click();
    await expect(drawer).toHaveCount(0);
  },
  portrait: (page) => exercisePlatformSidebarToggle(page, 'Expandir barra lateral', 'Colapsar barra lateral'),
  landscape: (page) => exercisePlatformSidebarToggle(page, 'Colapsar barra lateral', 'Expandir barra lateral'),
  desktop: (page) => exercisePlatformSidebarToggle(page, 'Colapsar barra lateral', 'Expandir barra lateral'),
  wide: (page) => exercisePlatformSidebarToggle(page, 'Colapsar barra lateral', 'Expandir barra lateral'),
});

async function exerciseCatalogView(page, scenario, profile) {
  if (scenario.catalogKey === 'frontend/pages/panel/clients/index.vue') {
    await setupPanelClients(page);
    await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
    if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) await page.getByRole('button', { name: 'Abrir menú' }).click();
    await page.getByRole('link', { name: 'Clientes', exact: true }).click();
    await expect(page).toHaveURL(/\/panel\/clients(?:\?.*)?$/);
    await expect(page.getByTestId('client-row-102')).toContainText('Mimittos SAS');
    if (['compact', 'portrait'].includes(profile)) {
      await page.getByTestId('clients-mobile-filters').click();
      await page.getByTestId('clients-module-selector-mobile').selectOption('hosting');
      await page.getByTestId('clients-subfilter-selector-mobile').selectOption('hosting-charged');
      await expect(page.getByTestId('clients-mobile-filter-results')).toHaveText('Ver 1 cliente');
      await page.getByTestId('clients-mobile-filter-results').click();
    } else {
      await page.getByTestId('clients-module-hosting').click();
      await page.getByTestId('filter-tabs-tab-hosting-charged').click();
    }
    await expect(page.getByTestId('client-row-101')).toContainText('Kore Healths');
    await expect(page.getByTestId('client-row-102')).toHaveCount(0);
    return page.getByTestId('client-row-101');
  }

  if (scenario.catalogKey === 'frontend/pages/platform/login.vue') {
    await mockApi(page, async () => null);
    await page.goto(scenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Email').fill('ana@responsive.test');
    await expect(page.getByLabel('Email')).toHaveValue('ana@responsive.test');
    return page.getByLabel('Email');
  }

  if (scenario.catalogKey === 'frontend/pages/platform/verify.vue') {
    await setPlatformVerificationState(page, { email: 'ana@responsive.test' });
    await mockApi(page, async () => null);
    await page.goto(scenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Nueva contraseña').fill('secure123');
    await expect(page.getByLabel('Nueva contraseña')).toHaveValue('secure123');
    return page.getByLabel('Nueva contraseña');
  }

  if (scenario.catalogKey === 'frontend/pages/platform/complete-profile.vue') {
    await setupPlatform(page, mockPlatformClientIncompleteProfile);
    await page.goto(scenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
    await page.getByPlaceholder('Tu nombre').fill('Ana Responsive');
    await expect(page.getByPlaceholder('Tu nombre')).toHaveValue('Ana Responsive');
    return page.getByPlaceholder('Tu nombre');
  }

  if (scenario.catalogKey === 'frontend/pages/platform/profile.vue') {
    await setupPlatform(page, mockPlatformClient);
    await page.goto(scenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Nombre').fill('Ana Responsive');
    await expect(page.getByLabel('Nombre')).toHaveValue('Ana Responsive');
    return page.getByLabel('Nombre');
  }

  if (scenario.catalogKey === 'frontend/pages/platform/forgot-password.vue') {
    await mockApi(page, async () => null);
    await page.goto(scenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Email').fill('ana@responsive.test');
    await expect(page.getByLabel('Email')).toHaveValue('ana@responsive.test');
    return page.getByLabel('Email');
  }

  if (scenario.catalogKey === 'frontend/pages/platform/reset-password.vue') {
    await mockApi(page, platformHandler());
    await page.goto('/platform/forgot-password', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Email').fill('ana@responsive.test');
    await page.getByRole('button', { name: 'Enviar código', exact: true }).click();
    await expect(page).toHaveURL(/\/platform\/verify-code$/);
    await page.getByLabel('Código').fill('123456');
    await page.getByRole('button', { name: 'Verificar', exact: true }).click();
    await expect(page).toHaveURL(/\/platform\/reset-password$/);
    await page.getByLabel('Nueva contraseña').fill('secure123');
    await page.getByLabel('Confirmar contraseña').fill('secure123');
    await expect(page.getByLabel('Confirmar contraseña')).toHaveValue('secure123');
    return page.getByLabel('Confirmar contraseña');
  }

  if (scenario.catalogKey === 'frontend/pages/platform/verify-code.vue') {
    await mockApi(page, platformHandler());
    await page.goto('/platform/forgot-password', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Email').fill('ana@responsive.test');
    await page.getByRole('button', { name: 'Enviar código', exact: true }).click();
    await expect(page).toHaveURL(/\/platform\/verify-code$/);
    await page.getByLabel('Código').fill('123456');
    await expect(page.getByLabel('Código')).toHaveValue('123456');
    return page.getByLabel('Código');
  }

  await setupPlatform(
    page,
    ['frontend/pages/platform/documents/index.vue', 'frontend/pages/platform/projects/[id]/delivery.vue'].includes(scenario.catalogKey)
      ? mockPlatformClient
      : mockPlatformAdmin,
  );
  // quality: allow-deep-link (catalog dynamic pages need their resolved fixture id; each route then drives a visible UI control)
  const url = scenario.catalogKey === 'frontend/pages/platform/projects/[id]/delivery.vue'
    ? `/es-co${scenario.resolvedUrl}`
    : scenario.resolvedUrl;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await platformNavigationByProfile[profile](page);

  if (scenario.catalogKey === 'frontend/pages/platform/projects/[id]/delivery.vue') {
    await page.getByTestId('delivery-review-open-21').click();
    const decision = page.getByTestId('delivery-review-decision-11');
    await decision.selectOption('approved');
    await expect(decision).toHaveValue('approved');
    await page.getByRole('dialog').getByRole('button', { name: 'Cancelar', exact: true }).click();
    const guide = page.getByTestId('delivery-requirement-11');
    await expect(guide).toContainText(deliveryRequirement.guide.expected_result);
    return guide;
  }

  const expected = {
    'frontend/pages/platform/documents/index.vue': 'Contrato de implementación',
    'frontend/pages/platform/notifications.vue': 'Entrega publicada',
    'frontend/pages/platform/projects/index.vue': 'Portal de clientes responsive',
    'frontend/pages/platform/projects/[id]/index.vue': 'Portal de clientes responsive',
    'frontend/pages/platform/projects/[id]/bugs.vue': 'El botón no guarda',
    'frontend/pages/platform/projects/[id]/changes.vue': 'Agregar reporte de auditoría',
    'frontend/pages/platform/projects/[id]/collection-accounts.vue': 'CC-001 · Emitida',
    'frontend/pages/platform/projects/[id]/data-model.vue': 'Cliente',
    'frontend/pages/platform/projects/[id]/deliverables/index.vue': 'Manual de marca',
    'frontend/pages/platform/projects/[id]/payments.vue': 'Hosting Trimestral',
    'frontend/pages/platform/clients/index.vue': 'Client E2E',
    'frontend/pages/platform/clients/[id].vue': 'client@e2e.test',
    'frontend/pages/platform/projects/[id]/access.vue': 'https://portal-responsive.test',
  }[scenario.catalogKey];
  const fixtureContent = scenario.catalogKey === 'frontend/pages/platform/projects/[id]/index.vue'
    ? page.getByRole('heading', { level: 1, name: expected, exact: true })
    : page.getByText(expected, { exact: true });
  await expect(fixtureContent).toHaveText(expected);
  return fixtureContent;
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`clients catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    for (const scenario of visualKeys) {
      test(`${scenario.label} keeps its responsive fixture and actionable control`, {
        tag: [`@flow:${flowForScenario[scenario.catalogKey]}`, '@outcome:display', '@responsive:clients', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`],
      }, async ({ page }, testInfo) => {
        // quality: allow-deep-link (the catalog matrix isolates each resolved platform route and fixture id; every cell still exercises its visible responsive navigation control before asserting route-specific data)
        const priorityLocator = await exerciseCatalogView(page, scenario, profile);
        // The route helper already asserts its fixture value; keeping this
        // direct count binds the generated catalog test to that concrete node.
        await expect(priorityLocator).toHaveCount(1);
        await assertResponsiveScenario(page, testInfo, scenario, { profile, priorityLocator });
      });
    }
  });
}

test.describe('clients responsive special', () => {
  test.use(viewportUse('compact'));
  test('client card moves a proposal through its explicit touch reassignment action', {
    tag: ['@flow:admin-client-drag-reassign', '@outcome:success', '@responsive-special:clients', '@viewport:compact', '@responsive-batch:clients-special-1'],
  }, async ({ page }) => {
    await setupPanelClients(page);
    // quality: allow-deep-link (the special isolates the compact client-card action after the catalog list navigation)
    await page.goto('/en-us/panel/clients', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('client-header-101').click();
    await page.getByTestId('client-proposal-move-1').click();
    const dialog = page.getByRole('dialog', { name: 'Mover propuesta', exact: true });
    await expect(dialog).toContainText('Propuesta Alpha');
    await expect(dialog).toContainText('Actualmente pertenece a Kore Healths.');
    await dialog.getByTestId('client-reassign-target').fill('Mimittos');
    await page.getByTestId('client-autocomplete-option-102').click();
    const updateRequest = page.waitForRequest((request) => request.url().includes('/api/proposals/1/update/') && request.method() === 'PATCH');
    await dialog.getByTestId('client-reassign-confirm').click();
    expect((await updateRequest).postDataJSON()).toEqual({ client_id: 102 });
    await expect(page.getByText('"Propuesta Alpha" movido a Mimittos SAS.')).toBeVisible();
    await expect(page.getByTestId('client-proposal-row-1')).toHaveCount(0);
    await page.getByTestId('client-header-102').click();
    await expect(page.getByTestId('client-proposal-row-1')).toContainText('Propuesta Alpha');
  });
});
