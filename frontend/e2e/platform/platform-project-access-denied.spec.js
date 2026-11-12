/**
 * E2E coverage for the project-space access-denied state.
 *
 * @flow:platform-project-detail
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_PROJECT_DETAIL } from '../helpers/flow-tags.js';
import { mockPlatformClient, setPlatformAuth } from '../helpers/platform-auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { waitForNuxtApp } from '../helpers/navigation.js';

test.setTimeout(60_000);

const restrictedProject = {
  id: 45,
  name: 'Proyecto restringido',
  status: 'active',
  status_label: 'Activo',
  current_state: { color: 'emerald', operational_effect: 'operating' },
  progress: 40,
};

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

async function mockRestrictedProject(page) {
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(mockPlatformClient);
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([restrictedProject]);
    if (apiPath === 'accounts/projects/45/' && method === 'GET') {
      return json({ detail: 'No tienes acceso a este proyecto.' }, 403);
    }
    return null;
  });
}

test('a denied project selection hides restricted data', {
  tag: [...PLATFORM_PROJECT_DETAIL, '@role:platform-client', '@outcome:error'],
}, async ({ page }) => {
  // Catches a 403 retaining an earlier project's name, sidebar, or commercial return link.
  await setPlatformAuth(page, { user: mockPlatformClient });
  await mockRestrictedProject(page);
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByTestId('project-row-45')).toContainText('Proyecto restringido');

  await page.getByTestId('project-row-45').click();

  const error = page.getByTestId('project-access-error');
  await expect(error).toContainText('No tienes acceso a este proyecto');
  await expect(error).toContainText('Tu cuenta no tiene permiso para abrir este espacio.');
  await expect(page.getByText('Proyecto restringido', { exact: true })).toHaveCount(0);
  await expect(page.getByTestId('project-back-to-panel')).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Volver a proyectos', exact: true })).toHaveCount(1);
});


const accessCases = [
  { actor: 2501, ownId: 25011, foreignId: 25021 },
  { actor: 2502, ownId: 25021, foreignId: 25011 },
];

async function mockOwnerBoundary(page, { actor, ownId, foreignId }, { status = 403 } = {}) {
  const user = { ...mockPlatformClient, id: actor, user_id: actor };
  const own = { ...restrictedProject, id: ownId, name: `Proyecto propio ${actor}` };
  const writes = [];
  await setPlatformAuth(page, { user });
  await mockApi(page, async ({ apiPath, method }) => {
    if (method !== 'GET') writes.push({ apiPath, method });
    if (apiPath === 'accounts/me/') return json(user);
    if (apiPath === 'accounts/projects/') return json([own]);
    if (apiPath === `accounts/projects/${ownId}/`) return json(own);
    if (apiPath === `accounts/projects/${ownId}/phases/`) return json([]);
    if (apiPath === `accounts/projects/${foreignId}/`) return json({ detail: 'Proyecto no disponible.' }, status);
    return null;
  });
  return { own, writes };
}

for (const viewport of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  for (const theme of ['light', 'dark']) {
    test.describe(`Project denial ${viewport} ${theme} (PA-252)`, () => {
      test.use({ ...viewportUse(viewport), colorScheme: theme });
      for (const access of accessCases) {
        test(`actor ${access.actor} returns to an owned project after a direct denial`, {
          tag: [...PLATFORM_PROJECT_DETAIL, '@role:platform-client', '@outcome:error'],
        }, async ({ page }) => {
          // quality: allow-deep-link (PA-252 explicitly requires an ID-substituted direct access)
          await page.addInitScript((value) => localStorage.setItem('platform_theme', value), theme);
          const { own, writes } = await mockOwnerBoundary(page, access);
          const response = page.waitForResponse((result) => result.url().includes(`/accounts/projects/${access.foreignId}/`));

          await page.goto(`/es-co/platform/projects/${access.foreignId}`, { waitUntil: 'domcontentloaded' });

          expect((await response).status()).toBe(403);
          await expect(page.getByTestId('project-access-error')).toContainText('No tienes acceso a este proyecto');
          await expect(page.getByText('Cargando proyecto…', { exact: true })).toHaveCount(0);
          await expect(page.getByTestId('project-back-to-panel')).toHaveCount(0);
          await page.getByRole('link', { name: 'Volver a proyectos', exact: true }).click();
          await expect(page).toHaveURL(/\/es-co\/platform\/projects$/);
          await page.getByTestId(`project-row-${own.id}`)
            .or(page.getByTestId(`project-card-${own.id}`)).filter({ visible: true }).click();
          await expect(page.getByRole('heading', { name: own.name, exact: true })).toBeVisible();
          await expect(page.getByTestId('project-access-error')).toHaveCount(0);
          expect(writes).toEqual([]);
        });
      }
    });
  }
}

test('an unavailable project preserves English in the exit (PA-252)', {
  tag: [...PLATFORM_PROJECT_DETAIL, '@role:platform-client', '@outcome:error'],
}, async ({ page }) => {
  // quality: allow-deep-link (the 404 direct-access recovery is the behavior under test)
  const { own } = await mockOwnerBoundary(page, accessCases[0], { status: 404 });

  await page.goto(`/en-us/platform/projects/${accessCases[0].foreignId}`, { waitUntil: 'domcontentloaded' });

  await expect(page.getByTestId('project-access-error')).toContainText('Project unavailable');
  const back = page.getByRole('link', { name: 'Back to projects', exact: true });
  await expect(back).toHaveAttribute('href', '/en-us/platform/projects');
  await expect(page.getByRole('button', { name: 'Try again', exact: true })).toHaveCount(0);
  await back.click();
  await expect(page).toHaveURL(/\/en-us\/platform\/projects$/);
  await expect(page.getByTestId(`project-row-${own.id}`)).toContainText(own.name);
});
