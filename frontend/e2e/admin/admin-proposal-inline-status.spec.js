/**
 * E2E tests for inline status change from the proposals table.
 *
 * Covers: admin changes proposal status via the badge select (admin mode:
 * every status selectable, forced jumps require confirmation), API call to
 * PATCH update-status, and Spanish labels grouped by natural vs forced.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_INLINE_STATUS_CHANGE } from '../helpers/flow-tags.js';

const mockProposals = [
  { id: 1, title: 'Proposal A', client_name: 'Client A', status: 'viewed', client_email: 'a@test.com', total_investment: '5000000', currency: 'COP', available_transitions: ['negotiating', 'rejected'] },
  { id: 2, title: 'Proposal B', client_name: 'Client B', status: 'sent', client_email: 'b@test.com', total_investment: '3000000', currency: 'COP' },
  { id: 3, title: 'Proposal C', client_name: 'Client C', status: 'accepted', client_email: 'c@test.com', total_investment: '8000000', currency: 'COP', available_transitions: ['finished'] },
  { id: 4, title: 'Proposal D', client_name: 'Client D', status: 'draft', client_email: 'd@test.com', total_investment: '2000000', currency: 'COP', available_transitions: ['sent'] },
];

function setupMock(page, { onStatusUpdate = null, emailDelivery = null } = {}) {
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
    }
    if (apiPath === 'proposals/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposals) };
    }
    if (apiPath === 'proposals/dashboard/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({}) };
    }
    if (apiPath === 'proposals/alerts/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    const statusMatch = apiPath.match(/^proposals\/(\d+)\/update-status\/$/);
    if (statusMatch) {
      const body = JSON.parse(route.request().postData() || '{}');
      if (onStatusUpdate) onStatusUpdate(Number(statusMatch[1]), body);
      const source = mockProposals.find((p) => p.id === Number(statusMatch[1])) || mockProposals[0];
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...source, status: body.status, available_transitions: [], ...(emailDelivery ? { email_delivery: emailDelivery } : {}) }),
      };
    }
    return null;
  });
}

async function gotoProposals(page) {
  await page.goto('/panel/proposals');
  await page.waitForResponse((resp) => resp.url().includes('/proposals') && resp.status() === 200);
}

test.describe('Admin Proposal Inline Status Change', () => {
  test.describe.configure({ timeout: 60_000 });

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8000, role: 'admin', is_staff: true } });
  });

  test('forced finished status PATCHes after confirmation', {
    tag: [...ADMIN_PROPOSAL_INLINE_STATUS_CHANGE, '@role:admin'],
  }, async ({ page }) => {
    const updates = [];
    await setupMock(page, { onStatusUpdate: (id, body) => updates.push({ id, body }) });
    await gotoProposals(page);

    // 'finished' is not a natural transition from 'viewed' → forced confirm.
    // Approval is covered by the explicit review-modal flow, not this generic confirmation.
    const row = page.getByRole('row').filter({ hasText: 'Proposal A' });
    const statusSelect = row.getByRole('combobox');
    await expect(statusSelect).toBeVisible();
    await statusSelect.selectOption('finished');

    const confirmButton = page.getByTestId('confirm-modal-confirm');
    await expect(confirmButton).toBeVisible();
    const responsePromise = page.waitForResponse((resp) => resp.url().includes('update-status') && resp.status() === 200);
    await confirmButton.click();
    await responsePromise;

    expect(updates).toEqual([{ id: 1, body: { status: 'finished' } }]);
  });

  test('natural transition PATCHes without confirmation', {
    tag: [...ADMIN_PROPOSAL_INLINE_STATUS_CHANGE, '@role:admin'],
  }, async ({ page }) => {
    const updates = [];
    await setupMock(page, { onStatusUpdate: (id, body) => updates.push({ id, body }) });
    await gotoProposals(page);

    // 'rejected' is a natural transition from 'viewed' → no confirm dialog.
    const row = page.getByRole('row').filter({ hasText: 'Proposal A' });
    const responsePromise = page.waitForResponse((resp) => resp.url().includes('update-status') && resp.status() === 200);
    await row.getByRole('combobox').selectOption('rejected');
    await responsePromise;

    expect(updates).toEqual([{ id: 1, body: { status: 'rejected' } }]);
  });

  test('renders every status with Spanish labels grouped by natural vs forced', {
    tag: [...ADMIN_PROPOSAL_INLINE_STATUS_CHANGE, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoProposals(page);

    const row = page.getByRole('row').filter({ hasText: 'Proposal A' });
    const statusSelect = row.getByRole('combobox');
    await expect(statusSelect).toBeVisible();

    const labels = await statusSelect.locator('option').allTextContents();
    for (const label of ['Vista', 'En negociación', 'Rechazada', 'Borrador', 'Enviada', 'Aceptada', 'Finalizada', 'Expirada']) {
      expect(labels).toContain(label);
    }
    const naturalLabels = await statusSelect.locator('optgroup[label="Flujo normal"] option').allTextContents();
    expect(naturalLabels).toEqual(['En negociación', 'Rechazada']);
  });

  test('accepted proposal exposes finished as a natural inline option', {
    tag: [...ADMIN_PROPOSAL_INLINE_STATUS_CHANGE, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await gotoProposals(page);

    const row = page.getByRole('row').filter({ hasText: 'Proposal C' });
    const statusSelect = row.getByRole('combobox');
    await expect(statusSelect).toBeVisible();
    const naturalLabels = await statusSelect.locator('optgroup[label="Flujo normal"] option').allTextContents();
    expect(naturalLabels).toEqual(['Finalizada']);
  });

  test('draft to sent surfaces the email_delivery failure toast', {
    tag: ['@outcome:failure', ...ADMIN_PROPOSAL_INLINE_STATUS_CHANGE, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page, {
      emailDelivery: { ok: false, reason: 'placeholder_email', detail: 'El cliente no tiene un email real configurado.' },
    });
    await gotoProposals(page);

    const row = page.getByRole('row').filter({ hasText: 'Proposal D' });
    await row.getByRole('combobox').selectOption('sent');
    // draft → sent is natural but always confirms ("Enviar propuesta").
    await expect(page.getByText('Enviar propuesta')).toBeVisible();
    await Promise.all([
      page.waitForResponse((resp) => resp.url().includes('update-status')),
      page.getByTestId('confirm-modal-confirm').click(),
    ]);

    await expect(page.getByText('El cliente no tiene un email real configurado.').first()).toBeVisible();
  });

  test('actions modal exposes the Cambiar estado row with the same select', {
    tag: [...ADMIN_PROPOSAL_INLINE_STATUS_CHANGE, '@role:admin'],
  }, async ({ page }) => {
    const updates = [];
    await setupMock(page, { onStatusUpdate: (id, body) => updates.push({ id, body }) });
    await gotoProposals(page);

    await page.getByTestId('proposal-actions-1').click();
    const modalRow = page.locator('div.fixed').filter({ hasText: 'Cambiar estado' });
    await expect(modalRow.first()).toBeVisible();

    await Promise.all([
      page.waitForResponse((resp) => resp.url().includes('update-status')),
      modalRow.getByRole('combobox').first().selectOption('rejected'),
    ]);
    expect(updates).toEqual([{ id: 1, body: { status: 'rejected' } }]);
  });

  test('edit page header select PATCHes the status inline', {
    tag: [...ADMIN_PROPOSAL_INLINE_STATUS_CHANGE, '@role:admin'],
  }, async ({ page }) => {
    const updates = [];
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === 'proposals/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockProposals[0], sections: [], requirement_groups: [], expires_at: new Date(Date.now() + 30 * 86400000).toISOString() }) };
      }
      if (apiPath === 'proposals/1/update-status/') {
        const body = JSON.parse(route.request().postData() || '{}');
        updates.push(body);
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockProposals[0], status: body.status, available_transitions: [] }) };
      }
      return null;
    });
    await page.goto('/panel/proposals/1/edit', { waitUntil: 'domcontentloaded' });

    const headerSelect = page.getByRole('combobox').first();
    await expect(headerSelect).toBeVisible({ timeout: 15000 });
    await Promise.all([
      page.waitForResponse((resp) => resp.url().includes('update-status')),
      headerSelect.selectOption('rejected'),
    ]);
    expect(updates).toEqual([{ status: 'rejected' }]);
  });
});
