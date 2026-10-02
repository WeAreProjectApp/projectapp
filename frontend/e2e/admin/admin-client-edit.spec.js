/**
 * E2E tests for admin client edit modal from the /panel/clients/ page.
 *
 * Covers: opening the edit modal via the edit button on a client row,
 * pre-filling with existing client data, submitting a name change,
 * and surfacing a server error from the update endpoint.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_CLIENT_EDIT } from '../helpers/flow-tags.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockClients = [
  {
    id: 301,
    name: 'Laura Pérez',
    email: 'laura@test.com',
    phone: '+57 310 111 2222',
    company: 'Laura Estudio',
    is_onboarded: true,
    is_email_placeholder: false,
    total_proposals: 2,
    is_orphan: false,
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-03-10T10:00:00Z',
  },
];

function setupMock(page, { onUpdate = null } = {}) {
  return mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'proposals/client-profiles/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockClients) };
    }
    const updateMatch = apiPath.match(/^proposals\/client-profiles\/(\d+)\/update\/$/);
    if (updateMatch && (method === 'PUT' || method === 'PATCH')) {
      if (onUpdate) return onUpdate(route);
      const body = JSON.parse(route.request().postData() || '{}');
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...mockClients[0], ...body }),
      };
    }
    const detailMatch = apiPath.match(/^proposals\/client-profiles\/(\d+)\/$/);
    if (detailMatch) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...mockClients[0], proposals: [] }),
      };
    }
    return null;
  });
}

test.describe('Admin Client Edit Modal', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9300, role: 'admin', is_staff: true },
    });
  });

  test('opens edit modal pre-filled with client data on edit button click', {
    tag: [...ADMIN_CLIENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/clients', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 20_000 });

    await page.getByTestId('client-edit-301').click();

    // Modal renders with client data pre-filled.
    await expect(page.getByTestId('clients-edit-name')).toHaveValue('Laura Pérez', { timeout: 5_000 });
    await expect(page.getByTestId('clients-edit-email')).toHaveValue('laura@test.com');
    await expect(page.getByTestId('clients-edit-phone')).toHaveValue('+57 310 111 2222');
    await expect(page.getByTestId('clients-edit-company')).toHaveValue('Laura Estudio');
  });

  test('submits updated name and closes modal on success', {
    tag: [...ADMIN_CLIENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let capturedPayload = null;
    await setupMock(page, {
      onUpdate: (route) => {
        capturedPayload = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockClients[0], name: 'Laura Pérez Actualizada' }),
        };
      },
    });
    await page.goto('/panel/clients', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 20_000 });

    await page.getByTestId('client-edit-301').click();
    await page.getByTestId('clients-edit-name').fill('Laura Pérez Actualizada');
    await page.getByTestId('clients-edit-submit').click();

    // Modal closes after successful submit.
    await expect(page.getByTestId('clients-edit-name')).not.toBeVisible({ timeout: 5_000 });

    // Payload sent to update endpoint includes the new name.
    expect(capturedPayload).not.toBeNull();
    expect(capturedPayload.name).toBe('Laura Pérez Actualizada');
  });

  test('round-trips a billing code carrying an ampersand', {
    tag: [...ADMIN_CLIENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // G&M is a real trade name. The field used to reject `&`, so the code for
    // this client could not be written as it is actually spelled.
    let capturedPayload = null;
    await setupMock(page, {
      onUpdate: (route) => {
        capturedPayload = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockClients[0], billing_code: 'G&M' }),
        };
      },
    });
    await page.goto('/panel/clients', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 20_000 });

    await page.getByTestId('client-edit-301').click();
    await page.getByTestId('clients-edit-billing-code').fill('g&m');
    await page.getByTestId('clients-edit-submit').click();

    await expect(page.getByTestId('clients-edit-name')).not.toBeVisible({ timeout: 5_000 });
    expect(capturedPayload.billing_code).toBe('G&M');
  });

  test('keeps billing labels single-line with aligned inputs', {
    tag: [...ADMIN_CLIENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // The semantic modal width keeps both short labels atomic; their shared
    // grid bands keep the controls aligned as a second line of defence.
    await setupMock(page);
    // quality: allow-deep-link (the clients list is this flow's entry point, as
    // in every spec here; the modal itself is opened by clicking)
    await page.goto('/panel/clients', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 20_000 });

    await page.getByTestId('client-edit-301').click();
    await expect(page.getByTestId('clients-edit-nit')).toBeVisible({ timeout: 5_000 });
    const dialog = page.getByRole('dialog', { name: 'Editar cliente' });
    await expect(dialog).toHaveCSS('opacity', '1');

    const typeLabelLocator = dialog.getByText('Tipo de identificación', { exact: true });
    const numberLabelLocator = dialog.getByText('Número de identificación', { exact: true });
    const addressLabelLocator = dialog.getByText('Dirección', { exact: true });
    const codeLabelLocator = dialog.getByText('Código de facturación', { exact: true });
    const typeLabel = await typeLabelLocator.boundingBox();
    const numberLabel = await numberLabelLocator.boundingBox();
    const addressLabel = await addressLabelLocator.boundingBox();
    const codeLabel = await codeLabelLocator.boundingBox();
    const labelWhiteSpaces = await Promise.all([
      typeLabelLocator.evaluate((label) => getComputedStyle(label).whiteSpace),
      numberLabelLocator.evaluate((label) => getComputedStyle(label).whiteSpace),
      addressLabelLocator.evaluate((label) => getComputedStyle(label).whiteSpace),
      codeLabelLocator.evaluate((label) => getComputedStyle(label).whiteSpace),
    ]);
    expect(labelWhiteSpaces).toEqual(['nowrap', 'nowrap', 'nowrap', 'nowrap']);
    expect(Math.max(
      Math.abs(typeLabel.height - numberLabel.height),
      Math.abs(addressLabel.height - codeLabel.height),
    )).toBeLessThanOrEqual(1);

    const type = await page.getByTestId('clients-edit-identification-type').boundingBox();
    const number = await page.getByTestId('clients-edit-nit').boundingBox();
    const address = await page.getByTestId('clients-edit-address').boundingBox();
    const code = await page.getByTestId('clients-edit-billing-code').boundingBox();
    expect(Math.max(
      Math.abs(type.y - number.y),
      Math.abs(address.y - code.y),
    )).toBeLessThanOrEqual(1);
    expect(Math.max(
      Math.abs(type.width - number.width),
      Math.abs(address.width - code.width),
    )).toBeLessThanOrEqual(1);
    expect(Math.abs(address.height - code.height)).toBeLessThanOrEqual(1);
    expect(number.x > type.x && code.x > address.x).toBe(true);
  });

  test('stacks the billing fields in reading order on a narrow screen', {
    tag: [...ADMIN_CLIENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await setupMock(page);
    // quality: allow-deep-link (the clients list is this flow's entry point, as
    // in every spec here; the modal itself is opened by clicking)
    await page.goto('/panel/clients', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 20_000 });

    await page.getByTestId('client-actions-301').click();
    const actions = page.getByTestId('client-actions-drawer');
    await actions.getByRole('button', { name: 'Editar cliente' }).click();
    await expect(page.getByTestId('clients-edit-nit')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole('dialog', { name: 'Editar cliente' })).toHaveCSS('opacity', '1');

    const type = await page.getByTestId('clients-edit-identification-type').boundingBox();
    const number = await page.getByTestId('clients-edit-nit').boundingBox();
    const address = await page.getByTestId('clients-edit-address').boundingBox();
    const code = await page.getByTestId('clients-edit-billing-code').boundingBox();

    const leftEdgeDrift = Math.max(
      Math.abs(type.x - number.x),
      Math.abs(number.x - address.x),
      Math.abs(address.x - code.x),
    );
    const verticalGaps = [
      number.y - (type.y + type.height),
      address.y - (number.y + number.height),
      code.y - (address.y + address.height),
    ];

    // One column: every adjacent field follows the complete reading order,
    // without a blank band between the legal identity, address and code.
    expect(leftEdgeDrift).toBeLessThanOrEqual(1);
    expect(Math.min(...verticalGaps)).toBeGreaterThan(0);
    expect(Math.max(...verticalGaps)).toBeLessThan(60);
  });

  test('surfaces server error when update returns 400', {
    tag: [...ADMIN_CLIENT_EDIT, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupMock(page, {
      onUpdate: () => ({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ name: ['Este nombre ya está en uso.'] }),
      }),
    });
    await page.goto('/panel/clients', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Clientes' })).toBeVisible({ timeout: 20_000 });

    await page.getByTestId('client-edit-301').click();
    await page.getByTestId('clients-edit-name').fill('Nombre duplicado');
    await page.getByTestId('clients-edit-submit').click();

    // Modal stays open and shows the error.
    await expect(page.getByTestId('clients-edit-name')).toBeVisible({ timeout: 5_000 });
  });
});
