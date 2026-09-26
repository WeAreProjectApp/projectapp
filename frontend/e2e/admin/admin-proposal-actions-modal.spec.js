/**
 * E2E tests for the admin proposal actions modal.
 *
 * Covers: opening the modal from listing, verifying action items render
 * with icons and info tooltips, conditional send/resend visibility.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_ACTIONS_MODAL } from '../helpers/flow-tags.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

const mockDraftProposal = {
  id: 1,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'Actions Modal Test',
  client_name: 'Test Client',
  client_email: 'client@test.com',
  email_intro: 'Esta propuesta centraliza la operación para que Test Client reduzca reprocesos.',
  client_phone: '+573001234567',
  status: 'draft',
  language: 'es',
  total_investment: '5000000',
  currency: 'COP',
  view_count: 0,
  heat_score: 5,
  sent_at: null,
  is_active: true,
  created_at: '2026-03-01T12:00:00Z',
};

const mockSentProposal = {
  ...mockDraftProposal,
  id: 2,
  uuid: '22222222-2222-2222-2222-222222222222',
  status: 'sent',
  sent_at: '2026-03-02T12:00:00Z',
};

function buildMockHandler(proposals) {
  return async ({ apiPath }) => {
    if (apiPath === 'auth/check/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
    }
    if (apiPath === 'proposals/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposals) };
    }
    if (apiPath === 'proposals/dashboard/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ total: 2, conversion_rate: 50 }) };
    }
    if (apiPath === 'proposals/alerts/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    return null;
  };
}

test.describe('Admin Proposal Actions Modal', () => {
  test.describe.configure({ timeout: 60_000 });

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8300, role: 'admin', is_staff: true },
    });
  });

  test('clicking actions button opens modal with proposal title', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler([mockDraftProposal]));
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Test Client')).toBeVisible({ timeout: 15000 });

    const listUrl = page.url();
    const actionsBtn = page.getByTestId('proposal-actions-1');
    await actionsBtn.click();

    await expect(page).toHaveURL(listUrl);
    await expect(page.getByText('Editar propuesta')).toBeVisible({ timeout: 3000 });
  });

  test('renders the leading menu control track', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display contract: control order, blank heading and fixed width are the observable outcome)
    // quality: allow-deep-link (the list navigation path is covered by its flow; this test isolates table layout)
    await mockApi(page, buildMockHandler([mockDraftProposal]));
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Test Client')).toBeVisible({ timeout: 15000 });
    const actionsHeader = page.getByTestId('proposal-actions-header');
    const leadingHeaders = await actionsHeader.evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 3).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
        hasCheckbox: Boolean(cell.querySelector('input[type="checkbox"]')),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: null, label: null, text: '', hasCheckbox: true },
      { testId: 'proposal-actions-header', label: 'Acciones', text: '', hasCheckbox: false },
      { testId: null, label: null, text: 'Cliente', hasCheckbox: false },
    ]);
    await expect(actionsHeader).toHaveCSS('width', '56px');
  });

  // Bug caught: the fixed layout kept the share of the columns a phone hides
  // and the visible ones stopped short of a blank band.
  test('the proposal table leaves no blank band on a phone', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the list navigation path is covered by its flow; this test isolates table layout)
    await page.setViewportSize({ width: 412, height: 915 });
    await mockApi(page, buildMockHandler([mockDraftProposal]));
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    const actionsBtn = page.getByTestId('proposal-actions-1');
    await expect(actionsBtn).toBeVisible({ timeout: 15000 });
    await expectNoBlankBand(page.getByTestId('proposal-actions-cell-1').locator('xpath=ancestor::table'));

    await actionsBtn.click();
    await expect(page.getByText('Editar propuesta')).toBeVisible({ timeout: 3000 });
  });

  test('keeps horizontal pan available from the action control', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (Input.dispatchTouchEvent is the trusted user gesture; the analyzer does not classify CDP calls)
    // quality: allow-deep-link (the navigation path is covered separately; this test isolates the wrapper's touch behavior)
    await page.setViewportSize({ width: 1195, height: 835 });
    await mockApi(page, buildMockHandler([mockDraftProposal]));
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    const actionsBtn = page.getByTestId('proposal-actions-1');
    await expect(actionsBtn).toBeVisible({ timeout: 15000 });
    const scroller = page.getByTestId('proposal-actions-cell-1').locator('xpath=ancestor::div[contains(@class,"overflow-x-auto")][1]');
    await scroller.evaluate((element) => { element.style.width = '18rem'; });
    await expect.poll(() => scroller.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);

    const box = await actionsBtn.boundingBox();
    expect(box).not.toBeNull();
    const client = await page.context().newCDPSession(page);
    const start = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchStart',
      touchPoints: [{ ...start, radiusX: 2, radiusY: 2, force: 1 }],
    });
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ ...start, x: start.x - 120, radiusX: 2, radiusY: 2, force: 1 }],
    });
    await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });

    await expect.poll(() => scroller.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    await expect(page.getByText('Editar propuesta')).toHaveCount(0);
  });

  test('draft proposal shows edit, preview, send, copy, whatsapp, duplicate, toggle, delete actions', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler([mockDraftProposal]));
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    await page.getByText('Test Client').waitFor({ state: 'visible', timeout: 15000 });

    const actionsBtn = page.getByTestId('proposal-actions-1');
    await actionsBtn.waitFor({ state: 'visible', timeout: 5000 });
    await actionsBtn.click();

    // Verify core actions are present
    await expect(page.getByText('Editar propuesta')).toBeVisible();
    await expect(page.getByText('Ver preview')).toBeVisible();
    await expect(page.getByText('Enviar al cliente')).toBeVisible();
    await expect(page.getByText('Copiar enlace')).toBeVisible();
    await expect(page.getByText('Enviar por WhatsApp')).toBeVisible();
    await expect(page.getByText('Duplicar propuesta')).toBeVisible();
    await expect(page.getByText('Eliminar')).toBeVisible();
  });

  test('sent proposal shows resend instead of send', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler([mockSentProposal]));
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Test Client')).toBeVisible({ timeout: 15000 });

    const actionsBtn = page.getByTestId('proposal-actions-2');
    await actionsBtn.click();

    // Should show re-send, not send
    await expect(page.getByText('Re-enviar email')).toBeVisible();
    await expect(page.getByText('Enviar al cliente')).not.toBeVisible();
  });

  test('closing modal by clicking backdrop', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler([mockDraftProposal]));
    await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Test Client')).toBeVisible({ timeout: 15000 });

    const actionsBtn = page.getByTestId('proposal-actions-1');
    await actionsBtn.click();
    await expect(page.getByText('Editar propuesta')).toBeVisible({ timeout: 5000 });

    // Overlay uses @click.self on fixed inset-0; avoid page.locator('.fixed').first() (sidebar wins).
    const modalOverlay = page.locator('div.fixed.inset-0').filter({
      has: page.getByRole('heading', { level: 3, name: mockDraftProposal.title }),
    });
    await modalOverlay.click({ position: { x: 8, y: 8 } });

    await expect(page.getByText('Editar propuesta')).not.toBeVisible({ timeout: 5000 });
  });
});

/**
 * The edit page (/panel/proposals/:id/edit) mounts a different actions modal
 * (BusinessProposal/admin/ProposalActionsModal.vue) whose "Lanzar a Plataforma"
 * action was widened to show for `negotiating` proposals, not only `accepted`.
 */
