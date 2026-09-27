/**
 * E2E tests for the /panel/projects module (Plataforma space).
 *
 * FLOWS: admin-panel-projects
 * Covers: listing + search + lifecycle-state filter; minimal create through the
 *         modal (with the non-blocking duplicate warning); backend 400
 *         keeping the modal open; state-count filtering; the
 *         clients-without-projects panel seeding the create modal; and the
 *         count link jumping into hostings pre-filtered by project.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PANEL_PROJECTS } from '../helpers/flow-tags.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const PROJECT_ROWS = [
  {
    id: 1,
    name: 'Kore',
    description: '',
    status: 'active',
    status_label: 'Activo',
    current_state: {
      id: 2,
      name: 'Activo',
      system_key: 'active',
      operational_effect: 'operating',
      description: 'Está entregado y operando.',
      operational_effect_help: 'Mantiene habilitados los cobros y los avisos.',
      color: 'emerald',
    },
    state_review_required: false,
    state_suggestion: null,
    created_at: '2026-08-01T10:00:00Z',
    client: { profile_id: 5, name: 'Germán Franco', company: 'Kore' },
    hostings_count: 2,
    incomes_count: 3,
  },
  {
    id: 2,
    name: 'Vástago',
    description: 'App de gestión',
    status: 'decommissioned',
    status_label: 'Dado de baja',
    current_state: {
      id: 6,
      name: 'Dado de baja',
      system_key: 'decommissioned',
      operational_effect: 'decommissioned',
      description: 'Terminó de forma definitiva.',
      operational_effect_help: 'Cancela el servicio y los cobros futuros.',
      color: 'gray',
    },
    state_review_required: false,
    state_suggestion: null,
    created_at: '2026-07-01T10:00:00Z',
    client: { profile_id: 7, name: 'Deivis Ríos', company: 'Vástago' },
    hostings_count: 0,
    incomes_count: 0,
  },
];

const PROJECT_STATES = [
  { id: 1, name: 'En desarrollo', description: 'Se está construyendo.', system_key: 'development', operational_effect: 'development', operational_effect_help: 'Permite los cobros de construcción.', color: 'blue', group: 1, order: 0, is_active: true, merged_into: null },
  { id: 2, name: 'Activo', description: 'Está entregado y operando.', system_key: 'active', operational_effect: 'operating', operational_effect_help: 'Mantiene habilitados los cobros y los avisos.', color: 'emerald', group: 1, order: 1, is_active: true, merged_into: null },
  { id: 7, name: 'En evolución', description: 'Está en producción mientras se desarrolla una ampliación.', system_key: 'evolving', operational_effect: 'operating', operational_effect_help: 'Mantiene habilitados los cobros y los avisos.', color: 'blue', group: 1, order: 2, is_active: true, merged_into: null },
  { id: 4, name: 'Suspendido', description: 'El servicio puede reactivarse.', system_key: 'suspended', operational_effect: 'suspended', operational_effect_help: 'Detiene nuevos cobros y avisos.', color: 'orange', group: 1, order: 4, is_active: true, merged_into: null },
  { id: 5, name: 'Completado', description: 'Terminó correctamente.', system_key: 'completed', operational_effect: 'completed', operational_effect_help: 'Exige un cierre financiero limpio.', color: 'purple', group: 1, order: 5, is_active: true, merged_into: null },
  { id: 6, name: 'Dado de baja', description: 'Terminó de forma definitiva.', system_key: 'decommissioned', operational_effect: 'decommissioned', operational_effect_help: 'Cancela el servicio y los cobros futuros.', color: 'gray', group: 1, order: 6, is_active: true, merged_into: null },
];

const META = {
  total: 2,
  by_state: PROJECT_STATES.map((state) => ({
    state_id: state.id,
    name: state.name,
    description: state.description,
    color: state.color,
    system_key: state.system_key,
    operational_effect: state.operational_effect,
    operational_effect_help: state.operational_effect_help,
    count: [2, 6].includes(state.id) ? 1 : 0,
  })),
  review_required: 0,
  clients_without_projects: 2,
  records_without_project: 0,
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

const ORPHAN_CLIENTS = [
  { id: 8, name: 'Wilson García', email: 'wilson@example.com', company: 'Gimnasio W' },
  { id: 9, name: 'Miguel y Carlos', email: 'crushme@example.com', company: 'Crushme' },
];

const HOSTING_ROWS = [
  {
    id: 21,
    client: 5,
    client_display_name: 'Germán Franco',
    billing_email: 'german@korehealths.com',
    client_name: 'German - Kore',
    project: 1,
    project_name: 'Kore',
    domain_url: 'https://korehealths.com/',
    monthly_value: '91667.00',
    payment_modality: 'semiannual',
    payment_modality_label: 'Semestral',
    benefit: '',
    valid_from: '2026-03-02',
    valid_to: '2026-09-02',
    cycles_count: 1,
    payment_per_cycle: '550002.00',
    total_paid: '1100000.00',
    is_active: true,
    notes: '',
    created_at: '2026-03-02T10:00:00Z',
    updated_at: '2026-03-02T10:00:00Z',
  },
  {
    id: 22,
    client: 7,
    client_display_name: 'Deivis Ríos',
    billing_email: '',
    client_name: 'Deivis - Vastago',
    project: null,
    project_name: null,
    domain_url: 'https://vastago.co/',
    monthly_value: '19000.00',
    payment_modality: 'nine_month',
    payment_modality_label: 'Cada 9 meses',
    benefit: '',
    valid_from: '2026-07-01',
    valid_to: '2027-04-01',
    cycles_count: 0,
    payment_per_cycle: '171000.00',
    total_paid: '0.00',
    is_active: true,
    notes: '',
    created_at: '2026-07-01T10:00:00Z',
    updated_at: '2026-07-01T10:00:00Z',
  },
];

function buildHandler({ calls, createStatus = 201, projects = PROJECT_ROWS, meta = META }) {
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
    if (apiPath.startsWith('project-states/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PROJECT_STATES),
      };
    }
    if (apiPath === 'project-state-groups/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 1,
          name: 'Ciclo del proyecto',
          catalog: 'projects',
          selection_mode: 'exclusive',
          order: 0,
          is_active: true,
        }]),
      };
    }
    if (apiPath.startsWith('projects/') && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: projects, meta }),
      };
    }
    if (apiPath === 'projects/create/' && method === 'POST') {
      const body = route.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (createStatus !== 201) {
        return {
          status: createStatus,
          contentType: 'application/json',
          body: JSON.stringify({
            client_profile_id: ['Ese cliente no existe o no es un perfil de cliente.'],
          }),
        };
      }
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          ...PROJECT_ROWS[0],
          id: 99,
          name: body.name,
          status: 'development',
          status_label: 'En desarrollo',
          current_state: PROJECT_STATES[0],
          hostings_count: 0,
          incomes_count: 0,
        }),
      };
    }
    if (/^projects\/\d+\/update\/$/.test(apiPath) && method === 'PATCH') {
      const body = route.request().postDataJSON() || {};
      calls.push({ apiPath, method, body });
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...PROJECT_ROWS[0], ...body }),
      };
    }
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(CLIENT_SEARCH_RESULT),
      };
    }
    if (apiPath.startsWith('proposals/client-profiles/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ORPHAN_CLIENTS),
      };
    }
    if (apiPath === 'accounting/hostings/' && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: HOSTING_ROWS, meta: { active_count: 2 } }),
      };
    }
    if (apiPath.startsWith('accounting/projects/')) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [] }),
      };
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  };
}

async function gotoProjects(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  const link = page.getByRole('link', { name: 'Proyectos', exact: true });
  await expect(link).toBeVisible({ timeout: 25_000 });
  await link.click();
  await expect(
    page.getByRole('heading', { name: 'Proyectos', exact: true }),
  ).toBeVisible({ timeout: 25_000 });
  // The heading is server-rendered. Waiting for a real row proves the Pinia
  // load and Nuxt hydration finished before an interaction is attempted.
  await expect(getProjectResult(page, 1)).toBeVisible({ timeout: 25_000 });
}

function getProjectResult(page, projectId) {
  return page.getByTestId(new RegExp(`^(?:accounting-row|project-card)-${projectId}$`));
}

test.describe('Admin Panel Projects', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test.describe('compact indicator header', () => {
    test.use(viewportUse('compact'));

    test('renders two equal-height summaries before the project cards', {
      tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display', '@responsive:projects'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await gotoProjects(page);

      const summaries = page.getByTestId('projects-indicators-compact').locator('article');
      await expect(summaries).toHaveCount(2);
      const heights = await summaries.evaluateAll((cards) => (
        cards.map((card) => Math.round(card.getBoundingClientRect().height))
      ));
      expect(new Set(heights).size).toBe(1);

      const firstProject = await getProjectResult(page, 1).boundingBox();
      expect(firstProject.y).toBeLessThan(915);
    });

    test('exposes zero-count lifecycle states from the compact summary', {
      tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display', '@responsive:projects'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await gotoProjects(page);

      await page.getByTestId('panel-projects-stat-states-summary').click();
      const stateRows = page.locator('[data-testid^="project-state-detail-"]');
      await expect(stateRows).toHaveCount(6);
      await expect(page.getByTestId('project-state-detail-4')).toContainText('Suspendido');
      await expect(page.getByTestId('project-state-detail-4')).toContainText('0');
      expect(await stateRows.evaluateAll((rows) => (
        rows.map((row) => row.getAttribute('aria-label'))
      ))).toEqual(
        PROJECT_STATES.map((state) => `Filtrar proyectos en estado ${state.name}`),
      );

      await page.getByTestId('project-state-detail-2').click();
      await expect(getProjectResult(page, 1)).toContainText('Activo');
      await expect(getProjectResult(page, 2)).toHaveCount(0);
    });

    test('keeps project validation beside the incomplete fields and the footer clean', {
      tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:error', '@responsive:projects'],
    }, async ({ page }) => {
      const calls = [];
      await mockApi(page, buildHandler({ calls }));
      await gotoProjects(page);

      await page.getByTestId('projects-new-button').click();
      await page.getByTestId('project-form-submit').click();

      const name = page.getByTestId('project-form-name');
      const client = page.getByTestId('project-form-client');
      await expect(name).toHaveAttribute('aria-invalid', 'true');
      await expect(client).toHaveAttribute('aria-invalid', 'true');
      await expect(page.getByText('Escribe el nombre del proyecto.', { exact: true })).toBeVisible();
      await expect(page.getByText('Elige o crea un cliente.', { exact: true })).toBeVisible();

      const actions = page.getByTestId('base-modal-actions');
      await expect(actions.getByRole('button')).toHaveCount(2);
      await expect(actions.getByRole('alert')).toHaveCount(0);
      expect(calls).toHaveLength(0);
    });
  });

  test.describe('portrait creation form', () => {
    test.use(viewportUse('portrait'));

    test('reads as one full-width block and exposes inline client creation', {
      tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display', '@responsive:projects'],
    }, async ({ page }) => {
      await mockApi(page, buildHandler({ calls: [] }));
      await gotoProjects(page);

      await page.getByTestId('projects-new-button').click();
      const name = page.getByTestId('project-form-name');
      const client = page.getByTestId('project-form-client');
      const state = page.getByTestId('project-form-status');

      await expect(state).toHaveValue('1');
      await expect(page.getByText('Cliente al que pertenece y se factura el proyecto.', { exact: true }))
        .toBeVisible();
      await expect(page.getByText(/si no (eliges|seleccionas) un estado/i)).toHaveCount(0);
      await expect(page.getByText(/\(opcional\)/i)).toHaveCount(0);

      const widths = await Promise.all([name, client, state].map(async (control) => (
        Math.round((await control.boundingBox()).width)
      )));
      expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(2);

      await client.fill('Germán');
      await expect(page.getByTestId('client-autocomplete-option-5')).toBeVisible();
      await expect(page.getByTestId('client-autocomplete-create-new'))
        .toContainText('Crear nuevo cliente "Germán"');
    });
  });

  test('search narrows the listing by project or client name', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoProjects(page);

    await expect(page.getByTestId('accounting-row-1')).toBeVisible();
    await expect(page.getByTestId('panel-projects-stat-orphans')).toContainText('2');

    await page.getByTestId('projects-search-input').fill('germán');
    await expect(page.getByTestId('accounting-row-1')).toBeVisible();

    await page.getByTestId('projects-search-input').fill('nadie');
    await expect(page.getByTestId('accounting-row-1')).toHaveCount(0);
    await expect(page.getByText('Sin resultados con esos filtros')).toBeVisible();
  });

  test('state help explains the meaning and the operational consequence', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoProjects(page);

    await page.getByTestId('project-table-state-help-1').click();

    const help = page.getByTestId('project-table-state-help-1-content');
    await expect(help).toContainText('Está entregado y operando.');
    await expect(help).toContainText('Mantiene habilitados los cobros y los avisos.');
  });

  test('the state control filters projects by the administrable catalog', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display', '@responsive:projects'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar navigation is covered by the search test)
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoProjects(page);

    await expect(getProjectResult(page, 1)).toBeVisible();
    await expect(getProjectResult(page, 2)).toBeVisible();

    await page.getByTestId('projects-state-filter').selectOption('state:6');
    await expect(getProjectResult(page, 2)).toBeVisible();
    await expect(getProjectResult(page, 1)).toHaveCount(0);
    await expect(getProjectResult(page, 2)).toContainText('Dado de baja');
  });

  test('creates a project with the PA-38 minimum through the modal', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoProjects(page);

    await page.getByTestId('projects-new-button').click();
    await page.getByTestId('project-form-name').fill('Crushme');
    await page.getByTestId('project-form-client').fill('Germán');
    await page.getByTestId('client-autocomplete-option-5').click();
    const footer = page.locator('[data-modal-footer]');
    const save = footer.getByTestId('project-form-submit');
    await expect(footer.getByRole('button')).toHaveCount(2);
    await expect(footer.getByRole('button', { name: 'Cancelar', exact: true })).toHaveText('Cancelar');
    await expect(save).toHaveText('Guardar');
    await expect(footer.getByRole('alert')).toHaveCount(0);
    await save.click();

    await expect(page.getByText('Proyecto creado')).toBeVisible();
    await expect(getProjectResult(page, 99)).toContainText('Crushme');
    expect(calls[0].body).toEqual({
      name: 'Crushme',
      client_profile_id: 5,
      description: '',
      state_id: 1,
    });
  });

  test('a same-name project warns without blocking the save', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoProjects(page);

    await page.getByTestId('projects-new-button').click();
    await page.getByTestId('project-form-name').fill('kore');
    await page.getByTestId('project-form-client').fill('Germán');
    await page.getByTestId('client-autocomplete-option-5').click();

    await expect(page.getByTestId('project-form-duplicate-warning')).toContainText('Kore');
    await page.getByTestId('project-form-submit').click();

    await expect(page.getByText('Proyecto creado')).toBeVisible();
    expect(calls).toHaveLength(1);
  });

  test('a backend field rejection stays beside its control and keeps the modal open', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls, createStatus: 400 }));
    await gotoProjects(page);

    await page.getByTestId('projects-new-button').click();
    await page.getByTestId('project-form-name').fill('Crushme');
    await page.getByTestId('project-form-client').fill('Germán');
    await page.getByTestId('client-autocomplete-option-5').click();
    await page.getByTestId('project-form-submit').click();

    await expect(page.getByText(
      'Ese cliente no existe o no es un perfil de cliente.',
      { exact: true },
    )).toBeVisible();
    await expect(page.getByTestId('project-form-client')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByText('No se pudo crear el proyecto', { exact: true })).toHaveCount(0);
    await expect(page.getByTestId('project-form-name')).toBeVisible();
  });

  test('a state count card applies the same lifecycle filter', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoProjects(page);

    await page.getByTestId('panel-projects-stat-state-2').click();
    await expect(getProjectResult(page, 1)).toContainText('Activo');
    await expect(getProjectResult(page, 2)).toHaveCount(0);
  });

  test('state help opens without applying the lifecycle filter', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoProjects(page);

    await page.getByTestId('project-stat-state-help-2').click();

    await expect(page.getByTestId('project-stat-state-help-2-content'))
      .toContainText('Está entregado y operando.');
    await expect(page.getByTestId('projects-state-filter')).toHaveValue('all');
    await expect(getProjectResult(page, 1)).toBeVisible();
    await expect(getProjectResult(page, 2)).toBeVisible();
  });

  test('operational help opens without activating its pending workflow', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      calls: [],
      meta: { ...META, records_without_project: 3 },
    }));
    await gotoProjects(page);

    await page.getByTestId('project-stat-unlinked-help').click();

    await expect(page.getByTestId('project-stat-unlinked-help-content'))
      .toContainText('Suma hostings e ingresos');
    await expect(page.getByTestId('project-pending-indicator-drawer')).toHaveCount(0);
  });

  test('non-zero state cards preserve the catalog order', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoProjects(page);

    const cards = page.locator('[data-testid^="panel-projects-stat-state-"]');
    await expect(cards).toHaveCount(2);
    expect(await cards.locator('[data-testid="indicator-label"]').allTextContents())
      .toEqual(['Activo', 'Dado de baja']);
    await expect(page.getByTestId('panel-projects-stat-state-1')).toHaveCount(0);
  });

  test('the unlinked-record indicator reveals its accounting destinations', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({
      calls: [],
      meta: { ...META, records_without_project: 3 },
    }));
    await gotoProjects(page);

    await page.getByTestId('panel-projects-stat-unlinked').click();
    await expect(page.getByTestId('project-pending-records-detail')).toContainText('3');
    await expect(page.getByTestId('project-unlinked-hostings-link'))
      .toHaveAttribute('href', /accounting_hostingTab=no-project/);
    await expect(page.getByTestId('project-unlinked-incomes-link'))
      .toHaveAttribute('href', /accounting_incomeTab=no-project/);
  });

  test('the uncovered-clients panel seeds the create modal', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = [];
    await mockApi(page, buildHandler({ calls }));
    await gotoProjects(page);

    await page.getByTestId('panel-projects-stat-orphans').click();
    await expect(page.getByTestId('panel-projects-orphans')).toContainText('Wilson García');

    await page.getByTestId('projects-orphan-create-8').click();
    await expect(page.getByTestId('project-form-name')).toBeVisible();
    await page.getByTestId('project-form-name').fill('Gimnasio');
    await page.getByTestId('project-form-submit').click();

    await expect(page.getByText('Proyecto creado')).toBeVisible();
    expect(calls[0].body.client_profile_id).toBe(8);
    expect(calls[0].body.name).toBe('Gimnasio');
  });

  test('the hostings count jumps into the accounting tab pre-filtered', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ calls: [] }));
    await gotoProjects(page);

    await page.getByTestId('project-hostings-link-1').click();
    await expect(page).toHaveURL(/\/panel\/accounting\/hostings\?project=1/);
    await expect(
      page.getByRole('heading', { name: 'Hostings', exact: true }),
    ).toBeVisible({ timeout: 25_000 });

    // The seed filters the table to the linked project's rows only.
    await expect(page.getByTestId('accounting-row-21')).toBeVisible();
    await expect(page.getByTestId('accounting-row-22')).toHaveCount(0);
  });
});
