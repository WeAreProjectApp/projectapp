/**
 * E2E tests for adding and deleting proposal sections from the editor.
 *
 * Add: «＋ Agregar sección» opens a modal listing only the section types
 * not yet present; picking one POSTs proposals/:id/sections/create/.
 * Delete: the trash icon on a section header confirms and DELETEs
 * proposals/sections/:id/delete/.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_SECTION_ADD_DELETE } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;

function buildProposal() {
  return {
    id: PROPOSAL_ID,
    uuid: '11111111-1111-1111-1111-111111111111',
    title: 'Add/Delete Test',
    client_name: 'Client',
    client_email: 'client@test.com',
    language: 'es',
    status: 'draft',
    total_investment: '1000000',
    currency: 'COP',
    sections: [
      { id: 1, section_type: 'greeting', title: 'Saludo', order: 0, is_enabled: true, is_wide_panel: false, content_json: {} },
      { id: 2, section_type: 'timeline', title: 'Cronograma', order: 1, is_enabled: true, is_wide_panel: false, content_json: {} },
    ],
    requirement_groups: [],
    change_logs: [],
  };
}

function buildHandler({ captured = {}, deleteStatus = 200 } = {}) {
  return async ({ route, apiPath }) => {
    if (apiPath === 'auth/check/') {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { id: 7, username: 'admin', is_staff: true } }),
      };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(buildProposal()) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/sections/create/`) {
      captured.create = route.request().postDataJSON();
      return {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          section: {
            id: 33,
            section_type: captured.create.section_type,
            title: 'Inversión',
            order: 2,
            is_enabled: true,
            is_wide_panel: false,
            content_json: { totalInvestment: '$1,000,000' },
          },
          proposal_totals: { total_investment: '1000000', effective_total_investment: '1000000' },
        }),
      };
    }
    const deleteMatch = apiPath.match(/^proposals\/sections\/(\d+)\/delete\/$/);
    if (deleteMatch) {
      captured.deletedId = Number(deleteMatch[1]);
      if (deleteStatus !== 200) {
        return {
          status: deleteStatus,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'No se puede eliminar: el cliente ya confirmó módulos en la calculadora.',
            code: 'fr_has_confirmed_selection',
            hint: 'Desactiva la sección en lugar de eliminarla.',
          }),
        };
      }
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          deleted: true,
          section_type: 'timeline',
          proposal_totals: { total_investment: '1000000', effective_total_investment: '1000000' },
        }),
      };
    }
    return null;
  };
}

async function openSectionsTab(page) {
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
  await selectProposalDestination(page, 'proposal', 'sections');
  await page.getByTestId('section-header-greeting').waitFor({ state: 'visible' });
}

test.describe('Admin Proposal Section Add/Delete', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 7, role: 'admin', is_staff: true } });
  });

  test('adds a missing section type from the modal', {
    tag: [...ADMIN_PROPOSAL_SECTION_ADD_DELETE, '@role:admin'],
  }, async ({ page }) => {
    const captured = {};
    await mockApi(page, buildHandler({ captured }));
    await openSectionsTab(page);

    await page.getByTestId('add-section-button').click();

    // Present types are not offered.
    await expect(page.getByTestId('add-section-option-greeting')).toHaveCount(0);
    await expect(page.getByTestId('add-section-option-timeline')).toHaveCount(0);

    await page.getByTestId('add-section-option-investment').click();

    await expect(page.getByText('Sección agregada.')).toBeVisible();
    expect(captured.create).toEqual({ section_type: 'investment' });
    // The new section appears in the list.
    await expect(page.getByTestId('section-header-investment')).toBeVisible();
  });

  test('deletes a section after confirmation', {
    tag: [...ADMIN_PROPOSAL_SECTION_ADD_DELETE, '@role:admin'],
  }, async ({ page }) => {
    const captured = {};
    await mockApi(page, buildHandler({ captured }));
    await openSectionsTab(page);

    await page.getByTestId('section-delete-timeline').click();
    await expect(page.getByText('Eliminar sección')).toBeVisible();
    await page.getByRole('button', { name: 'Eliminar', exact: true }).click();

    await expect(page.getByText('Sección eliminada.')).toBeVisible();
    expect(captured.deletedId).toBe(2);
    await expect(page.getByTestId('section-header-timeline')).toHaveCount(0);
  });

  test('surfaces the backend guard when deletion is blocked', {
    tag: ['@outcome:error', ...ADMIN_PROPOSAL_SECTION_ADD_DELETE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildHandler({ deleteStatus: 400 }));
    await openSectionsTab(page);

    await page.getByTestId('section-delete-timeline').click();
    await page.getByRole('button', { name: 'Eliminar', exact: true }).click();

    await expect(
      page.getByText('No se puede eliminar: el cliente ya confirmó módulos en la calculadora.'),
    ).toBeVisible();
    // The section is still there.
    await expect(page.getByTestId('section-header-timeline')).toBeVisible();
  });
});
