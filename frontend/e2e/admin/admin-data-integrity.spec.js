/**
 * Data-integrity E2E coverage. These specs catch regressions that hide a
 * persisted finding, apply a correction without its preview, or lose the
 * reason and audit trail that make an integrity decision reversible.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { buildDataIntegrityApi } from '../helpers/data-integrity-fixture.js';
import {
  ADMIN_DATA_INTEGRITY_FINDINGS,
  ADMIN_DATA_INTEGRITY_FIX,
  ADMIN_DATA_INTEGRITY_HISTORY,
  ADMIN_DATA_INTEGRITY_REVIEW,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

async function arrange(page, options = {}) {
  const fixture = buildDataIntegrityApi(options);
  await setAuthLocalStorage(page, {
    token: 'data-integrity-token',
    userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockApi(page, fixture.handler);
  return fixture;
}

async function openFromDesktopDashboard(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Integridad de datos', exact: true }).click();
  await expect(page).toHaveURL(/\/es-co\/panel\/data-integrity/);
  await expect(page.getByTestId('data-integrity-page')).toBeVisible();
}

async function openIntegrity(page, options = {}) {
  const fixture = await arrange(page, options);
  await page.goto('/es-co/panel/data-integrity', { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('data-integrity-page')).toBeVisible();
  return fixture;
}

async function selectFinding(page) {
  await page.getByRole('checkbox', { name: 'Incluir en la corrección', exact: true }).check();
  await page.getByTestId('integrity-preview').click();
  await expect(page.getByTestId('integrity-confirm-modal')).toContainText('Carpeta: Sin carpeta → Actas · 51');
}

async function fillReason(page, reason) {
  await page.getByLabel('Motivo', { exact: true }).fill(reason);
}

// Bug caught: a completed review is not refreshed into the persisted finding list.
test('shows the finding after a completed review', { tag: [...ADMIN_DATA_INTEGRITY_FINDINGS, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  const fixture = await openIntegrity(page);
  await page.getByTestId('integrity-scan').click();
  await expect(page.getByText('Revisión más reciente: Completada', { exact: true })).toBeVisible();
  await expect(page.getByTestId('integrity-finding-DC9')).toContainText('Acta de entrega');
  expect(fixture.state.calls.scans).toHaveLength(1);
});

// Bug caught: a failed review replaces the last completed result instead of explaining its status.
test('preserves the last result after a failed review', { tag: [...ADMIN_DATA_INTEGRITY_FINDINGS, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
  await openIntegrity(page, { scanFailure: true });
  await page.getByTestId('integrity-scan').click();
  await expect(page.getByRole('alert')).toContainText('La revisión falló. Se conserva el último resultado válido.');
  await expect(page.getByTestId('integrity-finding-DC9')).toContainText('Documento sin carpeta');
});

// Bug caught: a scoped review starts without the record identifier the operator selected.
test('shows a rejected review request', { tag: [...ADMIN_DATA_INTEGRITY_FINDINGS, '@role:admin', '@outcome:error'] }, async ({ page }) => {
  const fixture = await openIntegrity(page);
  await page.getByLabel('Qué revisar', { exact: true }).selectOption('client');
  await expect(page.getByLabel('Identificador del registro', { exact: true })).toBeVisible();
  await page.getByTestId('integrity-scan').click();
  await expect(page.getByRole('alert')).toContainText('Completa identificador del registro.');
  expect(fixture.state.calls.scans).toHaveLength(0);
});

// Bug caught: confirming a valid preview fails to persist the correction or its required reason.
test('records a previewed correction', { tag: [...ADMIN_DATA_INTEGRITY_FIX, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  const fixture = await openIntegrity(page);
  await selectFinding(page);
  await fillReason(page, 'Se reasigna al archivo de actas vigente.');
  await page.getByTestId('integrity-confirm').click();
  await expect(page.getByRole('status')).toContainText('La operación quedó registrada.');
  await expect(page.getByTestId('integrity-empty')).toContainText('No hay hallazgos en esta consulta');
  expect(fixture.state.calls.applies[0].reason).toBe('Se reasigna al archivo de actas vigente.');
});

// Bug caught: a blocked preview still exposes a confirmation that could modify protected evidence.
test('blocks a protected correction preview', { tag: [...ADMIN_DATA_INTEGRITY_FIX, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
  await openIntegrity(page, { blockedPreview: true });
  await page.getByRole('checkbox', { name: 'Incluir en la corrección', exact: true }).check();
  await page.getByTestId('integrity-preview').click();
  await expect(page.getByTestId('integrity-confirm-modal')).toContainText('El documento fue archivado y no puede moverse.');
  await expect(page.getByTestId('integrity-confirm')).toHaveCount(0);
});

// Bug caught: a stale impact hash dismisses the modal without explaining that no correction was applied.
test('explains a stale correction preview', { tag: [...ADMIN_DATA_INTEGRITY_FIX, '@role:admin', '@outcome:error'] }, async ({ page }) => {
  await openIntegrity(page, { applyStatus: 409 });
  await selectFinding(page);
  await fillReason(page, 'Se intentó con una vista previa vigente.');
  await page.getByTestId('integrity-confirm').click();
  await expect(page.getByRole('alert')).toContainText('La vista previa ya no coincide con los datos actuales.');
  await expect(page.getByTestId('integrity-confirm-modal')).toContainText('Revisa antes de confirmar');
});

// Bug caught: accepting an intentional finding drops the reason or does not remove it from pending work.
test('accepts an intentional finding', { tag: [...ADMIN_DATA_INTEGRITY_REVIEW, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  const fixture = await openIntegrity(page);
  await page.getByRole('button', { name: 'Aceptar como intencional', exact: true }).click();
  await fillReason(page, 'El documento queda fuera de carpeta por decisión comercial.');
  await page.getByTestId('integrity-confirm').click();
  await expect(page.getByTestId('integrity-empty')).toContainText('No hay hallazgos en esta consulta');
  expect(fixture.state.calls.reviews[0].action).toBe('accept');
});

// Bug caught: an accepted finding cannot return to the pending queue with a new audit reason.
test('reopens an accepted finding', { tag: [...ADMIN_DATA_INTEGRITY_REVIEW, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  await openIntegrity(page, { finding: { is_accepted: true } });
  await page.getByLabel('Estado', { exact: true }).selectOption('accepted');
  await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click();
  await page.getByRole('button', { name: 'Reabrir', exact: true }).click();
  await fillReason(page, 'Se detectó evidencia nueva.');
  await page.getByTestId('integrity-confirm').click();
  await page.getByLabel('Estado', { exact: true }).selectOption('pending');
  await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click();
  await expect(page.getByTestId('integrity-finding-DC9')).toContainText('Documento sin carpeta');
});

// Bug caught: a failed review request appears as a successful audit decision.
test('keeps a finding pending after a failed review', { tag: [...ADMIN_DATA_INTEGRITY_REVIEW, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
  await openIntegrity(page, { reviewStatus: 500 });
  await page.getByRole('button', { name: 'Aceptar como intencional', exact: true }).click();
  await fillReason(page, 'No debe guardarse.');
  await page.getByTestId('integrity-confirm').click();
  await expect(page.getByRole('alert')).toContainText('La decisión fue modificada por otra persona.');
  await expect(page.getByTestId('integrity-confirm-modal')).toContainText('Documento sin carpeta');
});

// Bug caught: a conflicting review closes the modal and makes the current decision invisible.
test('explains a conflicting review', { tag: [...ADMIN_DATA_INTEGRITY_REVIEW, '@role:admin', '@outcome:error'] }, async ({ page }) => {
  await openIntegrity(page, { reviewStatus: 409 });
  await page.getByRole('button', { name: 'Aceptar como intencional', exact: true }).click();
  await fillReason(page, 'No debe sustituir una decisión ajena.');
  await page.getByTestId('integrity-confirm').click();
  await expect(page.getByRole('alert')).toContainText('La decisión fue modificada por otra persona.');
  await expect(page.getByTestId('integrity-confirm-modal')).toContainText('Motivo');
});

async function openHistory(page, options = {}) {
  const fixture = await openIntegrity(page, options);
  await page.getByRole('tab', { name: 'Historial', exact: true }).click();
  await expect(page.getByTestId('integrity-history')).toContainText('Corrección #701');
  return fixture;
}

// Bug caught: a reversible correction cannot be restored after its undo preview is approved.
test('records an approved undo', { tag: [...ADMIN_DATA_INTEGRITY_HISTORY, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  const fixture = await openHistory(page);
  await page.getByRole('button', { name: 'Revisar deshacer', exact: true }).click();
  await fillReason(page, 'La carpeta elegida era incorrecta.');
  await page.getByTestId('integrity-confirm').click();
  await expect(page.getByRole('status')).toContainText('La operación quedó registrada.');
  await expect(page.getByTestId('integrity-history')).toContainText('Deshacer #703');
  expect(fixture.state.calls.undos[0].reason).toBe('La carpeta elegida era incorrecta.');
});

// Bug caught: a blocked undo exposes a confirm action despite later changes.
test('blocks an unsafe undo preview', { tag: [...ADMIN_DATA_INTEGRITY_HISTORY, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
  await openHistory(page, { undoBlocked: true });
  await page.getByRole('button', { name: 'Revisar deshacer', exact: true }).click();
  await expect(page.getByTestId('integrity-confirm-modal')).toContainText('Hay cambios posteriores que impiden deshacer.');
  await expect(page.getByTestId('integrity-confirm')).toHaveCount(0);
});

// Bug caught: an already reverted operation hides the conflict after the user supplies a reason.
test('explains a rejected undo', { tag: [...ADMIN_DATA_INTEGRITY_HISTORY, '@role:admin', '@outcome:error'] }, async ({ page }) => {
  await openHistory(page, { undoStatus: 409 });
  await page.getByRole('button', { name: 'Revisar deshacer', exact: true }).click();
  await fillReason(page, 'Se requiere comprobar el historial.');
  await page.getByTestId('integrity-confirm').click();
  await expect(page.getByRole('alert')).toContainText('La operación ya fue revertida.');
  await expect(page.getByTestId('integrity-confirm-modal')).toContainText('Revisa antes de confirmar');
});


test('shows the accepted finding decision', { tag: [...ADMIN_DATA_INTEGRITY_REVIEW, '@role:admin', '@outcome:display'] }, async ({ page }) => {
  // quality: allow-deep-link (the localized Dashboard is the entry point; integrity is reached through its sidebar link)
  await arrange(page, { finding: { is_accepted: true } });
  await openFromDesktopDashboard(page);
  await page.getByLabel('Estado', { exact: true }).selectOption('accepted');
  await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click();
  const finding = page.getByTestId('integrity-finding-DC9');
  await expect(finding).toContainText('Acta de entrega');
  await expect(finding.getByRole('button', { name: 'Reabrir', exact: true })).toBeEnabled();
});

test('shows the persisted correction audit record', { tag: [...ADMIN_DATA_INTEGRITY_HISTORY, '@role:admin', '@outcome:display'] }, async ({ page }) => {
  // quality: allow-deep-link (the localized Dashboard is the entry point; integrity is reached through its sidebar link)
  await arrange(page);
  await openFromDesktopDashboard(page);
  await page.getByRole('tab', { name: 'Historial', exact: true }).click();
  const history = page.getByTestId('integrity-history');
  await expect(history).toContainText('Corrección #701');
  await expect(history).toContainText('Corrección anterior');
  await expect(history).toContainText('admin@example.test');
});
