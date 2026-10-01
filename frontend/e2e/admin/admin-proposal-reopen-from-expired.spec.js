/**
 * E2E tests for auto-reopening an expired proposal via JSON update.
 *
 * Covers: expired proposal edit page → paste JSON with future expires_at →
 * confirm warning modal → PUT /proposals/:id/update-from-json/ → status reverts.
 *
 * The backend's ProposalService.reopen_if_unexpired() automatically changes
 * status from 'expired' to 'viewed' (or 'sent') when expires_at is extended.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_REOPEN_FROM_EXPIRED } from '../helpers/flow-tags.js';

test.describe.configure({ timeout: 60_000 });

const PROPOSAL_ID = 2;
const pastDate = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString();
const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

const mockExpiredProposal = {
  id: PROPOSAL_ID,
  uuid: '33333333-3333-3333-3333-333333333333',
  title: 'Expired Test Proposal',
  client_name: 'Expired Client',
  client_email: 'expired@test.com',
  status: 'expired',
  sent_at: '2026-01-01T12:00:00Z',
  expires_at: pastDate,
  language: 'es',
  total_investment: '5000000',
  currency: 'COP',
  view_count: 3,
  is_active: true,
  sections: [],
  requirement_groups: [],
};

const importJson = JSON.stringify({
  general: { clientName: 'Expired Client' },
  _meta: { expires_at: futureDate },
});

test.describe('Admin Proposal Reopen From Expired', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8300, role: 'admin', is_staff: true },
    });
  });

  test('JSON with future expires_at on expired proposal calls update-from-json and auto-reopens', {
    tag: [...ADMIN_PROPOSAL_REOPEN_FROM_EXPIRED, '@role:admin'],
  }, async ({ page }) => {
    let updateCalled = false;

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        // Stateful: once the reopen PUT ran, the backend reports the
        // reverted status, so any refetch reflects the reopen.
        const detail = updateCalled
          ? { ...mockExpiredProposal, status: 'viewed', expires_at: futureDate }
          : mockExpiredProposal;
        return { status: 200, contentType: 'application/json', body: JSON.stringify(detail) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/update-from-json/` && method === 'PUT') {
        updateCalled = true;
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockExpiredProposal, status: 'viewed', expires_at: futureDate }),
        };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    // The sticky-header status select shows the current status: Expirada.
    const statusSelect = page.getByLabel('Cambiar estado de la propuesta');
    await expect(statusSelect).toHaveValue('expired', { timeout: 10000 });

    await selectProposalDestination(page, 'proposal', 'json');

    const textarea = page.getByTestId('proposal-import-json-textarea');
    await textarea.fill(importJson);
    await textarea.dispatchEvent('input');

    const applyBtn = page.getByRole('button', { name: 'Aplicar JSON' });
    await expect(applyBtn).toBeVisible({ timeout: 5000 });
    await applyBtn.click();

    await expect(page.getByRole('heading', { name: 'Aplicar JSON' })).toBeVisible({ timeout: 5000 });

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes(`proposals/${PROPOSAL_ID}/update-from-json/`)),
      page.getByTestId('confirm-modal-confirm').click(),
    ]);
    await response.finished();

    expect(updateCalled).toBe(true);
    await expect(page.getByText('Propuesta actualizada desde JSON.')).toBeVisible({ timeout: 5000 });

    // The defining outcome of the flow: the status badge reverts
    // expired → viewed once the future expires_at is applied.
    await expect(statusSelect).toHaveValue('viewed', { timeout: 10000 });
  });

  test('a rejected JSON update fails without reopening the status client-side', {
    // Bug this catches: an apply-JSON failure that still flips the status
    // select to reopened client-side, even though nothing was persisted.
    tag: [...ADMIN_PROPOSAL_REOPEN_FROM_EXPIRED, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockExpiredProposal) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/update-from-json/` && method === 'PUT') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ client_email: ['Correo inválido.'] }),
        };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const statusSelect = page.getByLabel('Cambiar estado de la propuesta');
    await expect(statusSelect).toHaveValue('expired', { timeout: 10000 });

    await selectProposalDestination(page, 'proposal', 'json');

    const textarea = page.getByTestId('proposal-import-json-textarea');
    await textarea.fill(importJson);
    await textarea.dispatchEvent('input');

    const applyBtn = page.getByRole('button', { name: 'Aplicar JSON' });
    await expect(applyBtn).toBeVisible({ timeout: 5000 });
    await applyBtn.click();

    await expect(page.getByRole('heading', { name: 'Aplicar JSON' })).toBeVisible({ timeout: 5000 });

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes(`proposals/${PROPOSAL_ID}/update-from-json/`)),
      page.getByTestId('confirm-modal-confirm').click(),
    ]);
    await response.finished();

    const toast = page.getByRole('alert').filter({ hasText: 'Error al aplicar el JSON.' });
    await expect(toast).toBeVisible({ timeout: 5000 });

    // The defining outcome: the status select stays 'expired' — no client-side reopen.
    await expect(statusSelect).toHaveValue('expired');
  });

  test('General tab date change PATCHes /update/ and reopens the status', {
    tag: [...ADMIN_PROPOSAL_REOPEN_FROM_EXPIRED, '@role:admin'],
  }, async ({ page }) => {
    let patchBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockExpiredProposal) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/update/` && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockExpiredProposal, expires_at: futureDate, status: 'viewed' }),
        };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });

    const dateInput = page.locator('input[type="datetime-local"]').first();
    await expect(dateInput).toBeVisible({ timeout: 15000 });
    await dateInput.fill(futureDate.slice(0, 16));
    await Promise.all([
      page.waitForResponse((r) => r.url().includes(`proposals/${PROPOSAL_ID}/update/`)),
      page.getByRole('button', { name: 'Guardar Cambios' }).click(),
    ]);

    expect(patchBody.expires_at).toContain(futureDate.slice(0, 10));
    // The response status rides back into the header select: no longer expired.
    await expect(page.getByRole('combobox').first()).toHaveValue('viewed');
  });
});

