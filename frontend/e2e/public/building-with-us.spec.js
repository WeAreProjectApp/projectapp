/** Catches missing program content, broken public controls, lost preferences and unrecoverable API failures. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { buildingWithUsApiFixture, buildingWithUsProgramFixture } from '../helpers/building-with-us-fixture.js';
import {
  PUBLIC_BUILDING_WITH_US_OVERVIEW, PUBLIC_BUILDING_WITH_US_LANGUAGE,
  PUBLIC_BUILDING_WITH_US_LOAD, PUBLIC_BUILDING_WITH_US_FAQ,
  PUBLIC_BUILDING_WITH_US_PDF, PUBLIC_BUILDING_WITH_US_SHARE,
  PUBLIC_BUILDING_WITH_US_GUIDE, PUBLIC_BUILDING_WITH_US_THEME,
} from '../helpers/flow-tags.js';

const program = buildingWithUsProgramFixture();
const englishProgram = buildingWithUsProgramFixture('en');
const jsonError = { status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Unavailable' }) };

async function setupApi(page, scenario = {}) {
  await page.addInitScript(({ showGuide, theme }) => {
    if (showGuide) localStorage.removeItem('projectapp-building-with-us-guide-seen');
    else localStorage.setItem('projectapp-building-with-us-guide-seen', 'true');
    if (theme) localStorage.setItem('projectapp-building-with-us-theme', theme);
  }, { showGuide: Boolean(scenario.showGuide), theme: scenario.theme });
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'building-with-us/public/' && scenario.programUnavailable) return jsonError;
    if (apiPath === 'building-with-us/public/pdf/' && scenario.pdfUnavailable) return jsonError;
    return buildingWithUsApiFixture({ apiPath, method, route });
  });
}

async function openFromFooter(page) {
  await page.goto('/es-co', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  const link = page.getByRole('link', { name: 'Building with Us', exact: true }).first();
  await link.scrollIntoViewIfNeeded();
  await link.click();
  await page.waitForURL(/\/es-co\/building-with-us$/);
  await page.getByTestId('building-with-us-program').waitFor();
}

test.describe('Public Building with Us', () => {
  test.setTimeout(60_000);

  test('presents the program reached from the footer', {
    tag: [...PUBLIC_BUILDING_WITH_US_OVERVIEW, '@role:guest', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await expect(page.getByRole('heading', { level: 1, exact: true, name: program.hero.title })).toHaveText(program.hero.title);
    await expect(page.getByTestId('building-with-us-industries')).toContainText(/Logística[\s\S]*Salud[\s\S]*Educación/);
    await expect(page.getByTestId('building-with-us-model-monthly-investment').getByRole('list')).toContainText([
      /Experiencia de negocio[\s\S]*Inversión mensual acordada/,
      /Diseño y desarrollo[\s\S]*Infraestructura y operación/,
    ]);
    await expect(page.getByTestId('building-with-us-period-0')).toContainText(program.incubation_periods.items[0].title);
    await expect(page.getByTestId('building-with-us-whatsapp-cta')).toHaveAttribute('href', program.cta.whatsapp_url);
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toHaveCount(0);
    await expect(page.locator('video')).toHaveCount(0);
  });

  test('jumps to the chosen participation model', {
    tag: [...PUBLIC_BUILDING_WITH_US_OVERVIEW, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByRole('navigation', { name: 'Modelos de participación' }).getByRole('link', { name: program.participation_models.items[1].name, exact: true }).click();

    await expect(page).toHaveURL(/#building-with-us-model-shared-investment$/);
    await expect(page.getByTestId('building-with-us-model-shared-investment')).toContainText(program.participation_models.items[1].summary);
  });

  test('switches the public program to English', {
    tag: [...PUBLIC_BUILDING_WITH_US_LANGUAGE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('building-with-us-language-en').click();

    await expect(page).toHaveURL(/\/en-us\/building-with-us$/);
    await expect(page.getByRole('heading', { name: englishProgram.hero.title, exact: true })).toHaveText(englishProgram.hero.title);
    await expect(page.getByTestId('building-with-us-industries')).toContainText('Healthcare');
  });

  test('expands the answer about earned participation', {
    tag: [...PUBLIC_BUILDING_WITH_US_FAQ, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('building-with-us-faq-trigger-0').click();

    await expect(page.getByTestId('building-with-us-faq-trigger-0')).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByTestId('building-with-us-faq-panel-0')).toHaveText(program.faq.items[0].answer);
  });

  test('copies the current public URL from the share dialog', {
    tag: [...PUBLIC_BUILDING_WITH_US_SHARE, '@role:guest', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('building-with-us-share').click();
    await page.getByTestId('building-with-us-copy-link').click();

    await expect(page.getByTestId('building-with-us-share-feedback')).toHaveText('Enlace copiado');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(page.url());
  });

  test('reports a rejected clipboard write in the share dialog', {
    tag: [...PUBLIC_BUILDING_WITH_US_SHARE, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page);
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('denied')) } });
    });
    await openFromFooter(page);

    await page.getByTestId('building-with-us-share').click();
    await page.getByTestId('building-with-us-copy-link').click();

    await expect(page.getByTestId('building-with-us-share-feedback')).toHaveText('No pudimos copiar el enlace. Selecciónalo y cópialo manualmente.');
    await expect(page.getByTestId('building-with-us-share-url')).toHaveText(page.url());
  });

  test('downloads the localized program PDF', {
    tag: [...PUBLIC_BUILDING_WITH_US_PDF, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    const downloadPromise = page.waitForEvent('download');
    await page.getByTestId('building-with-us-download-pdf').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('building-with-us-es.pdf');
    expect(await download.failure()).toBeNull();
  });

  test('keeps the program readable after a PDF failure', {
    tag: [...PUBLIC_BUILDING_WITH_US_PDF, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { pdfUnavailable: true });
    await openFromFooter(page);

    await page.getByTestId('building-with-us-download-pdf').click();

    await expect(page.getByTestId('building-with-us-pdf-error')).toHaveText('No pudimos descargar el PDF. Vuelve a intentarlo.');
    await expect(page.getByRole('heading', { name: program.hero.title, exact: true })).toHaveText(program.hero.title);
  });

  test('recovers the program with the retry control', {
    tag: [...PUBLIC_BUILDING_WITH_US_LOAD, '@role:guest', '@outcome:failure', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { programUnavailable: true };
    await setupApi(page, scenario);
    // quality: allow-deep-link (a recipient opens a shared program URL while its API is unavailable)
    await page.goto('/es-co/building-with-us', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'No pudimos cargar Building with Us.', exact: true })).toHaveText('No pudimos cargar Building with Us.');
    scenario.programUnavailable = false;

    await page.getByTestId('building-with-us-retry').click();

    await expect(page.getByRole('heading', { name: program.hero.title, exact: true })).toHaveText(program.hero.title);
    await expect(page.getByTestId('building-with-us-retry')).toHaveCount(0);
  });

  test('introduces the program on the first visit', {
    tag: [...PUBLIC_BUILDING_WITH_US_GUIDE, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page, { showGuide: true });
    await openFromFooter(page);

    await expect(page.getByTestId('building-with-us-guide')).toContainText('Una alianza para construir');
    await expect(page.getByTestId('building-with-us-guide-progress')).toHaveText('1/9');
    await page.getByTestId('building-with-us-guide-next').click();
    await expect(page.getByTestId('building-with-us-guide-progress')).toHaveText('2/9');
  });

  test('restarts the guide from its floating button', {
    tag: [...PUBLIC_BUILDING_WITH_US_GUIDE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    await expect(page.getByTestId('building-with-us-guide')).toHaveCount(0);

    await page.getByTestId('building-with-us-guide-restart').click();

    await expect(page.getByTestId('building-with-us-guide-progress')).toHaveText('1/9');
    await page.getByRole('button', { name: 'Omitir', exact: true }).click();
    await expect(page.getByTestId('building-with-us-guide')).toHaveCount(0);
  });

  test('retains the selected dark theme after reload', {
    tag: [...PUBLIC_BUILDING_WITH_US_THEME, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('building-with-us-theme-toggle').click();
    await expect(page.getByTestId('building-with-us-program')).toHaveAttribute('data-theme', 'dark');
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('building-with-us-program')).toHaveAttribute('data-theme', 'dark');
    await expect(page.getByTestId('building-with-us-theme-toggle')).toHaveAttribute('aria-pressed', 'true');
  });

  test('preserves the saved theme while retrying a failed load', {
    tag: [...PUBLIC_BUILDING_WITH_US_THEME, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = { programUnavailable: true, theme: 'dark' };
    await setupApi(page, scenario);
    // quality: allow-deep-link (a saved public URL must retain its local theme even when the live program cannot load)
    await page.goto('/es-co/building-with-us', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'No pudimos cargar Building with Us.', exact: true })).toHaveText('No pudimos cargar Building with Us.');
    await expect(page.getByTestId('building-with-us-public-page')).toHaveAttribute('data-theme', 'dark');
    scenario.programUnavailable = false;

    await page.getByTestId('building-with-us-retry').click();

    await expect(page.getByTestId('building-with-us-program')).toHaveAttribute('data-theme', 'dark');
    await expect(page.getByTestId('building-with-us-theme-toggle')).toHaveAttribute('aria-pressed', 'true');
  });
});
