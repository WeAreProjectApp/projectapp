/**
 * E2E tests for platform complete-profile flow.
 *
 * @flow:platform-complete-profile
 * Covers: form render with required fields, submit with valid data,
 *         validation errors, redirect to dashboard on success,
 *         redirect to login when unauthenticated,
 *         redirect to dashboard when profile already completed.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectChoiceOption } from '../helpers/choice-select.js';
import { PLATFORM_COMPLETE_PROFILE } from '../helpers/flow-tags.js';
import { PANEL_VIEWPORTS } from '../helpers/viewports.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClientIncompleteProfile,
} from '../helpers/platform-auth.js';

const meResponse = (user) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(user),
});

test.describe('Platform Complete Profile', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  for (const profile of ['compact', 'desktop']) {
    test(`exposes the eight profile fields through their visible labels at ${profile}`, {
      tag: [...PLATFORM_COMPLETE_PROFILE, '@role:platform-client', '@outcome:display'],
    }, async ({ page }) => {
      await page.setViewportSize(PANEL_VIEWPORTS[profile]);
      await setPlatformAuth(page, { user: mockPlatformClientIncompleteProfile });
      await mockApi(page, async ({ apiPath }) => apiPath === 'accounts/me/' ? meResponse(mockPlatformClientIncompleteProfile) : null);
      // quality: allow-deep-link (incomplete profiles land on this form through the authentication guard)
      await page.goto('/es-co/platform/complete-profile', { waitUntil: 'domcontentloaded' });
      await page.getByText('Nombre', { exact: true }).click();

      await expect(page.getByLabel('Nombre', { exact: true })).toBeFocused();
      for (const label of ['Nombre', 'Apellido', 'Empresa', 'Teléfono', 'Cédula', 'Fecha de nacimiento', 'Sexo', 'Nivel de educación']) {
        const control = page.getByLabel(label, { exact: false });
        await expect(control).toHaveAccessibleName(new RegExp(`^${label}`));
        expect(await control.evaluate((element) => Array.from(element.labels, (item) => item.htmlFor))).toEqual([await control.getAttribute('id')]);
      }
      await expect(page.getByRole('button', { name: /completar perfil/i })).toBeDisabled();
    });
  }

  test('renders complete-profile form with all required fields', {
    tag: [...PLATFORM_COMPLETE_PROFILE, '@role:platform-client'],
  }, async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformClientIncompleteProfile });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformClientIncompleteProfile);
      }
      return null;
    });

    await page.goto('/platform/complete-profile', { waitUntil: 'domcontentloaded' });
    await page.getByText('Completa tu perfil').waitFor({ state: 'visible', timeout: 15000 });
    await expect(page.getByPlaceholder('Nombre de tu empresa')).toBeVisible();
    await expect(page.getByPlaceholder(/300 000 0000/)).toBeVisible();
    await expect(page.getByPlaceholder('1020304050')).toBeVisible();
    await expect(page.getByRole('button', { name: /completar perfil/i })).toBeVisible();
  });

  test('submit button is disabled when required fields are empty', {
    tag: [...PLATFORM_COMPLETE_PROFILE, '@role:platform-client'],
  }, async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformClientIncompleteProfile });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformClientIncompleteProfile);
      }
      return null;
    });

    await page.goto('/platform/complete-profile', { waitUntil: 'domcontentloaded' });
    await page.getByText('Completa tu perfil').waitFor({ state: 'visible', timeout: 15000 });

    const submitBtn = page.getByRole('button', { name: /completar perfil/i });
    await expect(submitBtn).toBeDisabled();
  });

  test('successful profile completion redirects a client to the documents portal', {
    tag: [...PLATFORM_COMPLETE_PROFILE, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    let profile = {
      ...mockPlatformClientIncompleteProfile,
      id: 34,
      user_id: 34,
    };
    await setPlatformAuth(page, { user: profile });

    await mockApi(page, async ({ apiPath, method, route }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(profile);
      }
      if (apiPath === 'accounts/me/complete-profile/' && method === 'POST') {
        const body = new Response(route.request().postDataBuffer(), {
          headers: { 'content-type': route.request().headers()['content-type'] },
        });
        profile = { ...profile, ...Object.fromEntries(await body.formData()), profile_completed: true };
        return meResponse(profile);
      }
      // Landing target: the client document portal loads its own documents.
      if (apiPath === 'accounts/documents/' && method === 'GET') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ documents: [], email: profile.email, email_verified: true }),
        };
      }
      if (apiPath === 'accounts/notifications/unread-count/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
      }
      if (apiPath.startsWith('accounts/projects')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.goto('/en-us/platform/complete-profile', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Completa tu perfil')).toBeVisible({ timeout: 30_000 });

    await page.getByPlaceholder('Tu nombre').fill('Client');
    await page.getByPlaceholder('Tu apellido').fill('Test');
    await page.getByPlaceholder('Nombre de tu empresa').fill('Test Corp');
    await page.getByPlaceholder(/300 000 0000/).fill('+57 300 111 2222');
    await page.getByPlaceholder('1020304050').fill('1234567890');
    await page.getByTestId('date-of-birth').fill('1992-03-15');
    const gender = page.getByRole('combobox', { name: 'Sexo', exact: true });
    const education = page.getByRole('combobox', { name: 'Nivel de educación', exact: true });
    const submit = page.getByRole('button', { name: /completar perfil/i });
    await gender.press('Enter');
    const listbox = page.getByRole('listbox');
    await expect(listbox.getByRole('option')).toHaveCount(5);
    await expect(listbox.getByRole('option', { name: 'Selecciona' })).toBeDisabled();
    await gender.press('ArrowDown');
    await gender.press('Enter');
    await expect(submit).toBeDisabled();
    await education.press('Enter');
    await expect(listbox.getByRole('option')).toHaveCount(7);
    await education.press('End');
    await education.press('ArrowUp');
    await education.press('ArrowUp');
    await education.press('Enter');
    await expect(submit).toBeEnabled();
    await submit.click();

    await page.waitForURL('**/platform/documents', { timeout: 15000 });
    await expect(page).toHaveURL(/\/platform\/documents/);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/platform\/documents$/);
    await page.goto('/en-us/platform/profile', { waitUntil: 'domcontentloaded' });
    await expect(gender).toHaveText('Femenino');
    await expect(education).toHaveText('Universitario');
  });

  test('shows error on API failure', {
    tag: ['@outcome:error', ...PLATFORM_COMPLETE_PROFILE, '@role:platform-client'],
  }, async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformClientIncompleteProfile });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformClientIncompleteProfile);
      }
      if (apiPath === 'accounts/me/complete-profile/' && method === 'POST') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'No pudimos completar tu perfil.' }),
        };
      }
      return null;
    });

    await page.goto('/en-us/platform/complete-profile', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Completa tu perfil')).toBeVisible({ timeout: 30_000 });

    await page.getByPlaceholder('Nombre de tu empresa').fill('Corp');
    await page.getByPlaceholder(/300 000 0000/).fill('+57 300 111 2222');
    await page.getByPlaceholder('1020304050').fill('1234567890');
    await page.getByTestId('date-of-birth').fill('1992-03-15');
    await selectChoiceOption(page, page.getByRole('combobox', { name: 'Sexo', exact: true }), 'Masculino');
    await selectChoiceOption(page, page.getByRole('combobox', { name: 'Nivel de educación', exact: true }), 'Técnico');

    await page.getByRole('button', { name: /completar perfil/i }).click();

    await expect(page.getByText(/no pudimos completar tu perfil/i)).toBeVisible();
  });

  test('unauthenticated user is redirected to login', {
    tag: [...PLATFORM_COMPLETE_PROFILE, '@role:guest'],
  }, async ({ page }) => {
    await page.goto('/platform/complete-profile', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/login**', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/login/);
  });

  test('user with completed profile is redirected away from complete-profile', {
    tag: [...PLATFORM_COMPLETE_PROFILE, '@role:platform-admin'],
  }, async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformAdmin);
      }
      if (apiPath === 'accounts/clients/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      if (apiPath === 'accounts/projects/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    // The /platform/dashboard route was removed — it redirects to projects.
    await page.goto('/platform/complete-profile', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/projects**', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/projects/);
  });
});
