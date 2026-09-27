/** R-foundation-01: compact controls can become unreachable while the panel still mounts. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const loginScenario = getResponsiveScenario('frontend/pages/panel/login.vue');
const styleguideScenario = getResponsiveScenario('frontend/pages/panel/styleguide.vue');

async function adminSession(page) {
  await setAuthLocalStorage(page, { token: 'foundation-token', userAuth: { id: 9001, role: 'admin', is_staff: true } });
  await mockApi(page, async ({ apiPath }) => apiPath === 'auth/check/'
    ? { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) }
    : null);
}

async function expectVisibleFooter(page, dialog) {
  const footer = dialog.locator('[data-modal-footer]');
  const box = await footer.boundingBox();
  expect(box).not.toBeNull();
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize().height + 1);
  await expect(footer.getByRole('button', { name: 'Cancelar' })).toBeInViewport();
  await expect(footer.getByRole('button', { name: 'Aceptar' })).toBeInViewport();
  expect(await dialog.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
  return box;
}

async function verifyLongModal(page) {
  await adminSession(page);
  // quality: allow-deep-link (the styleguide is the foundation acceptance surface)
  await page.goto('/panel/styleguide', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Abrir modal largo', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const before = await expectVisibleFooter(page, dialog);
  const body = dialog.locator('[data-modal-body]');
  await body.hover();
  await page.mouse.wheel(0, 10000);
  await expect.poll(() => body.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await expect(dialog.getByRole('textbox', { name: 'Observación 16', exact: true })).toBeInViewport();
  const after = await expectVisibleFooter(page, dialog);
  expect(Math.abs(after.y - before.y)).toBeLessThanOrEqual(1);
  await dialog.getByRole('button', { name: 'Aceptar' }).click();
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`foundation catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    test('login keeps the Django Admin entry actionable', {
      tag: ['@flow:admin-login', '@outcome:display', '@responsive:foundation', `@responsive-scenario:${loginScenario.catalogKey}`, `@responsive-batch:${batchForScenario(loginScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (the unauthenticated login surface has no earlier panel route)
      // Django owns /admin/. The responsive suite only boots Nuxt, so model
      // that external handoff endpoint explicitly and assert the clicked
      // navigation reaches it.
      await page.route(/^https?:\/\/[^/]+\/admin\/$/, (route) => route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body><h1>Django admin login</h1></body></html>',
      }));
      await page.goto('/panel/login', { waitUntil: 'domcontentloaded' });
      await waitForNuxtApp(page);
      // quality: allow-flow-tag-mismatch (this catalog route verifies the Django Admin handoff; credential entry belongs to Django's separate login surface)
      const adminLink = page.getByRole('link', { name: 'Ir al Django Admin' });
      await expect(adminLink).toHaveAttribute('href', '/admin/');
      await adminLink.click();
      await expect(page).toHaveURL(/\/admin\/$/);
      await expect(page.getByRole('heading', { name: 'Django admin login' })).toBeVisible();
      await assertResponsiveScenario(page, testInfo, loginScenario, { profile });
    });

    test('styleguide dismisses its modal from the responsive surface', {
      tag: ['@flow:admin-styleguide', '@outcome:display', '@responsive:foundation', `@responsive-scenario:${styleguideScenario.catalogKey}`, `@responsive-batch:${batchForScenario(styleguideScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (the styleguide is the foundation acceptance surface)
      await adminSession(page);
      await page.goto('/panel/styleguide', { waitUntil: 'domcontentloaded' });
      await page.getByRole('button', { name: 'Abrir modal', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await expect(dialog.getByRole('heading', { name: 'Demo modal' })).toHaveText('Demo modal');
      await expectVisibleFooter(page, dialog);
      await dialog.getByRole('button', { name: 'Cancelar' }).click();
      await expect(page.getByRole('heading', { name: 'Demo modal' })).toHaveCount(0);
      await assertResponsiveScenario(page, testInfo, styleguideScenario, { profile });
    });

    test('styleguide keeps the long modal footer visible while reading its last field', {
      tag: ['@flow:admin-styleguide', '@outcome:display', `@viewport:${profile}`],
    }, async ({ page }) => {
      // quality: allow-deep-link (the styleguide is the foundation acceptance surface)
      await verifyLongModal(page);
      await expect(page.getByRole('dialog')).toHaveCount(0);
    });
  });
}

test('styleguide keeps long modal actions reachable on a low screen', {
  tag: ['@flow:admin-styleguide', '@outcome:display'],
}, async ({ page }) => {
  // quality: allow-deep-link (the styleguide is the foundation acceptance surface)
  await page.setViewportSize({ width: 844, height: 390 });
  await verifyLongModal(page);
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
