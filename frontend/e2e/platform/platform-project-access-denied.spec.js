/**
 * E2E coverage for the project-space access-denied state.
 *
 * @flow:platform-project-detail
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_PROJECT_DETAIL } from '../helpers/flow-tags.js';
import { mockPlatformClient, setPlatformAuth } from '../helpers/platform-auth.js';
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
  await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });
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
