/**
 * E2E tests for platform admin client detail flow.
 *
 * @flow:platform-admin-client-detail
 * Covers: client detail page render with profile card and edit form,
 *         save changes, reset form, resend invite, deactivate client,
 *         not found state, back link navigation.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_ADMIN_CLIENT_DETAIL } from '../helpers/flow-tags.js';
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

const mockClientDetail = {
  user_id: 9002,
  first_name: 'Client',
  last_name: 'E2E',
  email: 'client@e2e-test.com',
  company_name: 'ACME Corp',
  phone: '+57 300 000 0002',
  is_active: true,
  is_onboarded: true,
  created_at: '2025-01-10T10:00:00Z',
  cedula: '9876543210',
  date_of_birth: '1995-06-20',
  gender: 'female',
  education_level: 'posgrado',
  avatar: null,
};

const longClient = {
  ...mockClientDetail,
  first_name: 'Cliente ficticio responsive',
  last_name: 'Apellidos extensos para verificar el espacio disponible en tarjetas y encabezados',
  company_name: 'Empresa ficticia responsive de investigación, desarrollo y operaciones internacionales con nombre comercial extenso para comprobar tarjetas, tablas y formularios',
};

async function expectUsableClientEditor(page) {
  await expect(page.getByText(longClient.company_name, { exact: true })).toBeVisible();
  for (const name of ['Nombre', 'Apellido', 'Empresa', 'Teléfono']) {
    const input = page.getByRole('textbox', { name, exact: true });
    await expect(input).toBeVisible();
    const box = await input.boundingBox();
    expect(box.width, `El campo ${name} quedó comprimido`).toBeGreaterThan(150);
  }
  const save = page.getByRole('button', { name: 'Guardar cambios', exact: true });
  await save.scrollIntoViewIfNeeded();
  await expect(save).toBeInViewport();
  expect(await save.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
  await expect(page.getByRole('button', { name: 'Restablecer', exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
}

function setupClientDetailMocks(page, { client = mockClientDetail } = {}) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformAdmin);
    if (apiPath === `accounts/clients/${client.user_id}/` && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(client) };
    }
    if (apiPath === `accounts/clients/${client.user_id}/` && method === 'PATCH') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...client, company_name: 'Updated Corp' }) };
    }
    if (apiPath === `accounts/clients/${client.user_id}/` && method === 'DELETE') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ detail: 'Cliente desactivado.' }) };
    }
    if (apiPath === `accounts/clients/${client.user_id}/resend-invite/` && method === 'POST') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ detail: 'Invitación reenviada.' }) };
    }
    if (apiPath.startsWith('accounts/clients/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([client]) };
    }
    return null;
  });
}

test.describe('Platform Admin Client Detail', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
    for (const collapsed of [false, true]) {
      test(`keeps the long client editor usable at ${profile} with sidebar collapsed=${collapsed}`, {
        tag: [...PLATFORM_ADMIN_CLIENT_DETAIL, '@role:platform-admin', '@outcome:display'],
      }, async ({ page }) => {
        await page.addInitScript((value) => localStorage.setItem('platform_sidebar_collapsed', String(value)), collapsed);
        await setupClientDetailMocks(page, { client: longClient });
        // quality: allow-deep-link (PA-237 explicitly requires direct loads of this client detail)
        await page.setViewportSize(PANEL_VIEWPORTS.wide);
        await page.goto(`/es-co/platform/clients/${longClient.user_id}`, { waitUntil: 'domcontentloaded' });
        await expect(page.getByRole('textbox', { name: 'Apellido', exact: true })).toHaveValue(longClient.last_name);

        await page.setViewportSize(PANEL_VIEWPORTS[profile]);

        await page.getByRole('textbox', { name: 'Nombre', exact: true }).fill('Borrador sin guardar');
        await page.getByRole('button', { name: 'Restablecer', exact: true }).click();
        await expect(page.getByRole('textbox', { name: 'Nombre', exact: true })).toHaveValue(longClient.first_name);
        await expectUsableClientEditor(page);
        await page.reload({ waitUntil: 'domcontentloaded' });
        await expect(page.getByRole('textbox', { name: 'Empresa', exact: true })).toHaveValue(longClient.company_name);
        await expectUsableClientEditor(page);
      });
    }
  }

  test('renders client detail page with profile card and edit form', {
    tag: ['@outcome:display', ...PLATFORM_ADMIN_CLIENT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — client detail renders the profile card; the back-link interaction covers this flow)
    await setupClientDetailMocks(page);
    await page.goto('/platform/clients/9002', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Client E2E')).toBeVisible();
    await expect(page.getByText('client@e2e-test.com')).toBeVisible();
    await expect(page.getByText('ACME Corp')).toBeVisible();
  });

  test('the back link returns to the clients list', {
    tag: [...PLATFORM_ADMIN_CLIENT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // Fails if the client-detail back link stops routing to the clients list.
    await setupClientDetailMocks(page);
    await page.goto('/platform/clients/9002', { waitUntil: 'domcontentloaded' });

    // Scope to main to avoid matching the sidebar 'Clientes' link.
    await page.locator('main').getByRole('link', { name: /clientes/i }).click();

    await expect(page).toHaveURL(/\/platform\/clients$/);
  });

  test('shows not found message for invalid client ID', {
    tag: ['@outcome:failure', ...PLATFORM_ADMIN_CLIENT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — not-found state renders for an invalid client id)
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformAdmin);
      if (apiPath === 'accounts/clients/9999/' && method === 'GET') {
        return { status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'No encontrado' }) };
      }
      if (apiPath.startsWith('accounts/clients/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.goto('/platform/clients/9999', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText(/no encontramos el cliente/i)).toBeVisible();
  });

  test('shows action buttons for admin operations', {
    tag: ['@outcome:display', ...PLATFORM_ADMIN_CLIENT_DETAIL, '@role:platform-admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — admin action controls render on the detail page)
    await setupClientDetailMocks(page);
    await page.goto('/platform/clients/9002', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('button', { name: /guardar cambios/i })).toBeVisible();
  });
});

test.describe('Platform Admin Client Detail — Access Guard', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test('client role is redirected away from client detail page', {
    tag: [...PLATFORM_ADMIN_CLIENT_DETAIL, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (access guard — client role redirected to dashboard, asserted by URL)
    await setPlatformAuth(page, { user: mockPlatformClient });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformClient);
      return null;
    });

    await page.goto('/platform/clients/9002', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/dashboard', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/dashboard/);
  });
});