const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

const mockEditProposal = (overrides = {}) => ({
  id: 3,
  uuid: '33333333-3333-3333-3333-333333333333',
  title: 'Launch Action Proposal',
  client_name: 'Nego Client',
  client_email: 'nego@test.com',
  email_intro: 'Esta propuesta organiza el lanzamiento para que Nego Client llegue antes a producción.',
  status: 'negotiating',
  language: 'es',
  total_investment: '8000000',
  currency: 'COP',
  discount_percent: 0,
  available_transitions: ['accepted', 'rejected'],
  platform_onboarding_completed_at: null,
  view_count: 4,
  sent_at: '2026-03-02T12:00:00Z',
  expires_at: futureDate,
  is_active: true,
  sections: [
    { id: 30, section_type: 'greeting', title: 'Bienvenido', order: 0, is_enabled: true, content_json: { clientName: 'Nego Client' } },
  ],
  requirement_groups: [],
  ...overrides,
});

function setupEditMocks(page, proposal) {
  return mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === `proposals/${proposal.id}/detail/`) return json(proposal);
    return null;
  });
}

test.describe('Proposal Actions Modal — edit page launch action', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8300, role: 'admin', is_staff: true },
    });
  });

  test('launch-to-platform action is available while the proposal is negotiating', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin'],
  }, async ({ page }) => {
    const proposal = mockEditProposal({ status: 'negotiating' });
    await setupEditMocks(page, proposal);

    await page.goto(`/panel/proposals/${proposal.id}/edit`, { waitUntil: 'domcontentloaded' });

    await page.getByTestId('proposal-actions-menu').click();

    const launch = page.getByTestId('proposal-action-launch');
    await expect(launch).toBeVisible({ timeout: 15000 });
    await expect(launch).toContainText('Lanzar a Plataforma');
  });

  test('public preview action opens the proposal view', {
    tag: ['@outcome:success', ...ADMIN_PROPOSAL_ACTIONS_MODAL, '@role:admin'],
  }, async ({ page }) => {
    const proposal = mockEditProposal({ status: 'draft' });
    await setupEditMocks(page, proposal);
    await page.context().route(
      new RegExp(`/api/proposals/${proposal.uuid}/$`),
      (route) => route.fulfill(json(proposal)),
    );

    await page.goto(`/panel/proposals/${proposal.id}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('proposal-actions-menu').click();

    const previewPagePromise = page.waitForEvent('popup');
    await page.getByTestId('proposal-action-preview').click();
    const previewPage = await previewPagePromise;

    await expect(previewPage).toHaveURL(
      new RegExp(`/proposal/${proposal.uuid}\\?preview=1$`),
    );
    await expect(previewPage.getByText(/MODO PREVIEW|PREVIEW MODE/)).toBeVisible();
    await expect(previewPage.getByText('500', { exact: true })).toHaveCount(0);
    await previewPage.close();
  });
});
