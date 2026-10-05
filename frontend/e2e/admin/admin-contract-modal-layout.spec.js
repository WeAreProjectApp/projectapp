/** @flow:admin-proposal-contract-modality */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_CONTRACT_MODALITY } from '../helpers/flow-tags.js';
import { PANEL_VIEWPORTS } from '../../config/responsive.js';
import { buildProposal, buildHandler, openDocuments } from '../helpers/contract-modals.js';

async function openContract(page, variant) {
  await setAuthLocalStorage(page, {
    token: 'e2e-admin-token', userAuth: { id: 8110, role: 'admin', is_staff: true },
  });
  const proposal = buildProposal({
    contract_modality: variant === 'combined' ? 'single' : 'split', proposal_documents: [],
  });
  await mockApi(page, buildHandler({ proposal }));
  await openDocuments(page);
  await page.getByTestId(`proposal-generate-contract-${variant}`).click();
  return page.getByRole('dialog');
}

async function expectCompactLayout(dialog, viewport, variant) {
  // quality: allow-fragile-selector (BaseModal publishes these stable geometry hooks for its panel and scrolling body)
  const panel = await dialog.locator('[data-modal-kind]').boundingBox();
  const body = await dialog.locator('[data-modal-body]').evaluate(el => ({
    width: el.clientWidth, content: el.scrollWidth, height: el.scrollHeight,
  }));
  const city = await dialog.getByLabel('Ciudad del contrato').boundingBox();
  const date = await dialog.getByLabel('Fecha del contrato').boundingBox();
  expect(panel.width).toBeLessThanOrEqual(Math.min(viewport.width, 672));
  expect(body.content).toBeLessThanOrEqual(body.width + 1);
  if (viewport.width < 640) {
    expect(date.y).toBeGreaterThan(city.y + city.height);
  } else {
    expect(Math.abs(date.y - city.y)).toBeLessThanOrEqual(1);
    expect(date.width).toBeLessThanOrEqual(320);
    // Leave room for font rendering while rejecting the previous taller layout.
    const contentHeightLimit = { combined: 1024, product: 800, service: 1024 };
    expect(body.height).toBeLessThanOrEqual(contentHeightLimit[variant]);
  }
}

for (const [profile, viewport] of Object.entries(PANEL_VIEWPORTS)) {
  test.describe(`Contract form ${profile}`, () => {
    test.use({ viewport });
    test.setTimeout(60_000);

    for (const variant of ['combined', 'product', 'service']) {
      test(`preserves a compact ${variant} form when reopening its saved data`, {
        tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
      }, async ({ page }) => {
        const dialog = await openContract(page, variant);
        await expectCompactLayout(dialog, viewport, variant);

        await dialog.getByLabel('Ciudad del contrato').fill('Bogotá');
        await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();
        await expect(dialog).toHaveCount(0);
        await page.getByTestId(`proposal-contract-row-${variant}`).getByRole('button', { name: 'Editar parámetros' }).click();

        await expect(dialog.getByLabel('Ciudad del contrato')).toHaveValue('Bogotá');
        await expectCompactLayout(dialog, viewport, variant);
      });
    }

    test('keeps service options reachable inside the viewport', {
      tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      const dialog = await openContract(page, 'service');
      const duration = dialog.getByRole('combobox', { name: 'Duración inicial' });
      await duration.click();
      const options = dialog.getByRole('listbox', { name: 'Duración inicial' });
      await expect(options.getByRole('option')).toHaveText(['tres (3) meses', 'seis (6) meses', 'nueve (9) meses', 'doce (12) meses', 'Personalizar']);
      const box = await options.boundingBox();
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
      await duration.press('Escape');
      await expect(duration).toBeFocused();
      await expect(dialog).toBeVisible();
      await duration.press('End');
      await duration.press('Enter');
      const custom = dialog.getByLabel('Duración inicial: valor personalizado');
      await expect(custom).toBeFocused();
      await custom.fill('cuatro (4) meses');
      await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await page.getByTestId('proposal-contract-row-service').getByRole('button', { name: 'Editar parámetros' }).click();
      await expect(dialog.getByLabel('Duración inicial: valor personalizado')).toHaveValue('cuatro (4) meses');
    });
  });
}
