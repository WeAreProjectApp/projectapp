/**
 * E2E tests for the LinkedIn content module at /panel/linkedin.
 *
 * Covers flow: admin-linkedin-module
 *   - Disconnected state shows "Conectar LinkedIn" button.
 *   - Connected state shows profile name and token expiry date.
 *   - Posts list renders rows with status chips.
 *   - Each row leads with an actions button that opens its menu in place.
 *   - Create modal saves a draft and the list refreshes.
 *   - Publish now (with confirm) flips the row to published.
 *   - Publish API failure surfaces an inline error message.
 *
 * All API endpoints are mocked — no real LinkedIn calls.
 */

import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_LINKEDIN_MODULE } from '../helpers/flow-tags.js';
import { chooseRowAction, openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

test.setTimeout(60_000);

// ─────────────────────────────────────────────
// Fixtures
// ─────────────────────────────────────────────

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const disconnectedStatus = { connected: false };

const connectedStatus = {
  connected: true,
  profile_name: 'Gustavo Pérez',
  profile_email: 'gustavo@example.com',
  expires_at: '2026-09-01T00:00:00Z',
};

const draftPost = {
  id: 1,
  commentary: 'Borrador de prueba para LinkedIn',
  image: null,
  status: 'draft',
  scheduled_at: null,
  published_at: null,
  linkedin_post_id: '',
  error_message: '',
  created_at: '2026-07-04T10:00:00Z',
  updated_at: '2026-07-04T10:00:00Z',
};

const publishedPost = {
  ...draftPost,
  status: 'published',
  published_at: '2026-07-04T12:00:00Z',
  linkedin_post_id: 'urn:li:share:123',
};

function setupPageMock(page, {
  linkedinStatus = connectedStatus,
  posts = [draftPost],
  publishResponse = null,
} = {}) {
  // Mutable list so create/publish can update what the list returns
  const state = { posts: [...posts] };

  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'linkedin/status/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(linkedinStatus) };
    }
    if (apiPath === 'linkedin/posts/' && route.request().method() === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(state.posts) };
    }
    if (apiPath === 'linkedin/posts/create/' && route.request().method() === 'POST') {
      const created = { ...draftPost, id: 99, commentary: 'Nuevo post desde E2E' };
      state.posts = [created, ...state.posts];
      return { status: 201, contentType: 'application/json', body: JSON.stringify(created) };
    }
    if (apiPath === 'linkedin/posts/1/publish/' && route.request().method() === 'POST') {
      if (publishResponse) return publishResponse;
      state.posts = [publishedPost];
      return { status: 200, contentType: 'application/json', body: JSON.stringify(publishedPost) };
    }
    return null;
  });
}

async function gotoModule(page) {
  await page.goto('/panel/linkedin');
  await page.waitForLoadState('domcontentloaded');
  await page.getByRole('heading', { name: 'LinkedIn' }).waitFor({ state: 'visible' });
}

// ─────────────────────────────────────────────
// Flow: admin-linkedin-module
// ─────────────────────────────────────────────

