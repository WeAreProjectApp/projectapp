import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';

function pdfFixture(text) {
  const stream = `BT /F1 12 Tf 20 100 Td (${text}) Tj ET`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let body = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(body)); body += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(body);
  body += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, '0')} 00000 n `).join('\n')}\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(body);
}
const original = pdfFixture('Original PDF');
const next = pdfFixture('Replacement PDF');
const file = { name: 'original.pdf', mimeType: 'application/pdf', buffer: original };
const json = (data, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(data) });
const tags = (outcome) => ['@flow:admin-document-pdf', '@role:admin', `@outcome:${outcome}`];

async function setup(page, { createFailure = false, replaceFailure = false, previewFailure = false } = {}) {
  await setAuthLocalStorage(page, { token: 'pdf-e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  let document = {
    id: 71, uuid: 'pdf-doc-71', title: 'Anexo PDF', status: 'draft', content_format: 'pdf',
    pdf: { filename: 'original.pdf', version: 1, size: original.length, text_status: 'indexed' },
    content_markdown: '', client_custom_notes: [], active_states: [], notes: [], folder: null,
    is_client_visible: false, editable: true, pdf_replaceable: true, content_editable: false,
    created_at: '2026-10-29T12:00:00Z', updated_at: '2026-10-29T12:00:00Z',
  };
  let createBody = '';
  let replacementBody = '';
  let metadataBody = null;
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'documents/') return json([document]);
    if (apiPath === 'documents/71/detail/') return json(document);
    if (apiPath === 'documents/create-from-pdf/' && method === 'POST') {
      createBody = route.request().postDataBuffer().toString();
      if (createFailure) return json({ file: ['El contenido del archivo no es PDF.'] }, 400);
      return json(document, 201);
    }
    if (apiPath === 'documents/71/update/') {
      metadataBody = route.request().postDataJSON();
      document = { ...document, ...metadataBody };
      return json(document);
    }
    if (apiPath === 'documents/71/replace-pdf/') {
      replacementBody = route.request().postDataBuffer().toString();
      if (replaceFailure) return json({ detail: 'El PDF cambió. Recarga el documento.' }, 409);
      document = { ...document, pdf: { ...document.pdf, version: 2, filename: 'new.pdf' } };
      return json(document);
    }
    if (apiPath === 'documents/71/pdf/') {
      if (previewFailure) return json({ detail: 'PDF no disponible.' }, 404);
      return { status: 200, contentType: 'application/pdf', body: document.pdf.version === 2 ? next : original,
        headers: { 'Content-Disposition': new URL(route.request().url()).searchParams.has('inline') ? 'inline' : 'attachment; filename="original.pdf"' } };
    }
    if (apiPath === 'entity-history/document/71/') return json({ results: [{ id: 91, number: 1, action: 'created', occurred_at: '2026-10-29T12:00:00Z', actor: 'Operador', source: 'http', fields: [{ label: 'Archivo PDF' }], complete: true }], count: 1, page: 1, page_size: 20, total_pages: 1 });
    if (apiPath === 'entity-history/document/71/versions/91/') return json({ id: 91, number: 1, changes: [], snapshot: { title: 'Anexo PDF', uploaded_pdf: 'private-reference', pdf_filename: 'original.pdf' } });
    if (apiPath.endsWith('/versions/91/file/')) return { status: 200, contentType: 'application/pdf', body: original };
    if (['document-folders/', 'document-tags/', 'document-states/', 'document-state-groups/', 'accounting/projects/', 'proposals/client-profiles/'].includes(apiPath)) return json([]);
    if (apiPath.includes('email-usage') || apiPath.includes('communications')) return json({ count: 0, results: [] });
    return null;
  });
  return { createBody: () => createBody, replacementBody: () => replacementBody, metadataBody: () => metadataBody };
}

async function createPdf(page) {
  await page.goto('/panel/documents/create', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Cargar Archivo' }).click();
  await page.getByTestId('doc-create-file').setInputFiles(file);
  await page.getByLabel('Título', { exact: true }).fill('Anexo PDF');
  await page.getByRole('button', { name: 'Crear Documento', exact: true }).filter({ visible: true }).click();
  await expect(page).toHaveURL(/\/documents\/71\/edit/);
}

test('creates a PDF through file selection', { tag: tags('success') }, async ({ page }) => {
  const requests = await setup(page);
  await createPdf(page);
  await expect(page.getByTestId('doc-uploaded-pdf-panel')).toContainText('original.pdf');
  expect(requests.createBody()).toContain('filename="original.pdf"');
  expect(requests.createBody()).not.toContain('name="markdown"');
  await expect(page.getByTestId('doc-markdown-editor-panel')).toHaveCount(0);
});

test('accepts a PDF dropped into the document form', { tag: tags('success') }, async ({ page }) => {
  await setup(page);
  await page.goto('/panel/documents/create', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Cargar Archivo' }).click();
  const transfer = await page.evaluateHandle((bytes) => {
    const dt = new DataTransfer();
    dt.items.add(new File([new Uint8Array(bytes)], 'dropped.pdf', { type: 'application/pdf' }));
    return dt;
  }, [...original]);
  await page.getByText('Arrastra un archivo .pdf, .md, .markdown o .txt aquí').dispatchEvent('drop', { dataTransfer: transfer });
  await expect(page.getByText('Archivo: dropped.pdf')).toBeVisible();
  await expect(page.getByTestId('doc-create-pdf-frame')).toBeVisible();
});

test('shows a rejected PDF under its upload field', { tag: tags('error') }, async ({ page }) => {
  await setup(page, { createFailure: true });
  await page.goto('/panel/documents/create', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Cargar Archivo' }).click();
  await page.getByTestId('doc-create-file').setInputFiles(file);
  await page.getByLabel('Título', { exact: true }).fill('Inválido');
  await page.getByRole('button', { name: 'Crear Documento', exact: true }).filter({ visible: true }).click();
  await expect(page.getByText('El contenido del archivo no es PDF.', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/documents\/create/);
});

test('shows the original PDF after creating it', { tag: tags('display') }, async ({ page }) => {
  await setup(page);
  await createPdf(page);
  await expect(page.getByTestId('doc-pdf-version')).toContainText('Versión 1 · original.pdf');
  await expect(page.getByTestId('doc-uploaded-pdf-frame')).toHaveAttribute('src', /inline=1&v=1/);
  const downloadEvent = page.waitForEvent('download');
  await page.getByTestId('doc-pdf-original-download').click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe('original.pdf');
});

test('replaces a PDF without changing its identity', { tag: tags('success') }, async ({ page }) => {
  const requests = await setup(page);
  await page.goto('/panel/documents/71/edit', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('doc-pdf-replace-file').setInputFiles({ ...file, name: 'new.pdf', buffer: next });
  await page.getByTestId('doc-pdf-replace-save').click();
  await expect(page.getByTestId('doc-pdf-version')).toContainText('Versión 2 · new.pdf');
  expect(requests.replacementBody()).toMatch(/name="expected_version"\r?\n\r?\n1/);
  await expect(page).toHaveURL(/\/documents\/71\/edit/);
  await page.getByRole('tab', { name: 'Historial', exact: true }).click();
  await page.getByRole('button', { name: 'Consultar', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Ver PDF de esta versión' })).toHaveAttribute('href', /\/versions\/91\/file\//);
});

test('retains the selected file after a concurrent replacement', { tag: tags('failure') }, async ({ page }) => {
  await setup(page, { replaceFailure: true });
  await page.goto('/panel/documents/71/edit', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('doc-pdf-replace-file').setInputFiles({ ...file, name: 'new.pdf', buffer: next });
  await page.getByTestId('doc-pdf-replace-save').click();
  await expect(page.locator('#doc-pdf-replace-error')).toHaveText('El PDF cambió. Recarga el documento.');
  await expect(page.getByTestId('doc-pdf-replace-save')).toBeVisible();
  await expect(page.getByTestId('doc-pdf-version')).toContainText('Versión 1');
});

test('keeps metadata editable without submitting Markdown', { tag: tags('success') }, async ({ page }) => {
  const requests = await setup(page);
  await page.goto('/panel/documents/71/edit', { waitUntil: 'domcontentloaded' });
  await page.locator('#edit-title').fill('Identificación nueva');
  await page.getByTestId('doc-save').click();
  await expect(page.getByTestId('doc-editor-title')).toHaveText('Identificación nueva');
  expect(requests.metadataBody().content_markdown).toBeUndefined();
  expect(requests.metadataBody().include_portada).toBeUndefined();
});

test('offers the original download when the viewer fails', { tag: tags('failure') }, async ({ page }) => {
  await setup(page, { previewFailure: true });
  await createPdf(page);
  await expect(page.getByTestId('doc-uploaded-pdf-error')).toContainText('El PDF no está disponible');
  await expect(page.getByTestId('doc-pdf-original-download')).toHaveAttribute('href', /\/documents\/71\/pdf\//);
});
