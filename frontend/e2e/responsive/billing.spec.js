/**
 * R-billing-01: the seven billing screens must retain an actionable financial
 * record at every supported viewport, instead of merely rendering a shell.
 */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';
import { contractAccount, hostingAccount, project, setupPanelBilling, setupPlatformBilling } from './billing-fixtures.js';

test.setTimeout(60_000);

const billingViews = Object.freeze([
  { key: 'frontend/pages/platform/collection-accounts/index.vue', path: '/en-us/platform/collection-accounts', group: 'list' },
  { key: 'frontend/pages/platform/collection-accounts/[id].vue', path: '/en-us/platform/collection-accounts/42', group: 'list' },
  { key: 'frontend/pages/platform/payments.vue', path: '/en-us/platform/payments', group: 'list' },
  { key: 'frontend/pages/platform/projects/[id]/collection-accounts.vue', path: '/en-us/platform/projects/1/collection-accounts', group: 'list' },
  { key: 'frontend/pages/platform/projects/[id]/payments.vue', path: '/en-us/platform/projects/1/payments', group: 'context' },
  { key: 'frontend/pages/panel/accounting/collection-context/[id].vue', path: '/en-us/panel/accounting/collection-context/42', group: 'context' },
  { key: 'frontend/pages/panel/accounting/project-hosting/[id].vue', path: '/en-us/panel/accounting/project-hosting/7', group: 'context' },
].map((view) => ({ ...view, scenario: getResponsiveScenario(view.key) })));

async function exerciseBillingView(page, view) {
  const { scenario } = view;
  if (view.key.startsWith('frontend/pages/panel/')) {
    await setupPanelBilling(page);
    await page.goto(view.path, { waitUntil: 'domcontentloaded' });
    await waitForNuxtApp(page);
  } else {
    await setupPlatformBilling(page);
    await page.goto(view.path, { waitUntil: 'domcontentloaded' });
    await waitForNuxtApp(page);
  }

  if (view.key.endsWith('collection-accounts/index.vue')) {
    await page.getByLabel('Nature').selectOption('hosting');
    const account = page.getByRole('link', { name: hostingAccount.public_number, exact: true });
    await expect(account).toHaveCount(1);
    return account;
  }

  if (view.key.endsWith('collection-accounts/[id].vue')) {
    await expect(page.getByRole('heading', { name: contractAccount.public_number, exact: true })).toHaveText(contractAccount.public_number);
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download PDF' }).click();
    expect((await download).suggestedFilename()).toBe('PA-AUR-001.pdf');
    return page.getByText('Documento emitido.', { exact: true });
  }

  if (view.key.endsWith('platform/payments.vue')) {
    const projectLink = page.getByTestId('billing-hosting-list').getByRole('link', { name: project.name, exact: true });
    await expect(projectLink).toHaveCount(1);
    await projectLink.click();
    await expect(page.getByTestId('project-hosting-context').getByText('One hosting per project, independent of its contracts.')).toHaveCount(1);
    await page.goBack();
    await expect(projectLink).toHaveCount(1);
    return projectLink;
  }

  if (view.key.endsWith('projects/[id]/collection-accounts.vue')) {
    await page.getByLabel('Nature').selectOption('hosting');
    const account = page.getByRole('link', { name: hostingAccount.public_number, exact: true });
    await expect(account).toHaveCount(1);
    return account;
  }

  if (view.key.endsWith('projects/[id]/payments.vue')) {
    await expect(page.getByTestId('project-hosting-context').getByText('Operational source', { exact: true })).toHaveCount(1);
    await page.getByTestId('project-hosting-context').getByRole('link', { name: 'View hosting accounts' }).click();
    await expect(page.getByRole('link', { name: hostingAccount.public_number, exact: true })).toHaveCount(1);
    await page.goBack();
    const source = page.getByTestId('project-hosting-context').getByRole('heading', { name: 'aurora.test · #30', exact: true });
    await expect(source).toHaveCount(1);
    return source;
  }

  if (view.key.endsWith('collection-context/[id].vue')) {
    await expect(page.getByRole('combobox', { name: 'Contrato', exact: true })).toHaveValue('10');
    await page.getByLabel('Razón de la asociación o corrección').fill('Matriz responsive con contexto contractual');
    const save = page.getByRole('button', { name: 'Guardar asociación' });
    await expect(save).toBeEnabled();
    return save;
  }

  await expect(page.getByText('Proyecto Aurora · versión 4', { exact: true })).toHaveCount(1);
  await page.getByLabel('Suscripción de plataforma').selectOption('90');
  await page.getByRole('checkbox', { name: '#30 · aurora.test', exact: true }).check();
  await page.getByLabel('Origen contable operativo').selectOption('30');
  await page.getByLabel('Razón').first().fill('Matriz responsive del origen operativo');
  await page.getByRole('button', { name: 'Previsualizar asociación' }).click();
  const preview = page.getByTestId('hosting-reconciliation-preview').getByText('"decision": "ready"');
  await expect(preview).toHaveCount(1);
  return preview;
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`billing views · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    for (const view of billingViews) {
      test(`${view.scenario.label} keeps its financial action reachable`, {
        tag: [
          `@flow:${view.scenario.flowId}`,
          '@outcome:display',
          '@responsive:billing',
          `@responsive-billing-${view.group}`,
          `@responsive-scenario:${view.scenario.catalogKey}`,
          `@responsive-batch:${batchForScenario(view.scenario.catalogKey)}`,
          `@viewport:${profile}`,
        ],
      }, async ({ page }, testInfo) => {
        // quality: allow-deep-link (each localized fixture route is cataloged; the scenario exercises its own financial control and concrete record before geometry).
        const priorityLocator = await exerciseBillingView(page, view);
        await expect(priorityLocator).toHaveCount(1);
        await assertResponsiveScenario(page, testInfo, view.scenario, { profile, priorityLocator });
      });
    }
  });
}
