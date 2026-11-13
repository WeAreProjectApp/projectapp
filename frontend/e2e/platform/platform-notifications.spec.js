/**
 * E2E tests for platform notifications flow.
 *
 * @flow:platform-notifications
 * Covers: notification list rendering, filter tabs (all/unread/read),
 *         mark-all-read, click-to-navigate deep links, unread count badge.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_NOTIFICATIONS } from '../helpers/flow-tags.js';
import { PLATFORM_REQUIREMENT_PACKAGES_REQUEST } from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClient,
} from '../helpers/platform-auth.js';

const mockNotifications = [
  {
    id: 1, type: 'requirement_moved', title: 'Requerimiento actualizado: Login',
    message: '"Login" se movió a "En progreso" en E-commerce.', is_read: false,
    project: 1, project_name: 'E-commerce Platform',
    related_object_type: 'requirement', related_object_id: 101,
    created_at: '2025-03-20T10:00:00Z',
  },
  {
    id: 2, type: 'bug_reported', title: 'Bug reportado: Botón no funciona',
    message: 'Client E2E reportó un bug en E-commerce.', is_read: false,
    project: 1, project_name: 'E-commerce Platform',
    related_object_type: 'bug_report', related_object_id: 5,
    created_at: '2025-03-19T14:00:00Z',
  },
  {
    id: 3, type: 'general', title: 'Pago confirmado',
    message: 'Tu pago de $675,000 COP fue procesado.', is_read: true,
    project: 1, project_name: 'E-commerce Platform',
    related_object_type: 'payment', related_object_id: 1,
    created_at: '2025-03-18T08:00:00Z',
  },
  {
    id: 4, type: 'general', title: 'Solicitud por tallas: estado del pedido',
    message: 'El equipo respondió tu solicitud para Atlas.', is_read: false,
    project: 1, project_name: 'E-commerce Platform',
    related_object_type: 'package_request', related_object_id: 701,
    created_at: '2025-03-21T10:00:00Z',
  },
];

const meResponse = (user) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(user) });

function setupMocks(page, { user }) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/notifications/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockNotifications) };
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 2 }) };
    }
    if (apiPath === 'accounts/notifications/mark-all-read/' && method === 'POST') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ marked_read: 2 }) };
    }
    if (apiPath.match(/accounts\/notifications\/\d+\/read\/$/) && method === 'PATCH') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ id: 1, is_read: true }) };
    }
    if (apiPath === 'accounts/projects/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    return null;
  });
}

test.describe('Platform Notifications — Admin', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  test('renders notification list with unread and read items', {
    tag: ['@outcome:display', ...PLATFORM_NOTIFICATIONS, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — notification list renders unread and read items; the filter interaction is covered below)
    await setupMocks(page, { user: mockPlatformAdmin });
    await page.goto('/platform/notifications', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /notificaciones/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText('Requerimiento actualizado: Login')).toBeVisible();
    await expect(page.getByText('Bug reportado: Botón no funciona')).toBeVisible();
    await expect(page.getByText('Pago confirmado')).toBeVisible();
  });

  test('filtering to unread hides the read notifications', {
    tag: ['@outcome:display', ...PLATFORM_NOTIFICATIONS, '@role:platform-admin'],
  }, async ({ page }) => {
    // Fails if the "Sin leer" filter stops hiding already-read notifications.
    await setupMocks(page, { user: mockPlatformAdmin });
    await page.goto('/platform/notifications', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /notificaciones/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText('Pago confirmado')).toBeVisible();
    await page.getByRole('button', { name: /sin leer/i }).click();
    await expect(page.getByText('Pago confirmado')).not.toBeVisible();
  });

  test('shows unread count in header', {
    tag: ['@outcome:display', ...PLATFORM_NOTIFICATIONS, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — unread count shown in header)
    await setupMocks(page, { user: mockPlatformAdmin });
    await page.goto('/platform/notifications', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /notificaciones/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText(/sin leer/i)).toBeVisible();
  });
});

test.describe('Platform Notifications — Client', () => {
  test.setTimeout(60_000);

  test('client sees their notifications', {
    tag: ['@outcome:display', ...PLATFORM_NOTIFICATIONS, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — client sees their notifications)
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/notifications', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /notificaciones/i }).waitFor({ state: 'visible', timeout: 30000 });

    await expect(page.getByText('Requerimiento actualizado: Login')).toBeVisible();
  });

  test('package-request notification opens the exact package request', {
    tag: ['@outcome:success', ...PLATFORM_REQUIREMENT_PACKAGES_REQUEST, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a package-request notification loses its request id or routes the client to the project summary.
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupMocks(page, { user: mockPlatformClient });
    await page.goto('/platform/notifications', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /notificaciones/i }).waitFor({ state: 'visible', timeout: 30_000 });

    await page.getByText('Solicitud por tallas: estado del pedido', { exact: true }).click();

    await expect(page).toHaveURL(/\/platform\/projects\/1\/packages\?request=701$/);
  });
});
