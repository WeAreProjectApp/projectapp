/**
 * R-project-collaboration-01: responsive project spaces must retain the
 * client suggestion, team collection, and explicitly granted access paths;
 * a breakpoint must not turn a visible project record into an unreachable
 * action or crop the concrete value that makes the page useful.
 */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

test.setTimeout(60_000);

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
const personalClientToken = 'eyJhbGciOiJub25lIn0.eyJ1c2VyX2lkIjo5MDAyfQ.signature';
const ideaScenario = getResponsiveScenario('frontend/pages/platform/projects/[id]/ideas.vue');
const panelIdeasScenario = getResponsiveScenario('frontend/pages/panel/projects/[id]/ideas.vue');
const accessScenario = getResponsiveScenario('frontend/pages/platform/projects/[id]/access.vue');

const project = {
  id: 1,
  name: 'Portal de ideas responsive',
  description: 'Proyecto de prueba que conserva un valor concreto.',
  status: 'active',
  status_label: 'Activo',
  current_state: { color: 'emerald', operational_effect: 'operating' },
  progress: 65,
  client_id: 9002,
  client_name: 'Client E2E',
  client_email: 'client@e2e.test',
  phases_total_amount: '1200000.00',
  bugs_open_count: 1,
  changes_pending_count: 0,
  can_view_client_access: true,
};
const panelProject = {
  id: 1,
  name: project.name,
  client_name: project.client_name,
  client_company: 'ACME Corp',
  status_label: 'Activo',
  current_state: project.current_state,
  created_at: '2026-09-01T12:00:00Z',
  hostings_count: 0,
  incomes_count: 0,
  unlinked_hostings_count: 0,
  unlinked_incomes_count: 0,
  unlinked_documents_count: 0,
};
const idea = {
  id: 21,
  text: 'Conservar el reporte semanal para el próximo contrato.',
  author: 'Client E2E',
  created_at: '2026-09-01T12:00:00Z',
  updated_at: '2026-09-01T12:00:00Z',
  revision_number: 1,
  version: 1,
  archived: false,
  can_edit: true,
};

function ideasPage() {
  return { results: [idea], count: 1, page: 1, page_size: 20, total_pages: 1 };
}

async function setupPlatform(page) {
  await setPlatformAuth(page, { user: mockPlatformClient, accessToken: personalClientToken });
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(mockPlatformClient);
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project]);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(project);
    if (apiPath === 'accounts/projects/1/ideas/' && method === 'GET') return json(ideasPage());
    if (apiPath === 'accounts/projects/1/client-access/' && method === 'GET') {
      return json({
        project_id: 1,
        environments: [{
          environment: 'staging',
          site_url: 'https://qa.portal-responsive.test/',
          credential_actions: ['admin_username'],
        }],
      });
    }
    if (apiPath === 'accounts/projects/1/client-access/environments/staging/credentials/admin_username/reveal/' && method === 'POST') {
      return json({ secret: 'qa-client-user' });
    }
    return null;
  });
}

async function setupPanel(page) {
  await setAuthLocalStorage(page, { token: 'responsive-project-ideas', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'projects/' && method === 'GET') {
      return json({ results: [panelProject], meta: { total: 1, by_state: [], review_required: 0, clients_without_projects: 0, records_without_project: 0 } });
    }
    if (apiPath === 'projects/1/ideas/' && method === 'GET') return json(ideasPage());
    if (apiPath === 'projects/1/idea-collections/' && method === 'GET') return json({ results: [], count: 0, page: 1 });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    return null;
  });
}

const platformProjectEntry = Object.freeze({
  compact: (page) => page.getByTestId('project-card-1').click(),
  portrait: (page) => page.getByTestId('project-card-1').click(),
  landscape: (page) => page.getByTestId('project-row-1').click(),
  desktop: (page) => page.getByTestId('project-row-1').click(),
  wide: (page) => page.getByTestId('project-row-1').click(),
});

const panelProjectsEntry = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Proyectos', exact: true }).click(); },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Proyectos', exact: true }).click(); },
  landscape: (page) => page.getByRole('link', { name: 'Proyectos', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Proyectos', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Proyectos', exact: true }).click(),
});

