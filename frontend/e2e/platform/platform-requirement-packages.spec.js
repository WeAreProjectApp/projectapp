// qa: draft-unvalidated (2026-11-12 — app not running)
/**
 * E2E coverage for requirement packages in the client project workspace.
 * Bugs caught: an unreachable package workspace, hidden examples, a request
 * form that drops its payload, or acceptance without recorded consent.
 */
import { test, expect } from '../helpers/test.js';
import {
  mockRequirementPackagesWorkspace,
  REQUIREMENT_PACKAGE_PROJECT,
  REQUIREMENT_PACKAGE_ORDER_ID,
  REQUIREMENT_PACKAGE_QUOTE_DIGEST,
} from '../helpers/requirement-packages-workspace.js';
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js';
import {
  PLATFORM_REQUIREMENT_PACKAGE_DECISION,
  PLATFORM_REQUIREMENT_PACKAGES_ACCESS,
  PLATFORM_REQUIREMENT_PACKAGES_PURCHASE,
  PLATFORM_REQUIREMENT_PACKAGES_REQUEST,
} from '../helpers/flow-tags.js';

const personalClientToken = 'eyJhbGciOiJub25lIn0.eyJ1c2VyX2lkIjo5MDAyfQ.signature';

async function openPackagesFromProject(page) {
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: /^(Mis )?proyectos$/, exact: false })).toBeVisible();
  await page.getByTestId(`project-row-${REQUIREMENT_PACKAGE_PROJECT.id}`).click();
  await expect(page.getByRole('heading', { name: REQUIREMENT_PACKAGE_PROJECT.name, exact: true })).toHaveText(REQUIREMENT_PACKAGE_PROJECT.name);
  await page.getByRole('link', { name: 'Paquetes de requerimientos', exact: true }).click();
  await expect(page).toHaveURL(/\/platform\/projects\/1\/packages$/);
}

