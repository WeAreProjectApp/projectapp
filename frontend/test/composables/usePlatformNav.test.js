/**
 * Tests for usePlatformNav — la fuente única de navegación de la plataforma.
 *
 * Protege contra la regresión que motivó este composable: el sidebar desktop
 * y el drawer móvil tenían la nav duplicada y derivaron (el drawer seguía
 * enlazando Dashboard y los módulos globales que el refactor de IA convirtió
 * en redirects).
 */

global.useI18n = jest.fn(() => ({ t: key => ({ "platformBilling.accounts": "Cuentas de cobro", "platformBilling.hosting": "Hosting" })[key] || key }))
global.useLocalePath = jest.fn(() => (path) => path)
global.useRoute = jest.fn(() => ({ path: '/platform/projects' }))

const mockAuth = { isAdmin: false, isClient: false }
jest.mock('../../stores/platform-auth', () => ({
  usePlatformAuthStore: jest.fn(() => mockAuth),
}))
jest.mock('../../stores/platform-notifications', () => ({
  usePlatformNotificationsStore: jest.fn(() => ({ unreadCount: 5 })),
}))

import { usePlatformNav } from '../../composables/usePlatformNav'

describe('usePlatformNav', () => {
  beforeEach(() => {
    mockAuth.isAdmin = false
    mockAuth.isClient = false
    global.useRoute = jest.fn(() => ({ path: '/platform/projects' }))
  })

  it('expone Notificaciones y Proyectos para cualquier rol', () => {
    const { primaryItems } = usePlatformNav()
    const labels = primaryItems.value.map((i) => i.label)
    expect(labels).toContain('Notificaciones')
    expect(labels).toContain('Proyectos')
  })

  it('oculta Clientes para el rol client y lo muestra para admin', () => {
    let { primaryItems } = usePlatformNav()
    expect(primaryItems.value.map((i) => i.label)).not.toContain('Clientes')

    mockAuth.isAdmin = true
    ;({ primaryItems } = usePlatformNav())
    expect(primaryItems.value.map((i) => i.label)).toContain('Clientes')
  })

  it('no expone las rutas globales eliminadas por el refactor de IA', () => {
    mockAuth.isAdmin = true
    const { primaryItems, accountItems, adminItems } = usePlatformNav()
    const hrefs = [...primaryItems.value, ...accountItems.value, ...adminItems.value].map((i) => i.href)
    for (const dead of [
      '/platform/dashboard',
      '/platform/board',
      '/platform/bugs',
      '/platform/changes',
      '/platform/deliverables',
    ]) {
      expect(hrefs).not.toContain(dead)
    }
  })

  it('ofrece las lecturas de cuentas y hosting en la navegación común', () => {
    const { primaryItems } = usePlatformNav()
    expect(primaryItems.value.find(item => item.label === 'Cuentas de cobro').href).toBe('/platform/collection-accounts')
    expect(primaryItems.value.find(item => item.label === 'Hosting').href).toBe('/platform/payments')
  })

  it('muestra Documentos apuntando al portal del cliente para el rol client', () => {
    mockAuth.isClient = true
    const { primaryItems } = usePlatformNav()
    const documentos = primaryItems.value.find((i) => i.label === 'Documentos')
    expect(documentos).toBeTruthy()
    expect(documentos.href).toBe('/platform/documents')
  })

  it('oculta Documentos cuando el usuario no es client', () => {
    mockAuth.isAdmin = true
    const { primaryItems } = usePlatformNav()
    expect(primaryItems.value.map((i) => i.label)).not.toContain('Documentos')
  })

  it('isActive coincide en ruta exacta y anidada, ignorando el prefijo de locale', () => {
    global.useRoute = jest.fn(() => ({ path: '/en-us/platform/projects/5/board' }))
    const { isActive } = usePlatformNav()
    expect(isActive('/en-us/platform/projects')).toBe(true)
    expect(isActive('/en-us/platform/clients')).toBe(false)
  })
})
