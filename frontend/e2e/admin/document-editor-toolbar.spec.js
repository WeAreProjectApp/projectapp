// qa: draft-unvalidated (2026-11-06 — app not running)
/**
 * PA-211 visual document-toolbar coverage.
 *
 * These tests exercise editor commands through the same staff document forms
 * used in the panel. Network captures establish the browser payload only;
 * persistence is covered by the backend/API suite.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_CREATE, ADMIN_DOCUMENT_EDIT } from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'staff-editor', is_staff: true } }),
};

const documentFixture = {
  id: 211,
  title: 'Guía editorial PA-211',
  status: 'draft',
  content_markdown: 'Texto enlazable',
  text_formats: { '/content_markdown': 'markdown_html_v1' },
  created_at: '2026-11-06T10:00:00Z',
};

async function mockEditorApi(page, state, options = {}) {
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `documents/${state.document.id}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(state.document) };
    }
    if (apiPath === `documents/${state.document.id}/update/` && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      options.onUpdate?.(payload);
      if (options.updateStatus) {
        return {
          status: options.updateStatus,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'No se pudo guardar el documento.' }),
        };
      }
      state.document = { ...state.document, ...payload };
      return { status: 200, contentType: 'application/json', body: JSON.stringify(state.document) };
    }
    if (
      apiPath === `documents/${state.document.id}/communications/`
      || apiPath === `documents/${state.document.id}/email-usage/`
    ) return { status: 200, contentType: 'application/json', body: JSON.stringify({ count: 0, results: [] }) };
    if (
      apiPath === 'document-folders/'
      || apiPath === 'document-tags/'
      || apiPath === 'document-states/'
      || apiPath === 'document-state-groups/'
      || apiPath === 'accounting/projects/'
    ) return { status: 200, contentType: 'application/json', body: '[]' };
    if (apiPath.startsWith('accounts/saved-filter-tabs')) {
      return { status: 200, contentType: 'application/json', body: '[]' };
    }
    return null;
  });
}

function editor(page) {
  return page.getByTestId('doc-markdown-editor');
}

async function openEdit(page, state, options) {
  await mockEditorApi(page, state, options);
  await page.goto(`/es-co/panel/documents/${state.document.id}/edit`, { waitUntil: 'domcontentloaded' });
}

async function openSource(page) {
  const documentEditor = editor(page);
  await documentEditor.getByRole('tab', { name: 'Fuente', exact: true }).click();
  return documentEditor.getByTestId('rich-text-source-input');
}

async function writeSource(page, value) {
  const source = await openSource(page);
  await source.fill(value);
  return source;
}

async function enterVisualMode(page) {
  const documentEditor = editor(page);
  await documentEditor.getByRole('tab', { name: 'Visual', exact: true }).click();
  return documentEditor.getByTestId('rich-text-visual-input');
}

async function selectAllVisualText(page) {
  const visual = await enterVisualMode(page);
  await visual.click();
  await visual.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
  return visual;
}

async function openInsertMenu(page) {
  await editor(page).getByTestId('document-insert-menu').click();
}

async function expectNoGlobalOverflow(page) {
  const overflow = await page.evaluate(() => Math.max(
    document.documentElement.scrollWidth,
    document.body.scrollWidth,
  ) - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe('Document visual toolbar', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'pa211-staff-token',
      userAuth: { id: 211, role: 'admin', is_staff: true },
    });
  });

  // Bug caught: applying a link could drop the selected text or lose its URL after reload.
  test('keeps a staff hyperlink after reload', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    let savedPayload = null;
    await openEdit(page, state, { onUpdate: (payload) => { savedPayload = payload; } });

    await selectAllVisualText(page);
    await editor(page).getByRole('button', { name: 'Enlace', exact: true }).click();
    await page.getByLabel('Dirección del enlace', { exact: true }).fill('https://projectapp.co');
    await page.getByRole('button', { name: 'Aplicar', exact: true }).click();

    const source = await openSource(page);
    await expect(source).toHaveValue(/https:\/\/projectapp\.co/);

    const requestPromise = page.waitForRequest((request) => (
      request.url().includes(`/api/documents/${state.document.id}/update/`) && request.method() === 'PATCH'
    ));
    await page.getByTestId('doc-save').click();
    const requestPayload = (await requestPromise).postDataJSON();
    expect(requestPayload.text_formats).toMatchObject({ '/content_markdown': 'markdown_html_v1' });
    expect(requestPayload.content_markdown).toContain('https://projectapp.co');
    expect(savedPayload.content_markdown).toContain('https://projectapp.co');

    await page.reload({ waitUntil: 'domcontentloaded' });
    const reloadedSource = await openSource(page);
    await expect(reloadedSource).toHaveValue(/https:\/\/projectapp\.co/);
  });

  // Bug caught: visual insertions could disappear or render as literal source in preview.
  test('renders an inserted index in preview', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    await mockEditorApi(page, state);
    await page.goto('/es-co/panel/documents/create', { waitUntil: 'domcontentloaded' });

    await writeSource(page, '# Alcance editorial\n\nRevisar antes de publicar.');
    const visual = await enterVisualMode(page);
    await visual.press('End');
    await openInsertMenu(page);
    await page.getByRole('menuitem', { name: 'Índice', exact: true }).click();
    await visual.getByText('Revisar antes de publicar.', { exact: true }).click();
    await openInsertMenu(page);
    await page.getByRole('menuitem', { name: 'Aviso', exact: true }).click();

    const source = await openSource(page);
    await expect(source).toHaveValue(/# Alcance editorial/);
    await expect(source).toHaveValue(/\[TOC\]/);
    await expect(source).toHaveValue(/\[!WARNING\]/);

    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
    const preview = page.getByTestId('doc-markdown-preview-pane');
    await expect(preview.getByRole('heading', { name: 'Alcance editorial', level: 1 })).toHaveText('Alcance editorial');
    await expect(preview.getByRole('link', { name: 'Alcance editorial', exact: true })).toHaveAttribute('href', /#document-.*-heading-1/);
    await expect(preview.getByText('Aviso', { exact: true })).toHaveText('Aviso');
    await expect(preview.getByText('Revisar antes de publicar.', { exact: true })).toHaveText('Revisar antes de publicar.');
  });

  // Bug caught: a rejected URL could discard the visual draft before the editor allows repair.
  test('keeps the visual draft recoverable after an invalid link', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    await openEdit(page, state);

    await selectAllVisualText(page);
    await editor(page).getByRole('button', { name: 'Enlace', exact: true }).click();
    const address = page.getByLabel('Dirección del enlace', { exact: true });
    await address.fill('javascript:alert(211)');
    await page.getByRole('button', { name: 'Aplicar', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveText('Introduce una dirección compatible: https, http, correo, teléfono o una ruta relativa.');

    await address.fill('https://projectapp.co/recuperado');
    await page.getByRole('button', { name: 'Aplicar', exact: true }).click();
    const source = await openSource(page);
    await expect(source).toHaveValue(/Texto enlazable/);
    await expect(source).toHaveValue(/https:\/\/projectapp\.co\/recuperado/);
  });

  // Bug caught: the contextual table controls could stop mutating the selected table.
  test('adds a row through the contextual table controls', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    await openEdit(page, state);

    const visual = await selectAllVisualText(page);
    await visual.press('End');
    await openInsertMenu(page);
    await page.getByRole('menuitem', { name: 'Insertar tabla', exact: true }).click();
    const toolbar = editor(page).getByRole('group', { name: 'Editar tabla', exact: true });
    await expect(toolbar.getByRole('button', { name: 'Añadir fila', exact: true })).toHaveText('Añadir fila');
    await toolbar.getByRole('button', { name: 'Añadir fila', exact: true }).click();
    await expect(editor(page).getByRole('row')).toHaveCount(4);
  });

  // Bug caught: a failed save could clear the enhanced Markdown source that the staff member must correct.
  test('retains enhanced source after a save failure', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    await openEdit(page, state, { updateStatus: 500 });

    const source = await writeSource(page, '# Recuperar borrador\n\n[TOC]');
    const responsePromise = page.waitForResponse((response) => (
      response.url().includes(`/api/documents/${state.document.id}/update/`) && response.status() === 500
    ));
    await page.getByTestId('doc-save').click();
    await responsePromise;
    await expect(source).toHaveValue('# Recuperar borrador\n\n[TOC]');
  });
});

const responsiveProfiles = ['compact', 'portrait', 'landscape', 'desktop', 'wide'];
for (const profile of responsiveProfiles) {
  test.describe(`Document visual toolbar at ${profile}`, () => {
    test.use(viewportUse(profile));
    test.setTimeout(60_000);

    // Bug caught: the insert action could push the document editor beyond the viewport on this profile.
    test(`keeps the insert action within the ${profile} viewport`, {
      tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success', `@viewport:${profile}`],
    }, async ({ page }) => {
      const state = { document: { ...documentFixture } };
      await openEdit(page, state);

      const visual = await selectAllVisualText(page);
      await visual.press('End');
      await openInsertMenu(page);
      await expectNoGlobalOverflow(page);
      await page.getByRole('menuitem', { name: 'Separador', exact: true }).click();
      const source = await openSource(page);
      await expect(source).toHaveValue(/---/);
    });
  });
}
