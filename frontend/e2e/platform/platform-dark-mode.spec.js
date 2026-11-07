/** Catches missing theme controls, non-persistent cover removal and unreadable theme surfaces (PA-227). */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setPlatformAuth, mockPlatformAdmin, mockPlatformClient } from '../helpers/platform-auth.js';
import { PLATFORM_PROJECT_DETAIL, PLATFORM_SIDEBAR_NAVIGATION } from '../helpers/flow-tags.js';
import { PANEL_VIEWPORTS } from '../../config/responsive.js';
import { textContrast } from '../helpers/text-contrast.js';

const project = {
  id: 1, name: 'Proyecto de contraste', status: 'active', status_label: 'Sin clasificar', progress: 0,
  bugs_open_count: 0, changes_pending_count: 0, client_id: 9002,
  client_name: 'Client E2E', client_email: 'client@e2e-test.com',
};

async function openSummary(page, user, theme) {
  await setPlatformAuth(page, { user });
  await page.addInitScript((value) => localStorage.setItem('platform_theme', localStorage.getItem('platform_theme') || value), theme);
  let profile = { ...user };
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'accounts/me/' && method === 'PATCH') {
      const multipart = route.request().headers()['content-type']?.includes('multipart/form-data');
      profile = { ...profile, ...(multipart ? { custom_cover_image: '/qa-cover.svg', cover_image: '' } : route.request().postDataJSON()) };
    }
    const body = apiPath === 'accounts/me/' ? profile
      : apiPath === 'accounts/projects/1/' ? project
        : apiPath === 'accounts/projects/' ? [project] : [];
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
  });
  await page.goto('/platform', { waitUntil: 'domcontentloaded' });
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

async function openNavigation(page, viewport) {
  if (viewport.width < 768) {
    await page.getByRole('button', { name: 'Abrir navegación', exact: true }).click();
  }
}

async function openCustomization(page, viewport) {
  await openNavigation(page, viewport);
  await page.getByRole('button', { name: 'Personalizar apariencia', exact: true }).filter({ visible: true }).first().click();
}

for (const [profile, viewport] of Object.entries(PANEL_VIEWPORTS)) {
  test.describe(`Platform theme ${profile}`, () => {
    test.use({ viewport });
    test.setTimeout(60_000);

    for (const theme of ['dark', 'light']) {
      for (const [role, user] of [['admin', mockPlatformAdmin], ['client', mockPlatformClient]]) {
        test(`persists the visible theme selection for ${role} from ${theme}`, {
          tag: ['@outcome:success', ...PLATFORM_SIDEBAR_NAVIGATION, `@role:platform-${role}`],
        }, async ({ page }, testInfo) => {
          await openSummary(page, user, theme);
          const target = theme === 'dark' ? 'light' : 'dark';
          const action = theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro';
          const nextAction = theme === 'dark' ? 'Activar modo oscuro' : 'Activar modo claro';
          const surface = () => page.getByText('Progreso', { exact: true }).evaluate((element) => getComputedStyle(element.parentElement).backgroundColor);
          const originalSurface = await surface();
          await openNavigation(page, viewport);

          await page.getByRole('button', { name: action, exact: true }).filter({ visible: true }).click();

          await expect(page.getByRole('button', { name: nextAction, exact: true }).filter({ visible: true })).toHaveText(nextAction);
          await expect.poll(surface).not.toBe(originalSurface);
          const selectedSurface = await surface();
          expect(await page.evaluate(() => localStorage.getItem('platform_theme'))).toBe(target);

          await page.reload({ waitUntil: 'domcontentloaded' });
          await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name);
          await openNavigation(page, viewport);

          await expect(page.getByRole('button', { name: nextAction, exact: true }).filter({ visible: true })).toHaveText(nextAction);
          await expect.poll(surface).toBe(selectedSurface);
          await attachEvidence(page, testInfo);
        });

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

      test(`persists custom cover removal in ${theme}`, {
        tag: ['@outcome:success', ...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin'],
      }, async ({ page }, testInfo) => {
        await page.route('**/qa-cover.svg', (route) => route.fulfill({
          contentType: 'image/svg+xml',
          body: '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#050c0a"/></svg>',
        }));
        await openSummary(page, { ...mockPlatformAdmin, custom_cover_image: '/qa-cover.svg' }, theme);
        await expect(page.getByTestId('platform-cover')).toBeVisible();
        await openCustomization(page, viewport);
        const customization = page.getByRole('dialog', { name: 'Personalizar interfaz', exact: true });

        await customization.getByRole('button', { name: 'Quitar', exact: true }).click();

        await expect(page.getByTestId('platform-cover')).toHaveCount(0);
        await customization.getByRole('button', { name: 'Cerrar personalización', exact: true }).click();
        await page.reload({ waitUntil: 'domcontentloaded' });
        await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name);
        await expect(page.getByTestId('platform-cover')).toHaveCount(0);
        await openCustomization(page, viewport);
        await expect(customization.getByRole('button', { name: 'Quitar', exact: true })).toHaveCount(0);
        await attachEvidence(page, testInfo);
      });

      for (const [family, shade] of [['Esmerald', 0], ['Esmerald', 8], ['Yellow', 4]]) {
        test(`keeps personalized actions readable with ${family} ${shade} in ${theme}`, {
          tag: ['@outcome:display', ...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin'],
        }, async ({ page }, testInfo) => {
          await openSummary(page, mockPlatformAdmin, theme);
          await openCustomization(page, viewport);
          const customization = page.getByRole('dialog', { name: 'Personalizar interfaz', exact: true });
          await customization.getByTitle(family, { exact: true }).nth(shade).click();
          await customization.getByRole('button', { name: 'Cerrar personalización', exact: true }).click();
          await expect(customization).toBeHidden();

          await page.getByRole('button', { name: 'Editar', exact: true }).click();

          const save = page.getByRole('dialog', { name: 'Editar proyecto', exact: true }).getByRole('button', { name: 'Guardar cambios', exact: true });
          expect(await textContrast(save)).toBeGreaterThanOrEqual(4.5);
          await save.hover();
          expect(await textContrast(save)).toBeGreaterThanOrEqual(4.5);
          await attachEvidence(page, testInfo);
        });
      }

      for (const [cover, color] of [['bright', '#fafafa'], ['dark', '#050c0a']]) {
        test(`keeps status readable over a ${cover} cover in ${theme}`, {
          tag: ['@outcome:display', ...PLATFORM_SIDEBAR_NAVIGATION, '@role:platform-admin'],
        }, async ({ page }, testInfo) => {
          await page.route('**/qa-cover.svg', (route) => route.fulfill({
            contentType: 'image/svg+xml',
            body: `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="${color}"/></svg>`,
          }));
          await openSummary(page, mockPlatformAdmin, theme);
          await openCustomization(page, viewport);
          const customization = page.getByRole('dialog', { name: 'Personalizar interfaz', exact: true });
          await customization.locator('input[type="file"]').setInputFiles({
            name: 'cover.svg', mimeType: 'image/svg+xml',
            buffer: Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="${color}"/></svg>`),
          });
          await expect(page.getByTestId('platform-cover')).toBeVisible();
          await customization.getByRole('button', { name: 'Cerrar personalización', exact: true }).click();
          await expect(customization).toBeHidden();

          expect(await textContrast(page.getByText('Sin clasificar', { exact: true }))).toBeGreaterThanOrEqual(4.5);
          expect(await textContrast(page.getByText('Progreso', { exact: true }))).toBeGreaterThanOrEqual(4.5);
          await attachEvidence(page, testInfo);
        });
      }
    }
  });
}
