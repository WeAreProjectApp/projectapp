/**
 * Panel secure links.
 *
 * Covers flows: admin-secure-link-create, admin-secure-link-manage
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_SECURE_LINK_CREATE, ADMIN_SECURE_LINK_MANAGE } from '../helpers/flow-tags.js';
import {
  SECURE_LINK_TOKEN, json, revealedContent, secureLinkRow, secureLinkTypes,
} from '../helpers/secure-links.js';

test.setTimeout(60_000);

const CREATED_URL = `http://localhost:3000/es-co/secure-link/view#${SECURE_LINK_TOKEN}`;

function listPayload(rows) {
  return {
    results: rows,
    count: rows.length,
    page: 1,
    page_size: 25,
    counts: { active: 1, consumed: 1, expired: 0, revoked: 0, all: rows.length },
    unopened_received: 0,
    public_create_url: 'http://localhost:3000/es-co/secure-link',
  };
}

async function setupPanel(page, { rows = [secureLinkRow()], create } = {}) {
  let store = [...rows];
  const calls = { create: [], content: 0, revoke: 0, reactivate: [] };
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'panel/dashboard/' && method === 'GET') {
      return json({ finance: null, proposals: { total_proposals: 0, by_status: {}, recent: [] }, additional_modules: {}, operations: {}, attention: [] });
    }
    if (apiPath === 'secure-links/public/types/') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/' && method === 'GET') return json(listPayload(store));
    if (apiPath === 'secure-links/create/' && method === 'POST') {
      calls.create.push(route.request().postDataJSON());
      if (create) return create;
      const row = secureLinkRow({ id: 9, title: 'Llaves Wompi' });
      store = [row, ...store];
      return json({ ...row, url: CREATED_URL }, 201);
    }
    const match = apiPath.match(/^secure-links\/(\d+)\/(content\/|revoke\/|reactivate\/)?$/);
    if (!match) return null;
    const id = Number(match[1]);
    const row = store.find((item) => item.id === id);
    if (!match[2]) return json({ ...row, events: [{ id: 1, kind: 'created', kind_label: 'Creado', actor_name: 'Admin', ip_address: null, details: {}, created_at: row.created_at }] });
    if (match[2] === 'content/') {
      calls.content += 1;
      return json(revealedContent);
    }
    if (match[2] === 'revoke/') {
      calls.revoke += 1;
      Object.assign(row, { status: 'revoked', revoked_at: '2026-09-26T16:00:00Z' });
      return json(row);
    }
    calls.reactivate.push(route.request().postDataJSON());
    Object.assign(row, { status: 'active', consumed_at: null, activation_count: 2 });
    return json({ ...row, url: CREATED_URL });
  });
  return calls;
}

test.describe('Admin secure links', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8901, role: 'admin', is_staff: true } });
  });

  test('creates a link and shows the one-time URL with copy actions', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page, { rows: [] });
    await page.goto('/panel/secure-links', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Llaves Wompi');
    await page.getByTestId('secure-link-field-password').fill('prv_test_123');
    await page.getByTestId('secure-link-validity').getByRole('tab', { name: '3 días' }).click();
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-created-url')).toHaveText(CREATED_URL);
    await expect(page.getByTestId('secure-link-copy-message')).toBeVisible();
    expect(calls.create[0]).toMatchObject({
      secret_type: 'credentials', title: 'Llaves Wompi', fields: { password: 'prv_test_123' },
      validity_days: 3, language: 'es',
    });
  });

  test('shows the server error on the missing secret field', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupPanel(page, {
      rows: [],
      create: json({ error: 'Revisa los datos del formulario.', code: 'invalid', password: ['Este campo es obligatorio.'] }, 400),
    });
    await page.goto('/panel/secure-links', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Sin clave');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-form').getByText('Este campo es obligatorio.')).toBeVisible();
    await expect(page.getByTestId('secure-link-created-url')).toHaveCount(0);
  });

  test('views content without consuming it and revokes an active link', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/panel/secure-links?link=7', { waitUntil: 'domcontentloaded' });

    const detail = page.getByTestId('secure-link-detail');
    await expect(detail.getByTestId('secure-link-events')).toContainText('Creado');
    await detail.getByTestId('secure-link-view-content').click();
    await expect(detail.getByTestId('secure-link-text-service')).toHaveText('Django admin');
    await expect(detail.getByTestId('secure-link-status-active')).toBeVisible();

    await detail.getByTestId('secure-link-revoke').click();
    await expect(detail.getByTestId('secure-link-status-revoked')).toBeVisible();
    expect(calls.content).toBe(1);
    expect(calls.revoke).toBe(1);
  });

  test('reactivates a used link from its detail', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const calls = await setupPanel(page, {
      rows: [secureLinkRow({ status: 'consumed', consumed_at: '2026-09-26T15:30:00Z' })],
    });
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click();

    await expect(page.getByTestId('secure-links-tabs')).toContainText('Usados (1)');
    await page.getByTestId('secure-link-actions-7').filter({ visible: true }).click();
    await page.getByTestId('secure-link-reactivate-7').click();
    const reactivation = page.getByTestId('secure-link-reactivate');
    await reactivation.getByRole('tab', { name: '1 día' }).click();
    await reactivation.getByTestId('secure-link-reactivate-submit').click();

    await expect(page.getByTestId('secure-link-detail').getByTestId('secure-link-status-active')).toBeVisible();
    expect(calls.reactivate[0]).toEqual({ validity_days: 1, rotate: false });
  });
});
