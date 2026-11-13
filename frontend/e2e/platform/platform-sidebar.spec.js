/**
 * E2E tests for platform sidebar navigation flow.
 *
 * @flow:platform-sidebar-navigation
 * Covers: sidebar render with navigation links, active link highlighting,
 *         admin-only links visibility, client restricted links,
 *         logout action, mobile drawer toggle.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_SIDEBAR_NAVIGATION } from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClient,
} from '../helpers/platform-auth.js';

const meResponse = (user) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(user),
});

test.describe('Platform initials palette', () => {
  test.setTimeout(60_000);
  for (const mode of ['light', 'dark']) {
    test(`keeps the initials brand pair with a light personal palette in ${mode} mode`, {
      tag: [...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin', '@outcome:display'],
    }, async ({ page }) => {
      // Bug caught: inheriting the personalized primary could replace the agreed avatar pair.
      const user = { ...mockPlatformAdmin, theme_color: '#F0FF3D' };
      await setPlatformAuth(page, { user });
      await setupSidebarMocks(page, user);
      await page.addInitScript(theme => localStorage.setItem('platform_theme', theme), mode);
      await page.goto('/platform', { waitUntil: 'domcontentloaded' });
      const sidebar = page.getByRole('complementary');
      await sidebar.getByRole('link', { name: 'Configuración', exact: true }).click();
      await expect(page).toHaveURL(/\/platform\/profile$/);

      const initials = sidebar.getByText('AE', { exact: true });
      await expect(initials).toHaveCSS('background-color', 'rgb(0, 41, 33)');
      await expect(initials).toHaveCSS('color', 'rgb(255, 255, 255)');
    });
  }
});

function setupSidebarMocks(page, user) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath.startsWith('accounts/clients/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath.startsWith('accounts/projects/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    return null;
  });
}

test.describe('Platform Sidebar — Admin', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  test('renders sidebar with admin navigation links', {
    tag: ['@outcome:display', ...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (layout chrome; the flow's interactive path is covered at :66-75)
    await setupSidebarMocks(page, mockPlatformAdmin);
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('link', { name: /notificaciones/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /proyectos/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /clientes/i })).toBeVisible();
  });

  test('sidebar shows user display name and initials', {
    tag: ['@outcome:display', ...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin'],
  }, async ({ page }) => {
    await setupSidebarMocks(page, mockPlatformAdmin);
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });

    // Scope to the desktop sidebar landmark: the mobile top bar renders the
    // same initials markup off-screen (md:hidden), which would otherwise
    // collide in strict mode.
    const sidebar = page.getByRole('complementary');
    // Exact match avoids partial-text hits elsewhere on the page.
    await expect(sidebar.getByText('Admin E2E', { exact: true })).toBeVisible();
    // Initials are derived from first/last name ("Admin E2E" -> "AE"); this
    // catches a regression in the userInitials getter that the name-only
    // assertion above would miss.
    await expect(sidebar.getByText('AE', { exact: true })).toBeVisible();
  });

  test('navigating to projects page via sidebar link works', {
    tag: [...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin'],
  }, async ({ page }) => {
    await setupSidebarMocks(page, mockPlatformAdmin);
    await page.goto('/platform/clients', { waitUntil: 'domcontentloaded' });

    await page.getByRole('link', { name: /proyectos/i }).click();
    await page.waitForURL('**/platform/projects', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/projects/);
  });
});

test.describe('Platform Sidebar — Client', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test('client sidebar does not show admin-only links like Clientes', {
    tag: [...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (layout chrome; the flow's interactive path is covered at :66-75)
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupSidebarMocks(page, mockPlatformClient);
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('link', { name: /proyectos/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /clientes/i })).not.toBeVisible();
  });
});
