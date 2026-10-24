/**
 * E2E tests for the admin "Re-enviar propuesta" flow.
 *
 * Covers: actions menu → resend button → editable retained message →
 * POST /proposals/:id/resend/ → success/failure feedback.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_RESEND } from '../helpers/flow-tags.js';
import { fillRichTextSource } from '../helpers/editorial.js';

test.describe.configure({ timeout: 60_000 });

const PROPOSAL_ID = 1;
const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

const mockSentProposal = {
  id: PROPOSAL_ID,
  uuid: '22222222-2222-2222-2222-222222222222',
  title: 'Resend Test Proposal',
  client_name: 'Test Client',
  client_email: 'client@test.com',
  email_intro: 'Esta propuesta automatiza la operación para reducir reprocesos.',
  status: 'sent',
  sent_at: '2026-01-01T12:00:00Z',
  expires_at: futureDate,
  language: 'es',
  total_investment: '5000000',
  currency: 'COP',
  view_count: 2,
  is_active: true,
  sections: [],
  requirement_groups: [],
};

test.describe('Admin Proposal Resend', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8300, role: 'admin', is_staff: true },
    });
  });

  test('actions menu → confirm → POST resend endpoint is called', {
    tag: [...ADMIN_PROPOSAL_RESEND, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let resendCalled = false;
    let resendPayload = null;

    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockSentProposal) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/resend/` && method === 'POST') {
        resendCalled = true;
        resendPayload = route.request().postDataJSON();
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...mockSentProposal,
            ...resendPayload,
            sent_at: new Date().toISOString(),
          }),
        };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await page.getByTestId('proposal-actions-menu').click();
    await page.getByTestId('proposal-action-resend').click();

    await expect(page.getByRole('heading', { name: 'Re-enviar propuesta' })).toBeVisible({ timeout: 5000 });
    const message = page.getByTestId('proposal-resend-email-intro');
    await message.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(message.getByTestId('rich-text-source-input')).toHaveValue(mockSentProposal.email_intro);
    await fillRichTextSource(message, 'Esta versión incorpora inventario para evitar quiebres de stock.');

    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes(`proposals/${PROPOSAL_ID}/resend/`)),
      page.getByTestId('proposal-resend-confirm').click(),
    ]);
    await response.finished();

    expect(resendCalled).toBe(true);
    expect(resendPayload).toEqual({
      email_intro: 'Esta versión incorpora inventario para evitar quiebres de stock.',
    });
    await expect(page.getByText('Propuesta re-enviada al cliente')).toBeVisible({ timeout: 5000 });
  });

  test('a blank retained message blocks resend before any request', {
    tag: [...ADMIN_PROPOSAL_RESEND, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    let resendCalled = false;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockSentProposal, email_intro: '' }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/resend/` && method === 'POST') {
        resendCalled = true;
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.getByTestId('proposal-actions-menu').click();
    await page.getByTestId('proposal-action-resend').click();

    const message = page.getByTestId('proposal-resend-email-intro');
    await message.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(message.getByTestId('rich-text-source-input')).toHaveValue('');
    await expect(page.getByTestId('proposal-resend-confirm')).toBeDisabled();
    expect(resendCalled).toBe(false);
  });

  test('failed delivery surfaces the email_delivery detail instead of success', {
    tag: ['@outcome:failure', ...ADMIN_PROPOSAL_RESEND, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockSentProposal) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/resend/` && method === 'POST') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...mockSentProposal,
            email_delivery: { ok: false, reason: 'send_failed', detail: 'El servidor SMTP rechazó el correo.' },
          }),
        };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);
    await page.getByTestId('proposal-actions-menu').click();
    await page.getByTestId('proposal-action-resend').click();
    await expect(page.getByRole('heading', { name: 'Re-enviar propuesta' })).toBeVisible({ timeout: 5000 });

    await Promise.all([
      page.waitForResponse(r => r.url().includes(`proposals/${PROPOSAL_ID}/resend/`)),
      page.getByTestId('proposal-resend-confirm').click(),
    ]);

    await expect(page.getByText('El servidor SMTP rechazó el correo.').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Propuesta re-enviada al cliente')).toBeHidden();
  });
});
