import { createPinia, setActivePinia } from 'pinia'
import { usePlatformClientAccessStore } from '../../stores/platform-client-access'

function deferred() {
  let resolve
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise })
  return { promise, resolve }
}

describe('usePlatformClientAccessStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformClientAccessStore()
  })

  it('leaves no access projection after clearing a pending project load', async () => {
    // Falla si desmontar una vista permite que URLs o acciones tardías vuelvan a aparecer.
    const response = deferred()
    const api = { client: jest.fn(() => response.promise) }

    const loading = store.load(41, api)
    store.clear()
    response.resolve({ project_id: 41, environments: [{ environment: 'production', site_url: 'https://old.example' }] })
    await loading

    expect(store.projectId).toBeNull()
    expect(store.environments).toEqual([])
  })

  it('keeps only the replacement project access projection after a late response', async () => {
    // Falla si un proyecto nuevo hereda URLs o acciones de credenciales del proyecto que se dejó atrás.
    const oldResponse = deferred()
    const oldApi = { client: jest.fn(() => oldResponse.promise) }
    const newApi = { client: jest.fn().mockResolvedValue({ project_id: 52, environments: [{ environment: 'staging', admin_url: 'https://qa.example' }] }) }

    const oldLoad = store.load(41, oldApi)
    const newLoad = store.load(52, newApi)
    oldResponse.resolve({ project_id: 41, environments: [{ environment: 'production', site_url: 'https://old.example' }] })
    await Promise.all([oldLoad, newLoad])

    expect(store.projectId).toBe(52)
    expect(store.environments).toEqual([{ environment: 'staging', admin_url: 'https://qa.example' }])
  })

  it('drops injected private fields from a client projection', async () => {
    // Falla si un serializer equivocado deja una contraseña, notas o repositorio en el estado persistente de la vista.
    const api = {
      client: jest.fn().mockResolvedValue({
        project_id: 52,
        environments: [{
          environment: 'production',
          site_url: 'https://public.example',
          credential_actions: ['admin_password', 'secret'],
          admin_password: 'never-store-this',
          secret: 'never-store-this-either',
          notes: 'nota interna',
          repository: 'git@internal.example:private.git',
        }],
      }),
    }

    await store.load(52, api)

    expect(store.$state.environments).toEqual([{
      environment: 'production',
      site_url: 'https://public.example',
      credential_actions: ['admin_password'],
    }])
    expect(JSON.stringify(store.$state)).not.toContain('never-store-this')
  })
})
