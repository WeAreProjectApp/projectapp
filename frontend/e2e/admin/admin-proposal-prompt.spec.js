/**
 * E2E tests for the proposal Prompt tab.
 *
 * @flow:admin-proposal-prompt
 * Covers: the commercial prompt rendering with its action bar, the
 *         edit → save round trip persisting to localStorage, cancel
 *         discarding the draft, and "Restaurar original" appearing only
 *         once the prompt diverges from the default.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_PROMPT } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 5;
const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: '55555555-5555-5555-5555-555555555555',
  title: 'Prompt Test Proposal',
  client_name: 'Prompt Client',
  client_email: 'prompt@test.com',
  status: 'draft',
  expires_at: futureDate,
  language: 'es',
  total_investment: '4000000',
  currency: 'COP',
  view_count: 0,
  is_active: true,
  sections: [],
  requirement_groups: [],
};

function setupMock(page) {
  return mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
    }
    return null;
  });
}

async function openPromptTab(page) {
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
  await selectProposalDestination(page, 'proposal', 'prompt');
  await expect(page.getByRole('button', { name: 'Editar', exact: true })).toBeVisible({ timeout: 15000 });
}

test.describe('Admin Proposal Prompt', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-admin-token', userAuth: { id: 8300, role: 'admin', is_staff: true } });
  });

  test('renders the commercial prompt with its action bar', {
    tag: [...ADMIN_PROPOSAL_PROMPT, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await openPromptTab(page);

    await expect(page.getByRole('button', { name: 'Copiar' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Descargar \.md/ })).toBeVisible();
    // Untouched prompt equals the default, so the reset action stays hidden.
    await expect(page.getByRole('button', { name: 'Restaurar original' })).toBeHidden();
  });

  test('editing and saving persists the prompt and reveals the reset action', {
    tag: [...ADMIN_PROPOSAL_PROMPT, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await openPromptTab(page);

    await page.getByRole('button', { name: 'Editar', exact: true }).click();
    const editor = page.locator('textarea.font-mono:visible').first();
    await expect(editor).toBeVisible();
    await editor.fill('Prompt personalizado para esta agencia.');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();

    await expect(page.getByRole('button', { name: 'Restaurar original' })).toBeVisible();
    await expect(page.getByText('Prompt personalizado para esta agencia.')).toBeVisible();
  });

  test('cancelling an edit discards the draft', {
    tag: [...ADMIN_PROPOSAL_PROMPT, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await openPromptTab(page);

    await page.getByRole('button', { name: 'Editar', exact: true }).click();
    await page.locator('textarea.font-mono:visible').first().fill('Texto descartado');
    await page.getByRole('button', { name: 'Cancelar', exact: true }).click();

    await expect(page.getByRole('button', { name: 'Editar', exact: true })).toBeVisible();
    await expect(page.getByText('Texto descartado')).toBeHidden();
  });
});
