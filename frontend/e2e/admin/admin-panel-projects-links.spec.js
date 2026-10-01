import { openProjectAction } from '../helpers/projects.js';
/**
 * E2E tests for PA-50/PA-51 on /panel/projects: the jump to the platform
 * space and the assign-unlinked flow.
 *
 * FLOWS: admin-panel-projects
 * Covers: the per-row "N sin proyecto" badge opening the confirm-first
 *         assign modal (only checked ids travel, badge gone after); the
 *         post-create offer when the new project's client has loose
 *         records; the space action bridging into /platform/projects/<id>
 *         in a new tab; and the bridge failure landing on /platform/login
 *         instead of a broken link.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PANEL_PROJECTS } from '../helpers/flow-tags.js';
import { waitForNuxtApp } from '../helpers/navigation.js';

test.setTimeout(60_000);

const CLIENT = { profile_id: 5, name: 'Germán Franco', company: 'Kore' };

function projectRow(overrides = {}) {
  return {
    id: 1,
    name: 'Kore',
    description: '',
    status: 'active',
    status_label: 'Activo',
    created_at: '2026-08-01T10:00:00Z',
    client: CLIENT,
    hostings_count: 0,
    incomes_count: 0,
    unlinked_hostings_count: 1,
    unlinked_incomes_count: 1,
    ...overrides,
  };
}

const UNLINKED_PREVIEW = {
  client: { profile_id: 5, name: 'Germán Franco' },
  hostings: [{ id: 21, label: 'Germán Franco — korehealths.com' }],
  incomes: [{
    id: 31,
    label: 'Kore - Fase 1',
    kind_label: 'Esperado',
    period_label: 'Julio 2026',
  }],
  total: 2,
};

const CLIENT_SEARCH_RESULT = [{
  id: 5,
  name: 'Germán Franco',
  email: 'german@korehealths.com',
  phone: '',
  company: 'Kore',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
}];

/**
 * Stateful handler: after a successful assign, the listing serves the row
 * with a clean backlog, which is exactly what the badge assertion needs.
 */
function buildHandler({ calls, state = { assigned: false }, bridgeStatus = 200 }) {
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { username: 'admin', is_staff: true, is_superuser: true },
        }),
      };
    }
    if (apiPath === 'accounts/session-token-bridge/' && method === 'POST') {
      calls.push({ apiPath, method });
      if (bridgeStatus !== 200) {
        return {
          status: bridgeStatus,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'No autorizado.' }),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tokens: { access: 'e2e-platform-access', refresh: 'e2e-platform-refresh' },
          user: { id: 9001, role: 'admin', email: 'admin@e2e.test' },
        }),
      };
    }
    if (apiPath === 'projects/1/unlinked-records/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(UNLINKED_PREVIEW),
      };
    }
    if (apiPath === 'projects/1/assign-unlinked/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      state.assigned = true;
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          assigned_hostings: 1,
          assigned_incomes: 1,
          project: projectRow({
            hostings_count: 1,
            incomes_count: 1,
            unlinked_hostings_count: 0,
            unlinked_incomes_count: 0,
          }),
        }),
      };
    }
    if (apiPath === 'projects/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(projectRow({ id: 1, name: body.name })),
      };
    }
    if (apiPath.startsWith('projects/') && method === 'GET') {
      const row = state.assigned
        ? projectRow({
          hostings_count: 1,
          incomes_count: 1,
          unlinked_hostings_count: 0,
          unlinked_incomes_count: 0,
        })
        : projectRow();
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [row],
          meta: {
            total: 1,
            active: 1,
            archived: 0,
            clients_without_projects: 0,
            records_without_project: state.assigned ? 0 : 2,
          },
        }),
      };
    }
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(CLIENT_SEARCH_RESULT),
      };
    }
    // The platform space the popup lands on (context-level mocks).
    if (apiPath === 'accounts/me/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 9001, role: 'admin', email: 'admin@e2e.test' }),
      };
    }
    if (apiPath.startsWith('accounts/projects/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 1, name: 'Kore', status: 'active' }),
      };
    }
    return null;
  };
}

async function gotoProjects(page) {
  await page.goto('/panel/projects', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(
    page.getByRole('heading', { name: 'Proyectos', exact: true }),
  ).toBeVisible({ timeout: 45_000 });
}

test.describe('Admin Panel Projects — space link and assign flow', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the badge opens the assign modal and only confirmed ids travel', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoProjects(page);

    await expect(page.getByTestId('panel-projects-stat-unlinked')).toContainText('2');
    await page.getByTestId('project-assign-unlinked-1').click();

    const modal = page.getByTestId('project-assign-unlinked-modal');
    await expect(modal).toContainText('korehealths.com');
    await expect(modal).toContainText('Kore - Fase 1');

    await page.getByTestId('project-assign-unlinked-confirm').click();

    await expect(page.getByText('Registros asignados a "Kore"')).toBeVisible();
    const assignCall = calls.find((c) => c.apiPath === 'projects/1/assign-unlinked/');
    // document_ids rides along since F7 (empty here: this client's backlog
    // has no documents in the fixture — the documents case lives in
    // admin-project-inline-assign-offer).
    expect(assignCall.body).toEqual({
      hosting_ids: [21],
      income_ids: [31],
      document_ids: [],
    });
    await expect(page.getByTestId('project-assign-unlinked-1')).toHaveCount(0);
    await expect(page.getByTestId('panel-projects-stat-unlinked')).toHaveCount(0);
  });

  test('creating a project for a client with loose records offers the assign modal', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoProjects(page);

    await page.getByTestId('projects-new-button').click();
    await page.getByTestId('project-form-name').fill('Kore');
    await page.getByTestId('project-form-client').fill('Germán');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('project-form-submit').click();

    // Offered, never assigned by itself: the modal is the confirmation step.
    const modal = page.getByTestId('project-assign-unlinked-modal');
    await expect(modal).toContainText('Kore - Fase 1');
    expect(calls.some((c) => c.apiPath === 'projects/1/assign-unlinked/')).toBe(false);
  });

  test('the space action bridges into the platform project in a new tab', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    // Context-level mocks so the popup tab inherits them too.
    await mockApi(page.context(), buildHandler({ calls }));
    await gotoProjects(page);

    const popupPromise = page.context().waitForEvent('page');
    await openProjectAction(page, 1, 'space');
    const popup = await popupPromise;

    await popup.waitForURL(/\/platform\/projects\/1/, { timeout: 25_000 });
    expect(calls.some((c) => c.apiPath === 'accounts/session-token-bridge/')).toBe(true);
  });

  test('a failed bridge lands on the platform login, never a broken link', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-flow-tag-mismatch (the login page is the FALLBACK LANDING of a failed bridge, not a login flow under test)
    const calls = [];
    await mockApi(page.context(), buildHandler({ calls, bridgeStatus: 403 }));
    await gotoProjects(page);

    const popupPromise = page.context().waitForEvent('page');
    await openProjectAction(page, 1, 'space');
    const popup = await popupPromise;

    await popup.waitForURL(/\/platform\/login/, { timeout: 25_000 });
    await expect(popup).toHaveURL(/\/platform\/login/);
  });
});
