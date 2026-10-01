/**
 * E2E tests for discount badge visibility across multiple proposal sections.
 *
 * Covers discount badges in the investment section and ProposalClosing panel
 * when a proposal has an active discount.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_DISCOUNT_MULTI_SECTION } from '../helpers/flow-tags.js';

const MOCK_UUID = 'd7111111-1111-1111-1111-111111111111';

const mockProposalWithDiscount = {
  id: 1,
  uuid: MOCK_UUID,
  title: 'Discount Multi Section Test',
  client_name: 'Test Client',
  status: 'sent',
  language: 'es',
  total_investment: '10000000',
  currency: 'COP',
  discount_percent: 15,
  discounted_investment: '8500000',
  expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  sections: [
    {
      id: 1, section_type: 'greeting', title: 'Bienvenido', order: 0, is_enabled: true,
      content_json: { clientName: 'Test Client', inspirationalQuote: '' },
    },
    {
      id: 2, section_type: 'investment', title: 'Inversión', order: 1, is_enabled: true,
      content_json: {
        index: '2',
        title: 'Inversión',
        introText: 'Tu inversión incluye:',
        totalInvestment: '$10.000.000',
        currency: 'COP',
        whatsIncluded: [],
        paymentOptions: [{ label: 'Pago único', description: '$10.000.000' }],
        valueReasons: [],
      },
    },
    {
      id: 3, section_type: 'functional_requirements', title: 'Requerimientos', order: 2, is_enabled: true,
      content_json: {
        index: '3', title: 'Requerimientos Funcionales', intro: 'Detalle.',
        groups: [], additionalModules: [],
      },
    },
  ],
  requirement_groups: [],
};

const mockProposalNoDiscount = {
  ...mockProposalWithDiscount,
  discount_percent: 0,
  discounted_investment: null,
};

function setupMock(page, proposal) {
  return mockApi(page, async ({ apiPath }) => {
    if (apiPath === `proposals/${MOCK_UUID}/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    }
    return null;
  });
}

test.describe('Proposal Discount Multi-Section', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((_uuid) => {
      localStorage.setItem('proposal_onboarding_seen', 'true');
    }, MOCK_UUID);
  });

  test('discount badge is visible in Investment section when proposal has active discount', {
    tag: [...PROPOSAL_DISCOUNT_MULTI_SECTION, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the guest's shared proposal URL is the entry point; the investment panel is reached through navigation)
    await setupMock(page, mockProposalWithDiscount);
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    // Navigate from greeting to investment
    const nextBtn = page.getByTestId('nav-next');
    await expect(nextBtn).toBeVisible({ timeout: 15000 });
    await nextBtn.click();

    // Discount banner should be visible with percentage and discounted price
    await expect(page.getByText(/15% OFF/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/8\.500\.000/)).toBeVisible();
  });

  test('discount badge is visible in ProposalClosing panel', {
    tag: [...PROPOSAL_DISCOUNT_MULTI_SECTION, '@role:guest'],
  }, async ({ page }) => {
    await setupMock(page, mockProposalWithDiscount);
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    // Navigate to the closing panel (after all sections)
    const nextBtn = page.getByTestId('nav-next');
    await expect(nextBtn).toBeVisible({ timeout: 15000 });
    // greeting → investment
    await nextBtn.click();
    await expect(page.getByRole('heading', { name: /Inversión/ })).toBeVisible({ timeout: 5000 });
    // investment → requirements
    await nextBtn.click();
    await expect(page.getByRole('heading', { name: /Requerimientos/ })).toBeVisible({ timeout: 5000 });
    // requirements → closing (next button disappears on last panel)
    await nextBtn.click();

    // Closing panel discount badge should show "Precio especial disponible"
    await expect(page.getByText(/Precio especial disponible/i)).toBeVisible({ timeout: 10000 });
  });

  test('discount badge is NOT visible when proposal has no discount', {
    tag: [...PROPOSAL_DISCOUNT_MULTI_SECTION, '@role:guest'],
  }, async ({ page }) => {
    await setupMock(page, mockProposalNoDiscount);
    await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`);

    // Navigate to investment section
    const nextBtn = page.getByTestId('nav-next');
    await expect(nextBtn).toBeVisible({ timeout: 15000 });
    await nextBtn.click();

    // The investment section should be visible but no discount banner
    await expect(page.getByText(/Inversión Total/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/15% OFF/)).not.toBeVisible();
  });
});
