/**
 * Admin controls for the proposal welcome video.
 *
 * Catches regressions where a global setting silently fails, where an
 * individual preference is lost on reload, or where an unavailable global
 * setting hides the reason from the administrator.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_PROPOSAL_EXPLAINER_PREFERENCE,
  ADMIN_PROPOSAL_EXPLAINER_VISIBILITY,
} from '../helpers/flow-tags.js';

const PROPOSAL_ID = 961;
const proposal = {
  id: PROPOSAL_ID,
  uuid: 'f0111111-1111-1111-1111-111111111111',
  title: 'Control de video E2E',
  client_name: 'Cliente de controles',
  client_email: 'cliente@example.com',
  language: 'es',
  status: 'draft',
  is_active: true,
  show_contract_terms: true,
  show_explainer_video: true,
  total_investment: '5000000',
  currency: 'COP',
  sections: [{
    id: 9611,
    section_type: 'technical_document',
    title: 'Detalle técnico',
    order: 0,
    is_enabled: true,
    content_json: { purpose: 'Detalle técnico de controles E2E', stack: [], epics: [] },
  }],
  requirement_groups: [],
};

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

function buildHandler(state, { settingsStatus = 200, proposalStatus = 200, onSettingsPatch = () => {}, onProposalPatch = () => {} } = {}) {
  return async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json(200, { user: { username: 'e2e-admin', is_staff: true } });
    if (apiPath === 'proposals/' && method === 'GET') return json(200, [state.proposal]);
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return json(200, state.proposal);
    if (apiPath === 'proposals/dashboard/') return json(200, { total_proposals: 1, by_status: { draft: 1 }, monthly_trend: [] });
    if (apiPath === 'proposals/alerts/') return json(200, []);
    if (apiPath === 'explainer-videos/admin/settings/' && method === 'GET') return json(200, state.settings);
    if (apiPath === 'explainer-videos/admin/settings/update/' && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      onSettingsPatch(payload);
      if (settingsStatus !== 200) return json(settingsStatus, { detail: 'temporary settings failure' });
      state.settings = { ...state.settings, ...payload };
      return json(200, state.settings);
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/update/` && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      onProposalPatch(payload);
      if (proposalStatus !== 200) return json(proposalStatus, { detail: 'temporary proposal failure' });
      state.proposal = { ...state.proposal, ...payload };
      return json(200, state.proposal);
    }
    return null;
  };
}

async function authenticate(page) {
  await setAuthLocalStorage(page, {
    token: 'e2e-admin-token',
    userAuth: { id: 9610, role: 'admin', is_staff: true },
  });
}

async function openProposalSettings(page) {
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Propuestas', exact: true }).click({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/panel\/proposals$/);
  await expect(page.getByRole('heading', { name: 'Propuestas' })).toBeVisible({ timeout: 20_000 });
  await page.getByTestId('filter-tabs-config').click();
  await expect(page.getByTestId('view-settings-panel')).toBeVisible();
}

async function openProposalGeneral(page) {
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Propuestas', exact: true }).click({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/panel\/proposals$/);
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click({ timeout: 20_000 });
  await expect(page).toHaveURL(new RegExp(`/panel/proposals/${PROPOSAL_ID}/edit`));
  await expect(page.getByTestId('proposal-explainer-preference')).toBeVisible({ timeout: 20_000 });
}

function freshState(overrides = {}) {
  return {
    proposal: { ...proposal, ...(overrides.proposal || {}) },
    settings: {
      show_additional_modules_video: true,
      show_financing_video: true,
      show_proposal_video: true,
      ...(overrides.settings || {}),
    },
  };
}

test.describe('Admin proposal welcome video visibility', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => authenticate(page));

  test('Configuraciones displays the compact welcome-video preview and current global state', {
    tag: [...ADMIN_PROPOSAL_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const state = freshState();
    await mockApi(page, buildHandler(state));
    // quality: allow-deep-link (authenticated panel entry is setup; the test reaches Configuraciones through the sidebar and tab UI)
    await openProposalSettings(page);

    await expect(page.getByTestId('admin-proposal-explainer-card')).toContainText('Proposal welcome video');
    await expect(page.getByTestId('admin-proposal-explainer-visibility-toggle')).toHaveAttribute('aria-checked', 'true');
  });

  test('playing the compact preview starts the real video media', {
    tag: [...ADMIN_PROPOSAL_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = freshState();
    await mockApi(page, buildHandler(state));
    await openProposalSettings(page);

    await page.getByTestId('admin-proposal-explainer-play').click();
    const player = page.getByTestId('admin-proposal-explainer-player');
    await expect(player).toHaveAttribute('aria-label', 'Proposal welcome video');
    await expect.poll(() => player.evaluate((element) => !element.paused)).toBe(true);
  });

  test('global switch saves the exact false value and survives a reload', {
    tag: [...ADMIN_PROPOSAL_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = freshState();
    let savedPayload = null;
    await mockApi(page, buildHandler(state, { onSettingsPatch: (payload) => { savedPayload = payload; } }));
    await openProposalSettings(page);

    const toggle = page.getByTestId('admin-proposal-explainer-visibility-toggle');
    await toggle.click();
    await expect(page.getByText('Video hidden for all proposals. Individual preferences are preserved.')).toBeVisible({ timeout: 10_000 });
    expect(savedPayload).toEqual({ show_proposal_video: false });
    await expect(toggle).toHaveAttribute('aria-checked', 'false');

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('filter-tabs-config')).toBeVisible({ timeout: 20_000 });
    await page.getByTestId('filter-tabs-config').click();
    await expect(page.getByTestId('admin-proposal-explainer-visibility-toggle')).toHaveAttribute('aria-checked', 'false');
  });

  test('failed global save restores the enabled switch and tells the administrator', {
    tag: [...ADMIN_PROPOSAL_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const state = freshState();
    await mockApi(page, buildHandler(state, { settingsStatus: 500 }));
    await openProposalSettings(page);

    const toggle = page.getByTestId('admin-proposal-explainer-visibility-toggle');
    await toggle.click();
    await expect(page.getByText('We could not save video visibility. Please try again.')).toBeVisible({ timeout: 10_000 });
    await expect(toggle).toHaveAttribute('aria-checked', 'true');
  });
});

test.describe('Admin proposal welcome video preference', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => authenticate(page));

  test('individual switch saves false and remains false after reopening the proposal', {
    tag: [...ADMIN_PROPOSAL_EXPLAINER_PREFERENCE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = freshState();
    let savedPayload = null;
    await mockApi(page, buildHandler(state, { onProposalPatch: (payload) => { savedPayload = payload; } }));
    await openProposalGeneral(page);

    const toggle = page.getByTestId('proposal-explainer-toggle');
    await expect(toggle).toHaveAttribute('aria-checked', 'true');
    await toggle.click();
    await expect(page.getByText('Preferencia del video guardada.')).toBeVisible({ timeout: 10_000 });
    expect(savedPayload).toEqual({ show_explainer_video: false });
    await expect(toggle).toHaveAttribute('aria-checked', 'false');

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('proposal-explainer-toggle')).toHaveAttribute('aria-checked', 'false', { timeout: 20_000 });
  });

  test('failed individual save restores the previous preference and reports the error', {
    tag: [...ADMIN_PROPOSAL_EXPLAINER_PREFERENCE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const state = freshState();
    await mockApi(page, buildHandler(state, { proposalStatus: 500 }));
    await openProposalGeneral(page);

    const toggle = page.getByTestId('proposal-explainer-toggle');
    await toggle.click();
    await expect(page.getByText('No se pudo guardar la visibilidad del video. Intenta de nuevo.')).toBeVisible({ timeout: 10_000 });
    await expect(toggle).toHaveAttribute('aria-checked', 'true');
  });

  test('global disabled setting explains why an enabled individual preference cannot appear', {
    tag: [...ADMIN_PROPOSAL_EXPLAINER_PREFERENCE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const state = freshState({ settings: { show_proposal_video: false } });
    await mockApi(page, buildHandler(state));
    // quality: allow-deep-link (authenticated panel entry is setup; the test reaches the proposal through sidebar and row UI)
    await openProposalGeneral(page);

    await expect(page.getByTestId('proposal-explainer-toggle')).toHaveAttribute('aria-checked', 'true');
    await expect(page.getByTestId('proposal-explainer-status'))
      .toHaveText('Oculto: el control general está apagado en Propuestas → Configuraciones.');
  });
});
