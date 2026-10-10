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
import { chooseRowAction, openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';
import {
  SECURE_LINK_TOKEN, chooseSecureLinkType, json, revealedContent, secureLinkRow, secureLinkTypes,
} from '../helpers/secure-links.js';

test.setTimeout(60_000);

const CREATED_URL = `http://localhost:3000/es-co/secure-link/view#${SECURE_LINK_TOKEN}`;
const ACTIONS_MODAL = 'secure-link-actions-modal';

function rowAction(page, id, action) {
  return chooseRowAction(page, {
    kebab: `secure-link-actions-${id}`, menu: ACTIONS_MODAL, action: `secure-link-${action}-${id}`,
  });
}

function historyFor(row) {
  return [{ id: 1, kind: 'created', kind_label: 'Creado', actor_name: 'Admin', ip_address: null, details: {}, created_at: row.created_at }];
}

function listPayload(rows) {
  const lifecycleCounts = rows.reduce((counts, row) => {
    counts[row.lifecycle_status || row.status] += 1;
    return counts;
  }, { ready: 0, sent: 0, opened: 0, expired: 0, revoked: 0 });
  return {
    results: rows,
    count: rows.length,
    page: 1,
    page_size: 25,
    counts: { active: rows.filter(row => row.status === 'active').length, consumed: rows.filter(row => row.status === 'consumed').length, expired: rows.filter(row => row.status === 'expired').length, revoked: rows.filter(row => row.status === 'revoked').length, all: rows.length },
    lifecycle_counts: { ...lifecycleCounts, all: rows.length },
    unopened_received: 0,
    public_create_url: 'http://localhost:3000/es-co/secure-link',
  };
}

async function setupPanel(page, {
  rows = [secureLinkRow()], create, types, detail, update, remove, list,
} = {}) {
  let store = [...rows];
  const calls = {
    create: [], content: 0, markSent: 0, revoke: 0, reactivate: [], update: [], delete: 0,
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
    const match = apiPath.match(/^secure-links\/(\d+)\/(content\/|mark-sent\/|revoke\/|reactivate\/)?$/);
    if (!match) return null;
    const id = Number(match[1]);
    const row = store.find((item) => item.id === id);
    if (!match[2] && method === 'GET') {
      if (detail) return typeof detail === 'function' ? detail({ route, row }) : detail;
      return json({ ...row, events: historyFor(row) });
    }
    if (!match[2] && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      calls.update.push(payload);
      if (update) return typeof update === 'function' ? update({ route, row, payload }) : update;
      Object.assign(row, payload);
      // The panel API answers an edit with the full detail, history included.
      return json({ ...row, events: [...historyFor(row), { id: 2, kind: 'updated', kind_label: 'Editado', actor_name: 'Admin', ip_address: null, details: {}, created_at: row.created_at }] });
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
    if (match[2] === 'mark-sent/') {
      calls.markSent += 1;
      Object.assign(row, { lifecycle_status: 'sent', sent_at: '2026-09-29T16:00:00Z' });
      return json(row);
    }
    if (match[2] === 'revoke/') {
      calls.revoke += 1;
      Object.assign(row, { status: 'revoked', lifecycle_status: 'revoked', revoked_at: '2026-09-26T16:00:00Z' });
      return json(row);
    }
    calls.reactivate.push(route.request().postDataJSON());
    Object.assign(row, { status: 'active', lifecycle_status: 'ready', consumed_at: null, sent_at: null, activation_count: 2 });
    return json({ ...row, url: CREATED_URL });
  });
  return calls;
}

test.describe('Admin secure links', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8901, role: 'admin', is_staff: true } });
  });

  // Bug caught: the new form could silently retain Credentials instead of its confidential-message default.
  test('creates a confidential message by default and shows the one-time URL with copy actions', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page, { rows: [] });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });

    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Llaves Wompi');
    await page.getByTestId('secure-link-field-message').fill('La clave se comparte por el canal acordado.');
    await page.getByTestId('secure-link-configuration').click();
    await page.getByTestId('secure-link-validity').getByRole('tab', { name: '3 días' }).click();
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-created-url')).toHaveText(CREATED_URL);
    await expect(page.getByTestId('secure-link-copy-message')).toBeVisible();
    expect(calls.create[0]).toMatchObject({
      secret_type: 'confidential_message', title: 'Llaves Wompi', fields: { message: 'La clave se comparte por el canal acordado.' },
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
    await chooseSecureLinkType(page, { name: 'Credenciales de acceso' });
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
    await expect(detail.getByTestId('secure-link-status-ready')).toHaveText('Listo para compartir');

    await detail.getByTestId('secure-link-revoke').click();
    await expect(detail.getByTestId('secure-link-status-revoked')).toBeVisible();
    expect(calls.content).toBe(1);
    expect(calls.revoke).toBe(1);
  });

  // Bug caught: lifecycle filters could omit an opened row or leave it marked as opened after reactivation.
  test('shows an opened link under Abierto and reactivates it as ready', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const calls = await setupPanel(page, {
      rows: [secureLinkRow({ status: 'consumed', lifecycle_status: 'opened', sent_at: '2026-09-26T15:00:00Z', consumed_at: '2026-09-26T15:30:00Z' })],
    });
    // quality: allow-deep-link (the panel home is the shell entry; its visible navigation opens the secure-links module)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click();

    await expect(page.getByTestId('secure-links-tabs')).toContainText('Abierto (1)');
    await page.getByTestId('secure-links-tabs').getByRole('tab', { name: 'Abierto (1)' }).click();
    await expect(page.getByTestId('secure-link-row-7')).toContainText('Admin Django producción');
    await page.getByTestId('secure-link-actions-7').filter({ visible: true }).click();
    await page.getByTestId('secure-link-reactivate-7').click();
    const reactivation = page.getByTestId('secure-link-reactivate');
    await reactivation.getByRole('tab', { name: '1 día' }).click();
    await reactivation.getByTestId('secure-link-reactivate-submit').click();

    await expect(page.getByTestId('secure-link-detail').getByTestId('secure-link-status-ready')).toHaveText('Listo para compartir');
    expect(calls.reactivate[0]).toEqual({ validity_days: 1, rotate: false });
  });
  // Bug caught: the floating type list could make Custom unreachable after replacing the native select.
  test('creates custom content without a client or project', {
    tag: [...ADMIN_SECURE_LINK_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const calls = await setupPanel(page, { rows: [] });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-links-new').click();
    await chooseSecureLinkType(page, { name: 'Personalizado' });
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

  // Bug caught: marking a manually shared link could skip the lifecycle endpoint and leave the badge ready.
  test('marks an active unsent link as sent from its row actions', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('secure-link-actions-7').click();
    await page.getByTestId('secure-link-mark-sent-7').click();

    await expect(page.getByTestId('secure-link-row-7').getByTestId('secure-link-status-sent')).toHaveText('Enviado');
    expect(calls.markSent).toBe(1);
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
    await chooseSecureLinkType(page, { name: 'Credenciales de acceso' });
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
    await chooseSecureLinkType(page, { name: 'Credenciales de acceso' });
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
    await chooseSecureLinkType(page, { name: 'Credenciales de acceso' });
    await page.getByTestId('secure-link-field-username').fill('previous-user');
    await page.getByTestId('secure-link-field-password').fill('previous-password');
    await page.getByTestId('secure-link-field-toggle-password').click();
    await page.getByRole('dialog').filter({ has: page.getByTestId('secure-link-form') }).getByRole('button', { name: 'Cancelar', exact: true }).click();
    await page.getByTestId('secure-links-new').click();
    await chooseSecureLinkType(page, { name: 'Credenciales de acceso' });

    await expect(page.getByTestId('secure-link-field-username')).toHaveValue('');
    await expect(page.getByTestId('secure-link-field-password')).toHaveValue('');
    await expect(page.getByTestId('secure-link-field-password')).toHaveAttribute('type', 'password');
    await expect(page.getByTestId('secure-link-field-password')).toHaveAttribute('autocomplete', 'new-password');
  });

  // Bug caught: renaming used to go through a second "Editar" form that sent the associations along.
  test('renames a link in place from its detail without revealing its content', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await rowAction(page, 7, 'open');

    const detail = page.getByTestId('secure-link-detail');
    await expect(detail.getByTestId('secure-link-edit-content')).toHaveCount(1);
    await expect(detail.getByTestId('secure-link-edit')).toHaveCount(0);
    await detail.getByTestId('secure-link-title-edit').click();
    await detail.getByTestId('secure-link-title-input').fill('Acceso Django actualizado');
    await detail.getByTestId('secure-link-title-save').click();

    await expect(detail.getByTestId('secure-link-title-editor').getByRole('heading')).toHaveText('Acceso Django actualizado');
    await expect(detail.getByTestId('secure-link-events')).toContainText('Editado');
    await expect(page.getByTestId('secure-link-row-7')).toContainText('Acceso Django actualizado');
    expect(calls.content).toBe(0);
    expect(calls.update[0]).toEqual({ title: 'Acceso Django actualizado' });
  });

  // Bug caught: Escape in the title field closed the whole detail and lost the open link.
  test('cancels an in-place rename with Escape and keeps the detail open', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await rowAction(page, 7, 'open');

    const detail = page.getByTestId('secure-link-detail');
    await detail.getByTestId('secure-link-title-edit').click();
    await detail.getByTestId('secure-link-title-input').fill('Borrador descartado');
    await detail.getByTestId('secure-link-title-input').press('Escape');

    await expect(detail.getByTestId('secure-link-title-input')).toHaveCount(0);
    await expect(detail.getByTestId('secure-link-title-editor').getByRole('heading')).toHaveText('Admin Django producción');
    await expect(detail).toBeVisible();
    expect(calls.update).toHaveLength(0);
  });

  // Bug caught: editing content could discard the fields retrieved explicitly from the detail.
  test('edits revealed content with the refreshed field values', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await rowAction(page, 7, 'open');
    await page.getByTestId('secure-link-edit-content').click();

    await expect(page.getByTestId('secure-link-field-password')).toHaveValue('S3cr3t-E2E!');
    await page.getByTestId('secure-link-field-password').fill('S3cr3t-Updated!');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-links-page')).toContainText('Admin Django producción');
    expect(calls.content).toBe(1);
    expect(calls.update[0]).toEqual({
      title: 'Admin Django producción', client: null, project: null,
      secret_type: 'credentials', fields: { service: 'Django admin', password: 'S3cr3t-Updated!' },
    });
  });

  // Bug caught: a rejected rename could clear the draft that the administrator needs to correct.
  test('keeps a rejected title draft next to the field', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupPanel(page, {
      update: json({ title: ['El título ya existe.'] }, 400),
    });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await rowAction(page, 7, 'open');
    const detail = page.getByTestId('secure-link-detail');
    await detail.getByTestId('secure-link-title-edit').click();
    await detail.getByTestId('secure-link-title-input').fill('Título duplicado');
    await detail.getByTestId('secure-link-title-save').click();

    await expect(detail.getByTestId('secure-link-title-error')).toHaveText('El título ya existe.');
    await expect(detail.getByTestId('secure-link-title-input')).toHaveValue('Título duplicado');
  });

  // Bug caught: cancelling the destructive dialog could still remove the secure link locally.
  test('cancels deletion without removing the secure link', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    // quality: allow-deep-link (the panel home is the shell entry; its visible navigation opens the secure-links module)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click();
    await rowAction(page, 7, 'delete');
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
    await chooseSecureLinkType(page, { name: 'Credenciales de acceso' });
    await page.getByTestId('secure-link-title').fill('Llaves Wompi');
    await page.getByTestId('secure-link-field-password').fill('created-secret');
    await page.getByTestId('secure-link-save').click();
    await page.getByTestId('secure-link-created-close').click();
    await rowAction(page, 9, 'open');
    const detail = page.getByTestId('secure-link-detail');
    await detail.getByTestId('secure-link-title-edit').click();
    await detail.getByTestId('secure-link-title-input').fill('Llaves Wompi editadas');
    await detail.getByTestId('secure-link-title-save').click();
    await expect(detail.getByTestId('secure-link-title-input')).toHaveCount(0);
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('secure-link-row-9')).toContainText('Llaves Wompi editadas');
    await rowAction(page, 9, 'delete');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Sin enlaces en esta vista')).toHaveCount(1);
    expect(calls.create).toHaveLength(1);
    expect(calls.update[0]).toEqual({ title: 'Llaves Wompi editadas' });
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
          counts: { active: 26, consumed: 0, expired: 0, revoked: 0, all: 26 }, lifecycle_counts: { ready: 26, sent: 0, opened: 0, expired: 0, revoked: 0, all: 26 },
        }
        : {
          ...listPayload([secureLinkRow({ id: 8, title: 'Enlace de la página anterior' })]), count: 25, page: 1, page_size: 25,
          counts: { active: 25, consumed: 0, expired: 0, revoked: 0, all: 25 }, lifecycle_counts: { ready: 25, sent: 0, opened: 0, expired: 0, revoked: 0, all: 25 },
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

  // Bug caught: the actions lived in a trailing "Acciones" dropdown, clipped on the last rows.
  test('leads each row with an unlabeled actions menu that opens in a modal', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupPanel(page);
    // quality: allow-deep-link (the panel home is the shell entry; its visible navigation opens the secure-links module)
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click();

    const actionsHeader = page.getByTestId('secure-link-row-actions-header');
    await expect(actionsHeader).toBeVisible({ timeout: 15000 });
    const leadingHeaders = await actionsHeader.evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 2).map((cell) => ({
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { label: 'Acciones', text: '' },
      { label: null, text: 'Enlace' },
    ]);
    await expectNoBlankBand(page.getByRole('table'));

    await openRowMenu(page, { kebab: 'secure-link-actions-7', menu: ACTIONS_MODAL });
    await expect(page.getByTestId(ACTIONS_MODAL).getByRole('button')).toHaveText([
      'Detalle e historial', 'Editar contenido', 'Copiar enlace', 'Marcar como enviado', 'Revocar', 'Eliminar',
    ]);
    await expect(page.getByTestId('secure-link-detail')).toHaveCount(0);
    await expect(page).not.toHaveURL(/link=/);
  });

  // Bug caught: changing a secret took a detour through the detail and its second edit button.
  test('edits content straight from the row actions', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await setupPanel(page);
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await rowAction(page, 7, 'edit-content');

    await expect(page.getByTestId('secure-link-field-password')).toHaveValue('S3cr3t-E2E!');
    await page.getByTestId('secure-link-field-password').fill('S3cr3t-Row!');
    await page.getByTestId('secure-link-save').click();

    await expect.poll(() => calls.update.length).toBe(1);
    await expect(page.getByTestId('secure-link-form')).toBeHidden();
    expect(calls.content).toBe(1);
    expect(calls.update[0]).toEqual({
      title: 'Admin Django producción', client: null, project: null,
      secret_type: 'credentials', fields: { service: 'Django admin', password: 'S3cr3t-Row!' },
    });
  });

  // Bug caught: links created elsewhere only appeared after reloading the whole page.
  test('reloads the table from the bottom refresh button', {
    tag: [...ADMIN_SECURE_LINK_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const rows = [secureLinkRow()];
    await setupPanel(page, { list: () => json(listPayload(rows)) });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('secure-link-row-7')).toBeVisible();
    await expect(page.getByTestId('secure-link-row-12')).toHaveCount(0);

    rows.unshift(secureLinkRow({ id: 12, title: 'Llaves del CDN' }));
    await page.getByRole('button', { name: 'Actualizar datos' }).click();

    await expect(page.getByTestId('secure-link-row-12')).toContainText('Llaves del CDN');
    await expect(page.getByTestId('secure-links-tabs')).toContainText('Todos (2)');
  });

});
