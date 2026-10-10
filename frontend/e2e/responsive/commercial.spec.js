/** R-commercial-01: commercial catalog routes must retain an actionable record, not just a page heading, at every responsive profile. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { viewportUse } from '../helpers/viewports.js';
import {
  financingAgreementFixture,
  financingAgreementTemplateFixture,
  financingClientContextFixture,
  financingClientFixture,
} from '../helpers/financing-agreement-fixture.js';
import { financingProgramFixture } from '../helpers/financing-fixture.js';
import { buildingWithUsApiFixture } from '../helpers/building-with-us-fixture.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const proposal = { id: 1, uuid: 'commercial-responsive-proposal', title: 'Propuesta de implementación', client_name: 'Acme Comercial', client_email: 'acme@test.com', status: 'draft', total_investment: 5000000, currency: 'COP', sections: [], heat_score: 72, view_count: 3, engagement_summary: { views: 3, investment_time_sec: 120, technical_time_sec: 0, technical_viewed: false, unique_devices: 1, skipped_sections: [] } };
const diagnostic = { id: 1, title: 'Diagnóstico responsive', client_name: 'Acme Comercial', client_email: 'acme@test.com', status: 'draft', uuid: 'diagnostic-1', sections: [] };
const diagnosticClient = { id: 101, name: 'Acme Comercial', company: 'Acme', email: 'acme@test.com' };
const hourPackage = { id: 1, name_es: 'Paquete 20 horas', name_en: '20 hour package', nationality: 'COL', currency: 'COP', hours: 20, hourly_rate: '100000.00', discount_percent: 0, is_active: true };
const moduleCategory = { id: 1, slug: 'analytics', name_es: 'Analítica', name_en: 'Analytics', is_active: true, order: 1 };
const moduleFixture = { id: 1, category: 1, slug: 'analitica-comercial', name_es: 'Analítica comercial', name_en: 'Commercial analytics', summary_es: 'Módulo con una acción visible.', summary_en: 'Module with a visible action.', is_active: true, order: 1 };
const proposalDefaults = { id: 1, language: 'es', sections_json: [], default_slug_pattern: '{client_name}', default_expiration_days: 21, default_reminder_days: 7, default_urgency_reminder_days: 14, created_at: null, updated_at: null };

async function setupCommercial(page) {
  await setAuthLocalStorage(page, { token: 'commercial-responsive-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method, route }) => {
    const buildingWithUs = buildingWithUsApiFixture({ apiPath, method, route });
    if (buildingWithUs) return buildingWithUs;
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'proposals/' && method === 'GET') return json([proposal]);
    if (apiPath === 'proposals/alerts/' && method === 'GET') return json([]);
    if (apiPath === 'proposals/1/' || apiPath === 'proposals/1/detail/') return json(proposal);
    if (apiPath === 'proposals/1/email-preview/' && method === 'POST') return json('<p>Vista previa responsive</p>');
    if (apiPath === 'diagnostics/' && method === 'GET') return json([diagnostic]);
    if (apiPath === 'diagnostics/1/' || apiPath === 'diagnostics/1/detail/') return json(diagnostic);
    if (apiPath === 'hour-packages/admin/' && method === 'GET') return json([hourPackage]);
    if (apiPath === 'hour-packages/admin/1/detail/' && method === 'GET') return json(hourPackage);
    if (apiPath === 'additional-modules/admin/' && method === 'GET') return json({ categories: [moduleCategory], modules: [moduleFixture], revision: 1 });
    if (apiPath === 'additional-modules/admin/shares/' && method === 'GET') return json([]);
    if (apiPath === 'financing/public/' && method === 'GET') return json(financingProgramFixture('es'));
    if (apiPath === 'financing/agreements/templates/' && method === 'GET') return json({ results: [financingAgreementTemplateFixture], known_placeholders: ['agreement_number', 'client_full_name'] });
    if (apiPath === 'financing/agreements/client-context/' && method === 'GET') return json(financingClientContextFixture());
    if (apiPath === 'financing/agreements/1/' && method === 'GET') return json(financingAgreementFixture({ id: 1 }));
    if (apiPath === 'proposals/client-profiles/search/' && method === 'GET') return json([diagnosticClient, financingClientFixture]);
    if (apiPath.startsWith('accounts/saved-filter-tabs') || apiPath.startsWith('proposals/client-profiles/')) return json([]);
    if (apiPath === 'proposals/defaults/' && method === 'GET') return json(proposalDefaults);
    if (apiPath === 'diagnostics/defaults/' && method === 'GET') return json({ language: 'es', default_currency: 'COP', default_slug_pattern: '{client_name}', payment_initial_pct: 50, payment_final_pct: 50 });
    if (apiPath === 'email-templates/' && method === 'GET') return json([]);
    if (apiPath.includes('defaults')) return json({});
    return null;
  });
}

const visualKeys = [
  'frontend/pages/panel/building-with-us/index.vue',
  'frontend/pages/panel/additional-modules/index.vue', 'frontend/pages/panel/partnership-program/index.vue', 'frontend/pages/panel/partnership-program/new.vue', 'frontend/pages/panel/partnership-program/[id].vue', 'frontend/pages/panel/proposals/index.vue', 'frontend/pages/panel/proposals/create.vue', 'frontend/pages/panel/proposals/[id]/edit.vue', 'frontend/pages/panel/defaults.vue', 'frontend/pages/panel/hour-packages/index.vue', 'frontend/pages/panel/hour-packages/create.vue', 'frontend/pages/panel/hour-packages/[id]/edit.vue', 'frontend/pages/panel/diagnostics/index.vue', 'frontend/pages/panel/diagnostics/create.vue', 'frontend/pages/panel/diagnostics/[id]/edit.vue',
].map(getResponsiveScenario);
const flowForScenario = {
  'frontend/pages/panel/building-with-us/index.vue': 'admin-building-with-us-contract',
  'frontend/pages/panel/additional-modules/index.vue': 'admin-additional-modules-manage',
  'frontend/pages/panel/partnership-program/index.vue': 'admin-financing-distribution',
  'frontend/pages/panel/partnership-program/new.vue': 'admin-financing-agreement-create',
  'frontend/pages/panel/partnership-program/[id].vue': 'admin-financing-agreement-lifecycle',
  'frontend/pages/panel/proposals/index.vue': 'admin-proposal-actions-modal',
  'frontend/pages/panel/proposals/create.vue': 'admin-proposal-create',
  'frontend/pages/panel/proposals/[id]/edit.vue': 'admin-proposal-edit',
  'frontend/pages/panel/defaults.vue': 'admin-proposal-defaults-config',
  'frontend/pages/panel/hour-packages/index.vue': 'admin-hour-packages-list',
  'frontend/pages/panel/hour-packages/create.vue': 'admin-hour-packages-create',
  'frontend/pages/panel/hour-packages/[id]/edit.vue': 'admin-hour-packages-edit',
  'frontend/pages/panel/diagnostics/index.vue': 'admin-diagnostic-list',
  'frontend/pages/panel/diagnostics/create.vue': 'admin-diagnostic-create',
  'frontend/pages/panel/diagnostics/[id]/edit.vue': 'admin-diagnostic-edit',
};

async function exerciseCommercialView(page, scenario) {
  await setupCommercial(page);
  // quality: allow-deep-link (the exact catalog route and fixture id are the behavior under responsive inspection)
  const route = scenario.catalogKey === 'frontend/pages/panel/building-with-us/index.vue'
    ? '/es-co/panel/building-with-us' : scenario.resolvedUrl;
  await page.goto(route, { waitUntil: 'domcontentloaded' });
  const entry = {
    'frontend/pages/panel/building-with-us/index.vue': { action: () => page.getByTestId('building-with-us-tab-contract').click(), value: 'Sincronizado' },
    'frontend/pages/panel/additional-modules/index.vue': { action: async () => { await expect(page.getByTestId('additional-admin-module-1')).toContainText('Commercial analytics'); await page.getByTestId('additional-module-new').click(); }, value: null },
    'frontend/pages/panel/partnership-program/index.vue': { action: async () => { await expect(page.getByTestId('financing-public-url')).toHaveValue(/^https:\/\/projectapp\.co\/(?:es-co|en-us)\/partnership-program$/); await page.getByTestId('financing-term-trigger-code-custody').click(); }, value: null },
    'frontend/pages/panel/partnership-program/new.vue': { action: async () => { await page.getByTestId('financing-agreement-client').fill('Semilla'); await page.getByTestId(`client-autocomplete-option-${financingClientFixture.id}`).click(); }, value: null },
    'frontend/pages/panel/partnership-program/[id].vue': { action: () => page.getByTestId('financing-mark-ready').click(), value: null },
    'frontend/pages/panel/proposals/index.vue': { action: () => page.getByTestId('proposal-actions-1').click(), value: null },
    'frontend/pages/panel/proposals/create.vue': { action: async () => { await page.getByRole('button', { name: 'Manual' }).click(); await page.getByLabel('Título', { exact: true }).fill('Propuesta manual responsive'); }, value: null },
    'frontend/pages/panel/proposals/[id]/edit.vue': { action: async () => { await selectProposalDestination(page, 'communication', 'emails'); await page.getByTestId('edit-email-preview-btn').click(); await expect(page.getByRole('heading', { name: 'Vista previa del correo', exact: true })).toBeVisible(); }, value: null },
    'frontend/pages/panel/defaults.vue': { action: async () => { await page.getByRole('button', { name: 'Diagnóstico', exact: true }).click(); await expect(page).toHaveURL(/mode=diagnostic/); }, value: 'Valores por Defecto' },
    'frontend/pages/panel/hour-packages/index.vue': { action: () => page.getByTestId('hour-packages-view-cards').click(), value: 'Paquete 20 horas' },
    'frontend/pages/panel/hour-packages/create.vue': { action: () => page.getByLabel('Nombre (ES)').fill('Paquete responsive'), value: 'Paquete responsive' },
    'frontend/pages/panel/hour-packages/[id]/edit.vue': { action: () => page.getByLabel('Horas', { exact: true }).fill('24'), value: '24' },
    'frontend/pages/panel/diagnostics/index.vue': { action: () => page.getByTestId('diagnostic-actions-1').click(), value: 'Diagnóstico responsive' },
    'frontend/pages/panel/diagnostics/create.vue': { action: async () => { await page.getByTestId('diagnostic-client-autocomplete').fill('Acme'); await page.getByTestId('client-autocomplete-option-101').click(); }, value: null },
    'frontend/pages/panel/diagnostics/[id]/edit.vue': { action: () => page.getByTestId('diagnostic-edit-title').fill('Diagnóstico responsive editado'), value: null },
  }[scenario.catalogKey];
  await entry.action();
  let content;
  if (scenario.catalogKey === 'frontend/pages/panel/building-with-us/index.vue') {
    content = page.getByTestId('building-with-us-mirror-status');
    await expect(content).toHaveText('Sincronizado');
  } else if (scenario.catalogKey === 'frontend/pages/panel/additional-modules/index.vue') {
    content = page.getByTestId('additional-module-form');
    await expect(content).toBeVisible();
    await expect(page.getByTestId('additional-module-name-es')).toBeVisible();
  } else if (scenario.catalogKey === 'frontend/pages/panel/partnership-program/index.vue') {
    content = page.getByTestId('financing-term-code-custody');
    await expect(content).toContainText('La custodia no transfiere la propiedad intelectual.');
  } else if (scenario.catalogKey === 'frontend/pages/panel/partnership-program/new.vue') {
    content = page.getByTestId('financing-client-legal-name');
    await expect(content).toHaveValue(financingClientFixture.name);
  } else if (scenario.catalogKey === 'frontend/pages/panel/partnership-program/[id].vue') {
    content = page.getByTestId('confirm-modal-confirm');
    await expect(page.getByRole('dialog')).toContainText(/snapshot legal|legal snapshot/);
    await expect(content).toBeVisible();
  } else if (scenario.catalogKey === 'frontend/pages/panel/proposals/index.vue') {
    const dialog = page.locator('[role="dialog"]').filter({ has: page.getByRole('heading', { name: 'Propuesta de implementación', exact: true }) });
    content = dialog.getByRole('heading', { name: 'Propuesta de implementación', exact: true });
    await expect(content).toBeVisible();
    await expect(dialog.getByRole('link', { name: /^Ver preview\b/ })).toBeVisible();
  } else if (scenario.catalogKey === 'frontend/pages/panel/proposals/[id]/edit.vue') {
    content = page.getByTestId('edit-email-preview-select');
    await expect(content).toBeVisible();
  } else if (scenario.catalogKey === 'frontend/pages/panel/proposals/create.vue') {
    content = page.getByLabel('Título', { exact: true });
    await expect(content).toHaveValue('Propuesta manual responsive');
  } else if (scenario.catalogKey === 'frontend/pages/panel/diagnostics/index.vue') {
    content = page.getByRole('heading', { name: 'Diagnóstico responsive', exact: true });
    await expect(content).toBeVisible();
    await expect(page.getByRole('link', { name: 'Abrir editor', exact: true })).toBeVisible();
  } else if (scenario.catalogKey === 'frontend/pages/panel/diagnostics/create.vue') {
    content = page.getByTestId('diagnostic-client-autocomplete');
    await expect(content).toHaveValue('Acme Comercial');
    await expect(page.getByTestId('client-autocomplete-linked')).toContainText('Cliente enlazado: Acme Comercial (#101)');
  } else if (scenario.catalogKey === 'frontend/pages/panel/diagnostics/[id]/edit.vue') {
    content = page.getByTestId('diagnostic-edit-title');
    await expect(content).toHaveValue('Diagnóstico responsive editado');
  } else if (scenario.catalogKey === 'frontend/pages/panel/defaults.vue') {
    content = page.getByTestId('diagnostic-defaults-slug-pattern');
    await expect(content).toHaveValue('{client_name}');
  } else if (scenario.catalogKey === 'frontend/pages/panel/hour-packages/index.vue') {
    content = page.getByTestId('hour-package-card-1');
    await expect(content).toContainText('Paquete 20 horas');
  } else if (scenario.catalogKey === 'frontend/pages/panel/hour-packages/create.vue') {
    content = page.getByLabel('Nombre (ES)');
    await expect(content).toHaveValue('Paquete responsive');
  } else if (scenario.catalogKey === 'frontend/pages/panel/hour-packages/[id]/edit.vue') {
    content = page.getByLabel('Horas', { exact: true });
    await expect(content).toHaveValue('24');
  } else {
    content = page.getByText(entry.value, { exact: true });
    await expect(content).toHaveCount(1);
  }
  return content;
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`commercial catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    for (const scenario of visualKeys) {
      test(`${scenario.label} preserves its actionable commercial fixture`, { tag: [`@flow:${flowForScenario[scenario.catalogKey]}`, '@outcome:display', '@responsive:commercial', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
        const priorityLocator = await exerciseCommercialView(page, scenario);
        await expect(priorityLocator).toHaveCount(1);
        const isFinancingDetail = scenario.catalogKey === 'frontend/pages/panel/partnership-program/[id].vue';
        await assertResponsiveScenario(page, testInfo, scenario, {
          profile,
          priorityLocator,
          modalLocator: isFinancingDetail ? page.getByRole('dialog') : undefined,
          finalActionLocator: isFinancingDetail ? page.getByTestId('confirm-modal-confirm') : undefined,
        });
      });
    }
  });
}

test.describe('commercial responsive special', () => {
  test.use(viewportUse('compact'));
  test('proposal row actions remain available without hover in the compact list', { tag: ['@flow:admin-proposal-actions-modal', '@outcome:success', '@responsive-special:commercial', '@viewport:compact', '@responsive-batch:commercial-special-1'] }, async ({ page }) => {
    await setupCommercial(page);
    // quality: allow-deep-link (catalog scenario covers the list route; this pins the compact action sheet)
    await page.goto('/en-us/panel/proposals', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/en-us\/panel\/proposals$/);
    await page.getByTestId('proposal-actions-1').click();
    const dialog = page.locator('[role="dialog"]').filter({ has: page.getByRole('heading', { name: 'Propuesta de implementación', exact: true }) });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('link', { name: /^Ver preview\b/ })).toHaveAttribute('href', '/proposal/commercial-responsive-proposal?preview=1');
  });
});
