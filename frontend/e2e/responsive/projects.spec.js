import { openProjectAction } from '../helpers/projects.js';
/** R-projects-01: project actions and the state catalog must not disappear at a responsive breakpoint. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const projectsScenario = getResponsiveScenario('frontend/pages/panel/projects/index.vue');
const statusesScenario = getResponsiveScenario('frontend/pages/panel/projects/statuses.vue');
const accessDetail = { project: { id: 9, name: 'Kore', client_name: 'Germán Franco' }, repository_url: 'https://git.example.test/kore', environments: [{ environment: 'production', label: 'Producción', site_url: 'https://kore.example.test', admin_url: 'https://kore.example.test/admin/', admin_username: 'prod-admin', has_password: true }, { environment: 'staging', label: 'Staging', site_url: 'https://staging.kore.example.test', admin_url: 'https://staging.kore.example.test/admin/', admin_username: 'stage-admin', has_password: true }], notes: [], legacy_access: null };

async function setupProjects(page) {
  await setAuthLocalStorage(page, { token: 'projects-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath }) => {
    const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'projects/') return json({ results: [{ id: 9, name: 'Kore', description: 'Plataforma clínica', status: 'development', status_label: 'En desarrollo', client: { profile_id: 5, name: 'Germán Franco', company: 'Kore' }, hostings_count: 1, incomes_count: 2, unlinked_hostings_count: 0, unlinked_incomes_count: 0, unlinked_documents_count: 0 }], meta: { total: 1, by_state: [], review_required: 0, clients_without_projects: 0, records_without_project: 0 } });
    if (apiPath === 'projects/9/access/') return json(accessDetail);
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    return null;
  });
}

const projectEntryByProfile = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Proyectos', exact: true }).click(); },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Proyectos', exact: true }).click(); },
  landscape: (page) => page.getByRole('link', { name: 'Proyectos', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Proyectos', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Proyectos', exact: true }).click(),
});

async function enterProjects(page, profile) {
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  await projectEntryByProfile[profile](page);
  await expect(page.getByRole('heading', { name: 'Proyectos', exact: true })).toHaveText('Proyectos');
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`projects catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    test('new project action opens from the project list', {
      tag: ['@flow:admin-panel-projects', '@outcome:display', '@responsive:projects', `@responsive-scenario:${projectsScenario.catalogKey}`, `@responsive-batch:${batchForScenario(projectsScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setupProjects(page);
      // quality: allow-deep-link (the authenticated panel home is the shell entry; this test reaches Projects through the visible responsive navigation)
      await enterProjects(page, profile);
      await page.getByTestId('projects-new-button').click();
      await expect(page.getByRole('dialog')).toContainText('Nuevo proyecto');
      await assertResponsiveScenario(page, testInfo, projectsScenario, { profile, modalLocator: page.getByRole('dialog') });
    });

    test('project state catalog is reached through its visible action', {
      tag: ['@flow:admin-project-state-catalog', '@outcome:display', '@responsive:projects', `@responsive-scenario:${statusesScenario.catalogKey}`, `@responsive-batch:${batchForScenario(statusesScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setupProjects(page);
      // quality: allow-deep-link (the authenticated panel home is the shell entry; this test reaches Projects through the visible responsive navigation)
      await enterProjects(page, profile);
      await page.getByTestId('projects-manage-states').click();
      await expect(page).toHaveURL(/\/panel\/projects\/statuses$/);
      await expect(page.getByText('Estados de proyectos', { exact: true })).toHaveText('Estados de proyectos');
      await assertResponsiveScenario(page, testInfo, statusesScenario, { profile });
    });

    test('project access detail preserves its stacked or paired environment layout', {
      tag: ['@flow:admin-project-access-detail', '@outcome:display', '@responsive:projects', '@responsive-special:projects', '@responsive-batch:projects-special-1', `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setupProjects(page);
      // quality: allow-deep-link (the authenticated panel home is the shell entry; this test reaches Projects through the visible responsive navigation)
      await enterProjects(page, profile);
      await openProjectAction(page, 9, 'detail');
      const modal = page.getByTestId('project-access-modal');
      await expect(modal).toContainText('https://kore.example.test');
      const production = await page.getByTestId('project-access-environment-production').boundingBox();
      const staging = await page.getByTestId('project-access-environment-staging').boundingBox();
      if (['compact', 'portrait'].includes(profile)) {
        expect(staging.y).toBeGreaterThan(production.y);
      } else {
        expect(Math.abs(staging.y - production.y)).toBeLessThanOrEqual(2);
        expect(staging.x).toBeGreaterThan(production.x);
      }
      await assertResponsiveScenario(page, testInfo, projectsScenario, { profile, modalLocator: modal });
    });
  });
}

test.describe('projects responsive special', () => {
  test.use(viewportUse('landscape'));
  test('change-client preview displays complete impact before confirmation', {
    tag: ['@flow:admin-project-change-client', '@outcome:display', '@responsive-special:projects', '@viewport:landscape', '@responsive-batch:projects-special-1'],
  }, async ({ page }) => {
    const preview = { project: { id: 1, name: 'Vastago' }, current_client: { profile_id: 5, name: 'Pepito Pérez' }, new_client: { profile_id: 9, name: 'Juanito López' }, hostings_move: [{ id: 21, label: 'Pepito Pérez — vastago.com' }], incomes_move: [{ id: 31, label: 'Vastago - Fase 1', kind_label: 'Esperado', period_label: 'Julio 2026' }], incomes_blocked: [{ id: 32, label: 'Vastago - Fase 2', kind_label: 'Esperado', period_label: 'Agosto 2026', reason: 'Tiene una cuenta de cobro activa: se desvincula del proyecto y conserva su cliente.' }], clientless: [], draft_accounts: [], issued_accounts: [{ id: 61, title: 'CC Vastago', public_number: 'PA-PE-001', status_label: 'Issued' }], communication_threads_detaching: [], other_documents_count: 0, hosting_ids: [21], income_ids: [31, 32], communication_thread_ids: [], totals: { move: 2, blocked: 1, clientless: 0, drafts: 0, issued: 1, communications: 0 } };
    await setAuthLocalStorage(page, { token: 'projects-special-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
    await mockApi(page, async ({ apiPath, method }) => {
      const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
      if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
      if (apiPath === 'projects/') return json({ results: [{ id: 1, name: 'Vastago', status: 'active', status_label: 'Activo', client: { profile_id: 5, name: 'Pepito Pérez' }, hostings_count: 1, incomes_count: 1 }], meta: { total: 1, by_state: [] } });
      if (apiPath.startsWith('proposals/client-profiles/search/')) return json([{ id: 9, name: 'Juanito López', email: ['juanito', 'lopez.co'].join('@') }]);
      if (apiPath === 'projects/1/change-client/preview/' && method === 'GET') return json(preview);
      if (apiPath === 'project-states/' || apiPath === 'project-state-groups/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
      return null;
    });
    // quality: allow-deep-link (the catalog test covers sidebar entry; this isolates the guided cascade special)
    await page.goto('/en-us/panel/projects', { waitUntil: 'domcontentloaded' });
    await openProjectAction(page, 1, 'edit');
    await page.getByTestId('project-form-change-client').click();
    const dialog = page.getByRole('dialog', { name: 'Cambiar el cliente de "Vastago"', exact: true });
    await expect(dialog).toBeVisible();
    await dialog.getByTestId('project-change-client-picker').fill('Juanito');
    await page.getByTestId('client-autocomplete-option-9').click();
    await expect(dialog.getByTestId('project-change-client-preview')).toContainText('Vastago - Fase 1 · Esperado · Julio 2026');
    await expect(dialog.getByTestId('project-change-client-preview')).toContainText('vastago.com');
    await expect(dialog.getByTestId('project-change-client-blocked')).toContainText('conservan su cliente');
    await expect(dialog.getByTestId('project-change-client-issued')).toContainText('PA-PE-001 · Issued');
    await expect(dialog.getByTestId('project-change-client-issued')).toContainText('no se reasignan');
    await expect(dialog.getByTestId('project-change-client-confirm')).toBeDisabled();
  });
});
