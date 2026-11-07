import { setActivePinia, createPinia } from 'pinia'
import { usePlatformProjectsStore } from '../../stores/platform-projects'

jest.mock('../../composables/usePlatformApi', () => {
  const mockGet = jest.fn()
  const mockPost = jest.fn()
  const mockPatch = jest.fn()
  const mockDelete = jest.fn()
  return {
    usePlatformApi: () => ({
      get: mockGet,
      post: mockPost,
      patch: mockPatch,
      delete: mockDelete,
    }),
    readPlatformSession: jest.fn(() => ({
      accessToken: '', refreshToken: '', user: null,
      verificationToken: '', pendingEmail: '',
    })),
    writePlatformSession: jest.fn(),
    clearPlatformSession: jest.fn(),
    __mockGet: mockGet,
    __mockPost: mockPost,
    __mockPatch: mockPatch,
    __mockDelete: mockDelete,
  }
})

const {
  __mockGet: mockGet,
  __mockPost: mockPost,
  __mockPatch: mockPatch,
  __mockDelete: mockDelete,
} = require('../../composables/usePlatformApi')

const SAMPLE_PROJECT = {
  id: 1,
  name: 'Website Redesign',
  status: 'active',
  status_label: 'Activo',
  current_state: {
    id: 2,
    name: 'Activo',
    color: 'emerald',
    operational_effect: 'operating',
  },
  progress: 40,
  client_name: 'Ana García',
}

