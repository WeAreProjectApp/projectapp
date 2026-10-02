/**
 * Platform client secure links.
 * Bug class covered: client UI must not mutate owner/audience/origin, duplicate
 * a request after a transient failure, or present a URL/state the API did not emit.
 */
import { test, expect } from '../helpers/test.js';
import {
  createdPlatformSecureUrl, installPlatformSecureLinksMock, openPlatformSecureLinks, platformSecureLink,
} from '../helpers/platform-secure-links.js';
import { json } from '../helpers/secure-links.js';

test.setTimeout(60_000);

async function openCreateForm(page) {
  await page.getByTestId('platform-secure-new').click();
  await expect(page.getByTestId('secure-link-type')).toHaveText('Credenciales de acceso');
  await expect(page.getByTestId('platform-secure-title')).toHaveValue('');
  await expect(page.getByTestId('secure-link-field-password')).toHaveValue('');
  await page.getByTestId('platform-secure-title').fill('Credenciales de staging');
  await page.getByTestId('secure-link-field-password').fill('fixture-password-only');
}

test('client creates a credentials link without mutable ownership and clears its URL when closing', {
  tag: ['@flow:platform-secure-link-create', '@outcome:display', '@outcome:success'],
}, async ({ page, context }) => {
  // quality: allow-deep-link (the authenticated projects list is the platform entry; the test clicks its project row and the client-only secure-links navigation)
  const { calls } = await installPlatformSecureLinksMock(page, { links: [] });
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await openPlatformSecureLinks(page);
  await openCreateForm(page);

  await page.getByTestId('platform-secure-submit').click();
  await expect.poll(() => calls.creates.length).toBe(1);
  expect(calls.creates[0]).toEqual(expect.objectContaining({
    request_id: expect.stringMatching(/^[0-9a-f-]{36}$/), title: 'Credenciales de staging', secret_type: 'credentials',
    fields: { password: 'fixture-password-only' }, validity_days: 7, language: 'es', replaces: null,
  }));
  expect(calls.creates[0]).not.toHaveProperty('owner');
  expect(calls.creates[0]).not.toHaveProperty('audience');
  expect(calls.creates[0]).not.toHaveProperty('origin');
  await expect(page.getByTestId('platform-secure-url')).toHaveValue(createdPlatformSecureUrl);
  await page.getByTestId('platform-secure-copy').click();
  await expect(page.getByTestId('platform-secure-copy')).toHaveText('Enlace copiado');
  await page.getByTestId('platform-secure-close').click();
  await expect(page.getByTestId('platform-secure-url')).toHaveCount(0);
});

test('idempotency conflict retains the request identifier until the client explicitly starts another creation', {
  tag: ['@flow:platform-secure-link-create', '@outcome:error'],
}, async ({ page }) => {
  const { calls } = await installPlatformSecureLinksMock(page, { links: [], create: () => json({ code: 'request_id_conflict' }, 409) });
  await openPlatformSecureLinks(page);
  await openCreateForm(page);
  await page.getByTestId('platform-secure-submit').click();
  await expect(page.getByTestId('platform-secure-form-error')).toHaveText(/ya se usó con otros datos/);
  await page.getByTestId('platform-secure-submit').click();
  await expect.poll(() => calls.creates.length).toBe(2);
  expect(calls.creates[1].request_id).toBe(calls.creates[0].request_id);
  await expect(page.getByTestId('platform-secure-title')).toHaveValue('Credenciales de staging');
  await page.getByRole('button', { name: 'Iniciar una creación con estos nuevos datos' }).click();
  await page.getByTestId('platform-secure-submit').click();
  await expect.poll(() => calls.creates.length).toBe(3);
  expect(calls.creates[2].request_id).not.toBe(calls.creates[0].request_id);
});

test('temporary create failure preserves the UUID and never renders an unissued URL', {
  tag: ['@flow:platform-secure-link-create', '@outcome:failure'],
}, async ({ page }) => {
  const { calls } = await installPlatformSecureLinksMock(page, { links: [], create: () => json({ code: 'secure_links_unavailable' }, 503) });
  await openPlatformSecureLinks(page);
  await openCreateForm(page);
  await page.getByTestId('platform-secure-submit').click();
  await expect(page.getByTestId('platform-secure-form-error')).toHaveText(/cifrado no está disponible/);
  await page.getByTestId('platform-secure-submit').click();
  await expect.poll(() => calls.creates.length).toBe(2);
  expect(calls.creates[1].request_id).toBe(calls.creates[0].request_id);
  await expect(page.getByTestId('platform-secure-title')).toHaveValue('Credenciales de staging');
  await expect(page.getByTestId('platform-secure-url')).toHaveCount(0);
});

