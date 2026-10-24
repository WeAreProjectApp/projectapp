// qa: draft-unvalidated (2026-10-24 — app not running)
/** Responsive Appi surface: launcher, selectors, history, quota and send action stay reachable. */
import { test, expect } from '../helpers/test.js'
import { VIEWPORTS, viewportUse } from '../helpers/viewports.js'
import {
  PLATFORM_APPI_AVAILABILITY, PLATFORM_APPI_GUIDANCE_BOUNDARY, PLATFORM_APPI_PRIVATE_HISTORY,
  PLATFORM_APPI_PROJECT_STATUS, PLATFORM_APPI_SHARED_QUOTA_AUDIO,
} from '../helpers/flow-tags.js'
import { conversation, detail, openAppi, readyMessage, setupAppi } from '../helpers/appi.js'

for (const alias of Object.keys(VIEWPORTS)) {
  test.describe(`Platform Appi responsive ${alias}`, () => {
    test.use(viewportUse(alias))
    test.setTimeout(60_000)

    test('keeps the completed Appi conversation reachable', {
      tag: [...PLATFORM_APPI_AVAILABILITY, ...PLATFORM_APPI_GUIDANCE_BOUNDARY, ...PLATFORM_APPI_PRIVATE_HISTORY,
        ...PLATFORM_APPI_PROJECT_STATUS, ...PLATFORM_APPI_SHARED_QUOTA_AUDIO, '@role:platform-client', '@outcome:display', '@responsive:platform-appi', `@viewport:${alias}`],
    }, async ({ page }) => {
      // quality: allow-deep-link (authenticated project list is the Appi shell entry; the test clicks an owned project before exercising the Appi widget)
      // Bug caught: Appi clips its selectors, quota meter or final send control at this viewport.
      const row = readyMessage({ answer: { text: 'El portal está listo para revisión.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] } })
      await setupAppi(page, { conversations: [conversation()], details: { 42: detail([row]) } })
      await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
      await page.getByTestId('project-row-7').or(page.getByTestId('project-card-7')).click()
      await page.waitForURL(/\/platform\/projects\/7$/)
      const panel = await openAppi(page)
      await page.getByTestId('appi-project').selectOption('7')
      await page.getByTestId('appi-history').selectOption('42')
      await expect(page.getByTestId('appi-answer')).toHaveText('El portal está listo para revisión.')
      await page.getByTestId('appi-messages').hover()
      await page.mouse.wheel(0, 1200)
      await expect(panel.getByTestId('appi-project')).toHaveValue('7')
      await expect(panel.getByTestId('appi-history')).toHaveValue('42')
      await expect(panel.getByTestId('appi-messages')).toContainText('El portal está listo para revisión.')
      await expect(panel.getByTestId('platform-ai-quota')).toContainText('4 disponibles')
      await expect(panel.getByTestId('appi-question')).toHaveAttribute('placeholder', 'Pregunta por tu proyecto o cómo usar la plataforma…')
      await expect(panel.getByTestId('appi-send')).toHaveText('Enviar pregunta')
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      const send = await panel.getByTestId('appi-send').boundingBox()
      expect(send).not.toBeNull()
      expect(send.y + send.height).toBeLessThanOrEqual(VIEWPORTS[alias].height + 1)
      await page.getByRole('button', { name: 'Cerrar Appi' }).click()
      await expect(page.getByTestId('appi-launcher')).toHaveText('Appi')
    })
  })
}
