/** Catches unreachable consulting distribution, stale previews, and history retries that discard already visible revisions. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';
import {
  consultingApiFixture, consultingOverviewFixture, consultingProgramFixture,
} from '../helpers/consulting-fixture.js';
import {
  ADMIN_CONSULTING_DISTRIBUTION, ADMIN_CONSULTING_HISTORY, ADMIN_CONSULTING_PREVIEW,
} from '../helpers/flow-tags.js';

const scenarios = new WeakMap();
const overview = consultingOverviewFixture();
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

async function setupApi(page, scenario) {
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'proposals/' || apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'proposals/dashboard/') return json({ total: 0, by_status: {} });
    if (apiPath === 'consulting/admin/' && scenario.overviewUnavailable) return json({ detail: 'Unavailable' }, 503);
    if (apiPath === 'consulting/public/' && scenario.previewUnavailable) return json({ detail: 'Unavailable' }, 503);
    if (apiPath === 'consulting/admin/program/versions/' && scenario.historyUnavailable) return json({ detail: 'Unavailable' }, 503);
    return consultingApiFixture({ apiPath, method, route });
  });
}

async function openPanel(page) {
  await page.goto('/es-co/panel/consulting', { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { level: 1, name: 'Consultoría y asesoría', exact: true }).waitFor();
}

async function openFromCommercial(page) {
  await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
  }
  await page.getByRole('link', { name: 'Consultoría y asesoría', exact: true }).click();
  await page.getByRole('heading', { level: 1, name: 'Consultoría y asesoría', exact: true }).waitFor();
}

test.describe('Admin consulting', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-consulting-admin',
      userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
    });
    const scenario = {};
    scenarios.set(page, scenario);
    await setupApi(page, scenario);
  });

  test('reaches consulting from the Comercial sidebar with the Spanish share URL', {
    tag: [...ADMIN_CONSULTING_DISTRIBUTION, '@role:admin', '@outcome:display', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the authenticated proposals list is the entry point before visible Comercial navigation).
    await openFromCommercial(page);

    await expect(page).toHaveURL(/\/es-co\/panel\/consulting$/);
    await expect(page.getByTestId('consulting-public-url-es')).toHaveText('https://projectapp.co/es-co/consulting');
    await expect(page.getByTestId('consulting-preview')).toContainText(consultingProgramFixture().hero.title);
  });

  test('copies the English public URL from the distribution card', {
    tag: [...ADMIN_CONSULTING_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openPanel(page);

    await page.getByTestId('consulting-copy-public-url-en').click();

    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('https://projectapp.co/en-us/consulting');
    await expect(page.getByRole('alert')).toContainText('URL pública copiada');
  });

  test('opens the public presentation from the distribution card', {
    tag: [...ADMIN_CONSULTING_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openPanel(page);
    const popupPromise = page.waitForEvent('popup');

    await page.getByTestId('consulting-open-public').click();
    const popup = await popupPromise;

    await expect(page.getByTestId('consulting-open-public')).toHaveAttribute('href', 'https://projectapp.co/es-co/consulting');
    await expect.poll(() => popup.url()).toBe('https://projectapp.co/es-co/consulting');
    await popup.close();
  });

  test('downloads the Spanish program PDF from the distribution card', {
    tag: [...ADMIN_CONSULTING_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openPanel(page);
    const downloadPromise = page.waitForEvent('download');

    await page.getByTestId('consulting-panel-download-pdf').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('consulting-es.pdf');
    expect(await download.failure()).toBeNull();
  });

  test('reports a rejected clipboard write without losing the distribution card', {
    tag: [...ADMIN_CONSULTING_DISTRIBUTION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('denied')) } });
    });
    await openPanel(page);

    await page.getByTestId('consulting-copy-public-url-es').click();

    await expect(page.getByRole('alert')).toContainText('No se pudo copiar la URL pública.');
    await expect(page.getByTestId('consulting-public-url-es')).toHaveText('https://projectapp.co/es-co/consulting');
  });

  test('shows the current version and Spanish preview after Comercial navigation', {
    tag: [...ADMIN_CONSULTING_PREVIEW, '@role:admin', '@outcome:display', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the authenticated proposals list is the entry point before visible Comercial navigation).
    await openFromCommercial(page);

    await expect(page.getByTestId('consulting-program-version')).toContainText(`Versión ${overview.program.version}`);
    await expect(page.getByTestId('consulting-preview')).toContainText(consultingProgramFixture().areas.items[4].title);
  });

  test('switches preview content to English without moving the panel URL', {
    tag: [...ADMIN_CONSULTING_PREVIEW, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openPanel(page);
    const requestPromise = page.waitForRequest(/\/api\/consulting\/public\/\?lang=en$/);

    await page.getByTestId('consulting-preview-en').click();

    expect(new URL((await requestPromise).url()).searchParams.get('lang')).toBe('en');
    await expect(page.getByRole('heading', { name: consultingProgramFixture('en').hero.title, exact: true })).toHaveText(consultingProgramFixture('en').hero.title);
    await expect(page).toHaveURL(/\/es-co\/panel\/consulting$/);
  });

  test('retries an unavailable English preview', {
    tag: [...ADMIN_CONSULTING_PREVIEW, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = scenarios.get(page);
    scenario.previewUnavailable = true;
    await openPanel(page);
    await expect(page.getByTestId('consulting-preview-error')).toContainText('No se pudo cargar la vista previa del servicio.');
    scenario.previewUnavailable = false;

    await page.getByTestId('consulting-preview-error').getByRole('button', { name: 'Reintentar', exact: true }).click();

    await expect(page.getByTestId('consulting-preview')).toContainText(consultingProgramFixture().hero.title);
    await expect(page.getByTestId('consulting-preview-error')).toHaveCount(0);
  });

  test('shows twenty concrete program revisions in history', {
    tag: [...ADMIN_CONSULTING_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the authenticated proposals list is the entry point before visible Comercial navigation).
    await openFromCommercial(page);

    await expect(page.getByTestId('consulting-program-history').getByRole('listitem')).toHaveCount(20);
    await expect(page.getByTestId('consulting-program-version-121')).toContainText('Versión 21');
  });

  test('loads the final history revision from offset twenty', {
    tag: [...ADMIN_CONSULTING_HISTORY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openPanel(page);
    const requestPromise = page.waitForRequest(/\/api\/consulting\/admin\/program\/versions\/\?limit=20&offset=20$/);

    await page.getByTestId('consulting-program-history-more').click();

    expect(new URL((await requestPromise).url()).searchParams.get('offset')).toBe('20');
    await expect(page.getByTestId('consulting-program-history').getByRole('listitem')).toHaveCount(21);
    await expect(page.getByTestId('consulting-program-version-101')).toContainText('Versión 1');
  });

  test('retries a failed next history page without dropping the first twenty revisions', {
    tag: [...ADMIN_CONSULTING_HISTORY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await openPanel(page);
    const scenario = scenarios.get(page);
    scenario.historyUnavailable = true;

    await page.getByTestId('consulting-program-history-more').click();
    await expect(page.getByTestId('consulting-program-history-error')).toContainText('No se pudo cargar el historial de versiones.');
    await expect(page.getByTestId('consulting-program-history').getByRole('listitem')).toHaveCount(20);
    scenario.historyUnavailable = false;

    await page.getByTestId('consulting-program-history-retry').click();

    await expect(page.getByTestId('consulting-program-history').getByRole('listitem')).toHaveCount(21);
    await expect(page.getByTestId('consulting-program-history-error')).toHaveCount(0);
  });
});
