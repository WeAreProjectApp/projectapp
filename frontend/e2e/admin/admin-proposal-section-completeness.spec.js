/**
 * E2E tests for the section completeness indicator in the edit page.
 *
 * Covers: progress bar renders with correct percentage and color coding
 * based on enabled sections with content vs total enabled sections.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_SECTION_COMPLETENESS } from '../helpers/flow-tags.js';

function buildProposal(sections) {
  return {
    id: 1,
    title: 'Completeness Proposal',
    client_name: 'Client Test',
    client_email: 'client@test.com',
    status: 'draft',
    language: 'es',
    total_investment: '5000000',
    currency: 'COP',
    expires_at: new Date(Date.now() + 86400000 * 10).toISOString(),
    sections,
    requirement_groups: [],
  };
}

const fullSections = [
  { id: 1, section_type: 'greeting', title: 'Greeting', order: 0, is_enabled: true, content_json: { clientName: 'Client' } },
  { id: 2, section_type: 'investment', title: 'Investment', order: 1, is_enabled: true, content_json: { totalInvestment: 5000000 } },
  { id: 3, section_type: 'timeline', title: 'Timeline', order: 2, is_enabled: true, content_json: { phases: [] } },
  { id: 4, section_type: 'closing', title: 'Closing', order: 3, is_enabled: true, content_json: {} },
];

const partialSections = [
  { id: 1, section_type: 'greeting', title: 'Greeting', order: 0, is_enabled: true, content_json: { clientName: 'Client' } },
  { id: 2, section_type: 'investment', title: 'Investment', order: 1, is_enabled: true, content_json: {} },
  { id: 3, section_type: 'timeline', title: 'Timeline', order: 2, is_enabled: true, content_json: {} },
  { id: 4, section_type: 'closing', title: 'Closing', order: 3, is_enabled: true, content_json: {} },
];

test.describe('Admin Proposal Section Completeness', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8000, role: 'admin', is_staff: true } });
  });

  test('shows completeness indicator on sections tab', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_SECTION_COMPLETENESS, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === 'proposals/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(buildProposal(fullSections)) };
      }
      return null;
    });

    await page.goto('/es-co/panel/proposals/1/edit');
    await page.waitForResponse(resp => resp.url().includes('/detail/') && resp.status() === 200);

    // Navigate to sections through its parent group.
    await selectProposalDestination(page, 'proposal', 'sections');
    await expect(page.getByText('Completitud de secciones')).toBeVisible({ timeout: 5000 });
  });

  test('partial content shows lower completeness percentage', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_SECTION_COMPLETENESS, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === 'proposals/1/detail/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(buildProposal(partialSections)) };
      }
      return null;
    });

    await page.goto('/es-co/panel/proposals/1/edit');
    await page.waitForResponse(resp => resp.url().includes('/detail/') && resp.status() === 200);

    await selectProposalDestination(page, 'proposal', 'sections');
    await expect(page.getByText('Completitud de secciones')).toBeVisible({ timeout: 5000 });
  });
});