describe('usePlatformProjectsStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformProjectsStore()
    jest.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty projects array', () => {
      expect(store.projects).toEqual([])
      expect(store.currentProject).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.error).toBe('')
      expect(store.errorStatus).toBeNull()
    })
  })

  describe('getters', () => {
    beforeEach(() => {
      store.projects = [
        { ...SAMPLE_PROJECT, id: 1, current_state: { operational_effect: 'development' } },
        { ...SAMPLE_PROJECT, id: 2, current_state: { operational_effect: 'operating' } },
        { ...SAMPLE_PROJECT, id: 3, current_state: { operational_effect: 'suspended' } },
        { ...SAMPLE_PROJECT, id: 4, current_state: { operational_effect: 'completed' } },
        { ...SAMPLE_PROJECT, id: 5, current_state: { operational_effect: 'decommissioned' } },
      ]
    })

    it('developmentProjects filters by lifecycle effect', () => {
      expect(store.developmentProjects).toHaveLength(1)
    })

    it('activeProjects filters by lifecycle effect', () => {
      expect(store.activeProjects).toHaveLength(1)
    })

    it('suspendedProjects filters by lifecycle effect', () => {
      expect(store.suspendedProjects).toHaveLength(1)
    })

    it('completedProjects filters by lifecycle effect', () => {
      expect(store.completedProjects).toHaveLength(1)
    })

    it('decommissionedProjects filters by lifecycle effect', () => {
      expect(store.decommissionedProjects).toHaveLength(1)
    })

    it('projectCount returns total count', () => {
      expect(store.projectCount).toBe(5)
    })
  })

  describe('fetchProjects', () => {
    it('populates projects on success', async () => {
      mockGet.mockResolvedValueOnce({ data: [SAMPLE_PROJECT] })

      const result = await store.fetchProjects()

      expect(result.success).toBe(true)
      expect(store.projects).toEqual([SAMPLE_PROJECT])
      expect(store.isLoading).toBe(false)
    })

    it('appends filter query params', async () => {
      mockGet.mockResolvedValueOnce({ data: [] })

      await store.fetchProjects({ client: 5, status: 'active' })

      expect(mockGet).toHaveBeenCalledWith(
        expect.stringContaining('client=5'),
      )
      expect(mockGet).toHaveBeenCalledWith(
        expect.stringContaining('status=active'),
      )
    })

    it('sets error on failure', async () => {
      mockGet.mockRejectedValueOnce({
        response: { data: { detail: 'Error de red.' } },
      })

      const result = await store.fetchProjects()

      expect(result.success).toBe(false)
      expect(store.error).toBe('Error de red.')
    })
  })

  describe('fetchProject', () => {
    it('sets currentProject on success', async () => {
      mockGet.mockResolvedValueOnce({ data: SAMPLE_PROJECT })

      const result = await store.fetchProject(1)

      expect(result.success).toBe(true)
      expect(store.currentProject).toEqual(SAMPLE_PROJECT)
    })

    it('sets error on failure', async () => {
      mockGet.mockRejectedValueOnce({
        response: { data: { detail: 'No encontrado.' } },
      })

      const result = await store.fetchProject(999)

      expect(result.success).toBe(false)
      expect(store.error).toBe('No encontrado.')
    })

    // Falla si una respuesta lenta de otro espacio reemplaza el proyecto de la ruta actual.
    it('keeps the newer project when an older successful request finishes last', async () => {
      let resolveFirst
      let resolveSecond
      mockGet
        .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
        .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))

      const firstRequest = store.fetchProject(1)
      const secondRequest = store.fetchProject(2)
      expect(store.isLoading).toBe(true)

      resolveSecond({ data: { ...SAMPLE_PROJECT, id: 2, name: 'Proyecto actual' } })
      const secondResult = await secondRequest
      resolveFirst({ data: { ...SAMPLE_PROJECT, id: 1, name: 'Proyecto anterior' } })
      const firstResult = await firstRequest

      expect(secondResult).toEqual({success:true,data:{...SAMPLE_PROJECT,id:2,name:'Proyecto actual'}})
      expect(firstResult).toEqual({success:false,stale:true})
      expect(store.currentProject).toEqual({...SAMPLE_PROJECT,id:2,name:'Proyecto actual'})
      expect(store.isLoading).toBe(false)
    })

    // Falla si un 403 tardío expone el error de un proyecto anterior sobre el espacio actual.
    it('discards an older access error after the newer project loads', async () => {
      let rejectFirst
      let resolveSecond
      mockGet
        .mockImplementationOnce(() => new Promise((resolve, reject) => { rejectFirst = reject }))
        .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))

      const firstRequest = store.fetchProject(1)
      const secondRequest = store.fetchProject(2)
      resolveSecond({ data: { ...SAMPLE_PROJECT, id: 2, name: 'Proyecto autorizado' } })
      await secondRequest
      rejectFirst({response:{status:403,data:{detail:'Sin acceso al proyecto anterior.'}}})
      const firstResult = await firstRequest

      expect(firstResult).toEqual({success:false,stale:true})
      expect(store.currentProject).toEqual({...SAMPLE_PROJECT,id:2,name:'Proyecto autorizado'})
      expect(store.error).toBe('')
      expect(store.errorStatus).toBeNull()
    })
  })

  describe('createProject', () => {
    it('prepends new project to list on success', async () => {
      store.projects = [{ ...SAMPLE_PROJECT, id: 2 }]
      const newProject = { ...SAMPLE_PROJECT, id: 3 }
      mockPost.mockResolvedValueOnce({ data: newProject })

      const result = await store.createProject({ name: 'New', client_id: 1 })

      expect(result.success).toBe(true)
      expect(store.projects[0]).toEqual(newProject)
      expect(store.projects).toHaveLength(2)
    })

    it('sets error on failure', async () => {
      mockPost.mockRejectedValueOnce({
        response: { data: { detail: 'Cliente no encontrado.' } },
      })

      const result = await store.createProject({ name: 'X', client_id: 999 })

      expect(result.success).toBe(false)
      expect(store.error).toBe('Cliente no encontrado.')
    })
  })

  describe('updateProject', () => {
    it('replaces project in list on success', async () => {
      store.projects = [SAMPLE_PROJECT]
      const updated = { ...SAMPLE_PROJECT, name: 'Updated' }
      mockPatch.mockResolvedValueOnce({ data: updated })

      const result = await store.updateProject(1, { name: 'Updated' })

      expect(result.success).toBe(true)
      expect(store.projects[0].name).toBe('Updated')
    })

    it('updates currentProject if matching', async () => {
      store.projects = [SAMPLE_PROJECT]
      store.currentProject = SAMPLE_PROJECT
      const updated = { ...SAMPLE_PROJECT, name: 'Updated' }
      mockPatch.mockResolvedValueOnce({ data: updated })

      await store.updateProject(1, { name: 'Updated' })

      expect(store.currentProject.name).toBe('Updated')
    })

    it('sets error on failure', async () => {
      mockPatch.mockRejectedValueOnce({
        response: { data: { detail: 'No autorizado.' } },
      })

      const result = await store.updateProject(1, { name: 'X' })

      expect(result.success).toBe(false)
      expect(store.error).toBe('No autorizado.')
      expect(store.isUpdating).toBe(false)
    })
  })

  describe('fetchAccessList', () => {
    it('returns access data on success', async () => {
      const access = [{ id: 1, name: 'GIM', admin_password: 'pw' }]
      mockGet.mockResolvedValueOnce({ data: access })

      const result = await store.fetchAccessList()

      expect(mockGet).toHaveBeenCalledWith('projects/access/')
      expect(result).toEqual({ success: true, data: access })
    })

    it('sets error message on failure', async () => {
      mockGet.mockRejectedValueOnce({
        response: { data: { detail: 'Prohibido.' } },
      })

      const result = await store.fetchAccessList()

      expect(result.success).toBe(false)
      expect(result.message).toBe('Prohibido.')
      expect(store.error).toBe('Prohibido.')
    })

    it('uses fallback message when error has no detail', async () => {
      mockGet.mockRejectedValueOnce({ response: { data: {} } })

      const result = await store.fetchAccessList()

      expect(result.message).toBe('No pudimos cargar los accesos.')
    })
  })

  describe('error fallback messages', () => {
    it('fetchProjects uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))

      const result = await store.fetchProjects()

      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar los proyectos.')
    })

    it('fetchProject uses fallback when detail is absent', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))

      const result = await store.fetchProject(1)

      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos cargar el proyecto.')
    })

    it('createProject uses fallback when detail is absent', async () => {
      mockPost.mockRejectedValueOnce(new Error('network'))

      const result = await store.createProject({ name: 'x' })

      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos crear el proyecto.')
    })

    it('updateProject uses fallback when detail is absent', async () => {
      mockPatch.mockRejectedValueOnce(new Error('network'))

      const result = await store.updateProject(1, { name: 'x' })

      expect(result.success).toBe(false)
      expect(result.message).toBe('No pudimos actualizar el proyecto.')
    })
  })

  describe('updateProject conditional branches', () => {
    it('does not update currentProject when id does not match', async () => {
      store.projects = [SAMPLE_PROJECT]
      store.currentProject = { ...SAMPLE_PROJECT, id: 99 }
      mockPatch.mockResolvedValueOnce({ data: { ...SAMPLE_PROJECT, name: 'Updated' } })

      await store.updateProject(1, { name: 'Updated' })

      expect(store.currentProject.id).toBe(99)
      expect(store.currentProject.name).toBe('Website Redesign')
    })

    it('preserves other projects in list when updating one', async () => {
      store.projects = [SAMPLE_PROJECT, { ...SAMPLE_PROJECT, id: 2, name: 'Other' }]
      mockPatch.mockResolvedValueOnce({ data: { ...SAMPLE_PROJECT, name: 'Updated' } })

      await store.updateProject(1, { name: 'Updated' })

      expect(store.projects[1].name).toBe('Other')
    })

  })

  describe('fetchProjects branches', () => {
    it('uses plain URL when no filters provided', async () => {
      mockGet.mockResolvedValueOnce({ data: [] })

      await store.fetchProjects()

      expect(mockGet).toHaveBeenCalledWith('projects/')
    })

    it('uses fallback message when error has no detail', async () => {
      mockGet.mockRejectedValueOnce({})

      const result = await store.fetchProjects()

      expect(result.message).toBe('No pudimos cargar los proyectos.')
    })
  })

  describe('fetchProject branches', () => {
    it('uses fallback message when error has no detail', async () => {
      mockGet.mockRejectedValueOnce({})

      const result = await store.fetchProject(1)

      expect(result.message).toBe('No pudimos cargar el proyecto.')
    })
  })

  describe('createProject branches', () => {
    it('returns errors field when server sends field errors', async () => {
      mockPost.mockRejectedValueOnce({ response: { data: { name: ['required'] } } })

      const result = await store.createProject({})

      expect(result.errors).toEqual({ name: ['required'] })
    })

    it('uses fallback message when error has no detail', async () => {
      mockPost.mockRejectedValueOnce({})

      const result = await store.createProject({})

      expect(result.message).toBe('No pudimos crear el proyecto.')
    })
  })

  describe('updateProject branches', () => {
    it('does not touch currentProject when ids differ', async () => {
      store.currentProject = SAMPLE_PROJECT
      mockPatch.mockResolvedValueOnce({ data: { ...SAMPLE_PROJECT, id: 99, name: 'X' } })

      await store.updateProject(99, { name: 'X' })

      expect(store.currentProject.name).toBe(SAMPLE_PROJECT.name)
    })

    it('uses fallback message when error has no detail', async () => {
      mockPatch.mockRejectedValueOnce({})

      const result = await store.updateProject(1, {})

      expect(result.message).toBe('No pudimos actualizar el proyecto.')
    })
  })
})
