/** Catches missing consulting value content, broken public controls, lost preferences, and failed recovery paths. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { consultingApiFixture, consultingProgramFixture } from '../helpers/consulting-fixture.js';
import {
  PUBLIC_CONSULTING_FAQ, PUBLIC_CONSULTING_GUIDE, PUBLIC_CONSULTING_LANGUAGE,
  PUBLIC_CONSULTING_LOAD, PUBLIC_CONSULTING_NEXT_STEP, PUBLIC_CONSULTING_OVERVIEW,
  PUBLIC_CONSULTING_PDF, PUBLIC_CONSULTING_SHARE, PUBLIC_CONSULTING_THEME,
} from '../helpers/flow-tags.js';

const program = consultingProgramFixture();
const englishProgram = consultingProgramFixture('en');
const jsonError = { status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Unavailable' }) };

async function setupApi(page, scenario = {}) {
  await page.addInitScript(({ showGuide, theme }) => {
    if (showGuide) localStorage.removeItem('projectapp-consulting-guide-seen');
    else localStorage.setItem('projectapp-consulting-guide-seen', 'true');
    if (theme) localStorage.setItem('projectapp-consulting-theme', theme);
  }, { showGuide: Boolean(scenario.showGuide), theme: scenario.theme });
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'consulting/public/' && scenario.programUnavailable) return jsonError;
    if (apiPath === 'consulting/public/pdf/' && scenario.pdfUnavailable) return jsonError;
    return consultingApiFixture({ apiPath, method, route });
  });
}

async function openFromFooter(page) {
  await page.goto('/es-co', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  const link = page.getByRole('link', { name: 'Consultoría y asesoría', exact: true }).first();
  await link.scrollIntoViewIfNeeded();
  await link.click();
  await page.waitForURL(/\/es-co\/consulting$/);
  await page.getByTestId('consulting-program').waitFor();
}

test.describe('Public consulting', () => {
  test.setTimeout(60_000);

  test('shows the five business areas, six impact paths, report, measurement and diagnostic after footer navigation', {
    tag: [...PUBLIC_CONSULTING_OVERVIEW, '@role:guest', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await expect(page.getByRole('heading', { level: 1, name: program.hero.title, exact: true })).toHaveText(program.hero.title);
    await expect(page.getByTestId('consulting-areas').locator('article')).toHaveCount(5);
    await expect(page.getByTestId('consulting-areas-economic')).toContainText('Económica');
    await expect(page.getByTestId('consulting-impact').locator('article')).toHaveCount(6);
    await expect(page.getByTestId('consulting-impact-costs')).toContainText('Costos que sobran');
    await expect(page.getByTestId('consulting-measurement-payback')).toContainText('Cuándo se recupera la inversión');
    await expect(page.getByTestId('consulting-deliverable-roadmap')).toContainText('Tiempo, dinero y siguiente paso');
    await expect(page.getByTestId('consulting-diagnostic-software')).toContainText('Después, cómo construir la solución');
  });

  test('switches the public presentation to English', {
    tag: [...PUBLIC_CONSULTING_LANGUAGE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('consulting-language-en').click();

    await expect(page).toHaveURL(/\/en-us\/consulting$/);
    await expect(page.getByRole('heading', { name: englishProgram.hero.title, exact: true })).toHaveText(englishProgram.hero.title);
    await expect(page.getByTestId('consulting-areas-economic')).toContainText('Economic');
  });

  test('expands and collapses the confidentiality answer', {
    tag: [...PUBLIC_CONSULTING_FAQ, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    const privacyIndex = program.faq.items.findIndex((item) => item.id === 'privacy');
    const trigger = page.getByTestId(`consulting-faq-trigger-${privacyIndex}`);
    const answer = page.getByTestId(`consulting-faq-panel-${privacyIndex}`);

    await trigger.click();
    await expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await expect(answer).toHaveText(program.faq.items[privacyIndex].answer);
    await trigger.click();
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
    await expect(answer).toBeHidden();
  });

  test('downloads the English PDF selected by the visitor', {
    tag: [...PUBLIC_CONSULTING_PDF, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    await page.getByTestId('consulting-language-en').click();
    const downloadPromise = page.waitForEvent('download');

    await page.getByTestId('consulting-download-pdf-floating').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('consulting-en.pdf');
    expect(await download.failure()).toBeNull();
  });

  test('keeps the public presentation readable after a PDF failure', {
    tag: [...PUBLIC_CONSULTING_PDF, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { pdfUnavailable: true });
    await openFromFooter(page);

    await page.getByTestId('consulting-download-pdf-floating').click();

    await expect(page.getByTestId('consulting-pdf-error')).toHaveText('No pudimos descargar el PDF. Vuelve a intentarlo.');
    await expect(page.getByRole('heading', { name: program.hero.title, exact: true })).toHaveText(program.hero.title);
  });

  test('recovers the program through retry after a public API failure', {
    tag: [...PUBLIC_CONSULTING_LOAD, '@role:guest', '@outcome:failure', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { programUnavailable: true };
    await setupApi(page, scenario);
    // quality: allow-deep-link (a recipient opens a shared consulting URL while the presentation API is unavailable).
    await page.goto('/es-co/consulting', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'No pudimos cargar la presentación de consultoría.', exact: true })).toHaveText('No pudimos cargar la presentación de consultoría.');
    scenario.programUnavailable = false;

    await page.getByTestId('consulting-retry').click();

    await expect(page.getByRole('heading', { name: program.hero.title, exact: true })).toHaveText(program.hero.title);
    await expect(page.getByTestId('consulting-retry')).toHaveCount(0);
  });

  test('walks the first-visit guide and restarts it after skipping', {
    tag: [...PUBLIC_CONSULTING_GUIDE, '@role:guest', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page, { showGuide: true });
    await openFromFooter(page);

    await expect(page.getByTestId('consulting-guide-progress')).toHaveText('1/7');
    await page.getByTestId('consulting-guide-next').click();
    await expect(page.getByTestId('consulting-guide-progress')).toHaveText('2/7');
    await page.getByRole('button', { name: 'Omitir', exact: true }).click();
    await expect(page.getByTestId('consulting-guide')).toHaveCount(0);
    await page.getByTestId('consulting-guide-restart').click();
    await expect(page.getByTestId('consulting-guide-progress')).toHaveText('1/7');
  });

  test('persists the selected dark theme after reload', {
    tag: [...PUBLIC_CONSULTING_THEME, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('consulting-theme-toggle').click();
    await expect(page.getByTestId('consulting-program')).toHaveAttribute('data-theme', 'dark');
    expect(await page.evaluate(() => localStorage.getItem('projectapp-consulting-theme'))).toBe('dark');
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('consulting-program')).toHaveAttribute('data-theme', 'dark');
    expect(await page.evaluate(() => localStorage.getItem('projectapp-consulting-theme'))).toBe('dark');
  });

  test('copies the current public URL from the share dialog', {
    tag: [...PUBLIC_CONSULTING_SHARE, '@role:guest', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await setupApi(page);
    await openFromFooter(page);

    await page.getByTestId('consulting-share').click();
    await page.getByTestId('consulting-copy-link').click();

    await expect(page.getByTestId('consulting-share-feedback')).toHaveText('Enlace copiado');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(page.url());
  });

  test('shows a selectable URL when browser clipboard access is rejected', {
    tag: [...PUBLIC_CONSULTING_SHARE, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page);
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('denied')) } });
    });
    await openFromFooter(page);

    await page.getByTestId('consulting-share').click();
    await page.getByTestId('consulting-copy-link').click();

    await expect(page.getByTestId('consulting-share-feedback')).toHaveText('No pudimos copiar el enlace. Selecciónalo y cópialo manualmente.');
    await expect(page.getByTestId('consulting-share-url')).toHaveText(page.url());
  });

  test('opens the quote request without sending a WhatsApp message', {
    tag: [...PUBLIC_CONSULTING_NEXT_STEP, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    const popupPromise = page.waitForEvent('popup');

    await page.getByTestId('consulting-whatsapp-cta').click();
    const popup = await popupPromise;

    await expect(page.getByTestId('consulting-whatsapp-cta')).toHaveAttribute('href', program.cta.whatsapp_url);
    const requestedUrl = new URL(program.cta.whatsapp_url);
    await expect.poll(() => new URL(popup.url()).origin).toBe('https://api.whatsapp.com');
    expect(new URL(popup.url()).searchParams.get('phone')).toBe(requestedUrl.pathname.slice(1));
    expect(new URL(popup.url()).searchParams.get('text')).toBe(requestedUrl.searchParams.get('text'));
    await popup.close();
  });

  test('navigates from implementation cards to a delivery cell and Building with Us', {
    tag: [...PUBLIC_CONSULTING_NEXT_STEP, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page);
    await openFromFooter(page);
    const cellsLink = page.getByTestId('consulting-implementation-cells').getByRole('link', { name: 'Conocer más: Horas de una célula', exact: true });

    await cellsLink.click();
    await expect(page).toHaveURL(/\/es-co\/building-on-demand$/);
    await page.goBack({ waitUntil: 'domcontentloaded' });
    const buildingLink = page.getByTestId('consulting-implementation-building-with-us').getByRole('link', { name: 'Conocer más: Building with Us', exact: true });
    await buildingLink.click();

    await expect(page).toHaveURL(/\/es-co\/building-with-us$/);
  });
});
