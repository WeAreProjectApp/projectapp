import { expect } from './test.js';
import { mockApi } from './api.js';
import { setAuthLocalStorage } from './auth.js';

const json = (value, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(value) });
export const historyDocument = { id: 265, title: 'Acuerdo PA-265', status: 'draft', content_format: 'markdown', content_markdown: '# Alcance\n\nContenido actual', created_at: '2026-11-01T12:00:00Z' };
export function historicalRevision(number, source = `# Alcance\n\nContenido revisión ${number}`, overrides = {}) {
  return {
    id: number, number, complete: true, action: 'updated', actor: 'Ana Revisora', source: 'http',
    occurred_at: `2026-11-${String(number).padStart(2, '0')}T12:00:00Z`,
    fields: [{ name: 'content_markdown', label: 'Contenido' }],
    snapshot: { title: 'Acuerdo PA-265', content_markdown: source }, changes: [], labels: {},
    previous_id: number > 1 ? number - 1 : null, ...overrides,
  };
}

export async function installDocumentHistory(page, { overrides = {}, fail = '', onRequest = () => {} } = {}) {
  const revisions = Array.from({ length: 25 }, (_, index) => historicalRevision(index + 1));
  for (const [id, revision] of Object.entries(overrides)) revisions[Number(id) - 1] = revision;
  let failed = false;
  await setAuthLocalStorage(page, { token: 'fixture-admin', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ route, apiPath, method }) => {
    onRequest({ apiPath, method });
    if (apiPath === 'auth/check/') return json({ user: { username: 'Ana Revisora', is_staff: true, is_superuser: true } });
    if (apiPath === 'documents/') return json([historyDocument]);
    if (apiPath === 'documents/265/detail/') return json(historyDocument);
    if (['document-folders/', 'document-tags/', 'document-states/', 'document-state-groups/', 'accounting/projects/'].includes(apiPath) || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (!apiPath.startsWith('entity-history/document/265/')) return null;
    const kind = apiPath.includes('/compare/') ? 'compare' : apiPath.includes('/versions/') ? 'version' : 'list';
    if (fail === kind && !failed) { failed = true; return json({ detail: 'Temporalmente no disponible' }, 503); }
    const url = new URL(route.request().url());
    if (kind === 'list') {
      const pageNumber = Number(url.searchParams.get('page')) || 1;
      const ordered = url.searchParams.get('order') === 'oldest' ? revisions : [...revisions].reverse();
      return json({ results: ordered.slice((pageNumber - 1) * 20, pageNumber * 20), page: pageNumber, count: revisions.length, num_pages: 2, latest_change: revisions[24] });
    }
    if (kind === 'version') return json(revisions[Number(apiPath.match(/versions\/(\d+)/)[1]) - 1]);
    return json({ from: revisions[Number(url.searchParams.get('from')) - 1], to: revisions[Number(url.searchParams.get('to')) - 1], changes: [] });
  });
}

export async function openDocumentHistory(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < 1024) await page.getByRole('button', { name: 'Abrir menú' }).click();
  await page.getByRole('link', { name: 'Gestor Documental', exact: true }).click();
  await page.getByRole('link', { name: historyDocument.title, exact: true }).click();
  await expect(page.getByTestId('doc-editor-title')).toHaveText(historyDocument.title);
  const tabs = page.getByTestId('entity-history-tabs');
  const mobile = tabs.getByLabel('Secciones');
  if (await mobile.isVisible()) await mobile.selectOption('history');
  else await tabs.getByRole('tab', { name: 'Historial', exact: true }).click();
  await expect(page.getByTestId('history-entry-25')).toContainText('Ana Revisora');
}
