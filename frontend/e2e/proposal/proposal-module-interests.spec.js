/**
 * Public proposal module-interest modal.
 *
 * Catches regressions where the retired calculator leaks prices or timelines,
 * saves an incompatible payload, or drops a client's selection after an API failure.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { viewportUse } from '../helpers/viewports.js';

const PROPOSAL_UUID = 'a1444444-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const ORIGINAL_TOTAL = '$5.000.000';
const catalog = {
  language: 'es',
  show_explainer_video: true,
  categories: [{
    id: 31,
    slug: 'growth',
    name: 'Crecimiento',
    modules: [{
      id: 97,
      slug: 'weekly-reporting',
      icon: '📈',
      name: 'Reportes semanales',
      summary: 'Una lectura semanal de resultados para priorizar mejoras.',
      what_is: 'Un tablero que resume avances y resultados.',
      purpose: 'Alinear las decisiones del equipo.',
      problems_solved: ['Evita reuniones sin datos.'],
      integrations: ['Panel de métricas'],
      implementation_requirements: ['Definir responsables'],
      price: 6000000,
      price_percent: 60,
    }],
  }],
};

const proposal = {
  id: 144,
  uuid: PROPOSAL_UUID,
  title: 'Propuesta de módulos E2E',
  client_name: 'Cliente de módulos',
  language: 'es',
  status: 'sent',
  is_active: true,
  total_investment: '5000000',
  currency: 'COP',
  sections: [
    {
      id: 1441,
      section_type: 'greeting',
      title: 'Bienvenida',
      order: 0,
      is_enabled: true,
      content_json: { clientName: 'Cliente de módulos', inspirationalQuote: '' },
    },
    {
      id: 1442,
      section_type: 'investment',
      title: 'Inversión',
      order: 1,
      is_enabled: true,
      content_json: {
        index: '2',
        title: 'Inversión',
        introText: 'Conoce el detalle de tu inversión.',
        totalInvestment: ORIGINAL_TOTAL,
        currency: 'COP',
        whatsIncluded: [{ icon: '🎨', title: 'Diseño', description: 'UX/UI personalizado' }],
        paymentOptions: [{ label: 'Pago inicial', description: '$2.500.000 COP' }],
      },
    },
  ],
  requirement_groups: [],
};

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

async function setupProposalApi(page, { catalogFailures = 0, saveFails = false, captured = [] } = {}) {
  let catalogCalls = 0;
  let savedModules = [];
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === `proposals/${PROPOSAL_UUID}/`) return json(200, proposal);
    if (apiPath === `proposals/${PROPOSAL_UUID}/module-interests/` && method === 'GET') return json(200, { modules: savedModules });
    if (apiPath === 'additional-modules/public/' && method === 'GET') {
      catalogCalls += 1;
      return catalogCalls <= catalogFailures ? json(503, { detail: 'Unavailable' }) : json(200, catalog);
    }
    if (apiPath === `proposals/${PROPOSAL_UUID}/module-interests/` && method === 'PUT') {
      captured.push(route.request().postDataJSON());
      if (saveFails) return json(503, { detail: 'Unavailable' });
      savedModules = [{ id: 97, name_es: 'Reportes semanales', category_es: 'Crecimiento' }];
      return json(200, { status: 'saved', modules: savedModules });
    }
    if (apiPath.includes('/track/') || apiPath === `proposals/${PROPOSAL_UUID}/record-view/`) return json(200, {});
    return null;
  });
}

async function openInterestModal(page) {
  await page.addInitScript((uuid) => {
    localStorage.setItem('proposal_onboarding_seen', 'true');
    localStorage.setItem(`investment_onboarding_seen_${uuid}`, 'true');
  }, PROPOSAL_UUID);
  // quality: allow-deep-link (a guest receives the shared detailed URL, then reaches the investment panel through its UI navigation)
  await page.goto(`/proposal/${PROPOSAL_UUID}?mode=detailed`, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('nav-next').click();
  const exploreButton = page.getByRole('button', { name: 'Explorar módulos adicionales' });
  await expect(exploreButton).toBeVisible({ timeout: 20_000 });
  await exploreButton.click();
  await expect(page.getByTestId('module-interests-modal')).toBeVisible();
}

test.describe('Proposal module interests', () => {
  test.setTimeout(60_000);

  for (const profile of ['compact', 'desktop']) {
    test.describe(`saving interest at ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
      test.use(viewportUse(profile));

      test('keeps the proposal total while saving the selected catalog module', {
        tag: ['@flow:proposal-module-interests', '@role:guest', '@outcome:success', '@responsive:public'],
      }, async ({ page }) => {
        // quality: allow-duplicate (per-viewport contract: module-interest modal at compact and desktop)
        const captured = [];
        await setupProposalApi(page, { captured });
        await openInterestModal(page);

        const modal = page.getByTestId('module-interests-modal');
        await expect(page.getByTestId('module-interests-video-card')).toContainText('Descubre lo que tu plataforma puede hacer');
        await expect(modal).toContainText('Crecimiento');
        await expect(modal).toContainText('Reportes semanales');
        await expect(modal).not.toContainText(/6000000|60%/);
        await modal.getByText('Ver detalles').click();
        await expect(modal).toContainText('Un tablero que resume avances y resultados.');

        const interestInput = page.getByRole('checkbox', { name: 'Me interesa: Reportes semanales' });
        await interestInput.check();
        await page.getByRole('button', { name: 'Guardar mi interés' }).click();

        await expect(page.getByRole('status')).toContainText('Interés guardado.');
        expect(captured).toEqual([{ module_ids: [97] }]);
        await expect(page.getByText(ORIGINAL_TOTAL, { exact: true })).toHaveText(ORIGINAL_TOTAL);

        const modalBox = await modal.boundingBox();
        const saveBox = await page.getByRole('button', { name: 'Guardar mi interés' }).boundingBox();
        const viewport = page.viewportSize();
        expect(modalBox.width).toBeLessThanOrEqual(viewport.width);
        expect(saveBox.y + saveBox.height).toBeLessThanOrEqual(viewport.height + 1);

        await page.getByRole('button', { name: 'Cerrar', exact: true }).click();
        await expect(modal).toHaveCount(0);
        await page.getByRole('button', { name: 'Explorar módulos adicionales' }).click();
        await expect(page.getByRole('checkbox', { name: 'Me interesa: Reportes semanales' })).toBeChecked();
      });
    });
  }

  test('shows the explainer, catalog category and module details without calculator prices', {
    tag: ['@flow:proposal-module-interests', '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the guest's shared proposal link is the entry point; opening and expanding the modal remains a real UI journey)
    await setupProposalApi(page);
    await openInterestModal(page);

    const modal = page.getByTestId('module-interests-modal');
    await expect(page.getByTestId('module-interests-video-card')).toContainText('Descubre lo que tu plataforma puede hacer');
    await expect(modal).toContainText('Crecimiento');
    await expect(modal).toContainText('Reportes semanales');
    await expect(modal).not.toContainText(/6000000|60%/);
    await modal.getByText('Ver detalles').click();
    await expect(modal).toContainText('Un tablero que resume avances y resultados.');
  });

  test('offers a retry after the catalog request fails', {
    tag: ['@flow:proposal-module-interests', '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupProposalApi(page, { catalogFailures: 1 });
    await openInterestModal(page);

    const modal = page.getByTestId('module-interests-modal');
    await expect(modal.getByRole('alert')).toContainText('No pudimos cargar los módulos.');
    await modal.getByRole('button', { name: 'Reintentar' }).click();
    await expect(modal).toContainText('Reportes semanales');
  });

  test('keeps a checked module selected after the interest save fails', {
    tag: ['@flow:proposal-module-interests', '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupProposalApi(page, { saveFails: true });
    await openInterestModal(page);

    const modal = page.getByTestId('module-interests-modal');
    const interestInput = page.getByRole('checkbox', { name: 'Me interesa: Reportes semanales' });
    await interestInput.check();
    await page.getByRole('button', { name: 'Guardar mi interés' }).click();

    await expect(page.getByRole('alert')).toContainText('No pudimos guardar tu interés. Tu selección sigue aquí; puedes reintentar.');
    await expect(interestInput).toBeChecked();
    await expect(page.getByText(ORIGINAL_TOTAL, { exact: true })).toHaveText(ORIGINAL_TOTAL);
  });
});
