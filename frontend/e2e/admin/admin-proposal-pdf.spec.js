/** Staff downloads original expired proposals independently of formal annexes. */
import { readFile } from 'node:fs/promises';
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';

test.describe.configure({ timeout: 60_000 });
const proposal = {
  id: 2, uuid: '33333333-3333-3333-3333-333333333333', title: 'Expired PDF proposal',
  client_name: 'Client', status: 'expired', expires_at: '2026-09-25T00:00:00Z', language: 'es',
  total_investment: '100000', currency: 'COP', is_active: true, sections: [], requirement_groups: [],
};

for (const [label, query, filename] of [
  ['Propuesta comercial', '', 'Propuesta_Comercial.pdf'],
  ['Detalle técnico', '?doc=technical', 'Detalle_Tecnico.pdf'],
]) {
  test(`downloads expired ${label} from General`, {
    tag: ['@flow:admin-proposal-download-pdf', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-admin-token', userAuth: { id: 8300, role: 'admin', is_staff: true } });
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      if (apiPath === 'proposals/2/detail/') return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
      if (apiPath.startsWith('proposals/2/pdf/')) return { status: 200, contentType: 'application/pdf', body: '%PDF-staff', headers: { 'content-disposition': `attachment; filename="${filename}"` } };
      return null;
    });
    await page.goto('/en-us/panel/proposals/2/edit', { waitUntil: 'domcontentloaded' });
    const link = page.getByRole('link', { name: label, exact: true });
    await expect(link).toHaveAttribute('href', `/api/proposals/2/pdf/${query}`);

    const filePromise = page.waitForEvent('download');
    await link.click();
    const file = await filePromise;

    expect(file.suggestedFilename()).toBe(filename);
    expect(await readFile(await file.path(), 'utf8')).toBe('%PDF-staff');
  });
}
