/**
 * E2E tests for updating an existing proposal from a pasted JSON payload.
 *
 * Covers: edit page → paste JSON into import textarea → confirm warning modal →
 * PUT /proposals/:id/update-from-json/ → success toast shown.
 *
 * Different from admin-proposal-create-from-json: targets an existing proposal id.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_UPDATE_FROM_JSON } from '../helpers/flow-tags.js';

test.describe.configure({ timeout: 60_000 });

const PROPOSAL_ID = 3;
const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

const mockDraftProposal = {
  id: PROPOSAL_ID,
  uuid: '44444444-4444-4444-4444-444444444444',
  title: 'Update From JSON Test',
  client_name: 'Original Client',
  client_email: 'original@test.com',
  status: 'draft',
  sent_at: null,
  expires_at: futureDate,
  language: 'es',
  total_investment: '3000000',
  currency: 'COP',
  view_count: 0,
  is_active: true,
  sections: [],
  requirement_groups: [],
};

const importJson = JSON.stringify({
  general: { clientName: 'Updated Client' },
  _meta: { title: 'Updated Proposal Title' },
});

test.describe('Admin Proposal Update From JSON', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8300, role: 'admin', is_staff: true },
    });
  });

  test('pasting JSON and confirming calls PUT update-from-json and shows success toast', {
    tag: [...ADMIN_PROPOSAL_UPDATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    let updateCalled = false;

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDraftProposal) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/update-from-json/` && method === 'PUT') {
        updateCalled = true;
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...mockDraftProposal,
            title: 'Updated Proposal Title',
            client_name: 'Updated Client',
            warnings: [],
          }),
        };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

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

    expect(updateCalled).toEqual(true);
    await expect(page.getByText('Propuesta actualizada desde JSON.')).toContainText('Propuesta actualizada desde JSON.', { timeout: 5000 });
  });

  test('unknown section keys ride the PUT and the flow still succeeds', {
    tag: [...ADMIN_PROPOSAL_UPDATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    let putBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockDraftProposal) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/update-from-json/` && method === 'PUT') {
        putBody = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockDraftProposal, warnings: ['Claves de sección ignoradas: seccionInventada.'] }),
        };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'proposal', 'json');
    const textarea = page.getByTestId('proposal-import-json-textarea');
    await textarea.fill(JSON.stringify({
      general: { clientName: 'Updated Client' },
      seccionInventada: { x: 1 },
    }));
    await textarea.dispatchEvent('input');
    await page.getByRole('button', { name: 'Aplicar JSON' }).click();
    await expect(page.getByRole('heading', { name: 'Aplicar JSON' })).toBeVisible();
    await Promise.all([
      page.waitForResponse(r => r.url().includes('update-from-json')),
      page.getByTestId('confirm-modal-confirm').click(),
    ]);

    // The backend answers 200 + warnings (pytest-covered); the tab keeps the
    // success toast — the warnings array is not currently surfaced in this UI.
    await expect(page.getByText('Propuesta actualizada desde JSON.')).toContainText('Propuesta actualizada desde JSON.', { timeout: 5000 });
    // handleApplyImportJson() spreads the whole parsed payload (minus _meta/_seller_prompt)
    // into payload.sections, so an unrecognized top-level key rides verbatim under sections.
    expect(putBody.sections.seccionInventada).toEqual({ x: 1 });
  });

  test('re-importing over an expired proposal without touching expires_at succeeds', {
    tag: [...ADMIN_PROPOSAL_UPDATE_FROM_JSON, '@role:admin'],
  }, async ({ page }) => {
    const pastDate = new Date(Date.now() - 10 * 86400000).toISOString();
    const expired = { ...mockDraftProposal, status: 'expired', expires_at: pastDate };
    let updateCalled = false;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(expired) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/update-from-json/` && method === 'PUT') {
        updateCalled = true;
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...expired, client_name: 'Updated Client' }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'proposal', 'json');
    const textarea = page.getByTestId('proposal-import-json-textarea');
    await textarea.fill(JSON.stringify({ general: { clientName: 'Updated Client' } }));
    await textarea.dispatchEvent('input');
    await page.getByRole('button', { name: 'Aplicar JSON' }).click();
    await expect(page.getByRole('heading', { name: 'Aplicar JSON' })).toBeVisible();
    await Promise.all([
      page.waitForResponse(r => r.url().includes('update-from-json')),
      page.getByTestId('confirm-modal-confirm').click(),
    ]);

    expect(updateCalled).toEqual(true);
    await expect(page.getByText('Propuesta actualizada desde JSON.')).toContainText('Propuesta actualizada desde JSON.', { timeout: 5000 });
  });
});

