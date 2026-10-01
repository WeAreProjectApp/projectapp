/**
 * E2E tests for platform project detail flow.
 *
 * @flow:platform-project-detail
 * Covers: project detail render with stats, module cards,
 *         back link to projects, edit modal (admin),
 *         not found state, board link navigation.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_PROJECT_DETAIL } from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClient,
} from '../helpers/platform-auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';

const meResponse = (user) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(user),
});

const mockProject = {
  id: 1,
  name: 'E-commerce Platform',
  description: 'Full-stack e-commerce solution',
  status: 'active',
  status_label: 'Activo',
  current_state: {
    id: 2,
    name: 'Activo',
    system_key: 'active',
    operational_effect: 'operating',
    color: 'emerald',
  },
  progress: 65,
  client_id: 9002,
  client_name: 'Client E2E',
  client_email: 'client@e2e-test.com',
  client_company: 'ACME Corp',
  start_date: '2025-01-01',
  estimated_end_date: '2025-06-30',
};

function setupDetailMocks(page, { user, project = mockProject }) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(project) };
    }
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([project]) };
    }
    if (apiPath === 'accounts/projects/1/' && method === 'PATCH') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...project, name: 'Updated Name' }) };
    }
    return null;
  });
}

async function gotoProjectDetail(page) {
  await page.goto('/platform/projects/1', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(
    page.getByRole('heading', { name: 'E-commerce Platform', exact: true }),
  ).toBeVisible({ timeout: 45_000 });
}

test.describe('Platform Project Detail — Admin', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  test('renders project detail with name, status badge, and stats', {
    tag: ['@outcome:display', ...PLATFORM_PROJECT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — project detail renders name, status and stats; the back-link interaction covers this flow)
    await setupDetailMocks(page, { user: mockPlatformAdmin });
    await gotoProjectDetail(page);
    await expect(page.getByText('Activo', { exact: true })).toBeVisible();
    await expect(page.getByText('Cliente: Client E2E')).toBeVisible();

    const main = page.locator('main');
    await expect(main.getByText('Progreso')).toBeVisible();
    await expect(main.getByText('65%')).toBeVisible();
  });

  test('the back link returns to the projects list', {
    tag: [...PLATFORM_PROJECT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // Fails if the project-detail back link stops routing to the projects list.
    await setupDetailMocks(page, { user: mockPlatformAdmin });
    await gotoProjectDetail(page);

    await page.locator('main').getByRole('link', { name: /proyectos/i }).click();

    await expect(page).toHaveURL(/\/platform\/projects$/);
  });

  test('renders the project delivery navigation link', {
    tag: ['@outcome:display', ...PLATFORM_PROJECT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the project nav exposes its delivery destination)
    await setupDetailMocks(page, { user: mockPlatformAdmin });
    await gotoProjectDetail(page);

    const boardLink = page.getByRole('link', { name: 'Entregas', exact: true });
    await expect(boardLink).toBeVisible();
    // i18n prefix strategy adds locale prefix to all hrefs
    await expect(boardLink).toHaveAttribute('href', /\/platform\/projects\/1\/delivery$/);
  });

  test('admin jumps back to the commercial record in a new tab (PA-50)', {
    tag: [...PLATFORM_PROJECT_DETAIL, '@role:platform-admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupDetailMocks(page, { user: mockPlatformAdmin });
    await gotoProjectDetail(page);

    const backLink = page.getByTestId('project-back-to-panel');
    await expect(backLink).toBeVisible();

    const popupPromise = page.context().waitForEvent('page');
    await backLink.click();
    const popup = await popupPromise;

    await popup.waitForURL(/\/panel\/projects\?highlight=1/, { timeout: 25_000 });
    await expect(popup).toHaveURL(/\/panel\/projects\?highlight=1/);
  });

  test('admin sees Editar button', {
    tag: ['@outcome:display', ...PLATFORM_PROJECT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — admin sees the Editar control)
    await setupDetailMocks(page, { user: mockPlatformAdmin });
    await gotoProjectDetail(page);

    await expect(page.getByRole('button', { name: /editar/i })).toBeVisible();
  });
});

test.describe('Platform Project Detail — Client', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test('client sees project detail without edit button', {
    tag: [...PLATFORM_PROJECT_DETAIL, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (permission display — client sees the detail without the edit control, by absence)
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupDetailMocks(page, { user: mockPlatformClient });
    await gotoProjectDetail(page);

    await expect(
      page.getByRole('heading', { name: 'E-commerce Platform', exact: true }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: /editar/i })).not.toBeVisible();
    // PA-50: the panel is admin territory; the back-link must not exist here.
    await expect(page.getByTestId('project-back-to-panel')).not.toBeVisible();
  });
});
