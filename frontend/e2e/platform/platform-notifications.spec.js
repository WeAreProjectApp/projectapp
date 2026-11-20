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

const deliveryStage = { id: 17, key: 'E1', title: 'Etapa de prueba publicada', status: 'in_review', publication_id: 31, requirements: [] };
const deliveryNotice = {
  id: 85, type: 'delivery_published', title: 'Nueva etapa para revisar',
  message: 'Ya puedes abrir la etapa de prueba.', is_read: false,
  project: 2, project_name: 'Proyecto de prueba', related_object_type: 'delivery_stage',
  related_object_id: deliveryStage.id, created_at: '2026-11-19T14:00:00Z',
};
const deliveryProject = { id: 2, name: deliveryNotice.project_name, status: 'active', progress: 25 };
const deliveryWorkspace = {
  project: deliveryProject, contracts: [{ id: 3, key: 'C1', title: 'Contrato de prueba' }],
  scopes: [{ id: 4, contract_id: 3, title: 'Alcance', phases: [{ id: 5, title: 'Fase', stages: [deliveryStage] }] }],
};

function setupMocks(page, { user, notifications = mockNotifications, markReadStatus = () => 200 }) {
  const rows = notifications.map(notification => ({ ...notification }));
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(user);
    if (apiPath === 'accounts/notifications/' && method === 'GET') {
      return meResponse(rows);
    }
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
      return meResponse({ count: rows.filter(notification => !notification.is_read).length });
    }
    if (apiPath === 'accounts/notifications/mark-all-read/' && method === 'POST') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ marked_read: 2 }) };
    }
    const readEndpoint = apiPath.match(/^accounts\/notifications\/(\d+)\/read\/$/);
    if (readEndpoint && method === 'POST') {
      const id = Number(readEndpoint[1]);
      const status = await markReadStatus(id);
      if (status !== 200) return { ...meResponse({ detail: 'Error de prueba al marcar lectura' }), status };
      const notification = rows.find(row => row.id === id);
      notification.is_read = true;
      return meResponse(notification);
    }
    if (apiPath === 'accounts/projects/2/' && method === 'GET') {
      return meResponse(deliveryProject);
    }
    if (apiPath === 'accounts/projects/2/delivery/' && method === 'GET') {
      return meResponse(deliveryWorkspace);
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

    await expect(page.getByText('3 sin leer', { exact: true })).toBeVisible();
  });
});

async function openDeliveryNotice(page, markReadStatus) {
  await setPlatformAuth(page, { user: mockPlatformClient });
  await setupMocks(page, {
    user: mockPlatformClient,
    notifications: [deliveryNotice, mockNotifications[0]],
    markReadStatus,
  });
  // quality: allow-deep-link (this regression starts from the notification filters)
  await page.goto('/en-us/platform/notifications', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Notificaciones', exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('2 sin leer', { exact: true })).toBeVisible();
  const unread = page.getByRole('button', { name: 'Sin leer', exact: true });
  await expect(page.getByRole('button', { name: 'Todas', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await unread.click();
  await expect(unread).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Todas', exact: true })).toHaveAttribute('aria-pressed', 'false');
  const read = page.getByRole('button', { name: 'Leídas', exact: true });
  await expect(read).toHaveAttribute('aria-pressed', 'false');
  await read.focus();
  await page.keyboard.press('Tab');
  return page.getByRole('link', { name: deliveryNotice.title, exact: true });
}

test('one Enter opens the published stage after persisting a single read', {
  tag: [...PLATFORM_NOTIFICATIONS, '@role:platform-client', '@outcome:success'],
}, async ({ page }) => {
  test.setTimeout(60_000);
  const requests = [];
  const { promise, resolve } = Promise.withResolvers();
  const notice = await openDeliveryNotice(page, id => { requests.push(id); return promise; });
  await expect(notice).toBeFocused();
  await expect(notice).toHaveCSS('box-shadow', /.+px /);

  await page.keyboard.press('Enter');
  await expect(notice).toHaveAttribute('aria-busy', 'true');
  await expect(notice).toBeFocused();
  await expect(page).toHaveURL(/\/platform\/notifications$/);
  await expect(page.getByText('2 sin leer', { exact: true })).toBeVisible();
  resolve(200);

  await expect(page).toHaveURL(/\/platform\/projects\/2\/delivery\?stage=17$/);
  await expect(page.getByTestId('delivery-stage-17')).toHaveAttribute('aria-current', 'location');
  expect(requests).toEqual([deliveryNotice.id]);
  await page.goBack({ waitUntil: 'domcontentloaded' });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByText('1 sin leer', { exact: true })).toBeVisible();
  const read = page.getByRole('button', { name: 'Leídas', exact: true });
  await read.click();
  await expect(read).toHaveAttribute('aria-pressed', 'true');
  await expect(notice).toBeVisible();
});

test('a failed read keeps the unread notice available for keyboard retry', {
  tag: [...PLATFORM_NOTIFICATIONS, '@role:platform-client', '@outcome:failure'],
}, async ({ page }) => {
  test.setTimeout(60_000);
  const requests = [];
  const { promise, resolve } = Promise.withResolvers();
  const notice = await openDeliveryNotice(page, id => {
    requests.push(id);
    return requests.length === 1 ? promise : 200;
  });
  await expect(notice).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(notice).toHaveAttribute('aria-busy', 'true');
  await page.keyboard.press('Enter');
  resolve(503);

  await expect(page.getByRole('alert')).toHaveText('No pudimos marcar el aviso como leído. Intenta de nuevo.');
  await expect(notice).toBeFocused();
  await expect(notice).toHaveAttribute('href', /\/platform\/projects\/2\/delivery\?stage=17$/);
  await expect(page.getByText('2 sin leer', { exact: true })).toBeVisible();
  expect(requests).toEqual([deliveryNotice.id]);
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('delivery-stage-17')).toBeVisible();
  expect(requests).toEqual([deliveryNotice.id, deliveryNotice.id]);
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
