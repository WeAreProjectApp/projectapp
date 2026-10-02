import { expect } from '../helpers/test.js'

export function citationFrom(context, text = '') {
  const source = context.sources.find((item) => item.fragments?.length && item.role === 'contract')
  const fragment = source.fragments.find((item) => item.text.includes(text)) || source.fragments[0]
  return { source_key: source.source_key, locator: fragment.locator, quote: fragment.text }
}

export async function preparePrompt(page) {
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith('/delivery/prompt/') && response.request().method() === 'POST')
  await page.getByTestId('delivery-prompt-prepare').click()
  const response = await responsePromise
  expect(response.status()).toBe(201)
  const context = await response.json()
  await expect(page.getByTestId('delivery-prompt-sources')).toBeVisible()
  return context
}

export function guidePayload(context, contractId) {
  return {
    schema_version: 2, context_id: context.id,
    scopes: [{
      key: 'source-based-scope', title: 'Alcance preparado con sus fuentes', contract_id: contractId,
      phases: [{ key: 'prepared-phase', title: 'Fase preparada', stages: [{
        key: 'prepared-stage', title: 'Etapa preparada', requirements: [{
          key: 'prepared-test', title: 'Validar las pruebas pactadas',
          guide: {
            environment: 'Staging', preparation: 'Abrir el caso preparado.',
            data: 'Registro de prueba.', steps: ['Abrir la pantalla.', 'Confirmar el resultado.'],
            expected_result: 'Aparece el resultado acordado.', failure_signals: 'Aparece un error.',
          },
          source_references: [citationFrom(context)],
        }],
      }] }],
    }],
  }
}

export function roleGuidePayload(context, contractId) {
  const payload = guidePayload(context, contractId)
  const stage = payload.scopes[0].phases[0].stages[0]
  stage.key = 'inventory-role-stage'
  stage.title = 'Etapa de inventario por rol'
  const requirement = stage.requirements[0]
  requirement.key = 'inventory-role-check'
  requirement.title = 'Validar el inventario por rol'
  requirement.guide = {
    ...requirement.guide,
    role: 'Operador de inventario',
    access: 'Ingresar con una cuenta habilitada de la sucursal.',
    allowed_actions: 'Consultar el inventario de su sucursal.',
    blocked_actions: 'No modificar registros de otras sucursales.',
    blocked_steps: ['Intentar modificar un registro de otra sucursal.'],
  }
  requirement.source_references = [citationFrom(context, 'Operador de inventario')]
  return payload
}

export function replyPayload(context, classification = 'inside_scope') {
  return {
    schema_version: 2, context_id: context.id,
    response_text: 'Atenderemos la validación de las pruebas pactadas.',
    classifications: [{
      request: 'Validar las pruebas pactadas.', classification,
      rationale: 'El pedido se revisó contra el texto contractual conservado.',
      citations: [citationFrom(context)],
    }],
  }
}

export async function previewReply(page, context) {
  await page.getByTestId('delivery-prompt-json').fill(JSON.stringify(replyPayload(context)))
  await page.getByTestId('delivery-prompt-preview').click()
  await expect(page.getByTestId('delivery-prompt-use-reply')).toBeEnabled()
}
