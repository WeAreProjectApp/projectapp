/**
 * Tests for useTechnicalPrompt composable.
 */
const STORAGE_KEY = 'projectapp-technical-prompt-override'

describe('useTechnicalPrompt', () => {
  beforeEach(() => {
    localStorage.clear()
    jest.resetModules()
  })

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY)
  })

  it('loadSavedPrompt reads from localStorage', () => {
    localStorage.setItem(STORAGE_KEY, 'saved-text')
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { loadSavedPrompt, promptText } = useTechnicalPrompt()
    loadSavedPrompt()
    expect(promptText.value).toBe('saved-text')
  })

  it('drives requirement counts by item complexity, not a fixed quota', () => {
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { DEFAULT_PROMPT } = useTechnicalPrompt()
    expect(DEFAULT_PROMPT).toContain('REGLA DE GRANULARIDAD')
    expect(DEFAULT_PROMPT).toContain('Anti-uniformidad')
    expect(DEFAULT_PROMPT).toContain('Anti-plantilla')
    expect(DEFAULT_PROMPT).toContain('un solo requerimiento')
    expect(DEFAULT_PROMPT).not.toContain('≥80%')
    expect(DEFAULT_PROMPT).not.toContain('**4 a 6**')
    expect(DEFAULT_PROMPT).not.toContain('2 a 5 requerimientos')
  })

  it('loadSavedPrompt ignores localStorage read errors', () => {
    const spy = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { loadSavedPrompt, DEFAULT_PROMPT, promptText } = useTechnicalPrompt()
    loadSavedPrompt()
    expect(promptText.value).toBe(DEFAULT_PROMPT)
    spy.mockRestore()
  })

  it('savePrompt updates ref and localStorage', () => {
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { savePrompt, promptText } = useTechnicalPrompt()
    savePrompt('hello')
    expect(promptText.value).toBe('hello')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('hello')
  })

  it('resetPrompt restores default and clears storage', () => {
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { resetPrompt, promptText, DEFAULT_PROMPT } = useTechnicalPrompt()
    localStorage.setItem(STORAGE_KEY, 'x')
    resetPrompt()
    expect(promptText.value).toBe(DEFAULT_PROMPT)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('resetPrompt still resets text when removeItem throws', () => {
    const rm = jest.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('denied')
    })
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { resetPrompt, promptText, DEFAULT_PROMPT } = useTechnicalPrompt()
    resetPrompt()
    expect(promptText.value).toBe(DEFAULT_PROMPT)
    rm.mockRestore()
  })

  it('savePrompt ignores localStorage write errors', () => {
    const spy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { savePrompt, promptText } = useTechnicalPrompt()
    savePrompt('still')
    expect(promptText.value).toBe('still')
    spy.mockRestore()
  })

  it('copyPrompt resolves when clipboard exists', async () => {
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { copyPrompt } = useTechnicalPrompt()
    const writeText = jest.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    await expect(copyPrompt()).resolves.toBeUndefined()
    expect(writeText).toHaveBeenCalled()
  })

  it('copyPrompt resolves when clipboard is missing', async () => {
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { copyPrompt } = useTechnicalPrompt()
    const prev = navigator.clipboard
    delete navigator.clipboard
    await expect(copyPrompt()).resolves.toBeUndefined()
    if (prev) navigator.clipboard = prev
  })

  it('downloadPrompt creates blob link', () => {
    const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
    const { downloadPrompt, promptText } = useTechnicalPrompt()
    promptText.value = 'md'
    const prevCreate = URL.createObjectURL
    const prevRevoke = URL.revokeObjectURL
    URL.createObjectURL = jest.fn(() => 'blob:z')
    URL.revokeObjectURL = jest.fn()
    const link = { click: jest.fn() }
    jest.spyOn(document, 'createElement').mockReturnValue(link)
    jest.spyOn(document.body, 'appendChild').mockImplementation(() => {})
    jest.spyOn(document.body, 'removeChild').mockImplementation(() => {})
    downloadPrompt()
    expect(link.click).toHaveBeenCalled()
    URL.createObjectURL = prevCreate
    URL.revokeObjectURL = prevRevoke
    document.createElement.mockRestore()
    document.body.appendChild.mockRestore()
    document.body.removeChild.mockRestore()
  })
})

