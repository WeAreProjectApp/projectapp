/**
 * Managed calculator documents stay read-only and route staff back to the
 * matching project calculator instead of exposing a misleading document save.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { calculatorDefinition, generalCalculator, json, projectCalculator, projectVersion } from '../helpers/requirement-calculator.js';
import { ADMIN_MANAGED_CALCULATOR_DOCUMENT } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

test('opens a managed calculator document from its project version in read-only mode', {
  tag: [...ADMIN_MANAGED_CALCULATOR_DOCUMENT, '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  // Catches the bug where a managed calculator document appears editable or returns to the general calculator.
  const calls = [];
  const version = projectVersion({ status: 'approved' });
  const managedDocument = {
    id: 900, title: 'Calculadora · Proyecto Aurora · v301', status: 'draft', project: 20,
    content_markdown: '# Calculadora', calculator: { kind: 'project', version_id: 301, status: 'approved' },
    text_formats: {}, active_states: [], notes: [], client_custom_notes: [], language: 'es',
  };
  await setAuthLocalStorage(page, { token: 'managed-document-e2e', userAuth: { id: 712, role: 'admin', is_staff: true } });
  await mockApi(page, async ({ route, apiPath, method }) => {
    calls.push({ apiPath, method });
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'requirement-calculator/' && method === 'GET') return json(generalCalculator(calculatorDefinition()));
    if (apiPath === 'requirement-calculator/revisions/?limit=20&offset=0' && method === 'GET') return json({ count: 0, results: [] });
    if (apiPath === 'requirement-calculator/projects/20/' && method === 'GET') return json(projectCalculator({ versions: [version], calculatorDocumentId: 900 }));
    if (apiPath === 'requirement-calculator/project-versions/301/' && method === 'GET') return json(version);
    if (apiPath === 'documents/900/detail/' && method === 'GET') return json(managedDocument);
    if (['document-folders/', 'document-tags/', 'document-states/', 'document-state-groups/', 'accounting/projects/'].includes(apiPath)) return json([]);
    if (apiPath === 'documents/900/communications/' || apiPath === 'documents/900/email-usage/') return json({ count: 0, results: [] });
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    return null;
  });

  // quality: allow-deep-link (the selected project version is setup; the document itself is reached through its visible link).
  await page.goto('/es-co/panel/requirement-calculator?project=20', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Abrir documento', exact: true }).click();
  await expect(page).toHaveURL(/\/es-co\/panel\/documents\/900\/edit$/);
  await expect(page.getByTestId('doc-calculator-alert')).toContainText('Variante del proyecto');
  const title = page.getByLabel('Título', { exact: true });
  await expect(title).toHaveValue('Calculadora · Proyecto Aurora · v301');
  await expect(title).toHaveAttribute('readonly', '');
  await page.getByTestId('doc-calculator-alert').getByRole('link', { name: 'Calculadora de requerimientos', exact: true }).click();
  await expect(page).toHaveURL(/requirement-calculator\?project=20/);
  expect(calls.some((call) => call.apiPath === 'documents/900/update/' && call.method === 'PATCH')).toBe(false);
});
