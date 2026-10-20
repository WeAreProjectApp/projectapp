/**
 * Falla si reaparece la aceptación pública o se rompe la negociación/rechazo.
 * La API es el límite simulado; cada respuesta se dispara desde el cierre real.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PROPOSAL_RESPOND } from '../helpers/flow-tags.js';

test.setTimeout(60_000);
const UUID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const json = body => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const proposal = {
  id: 1, uuid: UUID, title: 'Portal Atlas', client_name: 'Atlas', status: 'sent', language: 'es',
  total_investment: '5000000', currency: 'COP', requirement_groups: [],
  sections: [{ id: 1, section_type: 'greeting', title: 'Bienvenido', order: 0, is_enabled: true, content_json: { clientName: 'Atlas' } }],
};

async function openClosingPanel(page) {
  await page.goto(`/proposal/${UUID}?mode=detailed`, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('nav-next').click();
  await expect(page.getByTestId('nav-next')).toHaveCount(0);
}

async function mockProposal(page, status = 'sent') {
  const submissions = [];
  await mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === `proposals/${UUID}/`) return json({ ...proposal, status });
    if (apiPath === `proposals/${UUID}/respond/`) {
      const payload = route.request().postDataJSON();
      submissions.push(payload);
      return json({ status: payload.action });
    }
    return null;
  });
  return submissions;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('proposal_onboarding_seen', 'true'));
});

test('public closing offers adjustments without acceptance', {
  tag: [...PROPOSAL_RESPOND, '@role:guest', '@outcome:success'],
}, async ({ page }) => {
  const submissions = await mockProposal(page);
  await openClosingPanel(page);
  await expect(page.getByRole('button', { name: /Acepto la propuesta/i })).toHaveCount(0);
  await page.getByRole('button', { name: 'Necesito ajustes', exact: true }).click();

  await expect(page.getByText('Me interesa, pero negociemos alcance', { exact: true })).toHaveText('Me interesa, pero negociemos alcance');
  await expect(page.getByPlaceholder(/Acepto, pero necesito/i)).toHaveCount(0);
  expect(submissions).toEqual([]);
});

test('requesting adjustments submits the negotiation comment', {
  tag: [...PROPOSAL_RESPOND, '@role:guest', '@outcome:success'],
}, async ({ page }) => {
  const submissions = await mockProposal(page);
  await openClosingPanel(page);
  await page.getByRole('button', { name: 'Necesito ajustes', exact: true }).click();
  await page.getByPlaceholder(/Me gustaría reducir el número de módulos/).fill('Necesitamos dos módulos menos.');
  await page.getByRole('button', { name: /Enviar solicitud de ajuste/ }).click();

  await expect(page.getByText('¡Solicitud recibida!', { exact: true })).toHaveText('¡Solicitud recibida!');
  expect(submissions).toEqual([{ action: 'negotiating', comment: 'Necesitamos dos módulos menos.' }]);
});

test('rejecting a proposal displays the rejection receipt', {
  tag: [...PROPOSAL_RESPOND, '@role:guest', '@outcome:success'],
}, async ({ page }) => {
  const submissions = await mockProposal(page, 'viewed');
  await openClosingPanel(page);
  await page.getByRole('button', { name: 'No es el momento', exact: true }).click();
  await page.getByRole('button', { name: 'Confirmar rechazo', exact: true }).click();

  await expect(page.getByText('Propuesta rechazada. Gracias por tu tiempo.', { exact: true })).toHaveText('Propuesta rechazada. Gracias por tu tiempo.');
  expect(submissions).toEqual([{ action: 'rejected', reason: '', comment: '' }]);
});

test('approved proposal preserves its public receipt', {
  tag: [...PROPOSAL_RESPOND, '@role:guest', '@outcome:success'],
}, async ({ page }) => {
  const submissions = await mockProposal(page, 'accepted');
  await openClosingPanel(page);

  await expect(page.getByText('¡Propuesta aceptada!', { exact: true })).toHaveText('¡Propuesta aceptada!');
  await expect(page.getByRole('button', { name: /Acepto la propuesta|Necesito ajustes|No es el momento/i })).toHaveCount(0);
  expect(submissions).toEqual([]);
});
