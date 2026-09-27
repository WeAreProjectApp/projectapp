/**
 * Public proposal welcome video.
 *
 * Catches regressions where an eligible client cannot play the welcome video,
 * where a hidden effective response blocks the technical document, or where a
 * failed media request leaves the client without a way to continue.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PUBLIC_PROPOSAL_EXPLAINER } from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

const PROPOSAL_UUID = 'ef111111-1111-1111-1111-111111111111';

const proposal = {
  id: 960,
  uuid: PROPOSAL_UUID,
  title: 'Propuesta de bienvenida E2E',
  client_name: 'Cliente de bienvenida',
  client_email: 'cliente@example.com',
  language: 'es',
  status: 'sent',
  is_active: true,
  show_contract_terms: true,
  show_explainer_video: true,
  total_investment: '5000000',
  currency: 'COP',
  has_confirmed_module_selection: true,
  selected_modules: [],
  sections: [
    {
      id: 9601,
      section_type: 'technical_document',
      title: 'Detalle técnico',
      order: 0,
      is_enabled: true,
      is_wide_panel: true,
      content_json: {
        purpose: 'E2E propósito del detalle técnico',
        stack: [{ layer: 'Aplicación', technology: 'Vue', rationale: 'Interfaz pública' }],
        epics: [],
      },
    },
    {
      id: 9602,
      section_type: 'final_note',
      title: 'Cierre',
      order: 1,
      is_enabled: true,
      content_json: { thankYouMessage: 'Gracias por revisar la propuesta.' },
    },
  ],
  requirement_groups: [],
};

const contractTerms = {
  title: 'Contrato de prestación de servicios',
  label: 'Borrador informativo',
  preamble_markdown: 'Entre las partes identificadas como XXX-XXX-XXX.',
  clauses: [{
    id: 'clause-01',
    number: 1,
    title: 'CLÁUSULA PRIMERA — OBJETO',
    content_markdown: 'El proveedor desarrollará el alcance acordado.',
  }],
};

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

function proposalHandler({ showExplainerVideo = true } = {}) {
  return async ({ apiPath, method }) => {
    if (apiPath === `proposals/${PROPOSAL_UUID}/`) {
      return json(200, { ...proposal, show_explainer_video: showExplainerVideo });
    }
    if (apiPath === `proposals/${PROPOSAL_UUID}/contract-terms/` && method === 'GET') {
      return json(200, contractTerms);
    }
    if (apiPath === `proposals/${PROPOSAL_UUID}/record-view/` || apiPath.includes('/track/')) {
      return json(200, {});
    }
    return null;
  };
}

async function openSharedProposal(page, options) {
  await mockApi(page, proposalHandler(options));
  await page.addInitScript(() => localStorage.setItem('proposal_onboarding_seen', 'true'));
  // quality: allow-deep-link (the client receives this shared URL and then selects an option in the gateway)
  await page.goto(`/en-us/proposal/${PROPOSAL_UUID}`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: '¿Cómo prefieres explorar esta propuesta?' })).toBeVisible({ timeout: 30_000 });
}

test.describe('Public proposal welcome video', () => {
  test.setTimeout(60_000);

  for (const profile of ['compact', 'desktop']) {
    test.describe(`eligible gateway at ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
      test.use(viewportUse(profile));

      test('places a playable welcome video above its four choices', {
        tag: [...PUBLIC_PROPOSAL_EXPLAINER, '@role:guest', '@outcome:display', '@responsive:public'],
      }, async ({ page }) => {
        // quality: allow-deep-link (the client receives this shared proposal URL; the test then chooses the video in its gateway)
        // quality: allow-duplicate (per-viewport contract: public-proposal-explainer gateway at compact and desktop)
        await openSharedProposal(page);

        const videoCard = page.getByTestId('proposal-explainer-card');
        const legalCard = page.getByTestId('gateway-legal-card');
        await expect(videoCard).toContainText('Tu propuesta, paso a paso');
        await expect(legalCard).toContainText('Contrato y condiciones');
        await expect(page.getByTestId('gateway-technical-card')).toContainText('Detalle técnico');

        const videoBox = await videoCard.boundingBox();
        const legalBox = await legalCard.boundingBox();
        expect(videoBox.y).toBeLessThan(legalBox.y);
        await page.screenshot({ path: `test-results/proposal-gateway-${profile}.png`, fullPage: true });

        await page.getByTestId('proposal-explainer-play').click();
        await expect(page.getByTestId('proposal-explainer-player')).toHaveAttribute('controls', '');

      });
    });
  }

  test('playing the welcome video stops it when the client opens legal terms', {
    tag: [...PUBLIC_PROPOSAL_EXPLAINER, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await openSharedProposal(page);

    await page.getByTestId('proposal-explainer-play').click();
    const player = page.getByTestId('proposal-explainer-player');
    await expect.poll(() => player.evaluate((element) => !element.paused)).toBe(true);

    await page.getByTestId('gateway-legal-card').click();

    await expect(page.getByRole('heading', { name: 'Índice de cláusulas' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('CLÁUSULA PRIMERA — OBJETO')).toBeVisible();
    await expect(page.getByTestId('proposal-explainer-player')).toHaveCount(0);
  });

  test('effective hidden visibility removes only the video and leaves technical detail usable', {
    tag: [...PUBLIC_PROPOSAL_EXPLAINER, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await openSharedProposal(page, { showExplainerVideo: false });

    await expect(page.getByTestId('proposal-explainer-card')).toHaveCount(0);
    await page.getByTestId('gateway-technical-card').click();
    await expect(page.getByText('E2E propósito del detalle técnico')).toBeVisible({ timeout: 20_000 });
  });

  test('failed video media keeps a direct-file fallback and the legal option usable', {
    tag: [...PUBLIC_PROPOSAL_EXPLAINER, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await page.route('**/proposal-brag-v2-es*.mp4', (route) => route.fulfill({ status: 503, body: 'unavailable' }));
    await openSharedProposal(page);

    await page.getByTestId('proposal-explainer-play').click();
    await expect(page.getByTestId('proposal-explainer-error')).toContainText('No pudimos reproducir el video en este navegador.');
    await expect(page.getByTestId('proposal-explainer-open')).toHaveAttribute('target', '_blank');

    await page.getByTestId('gateway-legal-card').click();
    await expect(page.getByRole('heading', { name: 'Índice de cláusulas' })).toBeVisible({ timeout: 20_000 });
  });
});
