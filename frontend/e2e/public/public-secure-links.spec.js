/**
 * Public secure-link pages.
 *
 * Covers flows: public-secure-link-reveal, public-secure-link-create
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PUBLIC_SECURE_LINK_CREATE, PUBLIC_SECURE_LINK_REVEAL } from '../helpers/flow-tags.js';
import {
  SECURE_LINK_TOKEN, json, publicStatus, revealedContent, secureLinkTypes,
} from '../helpers/secure-links.js';

test.setTimeout(60_000);

const VIEW_URL = `/es-co/secure-link/view#${SECURE_LINK_TOKEN}`;

async function mockReveal(page, { status = publicStatus(), reveal = json(revealedContent) } = {}) {
  const calls = { status: [], reveal: [] };
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'secure-links/public/status/' && method === 'POST') {
      calls.status.push(route.request().postDataJSON());
      return typeof status.status === 'number' ? status : json(status);
    }
    if (apiPath === 'secure-links/public/reveal/' && method === 'POST') {
      calls.reveal.push(route.request().postDataJSON());
      return reveal;
    }
    return null;
  });
  return calls;
}

test('opening the page does not consume the link until Show content is pressed', {
  tag: [...PUBLIC_SECURE_LINK_REVEAL, '@role:guest', '@outcome:success'],
}, async ({ page }) => {
  const calls = await mockReveal(page);

  await page.goto(VIEW_URL, { waitUntil: 'domcontentloaded' });

  const reveal = page.getByTestId('secure-link-reveal');
  await expect(reveal).toBeVisible();
  expect(calls.reveal).toHaveLength(0);
  expect(calls.status[0]).toEqual({ token: SECURE_LINK_TOKEN });

  await reveal.click();
  await expect(page.getByTestId('secure-link-text-service')).toHaveText('Django admin');
  await expect(page.getByTestId('secure-link-text-password')).toHaveText('••••••••');
  await page.getByTestId('secure-link-reveal-password').click();
  await expect(page.getByTestId('secure-link-text-password')).toHaveText('S3cr3t-E2E!');
  expect(calls.reveal).toEqual([{ token: SECURE_LINK_TOKEN }]);
});

test('a link used by someone else meanwhile explains how to get it reactivated', {
  tag: [...PUBLIC_SECURE_LINK_REVEAL, '@role:guest', '@outcome:failure'],
}, async ({ page }) => {
  await mockReveal(page, {
    reveal: json({ error: 'Este enlace ya fue utilizado.', code: 'link_consumed' }, 410),
  });

  await page.goto(VIEW_URL, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('secure-link-reveal').click();

  await expect(page.getByTestId('secure-link-state-consumed')).toHaveText('Este enlace ya fue utilizado');
  await expect(page.getByText(/pide a quien te lo envió que lo reactive/)).toHaveCount(1);
  await expect(page.getByTestId('secure-link-content')).toHaveCount(0);
});

test('the recipient reads the link metadata and copies a revealed value', {
  tag: [...PUBLIC_SECURE_LINK_REVEAL, '@role:guest', '@outcome:display'],
}, async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await mockReveal(page);

  // quality: allow-deep-link (the emailed one-time URL is the only real entry point to this page)
  await page.goto(VIEW_URL, { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('secure-link-view-page')).toContainText('Credenciales de acceso · Enviado por ProjectApp');
  await page.getByTestId('secure-link-reveal').click();
  await page.getByTestId('secure-link-copy-password').click();

  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe('S3cr3t-E2E!');
});

test('a link created by a client sends the team member to sign in and keeps the token', {
  tag: [...PUBLIC_SECURE_LINK_REVEAL, '@role:guest', '@outcome:display'],
}, async ({ page }) => {
  await mockReveal(page, { status: publicStatus({ team_only: true, can_reveal: false, sender: 'Laura' }) });
  await page.route('**/admin/login/**', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: '<main>login</main>' }));

  // quality: allow-deep-link (the emailed one-time URL is the only real entry point to this page)
  await page.goto(VIEW_URL, { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('secure-link-reveal')).toHaveCount(0);
  await page.getByTestId('secure-link-staff-login').click();

  await expect(page).toHaveURL(/\/admin\/login\/\?next=%2Fes-co%2Fsecure-link%2Fview$/);
  expect(await page.evaluate(() => sessionStorage.getItem('secure-link-pending-token'))).toBe(SECURE_LINK_TOKEN);
});

async function mockCreate(page, { create } = {}) {
  const calls = [];
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'secure-links/public/types/' && method === 'GET') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/public/create/' && method === 'POST') {
      calls.push(route.request().postDataJSON());
      return create || json({
        accepted: true,
        url: `http://localhost:3000/es-co/secure-link/view#${SECURE_LINK_TOKEN}`,
        expires_at: '2026-09-29T15:00:00Z',
      }, 201);
    }
    return null;
  });
  return calls;
}

test('a client creates a link for the team and gets the URL to send', {
  tag: [...PUBLIC_SECURE_LINK_CREATE, '@role:guest', '@outcome:success'],
}, async ({ page }) => {
  const calls = await mockCreate(page);

  await page.goto('/es-co/secure-link', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('secure-link-field-service').fill('GoDaddy');
  await page.getByTestId('secure-link-field-password').fill('Cliente-Clave-1');
  await page.getByTestId('secure-link-public-name').fill('Laura Gómez');
  await page.getByTestId('secure-link-public-validity').getByRole('tab', { name: '3 días' }).click();
  await page.getByTestId('secure-link-public-submit').click();

  await expect(page.getByTestId('secure-link-create-url')).toContainText(`#${SECURE_LINK_TOKEN}`);
  await expect(page.getByTestId('secure-link-create-mail')).toHaveAttribute('href', /^mailto:team@projectapp\.co/);
  expect(calls[0]).toMatchObject({
    secret_type: 'credentials',
    fields: { service: 'GoDaddy', password: 'Cliente-Clave-1' },
    creator_name: 'Laura Gómez',
    validity_days: 3,
    website: '',
  });
});

test('missing required values are shown on the field without creating the link', {
  tag: [...PUBLIC_SECURE_LINK_CREATE, '@role:guest', '@outcome:error'],
}, async ({ page }) => {
  await mockCreate(page, {
    create: json({ error: 'Revisa los datos del formulario.', code: 'invalid', password: ['Este campo es obligatorio.'] }, 400),
  });

  await page.goto('/es-co/secure-link', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('secure-link-public-name').fill('Laura Gómez');
  await page.getByTestId('secure-link-public-submit').click();

  await expect(page.getByText('Este campo es obligatorio.')).toBeVisible();
  await expect(page.getByTestId('secure-link-create-url')).toHaveCount(0);
});
