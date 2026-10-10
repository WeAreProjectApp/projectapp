/**
 * E2E tests for the guided change-client cascade on /panel/projects.
 *
 * FLOWS: admin-project-change-client
 * Catches a mode being preselected before reviewing the impact, a permitted
 * transfer omitting the preview's impact hash, or a blocked preview hiding
 * its reasons/new-project guidance or sending a change-client request.
 */
import { openProjectAction } from '../helpers/projects.js';
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

const EMPTY_CHANGE_PLAN = {
  moved: { hostings: 0, incomes: 0, draft_accounts: 0, project_folders: 0 },
  detached: { hostings: 0, incomes: 0, draft_accounts: 0 },
  detached_communications: 0,
  skipped: { issued_accounts: 0, clientless: 0, other_documents: 0 },
  records: {
    hostings_move: [], hostings_detach: [],
    incomes_move: [], incomes_detach: [],
    draft_accounts_move: [], draft_accounts_detach: [],
    project_folders_move: [],
    communication_threads_detach: [], communication_folders_detach: [],
    liquid_children_move: [], liquid_children_detach: [],
  },
};

const PREVIEW = {
  project: { id: 1, name: 'Vastago' },
  current_client: { profile_id: 5, name: 'Pepito Pérez' },
  new_client: { profile_id: 9, name: 'Juanito López' },
  can_apply: true,
  blockers: [],
  blocker_counts: {
    hosting_subscription: 0, project_hosting: 0, hosting_record: 0,
    collection_account: 0, collection_account_context: 0,
    delivery_publication: 0, delivery_prompt_context: 0,
    contract_signature_evidence: 0, project_contract: 0, contract_amendment: 0,
    delivery_message: 0, bug_report: 0, change_request: 0,
  },
  planned: {
    move: {
      ...EMPTY_CHANGE_PLAN,
      moved: { ...EMPTY_CHANGE_PLAN.moved, incomes: 1 },
      records: { ...EMPTY_CHANGE_PLAN.records, incomes_move: [31] },
    },
    detach: {
      ...EMPTY_CHANGE_PLAN,
      detached: { ...EMPTY_CHANGE_PLAN.detached, incomes: 1 },
      records: { ...EMPTY_CHANGE_PLAN.records, incomes_detach: [31] },
    },
  },
  financial_history: {
    subscriptions: [], project_hosting_ids: [], hosting_record_ids: [],
    issued_accounts: [], collection_account_contexts: [],
  },
  impact_hash: 'a'.repeat(64),
  hostings_move: [],
  incomes_move: [{
    id: 31, label: 'Vastago - Fase 1',
    kind_label: 'Esperado', period_label: 'Julio 2026',
  }],
  incomes_blocked: [],
  clientless: [],
  draft_accounts: [],
  issued_accounts: [],
  communication_threads_detaching: [],
  other_documents_count: 0,
  hosting_ids: [],
  income_ids: [31],
  communication_thread_ids: [],
  totals: {
    move: 1, blocked: 0, clientless: 0, drafts: 0, issued: 0, communications: 0,
  },
};

