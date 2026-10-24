/** Appi client journeys. Each test states the user-visible regression it catches. */
import { test, expect } from '../helpers/test.js'
import {
  PLATFORM_APPI_AVAILABILITY, PLATFORM_APPI_GUIDANCE_BOUNDARY, PLATFORM_APPI_PRIVATE_HISTORY,
  PLATFORM_APPI_PROJECT_STATUS, PLATFORM_APPI_SHARED_QUOTA_AUDIO,
} from '../helpers/flow-tags.js'
import { PLATFORM_STORAGE_KEYS, mockPlatformClient } from '../helpers/platform-auth.js'
import { capabilities, conversation, json, openAppi, project, quota, readyMessage, setupAppi, visitClientProject } from '../helpers/appi.js'

const detail = (rows, overrides = {}) => ({ conversation: conversation(), messages: rows, quota: quota(), next_before: null, ...overrides })

test.describe('Platform Appi', () => {
  test.setTimeout(60_000)

  test('shows the ready launcher after a client enters an owned project', { tag: [...PLATFORM_APPI_AVAILABILITY, '@role:platform-client', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (authenticated project list is the Appi shell entry; the test clicks an owned project before exercising the Appi widget)
    // Bug caught: Appi disappears for a ready client or opens without consent.
    await setupAppi(page)
    await visitClientProject(page)
    await expect(page.getByTestId('appi-launcher')).toHaveText('Appi')
    await expect(page.getByTestId('appi-panel')).toHaveCount(0)
  })

  test('opens a usable chat from the ready launcher', { tag: [...PLATFORM_APPI_AVAILABILITY, '@role:platform-client', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: a ready launcher cannot open a usable Appi chat.
    await setupAppi(page)
    await visitClientProject(page)
    const panel = await openAppi(page)
    await expect(panel).toContainText('Te ayudo a conocer el estado de tus proyectos y a utilizar tu plataforma.')
    await expect(page.getByTestId('appi-question')).toHaveAttribute('placeholder', 'Pregunta por tu proyecto o cómo usar la plataforma…')
  })

  test('hides Appi after a disabled client reloads', { tag: [...PLATFORM_APPI_AVAILABILITY, '@role:platform-client', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: a disabled client can reopen Appi after restoring the authenticated page.
    const clientB = { ...mockPlatformClient, id: 9004, user_id: 9004, email: 'client-b@e2e-test.com' }
    let secondClient = false
    await setupAppi(page, { request: ({ apiPath, method }) => {
      if (apiPath === 'accounts/me/' && method === 'GET') return json(secondClient ? clientB : mockPlatformClient)
      if (apiPath === 'platform/ai/capabilities/' && method === 'GET' && secondClient) return json(capabilities({ chatbot: { enabled: false, available: false, voice_available: false } }))
      return null
    } })
    await visitClientProject(page)
    await openAppi(page)
    await page.getByTestId('appi-question').fill('Borrador privado de cliente A')
    secondClient = true
    await page.evaluate(({ keys, user }) => localStorage.setItem(keys.user, JSON.stringify(user)), { keys: PLATFORM_STORAGE_KEYS, user: clientB })
    await page.addInitScript(({ keys, user }) => localStorage.setItem(keys.user, JSON.stringify(user)), { keys: PLATFORM_STORAGE_KEYS, user: clientB })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: project.name, exact: true })).toBeVisible()
    await expect(page.getByTestId('appi-launcher')).toHaveCount(0)
    await expect(page.getByTestId('appi-panel')).toHaveCount(0)
    await expect(page.getByText('Borrador privado de cliente A')).toHaveCount(0)
  })

  test('keeps the chat closed when the capability request fails', { tag: [...PLATFORM_APPI_AVAILABILITY, '@role:platform-client', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: an unknown capability state permits a chargeable private conversation.
    let conversations = 0
    await setupAppi(page, { request: ({ apiPath, method }) => {
      if (apiPath === 'platform/ai/capabilities/' && method === 'GET') return json({ detail: 'Servicio no disponible' }, 503)
      if (apiPath === 'platform/chatbot/conversations/') conversations += 1
      return null
    } })
    await visitClientProject(page)
    await expect(page.getByTestId('appi-launcher')).toHaveCount(0)
    await expect(page.getByTestId('appi-panel')).toHaveCount(0)
    await expect.poll(() => conversations).toBe(0)
  })

  test('offers only global guidance without a selected project', { tag: [...PLATFORM_APPI_GUIDANCE_BOUNDARY, '@role:platform-client', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (authenticated project list is the Appi shell entry; the test clicks an owned project before exercising the Appi widget)
    // Bug caught: project-scoped prompts are offered against ambiguous all-projects context.
    await setupAppi(page)
    await visitClientProject(page)
    const panel = await openAppi(page)
    await page.getByTestId('appi-project').selectOption('')
    await expect(page.getByTestId('appi-project')).toHaveValue('')
    await expect(panel.getByRole('button', { name: '¿Cómo reporto un bug?' })).toHaveText('¿Cómo reporto un bug?')
    await expect(panel.getByRole('button', { name: '¿Dónde encuentro mis documentos?' })).toHaveText('¿Dónde encuentro mis documentos?')
    await expect(panel.getByRole('button', { name: '¿Cómo va mi proyecto?' })).toHaveCount(0)
    await page.getByTestId('appi-project').selectOption('7')
    await expect(panel.getByRole('button', { name: '¿Cómo va mi proyecto?' })).toBeVisible()
  })

  test('opens the returned bug guide destination', { tag: [...PLATFORM_APPI_GUIDANCE_BOUNDARY, '@role:platform-client', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: a valid usage guide cannot take the client to its platform resource.
    const answer = readyMessage({ question: '¿Cómo reporto un bug?', answer: { text: 'Usa el formulario del proyecto.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [{ target_key: 'bugs', label: 'Reportar un bug', href: '/platform/projects/7/bugs' }] } })
    await setupAppi(page, { request: ({ apiPath, method }) => {
      if (apiPath === 'platform/chatbot/conversations/42/messages/' && method === 'POST') return json(answer)
      if (apiPath === 'accounts/projects/7/bugs/' && method === 'GET') return json([])
      return null
    } })
    await visitClientProject(page); await openAppi(page)
    await page.getByTestId('appi-project').selectOption('7')
    await page.getByTestId('appi-question').fill('¿Cómo reporto un bug?')
    await page.getByTestId('appi-send').click()
    const action = page.getByRole('link', { name: 'Reportar un bug' })
    await expect(action).toHaveAttribute('href', /\/platform\/projects\/7\/bugs$/)
    await action.click()
    await expect(page).toHaveURL(/\/platform\/projects\/7\/bugs$/)
    await expect(page.getByTestId('appi-panel')).toHaveCount(0)
  })

  test('asks for a project before returning project-required guidance', { tag: [...PLATFORM_APPI_GUIDANCE_BOUNDARY, '@role:platform-client', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: Appi invents an ambiguous project action without project selection.
    const clarificationText = '¿Sobre cuál de estas opciones quieres consultar?\nSelecciona un proyecto propio en el selector de Appi para continuar.'
    const weatherText = 'Recuerda que mi propósito es brindarte información sobre tus proyectos y su estado. Puedo ayudarte a consultar contratos, fases, entregables, bugs y pendientes.'
    let createdProjectId
    await setupAppi(page, { request: ({ apiPath, method, route }) => {
      if (apiPath === 'platform/chatbot/conversations/' && method === 'POST') { createdProjectId = JSON.parse(route.request().postData() || '{}').project_id; return null }
      if (apiPath !== 'platform/chatbot/conversations/42/messages/' || method !== 'POST') return null
      const question = JSON.parse(route.request().postData() || '{}').question
      return json(readyMessage({ question, answer: { text: question === '¿Qué tiempo hará?' ? weatherText : clarificationText, verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] } }))
    } })
    await visitClientProject(page); await openAppi(page)
    await page.getByTestId('appi-project').selectOption('')
    await page.getByTestId('appi-question').fill('¿Cómo reporto un bug?')
    await page.getByTestId('appi-send').click()
    await expect(page.getByTestId('appi-answer')).toHaveText(clarificationText)
    expect(createdProjectId).toBeNull()
    await expect(page.getByTestId('appi-panel').getByRole('link')).toHaveCount(0)
    await page.getByTestId('appi-question').fill('¿Qué tiempo hará?')
    await page.getByTestId('appi-send').click()
    await expect(page.getByText(weatherText)).toHaveText(weatherText)
    await expect(page.getByTestId('appi-panel').getByRole('link')).toHaveCount(0)
  })

  test('retains a failed guide question for retry', { tag: [...PLATFORM_APPI_GUIDANCE_BOUNDARY, '@role:platform-client', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: a failed guide request loses input or pretends to provide guidance.
    await setupAppi(page, { request: ({ apiPath, method }) => apiPath === 'platform/chatbot/conversations/42/messages/' && method === 'POST' ? json({ detail: 'No disponible' }, 503) : null })
    await visitClientProject(page); await openAppi(page)
    await page.getByTestId('appi-question').fill('¿Cómo reporto un bug?')
    await page.getByTestId('appi-send').click()
    await expect(page.getByRole('alert')).toHaveText('No pudimos completar la operación. Revisa tu conexión e inténtalo de nuevo.')
    await expect(page.getByTestId('appi-question')).toHaveValue('¿Cómo reporto un bug?')
    await expect(page.getByTestId('appi-panel').getByRole('link')).toHaveCount(0)
  })

  test('shows a sourced current project answer', { tag: [...PLATFORM_APPI_PROJECT_STATUS, '@role:platform-client', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (authenticated project list is the Appi shell entry; the test clicks an owned project before exercising the Appi widget)
    // Bug caught: a project answer lacks its source or verification context.
    const row = readyMessage({ answer: { text: 'El portal está en revisión.', verified_at: '2026-10-24T12:00:00Z', actions: [], sources: [{ id: 'source-1', label: 'Estado del portal', href: '/platform/projects/7' }] } })
    await setupAppi(page, { conversations: [conversation()], details: { 42: detail([row]) } })
    await visitClientProject(page); await openAppi(page)
    await page.getByTestId('appi-history').selectOption('42')
    await expect(page.getByTestId('appi-answer')).toHaveText('El portal está en revisión.')
    await expect(page.getByRole('link', { name: 'Estado del portal' })).toHaveAttribute('href', /\/platform\/projects\/7$/)
    await expect(page.getByText(/Comprobado:/)).toBeVisible()
  })

  test('keeps both turns after a project re-query', { tag: [...PLATFORM_APPI_PROJECT_STATUS, '@role:platform-client', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: re-query overwrites history or omits the consumed allowance.
    let sent = 0
    await setupAppi(page, { request: ({ apiPath, method }) => {
      if (apiPath === 'platform/chatbot/conversations/42/messages/' && method === 'POST') {
        sent += 1; return json(readyMessage({ id: sent, question: '¿Cómo va mi proyecto?', answer: { text: `Estado confirmado ${sent}`, verified_at: '2026-10-24T12:00:00Z', actions: [], sources: [] }, quota: quota({ used: sent + 1, remaining: 4 - sent }) }))
      } return null
    } })
    await visitClientProject(page); await openAppi(page)
    await page.getByTestId('appi-project').selectOption('7'); await page.getByTestId('appi-question').fill('¿Cómo va mi proyecto?'); await page.getByTestId('appi-send').click()
    await expect(page.getByTestId('appi-answer')).toHaveText('Estado confirmado 1')
    await page.getByRole('button', { name: 'Consultar de nuevo' }).click()
    await expect(page.getByTestId('appi-answer')).toHaveText(['Estado confirmado 1', 'Estado confirmado 2'])
    await expect(page.getByTestId('platform-ai-quota')).toContainText('2 disponibles')
  })

  test('hides only an unavailable historical turn', { tag: [...PLATFORM_APPI_PROJECT_STATUS, '@role:platform-client', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: a revoked response remains visible or hides unrelated valid history.
    const current = readyMessage({ id: 1, answer: { text: 'Estado vigente.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] } })
    const unavailable = { id: 2, status: 'unavailable', question: 'Estado anterior', answer: null }
    await setupAppi(page, { conversations: [conversation()], details: { 42: detail([current, unavailable]) } })
    await visitClientProject(page); await openAppi(page); await page.getByTestId('appi-history').selectOption('42')
    await expect(page.getByTestId('appi-answer')).toHaveText('Estado vigente.')
    await expect(page.getByTestId('appi-message-unavailable')).toHaveText('Esta consulta ya no está disponible para tu cuenta.')
    await expect(page.getByTestId('appi-message-unavailable').getByTestId('appi-answer')).toHaveCount(0)
  })

  test('retries a failed status turn before showing an answer', { tag: [...PLATFORM_APPI_PROJECT_STATUS, '@role:platform-client', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: a processing failure is presented as project information or cannot recover.
    let polls = 0; let sends = 0
    await setupAppi(page, { request: ({ apiPath, method }) => {
      if (apiPath === 'platform/chatbot/conversations/42/messages/' && method === 'POST') { sends += 1; return json({ id: 88, status: sends === 1 ? 'pending' : 'ready', question: '¿Cómo va mi proyecto?', ...(sends > 1 ? { answer: { text: 'Recuperado.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] } } : {}) }) }
      if (apiPath === 'platform/chatbot/conversations/42/messages/88/' && method === 'GET') { polls += 1; return json({ id: 88, status: 'failed', question: '¿Cómo va mi proyecto?' }) }
      return null
    } })
    await visitClientProject(page); await openAppi(page); await page.getByTestId('appi-question').fill('¿Cómo va mi proyecto?'); await page.getByTestId('appi-send').click()
    await expect(page.getByTestId('appi-message-pending')).toContainText('Appi está consultando…')
    await expect.poll(() => polls).toBe(1)
    await expect(page.getByTestId('appi-message-failed')).toContainText('No pude completar la consulta. Puedes reintentar.')
    await expect(page.getByTestId('appi-message-failed').getByTestId('appi-answer')).toHaveCount(0)
    await page.getByRole('button', { name: 'Reintentar' }).click()
    await expect(page.getByTestId('appi-answer')).toHaveText('Recuperado.')
  })

  test('lists only the supplied private history titles', { tag: [...PLATFORM_APPI_PRIVATE_HISTORY, '@role:platform-client', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (authenticated project list is the Appi shell entry; the test clicks an owned project before exercising the Appi widget)
    // Bug caught: history exposes expired or another client’s conversation.
    await setupAppi(page, { conversations: [conversation({ id: 41, title: 'Portal esta semana' }), conversation({ id: 42, title: 'Bugs del portal' })] })
    await visitClientProject(page); await openAppi(page)
    await expect(page.getByTestId('appi-history').locator('option')).toHaveText(['Conversaciones', 'Portal esta semana', 'Bugs del portal'])
    await expect(page.getByTestId('appi-history')).not.toContainText('Cliente ajeno')
  })

  test('appends older history once and removes a deleted conversation', { tag: [...PLATFORM_APPI_PRIVATE_HISTORY, '@role:platform-client', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: pagination duplicates messages, deletion leaves stale history, or deletion restores allowance.
    let reads = 0
    const initial = detail([readyMessage({ id: 2, answer: { text: 'Mensaje reciente.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] } })], { next_before: 'older' })
    const older = detail([readyMessage({ id: 1, answer: { text: 'Mensaje anterior.', verified_at: '2026-10-23T12:00:00Z', sources: [], actions: [] } })], { next_before: null })
    await setupAppi(page, { conversations: [conversation()], request: ({ apiPath, method }) => {
      if (apiPath === 'platform/chatbot/conversations/42/' && method === 'GET') { reads += 1; return json(reads === 1 ? initial : older) }
      if (apiPath === 'platform/chatbot/conversations/42/' && method === 'DELETE') return { status: 204, body: '' }
      return null
    } })
    await visitClientProject(page); await openAppi(page); await page.getByTestId('appi-history').selectOption('42')
    await page.getByRole('button', { name: 'Ver mensajes anteriores' }).click()
    await expect(page.getByTestId('appi-answer')).toHaveText(['Mensaje anterior.', 'Mensaje reciente.'])
    await page.getByRole('button', { name: 'Eliminar conversación' }).click(); await page.getByRole('alert').getByRole('button', { name: 'Eliminar conversación', exact: true }).click()
    await expect(page.getByTestId('appi-history').locator('option')).toHaveCount(1)
    await expect(page.getByTestId('platform-ai-quota')).toContainText('4 disponibles')
  })

  test('preserves available history after an unavailable detail', { tag: [...PLATFORM_APPI_PRIVATE_HISTORY, '@role:platform-client', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: a failed history request clears all valid local history.
    await setupAppi(page, { conversations: [conversation({ id: 41, title: 'Válida' }), conversation({ id: 42, title: 'No disponible' })], request: ({ apiPath, method }) => apiPath === 'platform/chatbot/conversations/42/' && method === 'GET' ? json({ detail: 'No encontrada' }, 404) : null })
    await visitClientProject(page); await openAppi(page); await page.getByTestId('appi-history').selectOption('42')
    await expect(page.getByRole('alert')).toHaveText('No pudimos completar la operación. Revisa tu conexión e inténtalo de nuevo.')
    await expect(page.getByTestId('appi-history').locator('option')).toHaveText(['Conversaciones', 'Válida', 'No disponible'])
  })

  test('keeps history visible after a failed deletion', { tag: [...PLATFORM_APPI_PRIVATE_HISTORY, '@role:platform-client', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: a failed deletion is represented locally as successful.
    await setupAppi(page, { conversations: [conversation()], details: { 42: detail([]) }, request: ({ apiPath, method }) => apiPath === 'platform/chatbot/conversations/42/' && method === 'DELETE' ? json({ detail: 'No disponible' }, 503) : null })
    await visitClientProject(page); await openAppi(page); await page.getByTestId('appi-history').selectOption('42')
    await page.getByRole('button', { name: 'Eliminar conversación' }).click(); await page.getByRole('alert').getByRole('button', { name: 'Eliminar conversación', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('No pudimos completar la operación.')
    await expect(page.getByTestId('appi-history').locator('option')).toHaveText(['Conversaciones', 'Estado del portal'])
  })

  test('shows the shared quota snapshot when Appi opens', { tag: [...PLATFORM_APPI_SHARED_QUOTA_AUDIO, '@role:platform-client', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (authenticated project list is the Appi shell entry; the test clicks an owned project before exercising the Appi widget)
    // Bug caught: a client cannot understand the shared allowance or rolling window.
    await setupAppi(page, { appiCapabilities: capabilities({ quota: quota({ used: 2, limit: 5, remaining: 3, window_minutes: 45 }) }) })
    await visitClientProject(page); await openAppi(page)
    const meter = page.getByTestId('platform-ai-quota')
    await expect(meter).toContainText('2 de 5 solicitudes usadas · 3 disponibles')
    await expect(meter).toContainText('Ventana móvil de 45 minutos.')
    await expect(meter.getByRole('progressbar')).toHaveAttribute('value', '2')
    await expect(meter.getByRole('progressbar')).toHaveAttribute('max', '5')
  })

  test('sends one dictated receipt and refreshes its allowance', { tag: [...PLATFORM_APPI_SHARED_QUOTA_AUDIO, '@role:platform-client', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: dictated Appi input omits its receipt or displays the wrong post-redemption allowance.
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }) } })
      window.MediaRecorder = class { static isTypeSupported() { return true } constructor() { this.state = 'inactive' } start() { this.state = 'recording' } stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['voice'], { type: 'audio/webm' }) }); this.onstop?.() } }
    })
    let receipts = 0
    await setupAppi(page, { appiCapabilities: capabilities({ chatbot: { enabled: true, available: true, voice_available: true } }), request: ({ apiPath, method, route }) => {
      if (apiPath === 'platform/ai/transcriptions/' && method === 'POST') return json({ id: 'transcription-1', status: 'ready', transcript: '¿Cómo va mi proyecto?' })
      if (apiPath === 'platform/chatbot/conversations/42/messages/' && method === 'POST') { const body = JSON.parse(route.request().postData() || '{}'); if (body.transcription_id === 'transcription-1') receipts += 1; return json(readyMessage({ answer: { text: 'Estado dictado.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] }, quota: quota({ used: 2, remaining: 3 }) })) }
      return null
    } })
    await visitClientProject(page); await openAppi(page)
    await page.getByRole('button', { name: 'Dictar pregunta' }).click(); await page.getByRole('button', { name: /Detener grabación/ }).click(); await page.getByRole('button', { name: 'Transcribir' }).click()
    await expect(page.getByTestId('appi-question')).toHaveValue('¿Cómo va mi proyecto?')
    await page.getByTestId('appi-send').click()
    await expect.poll(() => receipts).toBe(1)
    await expect(page.getByTestId('appi-answer')).toHaveText('Estado dictado.')
    await expect(page.getByTestId('platform-ai-quota')).toContainText('3 disponibles')
  })

  test('blocks text and dictation when the shared allowance is empty', { tag: [...PLATFORM_APPI_SHARED_QUOTA_AUDIO, '@role:platform-client', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: an exhausted client can start another text or audio request.
    await setupAppi(page, { appiCapabilities: capabilities({ chatbot: { enabled: true, available: true, voice_available: true }, quota: quota({ used: 5, limit: 5, remaining: 0 }) }) })
    await visitClientProject(page); await openAppi(page)
    await expect(page.getByTestId('appi-send')).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Dictar pregunta' })).toBeDisabled()
    await expect(page.getByTestId('platform-ai-quota')).toContainText('Agotaste el cupo compartido.')
  })

  test('recovers from voice and send failures with the same request id', { tag: [...PLATFORM_APPI_SHARED_QUOTA_AUDIO, '@role:platform-client', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: voice/network failure strands typing or a retry creates a second logical charge.
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }) } })
      window.MediaRecorder = class { static isTypeSupported() { return true } constructor() { this.state = 'inactive' } start() { this.state = 'recording' } stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['voice'], { type: 'audio/webm' }) }); this.onstop?.() } }
    })
    const requestIds = []; let sends = 0
    await setupAppi(page, { appiCapabilities: capabilities({ chatbot: { enabled: true, available: true, voice_available: true } }), request: ({ apiPath, method, route }) => {
      if (apiPath === 'platform/ai/transcriptions/' && method === 'POST') return json({ id: 'transcription-2', status: 'pending' })
      if (apiPath === 'platform/ai/transcriptions/transcription-2/' && method === 'GET') return json({ id: 'transcription-2', status: 'failed' })
      if (apiPath === 'platform/chatbot/conversations/42/messages/' && method === 'POST') { const body = JSON.parse(route.request().postData() || '{}'); requestIds.push(body.request_id); sends += 1; return sends === 1 ? json({ detail: 'Sin conexión' }, 503) : json(readyMessage({ answer: { text: 'Reintento confirmado.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] } })) }
      return null
    } })
    await visitClientProject(page); await openAppi(page)
    await page.getByRole('button', { name: 'Dictar pregunta' }).click(); await page.getByRole('button', { name: /Detener grabación/ }).click(); await page.getByRole('button', { name: 'Transcribir' }).click()
    await expect(page.getByRole('alert')).toHaveText('No pudimos acceder al micrófono o transcribir el audio. Puedes escribir tu pregunta.')
    await page.getByTestId('appi-question').fill('¿Cómo va mi proyecto?'); await page.getByTestId('appi-send').click()
    await expect(page.getByTestId('appi-question')).toHaveValue('¿Cómo va mi proyecto?')
    await page.getByTestId('appi-send').click()
    await expect.poll(() => requestIds.length).toBe(2)
    await expect(requestIds[1]).toBe(requestIds[0])
    await expect(page.getByTestId('appi-answer')).toHaveText('Reintento confirmado.')
  })
})
