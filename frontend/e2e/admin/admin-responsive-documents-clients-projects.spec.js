/**
 * Responsive Phase 3 acceptance script.
 *
 * The same user-facing checks run at the five real device sizes agreed for
 * ProjectApp: phone, portrait tablet, landscape tablet, laptop and 27-inch
 * monitor. Each flow enters through panel navigation and asserts fixture data,
 * so this is a behavior check rather than a screenshot-only breakpoint test.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { PANEL_BREAKPOINTS, PANEL_VIEWPORTS } from '../../config/responsive.js';
import { viewportUse } from '../helpers/viewports.js';
import {
  ADMIN_CLIENTS_FILTER_PRESETS,
  ADMIN_DOCUMENT_LIST,
  ADMIN_PANEL_PROJECTS,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const VIEWPORTS = [
  { alias: 'compact', label: 'celular', ...PANEL_VIEWPORTS.compact, compact: true, phone: true },
  { alias: 'portrait', label: 'tableta vertical', ...PANEL_VIEWPORTS.portrait, compact: true, phone: false },
  { alias: 'landscape', label: 'tableta horizontal', ...PANEL_VIEWPORTS.landscape, compact: false, phone: false },
  { alias: 'desktop', label: 'portátil', ...PANEL_VIEWPORTS.desktop, compact: false, phone: false },
  { alias: 'wide', label: 'monitor 27 pulgadas', ...PANEL_VIEWPORTS.wide, compact: false, phone: false },
];

const jsonOk = (body) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const authCheck = jsonOk({
  user: { username: 'admin', is_staff: true, is_superuser: true },
});

const NEEDS_FIX_STATE = {
  id: 11,
  name: 'Solucionar bug',
  color: 'red',
  system_key: 'needs_fix',
  group_mode: 'additive',
  group_order: 1,
  order: 0,
};

async function enterModule(page, linkName, heading) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  const link = page.getByRole('link', { name: linkName, exact: true });
  await expect(link).toBeVisible({ timeout: 25_000 });
  await link.click();
  await expect(page.getByRole('heading', { name: heading, exact: true }))
    .toBeVisible({ timeout: 30_000 });
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

function rectanglesOverlap(first, second) {
  return Math.min(first.x + first.width, second.x + second.width) > Math.max(first.x, second.x)
    && Math.min(first.y + first.height, second.y + second.height) > Math.max(first.y, second.y);
}

async function expectIndicatorHelpContained(page, cardTestId, helpTestId) {
  const card = page.getByTestId(cardTestId);
  const help = page.getByTestId(helpTestId);

  await expect(help).toBeVisible();

  const [cardBox, helpBox] = await Promise.all([
    card.boundingBox(),
    help.boundingBox(),
  ]);

  expect(helpBox.x).toBeGreaterThanOrEqual(cardBox.x);
  expect(helpBox.y).toBeGreaterThanOrEqual(cardBox.y);
  expect(helpBox.x + helpBox.width).toBeLessThanOrEqual(cardBox.x + cardBox.width);
  expect(helpBox.y + helpBox.height).toBeLessThanOrEqual(cardBox.y + cardBox.height);

  return { card, helpBox, cardBox };
}

async function expectCompactIndicatorCardGeometry(page, cardTestId, helpTestId) {
  const { card, helpBox, cardBox } = await expectIndicatorHelpContained(
    page,
    cardTestId,
    helpTestId,
  );
  const label = card.getByTestId('indicator-label');
  const value = card.getByTestId('accounting-stat-value');
  const resultAction = card.getByTestId('indicator-result-action');

  await expect(card).toHaveAttribute('data-layout', 'compact-horizontal');

  const [labelBox, valueBox, resultActionBox] = await Promise.all([
    label.boundingBox(),
    value.boundingBox(),
    resultAction.boundingBox(),
  ]);

  expect(cardBox.height).toBeLessThanOrEqual(80);
  expect(rectanglesOverlap(helpBox, labelBox)).toBe(false);
  expect(rectanglesOverlap(helpBox, valueBox)).toBe(false);
  expect(rectanglesOverlap(helpBox, resultActionBox)).toBe(false);

  return cardBox;
}

async function expectExpandedProjectIndicatorParity(page) {
  const lifecycleBox = await expectCompactIndicatorCardGeometry(
    page,
    'panel-projects-stat-state-2',
    'project-stat-state-help-2',
  );
  const pendingCards = [
    ['panel-projects-stat-orphans', 'project-stat-orphans-help'],
    ['panel-projects-stat-unlinked', 'project-stat-unlinked-help'],
  ];

  for (const [cardTestId, helpTestId] of pendingCards) {
    const pendingBox = await expectCompactIndicatorCardGeometry(page, cardTestId, helpTestId);
    expect(Math.round(pendingBox.width)).toBe(Math.round(lifecycleBox.width));
    expect(Math.round(pendingBox.height)).toBe(Math.round(lifecycleBox.height));
  }
}

async function expectWidePageCap(page, testId, width) {
  if (width !== PANEL_VIEWPORTS.wide.width) return;
  const box = await page.getByTestId(testId).boundingBox();
  expect(box.width).toBeLessThanOrEqual(1401);
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, {
    token: 'responsive-phase-3-token',
    userAuth: { id: 9200, role: 'admin', is_staff: true, is_superuser: true },
  });
});

const DOCUMENT = {
  id: 501,
  title: 'Informe responsivo de agosto',
  status: 'published',
  is_archived: false,
  folder: null,
  folder_name: '',
  client: 101,
  client_display_name: 'Cliente Atlas Internacional',
  client_name: 'Cliente Atlas Internacional',
  project: 12,
  project_name: 'Proyecto Atlas',
  content_excerpt: 'Resumen operativo del documento.',
  tag_details: [{ id: 1, name: 'Entrega', color: 'green' }],
  active_states: [{
    id: 81,
    duration_seconds: 172800,
    opened_at: '2026-08-18T10:00:00Z',
    state: NEEDS_FIX_STATE,
  }],
  created_at: '2026-08-20T10:00:00Z',
};

const FOLDER = {
  id: 31,
  name: 'Futuros Requerimientos Internacionales',
  slug: 'futuros-requerimientos-internacionales',
  parent: null,
  order: 0,
  is_archived: false,
  archived_at: null,
  archived_cause: null,
  document_count: 1,
  active_document_count: 1,
  archived_document_count: 0,
  children_count: 0,
  active_children_count: 0,
  archived_children_count: 0,
};

async function mockDocuments(page) {
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'documents/') return jsonOk([DOCUMENT]);
    if (apiPath === 'documents/counts/') {
      return jsonOk({
        documents: { active: 1, archived: 0, unfiled_active: 1, unfiled_archived: 0 },
        folders: { active: 1, archived: 0 },
      });
    }
    if (apiPath === 'document-folders/') return jsonOk([FOLDER]);
    if (apiPath === 'document-tags/') return jsonOk([]);
    if (apiPath.startsWith('accounting/projects/')) return jsonOk({ results: [] });
    return null;
  });
}

test.describe('Documentos — matriz responsiva', () => {
  for (const viewport of VIEWPORTS) {
    test(`presenta el gestor responsivo en ${viewport.label} (${viewport.width}px)`, {
      tag: [...ADMIN_DOCUMENT_LIST, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await mockDocuments(page);
      await enterModule(page, 'Gestor Documental', 'Gestor Documental');

      if (viewport.compact) {
        await expect(page.getByTestId('folder-drawer-trigger')).toBeVisible();
        await expect(page.getByTestId('folder-panel')).toHaveCount(0);
        const card = page.getByTestId('document-card-501');
        await expect(card).toContainText('Informe responsivo de agosto');
        await expect(page.getByTestId('document-card-priority-row-501'))
          .toContainText('Solucionar bug');
        const secondaryMeta = await page.getByTestId('document-card-secondary-meta-501')
          .textContent();
        expect(secondaryMeta.indexOf('2026'))
          .toBeLessThan(secondaryMeta.indexOf('Cliente Atlas Internacional'));
        expect(secondaryMeta.indexOf('Cliente Atlas Internacional'))
          .toBeLessThan(secondaryMeta.indexOf('Proyecto Atlas'));

        await page.getByTestId('folder-drawer-trigger').click();
        const drawer = page.getByTestId('folder-drawer');
        await expect(drawer).toContainText('Futuros Requerimientos Internacionales');
        await drawer.getByRole('button', {
          name: /^Futuros Requerimientos Internacionales —/,
        }).click();
        await expect(drawer).toBeHidden();
      } else {
        await expect(page.getByTestId('folder-panel'))
          .toContainText('Futuros Requerimientos Internacionales');
        await expect(page.getByTestId('folder-drawer-trigger')).toHaveCount(0);
        await expect(page.getByTestId('document-row-501'))
          .toContainText('Informe responsivo de agosto');

        const headers = await page.getByRole('table').locator('thead th').allTextContents();
        expect(headers.map((label) => label.replace(/\s+/g, ' ').trim())).toEqual([
          '', 'Título', 'Estados', 'Creado', 'Cliente', 'Proyecto',
        ]);

        await expect(page.getByRole('columnheader', { name: 'Estados' })).toBeVisible();
        await expect(page.getByTestId('doc-states-cell-501')).toContainText('Solucionar bug');
        const clientHeader = page.getByRole('columnheader', { name: 'Cliente' });
        const projectHeader = page.getByRole('columnheader', { name: 'Proyecto' });
        if (viewport.width < PANEL_BREAKPOINTS.desktop) {
          await expect(clientHeader).toBeHidden();
          await expect(projectHeader).toBeHidden();
          await expect(page.getByTestId('document-title-meta-501'))
            .toContainText('Cliente Atlas Internacional');
          await expect(page.getByTestId('document-title-meta-501'))
            .toContainText('Proyecto Atlas');
        } else {
          await expect(clientHeader).toBeVisible();
          await expect(projectHeader).toBeVisible();
        }
      }

      await expectNoViewportOverflow(page);
      await expectWidePageCap(page, 'documents-page', viewport.width);
    });
  }
});

const CLIENT = {
  id: 101,
  user_id: 801,
  name: 'Alejandra de los Ángeles Torres',
  email: 'alejandra.torres@atlas-internacional.example',
  phone: '+57 300 111 2233',
  company: 'Atlas Internacional SAS',
  is_onboarded: true,
  is_email_placeholder: false,
  is_orphan: false,
  is_archived: false,
  total_proposals: 3,
  projects_count: 2,
  diagnostics_count: 1,
  incomes_count: 4,
  hostings_count: 2,
  active_hostings_count: 1,
  active_projects_count: 2,
  accepted_count: 1,
  last_status: 'accepted',
  last_sent_at: '2026-08-01T10:00:00Z',
  project_types: [],
  market_types: [],
  documents_count: 5,
  documents_no_project_count: 1,
  last_document_at: '2026-08-20T10:00:00Z',
  emails_sent_count: 6,
  emails_failed_count: 0,
  last_email_at: '2026-08-19T10:00:00Z',
  diagnostic_incomes_count: 0,
  diagnostics_without_proposal_count: 0,
  nit: '900123456',
  cedula: '',
  billing_code: 'ATLAS',
  created_at: '2026-01-01T10:00:00Z',
  updated_at: '2026-08-20T10:00:00Z',
};

async function mockClients(page) {
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return jsonOk([]);
    if (apiPath === 'proposals/client-profiles/status-counts/') {
      return jsonOk({ all: 1, active: 1, orphans: 0, archived: 0 });
    }
    if (apiPath === 'proposals/client-profiles/') return jsonOk([CLIENT]);
    if (apiPath === 'proposals/client-profiles/101/') {
      return jsonOk({
        ...CLIENT,
        proposals: [],
        projects: [],
        diagnostics: [],
        hostings: [],
        incomes: [],
        documents: [],
      });
    }
    return null;
  });
}

test.describe('Clientes — matriz responsiva', () => {
  for (const viewport of VIEWPORTS) {
    test(`presenta el registro responsivo en ${viewport.label} (${viewport.width}px)`, {
      tag: [...ADMIN_CLIENTS_FILTER_PRESETS, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await mockClients(page);
      await enterModule(page, 'Clientes', 'Clientes');

      const row = page.getByTestId('client-row-101');
      await expect(row).toContainText('Alejandra de los Ángeles Torres');
      await expect(row).toContainText('Atlas Internacional SAS');

      if (viewport.compact) {
        await expect(page.getByTestId('clients-status-selector')).toHaveCount(0);
        await page.getByTestId('clients-mobile-filters').click();
        await expect(page.getByTestId('clients-filters-drawer')).toBeVisible();
        await page.getByTestId('clients-module-selector-mobile').selectOption('documents');
        await page.getByTestId('clients-mobile-filter-results').click();

        await expect(row).toContainText('5 docs');
        await page.getByTestId('client-actions-101').click();
        const actions = page.getByTestId('client-actions-drawer');
        await expect(actions.getByRole('button', { name: 'Editar cliente' })).toBeVisible();
        await actions.getByRole('button', { name: 'Cerrar' }).click();
      } else {
        await expect(page.getByTestId('clients-status-selector')).toBeVisible();
        await expect(page.getByTestId('clients-mobile-filters')).toHaveCount(0);
        await page.getByTestId('clients-module-documents').click();
        await expect(page.getByTestId('client-documents-101')).toContainText('5 docs');
      }

      await expectNoViewportOverflow(page);
      await expectWidePageCap(page, 'clients-page', viewport.width);
    });
  }
});

const PROJECT = {
  id: 12,
  name: 'Plataforma Atlas Internacional',
  description: 'Operación comercial y contable',
  status: 'active',
  status_label: 'Activo',
  current_state: {
    id: 2,
    name: 'Activo',
    system_key: 'active',
    operational_effect: 'operating',
    color: 'emerald',
  },
  created_at: '2026-08-01T10:00:00Z',
  client: {
    profile_id: 101,
    name: 'Alejandra de los Ángeles Torres',
    company: 'Atlas Internacional SAS',
  },
  hostings_count: 2,
  incomes_count: 4,
  unlinked_hostings_count: 1,
  unlinked_incomes_count: 1,
  unlinked_documents_count: 1,
};

async function mockProjects(page) {
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath.startsWith('projects/') && method === 'GET') {
      return jsonOk({
        results: [PROJECT],
        meta: {
          total: 1,
          by_state: [{
            state_id: 2,
            name: 'Activo',
            color: 'emerald',
            operational_effect: 'operating',
            count: 1,
          }],
          review_required: 0,
          clients_without_projects: 3,
          records_without_project: 3,
        },
      });
    }
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return jsonOk([]);
    return null;
  });
}

async function enterCompactProjectsModule(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Abrir menú' }).click();
  const link = page.getByRole('link', { name: 'Proyectos', exact: true });
  await expect(link).toBeVisible({ timeout: 25_000 });
  await link.click();
  await expect(page.getByRole('heading', { name: 'Proyectos', exact: true }))
    .toBeVisible({ timeout: 30_000 });
}

async function enterExpandedProjectsModule(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  const link = page.getByRole('link', { name: 'Proyectos', exact: true });
  await expect(link).toBeVisible({ timeout: 25_000 });
  await link.click();
  await expect(page.getByRole('heading', { name: 'Proyectos', exact: true }))
    .toBeVisible({ timeout: 30_000 });
}

const COMPACT_PROJECT_VIEWPORTS = [
  { alias: 'compact', label: 'celular', width: 412 },
  { alias: 'portrait', label: 'tableta vertical', width: 835 },
];

const EXPANDED_PROJECT_VIEWPORTS = [
  { alias: 'landscape', label: 'tableta horizontal', width: 1195 },
  { alias: 'desktop', label: 'portátil', width: 1440 },
];

for (const viewport of COMPACT_PROJECT_VIEWPORTS) {
  test.describe(`Proyectos — contrato compacto en ${viewport.label}`, () => {
    test.use(viewportUse(viewport.alias));

    test(`presenta el módulo responsivo en ${viewport.label} (${viewport.width}px)`, {
      tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display', '@responsive:projects'],
    }, async ({ page }) => {
      await mockProjects(page);
      await enterCompactProjectsModule(page);

      const cards = page.getByTestId('projects-indicators-compact').locator('article');
      await expect(cards).toHaveCount(2);
      await expect(page.getByTestId('projects-card-list')).toBeVisible();
      await expect(page.getByTestId('accounting-row-12')).toHaveCount(0);
      await expect(page.getByTestId('project-card-12'))
        .toContainText('Plataforma Atlas Internacional');
      await expect(page.getByTestId('projects-state-filter')).toBeVisible();
      await expect(page.getByTestId('panel-projects-stat-states-summary')).toContainText('1');

      const firstCard = await cards.first().boundingBox();
      const secondCard = await cards.nth(1).boundingBox();
      expect(Math.round(firstCard.height)).toBe(Math.round(secondCard.height));
      await expectIndicatorHelpContained(
        page,
        'panel-projects-stat-states-summary',
        'project-states-summary-help',
      );
      await expectIndicatorHelpContained(
        page,
        'panel-projects-stat-pending-summary',
        'project-pending-summary-help',
      );
      await page.getByTestId('project-pending-summary-help').click();
      await expect(page.getByTestId('project-pending-summary-help-content')).toBeVisible();
      await expect(page.getByTestId('project-pending-indicator-drawer')).toHaveCount(0);

      await page.getByTestId('project-actions-12').click();
      const actions = page.getByTestId('project-actions-modal');
      await expect(actions.getByTestId('project-actions-edit')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(actions).toHaveCount(0);
      await expectNoViewportOverflow(page);
    });
  });
}

for (const viewport of EXPANDED_PROJECT_VIEWPORTS) {
  test.describe(`Proyectos — contrato expandido en ${viewport.label}`, () => {
    test.use(viewportUse(viewport.alias));

    test(`presenta el módulo responsivo en ${viewport.label} (${viewport.width}px)`, {
      tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display', '@responsive:projects'],
    }, async ({ page }) => {
      await mockProjects(page);
      await enterExpandedProjectsModule(page);

      const cards = page.locator('[aria-label="Indicadores de proyectos"] article');
      await expect(cards).toHaveCount(3);
      await expect(page.getByTestId('accounting-row-12'))
        .toContainText('Plataforma Atlas Internacional');
      await expect(page.getByTestId('projects-card-list')).toHaveCount(0);
      await expect(page.getByTestId('projects-state-filter')).toBeVisible();
      await expect(page.getByTestId('panel-projects-stat-state-2')).toContainText('Activo');
      await expect(page.getByTestId('panel-projects-stat-orphans')).toContainText('3');
      await expect(page.getByTestId('panel-projects-stat-unlinked')).toContainText('3');

      const card = await cards.first().boundingBox();
      expect(Math.round(card.height)).toBeGreaterThan(0);
      await expectExpandedProjectIndicatorParity(page);
      await expectNoViewportOverflow(page);
    });
  });
}

test.describe('Proyectos — contrato expandido de monitor', () => {
  test.use(viewportUse('wide'));

  test('presenta el módulo responsivo en monitor 27 pulgadas (2560px)', {
    tag: [...ADMIN_PANEL_PROJECTS, '@role:admin', '@outcome:display', '@responsive:projects'],
  }, async ({ page }) => {
    await mockProjects(page);
    await enterExpandedProjectsModule(page);

    const cards = page.locator('[aria-label="Indicadores de proyectos"] article');
    await expect(cards).toHaveCount(3);
    await expect(page.getByTestId('accounting-row-12'))
      .toContainText('Plataforma Atlas Internacional');
    await expect(page.getByTestId('projects-card-list')).toHaveCount(0);
    await expect(page.getByTestId('projects-state-filter')).toBeVisible();
    await expect(page.getByTestId('panel-projects-stat-state-2')).toContainText('Activo');
    await expect(page.getByTestId('panel-projects-stat-orphans')).toContainText('3');
    await expect(page.getByTestId('panel-projects-stat-unlinked')).toContainText('3');

    const card = await cards.first().boundingBox();
    const pageBox = await page.getByTestId('projects-page').boundingBox();
    expect(Math.round(card.height)).toBeGreaterThan(0);
    await expectExpandedProjectIndicatorParity(page);
    expect(pageBox.width).toBeLessThanOrEqual(1401);
    await expectNoViewportOverflow(page);
  });
});
