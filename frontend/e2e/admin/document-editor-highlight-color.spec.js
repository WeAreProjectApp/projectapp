// qa: draft-unvalidated (2026-11-07 — app not running)
/**
 * PA-211 foreground color inside rich-text highlights.
 *
 * Captures browser-computed colors through the staff document editor and its
 * DocumentMarkdownBody preview. API routes are mocked only at the boundary.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_EDIT } from '../helpers/flow-tags.js';

const documentFixture = {
  id: 411,
  title: 'Color editorial PA-211',
  status: 'draft',
  content_markdown: 'prueba',
  text_formats: { '/content_markdown': 'markdown_html_v1' },
  created_at: '2026-11-07T10:00:00Z',
};

const historicalEditorialSource = '<p>QA007 <span style="color: rgb(255, 0, 0);"><del><mark style="background-color: rgb(255, 255, 0);">etiqueta roja</mark></del></span> <span style="color: rgb(255, 0, 0);"><del><span style="color: rgb(0, 0, 255);"><mark style="background-color: rgb(255, 255, 0);">etiqueta azul</mark></span></del></span></p>';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'staff-editor', is_staff: true } }),
};

async function mockEditorApi(page, state, onUpdate = null) {
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `documents/${state.document.id}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(state.document) };
    }
    if (apiPath === `documents/${state.document.id}/update/` && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      onUpdate?.(payload);
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

async function openEdit(page, state, onUpdate) {
  await mockEditorApi(page, state, onUpdate);
  await page.goto(`/es-co/panel/documents/${state.document.id}/edit`, { waitUntil: 'domcontentloaded' });
}

async function openSource(page) {
  const documentEditor = editor(page);
  await documentEditor.getByRole('tab', { name: 'Fuente', exact: true }).click();
  return documentEditor.getByTestId('rich-text-source-input');
}

async function selectVisualText(page) {
  const documentEditor = editor(page);
  const visual = documentEditor.getByTestId('rich-text-visual-input');
  await visual.click();
  await visual.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
  return visual.getByText('prueba', { exact: true });
}

async function applyRedHighlight(page) {
  const documentEditor = editor(page);
  for (const name of ['Negrita', 'Cursiva', 'Tachado', 'Subrayado']) {
    await selectVisualText(page);
    await documentEditor.getByRole('button', { name, exact: true }).click();
  }
  await selectVisualText(page);
  await documentEditor.getByLabel('Color del texto', { exact: true }).fill('#ff0000');
  const selected = await selectVisualText(page);
  await documentEditor.getByLabel('Resaltado', { exact: true }).fill('#ffff00');
  return selected;
}

test.describe('Document editor highlight foreground', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'pa211-highlight-token',
      userAuth: { id: 411, role: 'admin', is_staff: true },
    });
  });

  // Bug caught: a highlighted red selection could inherit black from <mark> after stacked text formatting.
  test('keeps explicit red foreground in editor preview themes', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    let savedPayload = null;
    await openEdit(page, state, (payload) => { savedPayload = payload; });

    const selected = await applyRedHighlight(page);
    await expect(selected).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(selected).toHaveCSS('background-color', 'rgb(255, 255, 0)');

    const source = await openSource(page);
    await expect(source).toHaveValue(/color: rgb\(255, 0, 0\)/);
    await expect(source).toHaveValue(/background-color: rgb\(255, 255, 0\)/);
    await expect(source).toHaveValue(/<strong>/);
    await expect(source).toHaveValue(/<em>/);
    await expect(source).toHaveValue(/<s>/);
    await expect(source).toHaveValue(/<u>/);
    await expect(source).not.toHaveValue(/color:\s*inherit|data-color/);

    const requestPromise = page.waitForRequest((request) => (
      request.url().includes(`/api/documents/${state.document.id}/update/`) && request.method() === 'PATCH'
    ));
    const responsePromise = page.waitForResponse((response) => (
      response.url().includes(`/api/documents/${state.document.id}/update/`) && response.status() === 200
    ));
    await page.getByTestId('doc-save').click();
    const requestPayload = (await requestPromise).postDataJSON();
    await responsePromise;
    expect(requestPayload.text_formats).toMatchObject({ '/content_markdown': 'markdown_html_v1' });
    expect(savedPayload.content_markdown).toContain('background-color: rgb(255, 255, 0)');

    await page.reload({ waitUntil: 'domcontentloaded' });
    const reloadedSource = await openSource(page);
    await expect(reloadedSource).toHaveValue(requestPayload.content_markdown);
    await editor(page).getByRole('tab', { name: 'Visual', exact: true }).click();
    const visualMark = editor(page).getByText('prueba', { exact: true });
    await expect(visualMark).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(visualMark).toHaveCSS('background-color', 'rgb(255, 255, 0)');
    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
    const previewMark = page.getByTestId('doc-markdown-preview-pane').getByText('prueba', { exact: true });
    await expect(previewMark).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(previewMark).toHaveCSS('background-color', 'rgb(255, 255, 0)');

    await page.getByRole('button', { name: 'Cambiar a modo oscuro', exact: true }).click();
    await expect(page.locator('html')).toHaveClass(/(?:^|\s)dark(?:\s|$)/);
    await expect(previewMark).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(previewMark).toHaveCSS('background-color', 'rgb(255, 255, 0)');
    await page.getByRole('tab', { name: 'Editar', exact: true }).click();
    await expect(visualMark).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(visualMark).toHaveCSS('background-color', 'rgb(255, 255, 0)');
  });

  // Bug caught: DocumentMarkdownBody could let its gray <del> rule override an explicit span color in a yellow highlight.
  test('keeps historical nested colors in preview themes', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = {
      document: {
        ...documentFixture,
        content_markdown: historicalEditorialSource,
      },
    };
    await openEdit(page, state);

    const source = await openSource(page);
    await expect(source).toHaveValue(historicalEditorialSource);
    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
    const preview = page.getByTestId('doc-markdown-preview-pane');
    const redLabel = preview.getByText('etiqueta roja', { exact: true });
    const blueLabel = preview.getByText('etiqueta azul', { exact: true });
    await expect(redLabel).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(blueLabel).toHaveCSS('color', 'rgb(0, 0, 255)');
    await expect(redLabel).toHaveCSS('background-color', 'rgb(255, 255, 0)');
    await expect(blueLabel).toHaveCSS('background-color', 'rgb(255, 255, 0)');

    await page.getByRole('button', { name: 'Cambiar a modo oscuro', exact: true }).click();
    await expect(page.locator('html')).toHaveClass(/(?:^|\s)dark(?:\s|$)/);
    await expect(redLabel).toHaveCSS('color', 'rgb(255, 0, 0)');
    await expect(blueLabel).toHaveCSS('color', 'rgb(0, 0, 255)');
  });

  // Bug caught: a plain yellow highlight could inherit a white dark-theme foreground without an explicit text color.
  test('keeps uncolored highlights black after theme change', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    await openEdit(page, state);

    const selected = await selectVisualText(page);
    await editor(page).getByLabel('Resaltado', { exact: true }).fill('#ffff00');
    await expect(selected).toHaveCSS('color', 'rgb(0, 0, 0)');
    await expect(selected).toHaveCSS('background-color', 'rgb(255, 255, 0)');

    const source = await openSource(page);
    await expect(source).toHaveValue(/background-color: rgb\(255, 255, 0\)/);
    await expect(source).not.toHaveValue(/<span style="color:/);
    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
    const previewMark = page.getByTestId('doc-markdown-preview-pane').getByText('prueba', { exact: true });
    await page.getByRole('button', { name: 'Cambiar a modo oscuro', exact: true }).click();
    await expect(page.locator('html')).toHaveClass(/(?:^|\s)dark(?:\s|$)/);
    await expect(previewMark).toHaveCSS('color', 'rgb(0, 0, 0)');
  });

  // Bug caught: removing a highlight could also remove the preceding explicit foreground color.
  test('restores red foreground after highlight removal', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentFixture } };
    await openEdit(page, state);

    await applyRedHighlight(page);
    const selected = await selectVisualText(page);
    await editor(page).getByRole('button', { name: 'Quitar resaltado', exact: true }).click();
    await expect(selected).toHaveCSS('color', 'rgb(255, 0, 0)');
    const source = await openSource(page);
    await expect(source).toHaveValue(/color: rgb\(255, 0, 0\)/);
    await expect(source).not.toHaveValue(/background-color: rgb\(255, 255, 0\)/);
  });
});
