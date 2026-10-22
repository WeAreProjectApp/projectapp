/** Detects broken Células navigation, incorrect monthly economics and unusable contract mirror states. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';
import {
  BUILDING_ON_DEMAND_GUIDE_SEEN_KEY,
  buildingOnDemandApiFixture, buildingOnDemandContractFixture,
  buildingOnDemandOverviewFixture, buildingOnDemandProgramFixture,
} from '../helpers/building-on-demand-fixture.js';

const scenarios = new WeakMap();
const overview = buildingOnDemandOverviewFixture();
const program = buildingOnDemandProgramFixture();
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
const unavailable = () => json({ message: 'No disponible', code: 'UNAVAILABLE', details: {} }, 503);

async function setupApi(page, scenario) {
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'proposals/' || apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'proposals/dashboard/') return json({ total: 0, by_status: {} });
    scenario.videoSettings ??= {
      show_building_on_demand_video: true,
      resources: { 'building-on-demand:es': { mode: 'default' } },
    };
    if (apiPath === 'explainer-videos/admin/settings/' && method === 'GET') return json(scenario.videoSettings);
    if (apiPath === 'explainer-videos/admin/settings/update/' && method === 'PATCH') {
      scenario.videoPatch = route.request().postDataJSON();
      if (scenario.videoSaveFails) return json({ detail: 'No se pudo guardar.' }, 500);
      scenario.videoSettings = { ...scenario.videoSettings, ...scenario.videoPatch };
      return json(scenario.videoSettings);
    }
    if (apiPath === 'building-on-demand/admin/') {
      if (scenario.overviewUnavailable) return unavailable();
      return json(buildingOnDemandOverviewFixture({ withContract: !scenario.contractAbsent, mirrorStatus: scenario.mirrorStatus }));
    }
    if (apiPath === 'building-on-demand/admin/program/versions/' && scenario.historyUnavailable) return unavailable();
    if (apiPath === 'building-on-demand/admin/economics/' && scenario.economicsUnavailable) return unavailable();
    if (apiPath === 'building-on-demand/admin/contract/') {
      if (scenario.contractAbsent) return json({ message: 'No existe', code: 'NOT_FOUND', details: {} }, 404);
      if (scenario.contractUnavailable) return unavailable();
      return json(buildingOnDemandContractFixture(scenario.mirrorStatus));
    }
    return buildingOnDemandApiFixture({ apiPath, method, route });
  });
}

async function openPanel(page, query = '') {
  await page.goto(`/es-co/panel/cells${query}`, { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await page.getByRole('heading', { level: 1, name: 'Células', exact: true }).waitFor();
}

async function openFromSidebar(page) {
  await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
  }
  await page.getByRole('link', { name: 'Células', exact: true }).click();
  await page.getByRole('heading', { level: 1, name: 'Células', exact: true }).waitFor();
}

async function openEconomicsFromSidebar(page) {
  await openFromSidebar(page);
  await page.getByRole('tab', { name: 'Economía', exact: true }).click();
}

async function openContractFromSidebar(page) {
  await openFromSidebar(page);
  await page.getByRole('tab', { name: 'Contrato', exact: true }).click();
}

test.describe('Admin Building on Demand', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-building-on-demand-admin',
      userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
    });
    await page.addInitScript((key) => localStorage.setItem(key, 'true'), BUILDING_ON_DEMAND_GUIDE_SEEN_KEY);
    const scenario = {};
    scenarios.set(page, scenario);
    await setupApi(page, scenario);
  });

  test('opens the program through the Comercial sidebar', {
    tag: ['@flow:admin-building-on-demand-program', '@role:admin', '@outcome:display', '@responsive:commercial'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts authenticated sidebar navigation to Células)
    await openFromSidebar(page);

    await expect(page).toHaveURL(/\/es-co\/panel\/cells$/);
    await expect(page.getByTestId('building-on-demand-admin-program-version')).toContainText(`Versión ${overview.program.version}`);
    await expect(page.getByTestId('building-on-demand-admin-public-url-es')).toHaveText('https://projectapp.co/es-co/building-on-demand');
    await expect(page.getByTestId('building-on-demand-admin-open-public-en')).toHaveAttribute('href', 'https://projectapp.co/en-us/building-on-demand');
    await expect(page.getByTestId('building-on-demand-admin-download-pdf-es')).toBeVisible();
    await expect(page.getByTestId('building-on-demand-admin-mcp-hint')).toContainText('Este panel es de solo lectura.');
    await expect(page.getByTestId('building-on-demand-panel-preview')).toContainText(program.hero.title);
  });

  test('copies the English distribution URL', {
    tag: ['@flow:admin-building-on-demand-program', '@role:admin', '@outcome:success'],
  }, async ({ page, context }) => {
    // quality: allow-deep-link (sidebar reachability is tested separately; this isolates copying the public link)
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openPanel(page);

    await page.getByTestId('building-on-demand-admin-copy-public-url-en').click();

    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('https://projectapp.co/en-us/building-on-demand');
    await expect(page.getByRole('alert')).toContainText('URL pública copiada');
  });

  test('changes the program preview language', {
    tag: ['@flow:admin-building-on-demand-program', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar reachability is tested separately; this isolates preview language selection)
    await openPanel(page);
    await expect(page.getByTestId('building-on-demand-panel-preview')).toContainText(program.hero.title);

    await page.getByTestId('building-on-demand-panel-preview-language-en').click();

    await expect(page.getByTestId('building-on-demand-panel-preview')).toContainText(buildingOnDemandProgramFixture('en').hero.title);
    await expect(page.getByTestId('building-on-demand-panel-preview-language-en')).toHaveAttribute('aria-selected', 'true');
    await expect(page).toHaveURL(/\/es-co\/panel\/cells$/);
  });

  test('retries an unavailable program overview', {
    tag: ['@flow:admin-building-on-demand-program', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the program URL isolates recovery of its failed overview request)
    const scenario = scenarios.get(page);
    scenario.overviewUnavailable = true;
    await openPanel(page);
    await expect(page.getByTestId('building-on-demand-panel-overview-error')).toContainText('No se pudo cargar la información del módulo.');
    scenario.overviewUnavailable = false;

    await page.getByTestId('building-on-demand-panel-overview-retry').click();

    await expect(page.getByTestId('building-on-demand-admin-program-version')).toContainText(`Versión ${overview.program.version}`);
    await expect(page.getByTestId('building-on-demand-panel-overview-error')).toHaveCount(0);
  });

  test('loads the final older program version', {
    tag: ['@flow:admin-building-on-demand-history', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar reachability is tested separately; this isolates history pagination)
    await openPanel(page);
    await expect(page.getByTestId('building-on-demand-admin-program-history-count')).toHaveText('20 de 21 versiones');
    const nextPage = page.waitForRequest(/\/api\/building-on-demand\/admin\/program\/versions\/\?limit=20&offset=20$/);

    await page.getByRole('button', { name: 'Ver más', exact: true }).click();

    expect(new URL((await nextPage).url()).searchParams.get('offset')).toBe('20');
    await expect(page.getByTestId('building-on-demand-admin-program-history-count')).toHaveText('21 de 21 versiones');
    await expect(page.getByTestId('building-on-demand-admin-program-version-101')).toContainText('Versión 1');
    await expect(page.getByTestId('building-on-demand-admin-program-history-more')).toHaveCount(0);
  });

  test('retries an unavailable program history', {
    tag: ['@flow:admin-building-on-demand-history', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the program URL isolates recovery of its failed history request)
    const scenario = scenarios.get(page);
    scenario.historyUnavailable = true;
    await openPanel(page);
    await expect(page.getByTestId('building-on-demand-admin-program-history-error')).toContainText('No se pudo cargar el historial de versiones.');
    scenario.historyUnavailable = false;

    await page.getByTestId('building-on-demand-admin-program-history-retry').click();

    await expect(page.getByTestId('building-on-demand-admin-program-history-count')).toHaveText('20 de 21 versiones');
    await expect(page.getByTestId('building-on-demand-admin-program-history-error')).toHaveCount(0);
  });

  test('shows the Starter monthly break-even values', {
    tag: ['@flow:admin-building-on-demand-economics', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Economía)
    await openEconomicsFromSidebar(page);

    const row = page.getByTestId('building-on-demand-admin-economics-row-starter-monthly');
    await expect(row).toContainText('$1.800.000 COP');
    await expect(row).toContainText('$46.291 COP');
    await expect(row).toContainText('31,9 h');
    await expect(row).toContainText('33 %');
    await expect(row).toContainText('96 h');
  });

  test('shows the Business monthly break-even values', {
    tag: ['@flow:admin-building-on-demand-economics', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Economía)
    await openEconomicsFromSidebar(page);

    const row = page.getByTestId('building-on-demand-admin-economics-row-business-monthly');
    await expect(row).toContainText('$4.200.000 COP');
    await expect(row).toContainText('$116.501 COP');
    await expect(row).toContainText('74,2 h');
    await expect(row).toContainText('39 %');
    await expect(row).toContainText('192 h');
    await expect(page.getByTestId('building-on-demand-admin-economics-hour-cost')).toHaveText('$55.000 COP');
    await expect(page.getByTestId('building-on-demand-admin-economics-vat')).toHaveText('19 %');
  });

  test('shows the Enterprise monthly break-even values', {
    tag: ['@flow:admin-building-on-demand-economics', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Economía)
    await openEconomicsFromSidebar(page);

    const row = page.getByTestId('building-on-demand-admin-economics-row-enterprise-monthly');
    await expect(row).toContainText('$9.600.000 COP');
    await expect(row).toContainText('$200.991 COP');
    await expect(row).toContainText('170,9 h');
    await expect(row).toContainText('59 %');
    await expect(row).toContainText('288 h');
  });

  test('shows the Enterprise nine-month break-even values', {
    tag: ['@flow:admin-building-on-demand-economics', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Economía)
    await openEconomicsFromSidebar(page);

    const row = page.getByTestId('building-on-demand-admin-economics-row-enterprise-nine-month');
    await expect(row).toContainText('$7.200.000 COP');
    await expect(row).toContainText('127,3 h');
    await expect(row).toContainText('44 %');
    await expect(page.getByTestId('building-on-demand-admin-economics-provider')).toHaveText('Hostinger');
    await expect(page.getByTestId('building-on-demand-admin-economics-reference')).toHaveAttribute('href', 'https://www.hostinger.com/co/vps-servidor-web');
  });

  test('retries unavailable internal economics', {
    tag: ['@flow:admin-building-on-demand-economics', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the documented tab query isolates recovery of the economics request)
    const scenario = scenarios.get(page);
    scenario.economicsUnavailable = true;
    await openPanel(page, '?tab=economics');
    await expect(page.getByTestId('building-on-demand-admin-economics-error')).toContainText('No se pudo cargar la economía del programa.');
    scenario.economicsUnavailable = false;

    await page.getByTestId('building-on-demand-admin-economics-retry').click();

    await expect(page.getByTestId('building-on-demand-admin-economics-row-business-monthly')).toContainText('74,2 h');
    await expect(page.getByTestId('building-on-demand-admin-economics-error')).toHaveCount(0);
  });

  test('reads the synchronized contract mirror', {
    tag: ['@flow:admin-building-on-demand-contract', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Contrato)
    await openContractFromSidebar(page);

    await expect(page.getByTestId('building-on-demand-admin-contract-status')).toHaveText('Sincronizado');
    await expect(page.getByTestId('building-on-demand-admin-contract-version')).toContainText('Versión 21');
    await expect(page.getByTestId('building-on-demand-admin-contract-body')).toContainText('Las horas se renuevan cada mes, no se acumulan');
    await expect(page.getByTestId('building-on-demand-admin-mirror-link')).toHaveAttribute('href', '/es-co/panel/documents/731/edit');
    await expect(page.getByRole('link', { name: 'Ver PDF del contrato', exact: true })).toHaveAttribute('href', '/api/building-on-demand/admin/contract/pdf/?inline=1');
    await expect(page.getByTestId('building-on-demand-admin-mirror-alert')).toHaveCount(0);
  });

  test('explains an uninitialized contract mirror', {
    tag: ['@flow:admin-building-on-demand-contract', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Contrato)
    scenarios.get(page).mirrorStatus = 'not_initialized';
    await openContractFromSidebar(page);

    await expect(page.getByTestId('building-on-demand-admin-contract-status')).toHaveText('Sin inicializar');
    await expect(page.getByTestId('building-on-demand-admin-mirror-alert')).toContainText('se inicializa desde el conector MCP building-on-demand.');
    await expect(page.getByTestId('building-on-demand-admin-contract-body')).toContainText('Acceso a una célula Scrum compartida');
    await expect(page.getByTestId('building-on-demand-admin-mirror-link')).toHaveCount(0);
  });

  test('warns about an outdated contract mirror', {
    tag: ['@flow:admin-building-on-demand-contract', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Contrato)
    scenarios.get(page).mirrorStatus = 'out_of_sync';
    await openContractFromSidebar(page);

    await expect(page.getByTestId('building-on-demand-admin-contract-status')).toHaveText('Desactualizado');
    await expect(page.getByTestId('building-on-demand-admin-mirror-alert')).toContainText('La copia del Gestor Documental está desactualizada.');
    await expect(page.getByTestId('building-on-demand-admin-contract-mirror')).toContainText('Versión de la copia: 20');
    await expect(page.getByTestId('building-on-demand-admin-contract-version')).toContainText('Versión 21');
  });

  test('explains the contract not yet published', {
    tag: ['@flow:admin-building-on-demand-contract', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the proposals list starts sidebar navigation before selecting Contrato)
    scenarios.get(page).contractAbsent = true;
    await openContractFromSidebar(page);

    await expect(page.getByTestId('building-on-demand-admin-contract-unavailable')).toHaveText('El contrato todavía no está disponible');
    await expect(page.getByTestId('building-on-demand-admin-mcp-hint')).toContainText('Este panel es de solo lectura.');
    await expect(page.getByTestId('building-on-demand-admin-contract-history')).toHaveCount(0);
    await expect(page.getByTestId('building-on-demand-admin-contract-error')).toHaveCount(0);
  });

  test('downloads the published contract PDF', {
    tag: ['@flow:admin-building-on-demand-contract', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar reachability is tested separately; this isolates the contract download)
    await openPanel(page, '?tab=contract');
    const downloadPromise = page.waitForEvent('download');

    await page.getByTestId('building-on-demand-admin-contract-download-pdf').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('building-on-demand-contract.pdf');
    expect(await download.failure()).toBeNull();
  });

  test('retries an unavailable published contract', {
    tag: ['@flow:admin-building-on-demand-contract', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the documented tab query isolates recovery of the contract request)
    const scenario = scenarios.get(page);
    scenario.contractUnavailable = true;
    await openPanel(page, '?tab=contract');
    await expect(page.getByTestId('building-on-demand-admin-contract-error')).toContainText('No se pudo cargar el contrato.');
    scenario.contractUnavailable = false;

    await page.getByTestId('building-on-demand-admin-contract-retry').click();

    await expect(page.getByTestId('building-on-demand-admin-contract-body')).toContainText('Acceso a una célula Scrum compartida');
    await expect(page.getByTestId('building-on-demand-admin-contract-error')).toHaveCount(0);
  });

  test('opens the program from its tab query', {
    tag: ['@flow:admin-building-on-demand-program', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the documented tab query is the entry point under test)
    // quality: allow-no-interaction (the tab query itself selects the view; clicking a tab would replace the input under test)
    await openPanel(page, '?tab=program');

    await expect(page.getByRole('tab', { name: 'Programa', exact: true })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('building-on-demand-panel-preview')).toContainText(program.hero.title);
    await expect(page.getByTestId('building-on-demand-admin-program-version')).toContainText('Versión 21');
  });

  test('opens economics from its tab query', {
    tag: ['@flow:admin-building-on-demand-economics', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the documented tab query is the entry point under test)
    // quality: allow-no-interaction (the tab query itself selects the view; clicking a tab would replace the input under test)
    await openPanel(page, '?tab=economics');

    await expect(page.getByRole('tab', { name: 'Economía', exact: true })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('building-on-demand-admin-economics-row-business-monthly')).toContainText('$4.200.000 COP');
    await expect(page.getByTestId('building-on-demand-panel-preview')).toHaveCount(0);
  });

  test('opens the contract from its tab query', {
    tag: ['@flow:admin-building-on-demand-contract', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the documented tab query is the entry point under test)
    // quality: allow-no-interaction (the tab query itself selects the view; clicking a tab would replace the input under test)
    await openPanel(page, '?tab=contract');

    await expect(page.getByRole('tab', { name: 'Contrato', exact: true })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('building-on-demand-admin-contract-status')).toHaveText('Sincronizado');
    await expect(page.getByTestId('building-on-demand-panel-preview')).toHaveCount(0);
  });

  test('plays the Scrum explainer once from the Programa tab', {
    tag: ['@flow:admin-building-on-demand-explainer', '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the authenticated proposals entry is followed by the visible Células sidebar link)
    // Bug caught: Células duplicated the explainer inside the preview or could not start playback from its panel card.
    await openFromSidebar(page);
    const card = page.getByTestId('building-on-demand-explainer-card');

    await expect(card).toHaveCount(1);
    await expect(card).toContainText('Video explicativo de Células Scrum');
    await expect(page.getByTestId('building-on-demand-panel-preview').getByTestId('building-on-demand-explainer-card')).toHaveCount(0);

    await page.getByTestId('building-on-demand-explainer-play').click();

    await expect(page.getByTestId('building-on-demand-explainer-player')).toHaveAttribute('controls', '');
    await expect(page.getByTestId('building-on-demand-explainer-player')).toHaveAttribute('src', /building-on-demand-brag-v2-es\.mp4/);
  });

  test('hides the public Scrum explainer from its panel switch', {
    tag: ['@flow:admin-building-on-demand-explainer-visibility', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: the Scrum toggle updated a different setting, so visitors still received the video.
    await openPanel(page);
    const scenario = scenarios.get(page);
    const toggle = page.getByTestId('building-on-demand-explainer-visibility-toggle');
    await expect(toggle).toHaveAttribute('aria-checked', 'true');

    await toggle.click();

    await expect(toggle).toHaveAttribute('aria-checked', 'false');
    await expect(page.getByRole('alert')).toContainText('El video quedó oculto en la presentación pública.');
    expect(scenario.videoPatch).toEqual({ show_building_on_demand_video: false });
  });

  test('offers the Scrum file after panel playback fails', {
    tag: ['@flow:admin-building-on-demand-explainer', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Bug caught: a media failure in Células left administrators without a way to open the Scrum file.
    await page.route(/building-on-demand-brag-v2-es[^/?]*\.mp4$/, (route) => route.abort());
    await openFromSidebar(page);

    await page.getByTestId('building-on-demand-explainer-play').click();

    await expect(page.getByTestId('building-on-demand-explainer-error')).toContainText('No pudimos reproducir el video en este navegador.');
    await expect(page.getByTestId('building-on-demand-explainer-open')).toHaveAttribute('href', /building-on-demand-brag-v2-es\.mp4/);
  });

  test('restores the Scrum visibility switch after a save failure', {
    tag: ['@flow:admin-building-on-demand-explainer-visibility', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Bug caught: a rejected visibility save left Células claiming the public video was hidden.
    scenarios.get(page).videoSaveFails = true;
    await openPanel(page);
    const toggle = page.getByTestId('building-on-demand-explainer-visibility-toggle');
    await expect(toggle).toHaveAttribute('aria-checked', 'true');

    await toggle.click();

    await expect(page.getByRole('alert')).toContainText('No pudimos guardar la visibilidad del video. Intenta de nuevo.');
    await expect(toggle).toHaveAttribute('aria-checked', 'true');
  });
});
