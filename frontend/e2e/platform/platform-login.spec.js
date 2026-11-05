/**
 * E2E tests for platform login flow.
 *
 * @flow:platform-login
 * Covers: login page render, form validation, successful login redirect,
 *         error states, redirect to verify for unverified users,
 *         redirect to complete-profile for incomplete profiles,
 *         authenticated user redirect to dashboard.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_LOGIN, AUTHORIZED_LOGIN } from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
  mockPlatformClient,
  mockPlatformClientIncompleteProfile,
} from '../helpers/platform-auth.js';

const meResponse = (user) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(user),
});

/** Default mock that handles guest page-load calls. */
function setupGuestMocks(page) {
  return mockApi(page, async () => null);
}

const emailField = (page) => page.getByLabel('Email');
const passwordField = (page) => page.getByLabel('Contraseña');

/**
 * Wait for Nuxt hydration + GSAP entrance animation to complete.
 * GSAP usePageEntrance: 50ms delay + 0.6s duration + 0.08s stagger per element.
 * quality: allow-fragile-selector (waitForTimeout needed for Nuxt hydration + GSAP entrance animation)
 */
const loginFormReady = async (page) => {
  await page.waitForLoadState('load');
  await emailField(page).waitFor({ state: 'visible', timeout: 15000 });
  // Allow GSAP entrance animation to fully settle (50ms delay + 0.6s + stagger)
  // quality: allow-fragile-selector (waitForTimeout needed for Nuxt hydration + GSAP entrance animation)
  await page.waitForTimeout(2000);
  await expect(emailField(page)).toBeEditable({ timeout: 5000 });
};