test.describe('Admin LinkedIn module', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8900, role: 'admin', is_staff: true } });
  });

  test('shows disconnected state with connect button', {
    tag: [...ADMIN_LINKEDIN_MODULE, '@role:admin', '@outcome:display', '@responsive:content'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (renders the disconnected state from a mocked GET; no action toggles it)
    await setupPageMock(page, { linkedinStatus: disconnectedStatus, posts: [] });
    await gotoModule(page);

    await expect(page.getByText('LinkedIn no conectado.')).toBeVisible();
    await expect(page.getByRole('button', { name: /Conectar LinkedIn/ })).toBeVisible();
  });

  test('shows connected profile with token expiry date', {
    tag: [...ADMIN_LINKEDIN_MODULE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (renders the connected profile from a mocked GET; no action changes it)
    await setupPageMock(page);
    await gotoModule(page);

    await expect(page.getByText('Gustavo Pérez')).toBeVisible();
    await expect(page.getByText(/La conexión expira el/)).toBeVisible();
  });

  test('renders posts list with status chip', {
    tag: [...ADMIN_LINKEDIN_MODULE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (renders the seeded posts list from a mocked GET; no action changes it)
    await setupPageMock(page);
    await gotoModule(page);

    await expect(page.getByText('Borrador de prueba para LinkedIn')).toBeVisible();
    await expect(page.getByText('Borrador', { exact: true })).toBeVisible();
  });

  test('renders row actions as a leading menu that opens without navigating', {
    tag: [...ADMIN_LINKEDIN_MODULE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (admin panel E2E specs enter routes directly; this test isolates the row-actions layout and menu contract)
    await setupPageMock(page);
    await gotoModule(page);

    const actionsHeader = page.getByTestId('linkedin-post-row-actions-header');
    await expect(actionsHeader).toBeVisible();
    const leadingHeaders = await actionsHeader.evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 2).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: 'linkedin-post-row-actions-header', label: 'Acciones', text: '' },
      { testId: null, label: null, text: 'Texto' },
    ]);
    await expectNoBlankBand(actionsHeader.locator('xpath=ancestor::table'));

    const kebab = page.getByTestId('linkedin-post-actions-1');
    await expect(kebab).toHaveAccessibleName('Acciones de Borrador de prueba para LinkedIn');
    await expect(kebab).toHaveText('');

    const listUrl = page.url();
    await openRowMenu(page, { kebab: 'linkedin-post-actions-1', menu: 'linkedin-post-actions-modal' });
    const menu = page.getByTestId('linkedin-post-actions-modal');
    await expect(menu.getByRole('heading')).toHaveText('Borrador de prueba para LinkedIn');
    await expect(menu.getByRole('listitem')).toHaveText(['Editar', 'Publicar ahora', 'Eliminar']);
    await expect(page).toHaveURL(listUrl);
  });

  test('create modal saves a draft and refreshes the list', {
    tag: [...ADMIN_LINKEDIN_MODULE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupPageMock(page, { posts: [] });
    await gotoModule(page);

    await page.getByRole('button', { name: 'Nuevo post' }).click();
    await page.getByPlaceholder(/Escribe el contenido para LinkedIn/).fill('Nuevo post desde E2E');
    await page.getByRole('button', { name: 'Guardar', exact: true }).click();

    await expect(page.getByText('Post guardado.')).toBeVisible();
    await expect(page.getByText('Nuevo post desde E2E')).toBeVisible();
    // Save closes the create modal — proves the save actually completed, not just that the click fired.
    await expect(page.getByRole('heading', { name: 'Nuevo post' })).not.toBeVisible();
  });

  test('publish now with confirm flips post to published', {
    tag: [...ADMIN_LINKEDIN_MODULE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupPageMock(page);
    await gotoModule(page);

    await chooseRowAction(page, {
      kebab: 'linkedin-post-actions-1',
      menu: 'linkedin-post-actions-modal',
      action: 'linkedin-post-publish-1',
    });
    await page.getByRole('dialog', { name: 'Publicar en LinkedIn' })
      .getByRole('button', { name: 'Publicar', exact: true }).click();

    await expect(page.getByText('Publicado en LinkedIn correctamente.')).toBeVisible();
    // Scope to tbody: "Publicado" also matches the table column header
    await expect(page.locator('tbody').getByText('Publicado', { exact: true })).toBeVisible();
    // The row's previous "Borrador" chip must be gone — proves the row actually flipped state.
    await expect(page.locator('tbody').getByText('Borrador', { exact: true })).not.toBeVisible();
  });

  test('publish API failure surfaces inline error', {
    tag: [...ADMIN_LINKEDIN_MODULE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupPageMock(page, {
      publishResponse: {
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'LinkedIn API error (500): boom' }),
      },
    });
    await gotoModule(page);

    await chooseRowAction(page, {
      kebab: 'linkedin-post-actions-1',
      menu: 'linkedin-post-actions-modal',
      action: 'linkedin-post-publish-1',
    });
    await page.getByRole('dialog', { name: 'Publicar en LinkedIn' })
      .getByRole('button', { name: 'Publicar', exact: true }).click();

    await expect(page.getByText(/LinkedIn API error/)).toBeVisible();
    // The failure must not have flipped the row — it stays in "Borrador", never reaches "Publicado".
    await expect(page.locator('tbody').getByText('Publicado', { exact: true })).not.toBeVisible();
  });
});
