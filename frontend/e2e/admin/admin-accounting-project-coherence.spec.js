/**
 * E2E test for requisito 14 of the coherence ticket: change the client of a
 * record and verify every module agrees — without reloading, and after
 * reloading.
 *
 * FLOWS: admin-accounting-project-coherence
 * Covers: a stateful backend mock (the mutation rewrites the state every
 *         later request serves) driving one client reassignment end to end:
 *         the preview names the project the row will lose, the hostings
 *         table rebuilds in place from the response, /panel/projects reads
 *         the moved counters, and a full page.reload() serves the same
 *         truth — proving the DB is the source and the UI never needed the
 *         reload to be right.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { bulkAction } from '../helpers/bulk-actions.js';
import { ADMIN_ACCOUNTING_PROJECT_COHERENCE } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

function freshState() {
  return {
    hosting: {
      id: 1,
      client: 5,
      client_display_name: 'Kore SAS',
      billing_email: '',
      client_name: 'German - Kore',
      project: 40,
      project_name: 'Kore Web',
      domain_url: 'https://korehealths.com/',
      monthly_value: '91667.00',
      payment_modality: 'monthly',
      payment_modality_label: 'Mensual (histórico)',
      benefit: '',
      valid_from: '2026-03-02',
      valid_to: '2026-09-02',
      cycles_count: 1,
      payment_per_cycle: '91667.00',
      total_paid: '91667.00',
      is_active: true,
      notes: '',
      created_at: '2026-03-02T10:00:00Z',
      updated_at: '2026-03-02T10:00:00Z',
    },
  };
}

const CLIENT_SEARCH_RESULT = [{
  id: 9,
  name: 'Ana Pérez',
  email: 'ana@perez.co',
  phone: '',
  company: '',
  nit: '',
  cedula: '',
  is_email_placeholder: false,
}];

/** Every GET serves the CURRENT state; the bulk client POST mutates it. */
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
    if (apiPath === 'accounting/hostings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [state.hosting],
          meta: {
            active_count: 1,
            monthly_income: '91667.00',
            expiring_soon_count: 0,
            total_paid: '91667.00',
            without_client_count: 0,
            without_project_count: state.hosting.project ? 0 : 1,
          },
        }),
      };
    }
    if (apiPath === 'accounting/hostings/bulk-assign-client/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, body });
      // The server rule the preview announced: the project belonged to the
      // previous client, so the move clears it.
      state.hosting = {
        ...state.hosting,
        client: body.client,
        client_display_name: 'Ana Pérez',
        project: null,
        project_name: null,
      };
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ updated: 1, results: [state.hosting] }),
      };
    }
    if (apiPath === 'projects/' && method === 'GET') {
      const moved = state.hosting.project === null;
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [{
            id: 40,
            name: 'Kore Web',
            description: '',
            status: 'active',
            status_label: 'Activo',
            created_at: '2026-08-01T10:00:00Z',
            client: { profile_id: 5, name: 'Kore SAS', company: '' },
            hostings_count: moved ? 0 : 1,
            incomes_count: 0,
            unlinked_hostings_count: 0,
            unlinked_incomes_count: 0,
          }],
          meta: {
            total: 1,
            active: 1,
            archived: 0,
            clients_without_projects: 0,
            records_without_project: 0,
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

test.describe('Admin Accounting — client/project coherence across modules', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('a client change propagates to every module without a reload, and survives one', {
    tag: [...ADMIN_ACCOUNTING_PROJECT_COHERENCE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = freshState();
    const calls = [];
    await mockApi(page, buildHandler({ state, calls }));

    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('accounting-row-1')).toContainText('Kore Web');

    // Reassign the client; the preview names the project side effect.
    await page.getByTestId('accounting-select-1').check();
    await bulkAction(page, 'hostings', 'Asignar cliente');
    await page.getByTestId('hostings-bulk-client').fill('Ana');
    await page.getByTestId('client-autocomplete-option-9').click();
    await expect(page.getByTestId('client-bulk-summary-project-cleared')).toContainText(
      '1 pierde también su proyecto (era del cliente anterior)',
    );
    await page.getByTestId('hostings-bulk-assign').click();

    // Same view, no reload: the row rebuilt from the mutation response.
    await expect(page.getByTestId('accounting-row-1')).toContainText('Ana Pérez');
    await expect(
      page.getByTestId('hosting-no-project-1').filter({ visible: true }),
    ).toHaveText('Sin proyecto');
    expect(calls[0].body).toEqual({ hosting_ids: [1], client: 9 });

    // Another module, still no reload: the project's counter moved to 0, so
    // its deep link (rendered only while records exist) is gone.
    await page.goto('/panel/projects', { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Proyectos', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('accounting-row-40')).toContainText('Kore Web');
    await expect(page.getByTestId('project-hostings-link-40')).toHaveCount(0);

    // After a full reload the same truth comes back from the (stateful)
    // backend: the reload never was what fixed the view.
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('heading', { name: 'Proyectos', exact: true }),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByTestId('accounting-row-40')).toContainText('Kore Web');
    await expect(page.getByTestId('project-hostings-link-40')).toHaveCount(0);

    await page.goto('/panel/accounting/hostings', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('accounting-row-1')).toContainText('Ana Pérez');
    await expect(
      page.getByTestId('hosting-no-project-1').filter({ visible: true }),
    ).toHaveText('Sin proyecto');
  });
});
