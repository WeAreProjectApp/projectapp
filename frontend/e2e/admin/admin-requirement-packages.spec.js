// qa: draft-unvalidated (2026-11-12 — app not running)
/**
 * E2E coverage for the Panel queue, manual evaluation, package commerce and
 * examples. Bugs caught: a hidden queue, stale evaluations, payments that
 * credit on failure, or examples that silently overwrite another revision.
 */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  mockRequirementPackagesWorkspace,
  REQUIREMENT_PACKAGE_PROJECT,
  REQUIREMENT_PACKAGE_ORDER_ID,
} from '../helpers/requirement-packages-workspace.js';
import {
  ADMIN_REQUIREMENT_PACKAGE_COMMERCE,
  ADMIN_REQUIREMENT_PACKAGE_EVALUATION,
  ADMIN_REQUIREMENT_PACKAGE_EXAMPLES,
  ADMIN_REQUIREMENT_PACKAGES_QUEUE,
} from '../helpers/flow-tags.js';

async function openQueue(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Solicitudes por tallas', exact: true }).click();
  await expect(page).toHaveURL(/\/panel\/requirement-packages$/);
  await expect(page.getByRole('heading', { name: 'Solicitudes por tallas', exact: true })).toHaveText('Solicitudes por tallas');
}

async function openProjectWorkspace(page) {
  await page.getByRole('button', { name: 'Seleccionar proyecto', exact: true }).click();
  await page.getByRole('button', { name: REQUIREMENT_PACKAGE_PROJECT.name, exact: true }).click();
  await expect(page.getByTestId('requirement-packages-workspace')).toContainText('Tus cupos disponibles');
}

