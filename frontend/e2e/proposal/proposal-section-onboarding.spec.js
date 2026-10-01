/**
 * E2E tests for proposal section onboarding tooltips.
 *
 * @flow:proposal-section-onboarding
 * Covers: multi-step onboarding overlay on first visit, step progression,
 * skip/dismiss behavior, localStorage suppression on repeat visits,
 * investment onboarding trigger on section navigation.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_SECTION_ONBOARDING } from '../helpers/flow-tags.js';

const MOCK_UUID = 'cd111111-1111-1111-1111-111111111111';

function _buildSection(id, type, title, order, contentJson = {}) {
  return {
    id,
    section_type: type,
    title,
    order,
    is_enabled: true,
    is_wide_panel: type === 'functional_requirements',
    content_json: contentJson,
  };
}

const mockProposal = {
  id: 60,
  uuid: MOCK_UUID,
  title: 'Onboarding Test Proposal',
  client_name: 'Onboarding Client',
  client_email: 'onboard@test.com',
  language: 'es',
  status: 'sent',
  total_investment: '7000000',
  currency: 'COP',
  view_count: 1,
  sent_at: '2026-01-01T00:00:00Z',
  expires_at: '2026-06-01T00:00:00Z',
  sections: [
    _buildSection(601, 'greeting', '👋 Bienvenido', 0, {
      clientName: 'Onboarding Client',
      inspirationalQuote: 'Design is intelligence made visible.',
    }),
    _buildSection(602, 'executive_summary', '🧾 Resumen ejecutivo', 1, {
      index: '1', title: 'Resumen ejecutivo',
      paragraphs: ['Solución diseñada para escalar.'],
      highlightsTitle: 'Incluye', highlights: ['Diseño UX'],
    }),
    _buildSection(603, 'investment', '💰 Inversión', 2, {
      index: '2', title: 'Inversión', introText: '', totalInvestment: '7000000', currency: 'COP',
      whatsIncluded: [], paymentOptions: [], paymentMethods: [], valueReasons: [],
      modules: [
        { id: 'mod1', name: 'Módulo Web', price: 5000000, included: true, is_required: true },
        { id: 'mod2', name: 'Módulo App', price: 2000000, included: false, is_required: false },
      ],
    }),
    _buildSection(604, 'functional_requirements', '🧩 Requerimientos', 3, {
      index: '3', title: 'Requerimientos', intro: '',
      groups: [{ id: 'views', icon: '🖥️', title: 'Vistas', description: '', items: [] }],
      additionalModules: [],
    }),
  ],
  requirement_groups: [],
};

function buildMockHandler() {
  return async ({ apiPath }) => {
    if (apiPath === `proposals/${MOCK_UUID}/`) {
      return {
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockProposal),
      };
    }
    if (apiPath === `proposals/${MOCK_UUID}/record-view/`) {
      return { status: 200, contentType: 'application/json', body: '{}' };
    }
    if (apiPath.includes('/track/')) {
      return { status: 200, contentType: 'application/json', body: '{}' };
    }
    return null;
  };
}

test.describe('Proposal Section Onboarding', () => {
  test.setTimeout(60_000);

  test('first visit shows onboarding overlay with step 1', {
    tag: [...PROPOSAL_SECTION_ONBOARDING, '@role:guest'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (state-on-page-load test: first-visit overlay / localStorage suppression — the navigation IS the trigger; interactive coverage lives in the other 4 tests of this file)
    // Do NOT set proposal_onboarding_seen — simulate first visit
    await mockApi(page, buildMockHandler());
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    // Onboarding backdrop should be visible
    const backdrop = page.getByTestId('onboarding-backdrop');
    await expect(backdrop).toBeVisible({ timeout: 15000 });

    // First step title should be visible (dark mode toggle step)
    await expect(page.getByRole('heading', { name: 'Modo claro y oscuro' })).toBeVisible({ timeout: 5000 });

    // Progress indicator should show "1/N"
    const progress = page.getByTestId('onboarding-step-progress');
    await expect(progress).toBeVisible({ timeout: 5000 });
    await expect(progress).toHaveText(/^1\//);
  });

  test('clicking "Siguiente" advances to step 2', {
    tag: [...PROPOSAL_SECTION_ONBOARDING, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler());
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    // Wait for onboarding to appear
    await expect(page.getByTestId('onboarding-backdrop')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('heading', { name: 'Modo claro y oscuro' })).toBeVisible({ timeout: 5000 });

    // Click the onboarding next button
    await page.getByTestId('onboarding-next-btn').click({ timeout: 5000 });

    // Step 2: section index
    await expect(page.getByText('Índice de secciones')).toBeVisible({ timeout: 5000 });
    const progress = page.getByTestId('onboarding-step-progress');
    await expect(progress).toHaveText(/^2\//);
  });

  test('clicking "Omitir" dismisses onboarding overlay', {
    tag: [...PROPOSAL_SECTION_ONBOARDING, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler());
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    await expect(page.getByTestId('onboarding-backdrop')).toBeVisible({ timeout: 15000 });

    // Click skip
    await page.getByRole('button', { name: 'Omitir' }).click();

    // Backdrop should disappear
    await expect(page.getByTestId('onboarding-backdrop')).not.toBeVisible();
  });

  test('completing onboarding sets localStorage flag', {
    tag: [...PROPOSAL_SECTION_ONBOARDING, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler());
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    await expect(page.getByTestId('onboarding-backdrop')).toBeVisible({ timeout: 15000 });

    // Click skip to complete quickly
    await page.getByRole('button', { name: 'Omitir' }).click();
    await expect(page.getByTestId('onboarding-backdrop')).not.toBeVisible();

    // Check localStorage
    const flag = await page.evaluate(() => localStorage.getItem('proposal_onboarding_seen'));
    expect(flag).toBe('true');
  });

  test('repeat visit does NOT show onboarding overlay', {
    tag: [...PROPOSAL_SECTION_ONBOARDING, '@role:guest'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (state-on-page-load test: first-visit overlay / localStorage suppression — the navigation IS the trigger; interactive coverage lives in the other 4 tests of this file)
    // Set localStorage to simulate repeat visit
    await page.addInitScript(() => {
      localStorage.setItem('proposal_onboarding_seen', 'true');
    });

    await mockApi(page, buildMockHandler());
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    // Verify proposal loaded, then check onboarding is absent
    await expect(page.locator('[data-section-type="greeting"]')).toBeVisible({ timeout: 15000 });

    // Backdrop should NOT be visible
    await expect(page.getByTestId('onboarding-backdrop')).not.toBeVisible();
  });

  // Catches regressions where the detailed investment journey either skips the
  // additional-modules guidance or reintroduces a calculator price into it.
  test('detailed investment guidance explains saving module interest without a price', {
    tag: [...PROPOSAL_SECTION_ONBOARDING, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await page.addInitScript((uuid) => {
      localStorage.setItem('proposal_onboarding_seen', 'true');
      localStorage.removeItem(`investment_onboarding_seen_${uuid}`);
    }, MOCK_UUID);
    await mockApi(page, buildMockHandler());
    // quality: allow-deep-link (the guest receives this public proposal URL, then uses its gateway and section navigation)
    await page.goto(`/proposal/${MOCK_UUID}`, { waitUntil: 'domcontentloaded' });

    await page.getByTestId('gateway-detailed-card').click();
    await page.getByRole('button', { name: 'Abrir índice' }).click();
    await page.getByRole('navigation').getByRole('button', { name: /Inversión/ }).click();

    const tooltip = page.getByRole('heading', { name: 'Explora módulos adicionales' });
    await expect(tooltip).toHaveText('Explora módulos adicionales', { timeout: 20_000 });
    const explanation = page.getByText('Descubre módulos por categorías y guarda tu interés para conversar sobre ellos. La inversión y el alcance se acuerdan contigo.');
    await expect(explanation).toHaveText('Descubre módulos por categorías y guarda tu interés para conversar sobre ellos. La inversión y el alcance se acuerdan contigo.');
    await expect(explanation).not.toContainText(/[\d$]/);

    await page.getByRole('button', { name: 'Omitir' }).click();
    await expect(tooltip).toHaveCount(0);
  });

  test('last step shows "Entendido" button instead of "Siguiente"', {
    tag: [...PROPOSAL_SECTION_ONBOARDING, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler());
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    await expect(page.getByTestId('onboarding-backdrop')).toBeVisible({ timeout: 15000 });

    // Advance through all steps until the last one
    const progressEl = page.getByTestId('onboarding-step-progress');
    const nextBtn = page.getByTestId('onboarding-next-btn');
    const doneBtn = page.getByTestId('onboarding-done-btn');
    let reachedLastStep = false;
    let maxSteps = 10;

    while (maxSteps > 0) {
      maxSteps--;
      // Wait for either button to appear after transition completes
      await expect(nextBtn.or(doneBtn)).toBeVisible({ timeout: 5000 });

      if (await doneBtn.isVisible()) {
        reachedLastStep = true;
        await expect(doneBtn).toBeVisible({ timeout: 5000 });
        break;
      }

      // Remember current progress, click next, then wait for progress text to change
      const prevProgress = (await progressEl.textContent()).trim();
      // quality: allow-dispatchEvent (tooltip-pop out-in CSS transition causes instability/detach between steps)
      await nextBtn.dispatchEvent('click');
      await expect(progressEl).not.toHaveText(prevProgress, { timeout: 5000 });
    }

    expect(reachedLastStep).toBe(true);
  });
});
