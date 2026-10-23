/**
 * E2E tests for standalone email attachments.
 *
 * @flow:admin-standalone-email-attachments
 * Covers: attaching a valid file from /panel/emails and sending it in the
 *         multipart POST, the client-side type-validation rejection, and
 *         the per-file remove button.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_STANDALONE_EMAIL_ATTACHMENTS } from '../helpers/flow-tags.js';
import { fillRichTextSource, richTextEditorByPlaceholder } from '../helpers/editorial.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const PDF_FILE = {
  name: 'informe.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 contenido de prueba'),
};

function baseRoutes(apiPath) {
  if (apiPath === 'auth/check/') return authCheck;
  if (apiPath === 'emails/defaults/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ greeting: '', footer: '', signer: '' }) };
  if (apiPath.startsWith('emails/history/')) return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], count: 0, num_pages: 1 }) };
  return null;
}

async function openComposer(page) {
  await page.goto('/panel/emails');
  await expect(page.getByPlaceholder('correo@ejemplo.com')).toBeVisible();
}

test.describe('Admin Standalone Email Attachments', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test('attaches a valid file and sends it in the multipart POST', {
    tag: [...ADMIN_STANDALONE_EMAIL_ATTACHMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let sendBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'emails/send/' && method === 'POST') {
        sendBody = route.request().postData() || '';
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'ok' }) };
      }
      return baseRoutes(apiPath);
    });
    await openComposer(page);

    await page.locator('input[type="file"]').setInputFiles(PDF_FILE);
    await expect(page.getByText('informe.pdf')).toBeVisible();

    await page.getByPlaceholder('correo@ejemplo.com').fill('cliente@acme.com');
    await page.getByPlaceholder('Asunto del correo').fill('Informe mensual');
    await fillRichTextSource(richTextEditorByPlaceholder(page, 'Escribe el contenido de esta sección...'), 'Adjunto el informe.');
    await page.getByRole('button', { name: /Enviar/i }).click();

    await expect.poll(() => sendBody).not.toBeNull();
    expect(sendBody).toContain('informe.pdf');
  });

  test('rejects a disallowed file type with a validation error', {
    tag: [...ADMIN_STANDALONE_EMAIL_ATTACHMENTS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath));
    await openComposer(page);

    await page.locator('input[type="file"]').setInputFiles({
      name: 'virus.exe',
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('MZ'),
    });

    await expect(page.getByText('virus.exe: tipo no permitido')).toBeVisible();
    await expect(page.getByText('virus.exe', { exact: true })).toBeHidden();
  });

  test('removes an attached file from the list', {
    tag: [...ADMIN_STANDALONE_EMAIL_ATTACHMENTS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath));
    await openComposer(page);

    await page.locator('input[type="file"]').setInputFiles(PDF_FILE);
    const fileRow = page.locator('div').filter({ hasText: /^informe\.pdf$/ });
    await expect(fileRow.first()).toBeVisible();

    await fileRow.first().getByRole('button').click();

    await expect(page.getByText('informe.pdf')).toBeHidden();
  });
});