test.describe('Admin requirement packages', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-panel-token',
      userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
    });
  });

  test('filters the queue from the Panel and keeps the matching project visible', {
    tag: ['@outcome:display', ...ADMIN_REQUIREMENT_PACKAGES_QUEUE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: the queue search removes the only matching request or its project destination.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, {
      admin: true,
      queueRows: [
        { id: 701, title: 'Mostrar el estado del pedido', project_id: 1, project_name: 'Atlas Workspace', status: 'offered' },
        { id: 702, title: 'Enviar el resumen mensual', project_id: 2, project_name: 'Sin relación', status: 'pending' },
      ],
    });
    await openQueue(page);

    await expect(page.getByText('Enviar el resumen mensual', { exact: true })).toBeVisible();
    await page.getByLabel('Buscar proyecto o solicitud').fill('Atlas');
    await expect(page.getByText('Mostrar el estado del pedido', { exact: true })).toBeVisible();
    await expect(page.getByText('Sin relación', { exact: false })).not.toBeVisible();
  });

  test('opens the selected queue request in its matching project workspace', {
    tag: ['@outcome:success', ...ADMIN_REQUIREMENT_PACKAGES_QUEUE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a queue row opens a different project or drops the selected request context.
    await mockRequirementPackagesWorkspace(page, { admin: true });
    await openQueue(page);

    await page.getByRole('link', { name: 'Ver detalle', exact: true }).click();

    await expect(page).toHaveURL(/\/panel\/requirement-packages\?project=1&request=701$/);
    await expect(page.getByTestId('package-request-detail')).toContainText('Mostrar el estado del pedido');
  });

  test('reports a forbidden queue response without inventing an empty result', {
    tag: ['@outcome:error', ...ADMIN_REQUIREMENT_PACKAGES_QUEUE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a 403 queue response is mistaken for an empty queue and hides the permission problem.
    await mockRequirementPackagesWorkspace(page, { admin: true, failures: { queue: 403 } });
    await openQueue(page);

    await expect(page.getByRole('alert')).toHaveText('No pudimos cargar la bandeja.');
    await expect(page.getByText('Todavía no hay solicitudes.')).toHaveCount(0);
  });

  test('keeps the Panel shell available when the request queue fails to load', {
    tag: ['@outcome:failure', ...ADMIN_REQUIREMENT_PACKAGES_QUEUE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a queue transport failure replaces the Panel page with a blank or misleading empty state.
    await mockRequirementPackagesWorkspace(page, { admin: true, failures: { queue: 500 } });
    await openQueue(page);

    await expect(page.getByRole('alert')).toHaveText('No pudimos cargar la bandeja.');
    await expect(page.getByRole('button', { name: 'Seleccionar proyecto', exact: true })).toBeVisible();
  });

  test('starts evaluation and publishes a manual size proposal without consuming a cup', {
    tag: ['@outcome:success', ...ADMIN_REQUIREMENT_PACKAGE_EVALUATION, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: publishing a proposal fails to preserve the team’s size, schedule, and supporting signal.
    const { state, calls } = await mockRequirementPackagesWorkspace(page, { admin: true });
    state.requests[0].status = 'pending';
    state.requests[0].proposal = null;
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();
    await page.getByRole('button', { name: 'Comenzar evaluación', exact: true }).click();
    await page.getByLabel('Alcance propuesto').fill('Mostrar el estado confirmado sin crear un flujo nuevo.');
    await page.getByLabel('Por qué corresponde esta talla').fill('Reutiliza datos y vista existentes.');
    await page.getByLabel('Desde').fill('2026-11-17');
    await page.getByLabel('Hasta').fill('2026-11-20');
    await page.getByLabel('Cambia una salida visible').check();
    await page.getByRole('button', { name: 'Enviar propuesta al cliente', exact: true }).click();

    await expect(page.getByTestId('package-request-detail')).toContainText('Pendiente de aceptación');
    expect(calls.find((call) => call.apiPath === 'requirement-packages/projects/1/requests/701/evaluate/')).toBeTruthy();
    expect(calls.find((call) => call.apiPath === 'requirement-packages/projects/1/requests/701/offer/').body).toMatchObject({
      size: 'XS',
      delivery_from: '2026-11-17',
      delivery_until: '2026-11-20',
      signal_ids: ['signal-xs'],
    });
  });

  test('shows the offered scope, supporting signal, and indicative schedule before a client decides', {
    tag: ['@outcome:display', ...ADMIN_REQUIREMENT_PACKAGE_EVALUATION, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: an evaluator loses the scope, signal guidance, or promised schedule while reviewing a proposal.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, { admin: true });
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();

    await expect(page.getByTestId('package-request-detail')).toContainText('Talla S');
    await expect(page.getByTestId('package-request-detail')).toContainText('Mostrar el estado confirmado del pedido.');
    await expect(page.getByTestId('package-request-detail')).toContainText('2026-11-17 — 2026-11-20');
    await expect(page.getByLabel('Reutiliza una vista existente')).toBeVisible();
  });

  test('shows the server validation error when the evaluation proposal is rejected', {
    tag: ['@outcome:error', ...ADMIN_REQUIREMENT_PACKAGE_EVALUATION, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a rejected proposal disappears or is shown as available to the client.
    const { state } = await mockRequirementPackagesWorkspace(page, { admin: true, failures: { offer: 400 } });
    state.requests[0].status = 'evaluating';
    state.requests[0].proposal = null;
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();
    await page.getByLabel('Alcance propuesto').fill('Mostrar un estado existente.');
    await page.getByLabel('Por qué corresponde esta talla').fill('No cambia el proceso del pedido.');
    await page.getByLabel('Desde').fill('2026-11-17');
    await page.getByLabel('Hasta').fill('2026-11-20');
    await page.getByLabel('Cambia una salida visible').check();
    await page.getByRole('button', { name: 'Enviar propuesta al cliente', exact: true }).click();

    await expect(page.getByTestId('package-proposal-editor').getByRole('alert')).toHaveText('Selecciona las señales aplicables antes de enviar la propuesta.');
  });

  test('preserves the proposal draft when publishing fails at the server', {
    tag: ['@outcome:failure', ...ADMIN_REQUIREMENT_PACKAGE_EVALUATION, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a 500 during publication erases the evaluator’s prepared scope and explanation.
    const { state } = await mockRequirementPackagesWorkspace(page, { admin: true, failures: { offer: 500 } });
    state.requests[0].status = 'evaluating';
    state.requests[0].proposal = null;
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();
    await page.getByLabel('Alcance propuesto').fill('Mostrar el indicador del pedido en la ficha actual.');
    await page.getByLabel('Por qué corresponde esta talla').fill('Se apoya en una salida ya disponible.');
    await page.getByLabel('Desde').fill('2026-11-17');
    await page.getByLabel('Hasta').fill('2026-11-20');
    await page.getByLabel('Cambia una salida visible').check();
    await page.getByRole('button', { name: 'Enviar propuesta al cliente', exact: true }).click();

    await expect(page.getByTestId('package-proposal-editor').getByRole('alert')).toHaveText('Selecciona las señales aplicables antes de enviar la propuesta.');
    await expect(page.getByLabel('Alcance propuesto')).toHaveValue('Mostrar el indicador del pedido en la ficha actual.');
  });

  test('confirms an external payment and refreshes the project balance', {
    tag: ['@outcome:success', ...ADMIN_REQUIREMENT_PACKAGE_COMMERCE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a confirmed external payment does not activate its package allowances.
    const { calls } = await mockRequirementPackagesWorkspace(page, { admin: true });
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByLabel('Fecha real del pago').fill('2026-11-12T09:30');
    await page.getByLabel('Referencia del pago').fill('ATLAS-PAID-01');
    await page.getByRole('button', { name: 'Confirmar pago y activar cupos', exact: true }).click();

    await expect(page.getByText(/Paquete Atlas.*Pagada/)).toContainText('1.190.000');
    await expect(page.getByTestId('package-balance-S')).toHaveText('2');
    expect(calls.find((call) => call.apiPath === `requirement-packages/projects/1/orders/${REQUIREMENT_PACKAGE_ORDER_ID}/confirm-external/`).body).toMatchObject({
      payment_reference: 'ATLAS-PAID-01',
    });
  });

  test('displays the concrete purchase and allowance movement history', {
    tag: ['@outcome:display', ...ADMIN_REQUIREMENT_PACKAGE_COMMERCE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: commerce history omits the pending order or the prior debit that explains the current balance.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, { admin: true });
    await openQueue(page);
    await openProjectWorkspace(page);

    await expect(page.getByText('Paquete Atlas', { exact: false })).toBeVisible();
    await expect(page.getByText('Pago pendiente', { exact: true })).toBeVisible();
    await expect(page.getByText('Consumo · 1 S', { exact: false })).toBeVisible();
  });

  test('does not credit a balance when external payment confirmation fails', {
    tag: ['@outcome:failure', ...ADMIN_REQUIREMENT_PACKAGE_COMMERCE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a failed payment confirmation reports success or adds a usable cup.
    await mockRequirementPackagesWorkspace(page, { admin: true, failures: { external: 500 } });
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByLabel('Fecha real del pago').fill('2026-11-12T09:30');
    await page.getByLabel('Referencia del pago').fill('ATLAS-FAILED-01');
    await page.getByRole('button', { name: 'Confirmar pago y activar cupos', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos confirmar el pago externo.');
    await expect(page.getByTestId('package-balance-S')).toHaveText('1');
  });

  test('keeps the balance unchanged when payment confirmation is rejected by validation', {
    tag: ['@outcome:error', ...ADMIN_REQUIREMENT_PACKAGE_COMMERCE, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a 400 payment confirmation still credits a package allowance.
    await mockRequirementPackagesWorkspace(page, { admin: true, failures: { external: 400 } });
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByLabel('Fecha real del pago').fill('2026-11-12T09:30');
    await page.getByLabel('Referencia del pago').fill('ATLAS-INVALID-01');
    await page.getByRole('button', { name: 'Confirmar pago y activar cupos', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos confirmar el pago externo.');
    await expect(page.getByTestId('package-balance-S')).toHaveText('1');
  });

  test('publishes a project-specific XS example with a revision reason', {
    tag: ['@outcome:success', ...ADMIN_REQUIREMENT_PACKAGE_EXAMPLES, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a project example save loses the example or the audit reason.
    const { calls } = await mockRequirementPackagesWorkspace(page, { admin: true });
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByTestId('package-examples-XS').fill('Cambiar el estado de un pedido de Atlas');
    await page.getByLabel('Motivo de la publicación').fill('Aclarar el ejemplo para Atlas');
    await page.getByRole('button', { name: 'Publicar ejemplos', exact: true }).click();

    await expect(page.getByTestId('package-example-editor')).toContainText('Cambiar el estado de un pedido de Atlas');
    expect(calls.find((call) => call.apiPath === 'requirement-packages/projects/1/examples/').body).toMatchObject({
      examples: { XS: ['Cambiar el estado de un pedido de Atlas'] },
      note: 'Aclarar el ejemplo para Atlas',
    });
  });

  test('shows generic and project-specific example previews before publication', {
    tag: ['@outcome:display', ...ADMIN_REQUIREMENT_PACKAGE_EXAMPLES, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: the editor no longer distinguishes the generic example from the project-specific explanation.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, { admin: true });
    await openQueue(page);

    await expect(page.getByTestId('package-example-editor')).toContainText('Cambiar una etiqueta visible');
    await openProjectWorkspace(page);
    await expect(page.getByTestId('package-example-editor')).toContainText('Cambiar el texto de bienvenida de Atlas');
  });

  test('keeps the editor open when a concurrent example revision is rejected', {
    tag: ['@outcome:error', ...ADMIN_REQUIREMENT_PACKAGE_EXAMPLES, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a stale example revision looks published even though the server rejected it.
    await mockRequirementPackagesWorkspace(page, { admin: true, failures: { examples: 409 } });
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByTestId('package-examples-XS').fill('Ejemplo que debe revisarse');
    await page.getByLabel('Motivo de la publicación').fill('Prueba de concurrencia');
    await page.getByRole('button', { name: 'Publicar ejemplos', exact: true }).click();

    await expect(page.getByTestId('package-example-editor').getByRole('alert')).toHaveText('La versión de ejemplos cambió. Recarga antes de publicar.');
    await expect(page.getByTestId('package-examples-XS')).toHaveValue('Ejemplo que debe revisarse');
  });

  test('preserves an example draft when publication fails at the server', {
    tag: ['@outcome:failure', ...ADMIN_REQUIREMENT_PACKAGE_EXAMPLES, '@role:admin'],
  }, async ({ page }) => {
    // Bug caught: a 500 discards the pending example text even though nothing was published.
    await mockRequirementPackagesWorkspace(page, { admin: true, failures: { examples: 500 } });
    await openQueue(page);
    await openProjectWorkspace(page);

    await page.getByTestId('package-examples-XS').fill('Ejemplo que debe conservarse después del fallo');
    await page.getByLabel('Motivo de la publicación').fill('Verificar conservación ante fallo');
    await page.getByRole('button', { name: 'Publicar ejemplos', exact: true }).click();

    await expect(page.getByTestId('package-example-editor').getByRole('alert')).toHaveText('La versión de ejemplos cambió. Recarga antes de publicar.');
    await expect(page.getByTestId('package-examples-XS')).toHaveValue('Ejemplo que debe conservarse después del fallo');
  });
});
