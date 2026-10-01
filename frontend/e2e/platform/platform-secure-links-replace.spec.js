/**
 * Platform client secure-link replacement.
 * Bug class covered: correction must revoke first, never restore old content,
 * and create exactly one linked successor only when the API accepts it.
 */
import { test, expect } from '../helpers/test.js';
import {
  createdPlatformSecureUrl, installPlatformSecureLinksMock, openPlatformSecureLinks,
} from '../helpers/platform-secure-links.js';
import { json } from '../helpers/secure-links.js';

test.setTimeout(60_000);

async function beginReplacement(page) {
  await page.getByTestId('platform-secure-manage-7').click();
  await page.getByTestId('platform-secure-replace').click();
  await page.getByTestId('platform-secure-confirm').click();
  await expect(page.getByTestId('platform-secure-form')).toBeVisible();
}

async function fillReplacement(page) {
  await expect(page.getByTestId('platform-secure-title')).toHaveValue('Acceso de despliegue');
  await expect(page.getByTestId('secure-link-field-password')).toHaveValue('');
  await page.getByTestId('secure-link-field-password').fill('new-fixture-password');
  await page.getByTestId('platform-secure-submit').click();
}

test('replacement revokes the source and creates a linked successor with a fresh secret field', {
  tag: ['@flow:platform-secure-link-replace', '@outcome:display', '@outcome:success'],
}, async ({ page }) => {
  // quality: allow-deep-link (the authenticated projects list is the platform entry; replacement begins only after visible project and client navigation clicks)
  const { calls, state } = await installPlatformSecureLinksMock(page);
  await openPlatformSecureLinks(page);
  await beginReplacement(page);
  await expect.poll(() => calls.revokes).toBe(1);
  await fillReplacement(page);
  await expect.poll(() => calls.creates.length).toBe(1);
  expect(calls.creates[0]).toEqual(expect.objectContaining({ replaces: 7, fields: { password: 'new-fixture-password' } }));
  await expect(page.getByTestId('platform-secure-url')).toHaveValue(createdPlatformSecureUrl);
  await expect.poll(() => state.links.length).toBe(2);
  expect(state.links.find((link) => link.id === 7)).toEqual(expect.objectContaining({ status: 'revoked', replaced_by: 8 }));
  expect(state.links.find((link) => link.id === 8)).toEqual(expect.objectContaining({ replaces: 7 }));
});

test('invalid replacement preserves the already revoked source and renders no successor URL', {
  tag: ['@flow:platform-secure-link-replace', '@outcome:error'],
}, async ({ page }) => {
  const { state } = await installPlatformSecureLinksMock(page, { create: () => json({ code: 'invalid_replacement' }, 409) });
  await openPlatformSecureLinks(page);
  await beginReplacement(page);
  await fillReplacement(page);
  await expect(page.getByTestId('platform-secure-form-error')).toHaveText(/Sólo admite una sustitución/);
  await expect(page.getByTestId('platform-secure-url')).toHaveCount(0);
  expect(state.links).toHaveLength(1);
  expect(state.links[0]).toEqual(expect.objectContaining({ status: 'revoked', replaced_by: null }));
});

test('replacement service failure leaves the revoked source intact and does not reveal prior content', {
  tag: ['@flow:platform-secure-link-replace', '@outcome:failure'],
}, async ({ page }) => {
  const { state } = await installPlatformSecureLinksMock(page, { create: () => json({ code: 'secure_links_unavailable' }, 503) });
  await openPlatformSecureLinks(page);
  await beginReplacement(page);
  await fillReplacement(page);
  await expect(page.getByTestId('platform-secure-form-error')).toHaveText(/cifrado no está disponible/);
  await expect(page.getByTestId('platform-secure-url')).toHaveCount(0);
  expect(state.links).toHaveLength(1);
  expect(state.links[0]).toEqual(expect.objectContaining({ status: 'revoked', replaced_by: null }));
});
