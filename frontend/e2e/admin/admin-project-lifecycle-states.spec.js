import { openProjectAction } from '../helpers/projects.js';
/**
 * E2E coverage for the real project lifecycle and its administrable catalog.
 *
 * @flow:admin-project-lifecycle-states
 * @flow:admin-project-state-catalog
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';
import {
  ADMIN_PROJECT_LIFECYCLE_STATES,
  ADMIN_PROJECT_STATE_CATALOG,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const GROUPS = [{
  id: 1,
  name: 'Ciclo del proyecto',
  catalog: 'projects',
  selection_mode: 'exclusive',
  order: 0,
  is_active: true,
  state_count: 7,
}];

const DESCRIPTION_BY_KEY = {
  development: 'El proyecto se está construyendo.',
  active: 'Está entregado y operando.',
  evolving: 'Está en producción mientras se desarrolla una ampliación.',
  suspended: 'El servicio puede reactivarse.',
  completed: 'Terminó como debía y quedó cerrado correctamente.',
  decommissioned: 'Terminó de forma definitiva.',
};

const HELP_BY_EFFECT = {
  development: 'Permite los cobros de construcción.',
  operating: 'Mantiene habilitados los cobros y los avisos.',
  suspended: 'Detiene nuevos cobros y avisos.',
  completed: 'Exige un cierre financiero limpio.',
  decommissioned: 'Cancela el servicio y los cobros futuros.',
};

function projectState(
  id,
  name,
  systemKey,
  operationalEffect,
  color,
  overrides = {},
) {
  return {
    id,
    name,
    description: DESCRIPTION_BY_KEY[systemKey] || 'Estado adaptado por el equipo.',
    slug: name.toLowerCase().replaceAll(' ', '-'),
    color,
    system_key: systemKey,
    operational_effect: operationalEffect,
    operational_effect_help: HELP_BY_EFFECT[operationalEffect],
    order: id,
    group: 1,
    group_id: 1,
    group_name: 'Ciclo del proyecto',
    group_mode: 'exclusive',
    group_order: 0,
    is_active: true,
    merged_into: null,
    incompatibility_ids: [],
    show_in_document_manager: ['development', 'active', 'evolving'].includes(systemKey),
    active_project_count: 0,
    historical_episode_count: 0,
    ...overrides,
  };
}

function initialCatalog() {
  return [
    projectState(1, 'En desarrollo', 'development', 'development', 'blue'),
    projectState(2, 'Activo', 'active', 'operating', 'emerald', {
      active_project_count: 1,
      historical_episode_count: 3,
    }),
    projectState(7, 'En evolución', 'evolving', 'operating', 'blue', { order: 2 }),
    projectState(4, 'Suspendido', 'suspended', 'suspended', 'orange', { order: 3 }),
    projectState(5, 'Completado', 'completed', 'completed', 'purple', { order: 4 }),
    projectState(6, 'Dado de baja', 'decommissioned', 'decommissioned', 'gray', { order: 5 }),
    projectState(8, 'En garantía', '', 'operating', 'blue', {
      description: 'Acompañamiento posterior a la entrega.',
      order: 6,
    }),
  ];
}

function projectRow(state) {
  return {
    id: 9,
    name: 'Kore',
    description: 'Plataforma clínica',
    status: state.system_key || state.slug,
    status_label: state.name,
    current_state: state,
    state_review_required: false,
    state_suggestion: null,
    created_at: '2026-06-01T10:00:00Z',
    client: { profile_id: 5, name: 'Germán Franco', company: 'Kore' },
    hostings_count: 1,
    incomes_count: 2,
    unlinked_hostings_count: 0,
    unlinked_incomes_count: 0,
    unlinked_documents_count: 0,
  };
}

function listing(catalog, currentState) {
  return {
    results: [projectRow(currentState)],
    meta: {
      total: 1,
      by_state: catalog.filter((state) => state.is_active).map((state) => ({
        state_id: state.id,
        name: state.name,
        description: state.description,
        color: state.color,
        system_key: state.system_key,
        operational_effect: state.operational_effect,
        operational_effect_help: state.operational_effect_help,
        count: state.id === currentState.id ? 1 : 0,
      })),
      review_required: 0,
      clients_without_projects: 0,
      records_without_project: 0,
    },
  };
}

const HISTORY = [
  {
    id: 31,
    state: projectState(4, 'Suspendido', 'suspended', 'suspended', 'orange'),
    opened_at: '2026-08-12T10:00:00Z',
    opening_time_known: true,
    opened_by_name: 'Ana Admin',
    closed_at: null,
    closed_by_name: '',
    close_note: '',
    outcome: '',
    duration_seconds: 1209600,
    notes: [],
    events: [],
  },
  {
    id: 30,
    state: projectState(2, 'Activo', 'active', 'operating', 'emerald'),
    opened_at: '2026-06-01T10:00:00Z',
    opening_time_known: true,
    opened_by_name: 'Ana Admin',
    closed_at: '2026-08-12T10:00:00Z',
    closed_by_name: 'Ana Admin',
    close_note: 'Hosting sin pago desde agosto.',
    outcome: 'transitioned',
    duration_seconds: 6220800,
    notes: [],
    events: [],
  },
];

function baseRoutes(apiPath, method, catalog, currentState) {
  if (apiPath === 'auth/check/') {
    return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
  }
  if (apiPath === 'project-states/' && method === 'GET') return json(catalog);
  if (apiPath === 'project-state-groups/' && method === 'GET') return json(GROUPS);
  if (apiPath === 'projects/' && method === 'GET') {
    return json(listing(catalog, currentState));
  }
  if (apiPath === 'projects/9/state-history/' && method === 'GET') {
    return json(HISTORY);
  }
  if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
  return null;
}

async function openProjects(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  const projectsLink = page.getByRole('link', { name: 'Proyectos', exact: true });
  await expect(projectsLink).toBeVisible({ timeout: 25_000 });
  await Promise.all([
    page.waitForURL(/\/panel\/projects(?:[/?#]|$)/, { timeout: 25_000 }),
    projectsLink.click(),
  ]);
  await waitForNuxtApp(page);
  await expect(
    page.getByRole('heading', { name: 'Proyectos', exact: true }),
  ).toBeVisible({ timeout: 25_000 });
  // The SSR heading arrives before the client store. The populated desktop row
  // or compact card is the observable readiness boundary for lifecycle actions.
  const projectRecord = page.viewportSize().width < PANEL_BREAKPOINTS.landscape
    ? page.getByTestId('project-card-9')
    : page.getByTestId('accounting-row-9');
  await expect(projectRecord).toBeVisible({ timeout: 25_000 });
}

async function openStateTransition(page, projectId = 9) {
  await openProjectAction(page, projectId, 'state');
  await expect(page.getByTestId('project-state-transition-modal')).toBeVisible();
}

async function openCatalog(page) {
  await openProjects(page);
  await page.getByTestId('projects-manage-states').click();
  await expect(page.getByTestId('project-state-catalog')).toBeVisible();
}

async function visibleBox(locator) {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box;
}

async function expectNoViewportOverflow(page) {
  await expect.poll(() => page.evaluate(() => {
    const widest = Math.max(
      document.documentElement.scrollWidth,
      document.body.scrollWidth,
    );
    return widest - document.documentElement.clientWidth;
  })).toBeLessThanOrEqual(1);
}

async function expectInlineControlError(page, control, message) {
  await expect(control).toHaveAttribute('aria-invalid', 'true');
  const errorId = await control.getAttribute('aria-describedby');
  expect(errorId).toBeTruthy();
  await expect(page.locator(`[id="${errorId}"]`)).toHaveText(message);
}

function horizontalGap(first, second) {
  return second.x - (first.x + first.width);
}

function verticalGap(first, second) {
  return second.y - (first.y + first.height);
}

test.describe('Admin project lifecycle states', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('shows the dated lifecycle history reached from the project row', {
    tag: [...ADMIN_PROJECT_LIFECYCLE_STATES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[3];
    await mockApi(page, async ({ apiPath, method }) => (
      baseRoutes(apiPath, method, catalog, currentState)
    ));

    await openProjects(page);
    await openProjectAction(page, 9, 'history');

    const history = page.getByTestId('project-state-history');
    await expect(history).toContainText('Suspendido');
    await expect(history).toContainText('Activo');
    await expect(history).toContainText('Hosting sin pago desde agosto.');
    await expect(history).toContainText('Ana Admin');
  });

  test('places missing state validation beside the selector', {
    tag: [...ADMIN_PROJECT_LIFECYCLE_STATES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    let previewCalls = 0;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'projects/9/state-transitions/preview/' && method === 'POST') {
        previewCalls += 1;
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openProjects(page);
    await openStateTransition(page);

    const target = page.getByTestId('project-state-target');
    const actions = page.getByTestId('base-modal-actions');
    await expect(target).not.toHaveAttribute('aria-invalid', 'true');
    await expect(actions.getByRole('button')).toHaveCount(2);
    await expect(actions.getByRole('alert')).toHaveCount(0);

    await page.getByTestId('project-state-preview').click();

    await expectInlineControlError(
      page,
      target,
      'Elige el nuevo estado del proyecto.',
    );
    expect(previewCalls).toBe(0);

    await target.selectOption('4');
    await expect(target).not.toHaveAttribute('aria-invalid', 'true');
  });

  test('previews suspension consequences before changing the row', {
    tag: [...ADMIN_PROJECT_LIFECYCLE_STATES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    let currentState = catalog[1];
    const calls = [];
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'projects/9/state-transitions/preview/' && method === 'POST') {
        calls.push({ kind: 'preview', body: route.request().postDataJSON() });
        return json({
          target_effect: 'suspended',
          impact_token: 'a'.repeat(64),
          effective_at: '2026-08-26T10:00:00Z',
          pending_incomes: [],
          future_incomes: [],
          future_payments: [],
          active_hostings: [{ id: 80, domain_url: 'https://korehealths.com' }],
          blockers: [],
        });
      }
      if (apiPath === 'projects/9/state-transitions/' && method === 'POST') {
        calls.push({ kind: 'apply', body: route.request().postDataJSON() });
        currentState = catalog[3];
        return json({ project: projectRow(currentState), episode: HISTORY[0] });
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openProjects(page);
    await openStateTransition(page);
    await page.getByTestId('project-state-target').selectOption('4');
    await page.getByTestId('project-state-preview').click();

    await expect(page.getByTestId('project-state-impact')).toContainText(
      'La deuda ya causada se conserva',
    );
    await page.getByTestId('project-state-apply').click();

    await expect(page.getByRole('alert')).toContainText('Estado actualizado');
    await expect(page.getByTestId('accounting-row-9')).toContainText('Suspendido');
    expect(calls.map((call) => call.kind)).toEqual(['preview', 'apply']);
    expect(calls[1].body.state_id).toBe(4);
  });

  test('changes an operating project to the distinct En evolución state', {
    tag: [...ADMIN_PROJECT_LIFECYCLE_STATES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    let currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'projects/9/state-transitions/preview/' && method === 'POST') {
        return json({
          target_effect: 'operating',
          impact_token: 'e'.repeat(64),
          effective_at: '2026-08-26T10:00:00Z',
          pending_incomes: [],
          future_incomes: [],
          future_payments: [],
          active_hostings: [],
          blockers: [],
        });
      }
      if (apiPath === 'projects/9/state-transitions/' && method === 'POST') {
        currentState = catalog[2];
        return json({ project: projectRow(currentState), episode: HISTORY[0] });
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openProjects(page);
    await openStateTransition(page);
    await page.getByTestId('project-state-target').selectOption('7');
    await expect(page.getByTestId('project-state-selected-help')).toContainText(
      'Está en producción mientras se desarrolla una ampliación.',
    );
    await page.getByTestId('project-state-preview').click();
    await page.getByTestId('project-state-apply').click();

    await expect(page.getByTestId('accounting-row-9')).toContainText('En evolución');
  });

  test('blocks a direct decommission until debt and note decisions exist', {
    tag: [...ADMIN_PROJECT_LIFECYCLE_STATES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'projects/9/state-transitions/preview/' && method === 'POST') {
        return json({
          target_effect: 'decommissioned',
          impact_token: 'b'.repeat(64),
          effective_at: '2026-08-26T10:00:00Z',
          pending_incomes: [{
            id: 41,
            concept: 'Hosting agosto',
            pending_amount: '120000.00',
          }],
          future_incomes: [],
          future_payments: [],
          active_hostings: [],
          blockers: [],
        });
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openProjects(page);
    await openStateTransition(page);
    await page.getByTestId('project-state-target').selectOption('6');
    await page.getByTestId('project-state-preview').click();

    const apply = page.getByTestId('project-state-apply');
    const incomeDecision = page.getByTestId('project-state-income-41');
    const note = page.getByTestId('project-state-note');
    await expect(apply).toBeDisabled();
    await expectInlineControlError(
      page,
      incomeDecision,
      'Decide qué hacer con el ingreso "Hosting agosto".',
    );
    await expectInlineControlError(
      page,
      note,
      'Escribe una nota porque la baja omite el paso previo por Suspendido.',
    );
    await expect(page.getByTestId('base-modal-actions').getByRole('alert')).toHaveCount(0);

    await incomeDecision.selectOption('keep_receivable');
    await expect(incomeDecision).not.toHaveAttribute('aria-invalid', 'true');
    await expect(apply).toBeDisabled();
    await note.fill('Baja directa confirmada.');
    await expect(note).not.toHaveAttribute('aria-invalid', 'true');
    await expect(apply).toBeEnabled();
  });

  test('keeps the transition open when its impact preview became stale', {
    tag: [...ADMIN_PROJECT_LIFECYCLE_STATES, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'projects/9/state-transitions/preview/' && method === 'POST') {
        return json({
          target_effect: 'suspended',
          impact_token: 'c'.repeat(64),
          effective_at: '2026-08-26T10:00:00Z',
          pending_incomes: [],
          future_incomes: [],
          future_payments: [],
          active_hostings: [],
          blockers: [],
        });
      }
      if (apiPath === 'projects/9/state-transitions/' && method === 'POST') {
        return json({
          detail: 'Los cobros cambiaron. Revisa de nuevo las consecuencias.',
          code: 'stale_transition_preview',
        }, 409);
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openProjects(page);
    await openStateTransition(page);
    await page.getByTestId('project-state-target').selectOption('4');
    await page.getByTestId('project-state-preview').click();
    await page.getByTestId('project-state-apply').click();

    await expect(page.getByTestId('project-state-error')).toContainText(
      'Los cobros cambiaron',
    );
    await expect(page.getByTestId('project-state-transition-modal')).toBeVisible();
    await expect(page.getByTestId('accounting-row-9')).toContainText('Activo');
  });

  test('keeps state-change steps in reading order', {
    tag: [
      ...ADMIN_PROJECT_LIFECYCLE_STATES,
      '@role:admin',
      '@outcome:display',
      '@responsive:projects',
    ],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'projects/9/state-transitions/preview/' && method === 'POST') {
        return json({
          target_effect: 'decommissioned',
          impact_token: 'd'.repeat(64),
          effective_at: '2026-08-26T10:00:00Z',
          pending_incomes: [{
            id: 41,
            concept: 'Hosting agosto',
            pending_amount: '120000.00',
          }],
          future_incomes: [],
          future_payments: [],
          active_hostings: [],
          blockers: [],
        });
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openProjects(page);
    await openStateTransition(page);
    await page.getByTestId('project-state-target').selectOption('6');
    await page.getByTestId('project-state-preview').click();

    const modal = page.getByRole('dialog').filter({ has: page.getByTestId('project-state-transition-modal') });
    const orderedTestIds = await modal.evaluate((root) => [
      'project-state-target',
      'project-state-review-step',
      'project-state-impact',
      'base-modal-actions',
    ].filter((testId) => root.querySelector(`[data-testid="${testId}"]`))
      .sort((first, second) => {
        const firstNode = root.querySelector(`[data-testid="${first}"]`);
        const secondNode = root.querySelector(`[data-testid="${second}"]`);
        return firstNode.compareDocumentPosition(secondNode)
          & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
      }));

    expect(orderedTestIds).toEqual([
      'project-state-target',
      'project-state-review-step',
      'project-state-impact',
      'base-modal-actions',
    ]);
    const actions = page.getByTestId('base-modal-actions');
    await actions.scrollIntoViewIfNeeded();
    await expect(actions.getByRole('button')).toHaveCount(2);
    await expect(actions.getByRole('alert')).toHaveCount(0);
    await expectNoViewportOverflow(page);
  });
});

test.describe('Admin project state catalog', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('shows only the six seeded meanings', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => (
      baseRoutes(apiPath, method, catalog, currentState)
    ));

    await openCatalog(page);

    await expect(page.getByTestId('catalog-state-1')).toContainText('En desarrollo');
    await expect(page.getByTestId('catalog-state-7')).toContainText('En evolución');
    await expect(page.getByTestId('catalog-state-4')).toContainText('Suspendido');
    await expect(page.getByTestId('catalog-state-3')).toHaveCount(0);
    await expect(page.getByTestId('catalog-state-5')).toContainText('Completado');
    await expect(page.getByTestId('catalog-state-6')).toContainText('Dado de baja');
    await expect(page.getByTestId('catalog-state-2')).toContainText('1 proyectos activos · 3 episodios');
  });

  test('places missing creation requirements beside their fields', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    let createCalls = 0;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'project-states/' && method === 'POST') {
        createCalls += 1;
        return json({}, 201);
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);
    await page.getByTestId('catalog-create-state').click();

    const name = page.getByTestId('catalog-new-state-name');
    const description = page.getByTestId('catalog-new-state-description');
    await expect(name).toHaveAttribute('aria-invalid', 'true');
    await expect(description).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByText('Escribe el nombre del estado.', { exact: true }))
      .toBeVisible();
    await expect(page.getByText('Explica qué significa el estado.', { exact: true }))
      .toBeVisible();
    expect(createCalls).toBe(0);
  });

  test('places a missing merge target beside its selector', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    let mergeCalls = 0;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'project-states/8/merge/' && method === 'POST') {
        mergeCalls += 1;
        return json(catalog.find((state) => state.id === 8));
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);
    const row = page.getByTestId('catalog-state-8');
    await row.getByTestId('catalog-merge-state-8').click();

    const target = row.getByLabel('Destino para fusionar En garantía');
    await expect(target).toHaveAttribute('aria-invalid', 'true');
    await expect(row.getByText('Elige el estado de destino.', { exact: true }))
      .toBeVisible();
    expect(mergeCalls).toBe(0);

    await target.selectOption('2');
    await expect(row.getByText('Elige el estado de destino.', { exact: true }))
      .toHaveCount(0);
  });

  test('creates a reusable state with an explicit operational effect', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    let createBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'project-states/' && method === 'POST') {
        createBody = route.request().postDataJSON();
        const created = projectState(
          9,
          createBody.name,
          '',
          createBody.operational_effect,
          createBody.color,
          { description: createBody.description },
        );
        catalog.push(created);
        return json(created, 201);
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);
    await page.getByTestId('catalog-new-state-name').fill('En estabilización');
    await page.getByTestId('catalog-new-state-description').fill(
      'El proyecto opera mientras se estabiliza la entrega.',
    );
    await page.getByLabel('Efecto operativo del nuevo estado').selectOption('operating');
    await page.getByLabel('Color del nuevo estado').selectOption('purple');
    await page.getByTestId('catalog-create-state').click();

    await expect.poll(() => createBody).not.toBeNull();
    expect(createBody).toMatchObject({
      name: 'En estabilización',
      description: 'El proyecto opera mientras se estabiliza la entrega.',
      operational_effect: 'operating',
      color: 'purple',
    });
    await expect(page.getByTestId('catalog-state-9')).toContainText('En estabilización');
  });

  test('renames a state without changing its business effect', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    let updateBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'project-states/8/' && method === 'PATCH') {
        updateBody = route.request().postDataJSON();
        Object.assign(catalog.find((state) => state.id === 8), updateBody);
        return json(catalog.find((state) => state.id === 8));
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);
    const row = page.getByTestId('catalog-state-8');
    await row.getByLabel('Nombre del estado').fill('Garantía activa');
    await page.getByTestId('catalog-state-description-8').fill(
      'Acompañamiento activo posterior a la entrega.',
    );
    await page.getByTestId('catalog-save-state-8').click();

    await expect.poll(() => updateBody).not.toBeNull();
    expect(updateBody.operational_effect).toBe('operating');
    expect(updateBody.description).toBe(
      'Acompañamiento activo posterior a la entrega.',
    );
    await expect(page.getByTestId('catalog-state-8')).toContainText('Garantía activa');
  });

  test('keeps document inclusion out of the lifecycle-state form', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);

    await expect(page.getByTestId('catalog-state-8')).toContainText('En garantía');
    await expect(page.getByTestId('catalog-state-document-visibility-8')).toHaveCount(0);
    await expect(page.getByText('Mostrar sus proyectos en Documentos')).toHaveCount(0);
  });

  test('retires an unused custom state while keeping it in the catalog history', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'project-states/8/retire/' && method === 'POST') {
        const retired = catalog.find((state) => state.id === 8);
        retired.is_active = false;
        return json(retired);
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);
    await page.getByTestId('catalog-retire-state-8').click();
    await expect(page.getByRole('dialog')).toContainText('“En garantía” dejará de aparecer');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByRole('alert')).toContainText('Estado retirado');
    await expect(page.getByTestId('catalog-state-8')).toContainText('Retirado');
  });

  test('rejects retiring a state that still has active projects', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'project-states/2/retire/' && method === 'POST') {
        return json({
          detail: 'Mueve primero los proyectos que todavía usan este estado.',
          code: 'state_in_use',
        }, 409);
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);
    await page.getByTestId('catalog-retire-state-2').click();
    await expect(page.getByRole('dialog')).toContainText('“Activo” dejará de aparecer');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByRole('alert')).toContainText('No se puede retirar');
    await expect(page.getByRole('alert')).toContainText('Mueve primero los proyectos');
    await expect(page.getByTestId('catalog-state-2')).toContainText('Activo');
  });

  test('keeps the edited name when the catalog server fails', {
    tag: [...ADMIN_PROJECT_STATE_CATALOG, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const catalog = initialCatalog();
    const currentState = catalog[1];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'project-states/8/' && method === 'PATCH') {
        return json({ detail: 'El catálogo no está disponible.' }, 503);
      }
      return baseRoutes(apiPath, method, catalog, currentState);
    });

    await openCatalog(page);
    const name = page.getByTestId('catalog-state-8').getByLabel('Nombre del estado');
    await name.fill('Garantía hoy');
    await page.getByTestId('catalog-save-state-8').click();

    await expect(page.getByRole('alert')).toContainText('No se pudo actualizar');
    await expect(name).toHaveValue('Garantía hoy');
  });
});

function expectCommonActionLayout({
  editBandBox,
  maintenanceBandBox,
  mergeBox,
  retireBox,
}) {
  expect(verticalGap(editBandBox, maintenanceBandBox)).toBeGreaterThanOrEqual(8);
  expect(Math.abs(mergeBox.width - retireBox.width)).toBeLessThanOrEqual(1);
  expect(Math.abs(mergeBox.height - retireBox.height)).toBeLessThanOrEqual(1);
}

function expectCompactActionLayout(boxes) {
  expectCommonActionLayout(boxes);
  expect(Math.abs(boxes.saveBox.width - boxes.editBandBox.width)).toBeLessThanOrEqual(1);
  expect(Math.abs(boxes.mergeBox.width - boxes.maintenanceBandBox.width)).toBeLessThanOrEqual(1);
  expect(Math.abs(boxes.retireBox.width - boxes.maintenanceBandBox.width)).toBeLessThanOrEqual(1);
  expect(verticalGap(boxes.targetBox, boxes.mergeBox)).toBeGreaterThanOrEqual(8);
  expect(verticalGap(boxes.mergeBox, boxes.retireBox)).toBeGreaterThanOrEqual(8);
}

function expectPortraitActionLayout(boxes) {
  expectCommonActionLayout(boxes);
  expect(Math.abs(boxes.saveBox.width - boxes.editBandBox.width)).toBeLessThanOrEqual(1);
  expect(horizontalGap(boxes.targetBox, boxes.mergeBox)).toBeGreaterThanOrEqual(8);
  expect(horizontalGap(boxes.mergeBox, boxes.retireBox)).toBeGreaterThanOrEqual(8);
}

function expectExpandedActionLayout(boxes) {
  expectCommonActionLayout(boxes);
  expect(horizontalGap(boxes.targetBox, boxes.mergeBox)).toBeGreaterThanOrEqual(8);
  expect(horizontalGap(boxes.mergeBox, boxes.retireBox)).toBeGreaterThanOrEqual(8);
  expect(Math.abs(boxes.saveBox.width - boxes.mergeBox.width)).toBeLessThanOrEqual(1);
}

const CATALOG_LAYOUT_VIEWPORTS = [
  ['compact', 'celular', expectCompactActionLayout],
  ['portrait', 'tableta vertical', expectPortraitActionLayout],
  ['landscape', 'tableta horizontal', expectExpandedActionLayout],
  ['desktop', 'portátil', expectExpandedActionLayout],
  ['wide', 'monitor', expectExpandedActionLayout],
];

for (const [viewport, label, expectLayout] of CATALOG_LAYOUT_VIEWPORTS) {
  test.describe(`Catálogo de estados — acciones en ${label}`, () => {
    test.use(viewportUse(viewport));

    test.beforeEach(async ({ page }) => {
      await setAuthLocalStorage(page, {
        token: 'e2e-token',
        userAuth: { id: 9001, role: 'admin', is_staff: true },
      });
    });

    test(`mantiene proporcionales las acciones en ${label}`, {
      tag: [
        ...ADMIN_PROJECT_STATE_CATALOG,
        '@role:admin',
        '@outcome:display',
        '@responsive:projects',
      ],
    }, async ({ page }) => {
      const catalog = initialCatalog();
      const currentState = catalog[1];
      await mockApi(page, async ({ apiPath, method }) => (
        baseRoutes(apiPath, method, catalog, currentState)
      ));

      await openCatalog(page);
      const row = page.getByTestId('catalog-state-8');
      await row.scrollIntoViewIfNeeded();

      const editBand = row.getByTestId('catalog-state-edit-actions-8');
      const maintenanceBand = row.getByTestId('catalog-state-maintenance-actions-8');
      const save = row.getByTestId('catalog-save-state-8');
      const target = row.getByLabel('Destino para fusionar En garantía');
      const merge = row.getByTestId('catalog-merge-state-8');
      const retire = row.getByTestId('catalog-retire-state-8');
      const [
        editBandBox,
        maintenanceBandBox,
        saveBox,
        targetBox,
        mergeBox,
        retireBox,
      ] = await Promise.all([
        visibleBox(editBand),
        visibleBox(maintenanceBand),
        visibleBox(save),
        visibleBox(target),
        visibleBox(merge),
        visibleBox(retire),
      ]);

      expectLayout({
        editBandBox,
        maintenanceBandBox,
        saveBox,
        targetBox,
        mergeBox,
        retireBox,
      });

      await expectNoViewportOverflow(page);
    });
  });
}
