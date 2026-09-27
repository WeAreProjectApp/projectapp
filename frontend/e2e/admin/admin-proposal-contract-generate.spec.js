/**
 * E2E tests for admin proposal contract generation flow.
 *
 * @flow:admin-proposal-contract-generate
 * Covers: ContractParamsModal renders in default and custom modes,
 *         company settings auto-populate, form submission calls API,
 *         contract appears in Documents tab after generation.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_CONTRACT_GENERATE } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'Contract Test Proposal',
  client_name: 'Acme Corp',
  client_email: 'acme@example.com',
  language: 'es',
  status: 'negotiating',
  total_investment: '10000000',
  currency: 'COP',
  view_count: 3,
  sent_at: '2026-03-28T10:00:00Z',
  sections: [
    { id: 1, section_type: 'greeting', title: 'Saludo', order: 0, is_enabled: true, content_json: { clientName: 'Acme Corp' } },
  ],
  requirement_groups: [],
  proposal_documents: [],
  contract_params: null,
};

const companySettings = {
  contractor_full_name: 'Carlos Dev',
  contractor_nit: '1234567890',
  contractor_email: 'carlos@projectapp.co',
  bank_name: 'Bancolombia',
  bank_account_type: 'Ahorros',
  bank_account_number: '123456789',
  contract_city: 'Medellín',
};

const defaultContractTemplate = {
  id: 1,
  name: 'Default Contract Template',
  markdown_content: '# Contract Template\n\nDefault template content.',
};

function buildApiHandler(overrides = {}) {
  const proposal = overrides.proposal || mockProposal;
  return async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    }
    if (apiPath === 'proposals/company-settings/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(companySettings) };
    }
    if (apiPath === 'proposals/contract-template/default/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(defaultContractTemplate) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/save-and-negotiate/` && method === 'POST') {
      return { status: 201, contentType: 'application/json', body: JSON.stringify({ id: 10, document_type: 'contract', title: 'Contrato' }) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/documents/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    return null;
  };
}

test.describe('Admin Proposal Contract Generate', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test('Documents tab visible for negotiating proposal with contract section', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler());
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible();
  });

  test('Documents tab is visible for sent proposals; contract generator only renders once negotiating', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler({
      proposal: { ...mockProposal, status: 'sent' },
    }));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Generar contrato/i })).toHaveCount(0);
  });

  test('Documents tab is visible for viewed proposals; contract generator only renders once negotiating', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler({
      proposal: { ...mockProposal, status: 'viewed' },
    }));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Generar contrato/i })).toHaveCount(0);
  });

  test('contract section shows "No generado" when no contract exists', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler());
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText(/No generado/)).toBeVisible();
  });

  test('contract actions are enabled once proposal is negotiating', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler());
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('button', { name: /Generar contrato/i })).toBeEnabled();
    await expect(page.getByText('Disponible en negociación')).toHaveCount(0);
  });

  test('opens ContractParamsModal in default mode with company settings', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler());
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: /Generar contrato/i }).click();

    // Modal header
    await expect(page.getByText('Generar contrato de desarrollo')).toBeVisible();
    // Default mode tab selected
    await expect(page.getByRole('tab', { name: /Contrato por defecto/i })).toBeVisible();
    // Contractor section
    await expect(page.getByText('EL CONTRATISTA')).toBeVisible();
    // Client section
    await expect(page.getByText('EL CONTRATANTE')).toBeVisible();
  });

  test('can toggle to custom Markdown mode', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildApiHandler());
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: /Generar contrato/i }).click();

    // Toggle to custom mode
    await page.getByRole('tab', { name: /Contrato personalizado/i }).click();
    await expect(page.getByPlaceholder(/Pega o escribe tu contrato/i)).toBeVisible();
    // Preview toggle (scope to modal — "Vista previa" also exists as PDF preview labels in documents list).
    await expect(page.getByRole('dialog').getByRole('button', { name: /Vista previa/i })).toBeVisible();
  });

  test('generating the first contract during negotiation calls the contract update API', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    // A client-started negotiation has no contract yet; generating it must not
    // retry the negotiating transition, which the backend refuses.
    let updatePayload = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      if (apiPath === 'proposals/company-settings/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(companySettings) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/contract/update/` && method === 'PATCH') {
        updatePayload = route.request().postDataJSON();
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: /Generar contrato/i }).click();
    await page.getByRole('tab', { name: /Contrato personalizado/i }).click();
    await page.getByPlaceholder(/Pega o escribe tu contrato/i).fill('# Mi contrato\n\nContenido del contrato.');
    await page
      .getByRole('group', { name: 'Datos del contrato' })
      .locator('input[type="date"]')
      .fill('2026-04-15');

    await page.getByRole('dialog').getByRole('button', { name: 'Generar contrato', exact: true }).click();
    await expect(() => expect(updatePayload).not.toBeNull()).toPass({ timeout: 5000 });
    expect(updatePayload.variant).toBe('combined');
    expect(updatePayload.contract_params).toEqual({
      contract_source: 'custom',
      custom_contract_markdown: '# Mi contrato\n\nContenido del contrato.',
      contract_date: '2026-04-15',
    });
  });

  test('moving a sent proposal to negotiation calls save-and-negotiate API', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_GENERATE, '@role:admin'],
  }, async ({ page }) => {
    // The endpoint answers with the proposal detail, which the store adopts.
    let negotiatePayload = null;
    const sentProposal = { ...mockProposal, status: 'sent', available_transitions: ['negotiating', 'rejected'] };
    const negotiatingProposal = {
      ...sentProposal,
      status: 'negotiating',
      available_transitions: ['accepted', 'rejected'],
      contract_params: {
        contract_source: 'custom',
        custom_contract_markdown: '# Mi contrato\n\nContenido del contrato.',
        contract_date: '2026-04-15',
      },
    };
    await mockApi(page, async ({ apiPath, method, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(sentProposal) };
      }
      if (apiPath === 'proposals/company-settings/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(companySettings) };
      }
      if (apiPath === 'proposals/contract-template/default/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(defaultContractTemplate) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/contract/save-and-negotiate/` && method === 'POST') {
        negotiatePayload = route.request().postDataJSON();
        return { status: 200, contentType: 'application/json', body: JSON.stringify(negotiatingProposal) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/documents/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    // The next-action button lives on the General tab, the default one.
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('proposal-next-action-negotiate')).toBeVisible();

    // Toggle to custom mode and type Markdown (simpler than filling all default fields)
    await page.getByTestId('proposal-next-action-negotiate').click();
    await page.getByRole('tab', { name: /Contrato personalizado/i }).click();
    await page.getByPlaceholder(/Pega o escribe tu contrato/i).fill('# Mi contrato\n\nContenido del contrato.');

    // Fill contract date
    const dateInput = page
      .getByRole('group', { name: 'Datos del contrato' })
      .locator('input[type="date"]');
    await dateInput.fill('2026-04-15');

    await page.getByRole('button', { name: /Generar contrato y negociar/i }).click();
    await expect(() => expect(negotiatePayload).not.toBeNull()).toPass({ timeout: 5000 });
    expect(negotiatePayload.contract_params).toEqual({
      contract_source: 'custom',
      custom_contract_markdown: '# Mi contrato\n\nContenido del contrato.',
      contract_date: '2026-04-15',
    });

    // The next action follows the new status.
    await expect(page.getByTestId('proposal-next-action-launch')).toHaveText('Lanzar a Plataforma');
    await expect(page.getByTestId('proposal-next-action-negotiate')).toHaveCount(0);
  });
});
