import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setPlatformAuth, mockPlatformAdmin, mockPlatformClient } from '../helpers/platform-auth.js';
import { PLATFORM_PROJECT_DETAIL, PLATFORM_SIDEBAR_NAVIGATION } from '../helpers/flow-tags.js';
import { PANEL_VIEWPORTS } from '../../config/responsive.js';
import { textContrast } from '../helpers/text-contrast.js';

const project = {
  id: 1, name: 'Proyecto de contraste', status: 'active', progress: 0,
  bugs_open_count: 0, changes_pending_count: 0, client_id: 9002,
  client_name: 'Client E2E', client_email: 'client@e2e-test.com',
};

async function openSummary(page, user, theme) {
  await setPlatformAuth(page, { user });
  await page.addInitScript((value) => localStorage.setItem('platform_theme', value), theme);
  await mockApi(page, async ({ apiPath }) => {
    const body = apiPath === 'accounts/me/' ? user
      : apiPath === 'accounts/projects/1/' ? project
        : apiPath === 'accounts/projects/' ? [project] : [];
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
  });
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' });
  await page.getByTestId(/^project-(?:row|card)-1$/).click();
  await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name);
  await expect(page.getByText('Progreso', { exact: true })).toBeVisible();
}

async function attachEvidence(page, testInfo) {
  await testInfo.attach('rendered-theme', {
    body: await page.screenshot({ fullPage: true, animations: 'disabled' }),
    contentType: 'image/png',
  });
}

async function openCustomization(page, viewport) {
  if (viewport.width < 768) {
    await page.getByRole('button', { name: 'Abrir navegación', exact: true }).click();
  }
  await page.getByRole('button', { name: 'Personalizar apariencia', exact: true }).filter({ visible: true }).first().click();
}

for (const [profile, viewport] of Object.entries(PANEL_VIEWPORTS)) {
  test.describe(`Platform theme ${profile}`, () => {
    test.use({ viewport });
    test.setTimeout(60_000);

    for (const theme of ['dark', 'light']) {
      for (const [role, user] of [['admin', mockPlatformAdmin], ['client', mockPlatformClient]]) {
        test(`keeps summary text readable for ${role} in ${theme}`, {
          tag: ['@outcome:display', ...PLATFORM_PROJECT_DETAIL, `@role:platform-${role}`],
        }, async ({ page }, testInfo) => {
          await openSummary(page, user, theme);
          // An empty phase list used a fixed green at 60% opacity (2.63:1 in dark).
          await expect(page.getByText('Este proyecto no tiene fases vinculadas todavía.', { exact: true })).toBeVisible();

          for (const label of ['Progreso', 'Bugs abiertos', 'Solicitudes pendientes', 'Próximo pago de hosting', 'Este proyecto no tiene fases vinculadas todavía.']) {
            expect(await textContrast(page.getByText(label, { exact: true })), label).toBeGreaterThanOrEqual(4.5);
          }
          await attachEvidence(page, testInfo);
        });
      }

      test(`applies ${theme} surfaces to phase selection`, {
        tag: ['@outcome:display', ...PLATFORM_PROJECT_DETAIL, '@role:platform-admin'],
      }, async ({ page }, testInfo) => {
        await openSummary(page, mockPlatformAdmin, theme);
        const surface = await page.getByText('Progreso', { exact: true }).evaluate((element) => getComputedStyle(element.parentElement).backgroundColor);

        await page.getByRole('button', { name: /Agregar fase desde propuesta del cliente/ }).click();

        const dialog = page.getByRole('dialog', { name: 'Agregar fases', exact: true });
        await expect(dialog).toBeVisible();
        expect(await dialog.getByRole('heading').evaluate((element) => getComputedStyle(element.parentElement.parentElement).backgroundColor)).toBe(surface);
        expect(await textContrast(dialog.getByRole('heading'))).toBeGreaterThanOrEqual(4.5);
        await attachEvidence(page, testInfo);
      });

      test(`applies ${theme} surfaces to interface customization`, {
        tag: ['@outcome:display', ...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin'],
      }, async ({ page }, testInfo) => {
        await openSummary(page, mockPlatformAdmin, theme);
        const surface = await page.getByText('Progreso', { exact: true }).evaluate((element) => getComputedStyle(element.parentElement).backgroundColor);

        await openCustomization(page, viewport);

        const dialog = page.getByRole('dialog', { name: 'Personalizar interfaz', exact: true });
        await expect(dialog).toBeVisible();
        expect(await dialog.getByRole('heading').evaluate((element) => getComputedStyle(element.parentElement.parentElement.parentElement).backgroundColor)).toBe(surface);
        expect(await textContrast(dialog.getByText('Escoge un color y una imagen para hacer tuyo este espacio.', { exact: true }))).toBeGreaterThanOrEqual(4.5);
        await attachEvidence(page, testInfo);
      });
    }
  });
}