test('client manages safe metadata and history without controls for external recipients or secret content', {
  tag: ['@flow:platform-secure-link-manage', '@outcome:display'],
}, async ({ page }) => {
  // quality: allow-deep-link (the authenticated projects list is the platform entry; the test reaches metadata through the project row and client-only navigation)
  await installPlatformSecureLinksMock(page);
  await openPlatformSecureLinks(page);
  const row = page.getByTestId('platform-secure-row-7');
  await expect(row).toContainText('Acceso de despliegue');
  await page.getByTestId('platform-secure-manage-7').click();
  const detail = page.getByRole('dialog').filter({ has: page.getByTestId('platform-secure-detail-status') });
  await expect(page.getByTestId('platform-secure-history')).toContainText('Creado');
  await expect(detail.getByText(/sólo con el equipo de ProjectApp/)).toHaveCount(1);
  await expect(page.getByTestId('platform-secure-workspace').getByText(/archivos ni importaciones de accesos internos/)).toHaveCount(1);
  await expect(page.getByRole('button', { name: /leer contenido|eliminar|marcar como enviado|destinatario externo/i })).toHaveCount(0);
});

test('URL lookup is immediate while revoke and rotated reactivation wait for confirmation', {
  tag: ['@flow:platform-secure-link-manage', '@outcome:success'],
}, async ({ page }) => {
  const { calls } = await installPlatformSecureLinksMock(page);
  await openPlatformSecureLinks(page);
  await page.getByTestId('platform-secure-manage-7').click();
  await page.getByTestId('platform-secure-request-url').click();
  await expect.poll(() => calls.urls).toBe(1);
  await expect(page.getByTestId('platform-secure-url')).toHaveValue(createdPlatformSecureUrl);
  const revoke = page.getByTestId('platform-secure-revoke');
  await expect(revoke).toBeEnabled();
  await revoke.click();
  expect(calls.revokes).toBe(0);
  await page.getByTestId('platform-secure-confirm').click();
  await expect.poll(() => calls.revokes).toBe(1);
  await page.getByTestId('platform-secure-close').click();
  await page.getByTestId('platform-secure-manage-7').click();
  const reactivate = page.getByTestId('platform-secure-reactivate');
  await expect(reactivate).toBeEnabled();
  await reactivate.click();
  expect(calls.reactivations).toEqual([]);
  await page.getByTestId('platform-secure-confirm').click();
  await expect.poll(() => calls.reactivations.length).toBe(1);
  expect(calls.reactivations[0]).toEqual({ validity_days: 7, expected_updated_at: '2026-10-02T15:00:00Z' });
  await expect(page.getByTestId('platform-secure-url')).toHaveValue(createdPlatformSecureUrl);
});

test('history failure is visible and closing then managing again requests safe history anew', {
  tag: ['@flow:platform-secure-link-manage', '@outcome:failure'],
}, async ({ page }) => {
  const { calls } = await installPlatformSecureLinksMock(page, { events: () => json({ code: 'secure_links_unavailable' }, 503) });
  await openPlatformSecureLinks(page);
  await page.getByTestId('platform-secure-manage-7').click();
  await expect(page.getByTestId('platform-secure-detail-error')).toHaveText(/cifrado no está disponible/);
  await expect(page.getByTestId('platform-secure-url')).toHaveCount(0);
  await page.getByTestId('platform-secure-close').click();
  await page.getByTestId('platform-secure-manage-7').click();
  await expect.poll(() => calls.events).toBe(2);
});

test('version-conflicted reactivation retains the observed consumed state without a URL', {
  tag: ['@flow:platform-secure-link-manage', '@outcome:error'],
}, async ({ page }) => {
  const consumed = platformSecureLink({ status: 'consumed', consumed_at: '2026-10-02T13:00:00Z', capabilities: { copy_url: false, revoke: true, reactivate: true } });
  const { calls } = await installPlatformSecureLinksMock(page, { links: [consumed], reactivate: () => json({ code: 'version_conflict' }, 409) });
  await openPlatformSecureLinks(page);
  await page.getByTestId('platform-secure-manage-7').click();
  await expect(page.getByTestId('platform-secure-detail-status')).toHaveText('Abierto');
  await page.getByTestId('platform-secure-reactivate').click();
  await page.getByTestId('platform-secure-confirm').click();
  await expect(page.getByTestId('platform-secure-detail-error')).toHaveText(/enlace cambió/);
  expect(calls.reactivations[0].expected_updated_at).toBe('2026-10-01T15:00:00Z');
  await expect(page.getByTestId('platform-secure-detail-status')).toHaveText('Abierto');
  await expect(page.getByTestId('platform-secure-url')).toHaveCount(0);
});
