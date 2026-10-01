import { createProjectIdeasApi } from '../../services/projectIdeasApi'

describe('createProjectIdeasApi', () => {
  let transport
  let api

  beforeEach(() => {
    transport = {
      get: jest.fn(),
      post: jest.fn(),
      patch: jest.fn(),
    }
    api = createProjectIdeasApi(transport, 42)
  })

  it('returns an unwrapped new idea from its project route', async () => {
    // Falla si una idea se publica fuera del proyecto visible o se filtra el wrapper HTTP a la UI.
    const payload = { text: 'Reducir pasos de aprobación', request_id: 'idea-request-1' }
    transport.post.mockResolvedValueOnce({ data: { id: 7, text: payload.text } })

    const result = await api.create(payload)

    expect(transport.post).toHaveBeenCalledWith('projects/42/ideas/', payload)
    expect(result).toEqual({ id: 7, text: 'Reducir pasos de aprobación' })
  })

  it('returns an unwrapped idea edit from its project route', async () => {
    // Falla si la edición apunta a una idea de otro proyecto o entrega el wrapper Axios.
    const payload = { text: 'Reducir aún más pasos', expected_version: 3 }
    transport.patch.mockResolvedValueOnce({ data: { id: 7, version: 4, text: payload.text } })

    const result = await api.edit(7, payload)

    expect(transport.patch).toHaveBeenCalledWith('projects/42/ideas/7/', payload)
    expect(result).toEqual({ id: 7, version: 4, text: 'Reducir aún más pasos' })
  })

  it('returns an unwrapped collection from its project route', async () => {
    // Falla si la recopilación crea una colección en un proyecto ajeno o deja el wrapper HTTP expuesto.
    const payload = { title: 'Futuro contrato', items: [{ idea_id: 7, expected_version: 4 }], request_id: 'collection-request-1' }
    transport.post.mockResolvedValueOnce({ data: { id: 3, title: payload.title } })

    const result = await api.collect(payload)

    expect(transport.post).toHaveBeenCalledWith('projects/42/idea-collections/', payload)
    expect(result).toEqual({ id: 3, title: 'Futuro contrato' })
  })
})
