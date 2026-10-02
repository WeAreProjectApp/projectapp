/**
 * E2E tests for platform layout browser tab title mapping.
 *
 * @flow:platform-layout-title-mapping
 * Covers: static route, dynamic project base route, and nested dynamic route
 * (delivery within project), including an old board bookmark.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setPlatformAuth, mockPlatformAdmin } from '../helpers/platform-auth.js';
import { PLATFORM_LAYOUT_TITLE_MAPPING } from '../helpers/flow-tags.js';

const meResponse = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(mockPlatformAdmin),
};

test.describe('Platform Layout — Browser Tab Title', () => {
  test.setTimeout(120_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  test('shows "Proyectos" on /platform/projects', {
    tag: ['@outcome:display', ...PLATFORM_LAYOUT_TITLE_MAPPING, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (routing/title-mapping — asserts the browser tab title for the route; no in-page action applies)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'accounts/me/') return meResponse;
      return null;
    });
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveTitle(/Project App \(Proyectos\)/, { timeout: 10_000 });
  });

  test('shows "Proyecto" on /platform/projects/:id — dynamic regex route', {
    tag: ['@outcome:display', ...PLATFORM_LAYOUT_TITLE_MAPPING, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (routing/title-mapping — asserts the tab title for the dynamic project route)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'accounts/me/') return meResponse;
      return null;
    });
    await page.goto('/platform/projects/1', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveTitle(/Project App \(Proyecto\)/, { timeout: 10_000 });
  });

  test('shows the delivery title for a former board bookmark', {
    tag: ['@outcome:display', ...PLATFORM_LAYOUT_TITLE_MAPPING, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (routing/title-mapping — an old bookmark must use the delivery destination's title)
    // quality: allow-deep-link (a saved board bookmark is the entry point for this compatibility behavior)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'accounts/me/') return meResponse;
      return null;
    });
    await page.goto('/platform/projects/1/board', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveTitle('Scope and deliveries | Project App', { timeout: 10_000 });
  });
});
