/**
 * Catches a regression where reviewed voice text was submitted automatically,
 * or did not reach the bug form that the client still must submit manually.
 */
import { test, expect } from './helpers/test.js'
import { mockApi } from './helpers/api.js'
import { setPlatformAuth, mockPlatformClient } from './helpers/platform-auth.js'
import { waitForNuxtApp } from './helpers/navigation.js'

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })
const project = { id: 1, name: 'Portal de prueba', status_label: 'Activo', current_state: { color: 'emerald' }, client_name: 'Cliente E2E' }
const requirement = { id: 11, title: 'Guardar pagos', phase_id: 4, phase_title: 'Cobros', guide: {} }
const capabilities = {
  voice_reporting: { available: true },
  chatbot: { enabled: false, voice_available: false },
  quota: { limit: 20, used: 5, remaining: 15, window_minutes: 300, next_available_at: null },
}

async function installMediaRecorder(page, { microphoneDenied = false } = {}) {
  await page.addInitScript(({ microphoneDenied: denied }) => {
    class E2EFakeMediaRecorder {
      static isTypeSupported() { return true }
      constructor() { this.state = 'inactive'; this.ondataavailable = null; this.onstop = null }
      start() { this.state = 'recording' }
      stop() {
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob(['voice-fixture'], { type: 'audio/webm' }) })
        this.onstop?.()
      }
    }
    Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: E2EFakeMediaRecorder })
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: async () => {
        if (denied) throw new DOMException('Permission denied', 'NotAllowedError')
        return { getTracks: () => [{ stop() {} }] }
      } },
    })
  }, { microphoneDenied })
}

async function setup(page, { transcriptionFails = false, microphoneDenied = false, quota = capabilities.quota } = {}) {
  const scenario = { createdReports: 0, transcriptionFails }
  await installMediaRecorder(page, { microphoneDenied })
  await setPlatformAuth(page, { user: mockPlatformClient, accessToken: 'voice-client-token', refreshToken: 'voice-refresh-token' })
  await mockApi(page, ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(mockPlatformClient)
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project])
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(project)
    if (apiPath === 'accounts/projects/1/bug-reports/' && method === 'GET') return json([])
    if (apiPath === 'accounts/projects/1/issue-reports/context-options/' && method === 'GET') return json({ requirements: [requirement] })
    if (apiPath === 'platform/ai/capabilities/' && method === 'GET') return json({ ...capabilities, quota })
    if (apiPath === 'platform/ai/transcriptions/' && method === 'GET') return json([])
    if (apiPath === 'platform/ai/transcriptions/' && method === 'POST') {
      if (scenario.transcriptionFails) return json({ detail: 'Proveedor no disponible.' }, 503)
      return json({ id: 'transcription-1', status: 'ready', transcript: 'El pago queda cargando al guardar.' }, 202)
    }
    if (apiPath === 'platform/ai/projects/1/report-drafts/' && method === 'POST') {
      return json({
        id: 'draft-1', status: 'ready', proposal: {
          title: 'El pago no se guarda',
          description: 'El pago queda cargando al guardar.',
          expected_behavior: 'El pago se confirma.',
          actual_behavior: 'La pantalla sigue cargando.',
          steps_to_reproduce: ['Abrir un pago', 'Seleccionar Guardar'],
          missing_details: [],
        },
      }, 202)
    }
    if (apiPath === 'platform/ai/transcriptions/draft-1/' && method === 'GET') return json({ id: 'draft-1', status: 'ready', operation: 'draft' })
    if (apiPath === 'platform/ai/transcriptions/draft-1/' && method === 'DELETE') return { status: 204, body: '' }
    if (apiPath === 'platform/ai/transcriptions/transcription-1/' && method === 'DELETE') return { status: 204, body: '' }
    if (apiPath === 'accounts/projects/1/bug-reports/' && method === 'POST') {
      scenario.createdReports += 1
      return json({ id: 91, title: 'El pago no se guarda', status: 'reported' }, 201)
    }
    return null
  })
  return scenario
}

