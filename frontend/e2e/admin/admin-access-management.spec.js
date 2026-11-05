/**
 * E2E coverage for authorized account administration.
 *
 * These tests catch regressions where administrators cannot find an account,
 * share a filtered URL, or actually revoke the account selected in the menu.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { viewportUse } from '../helpers/viewports.js';
import { ADMIN_ACCESS_MANAGEMENT } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const account = (enabled = true) => ({
  id: 71,
  name: 'Ana Acceso',
  email: 'ana@example.com',
  company: 'Acme',
  enabled,
  onboarded: true,
  email_verified: true,
  google_linked: false,
  last_login: '2026-11-01T14:00:00Z',
  last_method: 'code',
});
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

async function setupAccessApi(page, options = {}) {
  const calls = { lists: [], patches: [] };
  let enabled = options.enabled ?? true;
  let listFailuresRemaining = options.listFailures || 0;
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/' && method === 'GET') {
      return json({ user: { username: 'access-admin', is_staff: true, is_superuser: true } });
    }
    if (apiPath === 'accounts/access/' && method === 'GET') {
      calls.lists.push(Object.fromEntries(new URL(route.request().url()).searchParams));
      if (listFailuresRemaining > 0) {
        listFailuresRemaining -= 1;
        return json({ detail: 'No pudimos cargar los accesos.' }, 503);
      }
      const query = new URL(route.request().url()).searchParams;
      // The fixture deliberately returns the changed account after mutation so
      // the UI assertion proves the reloaded row uses the PATCH result. Query
      // forwarding itself is asserted from `calls.lists` below.
      const visible = true;
      return json({
        results: visible ? [account(enabled)] : [],
        count: visible ? 1 : 0,
        page: 1,
        pages: 1,
        counts: { all: 1, enabled: enabled ? 1 : 0, disabled: enabled ? 0 : 1, pending: 0 },
        can_manage_team: true,
      });
    }
    if (apiPath === 'accounts/access/71/' && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      calls.patches.push(payload);
      if (options.patchFailure) return json({ detail: 'No pudimos guardar el cambio.' }, 500);
      enabled = payload.enabled;
      return json(account(enabled));
    }
    if (apiPath === 'accounts/saved-filter-tabs/' && method === 'GET') return json([]);
    if (apiPath === 'proposals/' && method === 'GET') return json([]);
    if (apiPath === 'proposals/dashboard/' && method === 'GET') return json({ total: 0, by_status: {} });
    if (apiPath === 'proposals/alerts/' && method === 'GET') return json([]);
    return null;
  });
  return calls;
}

async function navigateToAccesses(page) {
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  const viewport = page.viewportSize();
  if (viewport.width < 1024) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
    await page.getByRole('dialog', { name: 'Menú principal' }).getByRole('link', { name: 'Accesos' }).click();
  } else {
    await page.getByRole('navigation', { name: 'Navegación del panel' }).getByRole('link', { name: 'Accesos' }).click();
  }
  await expect(page).toHaveURL(/\/panel\/access/);
  await expect(page.getByTestId('access-page').getByRole('heading', { name: 'Accesos' })).toHaveText('Accesos');
}

test.describe('Panel access management', () => {
  test('revokes the searched enabled account after confirmation', {
    tag: [...ADMIN_ACCESS_MANAGEMENT, '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    // Fails if search/filter URL state is lost, the dropdown stops filtering, or
    // confirmation sends the mutation to a different account than the row shown.
    const calls = await setupAccessApi(page);
    await navigateToAccesses(page);

    await page.getByTestId('access-search').fill('ana');
    await expect(page).toHaveURL(/search=ana/);
    await page.getByTestId('access-filter-enabled').click();
    await page.getByRole('checkbox', { name: 'Sí' }).check();
    await expect(page).toHaveURL(/enabled=true/);
    await expect.poll(() => calls.lists.some((query) => query.search === 'ana' && query.enabled === 'true')).toBe(true);

    const row = page.getByTestId('access-row-71');
    await row.getByTestId('access-actions-71').click();
    await page.getByRole('menuitem', { name: 'Deshabilitar acceso' }).click();
    await expect(page.getByRole('heading', { name: 'Deshabilitar acceso' })).toHaveText('Deshabilitar acceso');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect.poll(() => calls.patches).toEqual([{ enabled: false }]);
    await expect(row.getByText('Sin acceso', { exact: true })).toHaveText('Sin acceso');
  });

  test('shows a concrete retry state when the access list cannot load', {
    tag: [...ADMIN_ACCESS_MANAGEMENT, '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    // Fails if a list outage blanks the management view without a visible way
    // to retry and recover the account row.
    await setupAccessApi(page, { listFailures: 1 });
    await navigateToAccesses(page);

    await expect(page.getByRole('alert')).toHaveText('No pudimos cargar los accesos. Reintentar');
    await page.getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByTestId('access-row-71').getByText('ana@example.com')).toHaveText('ana@example.com');
  });

  test('keeps the selected account enabled when the server rejects a disable request', {
    tag: [...ADMIN_ACCESS_MANAGEMENT, '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    // Fails if a failed PATCH falsely renders a revoked account or hides the
    // failure that tells the administrator the access change did not happen.
    const calls = await setupAccessApi(page, { patchFailure: true });
    await navigateToAccesses(page);

    await page.getByTestId('access-actions-71').click();
    await page.getByRole('menuitem', { name: 'Deshabilitar acceso' }).click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect.poll(() => calls.patches).toEqual([{ enabled: false }]);
    await expect(page.getByRole('alert')).toHaveText('No pudimos guardar el cambio.');
    await expect(page.getByTestId('access-row-71').getByText('Habilitado', { exact: true })).toHaveText('Habilitado');
  });
});

for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  test.describe(`access list at ${profile}`, () => {
    test.use(viewportUse(profile));

    test(`opens the access list from panel navigation at ${profile}`, {
      tag: [...ADMIN_ACCESS_MANAGEMENT, '@outcome:display', '@role:admin', '@responsive:dashboard', `@viewport:${profile}`],
    }, async ({ page }) => {
      // quality: allow-duplicate (per-viewport contract: admin-access-management @ responsive width)
      // quality: allow-deep-link (the authenticated panel dashboard is fixture setup;
      // the display flow itself reaches Accesos by clicking its real navigation link)
      // Fails if this viewport hides the only navigation path or the real
      // account fixture is no longer readable after reaching the module.
      await setupAccessApi(page);
      await navigateToAccesses(page);

      await expect(page.getByTestId('access-row-71').getByText('ana@example.com')).toHaveText('ana@example.com');
    });
  });
}
