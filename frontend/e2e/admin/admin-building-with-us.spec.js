/** Catches unreachable distribution, incorrect history pagination, missing mirror warnings and broken read-only contract actions. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';
import {
  buildingWithUsApiFixture, buildingWithUsContractFixture,
  buildingWithUsOverviewFixture, buildingWithUsProgramFixture,
} from '../helpers/building-with-us-fixture.js';
import {
  ADMIN_BUILDING_WITH_US_DISTRIBUTION,
  ADMIN_BUILDING_WITH_US_HISTORY,
  ADMIN_BUILDING_WITH_US_CONTRACT,
} from '../helpers/flow-tags.js';

const scenarios = new WeakMap();
const overview = buildingWithUsOverviewFixture();
const contract = buildingWithUsContractFixture();
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

async function setupApi(page, scenario) {
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'proposals/' || apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'proposals/dashboard/') return json({ total: 0, by_status: {} });
    if (apiPath === 'building-with-us/admin/' && scenario.overviewUnavailable) return json({ detail: 'Unavailable' }, 503);
    if (apiPath === 'building-with-us/admin/program/versions/' && scenario.historyUnavailable) return json({ detail: 'Unavailable' }, 503);
    if (apiPath === 'building-with-us/admin/contract/') {
      if (scenario.contractUnavailable) return json({ detail: 'Unavailable' }, 503);
      return json(buildingWithUsContractFixture(scenario.mirrorStatus));
    }
    return buildingWithUsApiFixture({ apiPath, method, route });
  });
}

async function openPanel(page) {
  // quality: allow-deep-link (sidebar reachability is tested separately; this isolates the selected panel action)
  await page.goto('/es-co/panel/building-with-us', { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { level: 1, name: 'Building with Us', exact: true }).waitFor();
}

async function openFromSidebar(page) {
  // quality: allow-deep-link (the authenticated proposals list is the starting point for navigation through Comercial)
  await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
  }
  await page.getByRole('link', { name: 'Building with Us', exact: true }).click();
  await page.getByRole('heading', { level: 1, name: 'Building with Us', exact: true }).waitFor();
}

async function openContract(page) {
  await openPanel(page);
  await page.getByTestId('building-with-us-tab-contract').click();
}

test.describe('Admin Building with Us', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-building-with-us-admin',
      userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
    });
    const scenario = {};
    scenarios.set(page, scenario);
    await setupApi(page, scenario);
  });

  test('opens the program through the Comercial sidebar', {
    tag: [...ADMIN_BUILDING_WITH_US_DISTRIBUTION, '@role:admin', '@outcome:display', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list is an authenticated entry point; the program is reached through the visible sidebar)
    await openFromSidebar(page);

    await expect(page).toHaveURL(/\/es-co\/panel\/building-with-us$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Building with Us', exact: true })).toHaveText('Building with Us');
    await expect(page.getByTestId('building-with-us-public-url-es')).toHaveText('https://projectapp.co/es-co/building-with-us');
    await expect(page.getByTestId('building-with-us-preview')).toContainText(buildingWithUsProgramFixture().hero.title);
  });

  test('copies the English public URL', {
    tag: [...ADMIN_BUILDING_WITH_US_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openPanel(page);

    await page.getByTestId('building-with-us-copy-public-url-en').click();

    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('https://projectapp.co/en-us/building-with-us');
    await expect(page.getByRole('alert')).toContainText('URL pública copiada');
  });

  test('downloads the program PDF from its distribution card', {
    tag: [...ADMIN_BUILDING_WITH_US_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openPanel(page);

    const downloadPromise = page.waitForEvent('download');
    await page.getByTestId('building-with-us-panel-download-pdf').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('building-with-us-es.pdf');
    expect(await download.failure()).toBeNull();
  });

  test('changes the preview language without moving the panel URL', {
    tag: [...ADMIN_BUILDING_WITH_US_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openPanel(page);
    const requestPromise = page.waitForRequest(/\/api\/building-with-us\/public\/\?lang=en$/);

    await page.getByTestId('building-with-us-language-en').click();

    expect(new URL((await requestPromise).url()).searchParams.get('lang')).toBe('en');
    await expect(page.getByRole('heading', { name: buildingWithUsProgramFixture('en').hero.title, exact: true })).toHaveText(buildingWithUsProgramFixture('en').hero.title);
    await expect(page).toHaveURL(/\/es-co\/panel\/building-with-us$/);
  });

  test('retries the unavailable module overview', {
    tag: [...ADMIN_BUILDING_WITH_US_DISTRIBUTION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = scenarios.get(page);
    scenario.overviewUnavailable = true;
    await openPanel(page);
    await expect(page.getByTestId('building-with-us-overview-error')).toContainText('No se pudo cargar la información del módulo.');
    scenario.overviewUnavailable = false;

    await page.getByTestId('building-with-us-overview-retry').click();

    await expect(page.getByTestId('building-with-us-program-version')).toContainText(`Versión ${overview.program.version}`);
    await expect(page.getByTestId('building-with-us-overview-error')).toHaveCount(0);
  });

  test('presents the current program version in its history', {
    tag: [...ADMIN_BUILDING_WITH_US_HISTORY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list is an authenticated entry point; history is reached through the program sidebar link)
    await openFromSidebar(page);
    const version = page.getByTestId(`building-with-us-program-version-${overview.program.version_id}`);

    await expect(version).toContainText(`Versión ${overview.program.version}`);
    await expect(version).toContainText(overview.program.author.name);
    await expect(version).toContainText(overview.program.change_note);
  });

  test('loads the next history page with the current offset', {
    tag: [...ADMIN_BUILDING_WITH_US_HISTORY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openPanel(page);
    const requestPromise = page.waitForRequest(/\/api\/building-with-us\/admin\/program\/versions\/\?limit=20&offset=20$/);

    await page.getByTestId('building-with-us-program-history-more').click();
    const request = await requestPromise;

    expect(new URL(request.url()).searchParams.get('offset')).toBe('20');
    await expect(page.getByTestId('building-with-us-program-history').getByRole('listitem')).toHaveCount(21);
    await expect(page.getByTestId('building-with-us-program-version-101')).toContainText('Versión 1');
    await expect(page.getByTestId('building-with-us-program-history-more')).toHaveCount(0);
  });

  test('retries an unavailable version history', {
    tag: [...ADMIN_BUILDING_WITH_US_HISTORY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = scenarios.get(page);
    scenario.historyUnavailable = true;
    await openPanel(page);
    await expect(page.getByTestId('building-with-us-program-history-error')).toContainText('No se pudo cargar el historial de versiones.');
    scenario.historyUnavailable = false;

    await page.getByTestId('building-with-us-program-history-retry').click();

    await expect(page.getByTestId('building-with-us-program-history').getByRole('listitem')).toHaveCount(20);
    await expect(page.getByTestId('building-with-us-program-history-error')).toHaveCount(0);
  });

  test('opens the synchronized contract from its tab', {
    tag: [...ADMIN_BUILDING_WITH_US_CONTRACT, '@role:admin', '@outcome:display', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list is an authenticated entry point; the contract is reached through the sidebar and tab)
    await openFromSidebar(page);

    await page.getByTestId('building-with-us-tab-contract').click();

    await expect(page).toHaveURL(/\/es-co\/panel\/building-with-us\?tab=contract$/);
    await expect(page.getByTestId('building-with-us-mirror-status')).toHaveText('Sincronizado');
    await expect(page.getByTestId('building-with-us-mirror-link')).toHaveAttribute('href', `/es-co/panel/documents/${contract.mirror.document_id}/edit`);
    await expect(page.getByTestId('building-with-us-contract-body').getByRole('heading', { level: 1, name: 'Contrato de alianza Building with Us', exact: true })).toHaveText('Contrato de alianza Building with Us');
  });

  test('warns about an outdated contract mirror', {
    tag: [...ADMIN_BUILDING_WITH_US_CONTRACT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    scenarios.get(page).mirrorStatus = 'out_of_sync';
    // quality: allow-deep-link (a saved contract-tab URL must expose the mirror warning immediately)
    // quality: allow-no-interaction (the read-only mirror warning is the result of opening the saved contract-tab URL)
    await page.goto('/es-co/panel/building-with-us?tab=contract', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('building-with-us-mirror-status')).toHaveText('Desactualizado');
    await expect(page.getByTestId('building-with-us-mirror-alert')).toHaveText('La copia del Gestor Documental está desactualizada. Se sincroniza desde el MCP «Building with Us».');
  });

  test('hides the mirror link before document initialization', {
    tag: [...ADMIN_BUILDING_WITH_US_CONTRACT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    scenarios.get(page).mirrorStatus = 'not_initialized';
    // quality: allow-deep-link (the proposals list is an authenticated entry point; the uninitialized mirror is inspected after sidebar and tab navigation)
    await openFromSidebar(page);

    await page.getByTestId('building-with-us-tab-contract').click();

    await expect(page.getByTestId('building-with-us-mirror-status')).toHaveText('Sin inicializar');
    await expect(page.getByTestId('building-with-us-mirror-link')).toHaveCount(0);
    await expect(page.getByTestId('building-with-us-mirror-alert')).toHaveText('La copia del Gestor Documental se inicializa desde el MCP «Building with Us».');
  });

  test('downloads the read-only contract PDF', {
    tag: [...ADMIN_BUILDING_WITH_US_CONTRACT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await openContract(page);

    const downloadPromise = page.waitForEvent('download');
    await page.getByTestId('building-with-us-contract-download-pdf').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('building-with-us-contract.pdf');
    expect(await download.failure()).toBeNull();
  });

  test('retries an unavailable contract', {
    tag: [...ADMIN_BUILDING_WITH_US_CONTRACT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = scenarios.get(page);
    scenario.contractUnavailable = true;
    await openContract(page);
    await expect(page.getByTestId('building-with-us-contract-error')).toContainText('No se pudo cargar el contrato.');
    scenario.contractUnavailable = false;

    await page.getByTestId('building-with-us-contract-retry').click();

    await expect(page.getByTestId('building-with-us-mirror-status')).toHaveText('Sincronizado');
    await expect(page.getByTestId('building-with-us-contract-body')).toContainText('Incubar un producto con alcance definido y aportes verificables.');
  });
});