async function openBugForm(page) {
  // quality: allow-deep-link (this success/failure slice exercises the voice control inside the existing bug form; project-list navigation is covered by platform-project-list)
  await page.goto('/es-co/platform/projects/1/bugs', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await expect(page.getByRole('heading', { name: 'Reporte de bugs', exact: true })).toHaveText('Reporte de bugs')
  await page.getByRole('button', { name: 'Reportar bug', exact: true }).click()
}

async function openBugFormFromProjectList(page) {
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  const projectRow = page.getByTestId('project-row-1').or(page.getByTestId('project-card-1'))
  await expect(projectRow).toContainText('Portal de prueba')
  await projectRow.click()
  await expect(page.getByRole('heading', { name: 'Portal de prueba', exact: true })).toHaveText('Portal de prueba')
  await page.getByRole('link', { name: 'Bugs', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Reporte de bugs', exact: true })).toHaveText('Reporte de bugs')
  await page.getByRole('button', { name: 'Reportar bug', exact: true }).click()
}

test.describe('Voice report for bugs', () => {
  test.setTimeout(60_000)

  // Catches the regression where reviewed audio text bypassed the review step or created a bug report by itself.
  test('places reviewed voice text in the bug form', {
    tag: ['@flow:platform-voice-report', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = await setup(page)
    await openBugForm(page)

    const voice = page.getByTestId('voice-report-input')
    await voice.getByRole('button', { name: 'Describir con una nota de voz', exact: true }).click()
    await expect(voice.getByTestId('platform-ai-quota')).toContainText('5 de 20 solicitudes usadas · 15 disponibles')
    await voice.getByRole('button', { name: 'Grabar o volver a grabar', exact: true }).click()
    await voice.getByRole('button', { name: /Detener/ }).click()
    await voice.getByRole('button', { name: 'Convertir a texto', exact: true }).click()
    await expect(voice.getByTestId('voice-transcript')).toHaveValue('El pago queda cargando al guardar.')
    await voice.getByRole('button', { name: 'Preparar texto estructurado', exact: true }).click()
    await expect(voice.getByTestId('voice-proposal')).toContainText('Revisa y corrige esta propuesta.')
    await voice.getByTestId('voice-proposal-title').fill('Pago bloqueado tras revisión')
    await voice.getByRole('button', { name: 'Revisé el texto: usar en el formulario', exact: true }).click()

    await expect(page.getByPlaceholder('¿Qué está fallando?')).toHaveValue('Pago bloqueado tras revisión')
    expect(scenario.createdReports).toBe(0)
  })

  // Catches the regression where a failed transcription hid the user's manual bug draft.
  test('preserves manual reporting after a transcription failure', {
    tag: ['@flow:platform-voice-report', '@outcome:failure'],
  }, async ({ page }) => {
    await setup(page, { transcriptionFails: true })
    await openBugForm(page)
    await page.getByPlaceholder('¿Qué está fallando?').fill('El pago manual sigue disponible')

    const voice = page.getByTestId('voice-report-input')
    await voice.getByRole('button', { name: 'Describir con una nota de voz', exact: true }).click()
    await voice.getByRole('button', { name: 'Grabar o volver a grabar', exact: true }).click()
    await voice.getByRole('button', { name: /Detener/ }).click()
    await voice.getByRole('button', { name: 'Convertir a texto', exact: true }).click()

    await expect(voice.getByRole('alert')).toHaveText('No se pudo procesar. Revisa la conexión, los límites o la disponibilidad. Conservamos el texto que estás editando.')
    await expect(page.getByPlaceholder('¿Qué está fallando?')).toHaveValue('El pago manual sigue disponible')
  })

  // Catches the regression where a browser microphone denial left the reporter without a concrete recovery message.
  test('explains a denied microphone permission', {
    tag: ['@flow:platform-voice-report', '@outcome:error'],
  }, async ({ page }) => {
    await setup(page, { microphoneDenied: true })
    await openBugForm(page)

    const voice = page.getByTestId('voice-report-input')
    await voice.getByRole('button', { name: 'Describir con una nota de voz', exact: true }).click()
    await voice.getByRole('button', { name: 'Grabar o volver a grabar', exact: true }).click()

    await expect(voice.getByRole('alert')).toHaveText('No pudimos acceder al micrófono o el navegador no admite grabación. Revisa los permisos o escribe tu reporte.')
  })

  // Catches the regression where an exhausted shared allowance still let the client record a paid voice request.
  test('shows the exhausted shared allowance before recording', {
    tag: ['@flow:platform-voice-report', '@outcome:display'],
  }, async ({ page }) => {
    await setup(page, { quota: { limit: 20, used: 20, remaining: 0, window_minutes: 300, next_available_at: '2026-10-24T15:00:00Z' } })
    await openBugFormFromProjectList(page)

    const voice = page.getByTestId('voice-report-input')
    await voice.getByRole('button', { name: 'Describir con una nota de voz', exact: true }).click()
    await expect(voice.getByTestId('platform-ai-quota')).toContainText('20 de 20 solicitudes usadas · 0 disponibles')
    await expect(voice.getByText('Agotaste el cupo compartido. Espera a que se libere una solicitud o continúa manualmente.')).toHaveText('Agotaste el cupo compartido. Espera a que se libere una solicitud o continúa manualmente.')
    await expect(voice.getByRole('button', { name: 'Grabar o volver a grabar', exact: true })).toBeDisabled()
  })
})
