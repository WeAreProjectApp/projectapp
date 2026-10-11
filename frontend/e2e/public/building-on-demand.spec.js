/** Catches incorrect monthly terms, misleading bag estimates and broken public document controls. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import {
  buildingOnDemandApiFixture,
  buildingOnDemandProgramFixture,
  BUILDING_ON_DEMAND_GUIDE_SEEN_KEY,
} from '../helpers/building-on-demand-fixture.js';

const program = buildingOnDemandProgramFixture();
const englishProgram = buildingOnDemandProgramFixture('en');
const starter = program.tiers.items.find((tier) => tier.id === 'starter');
const business = program.tiers.items.find((tier) => tier.id === 'business');
const enterprise = program.tiers.items.find((tier) => tier.id === 'enterprise');
const smallChange = program.estimator.tasks.find((task) => task.id === 'small-change');
const component = program.estimator.tasks.find((task) => task.id === 'component');
const largeFeature = program.estimator.tasks.find((task) => task.id === 'large-feature');
const requirementsSession = program.estimator.tasks.find((task) => task.id === 'requirements-session');
const unusedHours = program.faq.items.find((item) => item.id === 'unused-hours');
const jsonError = { status: 503, contentType: 'application/json', body: JSON.stringify({ message: 'Unavailable' }) };
const prepaidTerms = [
  { id: 'quarterly', label: '3 meses', starter: '1.710.000', business: '3.780.000', enterprise: '8.160.000', businessTotal: '11.340.000' },
  { id: 'semiannual', label: '6 meses', starter: '1.620.000', business: '3.570.000', enterprise: '7.680.000', businessTotal: '21.420.000' },
  { id: 'nine-month', label: '9 meses', starter: '1.530.000', business: '3.360.000', enterprise: '7.200.000', businessTotal: '30.240.000' },
];

async function setupApi(page, scenario = {}) {
  await page.addInitScript(({ showGuide, guideSeenKey }) => {
    if (showGuide) localStorage.removeItem(guideSeenKey);
    else localStorage.setItem(guideSeenKey, 'true');
  }, { showGuide: Boolean(scenario.showGuide), guideSeenKey: BUILDING_ON_DEMAND_GUIDE_SEEN_KEY });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'building-on-demand/public/' && scenario.programUnavailable) return jsonError;
    if (apiPath === 'building-on-demand/public/pdf/' && scenario.pdfUnavailable) return jsonError;
    return buildingOnDemandApiFixture({ apiPath, method, route });
  });
}

async function openFromFooter(page) {
  await page.goto('/es-co', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  const link = page.getByRole('link', { name: 'Building on Demand', exact: true }).first();
  await link.scrollIntoViewIfNeeded();
  await link.click();
  await page.waitForURL(/\/es-co\/building-on-demand$/);
  await page.getByTestId('building-on-demand-program').waitFor();
}

test.describe('Public Building on Demand', () => {
  test.setTimeout(60_000);

  test('presents the subscription tiers reached from the footer', {
    tag: ['@flow:public-building-on-demand-overview', '@role:guest', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await expect(page.getByRole('heading', { level: 1, name: program.hero.title, exact: true })).toHaveText(program.hero.title);
    await expect(page.getByTestId('building-on-demand-cell')).toContainText(program.cell.summary);
    await expect(page.getByTestId('building-on-demand-tier-starter').getByRole('heading', { name: starter.name, exact: true })).toHaveText(starter.name);
    await expect(page.getByTestId('building-on-demand-tier-starter')).toContainText('96 horas al mes');
    await expect(page.getByTestId('building-on-demand-tier-business').getByRole('heading', { name: business.name, exact: true })).toHaveText(business.name);
    await expect(page.getByTestId('building-on-demand-tier-business')).toContainText('192 horas al mes');
    await expect(page.getByTestId('building-on-demand-tier-business')).toContainText(business.badge);
    await expect(page.getByTestId('building-on-demand-tier-business')).toHaveAttribute('data-recommended', 'true');
    await expect(page.getByTestId('building-on-demand-tier-enterprise').getByRole('heading', { name: enterprise.name, exact: true })).toHaveText(enterprise.name);
    await expect(page.getByTestId('building-on-demand-tier-enterprise')).toContainText('288 horas al mes');
  });

  test('quotes the public subscription by month', {
    tag: ['@flow:public-building-on-demand-overview', '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await expect(page.getByTestId('building-on-demand-price-starter')).toContainText(/1\.800\.000 COP\s*\/ mes\s*\+ IVA/);
    await expect(page.getByTestId('building-on-demand-price-business')).toContainText(/4\.200\.000 COP\s*\/ mes\s*\+ IVA/);
    await expect(page.getByTestId('building-on-demand-price-enterprise')).toContainText(/9\.600\.000 COP\s*\/ mes\s*\+ IVA/);
    await expect(page.getByTestId('building-on-demand-public-page')).not.toContainText(/\b(?:precio|tarifa|costo|price|rate|cost)\s+(?:por\s+hora|per\s+hour)\b|\b(?:COP|USD)\s*\/\s*(?:h|hora|hour)\b|[$€]\s*[\d.,]+\s*\/\s*(?:h|hora|hour)\b|\bhourly\s+(?:price|rate)\b/i);
  });

  for (const term of prepaidTerms) {
    test(`applies the ${term.label} prepaid term`, {
      tag: ['@flow:public-building-on-demand-terms', '@role:guest', '@outcome:success'],
    }, async ({ page }) => {
      await setupApi(page);
      await openFromFooter(page);
      await expect(page.getByTestId('building-on-demand-price-business')).toContainText('4.200.000');

      await page.getByTestId('building-on-demand-terms').getByRole('tab', { name: term.label, exact: true }).click();

      await expect(page.getByTestId(`building-on-demand-term-${term.id}`)).toHaveAttribute('aria-selected', 'true');
      await expect(page.getByTestId('building-on-demand-price-starter')).toContainText(term.starter);
      await expect(page.getByTestId('building-on-demand-price-business')).toContainText(term.business);
      await expect(page.getByTestId('building-on-demand-price-enterprise')).toContainText(term.enterprise);
      await expect(page.getByTestId('building-on-demand-total-business')).toContainText(term.businessTotal);
      await expect(page.getByTestId('building-on-demand-terms')).toContainText(program.terms.note);
      await expect(page.getByTestId('building-on-demand-tier-business')).toContainText('192 horas al mes');
    });
  }

  test('asks for task selection before estimating a request', {
    tag: ['@flow:public-building-on-demand-estimator', '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByRole('link', { name: program.estimator.title, exact: true }).click();

    await expect(page.getByTestId('building-on-demand-estimator')).toContainText('Elige las tareas que tienes en mente para saber cómo encajan en tu bolsa.');
    await expect(page.getByTestId('building-on-demand-estimator')).toContainText(smallChange.hint);
    await expect(page.getByTestId('building-on-demand-estimator')).toContainText(program.estimator.disclaimer);
    await expect(page.getByTestId('building-on-demand-task-small-change-quantity')).toHaveText('0');
    await expect(page.getByTestId('building-on-demand-estimate-whatsapp')).toHaveCount(0);
  });

  test('compares the request with each monthly bag', {
    tag: ['@flow:public-building-on-demand-estimator', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    const increase = page.getByRole('button', { name: `Añadir una unidad de ${largeFeature.label}`, exact: true });

    await increase.click();
    await increase.click();
    await increase.click();

    await expect(page.getByTestId('building-on-demand-task-large-feature-quantity')).toHaveText('3');
    await expect(page.getByTestId('building-on-demand-estimate-range')).toHaveText('Tu pedido: entre 165 y 270 horas');
    await expect(page.getByTestId('building-on-demand-estimate-tier-starter')).toContainText('No cabe en un mes');
    await expect(page.getByTestId('building-on-demand-estimate-tier-starter')).toContainText('≈ 3 meses');
    await expect(page.getByTestId('building-on-demand-estimate-tier-business')).toContainText('Puede caber');
    await expect(page.getByTestId('building-on-demand-estimate-tier-enterprise').getByText('Cabe', { exact: true })).toBeVisible();
    await expect(page.getByTestId('building-on-demand-estimate-suggested')).toContainText('Enterprise');
    await expect(page.getByTestId('building-on-demand-estimate-suggested')).toContainText('Por el tiempo estimado de tu solicitud.');
  });

  test('links the estimate request to its WhatsApp summary', {
    tag: ['@flow:public-building-on-demand-estimator', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByRole('textbox', { name: program.estimator.description_label, exact: true }).fill(program.estimator.description_placeholder);
    await page.getByRole('button', { name: `Añadir una unidad de ${smallChange.label}`, exact: true }).click();
    await page.getByRole('button', { name: `Añadir una unidad de ${smallChange.label}`, exact: true }).click();
    await page.getByRole('button', { name: `Añadir una unidad de ${component.label}`, exact: true }).click();

    await expect(page.getByTestId('building-on-demand-estimate-range')).toHaveText('Tu pedido: entre 11 y 34 horas');
    const link = page.getByRole('link', { name: 'Pedir la estimación formal', exact: true });
    await expect(link).toHaveAttribute('href', /^https:\/\/wa\.me\//);
    const destination = new URL(await link.getAttribute('href'));
    expect(destination.pathname).toBe(new URL(program.contact.whatsapp_base_url).pathname);
    expect(destination.searchParams.get('text')).toBe([
      'Pedir la estimación formal — Building on Demand',
      program.estimator.description_placeholder,
      `2 × ${smallChange.label}`,
      `1 × ${component.label}`,
      'Tu pedido: entre 11 y 34 horas',
      'Nivel sugerido: Starter',
    ].join('\n'));
  });

  test('raises the suggestion for a role-gated task', {
    tag: ['@flow:public-building-on-demand-estimator', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    await page.getByRole('button', { name: `Añadir una unidad de ${smallChange.label}`, exact: true }).click();
    await expect(page.getByTestId('building-on-demand-estimate-suggested')).toContainText('Starter');

    await page.getByRole('button', { name: `Añadir una unidad de ${requirementsSession.label}`, exact: true }).click();

    await expect(page.getByTestId('building-on-demand-estimate-range')).toHaveText('Tu pedido: entre 9 y 27 horas');
    await expect(page.getByTestId('building-on-demand-estimate-tier-starter')).toContainText('Requiere los roles de Business o un nivel superior.');
    await expect(page.getByTestId('building-on-demand-estimate-suggested')).toContainText('Business');
    await expect(page.getByTestId('building-on-demand-estimate-suggested')).toContainText('Por los roles que necesita tu solicitud.');
  });

  test('recovers the program with the retry control', {
    tag: ['@flow:public-building-on-demand-load', '@role:guest', '@outcome:failure', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { programUnavailable: true };
    await setupApi(page, scenario);
    // quality: allow-deep-link (a recipient opens a shared program URL while its live API is unavailable)
    await page.goto('/es-co/building-on-demand', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'No pudimos cargar Building on Demand.', exact: true })).toHaveText('No pudimos cargar Building on Demand.');
    scenario.programUnavailable = false;

    await page.getByRole('button', { name: 'Reintentar', exact: true }).click();

    await expect(page.getByRole('heading', { name: program.hero.title, exact: true })).toHaveText(program.hero.title);
    await expect(page.getByTestId('building-on-demand-tier-business')).toContainText(business.ideal_for);
    await expect(page.getByTestId('building-on-demand-retry')).toHaveCount(0);
  });

  test('retains the selected dark theme after reload', {
    tag: ['@flow:public-building-on-demand-theme', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByRole('button', { name: 'Cambiar tema', exact: true }).click();
    await expect(page.getByTestId('building-on-demand-program')).toHaveAttribute('data-theme', 'dark');
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('building-on-demand-program')).toHaveAttribute('data-theme', 'dark');
    await expect(page.getByRole('button', { name: 'Cambiar tema', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('heading', { name: program.hero.title, exact: true })).toHaveText(program.hero.title);
  });

  test('introduces the program on the first visit', {
    tag: ['@flow:public-building-on-demand-guide', '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page, { showGuide: true });
    await openFromFooter(page);
    await expect(page.getByTestId('building-on-demand-guide')).toContainText('Tu producto, con una célula detrás');
    await expect(page.getByTestId('building-on-demand-guide-progress')).toHaveText('1/9');

    await page.getByRole('button', { name: 'Siguiente', exact: true }).click();

    await expect(page.getByTestId('building-on-demand-guide-progress')).toHaveText('2/9');
    await expect(page.getByTestId('building-on-demand-guide')).toContainText('Siete personas, una célula');
    await expect(page.getByTestId('building-on-demand-cell')).toContainText(program.cell.summary);
  });

  test('restarts the guide from its floating button', {
    tag: ['@flow:public-building-on-demand-guide', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    await expect(page.getByTestId('building-on-demand-guide')).toHaveCount(0);

    await page.getByRole('button', { name: 'Repetir la guía', exact: true }).click();

    await expect(page.getByTestId('building-on-demand-guide')).toContainText('Tu producto, con una célula detrás');
    await expect(page.getByTestId('building-on-demand-guide-progress')).toHaveText('1/9');
    await page.getByRole('button', { name: 'Omitir', exact: true }).click();
    await expect(page.getByTestId('building-on-demand-guide')).toHaveCount(0);
  });

  test('downloads the localized program PDF', {
    tag: ['@flow:public-building-on-demand-pdf', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Descargar PDF', exact: true }).click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('building-on-demand-es.pdf');
    expect(await download.failure()).toBeNull();
  });

  test('keeps the program readable after a PDF failure', {
    tag: ['@flow:public-building-on-demand-pdf', '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { pdfUnavailable: true });
    await openFromFooter(page);

    await page.getByRole('button', { name: 'Descargar PDF', exact: true }).click();

    await expect(page.getByTestId('building-on-demand-pdf-error')).toHaveText('No pudimos descargar el PDF. Vuelve a intentarlo.');
    await expect(page.getByRole('heading', { name: program.hero.title, exact: true })).toHaveText(program.hero.title);
    await expect(page.getByTestId('building-on-demand-price-business')).toContainText('4.200.000');
  });

  test('copies the current public URL from the share dialog', {
    tag: ['@flow:public-building-on-demand-share', '@role:guest', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await setupApi(page);
    await openFromFooter(page);

    await page.getByRole('button', { name: 'Compartir Building on Demand', exact: true }).click();
    await page.getByRole('button', { name: 'Copiar enlace', exact: true }).click();

    await expect(page.getByRole('dialog', { name: 'Compartir Building on Demand', exact: true })).toContainText('Comparte este enlace para explorar cómo hacer evolucionar tu producto.');
    await expect(page.getByTestId('building-on-demand-share-feedback')).toHaveText('Enlace copiado');
    await expect(page.getByTestId('building-on-demand-share-url')).toHaveText(page.url());
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(page.url());
  });

  test('reports a rejected clipboard write in the share dialog', {
    tag: ['@flow:public-building-on-demand-share', '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page);
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('denied')) } });
    });
    await openFromFooter(page);

    await page.getByRole('button', { name: 'Compartir Building on Demand', exact: true }).click();
    await page.getByRole('button', { name: 'Copiar enlace', exact: true }).click();

    await expect(page.getByTestId('building-on-demand-share-feedback')).toHaveText('No pudimos copiar el enlace. Selecciónalo y cópialo manualmente.');
    await expect(page.getByTestId('building-on-demand-share-url')).toHaveText(page.url());
  });

  test('switches the public program to English', {
    tag: ['@flow:public-building-on-demand-language', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('building-on-demand-language').getByRole('tab', { name: 'English', exact: true }).click();

    await expect(page).toHaveURL(/\/en-us\/building-on-demand$/);
    await expect(page.getByRole('heading', { name: englishProgram.hero.title, exact: true })).toHaveText(englishProgram.hero.title);
    await expect(page.getByTestId('building-on-demand-cell')).toContainText(englishProgram.cell.summary);
    await expect(page.getByTestId('building-on-demand-tier-business')).toContainText('192 hours per month');
    await expect(page.getByRole('button', { name: 'Download PDF', exact: true })).toBeVisible();
  });

  test('expands the answer about unused monthly hours', {
    tag: ['@flow:public-building-on-demand-faq', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByRole('button', { name: `Expandir: ${unusedHours.question}`, exact: true }).click();

    await expect(page.getByTestId('building-on-demand-faq-trigger-unused-hours')).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByTestId('building-on-demand-faq-panel-unused-hours')).toBeVisible();
    await expect(page.getByTestId('building-on-demand-faq-panel-unused-hours')).toHaveText(unusedHours.answer);
  });

  test('collapses a previously expanded FAQ answer', {
    tag: ['@flow:public-building-on-demand-faq', '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    await page.getByRole('button', { name: `Expandir: ${unusedHours.question}`, exact: true }).click();
    await expect(page.getByTestId('building-on-demand-faq-panel-unused-hours')).toHaveText(unusedHours.answer);

    await page.getByRole('button', { name: `Contraer: ${unusedHours.question}`, exact: true }).click();

    await expect(page.getByTestId('building-on-demand-faq-panel-unused-hours')).toBeHidden();
    await expect(page.getByRole('button', { name: `Expandir: ${unusedHours.question}`, exact: true })).toHaveAttribute('aria-expanded', 'false');
  });
});
