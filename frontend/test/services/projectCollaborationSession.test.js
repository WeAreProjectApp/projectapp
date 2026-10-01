import { hasPersonalPlatformSession } from '../../services/projectCollaborationSession'

function tokenFor(payload) {
  const encoded = btoa(JSON.stringify(payload)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
  return `header.${encoded}.signature`
}

describe('hasPersonalPlatformSession', () => {
  it('accepts a normal signed session payload', () => {
    // Falla si una sesión personal pierde los controles permitidos por una lectura errónea del JWT.
    expect(hasPersonalPlatformSession(tokenFor({ sub: 17, role: 'client' }))).toBe(true)
  })

  it('rejects an impersonated session payload', () => {
    // Falla si una sesión suplantada recibe botones de escritura o revelación antes del control del backend.
    expect(hasPersonalPlatformSession(tokenFor({ sub: 17, impersonated_by: 2 }))).toBe(false)
  })

  it('rejects a malformed session token', () => {
    // Falla si un token inválido habilita acciones sensibles desde una interfaz que no puede validar su procedencia.
    expect(hasPersonalPlatformSession('not-a-jwt')).toBe(false)
  })
})
