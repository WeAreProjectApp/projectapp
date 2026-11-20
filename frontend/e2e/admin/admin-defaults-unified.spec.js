/**
 * E2E tests for the unified Defaults shell page.
 *
 * FLOW: admin-defaults-unified
 * Covers: default proposal mode, mode switch updates URL, direct diagnostic nav,
 *         back link per mode, redirects from old routes.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DEFAULTS_UNIFIED } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const PROPOSAL_DEFAULTS = {
  id: null,
  language: 'es',
  sections_json: [
    {
      section_type: 'greeting',
      title: '👋 Saludo',
      order: 0,
      is_wide_panel: false,
      content_json: { proposalTitle: '', clientName: '', inspirationalQuote: '' },
    },
  ],
  created_at: null,
  updated_at: null,
};

const DIAGNOSTIC_DEFAULTS = {
  id: null,
  language: 'es',
  sections_json: [],
  payment_initial_pct: 60,
  payment_final_pct: 40,
  default_currency: 'COP',
  default_investment_amount: null,
  default_duration_label: '',
  expiration_days: 21,
  reminder_days: 7,
  urgency_reminder_days: 14,
  created_at: null,
  updated_at: null,
};

function buildHandler({ apiPath, method }) {
  if (apiPath === 'auth/check/') {
    return {
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
    };
  }
  if (apiPath === 'proposals/defaults/' && method === 'GET') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(PROPOSAL_DEFAULTS) };
  }
  if (apiPath === 'diagnostics/defaults/' && method === 'GET') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(DIAGNOSTIC_DEFAULTS) };
  }
  if (apiPath === 'proposals/' && method === 'GET') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
  }
  if (apiPath === 'proposals/alerts/' && method === 'GET') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
  }
  if (apiPath === 'diagnostics/' && method === 'GET') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
  }
  if (apiPath === 'email-templates/' && method === 'GET') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
  }
  return null;
}

test.describe('Admin Unified Defaults Shell', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('defaults to proposal mode on direct navigation', {
    tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/defaults', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'Valores por Defecto' })).toBeVisible({ timeout: 25_000 });

    // Mode toggle renders twice with the same testId — once in the mobile
    // section (sm:hidden) and once in the desktop segmented pills (hidden sm:flex).
    // Filter by `:visible` so the assertion targets whichever is shown for the
    // current viewport instead of `.first()` (which always picks the mobile one,
    // hidden in the desktop CI viewport).
    const proposalBtn = page.locator('[data-testid="defaults-mode-proposal"]:visible');
    await expect(proposalBtn).toBeVisible();
    await expect(proposalBtn).toHaveClass(/text-text-brand/);

    const diagnosticBtn = page.locator('[data-testid="defaults-mode-diagnostic"]:visible');
    await expect(diagnosticBtn).not.toHaveClass(/text-text-brand/);
  });

  test('clicking Diagnóstico switch updates URL to ?mode=diagnostic', {
    tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/defaults', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'Valores por Defecto' })).toBeVisible({ timeout: 25_000 });
    await page.locator('[data-testid="defaults-mode-diagnostic"]:visible').click();

    await expect(page).toHaveURL(/mode=diagnostic/);
    await expect(page.locator('[data-testid="defaults-mode-diagnostic"]:visible')).toHaveClass(/text-text-brand/);
  });

  test('direct navigation to ?mode=diagnostic activates diagnostic mode', {
    tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/defaults?mode=diagnostic', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'Valores por Defecto' })).toBeVisible({ timeout: 25_000 });
    await expect(page.locator('[data-testid="defaults-mode-diagnostic"]:visible')).toHaveClass(/text-text-brand/);
    await expect(page.locator('[data-testid="defaults-mode-proposal"]:visible')).not.toHaveClass(/text-text-brand/);
  });

  for (const { mode, endpoint, defaults, section } of [
    {
      mode: 'proposal', endpoint: 'proposals/defaults/', defaults: PROPOSAL_DEFAULTS,
      section: PROPOSAL_DEFAULTS.sections_json[0],
    },
    {
      mode: 'diagnostic', endpoint: 'diagnostics/defaults/', defaults: DIAGNOSTIC_DEFAULTS,
      section: { section_type: 'radiography', title: 'Radiografía', visibility: 'public', order: 1, is_enabled: true },
    },
  ]) {
    test(`${mode} shows the effective system sections for an empty configuration`, {
      tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      await mockApi(page, async (request) => {
        if (request.apiPath !== endpoint) return buildHandler(request);
        return {
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ ...defaults, id: 269, sections_json: [], effective_sections_json: [section] }),
        };
      });
      await page.goto(`/es-co/panel/defaults?mode=${mode}`, { waitUntil: 'domcontentloaded' });
      const sections = page.getByRole('tab', { name: 'Secciones', exact: true });

      await sections.click();

      await expect(page.getByText(section.title, { exact: true })).toBeVisible();
      await expect(page.getByText('Plantilla del sistema', { exact: true }).filter({ visible: true })).toBeVisible();
    });
  }

  test('back link shows "Volver a Propuestas" in proposal mode', {
    tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/defaults', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('link', { name: /Volver a Propuestas/i })).toBeVisible();
  });

  test('back link shows "Volver a Diagnósticos" in diagnostic mode', {
    tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/defaults?mode=diagnostic', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('link', { name: /Volver a Diagnósticos/i })).toBeVisible();
  });

  test('/panel/proposals/defaults redirects to /panel/defaults?mode=proposal', {
    tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/proposals/defaults', { waitUntil: 'domcontentloaded' });

    await expect(page).toHaveURL(/\/panel\/defaults/);
    await expect(page).toHaveURL(/mode=proposal/);
  });

  test('/panel/diagnostics/defaults redirects to /panel/defaults?mode=diagnostic', {
    tag: [...ADMIN_DEFAULTS_UNIFIED, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/diagnostics/defaults', { waitUntil: 'domcontentloaded' });

    await expect(page).toHaveURL(/\/panel\/defaults/);
    await expect(page).toHaveURL(/mode=diagnostic/);
  });
});
