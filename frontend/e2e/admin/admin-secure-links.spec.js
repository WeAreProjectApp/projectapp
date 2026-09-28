/**
 * Panel secure links.
 *
 * Covers flows: admin-secure-link-create, admin-secure-link-manage
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
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

async function setupPanel(page, {
  rows = [secureLinkRow()], create, types, detail, update, remove, list,
} = {}) {
  let store = [...rows];
  const calls = {
    create: [], content: 0, revoke: 0, reactivate: [], update: [], delete: 0,
  };
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'panel/dashboard/' && method === 'GET') {
      return json({ finance: null, proposals: { total_proposals: 0, by_status: {}, recent: [] }, additional_modules: {}, operations: {}, attention: [] });
    }
    if (apiPath === 'secure-links/public/types/') return types ? types() : json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/' && method === 'GET') {
      return list ? list({ route, store }) : json(listPayload(store));
    }
    if (apiPath === 'secure-links/create/' && method === 'POST') {
      calls.create.push(route.request().postDataJSON());
      if (create) return typeof create === 'function' ? create() : create;
      const row = secureLinkRow({ id: 9, title: 'Llaves Wompi' });
      store = [row, ...store];
      return json({ ...row, url: CREATED_URL }, 201);
    }
    const match = apiPath.match(/^secure-links\/(\d+)\/(content\/|revoke\/|reactivate\/)?$/);
    if (!match) return null;
    const id = Number(match[1]);
    const row = store.find((item) => item.id === id);
    if (!match[2] && method === 'GET') {
      if (detail) return typeof detail === 'function' ? detail({ route, row }) : detail;
      return json({ ...row, events: [{ id: 1, kind: 'created', kind_label: 'Creado', actor_name: 'Admin', ip_address: null, details: {}, created_at: row.created_at }] });
    }
    if (!match[2] && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      calls.update.push(payload);
      if (update) return typeof update === 'function' ? update({ route, row, payload }) : update;
      Object.assign(row, payload);
      return json(row);
    }
    if (!match[2] && method === 'DELETE') {
      calls.delete += 1;
      if (remove) return typeof remove === 'function' ? remove({ route, row }) : remove;
      store = store.filter((item) => item.id !== id);
      return { status: 204, body: '' };
    }
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
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Llaves Wompi');
    await page.getByTestId('secure-link-field-password').fill('prv_test_123');
    await page.getByTestId('secure-link-validity').getByRole('tab', { name: '3 días' }).click();
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-created-url')).toHaveText(CREATED_URL);
    await expect(page.getByTestId('secure-link-copy-message')).toBeVisible();
    expect(calls.create[0]).toMatchObject({
      secret_type: 'credentials', title: 'Llaves Wompi', fields: { password: 'prv_test_123' },
      validity_days: 3, language: 'es', client: null, project: null,
    });
  });

  test('shows the server error on the missing secret field', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupPanel(page, {
      rows: [],
      create: json({ error: 'Revisa los datos del formulario.', code: 'invalid', password: ['Este campo es obligatorio.'] }, 400),
    });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Sin clave');
    await page.getByTestId('secure-link-field-password').fill('server-rejected');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-form').getByText('Este campo es obligatorio.')).toBeVisible();
    await expect(page.getByTestId('secure-link-created-url')).toHaveCount(0);
  });

  test('views content without consuming it and revokes an active link', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links?link=7', { waitUntil: 'domcontentloaded' });
    await waitForNuxtApp(page);

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
    // quality: allow-deep-link (the panel home is the shell entry; its visible navigation opens the secure-links module)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
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
  test('creates custom content without a client or project', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const calls = await setupPanel(page, { rows: [] });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-type').selectOption('custom');
    await page.getByTestId('secure-link-title').fill('Referencia');
    await page.getByTestId('secure-link-field-custom_name').fill('Instrucciones');
    await page.getByTestId('secure-link-field-content').fill('  Texto privado\ncon espacios  ');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-created-url')).toHaveText(CREATED_URL);
    await page.getByTestId('secure-link-copy-created').click();
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(CREATED_URL);
    expect(calls.create[0]).toMatchObject({
      secret_type: 'custom', client: null, project: null,
      fields: { custom_name: 'Instrucciones', content: '  Texto privado\ncon espacios  ' },
    });
  });

  test('keeps the content ready to retry after an HTML failure', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const responses = [
      { status: 502, contentType: 'text/html', body: '<html>private server traceback</html>' },
      json({ ...secureLinkRow(), url: CREATED_URL }, 201),
    ];
    await setupPanel(page, { rows: [], create: () => responses.shift() });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Acceso');
    await page.getByTestId('secure-link-field-password').fill('retry-value');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-general-error')).toHaveText('No se pudo crear el enlace.');
    await expect(page.getByTestId('secure-link-form')).not.toContainText('traceback');
    await expect(page.getByTestId('secure-link-field-password')).toHaveValue('retry-value');
    await page.getByTestId('secure-link-save').click();
    await expect(page.getByTestId('secure-link-created-url')).toHaveText(CREATED_URL);
  });

  test('recovers the type catalog before submitting', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    let unavailable = true;
    await setupPanel(page, { types: () => unavailable ? json({ error: 'unavailable' }, 503) : json({ types: secureLinkTypes }) });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-links-new').click();

    await expect(page.getByTestId('secure-link-types-error')).toContainText('No pudimos cargar');
    await expect(page.getByTestId('secure-link-save')).toBeDisabled();
    unavailable = false;
    await page.getByTestId('secure-link-types-retry').click();
    await page.getByTestId('secure-link-title').fill('Recuperado');
    await page.getByTestId('secure-link-field-password').fill('test-value');
    await page.getByTestId('secure-link-save').click();
    await expect(page.getByTestId('secure-link-created-url')).toHaveText(CREATED_URL);
  });

  test('opens a fresh modal with empty masked credentials', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupPanel(page);
    // quality: allow-deep-link (the panel home is the shell entry; its visible navigation opens the secure-links module)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click();
    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-field-username').fill('previous-user');
    await page.getByTestId('secure-link-field-password').fill('previous-password');
    await page.getByTestId('secure-link-field-toggle-password').click();
    await page.getByRole('dialog').filter({ has: page.getByTestId('secure-link-form') }).getByRole('button', { name: 'Cancelar', exact: true }).click();
    await page.getByTestId('secure-links-new').click();

    await expect(page.getByTestId('secure-link-field-username')).toHaveValue('');
    await expect(page.getByTestId('secure-link-field-password')).toHaveValue('');
    await expect(page.getByTestId('secure-link-field-password')).toHaveAttribute('type', 'password');
    await expect(page.getByTestId('secure-link-field-password')).toHaveAttribute('autocomplete', 'new-password');
  });

  // Bug caught: metadata edits used to reveal the secret even when no content changed.
  test('edits link metadata without revealing its content', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-open-7').click();
    await page.getByTestId('secure-link-edit').click();

    await expect(page.getByTestId('secure-link-form')).toContainText('Editar enlace');
    await page.getByTestId('secure-link-title').fill('Acceso Django actualizado');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-links-page')).toContainText('Acceso Django actualizado');
    expect(calls.content).toBe(0);
    expect(calls.update[0]).toEqual({ title: 'Acceso Django actualizado', client: null, project: null });
  });

  // Bug caught: editing content could discard the fields retrieved explicitly from the detail.
  test('edits revealed content with the refreshed field values', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-open-7').click();
    await page.getByTestId('secure-link-edit-content').click();

    await expect(page.getByTestId('secure-link-field-password')).toHaveValue('S3cr3t-E2E!');
    await page.getByTestId('secure-link-field-password').fill('S3cr3t-Updated!');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-links-page')).toContainText('Admin Django producción');
    expect(calls.content).toBe(1);
    expect(calls.update[0]).toMatchObject({
      title: 'Admin Django producción', secret_type: 'credentials', fields: { password: 'S3cr3t-Updated!' },
    });
  });

  // Bug caught: a rejected metadata change could clear the draft that the administrator needs to correct.
  test('keeps a rejected metadata draft for correction', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupPanel(page, {
      update: json({ title: ['El título ya existe.'] }, 400),
    });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-open-7').click();
    await page.getByTestId('secure-link-edit').click();
    await page.getByTestId('secure-link-title').fill('Título duplicado');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-form')).toContainText('El título ya existe.');
    await expect(page.getByTestId('secure-link-title')).toHaveValue('Título duplicado');
  });

  // Bug caught: cancelling the destructive dialog could still remove the secure link locally.
  test('cancels deletion without removing the secure link', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    // quality: allow-deep-link (the panel home is the shell entry; its visible navigation opens the secure-links module)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click();
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-delete-7').click();
    await page.getByRole('dialog').getByRole('button', { name: 'Cancelar', exact: true }).click();

    await expect(page.getByTestId('secure-link-row-7')).toContainText('Admin Django producción');
    expect(calls.delete).toBe(0);
  });

  // Bug caught: a server failure could hide an undeleted secret from the current list.
  test('keeps the secure link visible after a failed deletion', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const calls = await setupPanel(page, { remove: json({ detail: 'No se pudo eliminar.' }, 500) });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-delete-7').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('secure-link-row-7')).toContainText('Admin Django producción');
    expect(calls.delete).toBe(1);
  });

  // Bug caught: confirming deletion could leave the stale row visible after the server removed it.
  test('removes the secure link after confirmed deletion', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-delete-7').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Sin enlaces en esta vista')).toHaveCount(1);
    expect(calls.delete).toBe(1);
  });

  // Bug caught: a failed detail request left the administrator on an endless loading state.
  test('retries a failed detail request', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    let unavailable = true;
    await setupPanel(page, {
      detail: ({ row }) => unavailable
        ? json({ detail: 'Servicio no disponible.' }, 503)
        : json({ ...row, events: [{ id: 1, kind: 'created', kind_label: 'Creado', actor_name: 'Admin', ip_address: null, details: {}, created_at: row.created_at }] }),
    });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-open-7').click();

    await expect(page.getByTestId('secure-link-detail-error')).toContainText('Servicio no disponible.');
    unavailable = false;
    await page.getByTestId('secure-link-detail-retry').click();
    await expect(page.getByTestId('secure-link-detail')).toContainText('Admin Django producción');
  });

  // Bug caught: a saved edit could disappear after reloading before the administrator deletes the link.
  test('persists a created link through edit reload and deletion', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page, { rows: [] });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Llaves Wompi');
    await page.getByTestId('secure-link-field-password').fill('created-secret');
    await page.getByTestId('secure-link-save').click();
    await page.getByTestId('secure-link-created-close').click();
    await page.getByTestId('secure-link-actions-9').click();
    await page.getByTestId('secure-link-open-9').click();
    await page.getByTestId('secure-link-edit').click();
    await page.getByTestId('secure-link-title').fill('Llaves Wompi editadas');
    await page.getByTestId('secure-link-save').click();
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('secure-link-row-9')).toContainText('Llaves Wompi editadas');
    await page.getByTestId('secure-link-actions-9').click();
    await page.getByTestId('secure-link-delete-9').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Sin enlaces en esta vista')).toHaveCount(1);
    expect(calls.create).toHaveLength(1);
    expect(calls.update[0]).toEqual({ title: 'Llaves Wompi editadas', client: null, project: null });
    expect(calls.delete).toBe(1);
  });

  // Bug caught: deleting the only result on the final page could retain a blank out-of-range page.
  test('clamps to the surviving page after deleting its final result', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let lastPage = true;
    const calls = await setupPanel(page, {
      list: () => json(lastPage
        ? {
          ...listPayload([secureLinkRow()]), count: 26, page: 2, page_size: 25,
          counts: { active: 26, consumed: 0, expired: 0, revoked: 0, all: 26 },
        }
        : {
          ...listPayload([secureLinkRow({ id: 8, title: 'Enlace de la página anterior' })]), count: 25, page: 1, page_size: 25,
          counts: { active: 25, consumed: 0, expired: 0, revoked: 0, all: 25 },
        }),
      remove: () => {
        lastPage = false;
        return { status: 204, body: '' };
      },
    });
    await page.goto('/es-co/panel/secure-links?page=2', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-delete-7').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByTestId('secure-link-row-8')).toContainText('Enlace de la página anterior');
    expect(calls.delete).toBe(1);
  });

});
