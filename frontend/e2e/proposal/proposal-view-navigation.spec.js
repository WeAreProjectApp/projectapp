/**
 * E2E tests for proposal section navigation.
 *
 * Covers: ProposalIndex open/close, clicking an index item to navigate,
 * ProposalIndex hidden when nav-side--left should be visible,
 * keyboard-style prev/next cycling through all sections.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_VIEW_NAVIGATION } from '../helpers/flow-tags.js';

const MOCK_UUID = 'cccccccc-cccc-cccc-cccc-cccccccccccc';

const mockProposalMultiSection = {
  id: 5,
  uuid: MOCK_UUID,
  title: 'Multi Section Navigation Test',
  client_name: 'Nav Client',
  status: 'sent',
  language: 'es',
  total_investment: '8000000',
  currency: 'COP',
  sections: [
    {
      id: 51,
      section_type: 'greeting',
      title: '👋 Bienvenido',
      order: 0,
      is_enabled: true,
      content_json: { clientName: 'Nav Client', inspirationalQuote: 'Move fast.' },
    },
    {
      id: 52,
      section_type: 'executive_summary',
      title: '🧾 Resumen Ejecutivo',
      order: 1,
      is_enabled: true,
      content_json: {
        index: '1',
        title: 'Resumen ejecutivo',
        paragraphs: ['Solución a medida.'],
        highlightsTitle: 'Incluye',
        highlights: ['Diseño UX'],
      },
    },
    {
      id: 53,
      section_type: 'context_diagnostic',
      title: '🧩 Contexto',
      order: 2,
      is_enabled: true,
      content_json: {
        index: '2',
        title: 'Contexto',
        paragraphs: ['El cliente busca crecer.'],
        issuesTitle: 'Desafíos',
        issues: ['Poca visibilidad'],
        opportunityTitle: 'Oportunidad',
        opportunity: 'Digitalización.',
      },
    },
  ],
  requirement_groups: [],
};

function buildMockHandler() {
  return async ({ apiPath }) => {
    if (apiPath === `proposals/${MOCK_UUID}/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposalMultiSection) };
    }
    return null;
  };
}

async function openProposal(page) {
  await page.goto(`/es-co/proposal/${MOCK_UUID}?mode=detailed`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('index-toggle')).toBeVisible({ timeout: 45_000 });
}

test.describe('Proposal View Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((_uuid) => {
      localStorage.setItem('proposal_onboarding_seen', 'true');
    }, MOCK_UUID);
  });

  test('clicking ProposalIndex toggle opens the index panel', {
    tag: [...PROPOSAL_VIEW_NAVIGATION, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler());
    await openProposal(page);

    // Index panel is hidden initially (translate-x-[-120%])
    const indexPanel = page.getByTestId('index-panel');
    await expect(indexPanel).toHaveAttribute('class', /pointer-events-none/);

    // Click toggle to open
    await page.getByTestId('index-toggle').click();

    // Index panel becomes visible
    await expect(indexPanel).toHaveAttribute('class', /pointer-events-auto/, { timeout: 3000 });
  });

  test('clicking an index item navigates to that section', {
    tag: [...PROPOSAL_VIEW_NAVIGATION, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (el enlace compartido es la entrada pública; el índice se abre y se navega por UI).
    await mockApi(page, buildMockHandler());
    await openProposal(page);

    // Open the index
    await page.getByTestId('index-toggle').click();
    const indexPanel = page.getByTestId('index-panel');
    await expect(indexPanel).toHaveAttribute('class', /pointer-events-auto/, { timeout: 3000 });

    // Click the 3rd item (Contexto) — index item 3
    const thirdItem = indexPanel.getByRole('button').nth(2);
    await thirdItem.click();

    // Index should close after navigation
    await expect(indexPanel).toHaveAttribute('class', /pointer-events-none/, { timeout: 3000 });

    // Previous button should be visible (no longer at first panel)
    await expect(page.getByTestId('nav-prev')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Contexto', exact: true })).toHaveText('Contexto');
  });

  test('ProposalIndex left nav button is hidden when index is open', {
    tag: [...PROPOSAL_VIEW_NAVIGATION, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler());
    await openProposal(page);

    // First navigate to section 2 so prev button would normally show
    const nextBtn = page.getByTestId('nav-next');
    await expect(nextBtn).toBeVisible();
    await nextBtn.click();

    // Prev button should be visible at section 2
    await expect(page.getByTestId('nav-prev')).toBeVisible({ timeout: 3000 });

    // Open index panel
    await page.getByTestId('index-toggle').click();
    await expect(page.getByTestId('index-panel')).toHaveAttribute('class', /pointer-events-auto/, { timeout: 3000 });

    // The nav-prev button should be hidden when index is open (hideLeft prop)
    await expect(page.getByTestId('nav-prev')).not.toBeVisible();
  });

  test('cycling through all sections reaches the closing panel', {
    tag: [...PROPOSAL_VIEW_NAVIGATION, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, buildMockHandler());
    const proposalReq = page.waitForResponse((r) => r.url().includes(`proposals/${MOCK_UUID}/`));
    await openProposal(page);
    await proposalReq;

    // Mock has 3 sections (greeting, executive_summary, context_diagnostic);
    // the page auto-appends proposal_closing → 4 panels total → 3 nav-next clicks.
    const nextBtn = page.getByTestId('nav-next');
    for (let i = 0; i < 3; i++) {
      await expect(nextBtn).toBeVisible();
      await nextBtn.click();
    }

    // On last panel (proposal_closing), next button is gone
    await expect(nextBtn).not.toBeVisible();

    // Falla si el cierre vuelve a permitir aprobar públicamente sin revisión interna.
    await expect(page.getByRole('button', { name: 'Necesito ajustes', exact: true })).toHaveText('Necesito ajustes');
    await expect(page.getByRole('button', { name: /Acepto la propuesta/i })).toHaveCount(0);
  });
});
