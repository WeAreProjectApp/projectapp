/**
 * E2E tests for the SyncPreviewModal — shown when an admin saves a
 * technical_document section on an accepted proposal with a linked project.
 *
 * Covers: "Det. técnico" tab → "Guardar detalle técnico" →
 * POST sync-preview returns has_project:true → modal renders diff →
 * "Confirmar y aplicar" → POST apply-sync endpoint called.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_SECTION_SYNC } from '../helpers/flow-tags.js';

test.describe.configure({ timeout: 60_000 });

const PROPOSAL_ID = 5;
const SECTION_ID = 10;

const mockTechnicalSection = {
  id: SECTION_ID,
  section_type: 'technical_document',
  title: 'Detalle Técnico',
  order: 0,
  is_enabled: true,
  is_wide_panel: false,
  content_json: {
    purpose: 'Descripción técnica del proyecto.',
    epics: [],
  },
};

const mockAcceptedProposal = {
  id: PROPOSAL_ID,
  uuid: '55555555-5555-5555-5555-555555555555',
  title: 'Accepted Proposal With Sync',
  client_name: 'Accepted Client',
  client_email: 'accepted@test.com',
  status: 'accepted',
  sent_at: '2026-01-01T12:00:00Z',
  expires_at: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString(),
  language: 'es',
  total_investment: '8000000',
  currency: 'COP',
  view_count: 10,
  deliverable_id: 999,
  platform_onboarding_completed_at: '2026-02-01T00:00:00Z',
  is_active: true,
  sections: [mockTechnicalSection],
  requirement_groups: [],
};

const mockSyncPreviewResponse = {
  has_project: true,
  project_info: { id: 99, name: 'Test Project', client_email: 'accepted@test.com' },
  deliverable_info: { id: 999, title: 'Entregable Principal' },
  diff: {
    epics: { to_create: [], to_update: [], to_delete: [] },
    requirements: { to_create: [], to_update: [], to_delete: [] },
  },
};

test.describe('Admin Proposal Section Sync (Preview & Apply)', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8300, role: 'admin', is_staff: true },
    });
  });

  test('saving technical section on accepted proposal opens sync preview modal; apply-sync called on confirm', {
    tag: [...ADMIN_PROPOSAL_SECTION_SYNC, '@role:admin'],
  }, async ({ page }) => {
    let applySyncCalled = false;

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockAcceptedProposal) };
      }
      if (apiPath === `proposals/sections/${SECTION_ID}/sync-preview/` && method === 'POST') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockSyncPreviewResponse) };
      }
      if (apiPath === `proposals/sections/${SECTION_ID}/apply-sync/` && method === 'POST') {
        applySyncCalled = true;
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: SECTION_ID, content_json: mockTechnicalSection.content_json }),
        };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'proposal', 'technical');

    await page.getByRole('button', { name: 'Guardar detalle técnico' }).click();

    await expect(page.getByText('Vista previa de sincronización')).toBeVisible({ timeout: 10000 });

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes(`proposals/sections/${SECTION_ID}/apply-sync/`)),
      page.getByRole('button', { name: 'Confirmar y aplicar' }).click(),
    ]);
    await response.finished();

    expect(applySyncCalled).toBe(true);
  });

  test('dismissing the sync preview renders the diff but does not apply it', {
    tag: [...ADMIN_PROPOSAL_SECTION_SYNC, '@role:admin'],
  }, async ({ page }) => {
    let applySyncCalled = false;

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockAcceptedProposal) };
      }
      if (apiPath === `proposals/sections/${SECTION_ID}/sync-preview/` && method === 'POST') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...mockSyncPreviewResponse,
            diff: {
              epics: { to_create: [{ title: 'Nueva Épica: Autenticación' }], to_update: [], to_delete: [] },
              requirements: { to_create: [], to_update: [], to_delete: [] },
            },
          }),
        };
      }
      if (apiPath === `proposals/sections/${SECTION_ID}/apply-sync/` && method === 'POST') {
        applySyncCalled = true;
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ id: SECTION_ID, content_json: mockTechnicalSection.content_json }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'proposal', 'technical');
    await page.getByRole('button', { name: 'Guardar detalle técnico' }).click();

    await expect(page.getByText('Vista previa de sincronización')).toBeVisible({ timeout: 10000 });
    // The non-empty diff renders the new-epic row.
    await expect(page.getByText('Nueva Épica: Autenticación')).toBeVisible();

    await page.getByRole('button', { name: 'Cancelar' }).click();

    await expect(page.getByText('Vista previa de sincronización')).not.toBeVisible();
    // Dismiss must NOT trigger the apply-sync POST.
    expect(applySyncCalled).toBe(false);
  });
});
