/**
 * E2E tests for the unsaved-changes (dirty) guard on proposal sections.
 *
 * Covers: the "Sin guardar" badge on edited sections, the confirmation
 * modal when collapsing a dirty section, and that cancelling keeps the
 * editor open with the edits intact.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_SECTION_DIRTY_GUARD } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'E2E Dirty Guard Test',
  client_name: 'Dirty Client',
  client_email: 'dirty@test.com',
  language: 'es',
  status: 'draft',
  total_investment: '5000000',
  currency: 'COP',
  view_count: 0,
  sent_at: null,
  expires_at: null,
  sections: [
    {
      id: 101,
      section_type: 'greeting',
      title: 'Saludo',
      order: 0,
      is_enabled: true,
      is_wide_panel: false,
      content_json: { proposalTitle: 'E2E Dirty Guard Test', clientName: 'Dirty Client', inspirationalQuote: '' },
    },
  ],
  requirement_groups: [],
  change_logs: [],
};

function buildHandler() {
  return async ({ apiPath }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { id: 7, username: 'admin', is_staff: true, is_superuser: false } }),
      };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
    }
    return null;
  };
}

async function openGreetingEditor(page) {
  await mockApi(page, buildHandler());
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
  await selectProposalDestination(page, 'proposal', 'sections');
  await page.getByTestId('section-header-greeting').click();
  await page.getByTestId('section-editor').waitFor({ state: 'visible' });
}

test.describe('Proposal Section — Dirty Guard', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 7, role: 'admin', is_staff: true },
    });
  });

  test('editing a field shows the "Sin guardar" badge', {
    tag: [...ADMIN_PROPOSAL_SECTION_DIRTY_GUARD, '@role:admin'],
  }, async ({ page }) => {
    await openGreetingEditor(page);

    const editor = page.getByTestId('section-editor');
    await editor.locator('input[type="text"]').first().fill('Saludo editado');

    await expect(page.getByTestId('section-dirty-badge-greeting')).toBeVisible();
  });

  test('collapsing a dirty section asks for confirmation; cancel keeps editing', {
    tag: [...ADMIN_PROPOSAL_SECTION_DIRTY_GUARD, '@role:admin'],
  }, async ({ page }) => {
    await openGreetingEditor(page);

    const editor = page.getByTestId('section-editor');
    await editor.locator('input[type="text"]').first().fill('Saludo editado');

    await page.getByTestId('section-header-greeting').click();

    await expect(page.getByText('Cambios sin guardar')).toBeVisible();
    await page.getByRole('button', { name: 'Seguir editando' }).click();

    await expect(editor).toBeVisible();
    await expect(editor.locator('input[type="text"]').first()).toHaveValue('Saludo editado');
  });

  test('confirming the collapse discards the edits and clears the badge', {
    tag: [...ADMIN_PROPOSAL_SECTION_DIRTY_GUARD, '@role:admin'],
  }, async ({ page }) => {
    await openGreetingEditor(page);

    const editor = page.getByTestId('section-editor');
    await editor.locator('input[type="text"]').first().fill('Saludo editado');

    await page.getByTestId('section-header-greeting').click();
    await page.getByRole('button', { name: 'Cerrar sin guardar' }).click();

    await expect(editor).toHaveCount(0);
    await expect(page.getByTestId('section-dirty-badge-greeting')).toHaveCount(0);
  });

  test('collapsing a clean section needs no confirmation', {
    tag: [...ADMIN_PROPOSAL_SECTION_DIRTY_GUARD, '@role:admin'],
  }, async ({ page }) => {
    await openGreetingEditor(page);

    await page.getByTestId('section-header-greeting').click();

    await expect(page.getByTestId('section-editor')).toHaveCount(0);
    await expect(page.getByText('Cambios sin guardar')).toHaveCount(0);
  });
});
