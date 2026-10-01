import { openProjectAction } from '../helpers/projects.js';
/**
 * E2E tests for the guided change-client cascade on /panel/projects.
 *
 * FLOWS: admin-project-change-client
 * Covers: the ghost entry on the edit form (the field itself stays
 *         immutable), the impact preview naming what moves, what an active
 *         cuenta blocks, and the issued documents nothing may touch; the
 *         mode chosen EVERY time (confirm disabled until move/detach is
 *         picked — no preselection); and the apply payload carrying the
 *         staleness ids the preview returned.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROJECT_CHANGE_CLIENT } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const CLIENT_SEARCH_RESULT = [{
  id: 9,
  name: 'Juanito López',
  email: 'juanito@lopez.co',
  phone: '',
  company: '',
  nit: '',
  cedula: '',
  is_email_placeholder: false,
}];

const PREVIEW = {
  project: { id: 1, name: 'Vastago' },
  current_client: { profile_id: 5, name: 'Pepito Pérez' },
  new_client: { profile_id: 9, name: 'Juanito López' },
  hostings_move: [{ id: 21, label: 'Pepito Pérez — vastago.com' }],
  incomes_move: [{
    id: 31, label: 'Vastago - Fase 1',
    kind_label: 'Esperado', period_label: 'Julio 2026',
  }],
  incomes_blocked: [{
    id: 32, label: 'Vastago - Fase 2',
    kind_label: 'Esperado', period_label: 'Agosto 2026',
    reason: 'Tiene una cuenta de cobro activa: se desvincula del proyecto y conserva su cliente.',
  }],
  clientless: [],
  draft_accounts: [],
  issued_accounts: [{
    id: 61, title: 'CC Vastago', public_number: 'PA-PE-001', status_label: 'Issued',
  }],
  communication_threads_detaching: [],
  other_documents_count: 0,
  hosting_ids: [21],
  income_ids: [31, 32],
  communication_thread_ids: [],
  totals: {
    move: 2, blocked: 1, clientless: 0, drafts: 0, issued: 1, communications: 0,
  },
};

function projectRow(overrides = {}) {
  return {
    id: 1,
    name: 'Vastago',
    description: '',
    status: 'active',
    status_label: 'Activo',
    created_at: '2026-08-01T10:00:00Z',
    client: { profile_id: 5, name: 'Pepito Pérez', company: '' },
    hostings_count: 1,
    incomes_count: 2,
    unlinked_hostings_count: 0,
    unlinked_incomes_count: 0,
    ...overrides,
  };
}

function buildHandler({ state, calls }) {
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
    if (apiPath === 'projects/1/change-client/preview/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PREVIEW),
      };
    }
    if (apiPath === 'projects/1/change-client/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      state.moved = true;
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          project: projectRow({
            client: { profile_id: 9, name: 'Juanito López', company: '' },
            incomes_count: 1,
          }),
          moved: { hostings: 1, incomes: 1, draft_accounts: 0 },
          detached: { hostings: 0, incomes: 1, draft_accounts: 0 },
          detached_communications: 0,
          skipped: { issued_accounts: 1, clientless: 0, other_documents: 0 },
        }),
      };
    }
    if (apiPath === 'projects/' && method === 'GET') {
      const row = state.moved
        ? projectRow({
          client: { profile_id: 9, name: 'Juanito López', company: '' },
          incomes_count: 1,
        })
        : projectRow();
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [row],
          meta: {
            total: 1, active: 1, archived: 0,
            clients_without_projects: 0, records_without_project: 0,
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
    return null;
  };
}

async function openCascadeModal(page) {
  await page.goto('/panel/projects', { waitUntil: 'domcontentloaded' });
  await expect(
    page.getByRole('heading', { name: 'Proyectos', exact: true }),
  ).toBeVisible({ timeout: 25_000 });
  await openProjectAction(page, 1, 'edit');
  await page.getByTestId('project-form-change-client').click();
  await expect(page.getByTestId('project-change-client-modal')).toBeVisible();
  await page.getByTestId('project-change-client-picker').fill('Juanito');
  await page.getByTestId('client-autocomplete-option-9').click();
  await expect(page.getByTestId('project-change-client-preview')).toBeVisible();
}

test.describe('Admin Projects — guided change-client cascade', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('the preview names the impact and the mode must be chosen every time', {
    tag: [...ADMIN_PROJECT_CHANGE_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar entry into /panel/projects is covered by admin-panel-projects; this pins the cascade preview)
    await mockApi(page, buildHandler({ state: {}, calls: [] }));
    await openCascadeModal(page);

    await expect(page.getByTestId('project-change-client-preview'))
      .toContainText('vastago.com');
    await expect(page.getByTestId('project-change-client-blocked'))
      .toContainText('conservan su cliente');
    await expect(page.getByTestId('project-change-client-issued'))
      .toContainText('no se reasignan');
    // No preselected mode: the decision is taken on every cascade.
    await expect(page.getByTestId('project-change-client-confirm')).toBeDisabled();
  });

  test('choosing Mover applies with the staleness ids and refreshes the row', {
    tag: [...ADMIN_PROJECT_CHANGE_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = {};
    const calls = [];
    await mockApi(page, buildHandler({ state, calls }));
    await openCascadeModal(page);

    await page.getByTestId('project-change-client-mode')
      .getByRole('tab', { name: 'Mover al nuevo cliente' }).click();
    await page.getByTestId('project-change-client-confirm').click();

    await expect(page.getByTestId('accounting-row-1')).toContainText('Juanito López');
    expect(calls[0].body).toEqual({
      client_profile_id: 9,
      mode: 'move',
      hosting_ids: [21],
      income_ids: [31, 32],
      communication_thread_ids: [],
    });
  });
});
