import { expect, test } from '../helpers/test.js';
import { chooseHostingAction } from '../helpers/accounting-hosting-cycles.js';
import { billingRow, billingServices, openHostingBillingList } from '../helpers/accounting-hosting-row-billing.js';
import { ADMIN_ACCOUNTING_HOSTING_BILLING } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const dialog = page => page.getByRole('dialog', { name: 'Enviar cuenta de cobro' });

async function reviewRow(page, service) {
  await chooseHostingAction(page, service.id, 'send-billing');
  const preview = dialog(page);
  const record = billingRow(service);
  await expect(preview).toContainText(record.project_name);
  await expect(preview).toContainText(record.client_display_name);
  await expect(preview).toContainText(record.domain_url);
  await expect(preview).toContainText(record.billing_email);
  await expect(preview.getByTestId('hosting-period-summary')).toContainText(service.period.join(' — '));
  await expect(preview.getByRole('button', { name: 'Enviar al cliente' })).toBeEnabled();
  await expect(preview).toContainText('PDF adjunto');
  await expect(preview).toContainText('próxima renovación');
  await expect(preview.getByRole('combobox')).toHaveCount(0);
  await expect(preview.getByRole('button', { name: 'Usar este hosting' })).toHaveCount(0);
  await expect(preview).not.toContainText('999.999');
  return preview;
}

test('each hosting row previews only its own account before cancellation', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:display'],
}, async ({ page }, testInfo) => {
  // quality: allow-deep-link (the starting URL is the Spanish Panel home; the operator reaches Hostings through its sidebar link)
  const writes = await openHostingBillingList(page);
  const alfa = await reviewRow(page, billingServices[0]);
  await alfa.screenshot({ path: testInfo.outputPath('fila-alfa.png') });
  await alfa.getByRole('button', { name: 'Cancelar' }).click();
  await expect(alfa).toHaveCount(0);
  const beta = await reviewRow(page, billingServices[1]);
  await expect(beta).not.toContainText('alfa@example.invalid');
  await beta.screenshot({ path: testInfo.outputPath('fila-beta.png') });
  await page.keyboard.press('Escape');
  await expect(beta).toHaveCount(0);
  expect(writes).toEqual([]);
  await expect(page.getByText('Cobro enviado')).toHaveCount(0);
});

test('confirmation posts the decision reviewed for the second row', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const writes = await openHostingBillingList(page);
  await chooseHostingAction(page, 2, 'send-billing');
  await expect(dialog(page)).toContainText('$45.000 COP');
  await dialog(page).getByRole('button', { name: 'Enviar al cliente' }).click();

  await expect(page.getByText('Cuenta de cobro enviada')).toBeVisible();
  expect(writes).toEqual([{ method: 'POST', apiPath: 'accounting/hostings/2/send-collection-account/',
    body: { hosting_payment_id: null, period_version: 'review-2' } }]);
});

test('a period changed since preview asks the operator to review it again', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:failure'],
}, async ({ page }) => {
  const writes = await openHostingBillingList(page, { conflict: true });
  await chooseHostingAction(page, 1, 'send-billing');
  await dialog(page).getByRole('button', { name: 'Enviar al cliente' }).click();

  await expect(page.getByText('No se pudo enviar la cuenta de cobro')).toBeVisible();
  await expect(page.getByText('El período cambió. Consulta de nuevo el período del servicio.')).toBeVisible();
  await expect(page.getByText('Cobro enviado')).toHaveCount(0);
  expect(writes).toHaveLength(1);
});

test('a period owned by a different client blocks the row with a correction', {
  tag: [...ADMIN_ACCOUNTING_HOSTING_BILLING, '@role:admin', '@outcome:error'],
}, async ({ page }) => {
  const writes = await openHostingBillingList(page, { wrongClient: true });
  await chooseHostingAction(page, 1, 'send-billing');
  const preview = dialog(page);
  await expect(preview.getByRole('alert')).toContainText('no coinciden');
  await expect(preview.getByRole('button', { name: 'Revisar conciliación del hosting' })).toBeVisible();
  await expect(preview.getByRole('button', { name: 'Enviar al cliente' })).toBeDisabled();
  await expect(preview.getByTestId('hosting-period-summary')).toHaveCount(0);
  await preview.getByRole('button', { name: 'Cancelar' }).click();
  expect(writes).toEqual([]);
});
