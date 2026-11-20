/**
 * E2E tests for platform profile edit flow.
 *
 * @flow:platform-profile-edit
 * @flow:platform-profile-avatar-picker
 * Covers: profile page render with avatar and form fields,
 *         save changes, validation error display,
 *         cancel navigation, role badge display.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import {
  PLATFORM_PROFILE_AVATAR_PICKER,
  PLATFORM_PROFILE_EDIT,
} from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClient,
} from '../helpers/platform-auth.js';

const meResponse = (user) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(user),
});

function setupProfileMocks(page, user) {
  let savedProfile = { ...user };
  return mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(savedProfile);
    if (apiPath === 'accounts/me/' && method === 'PATCH') {
      savedProfile = { ...savedProfile, ...route.request().postDataJSON() };
      return meResponse(savedProfile);
    }
    if (apiPath.startsWith('accounts/clients/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    return null;
  });
}

const REQUIRED_PROFILE_FIELDS = [
  'Nombre', 'Apellido', 'Empresa', 'Teléfono', 'Cédula',
  'Fecha de nacimiento', 'Sexo', 'Nivel de educación',
];

const profileEditCases = [
  {
    user: { ...mockPlatformClient, id: 2, user_id: 2, education_level: 'universitario' },
    label: 'Nivel de educación', before: 'Universitario', key: 'ArrowDown',
    field: 'education_level', value: 'posgrado', after: 'Posgrado',
    otherLabel: 'Sexo', otherValue: 'Femenino',
  },
  {
    user: { ...mockPlatformAdmin, id: 72, user_id: 72 },
    label: 'Sexo', before: 'Masculino', key: 'End',
    field: 'gender', value: 'prefer_not_to_say', after: 'Prefiero no decir',
    otherLabel: 'Nivel de educación', otherValue: 'Universitario',
  },
];

for (const { user, label, before, key, field, value, after, otherLabel, otherValue } of profileEditCases) {
  test(`persists a keyboard selection in the labeled ${user.role} profile`, {
    tag: ['@outcome:success', ...PLATFORM_PROFILE_EDIT, `@role:platform-${user.role}`],
  }, async ({ page }) => {
    test.setTimeout(60_000);
    await setPlatformAuth(page, { user });
    await setupProfileMocks(page, user);
    await page.goto('/en-us/platform/profile', { waitUntil: 'domcontentloaded' });
    const main = page.locator('main');
    const save = main.getByRole('button', { name: 'Guardar cambios' });
    await expect(save).toBeVisible({ timeout: 30_000 });
    await Promise.all(REQUIRED_PROFILE_FIELDS.map(name =>
      expect(main.getByLabel(name, { exact: true })).toHaveAccessibleName(name)));

    const choice = main.getByRole('combobox', { name: label, exact: true });
    await expect(choice).toHaveText(before);
    await choice.focus();
    await choice.press('ArrowDown');
    await choice.press(key);
    await choice.press('Enter');
    await expect(choice).toHaveText(after);

    const patch = page.waitForRequest(request =>
      request.method() === 'PATCH' && new URL(request.url()).pathname === '/api/accounts/me/');
    await save.click();
    const expectedFields = {
      first_name: user.first_name, last_name: user.last_name, company_name: user.company_name,
      phone: user.phone, cedula: user.cedula, date_of_birth: user.date_of_birth,
      gender: user.gender, education_level: user.education_level, [field]: value,
    };
    expect((await patch).postDataJSON()).toEqual(expectedFields);
    await expect(main.getByText('Perfil actualizado correctamente.')).toBeVisible();

    const read = page.waitForResponse(response =>
      response.request().method() === 'GET' && new URL(response.url()).pathname === '/api/accounts/me/');
    await page.reload({ waitUntil: 'domcontentloaded' });
    expect(await (await read).json()).toMatchObject(expectedFields);
    await expect(choice).toHaveText(after);
    await expect(main.getByRole('combobox', { name: otherLabel, exact: true })).toHaveText(otherValue);
  });
}

test.describe('Platform Profile Edit — Admin', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  test('renders profile page with user data and editable fields', {
    tag: ['@outcome:display', ...PLATFORM_PROFILE_EDIT, '@role:platform-admin', '@responsive:clients'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — profile renders the user's data and editable fields; the edit interaction is covered by the save test)
    await setupProfileMocks(page, mockPlatformAdmin);
    await page.goto('/platform/profile', { waitUntil: 'domcontentloaded' });

    const main = page.locator('main');
    await expect(main.getByText('Admin E2E')).toBeVisible();
    await expect(main.getByText('admin@e2e-test.com')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cambiar foto de perfil' })).toBeVisible();
    await expect(page.getByRole('button', { name: /guardar cambios/i })).toBeVisible();
  });

  test('opening the avatar picker keeps the image-only single-file contract', {
    tag: ['@outcome:success', ...PLATFORM_PROFILE_AVATAR_PICKER, '@role:platform-admin'],
  }, async ({ page }) => {
    // Bug caught: the accessible avatar action stopped opening the image-only single-file picker.
    // quality: allow-deep-link (the picker contract is local to the profile surface; profile navigation is covered separately)
    await setupProfileMocks(page, mockPlatformAdmin);
    await page.goto('/platform/profile', { waitUntil: 'domcontentloaded' });

    const avatarPicker = page.getByRole('button', { name: 'Cambiar foto de perfil' });
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      avatarPicker.click(),
    ]);

    const avatarInput = fileChooser.element();
    expect(await avatarInput.getAttribute('accept')).toBe('image/*');
    expect(fileChooser.isMultiple()).toBe(false);
  });

  test('saving a changed first name confirms the update', {
    tag: ['@outcome:success', ...PLATFORM_PROFILE_EDIT, '@role:platform-admin'],
  }, async ({ page }) => {
    // Bug caught: saving the profile stopped sending the edited name or stopped confirming the update.
    await setupProfileMocks(page, mockPlatformAdmin);
    await page.goto('/platform/profile', { waitUntil: 'domcontentloaded' });

    const firstNameInput = page.getByLabel('Nombre', { exact: true });
    await firstNameInput.fill('Ada');

    const updateRequest = page.waitForRequest(
      (request) => /accounts\/me\/$/.test(request.url()) && request.method() === 'PATCH',
    );
    await page.getByRole('button', { name: /guardar cambios/i }).click();
    const request = await updateRequest;

    expect(request.postDataJSON()).toMatchObject({ first_name: 'Ada' });
    await expect(page.getByText('Perfil actualizado correctamente.')).toHaveText('Perfil actualizado correctamente.');
  });

  test('shows validation error on API failure', {
    tag: ['@outcome:error', ...PLATFORM_PROFILE_EDIT, '@role:platform-admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformAdmin);
      if (apiPath === 'accounts/me/' && method === 'PATCH') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'No pudimos actualizar tu perfil.' }),
        };
      }
      if (apiPath.startsWith('accounts/clients/')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.goto('/platform/profile', { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: /guardar cambios/i }).click();
    await expect(page.getByText(/no pudimos actualizar/i)).toContainText(/no pudimos actualizar/i);
  });
});

test.describe('Platform Profile Edit — Client', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test('client renders profile page with their data', {
    tag: ['@outcome:display', ...PLATFORM_PROFILE_EDIT, '@role:platform-client'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — client's profile renders their data)
    await setPlatformAuth(page, { user: mockPlatformClient });
    await setupProfileMocks(page, mockPlatformClient);
    await page.goto('/platform/profile', { waitUntil: 'domcontentloaded' });

    const main = page.locator('main');
    await expect(main.getByText('Client E2E')).toBeVisible();
    await expect(main.getByText('client@e2e-test.com')).toBeVisible();
  });
});

test.describe('Platform Profile Edit — Auth guard', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test('unauthenticated user is redirected to login', {
    tag: [...PLATFORM_PROFILE_EDIT, '@role:guest'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (auth guard — an unauthenticated user is redirected to login, asserted by URL)
    await page.goto('/platform/profile', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/login**', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/login/);
  });
});
