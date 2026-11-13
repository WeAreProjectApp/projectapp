import { test, expect } from '../helpers/test.js';
import { ADMIN_DOCUMENT_CHANGE_HISTORY } from '../helpers/flow-tags.js';
import { VIEWPORTS } from '../helpers/viewports.js';
import { historicalRevision, installDocumentHistory, openDocumentHistory } from '../helpers/document-history.js';

test.setTimeout(60_000);
const tags = (outcome) => [...ADMIN_DOCUMENT_CHANGE_HISTORY, '@role:admin', `@outcome:${outcome}`];
const consultLatest = (page) => page.getByTestId('history-entry-25').getByRole('button', { name: 'Consultar' }).click();

async function setTheme(page, theme) {
  const isDark = await page.locator('html').evaluate((element) => element.classList.contains('dark'));
  if ((theme === 'dark') !== isDark) await page.getByRole('button', { name: theme === 'dark' ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro' }).first().click();
}

for (const viewport of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  for (const theme of ['light', 'dark']) {
    test(`reads historical changes in ${theme} at ${viewport}`, { tag: [...tags('display'), `@viewport:${viewport}`] }, async ({ page }) => {
      await page.setViewportSize(VIEWPORTS[viewport]);
      await installDocumentHistory(page);
      await openDocumentHistory(page);
      await setTheme(page, theme);
      await consultLatest(page);
      const removed = page.locator('[data-history-change="removed"]');
      const added = page.locator('[data-history-change="added"]');
      await expect(removed).toContainText('− Eliminado');
      await expect(removed).toContainText('Contenido revisión 24');
      await expect(added).toContainText('+ Agregado');
      await expect(added).toContainText('Contenido revisión 25');
      await expect(page.getByTestId('history-comparison-heading')).toContainText('Comparación v24 → v25');
      await expect(page.getByTestId('history-version-detail')).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  }
}

test('compares revisions selected on different history pages', { tag: tags('success') }, async ({ page }) => {
  await installDocumentHistory(page);
  await openDocumentHistory(page);
  await page.getByRole('checkbox', { name: 'Seleccionar versión 25', exact: true }).check();
  await page.getByRole('navigation', { name: 'Paginación del historial' }).getByRole('button', { name: 'Página siguiente' }).click();
  await page.getByRole('checkbox', { name: 'Seleccionar versión 1', exact: true }).check();
  await page.getByTestId('history-compare').click();

  await expect(page.getByTestId('history-comparison-heading')).toContainText('Comparación v1 → v25');
  await expect(page.locator('[data-history-change="removed"]')).toContainText('Contenido revisión 1');
});

test('resets pagination when the dropdown changes the order', { tag: tags('success') }, async ({ page }) => {
  await installDocumentHistory(page);
  await openDocumentHistory(page);
  await page.getByRole('navigation', { name: 'Paginación del historial' }).getByRole('button', { name: 'Página siguiente' }).click();
  await page.getByTestId('history-order').click();
  await page.getByTestId('history-order-oldest').click();

  await expect(page.getByTestId('history-order')).toContainText('Más antiguo primero');
  await expect(page.getByTestId('history-entry-1')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Paginación del historial' })).toHaveCount(1);
  await expect(page.getByRole('navigation', { name: 'Paginación del historial' })).toContainText('1–20');
});

test('returns from the full reading to the selected comparison', { tag: tags('success') }, async ({ page }) => {
  await installDocumentHistory(page);
  await openDocumentHistory(page);
  await consultLatest(page);
  await page.getByTestId('history-full-version').click();
  await expect(page.getByTestId('history-full-content').getByRole('heading', { name: 'Alcance' })).toBeVisible();
  await page.getByTestId('history-full-version').click();

  await expect(page.getByTestId('history-comparison-heading')).toContainText('v24 → v25');
  await expect(page.locator('[data-history-change="removed"]')).toContainText('Contenido revisión 24');
});

test('retries a failed version consultation in its visible panel', { tag: tags('failure') }, async ({ page }) => {
  await installDocumentHistory(page, { fail: 'version' });
  await openDocumentHistory(page);
  await consultLatest(page);
  await expect(page.getByRole('alert')).toContainText('No se pudo completar la consulta');
  await page.getByRole('alert').getByRole('button', { name: 'Reintentar' }).click();

  await expect(page.getByTestId('history-comparison-heading')).toContainText('v24 → v25');
});

test('explains revisions without content differences', { tag: tags('display') }, async ({ page }) => {
  const source = '# Sin cambios\n\nMismo contenido';
  await installDocumentHistory(page, { overrides: { 24: historicalRevision(24, source), 25: historicalRevision(25, source) } });
  await openDocumentHistory(page);
  await consultLatest(page);

  await expect(page.getByTestId('history-no-changes')).toHaveText('No hay diferencias entre estas versiones.');
});

test('distinguishes an editorial formatting change', { tag: tags('success') }, async ({ page }) => {
  await installDocumentHistory(page, { overrides: { 24: historicalRevision(24, 'Acuerdo'), 25: historicalRevision(25, '**Acuerdo**') } });
  await openDocumentHistory(page);
  await consultLatest(page);

  await expect(page.getByTestId('history-rich-diff')).toContainText('Cambio de formato');
  await expect(page.locator('[data-history-change="added"] strong')).toHaveText('Acuerdo');
});

test('retains the final paragraph in a large historical document', { tag: tags('success') }, async ({ page }) => {
  const paragraphs = Array.from({ length: 600 }, (_, index) => `Párrafo histórico ${index}`).join('\n\n');
  await installDocumentHistory(page, { overrides: { 25: historicalRevision(25, `# Documento extenso\n\n${paragraphs}`) } });
  await openDocumentHistory(page);
  await consultLatest(page);
  await page.getByTestId('history-full-version').click();

  await expect(page.getByTestId('history-full-content')).toContainText('Párrafo histórico 599');
});
