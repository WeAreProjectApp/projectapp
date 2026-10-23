/**
 * Editorial document editor regression coverage.
 *
 * Catches a visual toolbar change being lost while switching to source mode,
 * saving, reloading, or continuing the same document edit.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_CREATE, ADMIN_DOCUMENT_EDIT } from '../helpers/flow-tags.js';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'editor', is_staff: true } }),
};

const documentBase = {
  id: 91,
  title: 'Alcance editorial',
  status: 'draft',
  content_markdown: 'Texto inicial',
  text_formats: { '/content_markdown': 'markdown_html_v1' },
  created_at: '2026-10-23T10:00:00Z',
};

async function mockDocumentEditorApi(page, state, onCreate = null) {
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `documents/${state.document.id}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(state.document) };
    }
    if (apiPath === `documents/${state.document.id}/update/` && method === 'PATCH') {
      state.document = { ...state.document, ...route.request().postDataJSON() };
      return { status: 200, contentType: 'application/json', body: JSON.stringify(state.document) };
    }
    if (
      apiPath === `documents/${state.document.id}/communications/`
      || apiPath === `documents/${state.document.id}/email-usage/`
    ) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify({ count: 0, results: [] }) };
    }
    if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      onCreate?.(payload);
      state.document = {
        ...state.document,
        id: 92,
        title: payload.title,
        content_markdown: payload.markdown,
        text_formats: payload.text_formats,
      };
      return { status: 201, contentType: 'application/json', body: JSON.stringify(state.document) };
    }
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

function documentEditor(page) {
  return page.getByTestId('doc-markdown-editor');
}

async function turnSourceIntoFormattedDocument(page) {
  const editor = documentEditor(page);
  await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
  const source = editor.getByTestId('rich-text-source-input');
  await source.fill('Texto para formato');
  await editor.getByRole('tab', { name: /^Visual$/ }).click();

  const visual = editor.getByTestId('rich-text-visual-input');
  await visual.click();
  await visual.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
  await editor.getByRole('button', { name: /^(Negrita|Bold)$/ }).click();
  await editor.getByRole('button', { name: /^(Lista con viñetas|Bulleted list)$/ }).click();
  await visual.click();
  await visual.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
  await editor.getByLabel(/^(Color del texto|Text color)$/).fill('#ff0000');
  await editor.getByRole('button', { name: /^(Insertar tabla|Insert table)$/ }).click();

  await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
  return source;
}

test.describe('Editorial rich text in documents', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'editorial-document-token',
      userAuth: { id: 761, role: 'admin', is_staff: true },
    });
  });

  test('saves visual formatting through a document source round trip', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentBase } };
    await mockDocumentEditorApi(page, state);
    await page.goto('/es-co/panel/documents/91/edit', { waitUntil: 'domcontentloaded' });

    const source = await turnSourceIntoFormattedDocument(page);
    await expect(source).toHaveValue(/Texto para formato/);
    await expect(source).toHaveValue(/\*\*Texto para formato\*\*/);
    await expect(source).toHaveValue(/color:/);
    await expect(source).toHaveValue(/\||<table/);

    const requestPromise = page.waitForRequest((request) => (
      request.url().includes('/api/documents/91/update/') && request.method() === 'PATCH'
    ));
    await page.getByTestId('doc-save').click();
    const payload = (await requestPromise).postDataJSON();
    expect(payload.text_formats).toMatchObject({ '/content_markdown': 'markdown_html_v1' });
    expect(payload.content_markdown).toContain('Texto para formato');

    await page.reload({ waitUntil: 'domcontentloaded' });
    const reloaded = documentEditor(page);
    await reloaded.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(reloaded.getByTestId('rich-text-source-input')).toHaveValue(payload.content_markdown);
    await reloaded.getByRole('tab', { name: /^Visual$/ }).click();
    await expect(reloaded.getByTestId('rich-text-visual-input')).toContainText('Texto para formato');
  });

  test('creates a document with its source format declaration', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let createdPayload = null;
    const state = { document: { ...documentBase } };
    await mockDocumentEditorApi(page, state, (payload) => { createdPayload = payload; });
    await page.goto('/es-co/panel/documents/create', { waitUntil: 'domcontentloaded' });

    await page.getByLabel(/T[ií]tulo/i).fill('Documento con formato');
    const editor = documentEditor(page);
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await editor.getByTestId('rich-text-source-input').fill('**Alcance aprobado**\n\n- Primero\n- Segundo');
    await editor.getByRole('tab', { name: /^Visual$/ }).click();
    await expect(editor.getByTestId('rich-text-visual-input')).toContainText('Alcance aprobado');

    await page.getByRole('button', { name: 'Crear Documento', exact: true }).click();
    await expect.poll(() => createdPayload).toMatchObject({
      markdown: '**Alcance aprobado**\n\n- Primero\n- Segundo',
      text_formats: { '/content_markdown': 'markdown_html_v1' },
    });
  });
});
