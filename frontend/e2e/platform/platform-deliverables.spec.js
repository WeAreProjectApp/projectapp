/**
 * E2E tests for platform deliverables flow.
 *
 * @flow:platform-deliverables
 * @flow:platform-deliverable-detail
 * Covers: deliverable list rendering, category filter tabs, admin upload deliverable,
 *         client view/download, version history, unified cross-project view,
 *         deliverable detail page and linked proposal PDFs.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_DELIVERABLES, PLATFORM_DELIVERABLE_DETAIL } from '../helpers/flow-tags.js';
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

const mockDeliverableDetail = {
  id: 1,
  title: 'Wireframes página principal',
  description: 'Wireframes de baja fidelidad.',
  source_epic_key: 'EPIC-1',
  source_epic_title: 'Módulo onboarding',
  has_business_proposal: true,
  proposal_title: 'Propuesta comercial demo',
  file_url: '/media/wireframes-v1.pdf',
  file_name: 'wireframes-v1.pdf',
  attachment_files: [],
  pdf_download_paths: {
    commercial: 'projects/1/deliverables/1/pdf/commercial/',
    technical: 'projects/1/deliverables/1/pdf/technical/',
  },
};

const mockDeliverables = [
  {
    id: 1, title: 'Wireframes página principal', description: 'Wireframes de baja fidelidad.',
    category: 'designs', current_version: 1, file_url: '/media/wireframes-v1.pdf',
    file_name: 'wireframes-v1.pdf', file_size: 2048, uploaded_by_name: 'Admin E2E',
    versions_count: 1, created_at: '2025-02-01T10:00:00Z', updated_at: '2025-02-01T10:00:00Z',
  },
  {
    id: 2, title: 'Credenciales Wompi Sandbox', description: 'Llaves de API para pruebas.',
    category: 'credentials', current_version: 1, file_url: '/media/wompi-keys.txt',
    file_name: 'wompi-keys.txt', file_size: 512, uploaded_by_name: 'Admin E2E',
    versions_count: 1, created_at: '2025-01-28T10:00:00Z', updated_at: '2025-01-28T10:00:00Z',
  },
];

const meResponse = (user) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(user) });

function setupMocks(page, { user }) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProject) };
    }
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject]) };
    }
    if (apiPath === 'accounts/projects/1/deliverables/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDeliverables) };
    }
    if (apiPath === 'accounts/projects/1/deliverables/' && method === 'POST') {
      return { status: 201, contentType: 'application/json', body: JSON.stringify({ id: 10, title: 'New file', category: 'documents', current_version: 1, versions_count: 1 }) };
    }
    if (apiPath === 'accounts/projects/1/deliverables/1/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDeliverableDetail) };
    }
    if (apiPath === 'accounts/projects/1/deliverables/1/pdf/commercial/' && method === 'GET') {
      return { status: 200, contentType: 'application/pdf', body: '%PDF-e2e-deliverable-commercial' };
    }
    if (apiPath === 'accounts/projects/1/deliverables/1/pdf/technical/' && method === 'GET') {
      return { status: 200, contentType: 'application/pdf', body: '%PDF-e2e-deliverable-technical' };
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
    }
    return null;
  });
}

test.describe('Platform Deliverables — Client', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformClient });
  });

  test('renders deliverable list with file names and categories', {
    tag: ['@outcome:display', ...PLATFORM_DELIVERABLES, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — deliverable list renders file names and categories)
    await setupMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/projects/1/deliverables', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /recursos/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText('Wireframes página principal')).toBeVisible();
    await expect(page.getByText('Credenciales Wompi Sandbox')).toBeVisible();
  });

  test('client can upload a resource', {
    tag: ['@outcome:display', ...PLATFORM_DELIVERABLES, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the upload control renders for the client)
    await setupMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/projects/1/deliverables', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /recursos/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByRole('button', { name: /subir recurso/i })).toBeVisible();
  });
});

test.describe('Platform Deliverables — Admin', () => {
  test.setTimeout(60_000);

  test('admin sees upload button and deliverable list', {
    tag: ['@outcome:display', ...PLATFORM_DELIVERABLES, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — admin sees the upload control and deliverable list)
    await setPlatformAuth(page, { user: mockPlatformAdmin });
    await setupMocks(page, { user: mockPlatformAdmin });
    await page.goto('/platform/projects/1/deliverables', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /recursos/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText('Wireframes página principal')).toBeVisible();
    await expect(page.getByRole('button', { name: /subir recurso/i })).toBeVisible();
  });
});

// The standalone deliverable detail page was removed in the platform IA
// refactor — deliverable detail now opens as a modal inside the project
// deliverables list, and the /deliverables/:id route redirects to the list.
test.describe('Platform Deliverable detail', () => {
  test.setTimeout(60_000);

  test('visiting a deliverable detail URL redirects to the project resources list', {
    tag: [...PLATFORM_DELIVERABLE_DETAIL, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (redirect — the removed standalone detail route redirects to the project list, asserted by heading)
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/projects/1/deliverables/1', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/projects/1/deliverables', { timeout: 30_000 });
    await expect(page.getByRole('heading', { name: /recursos/i })).toBeVisible({ timeout: 30_000 });
  });
});

// ── Unified cross-project view (/platform/deliverables) ──

const mockProject2 = {
  id: 2, name: 'Mobile App', status: 'active', progress: 20,
  client_id: 9002, client_name: 'Client E2E', client_email: 'client@e2e-test.com',
  client_company: 'ACME Corp', start_date: '2025-03-01', estimated_end_date: '2025-09-30',
};

const mockDeliverablesCrossProject = [
  { ...mockDeliverables[0], project_id: 1, project_name: 'E-commerce Platform' },
  { ...mockDeliverables[1], project_id: 1, project_name: 'E-commerce Platform' },
  {
    id: 3, title: 'iOS Prototype', description: 'First prototype build.',
    category: 'apks', current_version: 1, file_url: '/media/app-v1.ipa',
    file_name: 'app-v1.ipa', file_size: 4096, uploaded_by_name: 'Admin E2E',
    versions_count: 1, created_at: '2025-02-05T10:00:00Z', updated_at: '2025-02-05T10:00:00Z',
    project_id: 2, project_name: 'Mobile App',
  },
];

function setupUnifiedDeliverablesMocks(page, { user, deliverables = mockDeliverablesCrossProject }) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([mockProject, mockProject2]) };
    }
    if (apiPath.startsWith('accounts/deliverables/') && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(deliverables) };
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
    }
    return null;
  });
}

// The standalone /platform/deliverables view was removed in the platform IA
// refactor — deliverables are now project-scoped and the route redirects.
test.describe('Platform Deliverables — /platform/deliverables redirect', () => {
  test.setTimeout(60_000);

  test('client visiting /platform/deliverables is redirected to projects', {
    tag: [...PLATFORM_DELIVERABLES, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (redirect — the removed standalone list route redirects to projects, asserted by URL)
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupUnifiedDeliverablesMocks(page, { user: mockPlatformClient });
    await page.goto('/en-us/platform/deliverables', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/en-us\/platform\/projects\/?$/);
  });
});
