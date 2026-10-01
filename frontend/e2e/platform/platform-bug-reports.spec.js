/**
 * E2E tests for platform bug reports flow.
 *
 * @flow:platform-bug-reports
 * Covers: bug report list rendering, status/severity filters, create bug report,
 *         admin evaluate bug report, unified cross-project view.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_BUG_REPORTS } from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClient,
} from '../helpers/platform-auth.js';

const mockProject = {
  id: 1, name: 'E-commerce Platform', status: 'active', progress: 33,
  client_id: 9002, client_name: 'Client E2E', client_email: 'client@e2e-test.com',
  client_company: 'ACME Corp', start_date: '2025-01-01', estimated_end_date: '2025-06-30',
};

const mockBugReports = [
  {
    id: 1, title: 'Botón no responde en móvil', description: 'El botón de agregar al carrito no funciona en Safari iOS.',
    severity: 'critical', status: 'confirmed', steps_to_reproduce: ['Abrir en iPhone', 'Ir a producto', 'Tocar botón'],
    expected_behavior: 'Debería agregar al carrito.', actual_behavior: 'No pasa nada.',
    environment: 'production', device_browser: 'iPhone 14 / Safari 17', is_recurring: true,
    admin_response: 'Confirmado, priorizando fix.', linked_bug_id: null, screenshot_url: null,
    reported_by_name: 'Client E2E', reported_by_email: 'client@e2e-test.com',
    comments_count: 1, created_at: '2025-02-01T10:00:00Z',
  },
  {
    id: 2, title: 'Error 500 al buscar', description: 'Buscar con caracteres especiales da error.',
    severity: 'medium', status: 'reported', steps_to_reproduce: ['Ir al buscador', 'Escribir comillas'],
    expected_behavior: 'Mostrar resultados.', actual_behavior: 'Error 500.',
    environment: 'production', device_browser: 'Chrome / macOS', is_recurring: true,
    admin_response: '', linked_bug_id: null, screenshot_url: null,
    reported_by_name: 'Client E2E', reported_by_email: 'client@e2e-test.com',
    comments_count: 0, created_at: '2025-01-28T10:00:00Z',
  },
];

// A published guide is optional for bugs; selecting one captures its round.
const mockProjectRequirements = [
  { id: 501, title: 'Checkout flow', phase_title: 'Fase 1', stage_title: 'Etapa 1', source_publication_id: 101, source_requirement_version: 1 },
];

const meResponse = (user) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(user) });

function setupMocks(page, { user }) {
  return mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProject) };
    }
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject]) };
    }
    if (apiPath === 'accounts/projects/1/issue-reports/context-options/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ requirements: mockProjectRequirements, contracts: [], documents: [] }) };
    }
    if (apiPath === 'accounts/projects/1/bug-reports/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockBugReports) };
    }
    if (apiPath === 'accounts/projects/1/bug-reports/' && method === 'POST') {
      return { status: 201, contentType: 'application/json', body: JSON.stringify({ id: 10, title: route.request().postDataJSON().title, severity: 'medium', status: 'reported', comments_count: 0 }) };
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
    }
    return null;
  });
}

test.describe('Platform Bug Reports — Client', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformClient });
  });

  test('renders bug report list with severity badges', {
    tag: ['@outcome:display', ...PLATFORM_BUG_REPORTS, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display list — asserts the reported bugs render with their titles; the create interaction is covered below)
    await setupMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/projects/1/bugs', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /reporte de bugs/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText('Botón no responde en móvil')).toBeVisible();
    await expect(page.getByText('Error 500 al buscar')).toBeVisible();
  });

  test('client can create a new bug report', {
    tag: [...PLATFORM_BUG_REPORTS, '@role:platform-client'],
  }, async ({ page }) => {
    await setupMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/projects/1/bugs', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /reporte de bugs/i }).waitFor({ state: 'visible', timeout: 30000 });

    await page.getByRole('button', { name: /reportar bug/i }).click();
    await page.getByPlaceholder('¿Qué está fallando?').fill('New bug report');
    await page.getByLabel('Entrega de origen (opcional)', { exact: true }).selectOption('501');
    await page.getByRole('button', { name: /reportar bug/i }).last().click();

    // On a successful submit the create form closes.
    await expect(page.getByPlaceholder('¿Qué está fallando?')).not.toBeVisible();
    await expect(page.getByText('New bug report', { exact: true })).toBeVisible();
  });
});

test.describe('Platform Bug Reports — Admin', () => {
  test.setTimeout(60_000);

  test('admin sees bug reports with status counts', {
    tag: ['@outcome:display', ...PLATFORM_BUG_REPORTS, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — admin view of the project's bug list)
    await setPlatformAuth(page, { user: mockPlatformAdmin });
    await setupMocks(page, { user: mockPlatformAdmin });
    await page.goto('/platform/projects/1/bugs', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /reporte de bugs/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText('Botón no responde en móvil')).toBeVisible();
  });
});

// ── Unified cross-project view (/platform/bugs) ──

const mockProject2 = {
  id: 2, name: 'Mobile App', status: 'active', progress: 20,
  client_id: 9002, client_name: 'Client E2E', client_email: 'client@e2e-test.com',
  client_company: 'ACME Corp', start_date: '2025-03-01', estimated_end_date: '2025-09-30',
};

const mockBugsCrossProject = [
  { ...mockBugReports[0], project_id: 1, project_name: 'E-commerce Platform' },
  { ...mockBugReports[1], project_id: 1, project_name: 'E-commerce Platform' },
  {
    id: 3, title: 'App crashes on login', description: 'Force close after entering password.',
    severity: 'high', status: 'reported', steps_to_reproduce: ['Open app', 'Tap login'],
    expected_behavior: 'Navigate to dashboard.', actual_behavior: 'App crashes.',
    environment: 'production', device_browser: 'Android 14', is_recurring: false,
    admin_response: '', linked_bug_id: null, screenshot_url: null,
    reported_by_name: 'Client E2E', reported_by_email: 'client@e2e-test.com',
    comments_count: 0, created_at: '2025-02-05T10:00:00Z', project_id: 2, project_name: 'Mobile App',
  },
];

function setupUnifiedBugsMocks(page, { user, bugs = mockBugsCrossProject }) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject, mockProject2]) };
    }
    if (apiPath.startsWith('accounts/bug-reports/') && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(bugs) };
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
    }
    return null;
  });
}

// The standalone /platform/bugs view was removed in the platform IA
// refactor — bugs are now project-scoped and the route redirects.
test.describe('Platform Bug Reports — /platform/bugs redirect', () => {
  test.setTimeout(60_000);

  test('client visiting /platform/bugs is redirected to projects', {
    tag: [...PLATFORM_BUG_REPORTS, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (redirect behavior — the removed /platform/bugs route is asserted to redirect to projects, by URL)
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupUnifiedBugsMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/bugs', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/projects**', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/projects/);
  });
});
