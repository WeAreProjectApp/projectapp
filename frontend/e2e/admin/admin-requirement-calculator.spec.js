/**
 * Requirement calculator administration journeys.
 * These tests catch regressions that can make a protected calculator look
 * published, hide calibration evidence, or discard a prior revision.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  calibration, calculatorDefinition, estimates, generalCalculator, json,
} from '../helpers/requirement-calculator.js';
import {
  ADMIN_REQUIREMENT_CALCULATOR_CALIBRATION,
  ADMIN_REQUIREMENT_CALCULATOR_DEFINITION,
  ADMIN_REQUIREMENT_CALCULATOR_REVISION_RESTORE,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

async function arrangeCalculator(page, { previewStatus = 200, revisionStatus = 200, actualStatus = 201 } = {}) {
  const calls = [];
  const definition = calculatorDefinition();
  let calibrationResponse = calibration;
  await setAuthLocalStorage(page, { token: 'calculator-e2e', userAuth: { id: 710, role: 'admin', is_staff: true } });
  await mockApi(page, async ({ route, apiPath, method }) => {
    calls.push({ apiPath, method, body: route.request().postData() });
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'dashboard/summary/' && method === 'GET') return json({});
    if (apiPath === 'requirement-calculator/' && method === 'GET') return json(generalCalculator(definition));
    if (apiPath === 'requirement-calculator/' && method === 'POST') {
      return json({ ...generalCalculator(definition), revision_id: 12, if_match: 'general-v12' });
    }
    if (apiPath === 'requirement-calculator/revisions/?limit=20&offset=0' && method === 'GET') {
      return json({ count: 1, results: [{ id: 9, note: 'Regla anterior', created_at: '2026-10-01T09:00:00Z' }] });
    }
    if (apiPath === 'requirement-calculator/revisions/9/' && method === 'GET') {
      return revisionStatus === 200
        ? json({ id: 9, definition: calculatorDefinition('Revisión histórica') })
        : json({ detail: 'La revisión ya no está disponible.' }, revisionStatus);
    }
    if (apiPath === 'requirement-calculator/preview/' && method === 'POST') {
      return previewStatus === 200
        ? json({ markdown: '# Vista previa calculada\nTalla M' })
        : json({ detail: previewStatus === 400 ? 'La talla XS requiere puntos.' : 'No fue posible previsualizar.' }, previewStatus);
    }
    if (apiPath === 'requirement-calculator/calibration/' && method === 'GET') return json(calibrationResponse);
    if (apiPath === 'requirement-calculator/estimates/?limit=20&offset=0' && method === 'GET') return json(estimates);
    if (apiPath === 'requirement-calculator/estimates/44/' && method === 'GET') {
      return json({ ...estimates.results[0], requirement: 'Alta de clientes con reglas de negocio completas', explanation: 'Formulario con validación y auditoría.' });
    }
    if (apiPath === 'requirement-calculator/estimates/44/actuals/?limit=3&offset=0' && method === 'GET') {
      return json({ count: 4, results: [{ id: 77, evidence: 'Bitácora completa con enlaces', cause: 'Ajuste inicial', actual_hours: '22.00' }] });
    }
    if (apiPath === 'requirement-calculator/actuals/' && method === 'POST') {
      if (actualStatus < 300) {
        calibrationResponse = { ...calibration, cohorts: [{ ...calibration.cohorts[0], samples: 2, median_hours: 26 }] };
        return json({ id: 78, supersedes_id: 77 }, actualStatus);
      }
      return json({ detail: actualStatus === 400 ? 'La evidencia es obligatoria.' : 'No fue posible registrar el cierre.' }, actualStatus);
    }
    return null;
  });
  return calls;
}

async function openCalculatorFromNavigation(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  const calculatorLink = page.getByRole('link', { name: 'Calculadora de requerimientos', exact: true })
    .or(page.getByTitle('Calculadora de requerimientos'));
  await calculatorLink.click();
  await expect(page).toHaveURL(/\/es-co\/panel\/requirement-calculator$/);
}

test.describe('Admin requirement calculator', () => {
  test('shows the active definition after sidebar navigation', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_DEFINITION, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the commercial sidebar opens a calculator without its current definition.
    await arrangeCalculator(page);
    // quality: allow-deep-link (panel root is fixture setup; the tested navigation uses the sidebar link).
    await openCalculatorFromNavigation(page);
    await expect(page.getByTestId('calculator-definition-editor')).toContainText('Definición comercial vigente');
    await expect(page.getByTestId('calculator-size-M')).toContainText('Talla M');
  });

  test('previews a definition without publishing it', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_DEFINITION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where preview uses the publication route or leaves no visible preview.
    const calls = await arrangeCalculator(page);
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Previsualizar definición', exact: true }).click();
    await expect(page.getByTestId('calculator-preview')).toHaveText('# Vista previa calculada\nTalla M');
    expect(calls.filter((call) => call.apiPath === 'requirement-calculator/preview/' && call.method === 'POST')).toHaveLength(1);
    expect(calls.filter((call) => call.apiPath === 'requirement-calculator/' && call.method === 'POST')).toHaveLength(0);
  });

  test('publishes a confirmed new revision', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_DEFINITION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where confirming the general save never creates the next immutable revision.
    const calls = await arrangeCalculator(page);
    await openCalculatorFromNavigation(page);
    await page.getByTestId('calculator-note').fill('Se calibraron los parámetros de noviembre');
    await page.getByTestId('calculator-save').click();
    await expect(page.getByText('Se activará una nueva revisión general', { exact: false })).toContainText('ofertas emitidas');
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByRole('status')).toHaveText('Cambios guardados; documento sincronizado.');
    expect(calls.filter((call) => call.apiPath === 'requirement-calculator/' && call.method === 'POST')).toHaveLength(1);
  });

  test('shows validation feedback when preview rejects parameters', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_DEFINITION, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a 400 preview rejection disappears behind the editor.
    await arrangeCalculator(page, { previewStatus: 400 });
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Previsualizar definición', exact: true }).click();
    await expect(page.getByTestId('calculator-error')).toContainText('La talla XS requiere puntos.');
  });

  test('keeps publication inactive when preview has a server failure', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_DEFINITION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where a failed preview is displayed as a valid publication-ready result.
    const calls = await arrangeCalculator(page, { previewStatus: 500 });
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Previsualizar definición', exact: true }).click();
    await expect(page.getByTestId('calculator-error')).toContainText('No fue posible previsualizar.');
    expect(calls.some((call) => call.apiPath === 'requirement-calculator/' && call.method === 'POST')).toBe(false);
  });

  test('lists a historical revision before any restoration', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_REVISION_RESTORE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the revision tab hides the historical reason required for restoration.
    await arrangeCalculator(page);
    // quality: allow-deep-link (panel root is fixture setup; the tested navigation uses the sidebar link).
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Versiones', exact: true }).click();
    await expect(page.getByText('Regla anterior', { exact: true })).toHaveText('Regla anterior');
  });

  test('loads a historical revision into the editor without publishing it', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_REVISION_RESTORE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where restoring a revision silently changes the active calculator.
    const calls = await arrangeCalculator(page);
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Versiones', exact: true }).click();
    await page.getByRole('button', { name: 'Preparar restauración', exact: true }).click();
    await expect(page.getByTestId('calculator-title')).toHaveValue('Revisión histórica');
    expect(calls.some((call) => call.apiPath === 'requirement-calculator/' && call.method === 'POST')).toBe(false);
  });

  test('keeps the active definition when loading a revision fails', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_REVISION_RESTORE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where a failed revision fetch blanks the editor and looks like a restore.
    await arrangeCalculator(page, { revisionStatus: 500 });
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Versiones', exact: true }).click();
    await page.getByRole('button', { name: 'Preparar restauración', exact: true }).click();
    await expect(page.getByTestId('calculator-error')).toContainText('La revisión ya no está disponible.');
    await page.getByRole('button', { name: 'Definición', exact: true }).click();
    await expect(page.getByTestId('calculator-title')).toHaveValue('Definición comercial vigente');
  });

  test('displays the provisional calibration cohort after opening its tab', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_CALIBRATION, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where calibration hides that a cohort has too few closures to recalibrate.
    await arrangeCalculator(page);
    // quality: allow-deep-link (panel root is fixture setup; the tested navigation uses the sidebar link).
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Calibración', exact: true }).click();
    await expect(page.getByText('Datos insuficientes', { exact: true })).toHaveText('Datos insuficientes');
    await expect(page.getByText(/Cierres: 1 \/ mínimo 3/)).toContainText('Mediana real interna: 24 h');
  });

  test('loads the full evidence history on demand instead of truncating it in the summary', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_CALIBRATION, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Catches the bug where the calibration summary has no path to retained closure evidence.
    const calls = await arrangeCalculator(page);
    // quality: allow-deep-link (panel root is fixture setup; the tested navigation uses the sidebar link).
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Calibración', exact: true }).click();
    await page.getByTestId('calculator-estimate-detail-44').click();
    await expect(page.getByText('Alta de clientes con reglas de negocio completas', { exact: true })).toHaveText('Alta de clientes con reglas de negocio completas');
    await expect(page.getByText('Bitácora completa con enlaces', { exact: true })).toHaveText('Bitácora completa con enlaces');
    expect(calls.filter((call) => call.apiPath === 'requirement-calculator/estimates/44/' && call.method === 'GET')).toHaveLength(1);
    expect(calls.filter((call) => call.apiPath === 'requirement-calculator/estimates/44/actuals/' && call.method === 'GET')).toHaveLength(1);
  });

  test('records a correction against the latest closure and reloads calibration', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_CALIBRATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Catches the bug where a correction overwrites evidence instead of superseding the latest actual.
    const calls = await arrangeCalculator(page);
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Calibración', exact: true }).click();
    await page.getByTestId('calculator-actual-estimate_id').selectOption('44');
    await page.getByTestId('calculator-actual-actual_hours').fill('26');
    await page.getByTestId('calculator-actual-hourly_cost_cop').fill('61000');
    await page.getByTestId('calculator-actual-evidence').fill('Bitácora validada');
    await page.getByTestId('calculator-actual-cause').fill('Corrección de alcance');
    await page.getByTestId('calculator-actual-submit').click();
    await expect(page.getByText('Cambios guardados; documento sincronizado.')).toHaveCount(0);
    const actual = calls.find((call) => call.apiPath === 'requirement-calculator/actuals/' && call.method === 'POST');
    expect(JSON.parse(actual.body)).toMatchObject({ estimate_id: '44', supersedes_id: 77, actual_hours: '26', hourly_cost_cop: '61000' });
    expect(calls.filter((call) => call.apiPath === 'requirement-calculator/calibration/' && call.method === 'GET').length).toBeGreaterThanOrEqual(2);
    await expect(page.getByText(/Cierres: 2 \/ mínimo 3/)).toContainText('Mediana real interna: 26 h');
  });

  test('shows a rejected closure without replacing its current evidence', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_CALIBRATION, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the bug where a rejected closure looks saved and erases the correction context.
    await arrangeCalculator(page, { actualStatus: 400 });
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Calibración', exact: true }).click();
    await page.getByTestId('calculator-actual-estimate_id').selectOption('44');
    await page.getByTestId('calculator-actual-actual_hours').fill('26');
    await page.getByTestId('calculator-actual-evidence').fill('Registro incompleto');
    await page.getByTestId('calculator-actual-cause').fill('Corrección');
    await page.getByTestId('calculator-actual-submit').click();
    await expect(page.getByTestId('calculator-error')).toContainText('La evidencia es obligatoria.');
    await expect(page.getByText('Bitácora', { exact: true })).toHaveText('Bitácora');
  });

  test('shows a server failure when recording a closure', {
    tag: [...ADMIN_REQUIREMENT_CALCULATOR_CALIBRATION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches the bug where a 500 closure failure falsely advances calibration.
    await arrangeCalculator(page, { actualStatus: 500 });
    await openCalculatorFromNavigation(page);
    await page.getByRole('button', { name: 'Calibración', exact: true }).click();
    await page.getByTestId('calculator-actual-estimate_id').selectOption('44');
    await page.getByTestId('calculator-actual-actual_hours').fill('26');
    await page.getByTestId('calculator-actual-evidence').fill('Bitácora nueva');
    await page.getByTestId('calculator-actual-cause').fill('Corrección');
    await page.getByTestId('calculator-actual-submit').click();
    await expect(page.getByTestId('calculator-error')).toContainText('No fue posible registrar el cierre.');
  });
});
