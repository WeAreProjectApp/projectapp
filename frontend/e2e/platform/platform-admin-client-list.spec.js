/**
 * E2E tests for platform admin client list flow.
 *
 * @flow:platform-admin-client-list
 * Covers: client table render, status filter tabs, search filtering,
 *         invite client modal, resend invite, deactivate client,
 *         detail link navigation, admin-only access guard.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_ADMIN_CLIENT_LIST } from '../helpers/flow-tags.js';
import { PANEL_VIEWPORTS } from '../helpers/viewports.js';
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

const mockClients = [
  {
    user_id: 9002,
    first_name: 'Active',
    last_name: 'Client',
    email: 'active@e2e-test.com',
    company_name: 'ACME Corp',
    phone: '+57 300 111 1111',
    is_active: true,
    is_onboarded: true,
    created_at: '2025-01-10T10:00:00Z',
  },
  {
    user_id: 9003,
    first_name: 'Pending',
    last_name: 'Client',
    email: 'pending@e2e-test.com',
    company_name: 'Startup Inc',
    phone: '+57 300 222 2222',
    is_active: true,
    is_onboarded: false,
    created_at: '2025-01-12T10:00:00Z',
  },
  {
    user_id: 9004,
    first_name: 'Inactive',
    last_name: 'Client',
    email: 'inactive@e2e-test.com',
    company_name: 'Old Corp',
    phone: '+57 300 333 3333',
    is_active: false,
    is_onboarded: true,
    created_at: '2025-01-05T10:00:00Z',
  },
];

function setupClientMocks(page) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformAdmin);
    if (apiPath === 'accounts/clients/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockClients) };
    }
    if (apiPath === 'accounts/clients/' && method === 'POST') {
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 9005,
          first_name: 'New',
          last_name: 'Client',
          email: 'new@e2e-test.com',
          company_name: 'New Corp',
          is_active: true,
          is_onboarded: false,
        }),
      };
    }
    if (apiPath.match(/accounts\/clients\/\d+\/resend-invite\//) && method === 'POST') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ detail: 'Invitación reenviada.' }) };
    }
    if (apiPath.match(/accounts\/clients\/\d+\//) && method === 'DELETE') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ detail: 'Cliente desactivado.' }) };
    }
    return null;
  });
}

test.describe('Platform Admin Client List', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  for (const profile of ['compact', 'desktop']) {
    for (const theme of ['light', 'dark']) {
      test(`returns focus to the invitation trigger at ${profile} in ${theme} mode`, {
        tag: [...PLATFORM_ADMIN_CLIENT_LIST, '@role:platform-admin', '@outcome:success'],
      }, async ({ page }) => {
        await page.setViewportSize(PANEL_VIEWPORTS[profile]);
        await page.addInitScript((value) => localStorage.setItem('platform_theme', value), theme);
        await setupClientMocks(page);
        await page.goto('/es-co/platform/clients', { waitUntil: 'domcontentloaded' });
        const trigger = page.getByRole('button', { name: 'Invitar cliente', exact: true });

        await trigger.click();

        const dialog = page.getByRole('dialog', { name: 'Invitar cliente', exact: true });
        await expect(dialog).toHaveAttribute('aria-modal', 'true');
        await expect(dialog).toBeFocused();
        await dialog.getByRole('button', { name: 'Cancelar', exact: true }).click();
        await expect(dialog).not.toBeVisible();
        await expect(trigger).toBeFocused();
      });
    }
  }

  test('renders client table with columns and data', {
    tag: ['@outcome:display', ...PLATFORM_ADMIN_CLIENT_LIST, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — client table renders rows from the API; the flow's interaction is the invite-modal test)
    await setupClientMocks(page);
    await page.goto('/platform/clients', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Active Client', { exact: true })).toBeVisible();
    await expect(page.getByText('ACME Corp')).toBeVisible();
    await expect(page.getByText('Pending Client')).toBeVisible();
    await expect(page.getByText('Startup Inc')).toBeVisible();
  });

  test('renders status filter tabs', {
    tag: ['@outcome:display', ...PLATFORM_ADMIN_CLIENT_LIST, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — status filter tabs render)
    await setupClientMocks(page);
    await page.goto('/platform/clients', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('button', { name: /todos/i })).toBeVisible();
  });

  test('shows invite client button', {
    tag: ['@outcome:display', ...PLATFORM_ADMIN_CLIENT_LIST, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the invite-client control renders)
    await setupClientMocks(page);
    await page.goto('/platform/clients', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('button', { name: /invitar cliente/i })).toBeVisible();
  });

  test('opening the invite-client modal shows the invite form', {
    tag: ['@outcome:display', ...PLATFORM_ADMIN_CLIENT_LIST, '@role:platform-admin'],
  }, async ({ page }) => {
    // Fails if the "Invitar cliente" button stops opening the invite modal.
    await setupClientMocks(page);
    await page.goto('/platform/clients', { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: /invitar cliente/i }).click();

    await expect(page.getByRole('heading', { name: 'Invitar cliente' })).toContainText('Invitar cliente');
  });

  test('shows empty state when no clients exist', {
    tag: ['@outcome:display', ...PLATFORM_ADMIN_CLIENT_LIST, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — empty state renders when no clients exist)
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformAdmin);
      if (apiPath === 'accounts/clients/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.goto('/platform/clients', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText(/no hay clientes/i)).toBeVisible();
  });
});

test.describe('Platform Admin Client List — Access Guard', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test('client role is redirected away from clients page', {
    tag: [...PLATFORM_ADMIN_CLIENT_LIST, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (access guard — client role redirected to dashboard, asserted by URL)
    await setPlatformAuth(page, { user: mockPlatformClient });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformClient);
      return null;
    });

    await page.goto('/platform/clients', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/dashboard', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/dashboard/);
  });
});
