// qa: draft-unvalidated (2026-11-06 — app not running)
/**
 * PA-201/202/208/214 regression coverage.
 * Each assertion is tied to the observable layout or email outcome an admin sees.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import {
  ADMIN_OUTBOUND_EMAIL_HISTORY_FILTER,
  ADMIN_OUTBOUND_EMAIL_HISTORY_RETRY,
  ADMIN_PANEL_SIDEBAR_RESIZE,
  ADMIN_SECURE_LINK_FOLDER_PANEL_RESIZE,
} from '../helpers/flow-tags.js';
import { secureLinkRow, secureLinkTypes, json } from '../helpers/secure-links.js';

test.setTimeout(60_000);

const admin = { id: 9001, role: 'admin', is_staff: true, is_superuser: true };
const folder = {
  id: 71, name: 'Proyecto con credenciales extensas', parent: null, order: 0,
  client: null, project: null, managed_project: null, folder_kind: 'manual',
  is_archived: false, is_read_only: false, link_count: 1, archived_link_count: 0,
};
const secureRow = secureLinkRow({ id: 72, folder: folder.id });
const failedRecipient = {
  id: 44, email: 'cobros@acme.test', status: 'failed', is_retryable: true,
  retry_blocked_reason: '',
};
const blockedRecipient = {
  id: 45, email: 'historico@acme.test', status: 'failed', is_retryable: false,
  retry_blocked_reason: 'No hay datos históricos suficientes para reconstruir esta confirmación.',
};

function historyRow(overrides = {}) {
  return {
    id: 10, subject: 'Confirmación de pago ACME', recipient: failedRecipient.email,
    status: 'failed', sent_at: '2026-11-05T10:00:00Z', family_label: 'Contabilidad',
    template_label: 'Confirmación de pago', audience_label: 'Cliente', has_body: true,
    can_resend: false, to_recipients: [failedRecipient], cc_recipients: [],
    metadata: { greeting: 'Hola ACME', sections: ['Confirmamos el pago.'] },
    error_message: 'SMTP temporalmente no disponible.',
    ...overrides,
  };
}

async function setAdmin(page) {
  await setAuthLocalStorage(page, { token: 'panel-usability-token', userAuth: admin });
}

async function mockSecureLinks(page) {
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/') return json({ finance: null, proposals: { total_proposals: 0, by_status: {} }, operations: {}, attention: [] });
    if (apiPath === 'secure-links/public/types/') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/folders/' && method === 'GET') {
      return json({
        folders: [folder],
        navigation: { totals: { active: { folders: 1, documents: 1 }, archived: { folders: 0, documents: 0 } }, unassigned: {}, projects: [], clients: [] },
      });
    }
    if (apiPath === 'secure-links/' && method === 'GET') {
      return json({ results: [secureRow], count: 1, page: 1, page_size: 25, counts: { active: 1, all: 1 }, lifecycle_counts: { ready: 1, all: 1 }, unopened_received: 0 });
    }
    return null;
  });
}

async function mockEmails(page, { retryStatus = 201 } = {}) {
  let retried = false;
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/') return json({ finance: null, proposals: { total_proposals: 0, by_status: {} }, operations: {}, attention: [] });
    if (apiPath === 'emails/defaults/' && method === 'GET') return json({ greeting: 'Hola', footer: 'Equipo Project App', config: {}, defaults: {}, available_signers: [] });
    if (apiPath === 'emails/copy-recipients/' && method === 'GET') return json({ results: [], families: [], copy_mode: 'bcc' });
    if (apiPath === 'email-deliverability/' && method === 'GET') {
      return json({ total_emails_30d: 42, success_rate: 95, sent_count: 40, failed_count: 2, by_template: [{ template_key: 'payment_confirmation', total: 42, sent: 40, failed: 2, success_rate: 95 }], daily_trend: [{ date: '2026-11-05', total: 42, sent: 40, failed: 2 }], recent_failures: [{ template_key: 'payment_confirmation', recipient: failedRecipient.email, status: 'failed', sent_at: '2026-11-05T10:00:00Z', error_message: 'SMTP temporalmente no disponible.' }] });
    }
    if (apiPath === 'emails/history/' && method === 'GET') {
      const rows = [historyRow(), historyRow({ id: 11, subject: 'Confirmación histórica', recipient: blockedRecipient.email, to_recipients: [blockedRecipient] })];
      const attemptStatus = retryStatus === 201 ? 'sent' : 'failed';
      if (retried) rows.unshift(historyRow({ id: 99, status: attemptStatus, recipient: failedRecipient.email, to_recipients: [{ ...failedRecipient, id: 99, status: attemptStatus, is_retryable: attemptStatus === 'failed' }], retry_of: failedRecipient.id, error_message: attemptStatus === 'failed' ? 'SMTP temporalmente no disponible.' : '' }));
      return json({ results: rows, total: rows.length, page: 1, has_next: false, attachment_type_options: [] });
    }
    if (apiPath === `emails/history/${failedRecipient.id}/retry/` && method === 'POST') {
      expect(route.request().postDataJSON()).toEqual({});
      retried = true;
      if (retryStatus !== 201) return json({ id: 99, detail: 'SMTP temporalmente no disponible.' }, retryStatus);
      return json({ id: 99, retry_of: failedRecipient.id, status: 'sent' }, 201);
    }
    return null;
  });
}

async function openPanelArea(page, label) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await page.getByRole('link', { name: label, exact: true }).click();
}

async function dragHandle(page, handle, deltaX) {
  const box = await handle.boundingBox();
  const x = box.x + (box.width / 2);
  const y = box.y + (box.height / 2);
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + deltaX, y, { steps: 5 });
  await page.mouse.up();
}

test.describe('panel usability and outbound email retry', () => {
  // Bug caught: a drag changed only the sidebar while the main content stayed put.
  test('preserves the resized Panel menu width through collapse', {
    tag: [...ADMIN_PANEL_SIDEBAR_RESIZE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await setAdmin(page);
    await mockApi(page, async ({ apiPath }) => apiPath === 'auth/check/' ? json({ user: { username: 'admin', is_staff: true } }) : null);
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
    const sidebar = page.getByTestId('panel-sidebar');
    const handle = page.getByTestId('panel-sidebar-resize-handle');
    const main = page.getByRole('main');
    const [initialSidebar, initialMain] = await Promise.all([sidebar.boundingBox(), main.boundingBox()]);
    await dragHandle(page, handle, 140);
    const [wideSidebar, wideMain] = await Promise.all([sidebar.boundingBox(), main.boundingBox()]);
    expect(wideSidebar.width).toBeGreaterThan(initialSidebar.width + 130);
    expect(wideMain.x).toBeGreaterThan(initialMain.x + 130);
    await dragHandle(page, handle, -80);
    await expect(sidebar).toHaveCSS('width', '300px');
    expect((await main.boundingBox()).x).toBe(300);
    await page.getByRole('button', { name: 'Contraer barra lateral', exact: true }).click();
    await expect(sidebar).toHaveCSS('width', '64px');
    await page.getByRole('button', { name: 'Expandir barra lateral', exact: true }).click();
    await expect(sidebar).toHaveCSS('width', '300px');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(sidebar).toHaveCSS('width', '300px');
  });

  // Bug caught: at the minimum desktop width, package labels were clipped and
  // the consulting destination remained in the wrong navigation section.
  test('opens consulting from the Programs navigation section', {
    tag: [...ADMIN_PANEL_SIDEBAR_RESIZE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await setAdmin(page);
    await mockApi(page, async ({ apiPath }) => apiPath === 'auth/check/' ? json({ user: { username: 'admin', is_staff: true } }) : null);
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
    const handle = page.getByTestId('panel-sidebar-resize-handle');
    await handle.focus();
    await page.keyboard.press('Home');
    const packages = page.getByRole('link', { name: 'Paquetes de requerimientos', exact: true });
    await expect(packages).toHaveText('Paquetes de requerimientos');
    const label = packages.getByText('Paquetes de requerimientos', { exact: true });
    const metrics = await label.evaluate(node => ({ width: node.clientWidth, scroll: node.scrollWidth, height: node.getBoundingClientRect().height, line: parseFloat(getComputedStyle(node).lineHeight) }));
    expect(metrics.scroll).toBeLessThanOrEqual(metrics.width);
    expect(metrics.height).toBeGreaterThan(metrics.line);
    await page.getByRole('link', { name: 'Consultoría y asesoría', exact: true }).click();
    await expect(page).toHaveURL(/\/panel\/consulting$/);
    await expect(page.getByRole('heading', { name: 'Consultoría y asesoría', exact: true })).toHaveText('Consultoría y asesoría');
  });

  // Bug caught: secure-link navigation remained fixed or persisted with Documents' width.
  test('persists a mouse-resized secure-links folder panel width', {
    tag: [...ADMIN_SECURE_LINK_FOLDER_PANEL_RESIZE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await setAdmin(page);
    await mockSecureLinks(page);
    await openPanelArea(page, 'Enlaces seguros');
    const sidebar = page.getByTestId('secure-folders-sidebar');
    const content = page.getByRole('region', { name: 'Contenido de enlaces seguros' });
    const handle = page.getByTestId('secure-folders-resize-handle');
    const [initialSidebar, initialContent] = await Promise.all([sidebar.boundingBox(), content.boundingBox()]);
    expect(Math.abs(initialSidebar.width - 256)).toBeLessThanOrEqual(2);
    await dragHandle(page, handle, 120);
    const [wideSidebar, wideContent] = await Promise.all([sidebar.boundingBox(), content.boundingBox()]);
    expect(wideSidebar.width).toBeGreaterThan(initialSidebar.width + 110);
    expect(wideContent.x).toBeGreaterThan(initialContent.x + 110);
    await dragHandle(page, handle, -280);
    expect((await sidebar.boundingBox()).width).toBeLessThanOrEqual(242);
    expect(await page.evaluate(() => localStorage.getItem('projectapp-secure-links-folder-width'))).toBe('240');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('secure-folders-sidebar')).toBeVisible();
    expect((await page.getByTestId('secure-folders-sidebar').boundingBox()).width).toBeLessThanOrEqual(242);
  });

  // Bug caught: compact secure links rendered neither the drawer nor its folders.
  test('uses the secure-links folder drawer below the desktop panel breakpoint', {
    tag: [...ADMIN_SECURE_LINK_FOLDER_PANEL_RESIZE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 835, height: 900 });
    await setAdmin(page);
    await mockSecureLinks(page);
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
    await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
    await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click();
    await page.getByTestId('secure-folders-open').click();
    await expect(page.getByRole('dialog', { name: 'Carpetas de enlaces seguros' })).toContainText(folder.name);
    await expect(page.getByTestId('secure-folders-resize-handle')).toBeHidden();
  });

  // Bug caught: delivery status was unavailable from the Communications email entry.
  test('shows the failed recipient in email status through Communications', {
    tag: ['@flow:admin-email-deliverability', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setAdmin(page);
    await mockEmails(page);
    await openPanelArea(page, 'Emails');
    await page.getByRole('tab', { name: 'Estado de los emails', exact: true }).click();
    await expect(page).toHaveURL(/tab=status/);
    await expect(page.getByText('42', { exact: true }).first()).toHaveText('42');
    await expect(page.getByText(failedRecipient.email, { exact: true })).toHaveText(failedRecipient.email);
  });

  // Bug caught: the confirmation prompt could retry a different address or
  // leave the successful attempt absent from the expanded email history.
  test('refreshes the retried recipient attempt', {
    tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_RETRY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setAdmin(page);
    await mockEmails(page);
    await openPanelArea(page, 'Emails');
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();
    await page.getByTestId('email-history-record-10').getByRole('button').click();
    await page.getByTestId(`email-history-retry-${failedRecipient.id}`).click();
    await expect(page.getByRole('dialog')).toContainText(failedRecipient.email);
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByTestId('email-history-record-99')).toContainText('Enviado');
    await expect(page.getByTestId('email-history-record-99')).toContainText(failedRecipient.email);
  });

  // Bug caught: historical failures hid why the original recipient could not be retried.
  test('explains why an unreconstructable historical recipient cannot be retried', {
    tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_RETRY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setAdmin(page);
    await mockEmails(page);
    await openPanelArea(page, 'Emails');
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();
    await page.getByTestId('email-history-record-11').getByRole('button').click();
    await expect(page.getByTestId(`email-history-retry-blocked-${blockedRecipient.id}`)).toHaveText(blockedRecipient.retry_blocked_reason);
  });

  // Bug caught: a second SMTP failure disappeared after the confirmation dialog closed.
  test('keeps a failed retry visible to the operator', {
    tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_RETRY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setAdmin(page);
    await mockEmails(page, { retryStatus: 503 });
    await openPanelArea(page, 'Emails');
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();
    await page.getByTestId('email-history-record-10').getByRole('button').click();
    await page.getByTestId(`email-history-retry-${failedRecipient.id}`).click();
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByRole('alert').filter({ hasText: 'El reintento no salió' })).toContainText('SMTP temporalmente no disponible.');
    await expect(page.getByTestId('email-history-record-99')).toContainText('Fallido');
  });

  test('shows a rejected retry after its origin becomes unavailable', {
    tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_RETRY, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setAdmin(page);
    await mockEmails(page, { retryStatus: 409 });
    await openPanelArea(page, 'Emails');
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();
    await page.getByTestId('email-history-record-10').getByRole('button').click();
    await page.getByTestId(`email-history-retry-${failedRecipient.id}`).click();
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByRole('alert').filter({ hasText: 'El reintento no salió' })).toBeVisible();
  });

  // Bug caught: applying filters left cramped inputs unreadable or could not clear dates.
  test('clears applied readable history filters', {
    tag: [...ADMIN_OUTBOUND_EMAIL_HISTORY_FILTER, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 1195, height: 900 });
    await setAdmin(page);
    await mockEmails(page);
    await openPanelArea(page, 'Emails');
    await page.getByRole('tab', { name: 'Historial', exact: true }).click();
    const filters = page.getByTestId('email-history-filters');
    await page.getByLabel('Buscar destinatario').fill(failedRecipient.email);
    await page.getByLabel('Fecha inicial').fill('2026-11-01');
    await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click();
    await expect(page.getByLabel('Buscar destinatario')).toHaveValue(failedRecipient.email);
    await expect(page.getByLabel('Fecha inicial')).toHaveValue('2026-11-01');
    expect((await filters.boundingBox()).width).toBeGreaterThan(700);
    await page.getByRole('button', { name: 'Limpiar', exact: true }).click();
    await expect(page.getByLabel('Buscar destinatario')).toHaveValue('');
    await expect(page.getByLabel('Fecha inicial')).toHaveValue('');
  });
});