test.describe('Platform Login', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test('renders login page with email and password fields', {
    tag: [...PLATFORM_LOGIN, '@role:guest'],
  }, async ({ page }) => {
    await setupGuestMocks(page);
    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await expect(emailField(page)).toBeVisible();
    await expect(passwordField(page)).toBeVisible();
    await expect(page.getByRole('button', { name: /iniciar sesión/i })).toBeVisible();
  });

  test('submit button is disabled when fields are empty', {
    tag: [...PLATFORM_LOGIN, '@role:guest'],
  }, async ({ page }) => {
    await setupGuestMocks(page);
    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    const submitBtn = page.getByRole('button', { name: /iniciar sesión/i });
    await expect(submitBtn).toBeDisabled();
  });

  test('shows validation error for invalid email format', {
    tag: ['@outcome:error', ...PLATFORM_LOGIN, '@role:guest'],
  }, async ({ page }) => {
    await setupGuestMocks(page);
    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await emailField(page).fill('not-an-email');
    await passwordField(page).fill('somepassword');
    // Bypass HTML5 type="email" validation so the custom validator runs
    await page.evaluate(() => document.querySelector('form').setAttribute('novalidate', ''));
    await page.getByRole('button', { name: /iniciar sesión/i }).click();

    await expect(page.getByText('Ingresa un email válido.')).toBeVisible();
  });

  test('shows error message on invalid credentials', {
    tag: ['@outcome:error', ...PLATFORM_LOGIN, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/login/' && method === 'POST') {
        return {
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Credenciales incorrectas.' }),
        };
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await emailField(page).fill('wrong@test.com');
    await passwordField(page).fill('wrongpass');
    await page.getByRole('button', { name: /iniciar sesión/i }).click();

    await expect(page.getByText('Credenciales incorrectas.')).toBeVisible();
  });

  test('successful login redirects onboarded user to dashboard', {
    tag: [...PLATFORM_LOGIN, '@role:platform-admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/login/' && method === 'POST') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            requires_verification: false,
            tokens: { access: 'mock-access', refresh: 'mock-refresh' },
            user: mockPlatformAdmin,
          }),
        };
      }
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformAdmin);
      }
      if (apiPath.startsWith('accounts/clients')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await emailField(page).fill('admin@e2e-test.com');
    await passwordField(page).fill('validpassword');
    await page.getByRole('button', { name: /iniciar sesión/i }).click();

    await page.waitForURL('**/platform/dashboard', { timeout: 15000 });
    await expect(page).toHaveURL(/\/platform\/dashboard/);
  });

  test('successful login redirects an onboarded client to the documents portal', {
    tag: [...PLATFORM_LOGIN, '@role:platform-client'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/login/' && method === 'POST') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            requires_verification: false,
            tokens: { access: 'mock-access', refresh: 'mock-refresh' },
            user: mockPlatformClient,
          }),
        };
      }
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformClient);
      }
      // Landing target: the client document portal loads its own documents.
      if (apiPath === 'accounts/documents/' && method === 'GET') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ documents: [], email: mockPlatformClient.email, email_verified: true }),
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

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await emailField(page).fill('client@e2e-test.com');
    await passwordField(page).fill('validpassword');
    await page.getByRole('button', { name: /iniciar sesión/i }).click();

    await page.waitForURL('**/platform/documents', { timeout: 15000 });
    await expect(page).toHaveURL(/\/platform\/documents/);
  });

  test('login of non-onboarded user redirects to verify page', {
    tag: [...PLATFORM_LOGIN, '@role:platform-client'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/login/' && method === 'POST') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            requires_verification: true,
            verification_token: 'mock-verification-token',
            email: 'newclient@test.com',
          }),
        };
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await emailField(page).fill('newclient@test.com');
    await passwordField(page).fill('temppassword');
    await page.getByRole('button', { name: /iniciar sesión/i }).click();

    await page.waitForURL('**/platform/verify', { timeout: 15000 });
    await expect(page).toHaveURL(/\/platform\/verify/);
  });

  test('login of user with incomplete profile redirects to complete-profile', {
    tag: [...PLATFORM_LOGIN, '@role:platform-client'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/login/' && method === 'POST') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            requires_verification: false,
            tokens: { access: 'mock-access', refresh: 'mock-refresh' },
            user: mockPlatformClientIncompleteProfile,
          }),
        };
      }
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformClientIncompleteProfile);
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await emailField(page).fill('incomplete@e2e-test.com');
    await passwordField(page).fill('validpassword');
    await page.getByRole('button', { name: /iniciar sesión/i }).click();

    await page.waitForURL('**/platform/complete-profile', { timeout: 15000 });
    await expect(page).toHaveURL(/\/platform\/complete-profile/);
  });

  test('already authenticated admin visiting login is redirected to dashboard', {
    tag: [...PLATFORM_LOGIN, '@role:platform-admin'],
  }, async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') {
        return meResponse(mockPlatformAdmin);
      }
      if (apiPath.startsWith('accounts/clients')) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/platform/dashboard', { timeout: 30000 });
    await expect(page).toHaveURL(/\/platform\/dashboard/);
  });

  test('shows deactivated account error message', {
    tag: ['@outcome:error', ...PLATFORM_LOGIN, '@role:guest'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'accounts/login/' && method === 'POST') {
        return {
          status: 403,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Tu cuenta ha sido desactivada. Contacta al administrador.' }),
        };
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);

    await emailField(page).fill('deactivated@test.com');
    await passwordField(page).fill('somepass');
    await page.getByRole('button', { name: /iniciar sesión/i }).click();

    await expect(page.getByText(/cuenta ha sido desactivada/)).toBeVisible();
  });

  test('email code login stores the client session and follows a safe documents redirect', {
    tag: [...AUTHORIZED_LOGIN, '@outcome:success', '@role:platform-client'],
  }, async ({ page }) => {
    // Fails if code login does not persist the returned JWT/profile or ignores a
    // local redirect requested by the client before arriving at the login form.
    const requests = [];
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/config/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'csrf', google_client_id: '' }) };
      }
      if (apiPath === 'auth/platform/email-request/' && method === 'POST') {
        requests.push({ apiPath, body: route.request().postDataJSON() });
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ challenge_id: 'platform-challenge', detail: 'Si el correo está registrado y habilitado, recibirás un código.', retry_after: 0 }) };
      }
      if (apiPath === 'auth/platform/email-verify/' && method === 'POST') {
        requests.push({ apiPath, body: route.request().postDataJSON() });
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ tokens: { access: 'code-access-token', refresh: 'code-refresh-token' }, user: mockPlatformClient }) };
      }
      if (apiPath === 'accounts/documents/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ documents: [], email: mockPlatformClient.email, email_verified: true }) };
      }
      if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) };
      }
      if (apiPath.startsWith('accounts/projects') && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      }
      return null;
    });

    await page.goto('/platform/login?redirect=/platform/documents', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);
    await page.getByRole('tab', { name: 'Código por correo' }).click();
    await page.getByTestId('access-email').fill('client@e2e-test.com');
    await page.getByRole('button', { name: 'Enviar código' }).click();
    await page.getByTestId('access-code').fill('12345');
    await expect(page.getByRole('button', { name: 'Verificar e iniciar sesión' })).toBeDisabled();
    await page.getByTestId('access-code').fill('123456');
    await page.getByRole('button', { name: 'Verificar e iniciar sesión' }).click();

    await expect(page).toHaveURL(/\/platform\/documents$/);
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('platform_access_token'))).toBe('code-access-token');
    expect(requests).toEqual([
      { apiPath: 'auth/platform/email-request/', body: { email: 'client@e2e-test.com', recaptcha_token: '' } },
      { apiPath: 'auth/platform/email-verify/', body: { challenge_id: 'platform-challenge', code: '123456', next: '' } },
    ]);
  });

  test('email code request shows its server rejection without exposing whether an account exists', {
    tag: [...AUTHORIZED_LOGIN, '@outcome:error', '@role:guest'],
  }, async ({ page }) => {
    // Fails if rate-limit or account rejection responses disappear instead of
    // keeping the visitor on the generic, non-enumerating access surface.
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/config/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'csrf', google_client_id: '' }) };
      }
      if (apiPath === 'auth/platform/email-request/' && method === 'POST') {
        return { status: 429, contentType: 'application/json', body: JSON.stringify({ detail: 'Espera antes de pedir otro código.' }) };
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);
    await page.getByTestId('access-email').fill('unknown@example.com');
    await page.getByRole('button', { name: 'Enviar código' }).click();

    await expect(page.getByRole('alert')).toHaveText('Espera antes de pedir otro código.');
  });

  test('email code verification exposes a recoverable server failure', {
    tag: [...AUTHORIZED_LOGIN, '@outcome:failure', '@role:guest'],
  }, async ({ page }) => {
    // Fails if a failed verification leaves the visitor in a silent busy state
    // rather than presenting a concrete retryable failure message.
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/config/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'csrf', google_client_id: '' }) };
      }
      if (apiPath === 'auth/platform/email-request/' && method === 'POST') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ challenge_id: 'unavailable-challenge', detail: 'Si el correo está registrado y habilitado, recibirás un código.', retry_after: 0 }) };
      }
      if (apiPath === 'auth/platform/email-verify/' && method === 'POST') {
        return { status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'No pudimos completar el acceso. Intenta de nuevo.' }) };
      }
      return null;
    });

    await page.goto('/platform/login', { waitUntil: 'domcontentloaded' });
    await loginFormReady(page);
    await page.getByTestId('access-email').fill('client@e2e-test.com');
    await page.getByRole('button', { name: 'Enviar código' }).click();
    await page.getByTestId('access-code').fill('123456');
    await page.getByRole('button', { name: 'Verificar e iniciar sesión' }).click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos completar el acceso. Intenta de nuevo.');
  });
});
