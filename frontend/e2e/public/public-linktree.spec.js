/**
 * E2E tests for the public linktree page (/lk/@handle).
 *
 * Covers flow: public-linktree-view
 *   - Renders identity, tiered buttons (pair side by side) and footer.
 *   - Pending buttons render dashed/inert with the PENDIENTE tag.
 *   - Unknown handle shows the not-available state.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PUBLIC_LINKTREE_VIEW } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const publicTree = {
  handle: 'gustavo',
  kind: 'personal',
  display_name: 'Gustavo Pérez',
  role: 'Co Founder & CEO',
  bio: 'Automatizamos procesos e implementamos la infraestructura de software que tu negocio necesita.',
  avatar: null,
  claim_line_1: '',
  claim_line_2: '',
  badge_text: 'TECH WEEK CO',
  footer_tagline: 'DISEÑO · CÓDIGO · RESULTADOS',
  show_brand_header: true,
  pwa_enabled: true,
  pwa_title: 'Guarda la tarjeta en tu teléfono',
  pwa_description: 'Queda como un ícono en tu pantalla de inicio, sin instalar nada de la tienda.',
  vcard_first_name: 'Gustavo',
  vcard_last_name: 'Pérez',
  vcard_org: 'ProjectApp.',
  vcard_email: 'team@projectapp.co',
  vcard_tel: '+573238122373',
  vcard_url: 'https://projectapp.co',
  buttons: [
    {
      id: 1, tier: 'primary', action: 'linkedin', label: 'Conectemos en LinkedIn',
      href: '', icon: '', resolved_icon: 'linkedin', kind: 'url',
      is_pending: true, order: 0, is_active: true,
    },
    {
      id: 2, tier: 'pair', action: 'vcard', label: 'Guardar',
      href: '', icon: '', resolved_icon: 'user-round-plus', kind: 'download-vcard',
      is_pending: false, order: 1, is_active: true,
    },
    {
      id: 3, tier: 'pair', action: 'whatsapp', label: 'WhatsApp',
      href: 'https://wa.me/573238122373', icon: '', resolved_icon: 'whatsapp',
      kind: 'url', is_pending: false, order: 2, is_active: true,
    },
    {
      id: 4, tier: 'row', action: 'web', label: 'Conoce ProjectApp',
      href: 'https://projectapp.co/en-us/', icon: '', resolved_icon: 'globe',
      kind: 'url', is_pending: false, order: 3, is_active: true,
    },
  ],
};

function setupPublicMock(page, { found = true } = {}) {
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath.match(/^linktrees\/public\/[^/]+\/$/) && route.request().method() === 'GET') {
      if (!found) {
        return { status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found.' }) };
      }
      return { status: 200, contentType: 'application/json', body: JSON.stringify(publicTree) };
    }
    return null;
  });
}

test.describe('Public Linktree', () => {
  test('renders identity, buttons and footer for a valid handle', {
    tag: [...PUBLIC_LINKTREE_VIEW, '@role:visitor', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    // quality: allow-deep-link (public linktree is reached from a QR scan / external short link — there is no in-app navigation to it)
    // quality: allow-no-interaction (public display contract: the page renders API data; actions are covered by unit tests)
    await setupPublicMock(page);
    await page.goto('/es-co/lk/@gustavo');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('heading', { name: 'Gustavo Pérez' })).toBeVisible();
    await expect(page).toHaveTitle('Gustavo Pérez · ProjectApp.');
    await expect(page.locator('html')).toHaveAttribute('lang', 'es-CO');
    await expect(page.locator('head meta[name="robots"]')).toHaveAttribute('content', 'noindex');
    await expect(page.getByTestId('linktree-badge')).toHaveText('TECH WEEK CO');
    await expect(page.getByTestId('linktree-buttons').locator('.lt-btn')).toHaveCount(4);
    await expect(page.locator('.lt-pair-row .lt-btn')).toHaveCount(2);
    await expect(page.getByTestId('linktree-pwa-block')).toBeVisible();
    await expect(page.getByText('DISEÑO · CÓDIGO · RESULTADOS')).toBeVisible();
  });

  test('declares English for a classic card opened in the English route', {
    tag: [...PUBLIC_LINKTREE_VIEW, '@role:visitor', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the classic card is opened from a shared link)
    // quality: allow-no-interaction (the readonly document head is the display outcome)
    await setupPublicMock(page);
    await page.goto('/en-us/lk/@gustavo', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'Gustavo Pérez' })).toBeVisible();
    await expect(page).toHaveTitle('Gustavo Pérez · ProjectApp.');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en-US');
    await expect(page.locator('head meta[name="robots"]')).toHaveAttribute('content', 'noindex');
  });

  test('renders an unresolved destination as a dashed PENDIENTE button', {
    tag: [...PUBLIC_LINKTREE_VIEW, '@role:visitor', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (public linktree is reached from a QR scan / external short link — there is no in-app navigation to it)
    // quality: allow-no-interaction (pending buttons are inert by design — the assertion IS that they don't navigate)
    await setupPublicMock(page);
    await page.goto('/es-co/lk/@gustavo');
    await page.waitForLoadState('domcontentloaded');

    const pending = page.locator('.lt-btn--pending');
    await expect(pending).toHaveCount(1);
    await expect(pending).toContainText('PENDIENTE');
  });

  test('shows the not-available state for an unknown handle', {
    tag: [...PUBLIC_LINKTREE_VIEW, '@role:visitor', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (public linktree is reached from a QR scan / external short link — there is no in-app navigation to it)
    // quality: allow-no-interaction (failure outcome is a terminal state: the API 404s and the page offers nothing to interact with)
    await setupPublicMock(page, { found: false });
    await page.goto('/es-co/lk/@nadie');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByTestId('linktree-not-found')).toContainText('Este enlace no está disponible.');
    await expect(page.getByTestId('linktree-card')).toHaveCount(0);
  });
});
