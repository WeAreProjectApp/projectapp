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
import { VIEWPORTS } from '../helpers/viewports.js';

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
    if (apiPath === 'documents/') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([{ ...state.document, content_excerpt: state.document.content_markdown, active_states: [] }]) };
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

function contrastRatio([r, g, b], [backR, backG, backB]) {
  const luminance = ([red, green, blue]) => [red, green, blue].map((value) => {
    const channel = value / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  }).reduce((total, channel, index) => total + channel * [0.2126, 0.7152, 0.0722][index], 0);
  const [light, dark] = [luminance([r, g, b]), luminance([backR, backG, backB])].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

async function setPanelTheme(page, target) {
  const isDark = await page.locator('html').evaluate((node) => node.classList.contains('dark'));
  if ((target === 'dark') !== isDark) {
    await page.getByRole('button', { name: target === 'dark' ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro' }).first().click();
  }
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
  // Collapse the styled selection before inserting the table. Tiptap correctly
  // replaces an active selection with a table, which would test replacement
  // rather than source/visual round-trip preservation.
  await visual.press('End');
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
    await expect(source).toHaveValue(/<strong>Texto para formato<\/strong>/);
    await expect(source).toHaveValue(/<ul>/);
    await expect(source).toHaveValue(/color: rgb\(255, 0, 0\)/);
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

  test('keeps a long visual document inside its scrollable editor pane', {
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentBase } };
    await mockDocumentEditorApi(page, state);
    await page.goto('/es-co/panel/documents/91/edit', { waitUntil: 'domcontentloaded' });

    const editor = documentEditor(page);
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await editor.getByTestId('rich-text-source-input').fill(
      Array.from({ length: 60 }, (_, index) => `Línea editorial ${index + 1}`).join('\n'),
    );
    await editor.getByRole('tab', { name: /^Visual$/ }).click();

    const scrollArea = editor.getByTestId('rich-text-scroll-area');
    const metrics = await scrollArea.evaluate((node) => ({
      clientHeight: node.clientHeight,
      scrollHeight: node.scrollHeight,
      bottom: node.getBoundingClientRect().bottom,
      editorBottom: node.closest('[data-testid="doc-markdown-editor"]')?.getBoundingClientRect().bottom,
    }));
    expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight);
    expect(metrics.bottom).toBeLessThanOrEqual((metrics.editorBottom || 0) + 1);

    await scrollArea.evaluate((node) => { node.scrollTop = node.scrollHeight; });
    const lastLineIsVisible = await scrollArea.evaluate((node) => {
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      let textNode = walker.nextNode();
      while (textNode && !textNode.textContent?.includes('Línea editorial 60')) textNode = walker.nextNode();
      if (!textNode) return false;
      const start = textNode.textContent.indexOf('Línea editorial 60');
      const range = document.createRange();
      range.setStart(textNode, start);
      range.setEnd(textNode, start + 'Línea editorial 60'.length);
      const line = range.getBoundingClientRect();
      const area = node.getBoundingClientRect();
      return line.top >= area.top && line.bottom <= area.bottom;
    });
    expect(lastLineIsVisible).toBe(true);
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

  test('preserves an active Código control through source reload', {
    // Bug caught: the active <> glyph blended into the dark toolbar and code formatting vanished after reopening.
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentBase, content_markdown: 'Normal codigo' } };
    await mockDocumentEditorApi(page, state);
    await page.goto('/es-co/panel/documents/91/edit', { waitUntil: 'domcontentloaded' });

    const editor = documentEditor(page);
    const visual = editor.getByTestId('rich-text-visual-input');
    await visual.click();
    await visual.evaluate((node) => {
      const text = document.createTreeWalker(node, NodeFilter.SHOW_TEXT).nextNode();
      const start = text.textContent.indexOf('codigo');
      const range = document.createRange();
      range.setStart(text, start); range.setEnd(text, start + 'codigo'.length);
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
    });
    const code = editor.getByRole('button', { name: /^(Código|Code)$/ });
    await code.click();
    await expect(code).toHaveAttribute('aria-pressed', 'true');
    for (const profile of ['compact', 'portrait', 'desktop']) {
      await page.setViewportSize(VIEWPORTS[profile]);
      for (const target of ['light', 'dark']) {
        await setPanelTheme(page, target);
        await expect(code).toBeVisible();
        await expect(code).toHaveAttribute('aria-pressed', 'true');
        const colors = await code.evaluate((node) => {
          const rgb = (value) => value.match(/\d+/g).slice(0, 3).map(Number);
          const style = getComputedStyle(node);
          return { foreground: rgb(style.color), background: rgb(style.backgroundColor) };
        });
        expect(contrastRatio(colors.foreground, colors.background), `${profile}/${target} Código glyph`).toBeGreaterThanOrEqual(3);
      }
    }
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(editor.getByTestId('rich-text-source-input')).toHaveValue(/<code>|`codigo`/);

    await page.getByTestId('doc-save').click();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await documentEditor(page).getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(documentEditor(page).getByTestId('rich-text-source-input')).toHaveValue(/<code>|`codigo`/);
  });

  for (const style of ['professional', 'friendly']) test(`renders ${style} paragraph headers legibly with colspan`, {
    // Bug caught: HTML saved from Visual gave TH > P its body text color, making table headings unreadable.
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const state = { document: { ...documentBase, template_style: style, content_markdown: '<table><thead><tr><th><p>Elemento</p></th><th colspan="2"><p>Cabecera combinada</p></th></tr></thead></table>' } };
    await mockDocumentEditorApi(page, state);
    await page.goto('/es-co/panel/documents', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('document-open-91').click();

    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
    const header = page.getByRole('columnheader', { name: 'Cabecera combinada' });
    await expect(header).toHaveAttribute('colspan', '2');
    for (const target of ['light', 'dark']) {
      await setPanelTheme(page, target);
      const colors = await header.locator('p').evaluate((node) => {
        const rgb = (value) => value.match(/\d+/g).slice(0, 3).map(Number);
        return { foreground: rgb(getComputedStyle(node).color), background: rgb(getComputedStyle(node.parentElement).backgroundColor) };
      });
      expect(contrastRatio(colors.foreground, colors.background), `${target} table header`).toBeGreaterThanOrEqual(4.5);
    }
    await expect(page.getByRole('columnheader', { name: 'Elemento' })).toHaveText('Elemento');
    await page.getByRole('tab', { name: 'Editar', exact: true }).click();
    await documentEditor(page).getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await documentEditor(page).getByTestId('rich-text-source-input').fill(`${state.document.content_markdown}\n\nControl guardado`);
    await page.getByTestId('doc-save').click();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();
    await expect(page.getByRole('columnheader', { name: 'Cabecera combinada' })).toHaveAttribute('colspan', '2');
    await expect(page.getByRole('columnheader', { name: 'Elemento' })).toHaveText('Elemento');
  });

  test('renders escaped punctuation in the saved gallery excerpt', {
    // Bug caught: card previews displayed a Markdown escape before a normal period after reopening a document.
    tag: [...ADMIN_DOCUMENT_EDIT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { document: { ...documentBase } };
    await mockDocumentEditorApi(page, state);
    await page.goto('/es-co/panel/documents/91/edit', { waitUntil: 'domcontentloaded' });
    const editor = documentEditor(page);
    await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await editor.getByTestId('rich-text-source-input').fill('Texto de control sin formato\\.\n\n`C:\\ruta`');
    await page.getByTestId('doc-save').click();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await documentEditor(page).getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
    await expect(documentEditor(page).getByTestId('rich-text-source-input')).toHaveValue('Texto de control sin formato\\.\n\n`C:\\ruta`');

    await page.getByTestId('doc-cancel').click();
    await page.getByTestId('doc-view-grid').click();
    const card = page.getByTestId('document-card-91');
    await expect(card).toContainText('Texto de control sin formato.');
    await expect(card).not.toContainText('formato\\.');
    await expect(card).toContainText('C:\\ruta');
  });
});