const BLOCKED_PREVIEW = {
  ...PREVIEW,
  can_apply: false,
  blockers: [
    {
      code: 'client_change_financial_history',
      message: 'El proyecto tiene cuentas o hosting con historia financiera; no puede trasladarse a otro cliente.',
      resource_type: 'hosting_record', resource_id: 21,
      resolution: 'create_new_project',
    },
    {
      code: 'client_change_financial_history',
      message: 'El proyecto tiene cuentas o hosting con historia financiera; no puede trasladarse a otro cliente.',
      resource_type: 'collection_account', resource_id: 61,
      resolution: 'create_new_project',
    },
    {
      code: 'delivery_client_history_frozen',
      message: 'Este proyecto conserva entregas, firmas, fuentes o conversaciones del cliente actual. No puedes transferirlo a otra persona porque expondría esa historia. Crea un proyecto separado para el nuevo cliente.',
      resource_type: 'delivery_publication', resource_id: 73,
      resolution: 'create_new_project',
    },
  ],
  blocker_counts: {
    ...PREVIEW.blocker_counts,
    hosting_record: 1, collection_account: 1, delivery_publication: 1,
  },
  planned: {
    move: {
      ...PREVIEW.planned.move,
      moved: { ...PREVIEW.planned.move.moved, hostings: 1 },
      detached: { ...EMPTY_CHANGE_PLAN.detached, incomes: 1 },
      skipped: { ...EMPTY_CHANGE_PLAN.skipped, issued_accounts: 1 },
      records: {
        ...PREVIEW.planned.move.records,
        hostings_move: [21], incomes_detach: [32],
      },
    },
    detach: {
      ...PREVIEW.planned.detach,
      detached: { ...EMPTY_CHANGE_PLAN.detached, hostings: 1, incomes: 2 },
      skipped: { ...EMPTY_CHANGE_PLAN.skipped, issued_accounts: 1 },
      records: {
        ...PREVIEW.planned.detach.records,
        hostings_detach: [21], incomes_detach: [31, 32],
      },
    },
  },
  financial_history: {
    ...PREVIEW.financial_history,
    hosting_record_ids: [21],
    issued_accounts: [{ id: 61, status: 'issued' }],
  },
  impact_hash: 'b'.repeat(64),
  hostings_move: [{ id: 21, label: 'Pepito Pérez — vastago.com' }],
  incomes_blocked: [{
    id: 32, label: 'Vastago - Fase 2',
    kind_label: 'Esperado', period_label: 'Agosto 2026',
    reason: 'Tiene una cuenta de cobro activa: se desvincula del proyecto y conserva su cliente.',
  }],
  issued_accounts: [{
    id: 61, title: 'CC Vastago', public_number: 'PA-PE-001', status_label: 'Issued',
  }],
  hosting_ids: [21],
  income_ids: [31, 32],
  totals: { ...PREVIEW.totals, move: 2, blocked: 1, issued: 1 },
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
    hostings_count: 0,
    incomes_count: 1,
    unlinked_hostings_count: 0,
    unlinked_incomes_count: 0,
    ...overrides,
  };
}

function buildHandler({ state, calls, preview = PREVIEW }) {
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
        body: JSON.stringify(preview),
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
          moved: { hostings: 0, incomes: 1, draft_accounts: 0 },
          detached: { hostings: 0, incomes: 0, draft_accounts: 0 },
          detached_communications: 0,
          skipped: { issued_accounts: 0, clientless: 0, other_documents: 0 },
        }),
      };
    }
    if (apiPath === 'projects/' && method === 'GET') {
      const row = state.moved
        ? projectRow({
          client: { profile_id: 9, name: 'Juanito López', company: '' },
          incomes_count: 1,
        })
        : projectRow({
          hostings_count: preview.hosting_ids.length,
          incomes_count: preview.income_ids.length,
        });
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

  test('a permitted preview requires an explicit cascade mode', {
    tag: [...ADMIN_PROJECT_CHANGE_CLIENT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar entry into /panel/projects is covered by admin-panel-projects; this pins the cascade preview)
    await mockApi(page, buildHandler({ state: {}, calls: [] }));
    await openCascadeModal(page);

    await expect(page.getByTestId('project-change-client-preview'))
      .toContainText('Vastago - Fase 1 · Esperado · Julio 2026');
    await expect(page.getByTestId('project-change-client-mode')).toBeVisible();
    // No preselected mode: the decision is taken on every cascade.
    await expect(page.getByTestId('project-change-client-confirm')).toBeDisabled();
  });

  test('choosing Mover submits the reviewed impact hash', {
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
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toEqual({
      client_profile_id: 9,
      mode: 'move',
      hosting_ids: [],
      income_ids: [31],
      communication_thread_ids: [],
      expected_impact_hash: PREVIEW.impact_hash,
    });
  });

  test('a blocked preview prevents changing the project client', {
    tag: [...ADMIN_PROJECT_CHANGE_CLIENT, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ state: {}, calls, preview: BLOCKED_PREVIEW }));
    await openCascadeModal(page);

    const blockers = page.getByTestId('project-change-client-blockers');
    await expect(blockers.getByRole('listitem'))
      .toHaveText(BLOCKED_PREVIEW.blockers.map((blocker) => blocker.message));
    await expect(page.getByTestId('project-change-client-resolution')).toBeVisible();
    await expect(page.getByTestId('project-change-client-resolution'))
      .toHaveText('La historia financiera o de entregas queda con el cliente actual. Crea un proyecto nuevo para el cliente destino.');
    await expect(page.getByTestId('project-change-client-mode')).toHaveCount(0);
    await expect(page.getByTestId('project-change-client-confirm')).toBeDisabled();

    await page.getByTestId('project-change-client-cancel').click();
    await expect(page.getByTestId('project-change-client-modal')).toBeHidden();
    expect(calls).toEqual([]);
  });
});
