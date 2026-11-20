/**
 * E2E tests for the admin diagnostic defaults configuration flow.
 *
 * FLOW: admin-diagnostic-defaults-config
 * Covers: render General tab with hardcoded fallback, save edited percentages,
 *         reset confirmation modal, back link.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DIAGNOSTIC_DEFAULTS_CONFIG } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const HARDCODED_SECTIONS = [
  {
    section_type: 'purpose',
    title: '🎯 Propósito',
    order: 0,
    is_enabled: true,
    visibility: 'both',
    content_json: { heading: 'Propósito' },
  },
  {
    section_type: 'cost',
    title: '💰 Inversión',
    order: 5,
    is_enabled: true,
    visibility: 'final',
    content_json: { amount: 0 },
  },
];

const HARDCODED_FALLBACK = {
  id: null,
  language: 'es',
  sections_json: HARDCODED_SECTIONS,
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

const SAVED_CONFIG = {
  ...HARDCODED_FALLBACK,
  id: 1,
  payment_initial_pct: 70,
  payment_final_pct: 30,
  default_duration_label: '4 semanas',
  default_investment_amount: '1500000.00',
  created_at: '2026-04-18T10:00:00Z',
  updated_at: '2026-04-18T10:00:00Z',
};

function buildHandler({ apiPath, method }, { saved = false } = {}) {
  if (apiPath === 'auth/check/') {
    return {
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
    };
  }
  if (apiPath === 'diagnostics/defaults/' && method === 'GET') {
    return {
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(saved ? SAVED_CONFIG : HARDCODED_FALLBACK),
    };
  }
  if (apiPath === 'diagnostics/defaults/' && method === 'PUT') {
    return {
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SAVED_CONFIG),
    };
  }
  if (apiPath === 'diagnostics/defaults/reset/' && method === 'POST') {
    return {
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'reset', deleted: true }),
    };
  }
  if (apiPath === 'diagnostics/' && method === 'GET') {
    return {
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    };
  }
  return null;
}

test.describe('Admin Diagnostic Defaults Config', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true },
    });
  });

  test('renders General tab with the 60/40 hardcoded fallback', {
    tag: [...ADMIN_DIAGNOSTIC_DEFAULTS_CONFIG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/diagnostics/defaults', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'Valores por Defecto' })).toBeVisible();

    const initialInput = page.getByTestId('defaults-payment-initial');
    const finalInput = page.getByTestId('defaults-payment-final');
    await expect(initialInput).toHaveValue('60');
    await expect(finalInput).toHaveValue('40');
    await expect(page.getByRole('combobox', { name: 'Moneda', exact: true })).toHaveText('COP');
    await expect(page.getByTestId('defaults-expiration-days')).toHaveValue('21');
  });

  test('auto-syncs payment percentages to sum 100', {
    tag: [...ADMIN_DIAGNOSTIC_DEFAULTS_CONFIG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/diagnostics/defaults', { waitUntil: 'domcontentloaded' });

    const initialInput = page.getByTestId('defaults-payment-initial');
    await initialInput.waitFor();
    await initialInput.fill('70');
    await initialInput.dispatchEvent('input');

    await expect(page.getByTestId('defaults-payment-final')).toHaveValue('30');
    await expect(page.getByTestId('defaults-payment-warning')).toBeHidden();
  });

  test('save button persists edits and applies the response', {
    tag: [...ADMIN_DIAGNOSTIC_DEFAULTS_CONFIG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let getCalls = 0;
    await mockApi(page, async (info) => {
      if (info.apiPath === 'diagnostics/defaults/' && info.method === 'GET') {
        getCalls += 1;
      }
      return buildHandler(info);
    });
    await page.goto('/panel/diagnostics/defaults', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('defaults-payment-initial').waitFor();
    await page.getByTestId('defaults-payment-initial').fill('70');
    await page.getByTestId('defaults-payment-initial').dispatchEvent('input');
    await page.getByTestId('defaults-duration-label').fill('4 semanas');

    const initialGetCount = getCalls;
    await page.getByTestId('defaults-save-btn').click();

    await expect(page.getByTestId('defaults-payment-initial')).toHaveValue('70');
    await expect(page.getByTestId('defaults-duration-label')).toHaveValue('4 semanas');
    expect(getCalls).toBe(initialGetCount); // PUT response is applied directly, no refetch
  });

  test('reset opens the confirm modal', {
    tag: [...ADMIN_DIAGNOSTIC_DEFAULTS_CONFIG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/diagnostics/defaults', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('defaults-reset-btn').waitFor();
    await page.getByTestId('defaults-reset-btn').click();

    await expect(page.getByRole('heading', { name: 'Restablecer valores por defecto' })).toBeVisible();
    await expect(page.getByTestId('confirm-modal-confirm')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cancelar' })).toBeVisible();
  });

  test('back link navigates to diagnostics list', {
    tag: [...ADMIN_DIAGNOSTIC_DEFAULTS_CONFIG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async (info) => buildHandler(info));
    await page.goto('/panel/diagnostics/defaults', { waitUntil: 'domcontentloaded' });

    await page.getByRole('link', { name: /Volver a Diagnósticos/i }).click();
    // Pre-click URL is /panel/diagnostics/defaults, which the plain
    // '**/panel/diagnostics**' pattern already matches — negative lookahead
    // excludes the defaults sub-route so this only passes once the SPA
    // actually navigates to the diagnostics list.
    await page.waitForURL(/\/panel\/diagnostics(\?|$|\/(?!defaults))/);
  });
});
