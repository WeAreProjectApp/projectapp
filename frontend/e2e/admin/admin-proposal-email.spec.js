/**
 * E2E tests for admin sending branded and proposal emails from proposal edit page.
 *
 * Covers: Correos tab visibility in draft and later states, the personalized
 * initial-message editor, and the follow-up composer after the first send.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_SEND_BRANDED_EMAIL, ADMIN_SEND_PROPOSAL_EMAIL } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 7;
const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

function makeProposal(overrides = {}) {
  return {
    id: PROPOSAL_ID,
    uuid: 'email-test-uuid-1234-5678-abcdef',
    title: 'Email Test Proposal',
    client_name: 'Email Client',
    client_email: 'client@emailtest.com',
    email_intro: 'Esta propuesta centraliza las solicitudes para acelerar la atención.',
    status: 'negotiating',
    language: 'es',
    total_investment: '8000000',
    currency: 'COP',
    view_count: 3,
    sent_at: '2026-03-01T10:00:00Z',
    expires_at: futureDate,
    is_active: true,
    sections: [
      { id: 10, section_type: 'greeting', title: 'Bienvenido', order: 0, is_enabled: true, content_json: { clientName: 'Email Client' } },
    ],
    requirement_groups: [],
    change_logs: [],
    ...overrides,
  };
}

const emailDefaults = {
  greeting: 'Hola Email Client',
  footer: 'Quedamos atentos a tus comentarios.\nUn abrazo, el equipo de Project App.',
};

const emptyHistory = { results: [], total: 0, page: 1, has_next: false };

function emailApiRoutes(proposal) {
  return async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath.startsWith('proposals/client-profiles/search/')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    }
    if (apiPath.includes('/branded-email/defaults/') || apiPath.includes('/proposal-email/defaults/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emailDefaults) };
    }
    if (apiPath.includes('/branded-email/history/') || apiPath.includes('/proposal-email/history/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emptyHistory) };
    }
    return null;
  };
}

// Extends `emailApiRoutes` with the composer's POST .../{basePath}/send/ endpoint,
// so tests can drive the actual send action instead of only checking tab/render state.
function emailApiRoutesWithSend(
  proposal,
  sendBasePath,
  onSend,
  response = { status: 200, contentType: 'application/json', body: JSON.stringify({ id: 501 }) },
) {
  const base = emailApiRoutes(proposal);
  return async (ctx) => {
    const { apiPath, method } = ctx;
    if (apiPath === `proposals/${PROPOSAL_ID}/${sendBasePath}/send/` && method === 'POST') {
      onSend(ctx);
      return response;
    }
    return base(ctx);
  };
}

test.describe('Admin Proposal Email — Branded', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8700, role: 'admin', is_staff: true },
    });
  });

  test('branded email tab is visible for negotiating proposal', {
    tag: [...ADMIN_SEND_BRANDED_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (checks the Correos tab's status-gated visibility for a negotiating proposal; the send action itself is driven in the dedicated send test below)
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'negotiating' });
    await mockApi(page, emailApiRoutes(proposal));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const correosTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Comunicación', exact: true });
    await expect(correosTab).toBeVisible({ timeout: 15000 });
  });

  test('branded email composer renders sections editor', {
    tag: [...ADMIN_SEND_BRANDED_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'negotiating' });
    await mockApi(page, emailApiRoutes(proposal));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const correosTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Comunicación', exact: true });
    await expect(correosTab).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'communication', 'emails');

    await expect(page.locator('input[placeholder*="Asunto"]')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Secciones del correo')).toContainText('Secciones del correo');
    // Scope to the composer's add-section button: the proposal Sections tab also
    // renders an "＋ Agregar sección" control, so match the composer's exact name.
    await expect(page.getByRole('button', { name: 'Agregar sección', exact: true })).toBeVisible();
  });

  test('sending branded email calls POST branded-email/send/ and shows success toast', {
    tag: [...ADMIN_SEND_BRANDED_EMAIL, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'negotiating' });
    let sendCalled = false;
    let sendBody = '';
    await mockApi(page, emailApiRoutesWithSend(proposal, 'branded-email', ({ route }) => {
      sendCalled = true;
      sendBody = route.request().postData() || '';
    }));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const correosTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Comunicación', exact: true });
    await expect(correosTab).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'communication', 'emails');

    // Switch from the default "Seguimiento" (proposal) mode to "General" (branded).
    await page.getByRole('button', { name: 'General' }).click();

    const toInput = page.getByTestId('proposal-email-to');
    await toInput.fill('stakeholder@example.com');
    await toInput.press('Enter');
    await page.getByTestId('proposal-email-show-cc').click();
    const ccInput = page.getByTestId('proposal-email-cc');
    await ccInput.fill('copy@example.com');
    await ccInput.press('Enter');
    await page.getByPlaceholder('Asunto del correo').fill('Aviso general de la propuesta');
    await page.getByPlaceholder('Escribe el contenido de esta sección...').fill('Contenido del correo de marca.');

    await Promise.all([
      page.waitForResponse((r) => r.url().includes(`proposals/${PROPOSAL_ID}/branded-email/send/`)),
      page.getByRole('button', { name: 'Enviar correo' }).click(),
    ]);

    expect(sendCalled).toEqual(true);
    expect(sendBody).toContain('client@emailtest.com');
    expect(sendBody).toContain('stakeholder@example.com');
    expect(sendBody).toContain('copy@example.com');
    await expect(page.getByText('Correo enviado correctamente.')).toContainText('Correo enviado correctamente.', { timeout: 5000 });
  });

  test('branded email reports a server-side send failure', {
    tag: [...ADMIN_SEND_BRANDED_EMAIL, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'negotiating' });
    await mockApi(page, emailApiRoutesWithSend(
      proposal,
      'branded-email',
      () => {},
      { status: 502, contentType: 'application/json', body: JSON.stringify({ error: 'SMTP unavailable' }) },
    ));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'communication', 'emails');
    await page.getByRole('button', { name: 'General' }).click();
    await page.getByPlaceholder('Asunto del correo').fill('Aviso general');
    await page.getByPlaceholder('Escribe el contenido de esta sección...').fill('Contenido listo para enviar.');

    await page.getByRole('button', { name: 'Enviar correo' }).click();

    await expect(page.getByText('Error al enviar el correo. Intenta de nuevo.')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Admin Proposal Email — Proposal Mode', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8700, role: 'admin', is_staff: true },
    });
  });

  test('proposal email tab is visible for sent proposal', {
    tag: [...ADMIN_SEND_PROPOSAL_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (checks the Correos tab's status-gated visibility for a sent proposal; the send action itself is driven in the dedicated send test below)
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'sent' });
    await mockApi(page, emailApiRoutes(proposal));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const correosTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Comunicación', exact: true });
    await expect(correosTab).toBeVisible({ timeout: 15000 });
  });

  test('draft proposal exposes Correos with the initial-message editor', {
    tag: [...ADMIN_SEND_PROPOSAL_EMAIL, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposal edit view is the canonical entry point for its Correos tab)
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'draft' });
    await mockApi(page, emailApiRoutes(proposal));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const correosTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Comunicación', exact: true });
    await expect(correosTab).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'communication', 'emails');
    await expect(page.getByTestId('proposal-email-intro-card')).toBeVisible();
    await expect(page.getByTestId('proposal-email-intro')).toHaveValue(proposal.email_intro);
    await expect(page.getByText('El historial y los correos de seguimiento aparecerán después del primer envío.')).toBeVisible();
  });

  test('sending proposal follow-up email calls POST proposal-email/send/ and shows success toast', {
    tag: [...ADMIN_SEND_PROPOSAL_EMAIL, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'sent' });
    let sendCalled = false;
    let sendBody = '';
    await mockApi(page, emailApiRoutesWithSend(proposal, 'proposal-email', ({ route }) => {
      sendCalled = true;
      sendBody = route.request().postData() || '';
    }));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const correosTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Comunicación', exact: true });
    await expect(correosTab).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'communication', 'emails');

    // Default mode is "Seguimiento" (proposal-email) — no mode switch needed.
    const toInput = page.getByTestId('proposal-email-to');
    await toInput.fill('decision-maker@example.com');
    await toInput.press('Enter');
    await page.getByTestId('proposal-email-show-cc').click();
    const ccInput = page.getByTestId('proposal-email-cc');
    await ccInput.fill('advisor@example.com');
    await ccInput.press('Enter');
    await page.getByPlaceholder('Asunto del correo').fill('Seguimiento de tu propuesta');
    await page.getByPlaceholder('Escribe el contenido de esta sección...').fill('Quedamos atentos a tu decisión.');

    await Promise.all([
      page.waitForResponse((r) => r.url().includes(`proposals/${PROPOSAL_ID}/proposal-email/send/`)),
      page.getByRole('button', { name: 'Enviar correo' }).click(),
    ]);

    expect(sendCalled).toEqual(true);
    expect(sendBody).toContain('client@emailtest.com');
    expect(sendBody).toContain('decision-maker@example.com');
    expect(sendBody).toContain('advisor@example.com');
    await expect(page.getByText('Correo enviado correctamente.')).toContainText('Correo enviado correctamente.', { timeout: 5000 });
  });

  test('proposal follow-up reports a server-side send failure', {
    tag: [...ADMIN_SEND_PROPOSAL_EMAIL, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    test.setTimeout(60_000);
    const proposal = makeProposal({ status: 'sent' });
    await mockApi(page, emailApiRoutesWithSend(
      proposal,
      'proposal-email',
      () => {},
      { status: 502, contentType: 'application/json', body: JSON.stringify({ error: 'SMTP unavailable' }) },
    ));

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'communication', 'emails');
    await page.getByPlaceholder('Asunto del correo').fill('Seguimiento');
    await page.getByPlaceholder('Escribe el contenido de esta sección...').fill('Mensaje listo para enviar.');

    await page.getByRole('button', { name: 'Enviar correo' }).click();

    await expect(page.getByText('Error al enviar el correo. Intenta de nuevo.')).toBeVisible({ timeout: 5000 });
  });
});
