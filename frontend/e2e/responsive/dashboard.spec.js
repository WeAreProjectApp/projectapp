/** R-dashboard-01: dashboard controls must expose fixture-backed details at every profile instead of leaving a responsive shell. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const dashboard = { finance: { year: 2026, liquid_utility: 80000000, expected_utility: 110000000 }, proposals: { pipeline_value: 45000000, pipeline_count: 3, total_proposals: 10, by_status: {} }, additional_modules: { active_module_count: 2, active_share_count: 1, unopened_active_share_count: 0 }, operations: { tasks: { open: 1, overdue: 0 }, documents: { by_status: {} }, diagnostics: { by_status: {} }, emails: { total_30d: 1 }, hour_packages: { active_count: 1 } }, attention: [] };
const keys = ['frontend/pages/panel/index.vue', 'frontend/pages/panel/views.vue', 'frontend/pages/panel/admins/index.vue', 'frontend/pages/panel/tasks/index.vue', 'frontend/pages/panel/access/index.vue'].map(getResponsiveScenario);
const flows = { 'frontend/pages/panel/index.vue': 'admin-dashboard-stats-modals', 'frontend/pages/panel/views.vue': 'admin-view-map', 'frontend/pages/panel/admins/index.vue': 'admin-admin-management', 'frontend/pages/panel/tasks/index.vue': 'admin-kanban-tasks', 'frontend/pages/panel/access/index.vue': 'admin-access-management' };

async function setup(page) {
  await setAuthLocalStorage(page, { token: 'dashboard-responsive-token', userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/') return json(dashboard);
    if (apiPath === 'proposals/dashboard/') return json({ pipeline_count: 3, pipeline_value: 45000000, by_status: {}, monthly_trend: [] });
    if (apiPath === 'accounts/access/' && method === 'GET') return json({ results: [{ id: 2, name: 'Cliente registrado', email: 'cliente@example.test', company: 'Empresa de prueba', enabled: false, onboarded: false, email_verified: false, google_linked: false, last_login: null, last_method: '' }], count: 1, page: 1, pages: 1, counts: { all: 1, enabled: 0, disabled: 1, pending: 1 }, can_manage_team: true });
    if (apiPath.includes('view-catalog') || apiPath.includes('views')) return json({ sections: [], views: [] });
    if (apiPath.includes('admins')) return json({ results: [{ id: 1, username: 'Ana responsable', email: 'ana@project.test', is_active: true }], count: 1 });
    if (apiPath === 'tasks/assignees/' && method === 'GET') return json([{ id: 7, name: 'Ana responsable' }]);
    if (apiPath === 'tasks/' && method === 'GET') {
      const board = new URL(route.request().url()).searchParams.get('board');
      if (board === 'macro') return json({ items: [] });
      return json({
        todo: board === 'standard' ? [{ id: 1, title: 'Tarea responsive', status: 'todo', board_type: 'standard' }] : [],
        in_progress: [],
        blocked: [],
        done: [],
      });
    }
    if (method === 'PATCH') return json({});
    return null;
  });
}

async function exercise(page, scenario) {
  await setup(page);
  // quality: allow-deep-link (the responsive catalog needs its exact protected route and stable fixture)
  await page.goto(scenario.resolvedUrl, { waitUntil: 'domcontentloaded' });
  const entries = {
    'frontend/pages/panel/index.vue': { action: () => page.getByTestId('dashboard-pipeline-tile').click(), result: () => page.getByTestId('stats-modal'), assert: (locator) => expect(locator).toContainText('Estadísticas de propuestas') },
    'frontend/pages/panel/views.vue': { action: async () => { await page.getByTestId('view-map-section-config').click(); await page.getByTestId('view-map-default-mode').getByTestId('view-mode-map').click(); }, result: () => page.getByText('Vista por defecto guardada.', { exact: true }), assert: (locator) => expect(locator).toHaveText('Vista por defecto guardada.') },
    'frontend/pages/panel/admins/index.vue': { action: () => page.getByRole('button', { name: 'Agregar Administrador', exact: true }).click(), result: () => page.getByRole('dialog').getByRole('heading', { name: 'Agregar administrador', exact: true }), assert: (locator) => expect(locator).toHaveText('Agregar administrador') },
    'frontend/pages/panel/tasks/index.vue': { action: () => page.getByTestId('new-task-btn').click(), result: () => page.getByRole('dialog', { name: 'New task', exact: true }), assert: async (locator) => { await expect(locator.getByRole('heading', { name: 'New task', exact: true })).toBeVisible(); await expect(locator.getByTestId('task-title-input')).toBeEditable(); } },
    'frontend/pages/panel/access/index.vue': { action: () => page.getByTestId('access-create').click(), result: () => page.getByRole('dialog', { name: 'Nuevo cliente', exact: true }), assert: (locator) => expect(locator).toContainText('Se registrará sin acceso.') },
  }[scenario.catalogKey];
  await entries.action();
  const priorityLocator = entries.result();
  await entries.assert(priorityLocator);
  return priorityLocator;
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`dashboard catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    for (const scenario of keys) {
      test(`${scenario.label} keeps its real action and fixture`, { tag: [`@flow:${flows[scenario.catalogKey]}`, '@outcome:display', '@responsive:dashboard', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`] }, async ({ page }, testInfo) => {
        const priorityLocator = await exercise(page, scenario);
        await expect(priorityLocator).toHaveCount(1);
        await assertResponsiveScenario(page, testInfo, scenario, { profile, priorityLocator });
      });
    }
  });
}
