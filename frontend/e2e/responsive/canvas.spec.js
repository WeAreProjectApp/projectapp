/** R-canvas-01: document forms must retain their editable fields and exit actions at every profile. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const createScenario = getResponsiveScenario('frontend/pages/panel/documents/create.vue');
const editScenario = getResponsiveScenario('frontend/pages/panel/documents/[id]/edit.vue');
// Complete editor fixture, adapted from admin-document-unsaved-guard: the
// canvas needs markdown, association and template fields to mount its preview.
const record = { id: 1, title: 'Contrato de Servicios', status: 'draft', content_markdown: '# Contrato\n\nEste es el contenido.', client: 7, client_display_name: 'Kore SAS', project: null, language: 'es', template_style: 'professional', client_name: 'ACME Corp', created_at: '2026-03-01T10:00:00Z' };

async function setupCanvas(page) {
  await setAuthLocalStorage(page, { token: 'canvas-token', userAuth: { id: 9001, role: 'admin', is_staff: true } });
  await mockApi(page, async ({ apiPath }) => {
    const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'documents/') return json([record]);
    if (apiPath === 'documents/1/detail/') return json(record);
    if (apiPath === 'document-folders/') return json([{ id: 3, name: 'Contratos', is_archived: false }]);
    if (apiPath === 'document-tags/' || apiPath === 'document-states/' || apiPath === 'document-state-groups/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath.startsWith('accounting/projects/')) return json({ results: [] });
    if (apiPath === 'proposals/client-profiles/status-counts/') return json({ all: 0, active: 0, orphans: 0, archived: 0 });
    if (apiPath === 'proposals/client-profiles/') return json([]);
    return null;
  });
}

test.describe('canvas responsive special', () => {
  test.describe('preview', () => {
    test.use(viewportUse('landscape'));
    test('editor toggles the markdown preview without losing its concrete heading', {
      tag: ['@flow:admin-document-edit', '@outcome:display', '@responsive-special:canvas', '@viewport:landscape', '@responsive-batch:canvas-special-1'],
    }, async ({ page }) => {
      await setupCanvas(page);
      // quality: allow-deep-link (the catalog edit scenario reaches this canvas from its row action)
      await page.goto('/en-us/panel/documents/1/edit', { waitUntil: 'domcontentloaded' });
      const markdown = page.getByRole('textbox', { name: 'Contenido Markdown' });
      await expect(markdown).toHaveValue(/Contrato/);
      // Regression: the responsive editor previously left the preview toggle
      // unreachable and the preview without rendered content.
      await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Contrato', level: 1, exact: true })).toHaveText('Contrato');
      await page.getByRole('tab', { name: 'Editar', exact: true }).click();
      await expect(markdown).toHaveValue(/Contrato/);
    });
  });

  test.describe('unsaved exit guard', () => {
    test.use(viewportUse('compact'));
    test('exit guard keeps an edited title when the user chooses to continue editing', {
      tag: ['@flow:admin-document-unsaved-guard', '@outcome:success', '@responsive-special:canvas', '@viewport:compact', '@responsive-batch:canvas-special-1'],
    }, async ({ page }) => {
      await setupCanvas(page);
      // quality: allow-deep-link (the special isolates the leave guard after the catalog covers editor entry)
      await page.goto('/en-us/panel/documents/1/edit', { waitUntil: 'domcontentloaded' });
      await page.getByRole('textbox', { name: /^T[ií]tulo\s*\*?$/i }).fill('Contrato Actualizado');
      await expect(page.getByTestId('doc-unsaved-notice')).toContainText('Título sin guardar');
      await page.getByRole('link', { name: /Volver a documentos/i }).click();
      await page.getByRole('button', { name: 'Seguir editando', exact: true }).click();
      await expect(page).toHaveURL(/\/panel\/documents\/1\/edit$/);
      await expect(page.getByRole('textbox', { name: /^T[ií]tulo\s*\*?$/i })).toHaveValue('Contrato Actualizado');
    });
  });
});

const canvasDocumentEntryByProfile = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Gestor Documental', exact: true }).click(); },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Gestor Documental', exact: true }).click(); },
  landscape: (page) => page.getByRole('link', { name: 'Gestor Documental', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Gestor Documental', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Gestor Documental', exact: true }).click(),
});

async function openDocuments(page, profile) {
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/en-us\/panel\/?$/);
  await canvasDocumentEntryByProfile[profile](page);
  await expect(page).toHaveURL(/\/panel\/documents(?:\?.*)?$/);
  await expect(page.getByRole('heading', { name: 'Gestor Documental', exact: true }))
    .toHaveText('Gestor Documental', { timeout: 35_000 });
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`canvas catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));
    test('create canvas preserves entered title before leaving the form', {
      tag: ['@flow:admin-document-create', '@outcome:display', '@responsive:canvas', `@responsive-scenario:${createScenario.catalogKey}`, `@responsive-batch:${batchForScenario(createScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setupCanvas(page);
      // quality: allow-deep-link (the authenticated panel home is the canonical shell entry; this test then reaches the canvas through the visible Documents navigation and create action)
      await openDocuments(page, profile);
      await page.getByRole('link', { name: /Nuevo Documento/i }).click();
      await page.getByLabel('Título *').fill('Documento responsive de prueba');
      await expect(page.getByTestId('doc-create-unsaved-notice')).toContainText('todavía no existe');
      await assertResponsiveScenario(page, testInfo, createScenario, { profile });
    });

    test('edit canvas opens through the document row action', {
      tag: ['@flow:admin-document-edit', '@outcome:display', '@responsive:canvas', `@responsive-scenario:${editScenario.catalogKey}`, `@responsive-batch:${batchForScenario(editScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setupCanvas(page);
      // quality: allow-deep-link (the authenticated panel home is the canonical shell entry; this test then reaches the editor through the visible Documents navigation and row action)
      await openDocuments(page, profile);
      const documentItem = page
        .getByTestId(/^document-(?:row|card)-1$/)
        .filter({ visible: true });
      const actions = documentItem.getByRole('button', { name: /^Acciones de Contrato de Servicios$/ });
      await actions.click();
      await page.getByRole('button', { name: /Editar contenido/i }).click();
      await expect(page).toHaveURL(/\/panel\/documents\/1\/edit(?:\?.*)?$/);
      await expect(page.getByRole('textbox', { name: /^T[ií]tulo\s*\*?$/i })).toHaveValue('Contrato de Servicios');
      await assertResponsiveScenario(page, testInfo, editScenario, { profile });
    });
  });
}
