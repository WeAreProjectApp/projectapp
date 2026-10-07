/**
 * E2E tests for reassigning a proposal to a different client from edit view.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_UPDATE_CLIENT } from '../helpers/flow-tags.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';

const PROPOSAL_ID = 44;

const initialProposal = {
  id: PROPOSAL_ID,
  uuid: '44444444-1111-1111-1111-444444444444',
  title: 'Migracion CRM',
  client_name: 'Cliente Actual',
  client_email: 'actual@example.com',
  client_phone: '+57 300 000 0001',
  status: 'draft',
  language: 'es',
  total_investment: '4500000',
  currency: 'COP',
  view_count: 0,
  heat_score: 5,
  sent_at: null,
  is_active: true,
  created_at: '2026-04-01T12:00:00Z',
  sections: [],
  requirement_groups: [],
  client: {
    id: 701,
    name: 'Cliente Actual',
    email: 'actual@example.com',
    phone: '+57 300 000 0001',
    company: 'ActualCo',
    is_email_placeholder: false,
  },
};

const reassignedClient = {
  id: 702,
  name: 'Cliente Nuevo',
  email: 'nuevo@example.com',
  phone: '+57 311 222 3344',
  company: 'NuevoCo',
  is_email_placeholder: false,
  total_proposals: 1,
};

test.describe.configure({ timeout: 60_000 });

test.describe('Admin Proposal Update Client', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('reassigns the proposal to a different client and syncs snapshot fields', {
    tag: [...ADMIN_PROPOSAL_UPDATE_CLIENT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let capturedPayload = null;

    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }

      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(initialProposal) };
      }

      if (apiPath === 'proposals/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([initialProposal]) };
      }

      if (apiPath.startsWith('proposals/client-profiles/search/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([reassignedClient]) };
      }

      if (apiPath === `proposals/${PROPOSAL_ID}/update/` && method === 'PATCH') {
        capturedPayload = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...initialProposal,
            client_name: reassignedClient.name,
            client_email: reassignedClient.email,
            client_phone: reassignedClient.phone,
            client: reassignedClient,
          }),
        };
      }

      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'project', 'project-data');
    await expect(page.getByTestId('proposal-edit-client-autocomplete')).toBeVisible({ timeout: 20_000 });

    const autocomplete = page.getByTestId('proposal-edit-client-autocomplete');
    await autocomplete.fill('nuevo');
    await expect(page.getByTestId('client-autocomplete-option-702')).toBeVisible({ timeout: 5_000 });
    await page.getByTestId('client-autocomplete-option-702').click();

    await expect(page.getByTestId('edit-client-name')).toHaveValue('Cliente Nuevo');
    await expect(page.getByTestId('edit-client-email')).toHaveValue('nuevo@example.com');
    await expect(page.getByTestId('edit-client-phone')).toHaveValue('+57 311 222 3344');
    await expect(page.getByTestId('edit-client-company')).toHaveValue('NuevoCo');

    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes(`/api/proposals/${PROPOSAL_ID}/update/`) && res.request().method() === 'PATCH'),
      page.getByRole('button', { name: 'Guardar cliente' }).click(),
    ]);
    await response.finished();

    expect(capturedPayload).not.toBeNull();
    expect(capturedPayload.client_id).toBe(702);
    expect(capturedPayload.client_name).toBe('Cliente Nuevo');
    expect(capturedPayload.client_email).toBe('nuevo@example.com');

    await expect(page.getByRole('alert')).toContainText('Cambios guardados.');
  });
});
