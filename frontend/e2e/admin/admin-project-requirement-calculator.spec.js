/**
 * Project calculator draft and approval journeys.
 * They catch a project version being created or approved when the server did
 * not accept the immutable parameter snapshot.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  calculatorDefinition, generalCalculator, json, projectCalculator, projectVersion,
} from '../helpers/requirement-calculator.js';
import {
  ADMIN_PROJECT_REQUIREMENT_CALCULATOR_APPROVE,
  ADMIN_PROJECT_REQUIREMENT_CALCULATOR_DRAFT,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const projectRow = {
  id: 20, name: 'Proyecto Aurora', description: 'Proyecto de prueba', status: 'active', status_label: 'Activo',
  client: { profile_id: 7, name: 'Cliente Aurora', company: 'Aurora' }, hostings_count: 0, incomes_count: 0,
  current_state: { id: 2, name: 'Activo', system_key: 'active', operational_effect: 'operating', color: 'emerald' },
};

async function arrangeProjectCalculator(page, { createStatus = 201, approveStatus = 200, withDraft = false } = {}) {
  const calls = [];
  let version = withDraft ? projectVersion() : null;
  await setAuthLocalStorage(page, { token: 'project-calculator-e2e', userAuth: { id: 711, role: 'admin', is_staff: true } });
  await mockApi(page, async ({ route, apiPath, method }) => {
    calls.push({ apiPath, method, body: route.request().postData() });
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'dashboard/summary/' && method === 'GET') return json({});
    if (apiPath === 'project-states/' && method === 'GET') return json([projectRow.current_state]);
    if (apiPath === 'project-state-groups/' && method === 'GET') return json([]);
    if (apiPath === 'projects/' && method === 'GET') return json({ results: [projectRow], meta: { total: 1, by_state: [], review_required: 0, clients_without_projects: 0, records_without_project: 0 } });
    if (apiPath === 'requirement-calculator/' && method === 'GET') return json(generalCalculator());
    if (apiPath === 'requirement-calculator/revisions/' && method === 'GET') return json({ count: 0, results: [] });
    if (apiPath === 'requirement-calculator/projects/20/' && method === 'GET') return json(projectCalculator({ versions: version ? [version] : [], calculatorDocumentId: version?.status === 'approved' ? version.document_id : null }));
    if (apiPath === 'requirement-calculator/project-versions/301/' && method === 'GET') return json(version || projectVersion());
    if (apiPath === 'requirement-calculator/projects/20/' && method === 'POST') {
      if (createStatus >= 300) {
        return json({ detail: createStatus === 409 ? 'Ya existe un borrador para este proyecto.' : 'No se pudo crear el borrador.' }, createStatus);
      }
      version = projectVersion();
      return json(version, createStatus);
    }
    if (apiPath === 'requirement-calculator/project-versions/301/approve/' && method === 'POST') {
      if (approveStatus >= 300) return json({ detail: approveStatus === 409 ? 'La versión cambió en otra sesión.' : 'No se pudo generar el PDF.' }, approveStatus);
      version = projectVersion({ status: 'approved' });
      return json(version);
    }
    if (apiPath === 'requirement-calculator/project-versions/301/' && method === 'PATCH') return json(version || projectVersion());
    return null;
  });
  return calls;
}

async function openProjectCalculator(page) {
  await page.goto('/es-co/panel/requirement-calculator?project=20', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Calculadora de requerimientos', exact: true })).toHaveText('Calculadora de requerimientos');
}

test.describe('Admin project calculator versions', () => {
  test('opens calculator parameters from a project action', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_DRAFT, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where a project action loses the project id before opening its calculator.
    await arrangeProjectCalculator(page);
    // quality: allow-deep-link (panel root is fixture setup; the tested navigation continues by clicking Proyectos and its action menu).
    await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Proyectos', exact: true }).or(page.getByTitle('Proyectos')).click();
    const project = page.getByRole('row', { name: /Proyecto Aurora/ });
    await expect(project).toContainText('Proyecto Aurora');
    await project.getByRole('button', { name: /^Acciones de / }).click();
    await page.getByTestId('project-actions-calculator').click();
    await expect(page).toHaveURL(/requirement-calculator\?project=20/);
    await expect(page.getByTestId('calculator-note')).toHaveValue('');
  });

  test('creates one project draft with its document link', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_DRAFT, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where a successful draft creation loses the returned document and version.
    const calls = await arrangeProjectCalculator(page);
    await openProjectCalculator(page);
    await page.getByTestId('calculator-note').fill('Ajuste negociado para Aurora');
    await page.getByRole('button', { name: 'Crear borrador para el proyecto', exact: true }).click();
    await expect(page.getByTestId('calculator-project-version')).toHaveValue('301');
    await expect(page.getByRole('link', { name: 'Abrir documento', exact: true })).toHaveAttribute('href', '/es-co/panel/documents/900/edit');
    expect(calls.filter((call) => call.apiPath === 'requirement-calculator/projects/20/' && call.method === 'POST')).toHaveLength(1);
  });

  test('shows a duplicate-draft conflict without inventing an approved version', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_DRAFT, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a 409 creation conflict appears as an approved calculator.
    await arrangeProjectCalculator(page, { createStatus: 409 });
    await openProjectCalculator(page);
    await page.getByTestId('calculator-note').fill('Intento de borrador repetido');
    await page.getByRole('button', { name: 'Crear borrador para el proyecto', exact: true }).click();
    await expect(page.getByTestId('calculator-error')).toContainText('Ya existe un borrador para este proyecto.');
    await expect(page.getByTestId('calculator-project-version')).toHaveCount(0);
  });

  test('keeps the draft absent when its creation endpoint fails', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_DRAFT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where a server failure renders a project draft that was never created.
    await arrangeProjectCalculator(page, { createStatus: 500 });
    await openProjectCalculator(page);
    await page.getByTestId('calculator-note').fill('Intento de borrador');
    await page.getByRole('button', { name: 'Crear borrador para el proyecto', exact: true }).click();
    await expect(page.getByTestId('calculator-error')).toContainText('No se pudo crear el borrador.');
    await expect(page.getByTestId('calculator-project-version')).toHaveCount(0);
    await expect(page.getByText('Esta versión está aprobada', { exact: false })).toHaveCount(0);
  });

  test('displays an existing draft as parameters that can be reviewed', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_APPROVE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where a saved draft does not load the version-specific parameters before approval.
    await arrangeProjectCalculator(page, { withDraft: true });
    // quality: allow-deep-link (the version page is setup; this test verifies the parameter editor interaction).
    await openProjectCalculator(page);
    await page.getByText('Señales de clasificación (1)', { exact: true }).click();
    await expect(page.getByTestId('calculator-XS-points')).toHaveValue('1');
    await expect(page.getByTestId('calculator-project-version')).toHaveValue('301');
  });

  test('requires saving local parameter changes before approval', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_APPROVE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where approval freezes unsaved local parameter edits.
    const calls = await arrangeProjectCalculator(page, { withDraft: true });
    await openProjectCalculator(page);
    await page.getByTestId('calculator-XS-points').fill('9');
    await expect(page.getByTestId('calculator-approve')).toBeDisabled();
    expect(calls.some((call) => call.apiPath.endsWith('/approve/') && call.method === 'POST')).toBe(false);
  });

  test('approves a confirmed clean draft for the project', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_APPROVE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where approval bypasses confirmation or never switches the version to approved.
    const calls = await arrangeProjectCalculator(page, { withDraft: true });
    await openProjectCalculator(page);
    await page.getByTestId('calculator-note').fill('Aprobación comercial revisada');
    await page.getByTestId('calculator-approve').click();
    await expect(page.getByText('Se congelarán parámetros, documento y PDF', { exact: false })).toContainText('no envía ni publica');
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByText('Esta versión está aprobada', { exact: false })).toContainText('Prepara otro borrador');
    expect(calls.filter((call) => call.apiPath.endsWith('/approve/') && call.method === 'POST')).toHaveLength(1);
  });

  test('shows an approval conflict with the editable draft', {
    tag: [...ADMIN_PROJECT_REQUIREMENT_CALCULATOR_APPROVE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a stale approval conflict freezes the local draft anyway.
    await arrangeProjectCalculator(page, { withDraft: true, approveStatus: 409 });
    await openProjectCalculator(page);
    await page.getByTestId('calculator-note').fill('Aprobación con posible conflicto');
    await page.getByTestId('calculator-approve').click();
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByTestId('calculator-error')).toContainText('La versión cambió en otra sesión.');
    await expect(page.getByTestId('calculator-XS-points')).toHaveValue('1');
  });
});
