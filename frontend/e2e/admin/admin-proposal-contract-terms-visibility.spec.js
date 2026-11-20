/**
 * Admin control for the proposal Contract and terms mode.
 *
 * @flow:admin-proposal-contract-terms-visibility
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_CONTRACT_TERMS_VISIBILITY } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 903;
const proposal = {
  id: PROPOSAL_ID,
  uuid: 'ed111111-1111-1111-1111-111111111111',
  title: 'Visibilidad contractual E2E',
  client_name: 'Cliente E2E',
  client_email: 'cliente@example.com',
  language: 'es',
  status: 'draft',
  total_investment: '5000000',
  currency: 'COP',
  show_contract_terms: true,
  sections: [],
  requirement_groups: [],
};

function buildEditHandler({ updateStatus = 200, capturePayload = () => {} } = {}) {
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    }
    if (apiPath === 'proposals/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([proposal]) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/update/` && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      capturePayload(payload);
      return {
        status: updateStatus,
        contentType: 'application/json',
        body: JSON.stringify(updateStatus === 200 ? { ...proposal, ...payload } : { error: 'temporary_failure' }),
      };
    }
    return null;
  };
}

test.describe('Admin proposal contract visibility', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(60_000);
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('edit switch persists the hidden state', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_TERMS_VISIBILITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let capturedPayload = null;
    await mockApi(page, buildEditHandler({ capturePayload: payload => { capturedPayload = payload; } }));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });

    const toggle = page.getByTestId('proposal-contract-terms-toggle');
    await expect(toggle).toHaveAttribute('aria-checked', 'true', { timeout: 20_000 });
    await toggle.click();

    await expect(page.getByText('Contrato y condiciones oculto.')).toBeVisible({ timeout: 10_000 });
    expect(capturedPayload).toEqual({ show_contract_terms: false });
    await expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  test('failed edit restores the visible state', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_TERMS_VISIBILITY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, buildEditHandler({ updateStatus: 500 }));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });

    const toggle = page.getByTestId('proposal-contract-terms-toggle');
    await expect(toggle).toHaveAttribute('aria-checked', 'true', { timeout: 20_000 });
    await toggle.click();

    await expect(page.getByText('No se pudo cambiar la visibilidad del contrato.')).toBeVisible({ timeout: 10_000 });
    await expect(toggle).toHaveAttribute('aria-checked', 'true');
  });

  test('creation submits the selected hidden state', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_TERMS_VISIBILITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let capturedPayload = null;
    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === 'proposals/defaults/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ reminder_days: 3, urgency_reminder_days: 7 }) };
      }
      if (apiPath === 'proposals/create/') {
        capturedPayload = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(proposal) };
      }
      return null;
    });
    await page.goto('/panel/proposals/create', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Manual' }).click();
    await page.getByTestId('create-contract-terms-toggle').click();
    await page.getByLabel('Título').fill('Visibilidad contractual E2E');
    await page.getByLabel('Nombre').fill('Cliente E2E');
    await page.getByLabel('Email').fill('cliente@example.com');

    await page.getByRole('button', { name: /Crear Propuesta/i }).click();
    await expect(page.getByText('Propuesta creada')).toBeVisible({ timeout: 15_000 });
    expect(capturedPayload.show_contract_terms).toBe(false);
  });
});