describe('useTechnicalPrompt DEFAULT_PROMPT coherence rules (regression guard)', () => {
  const { useTechnicalPrompt } = require('../../composables/useTechnicalPrompt')
  const { DEFAULT_PROMPT } = useTechnicalPrompt()

  it('mandates one epic per commercial card with verbatim epicKey', () => {
    expect(DEFAULT_PROMPT).toContain('EXACTAMENTE UNA')
    expect(DEFAULT_PROMPT).toContain('EXACTO Y VERBATIM')
    expect(DEFAULT_PROMPT).toContain('NUNCA `admin-module`')
  })

  it('forbids epics for non-contracted modules', () => {
    expect(DEFAULT_PROMPT).toContain('PROHIBIDO crear épicas para módulos NO contratados')
  })

  it('enumerates the 5 base modules including ai_automation_module', () => {
    expect(DEFAULT_PROMPT).toContain('ai_automation_module')
    expect(DEFAULT_PROMPT).toContain('5 módulos base')
    expect(DEFAULT_PROMPT).not.toContain('4 módulos base')
  })

  it('requires the commercial cross-cutting epic', () => {
    expect(DEFAULT_PROMPT).toContain('\`features\`, \`cross_cutting_features\`')
  })

  it('requires links for every commercial cross-cutting item', () => {
    expect(DEFAULT_PROMPT).toContain('incluidos TODOS los items de la tarjeta comercial \`cross_cutting_features\`')
  })

  it('prevents a technical-only epic from duplicating the commercial cross-cutting card', () => {
    expect(DEFAULT_PROMPT).toContain('no puede duplicar \`cross_cutting_features\`')
  })

  it('requires canonical linked_module_ids on additional-module epics', () => {
    expect(DEFAULT_PROMPT).toContain('["module-<id>"]')
    expect(DEFAULT_PROMPT).toContain('OBLIGATORIO')
  })

  it('requires every commercial item to be linked by at least one requirement (DEBE)', () => {
    expect(DEFAULT_PROMPT).toContain('DEBE quedar enlazado por AL MENOS un requerimiento')
    expect(DEFAULT_PROMPT).not.toContain('debería quedar enlazado')
  })

  it('defines the halt rule when step-1 functionalRequirements is missing', () => {
    expect(DEFAULT_PROMPT).toContain('REGLA DE ALTO')
    expect(DEFAULT_PROMPT).toContain('NO generes el JSON')
  })

  it('allows underscores in epicKey while keeping flowKey kebab', () => {
    expect(DEFAULT_PROMPT).toContain('guiones y guiones bajos')
    expect(DEFAULT_PROMPT).toMatch(/flowKey\*\*: ASCII, minúsculas, números y guiones \(kebab\)/)
  })

  it('prefers small requirements and splits five-point stories', () => {
    expect(DEFAULT_PROMPT).toContain('preferencia equivalente a 1–3 puntos')
    expect(DEFAULT_PROMPT).toContain('5 puntos o más')
    expect(DEFAULT_PROMPT).toContain('divídela en requerimientos independientes')
  })

  it('models external integrations for resilient cached reads', () => {
    expect(DEFAULT_PROMPT).toContain('Modelo de datos para integraciones resilientes')
    expect(DEFAULT_PROMPT).toContain('estado de salud y la política de retención/cache')
    expect(DEFAULT_PROMPT).toContain('último dato válido, frescura, checksum y expiración')
  })

  it('includes the pre-output checklist', () => {
    expect(DEFAULT_PROMPT).toContain('CHECKLIST ANTES DE RESPONDER')
    expect(DEFAULT_PROMPT).toContain('Cobertura total de items')
    expect(DEFAULT_PROMPT).toContain('cero ids inventados')
  })
})
