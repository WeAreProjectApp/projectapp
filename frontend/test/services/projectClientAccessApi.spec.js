import { createProjectClientAccessApi } from '../../services/projectClientAccessApi'

describe('createProjectClientAccessApi', () => {
  let transport
  let api

  beforeEach(() => {
    transport = { get: jest.fn(), patch: jest.fn(), post: jest.fn() }
    api = createProjectClientAccessApi(transport, 42)
  })

  it('reads the limited client projection without a credential request', async () => {
    // Falla si la vista limitada usa por error la ruta de revelación de secretos.
    transport.get.mockResolvedValueOnce({ data: { project_id: 42, environments: [] } })

    const result = await api.client()

    expect(transport.get).toHaveBeenCalledWith('projects/42/client-access/')
    expect(transport.post).toHaveBeenCalledTimes(0)
    expect(result).toEqual({ project_id: 42, environments: [] })
  })

  it('reads the project policy from its administrative route', async () => {
    // Falla si el panel consulta una política de otro proyecto o el endpoint de cliente.
    transport.get.mockResolvedValueOnce({ data: { version: 8 } })

    const result = await api.policy()

    expect(transport.get).toHaveBeenCalledWith('projects/42/access/client-policy/')
    expect(result).toEqual({ version: 8 })
  })

  it('updates the project policy with the submitted matrix', async () => {
    // Falla si la matriz de visibilidad se envía a una ruta distinta de la política del proyecto.
    const payload = { expected_version: 8, source_token: 'token-8', permissions: { production: {} } }
    transport.patch.mockResolvedValueOnce({ data: { version: 9 } })

    const result = await api.updatePolicy(payload)

    expect(transport.patch).toHaveBeenCalledWith('projects/42/access/client-policy/', payload)
    expect(result).toEqual({ version: 9 })
  })

  it('reveals one requested credential through its dedicated route', async () => {
    // Falla si una revelación se convierte en una carga general de accesos o envía campos extra.
    transport.post.mockResolvedValueOnce({ data: { secret: 'clave-efimera' } })

    const result = await api.reveal('production', 'admin_password')

    expect(transport.post).toHaveBeenCalledWith(
      'projects/42/client-access/environments/production/credentials/admin_password/reveal/',
      {},
    )
    expect(result).toEqual({ secret: 'clave-efimera' })
  })
})
