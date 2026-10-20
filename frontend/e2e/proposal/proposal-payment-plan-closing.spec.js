/**
 * E2E tests for payment plan milestones displayed in the closing section.
 *
 * Covers: payment milestones remain available beside public adjustment actions when proposal
 * has payment_options configured and status is sent/viewed.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_PAYMENT_PLAN_CLOSING } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const MOCK_UUID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

const baseSections = [
  {
    id: 1,
    section_type: 'greeting',
    title: '👋 Bienvenido',
    order: 0,
    is_enabled: true,
    content_json: { clientName: 'Test Client', inspirationalQuote: '' },
  },
];

function buildProposal(paymentOptions) {
  return {
    id: 1,
    uuid: MOCK_UUID,
    title: 'Payment Plan Proposal',
    client_name: 'Test Client',
    status: 'sent',
    language: 'es',
    total_investment: '5000000',
    currency: 'COP',
    payment_options: paymentOptions,
    sections: baseSections,
    requirement_groups: [],
  };
}

async function openClosingPanel(page) {
  await page.goto(`/proposal/${MOCK_UUID}?mode=detailed`, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('nav-next').click();
  await expect(page.getByTestId('nav-next')).toHaveCount(0);
}

test.describe('Proposal Payment Plan in Closing', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((_uuid) => {
      localStorage.setItem('proposal_onboarding_seen', 'true');
    }, MOCK_UUID);
  });

  test('displays payment milestones when payment_options is an array', {
    tag: [...PROPOSAL_PAYMENT_PLAN_CLOSING, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (el enlace compartido es la entrada pública; llega al cierre por la navegación de la propuesta).
    // Falla si el cierre oculta las cuotas acordadas después de retirar la aceptación pública.
    const proposal = buildProposal([
      { label: 'Firma del contrato', amount: '$2,500,000' },
      { label: 'Entrega fase 1', amount: '$1,500,000' },
      { label: 'Entrega final', amount: '$1,000,000' },
    ]);

    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
      }
      return null;
    });

    await openClosingPanel(page);

    await expect(page.getByText('Formas de pago')).toBeVisible();
    await expect(page.getByText('Firma del contrato', { exact: true })).toHaveText('Firma del contrato');
    await expect(page.getByText('Entrega fase 1', { exact: true })).toHaveText('Entrega fase 1');
    await expect(page.getByText('Entrega final', { exact: true })).toHaveText('Entrega final');
  });

  test('hides payment milestones when payment_options is empty', {
    tag: [...PROPOSAL_PAYMENT_PLAN_CLOSING, '@role:guest'],
  }, async ({ page }) => {
    const proposal = buildProposal([]);

    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
      }
      return null;
    });

    await openClosingPanel(page);

    // Falla si retirar la aceptación elimina también la posibilidad de pedir ajustes.
    await expect(page.getByRole('button', { name: 'Necesito ajustes', exact: true })).toHaveText('Necesito ajustes');
    await expect(page.getByRole('button', { name: /Acepto la propuesta/i })).toHaveCount(0);
    await expect(page.getByText('Formas de pago')).toHaveCount(0);
  });

  test('hides payment milestones after proposal is accepted', {
    tag: [...PROPOSAL_PAYMENT_PLAN_CLOSING, '@role:guest'],
  }, async ({ page }) => {
    const proposal = buildProposal([
      { label: 'Firma', amount: '$2,500,000' },
    ]);
    proposal.status = 'accepted';

    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === `proposals/${MOCK_UUID}/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
      }
      return null;
    });

    await openClosingPanel(page);

    // Accepted state visible, payment plan hidden
    await expect(page.getByText('¡Propuesta aceptada!', { exact: true })).toHaveText('¡Propuesta aceptada!');
    await expect(page.getByText('Formas de pago')).toHaveCount(0);
  });
});
