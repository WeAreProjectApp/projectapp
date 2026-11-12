/**
 * E2E tests for the admin login entry point and the panel session guard.
 *
 * Admin authentication retains Django password handoff while exposing an
 * authorized email-code alternative. CAPTCHA interactions are covered by
 * captcha/panel-login-captcha.spec.js with its isolated server.
 *
 * The second describe block covers the companion flow
 * admin-panel-session-expired: what happens when a browser without a valid
 * staff session requests a protected /panel/* route directly (middleware
 * frontend/middleware/admin-auth.js).
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { ADMIN_LOGIN, ADMIN_PANEL_SESSION_EXPIRED, AUTHORIZED_LOGIN } from '../helpers/flow-tags.js';

test.describe('Admin Login', () => {
  test('password login remains available while an email code reaches the returned panel redirect', {
    tag: [...AUTHORIZED_LOGIN, '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    // Fails if the code journey removes the password fallback, posts a different
    // challenge, or follows a redirect other than the backend's safe destination.
    const posts = [];
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/config/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'csrf', google_client_id: '' }) };
      }
      if (apiPath === 'auth/panel/email-request/' && method === 'POST') {
        posts.push({ apiPath, body: route.request().postDataJSON() });
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ challenge_id: 'panel-challenge', detail: 'Si el correo está registrado y habilitado, recibirás un código.', retry_after: 0 }) };
      }
      if (apiPath === 'auth/panel/email-verify/' && method === 'POST') {
        posts.push({ apiPath, body: route.request().postDataJSON() });
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ redirect: '/panel/access' }) };
      }
      if (apiPath === 'auth/check/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'code-admin', is_staff: true, is_superuser: true } }) };
      }
      if (apiPath === 'accounts/access/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], count: 0, page: 1, pages: 1, counts: {}, can_manage_team: true }) };
      }
      return null;
    });

    await page.goto('/panel/login?next=/panel/access', { waitUntil: 'domcontentloaded' });

    const passwordLink = page.getByRole('link', { name: 'Entrar con contraseña' });
    await expect(passwordLink).toHaveAttribute('href', '/admin/login/?next=%2Fpanel%2Faccess');
    await page.getByRole('tab', { name: 'Código por correo' }).click();
    await page.getByTestId('access-email').fill('admin@example.com');
    await page.getByRole('button', { name: 'Enviar código' }).click();
    await expect(page.getByRole('status')).toHaveText('Si el correo está registrado y habilitado, recibirás un código.');
    await page.getByTestId('access-code').fill('123456');
    await page.getByRole('button', { name: 'Verificar e iniciar sesión' }).click();

    await expect(page).toHaveURL(/\/panel\/access$/);
    expect(posts).toEqual([
      { apiPath: 'auth/panel/email-request/', body: { email: 'admin@example.com', recaptcha_token: '' } },
      { apiPath: 'auth/panel/email-verify/', body: { challenge_id: 'panel-challenge', code: '123456', next: '/panel/access' } },
    ]);
  });

  test('a failed email-code verification tells the administrator that the code cannot be used', {
    tag: [...AUTHORIZED_LOGIN, '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    // Fails if an unavailable or expired code error is hidden, leaving the
    // operator unable to recover through the visible password or retry paths.
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/config/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'csrf', google_client_id: '' }) };
      }
      if (apiPath === 'auth/panel/email-request/' && method === 'POST') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ challenge_id: 'expired-challenge', detail: 'Si el correo está registrado y habilitado, recibirás un código.', retry_after: 0 }) };
      }
      if (apiPath === 'auth/panel/email-verify/' && method === 'POST') {
        return { status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'No pudimos verificar el código. Intenta de nuevo.' }) };
      }
      return null;
    });

    await page.goto('/panel/login', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('access-email').fill('admin@example.com');
    await page.getByRole('button', { name: 'Enviar código' }).click();
    await page.getByTestId('access-code').fill('123456');
    await page.getByRole('button', { name: 'Verificar e iniciar sesión' }).click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos verificar el código. Intenta de nuevo.');
  });
});

test.describe('Admin Panel Session Guard', () => {
  test('requesting a protected panel route without a staff session hard-redirects to the Django login with next=', {
    tag: [...ADMIN_PANEL_SESSION_EXPIRED, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (this flow is triggered by a direct request
    // to a protected /panel/* route — a stale bookmark, a shared link, or a
    // browser reopened after the session cookie expired. There is no in-page
    // element to click before the admin-auth middleware's hard redirect fires;
    // page.goto() IS the user action under test, not a bypass of one.)
    // Fails if admin-auth stops redirecting on a 401/403 from /api/auth/check/
    // (letting an unauthenticated browser render the panel), or if it drops/
    // mangles the `next=` param so signing in again no longer returns the
    // admin to the page they originally requested.
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/' && method === 'GET') {
        return {
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Authentication credentials were not provided.' }),
        };
      }
      return null;
    });

    // Stub the destination, the same way this suite stubs /api/**: /admin/ is
    // proxied to Django (nuxt.config dev proxy), which only runs on a dev box.
    // Without a listener the proxy fails at the network level, Chromium cancels
    // the navigation and the URL never leaves the panel route — so the guard
    // under test would read as broken wherever Django is not up (CI included).
    await page.route('**/admin/login/**', (route) => route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<html><body>Django admin login</body></html>',
    }));

    // Direct navigation to a protected panel page, pre-localized so the locale
    // redirect doesn't add an extra hop before the auth guard runs.
    await page.goto('/en-us/panel/proposals', { waitUntil: 'domcontentloaded' }).catch(() => {});

    // The middleware redirects with window.location.href (full page nav, not
    // navigateTo/SPA), so it lands outside the Nuxt router entirely. Assert the
    // full concrete URL — both the Django login path AND the preserved next=
    // target — so this fails if either the redirect or the `next=` value drifts.
    await expect(page).toHaveURL(/\/admin\/login\/\?next=\/en-us\/panel\/proposals$/, { timeout: 20_000 });

    const redirectUrl = new URL(page.url());
    expect(redirectUrl.searchParams.get('next')).toBe('/en-us/panel/proposals');
  });
});
