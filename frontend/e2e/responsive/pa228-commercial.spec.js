/** PA-228 / RESP-R061: technical insertion, email preview and both navigation funnels. */
import { test, expect } from '../helpers/test.js';
import { viewportUse } from '../helpers/viewports.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { RESPONSIVE_PROFILES } from './catalog-scenarios.js';
import {
  openPa228, moduleTitle, funnelSteps, technicalSteps, resizeFromDesktop,
  expectFitsHorizontally, expectReadable, expectPageFits,
} from '../helpers/pa228-responsive.js';

test.setTimeout(60_000);

async function expectFunnel(page, mode, steps) {
  const panel = page.getByTestId(`proposal-funnel-${mode}`);
  await expect(panel.getByTestId('proposal-funnel-row')).toHaveCount(steps.length);
  await expect(panel.getByTestId('proposal-funnel-title')).toHaveText(steps.map((step) => step.section_title));
  await expect(panel.getByTestId('proposal-funnel-count')).toHaveText(steps.map((step) => `${step.reached_count} sesiones`));
  await expectReadable(panel.getByTestId('proposal-funnel-title'));
  await expectReadable(panel.getByTestId('proposal-funnel-count'));
  await expectPageFits(page);
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`PA-228 proposals · ${profile}`, {
    tag: ['@responsive:commercial', '@responsive-special:commercial', '@responsive-batch:commercial-special-2', `@viewport:${profile}`],
  }, () => {
    test.use({ ...viewportUse(profile), reducedMotion: 'reduce' });

    test('long commercial module remains selectable', {
      tag: ['@flow:admin-proposal-edit', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-deep-link (direct editor loading is one of the reported responsive reproduction paths)
      await openPa228(page, '/panel/proposals/1/edit');
      await selectProposalDestination(page, 'proposal', 'technical');
      const select = page.getByTestId('technical-stub-module');
      await expect(select.getByRole('option', { name: moduleTitle, exact: true })).toBeAttached();
      await expectFitsHorizontally(select);
      await expectPageFits(page);

      await resizeFromDesktop(page, profile);
      await select.selectOption('pa228-module');
      await select.focus();
      await expect(select).toHaveValue('pa228-module');
      await expectFitsHorizontally(select);
      const insert = page.getByRole('button', { name: 'Insertar módulo genérico', exact: true });
      await expectFitsHorizontally(insert);
      await expectPageFits(page);
      await insert.click();
      await expect(page.getByPlaceholder('Título del módulo', { exact: true })).toHaveValue(`Alcance ampliado: ${moduleTitle}`);
    });

    test('email preview keeps its close action reachable', {
      tag: ['@flow:admin-proposal-edit', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-deep-link (the same proposal must be loaded directly before testing the mobile preview header)
      await openPa228(page, '/panel/proposals/1/edit');
      await selectProposalDestination(page, 'communication', 'emails');
      await page.getByTestId('edit-email-preview-btn').click();
      const header = page.getByTestId('edit-email-preview-header');
      const frame = page.frameLocator('iframe[title="Vista previa del correo"]');
      await expect(frame.getByText('Vista previa ficticia: proposal_sent_client', { exact: true })).toBeVisible();
      await expectFitsHorizontally(header.getByRole('combobox'));
      await expectFitsHorizontally(header.getByRole('button'));
      await expect(header.getByRole('button', { name: 'Cerrar', exact: true })).toBeInViewport();
      await expectPageFits(page);

      await resizeFromDesktop(page, profile);
      await header.getByRole('combobox').selectOption('proposal_reminder');
      await header.getByRole('button', { name: 'Recargar', exact: true }).click();
      await expect(frame.getByText('Vista previa ficticia: proposal_reminder', { exact: true })).toBeVisible();
      await expectFitsHorizontally(header.getByRole('button'));
      await header.getByRole('button', { name: 'Cerrar', exact: true }).click();
      await expect(header).toBeHidden();
    });

    test('funnel session counts remain readable', {
      tag: ['@flow:admin-proposal-analytics', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (load the fixture editor directly, then open analytics through its responsive navigation)
      await openPa228(page, '/panel/proposals/1/edit');
      await selectProposalDestination(page, 'tracking', 'analytics');
      await expectFunnel(page, 'exec', funnelSteps);
      await expect(page.getByTestId('proposal-funnel-exec').getByText('solo detallado', { exact: true })).toHaveCount(6);

      await resizeFromDesktop(page, profile);
      await expectFunnel(page, 'exec', funnelSteps);
      await page.getByRole('button', { name: 'Técnico', exact: true }).click();
      await expectFunnel(page, 'technical', technicalSteps);
      await expect(page.getByTestId('proposal-funnel-technical').getByText('no visto', { exact: true })).toBeVisible();
    });
  });
}