test.describe('Platform requirement packages', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformClient, accessToken: personalClientToken });
  });

  test('opens package examples from the project and sends the requested outcome for evaluation', {
    tag: ['@outcome:success', ...PLATFORM_REQUIREMENT_PACKAGES_REQUEST, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: the project navigation hides package examples or the submitted request loses its title or context.
    const { calls } = await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    await openPackagesFromProject(page);

    await expect(page.getByTestId('requirement-packages-workspace')).toContainText('Describe el resultado que necesitas');
    await expect(page.getByTestId('package-size-XS')).toContainText('Ajuste puntual sobre una salida existente.');
    await expect(page.getByTestId('package-size-XS')).toContainText('Cambiar el texto de bienvenida de Atlas');
    await page.getByLabel('Título del cambio').fill('Aclarar el estado del pedido');
    await page.getByLabel('Qué resultado necesitas y en qué contexto').fill('Mostrar el estado confirmado en la ficha del pedido.');
    await page.getByRole('button', { name: 'Enviar a evaluación', exact: true }).click();

    await expect(page.getByTestId('package-request-detail')).toContainText('Aclarar el estado del pedido');
    expect(calls.filter((call) => call.apiPath === 'requirement-packages/projects/1/requests/')).toHaveLength(1);
    expect(calls.find((call) => call.apiPath === 'requirement-packages/projects/1/requests/').body).toMatchObject({
      title: 'Aclarar el estado del pedido',
      description: 'Mostrar el estado confirmado en la ficha del pedido.',
    });
  });

  test('shows the request form and the size guide after project navigation', {
    tag: ['@outcome:display', ...PLATFORM_REQUIREMENT_PACKAGES_REQUEST, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: the package page loses the client request form or the size explanation that makes it actionable.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    await openPackagesFromProject(page);

    await expect(page.getByRole('heading', { name: 'Solicitar un cambio', exact: true })).toHaveText('Solicitar un cambio');
    await expect(page.getByLabel('Título del cambio')).toHaveAttribute('maxlength', '300');
    await expect(page.getByTestId('package-size-S')).toContainText('Agregar un filtro a un listado existente');
  });

  test('keeps the request visible when the server rejects an incomplete evaluation request', {
    tag: ['@outcome:error', ...PLATFORM_REQUIREMENT_PACKAGES_REQUEST, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a rejected request clears client input or falsely looks like it entered the queue.
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient, failures: { request: 400 } });
    await openPackagesFromProject(page);

    await page.getByLabel('Título del cambio').fill('Estado del pedido');
    await page.getByLabel('Qué resultado necesitas y en qué contexto').fill('Necesito una explicación concreta para el cliente.');
    await page.getByRole('button', { name: 'Enviar a evaluación', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Describe el resultado esperado antes de enviarlo.');
    await expect(page.getByLabel('Título del cambio')).toHaveValue('Estado del pedido');
  });

  test('preserves the client request draft when the evaluation service fails', {
    tag: ['@outcome:failure', ...PLATFORM_REQUIREMENT_PACKAGES_REQUEST, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a 500 after submit clears the requested outcome before the client can retry it.
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient, failures: { request: 500 } });
    await openPackagesFromProject(page);

    await page.getByLabel('Título del cambio').fill('Mantener el resumen semanal');
    await page.getByLabel('Qué resultado necesitas y en qué contexto').fill('Necesito consultar el resumen semanal dentro de Atlas.');
    await page.getByRole('button', { name: 'Enviar a evaluación', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Describe el resultado esperado antes de enviarlo.');
    await expect(page.getByLabel('Qué resultado necesitas y en qué contexto')).toHaveValue('Necesito consultar el resumen semanal dentro de Atlas.');
  });

  test('creates an external-payment order only after package conditions are accepted', {
    tag: ['@outcome:success', ...PLATFORM_REQUIREMENT_PACKAGES_PURCHASE, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: the purchase form creates an order before the client accepts the displayed conditions.
    const { calls } = await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    await openPackagesFromProject(page);

    await expect(page.getByText(/Total con impuestos:/)).toContainText('1.190.000');
    const payment = page.getByRole('button', { name: 'Solicitar pago por otro medio', exact: true });
    await expect(payment).toBeDisabled();
    await page.getByLabel('He leído y acepto las condiciones del paquete').check();
    await payment.click();

    await expect(page.getByText(/Paquete Atlas.*Pago pendiente/)).toContainText('1.190.000');
    expect(calls.find((call) => call.apiPath === 'requirement-packages/projects/1/orders/').body).toMatchObject({
      package_id: 101,
      method: 'external',
      conditions_accepted: true,
      quote_digest: REQUIREMENT_PACKAGE_QUOTE_DIGEST,
    });
  });

  test('displays catalog terms and the concrete tax-inclusive package total', {
    tag: ['@outcome:display', ...PLATFORM_REQUIREMENT_PACKAGES_PURCHASE, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: the purchase page hides the package conditions or total that the client must review before buying.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    await openPackagesFromProject(page);

    await expect(page.getByRole('heading', { name: 'Comprar un paquete', exact: true })).toHaveText('Comprar un paquete');
    await expect(page.getByText('Válido para Atlas y no transferible.')).toBeVisible();
    await expect(page.getByText(/Total con impuestos:/)).toContainText('1.190.000');
    await expect(page.getByLabel('He leído y acepto las condiciones del paquete')).not.toBeChecked();
  });

  test('reports a failed purchase without creating a paid allowance', {
    tag: ['@outcome:failure', ...PLATFORM_REQUIREMENT_PACKAGES_PURCHASE, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a failed order appears paid or increases the displayed allowance balance.
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient, failures: { order: 500 } });
    await openPackagesFromProject(page);

    await page.getByLabel('He leído y acepto las condiciones del paquete').check();
    await page.getByRole('button', { name: 'Solicitar pago por otro medio', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos crear la compra. Inténtalo de nuevo.');
    await expect(page.getByTestId('package-balance-S')).toHaveText('1');
  });

  test('keeps balances unchanged when an order is rejected as stale', {
    tag: ['@outcome:error', ...PLATFORM_REQUIREMENT_PACKAGES_PURCHASE, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a 409 quote rejection still appears as a new usable package balance.
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient, failures: { order: 409 } });
    await openPackagesFromProject(page);

    await page.getByLabel('He leído y acepto las condiciones del paquete').check();
    await page.getByRole('button', { name: 'Solicitar pago por otro medio', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos crear la compra. Inténtalo de nuevo.');
    await expect(page.getByTestId('package-balance-S')).toHaveText('1');
  });

  test('accepts an offered XS proposal once after the client records consent', {
    tag: ['@outcome:success', ...PLATFORM_REQUIREMENT_PACKAGE_DECISION, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: an offered proposal consumes without consent, repeats the debit, or leaves the balance stale.
    const { state, calls } = await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    state.requests[0].proposal.size = 'XS';
    state.balances.XS = 1;
    await openPackagesFromProject(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();
    await expect(page.getByText(`El cupo se descontará de la compra ${REQUIREMENT_PACKAGE_ORDER_ID}.`)).toBeVisible();
    const accept = page.getByTestId('package-accept');
    await expect(accept).toBeDisabled();
    await page.getByLabel('Confirmo el alcance, la talla y la agenda orientativa de esta propuesta.').check();
    await accept.click();

    await expect(page.getByTestId('package-request-detail')).toContainText('Aceptada');
    await expect(page.getByTestId('package-balance-XS')).toHaveText('0');
    const decisions = calls.filter((call) => call.apiPath === 'requirement-packages/projects/1/requests/701/decide/');
    expect(decisions).toHaveLength(1);
    expect(decisions[0].body).toMatchObject({ decision: 'accept', proposal_id: 801, order_id: REQUIREMENT_PACKAGE_ORDER_ID });
  });

  test('displays the proposed size, scope, and source purchase before consent', {
    tag: ['@outcome:display', ...PLATFORM_REQUIREMENT_PACKAGE_DECISION, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: an offered proposal loses its size, scope, or purchase source before the client decides.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    await openPackagesFromProject(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();

    await expect(page.getByTestId('package-request-detail')).toContainText('Talla S');
    await expect(page.getByTestId('package-request-detail')).toContainText('Mostrar el estado confirmado del pedido.');
    await expect(page.getByText(`El cupo se descontará de la compra ${REQUIREMENT_PACKAGE_ORDER_ID}.`)).toBeVisible();
  });

  test('keeps the XS balance when a consented decision fails', {
    tag: ['@outcome:failure', ...PLATFORM_REQUIREMENT_PACKAGE_DECISION, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a failed acceptance decrements the client-visible balance despite no recorded decision.
    const { state } = await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient, failures: { decision: 500 } });
    state.requests[0].proposal.size = 'XS';
    state.balances.XS = 1;
    await openPackagesFromProject(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();
    await page.getByLabel('Confirmo el alcance, la talla y la agenda orientativa de esta propuesta.').check();
    await page.getByTestId('package-accept').click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos registrar tu decisión. Inténtalo de nuevo.');
    await expect(page.getByTestId('package-balance-XS')).toHaveText('1');
  });

  test('does not consume an XS allowance when a consented decision conflicts', {
    tag: ['@outcome:error', ...PLATFORM_REQUIREMENT_PACKAGE_DECISION, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a 409 decision conflict debits the client balance without an accepted decision.
    const { state } = await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient, failures: { decision: 409 } });
    state.requests[0].proposal.size = 'XS';
    state.balances.XS = 1;
    await openPackagesFromProject(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();
    await page.getByLabel('Confirmo el alcance, la talla y la agenda orientativa de esta propuesta.').check();
    await page.getByTestId('package-accept').click();

    await expect(page.getByRole('alert')).toHaveText('No pudimos registrar tu decisión. Inténtalo de nuevo.');
    await expect(page.getByTestId('package-balance-XS')).toHaveText('1');
  });

  test('lets the project owner enter the package workspace from the visible project navigation', {
    tag: ['@outcome:success', ...PLATFORM_REQUIREMENT_PACKAGES_ACCESS, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: an entitled client can see a project but cannot enter its package workspace.
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    await openPackagesFromProject(page);

    await expect(page.getByTestId('requirement-packages-workspace')).toContainText('Tus cupos disponibles');
  });

  test('keeps administrator-only commerce controls out of the client workspace', {
    tag: ['@outcome:display', ...PLATFORM_REQUIREMENT_PACKAGES_ACCESS, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: a client workspace exposes the team payment-confirmation or example-administration controls.
    // quality: allow-deep-link (authenticated shell entry; the test reaches the package view through visible navigation)
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
    await openPackagesFromProject(page);

    await expect(page.getByText('Confirmar pago y activar cupos', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Administrar ejemplos', { exact: true })).toHaveCount(0);
    await expect(page.getByTestId('package-balance-XS')).toHaveText('2');
  });

  test('does not let an administrator session enable the client consent action', {
    tag: ['@outcome:error', ...PLATFORM_REQUIREMENT_PACKAGES_ACCESS, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: an administrative session can substitute the client’s consent on an offered proposal.
    await setPlatformAuth(page, { user: { ...mockPlatformClient, role: 'admin' }, accessToken: 'e2e-admin-token' });
    await mockRequirementPackagesWorkspace(page, { user: { ...mockPlatformClient, role: 'admin' } });
    await openPackagesFromProject(page);

    await page.getByRole('button', { name: 'Ver solicitud', exact: true }).click();
    await expect(page.getByLabel('Confirmo el alcance, la talla y la agenda orientativa de esta propuesta.')).toBeDisabled();
    await expect(page.getByTestId('package-accept')).toBeDisabled();
    await expect(page.getByTestId('package-accept')).toHaveAttribute('title', 'La aceptación debe realizarla el cliente desde su propia sesión.');
  });

  test('does not reveal balances when the package overview fails to load', {
    tag: ['@outcome:failure', ...PLATFORM_REQUIREMENT_PACKAGES_ACCESS, '@role:platform-client'],
  }, async ({ page }) => {
    // Bug caught: an overview failure leaves stale allowance balances visible to a client who cannot load the workspace.
    await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient, failures: { overview: 500 } });
    await openPackagesFromProject(page);

    await expect(page.getByRole('alert')).toHaveText('No pudimos cargar los paquetes.');
    await expect(page.getByTestId('package-balance-XS')).toHaveCount(0);
  });
});