const panelIdeasEntry = Object.freeze({
  compact: async (page) => { await page.getByTestId('project-actions-1').click(); await page.getByTestId('project-actions-ideas').click(); },
  portrait: async (page) => { await page.getByTestId('project-actions-1').click(); await page.getByTestId('project-actions-ideas').click(); },
  landscape: async (page) => { await page.getByTestId('project-actions-1').click(); await page.getByTestId('project-actions-ideas').click(); },
  desktop: async (page) => { await page.getByTestId('project-actions-1').click(); await page.getByTestId('project-actions-ideas').click(); },
  wide: async (page) => { await page.getByTestId('project-actions-1').click(); await page.getByTestId('project-actions-ideas').click(); },
});

async function openPlatformProject(page, profile) {
  // quality: allow-deep-link (the authenticated project list is the shell entry; the display flow reaches the project space through its record)
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByRole('heading', { name: 'Mis proyectos', exact: true })).toHaveText('Mis proyectos');
  await platformProjectEntry[profile](page);
  await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name);
}

async function openPanelIdeas(page, profile) {
  // quality: allow-deep-link (the authenticated panel home is the shell entry; the display flow reaches Projects through its visible navigation)
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  await panelProjectsEntry[profile](page);
  await expect(page.getByRole('heading', { name: 'Proyectos', exact: true })).toHaveText('Proyectos');
  await panelIdeasEntry[profile](page);
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`project collaboration responsive · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('client reaches the preserved project suggestion through the responsive project record', {
      tag: ['@flow:platform-project-ideas', '@outcome:display', '@responsive:clients', `@responsive-scenario:${ideaScenario.catalogKey}`, `@responsive-batch:${batchForScenario(ideaScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (openPlatformProject enters the authenticated project list and clicks the responsive project record)
      await setupPlatform(page);
      await openPlatformProject(page, profile);
      await page.getByRole('link', { name: 'Ideas', exact: true }).click();
      const workspace = page.getByTestId('project-ideas-workspace');
      await expect(workspace.getByTestId('project-idea-21')).toContainText(idea.text);
      await expect(workspace.getByTestId('project-idea-save')).toHaveText('Guardar idea');
      await assertResponsiveScenario(page, testInfo, ideaScenario, { profile });
    });

    test('team reaches the future-only idea collection from responsive panel actions', {
      tag: ['@flow:admin-project-idea-collection', '@outcome:display', '@responsive:projects', `@responsive-scenario:${panelIdeasScenario.catalogKey}`, `@responsive-batch:${batchForScenario(panelIdeasScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (openPanelIdeas enters the authenticated panel shell and follows the visible Projects and Ideas actions)
      await setupPanel(page);
      await openPanelIdeas(page, profile);
      const workspace = page.getByTestId('project-ideas-workspace');
      await workspace.getByTestId('project-idea-21').getByRole('checkbox').check();
      await expect(workspace.getByTestId('project-idea-21')).toContainText(idea.text);
      await expect(workspace.getByTestId('idea-collection-title')).toHaveValue('');
      await workspace.getByTestId('idea-collection-title').fill('Opciones conservadas');
      await expect(workspace.getByTestId('idea-collection-save')).toBeEnabled();
      await assertResponsiveScenario(page, testInfo, panelIdeasScenario, { profile });
    });

    test('client opens only the granted responsive access and explicitly reveals its action', {
      tag: ['@flow:platform-project-client-access', '@outcome:display', '@responsive:clients', '@responsive-special:clients', '@responsive-batch:clients-special-2', `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (openPlatformProject enters the authenticated project list and clicks the responsive project record before Access)
      await setupPlatform(page);
      await openPlatformProject(page, profile);
      await page.getByRole('link', { name: 'Accesos', exact: true }).click();
      const access = page.getByTestId('project-client-access');
      await expect(access.getByRole('link')).toHaveText('https://qa.portal-responsive.test/');
      await access.getByRole('button', { name: 'Mostrar', exact: true }).click();
      await expect(access.getByTestId('client-credential-value')).toHaveText('qa-client-user');
      await assertResponsiveScenario(page, testInfo, accessScenario, { profile });
    });
  });
}
