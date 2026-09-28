/**
 * Tests for documents store (panel admin).
 */
import { setActivePinia, createPinia } from 'pinia'
import { useDocumentStore } from '../../stores/documents'

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}))

const {
  get_request,
  create_request,
  patch_request,
  delete_request,
} = require('../../stores/services/request_http')

describe('useDocumentStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useDocumentStore()
    jest.clearAllMocks()
    jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty documents', () => {
      expect(store.documents).toEqual([])
      expect(store.currentDocument).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.isUpdating).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('getDocumentById', () => {
    it('returns document matching id', () => {
      store.documents = [{ id: 1, title: 'A' }, { id: 2, title: 'B' }]
      expect(store.getDocumentById(2)).toEqual({ id: 2, title: 'B' })
    })
  })

  describe('fetchDocuments', () => {
    it('stores list on success', async () => {
      get_request.mockResolvedValueOnce({ data: [{ id: 1 }] })
      const result = await store.fetchDocuments()
      expect(result.success).toBe(true)
      expect(store.documents).toEqual([{ id: 1 }])
      expect(store.isLoading).toBe(false)
    })

    it('returns errors payload on failure', async () => {
      get_request.mockRejectedValueOnce({ response: { data: { detail: 'x' } } })
      const result = await store.fetchDocuments()
      expect(result.success).toBe(false)
      expect(store.error).toBe('fetch_failed')
      expect(result.errors).toEqual({ detail: 'x' })
    })

    it('normalizes failure into message/code/status', async () => {
      get_request.mockRejectedValueOnce({
        response: { status: 500, data: { detail: 'boom' } },
      })
      const result = await store.fetchDocuments()
      expect(result.message).toBe('boom')
      expect(result.status).toBe(500)
    })

    it('falls back to a spanish message when the error has no payload', async () => {
      get_request.mockRejectedValueOnce(new Error('network'))
      const result = await store.fetchDocuments()
      expect(result.success).toBe(false)
      expect(result.message).toBe('No se pudieron cargar los documentos.')
    })

    it('calls documents/ with no query params when no filters active', async () => {
      get_request.mockResolvedValueOnce({ data: [] })
      await store.fetchDocuments()
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active')
    })

    it('sends folder query param when activeFolderId is a numeric id', async () => {
      store.activeFolderId = 7
      get_request.mockResolvedValueOnce({ data: [] })
      await store.fetchDocuments()
      expect(get_request).toHaveBeenCalledWith('documents/?folder=7&scope=active')
    })

    it('sends folder=none when activeFolderId is "none"', async () => {
      store.activeFolderId = 'none'
      get_request.mockResolvedValueOnce({ data: [] })
      await store.fetchDocuments()
      expect(get_request).toHaveBeenCalledWith('documents/?folder=none&scope=active')
    })

    it('sends tags query param when activeTagIds has values', async () => {
      store.activeTagIds = [3, 5]
      get_request.mockResolvedValueOnce({ data: [] })
      await store.fetchDocuments()
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active&tags=3%2C5')
    })

    it('accepts override params without mutating store filters', async () => {
      store.activeFolderId = 'all'
      store.activeTagIds = []
      get_request.mockResolvedValueOnce({ data: [] })
      await store.fetchDocuments({ folder: 2, tags: [9] })
      expect(get_request).toHaveBeenCalledWith('documents/?folder=2&scope=active&tags=9')
      expect(store.activeFolderId).toBe('all')
      expect(store.activeTagIds).toEqual([])
    })
  })

  describe('setFilters', () => {
    it('updates folder and triggers refetch', async () => {
      get_request.mockResolvedValueOnce({ data: [] })
      await store.setFilters({ folder: 4 })
      expect(store.activeFolderId).toBe(4)
      expect(get_request).toHaveBeenCalledWith('documents/?folder=4&scope=active')
    })

    it('updates tags array by cloning input', async () => {
      get_request.mockResolvedValueOnce({ data: [] })
      const inputTags = [1, 2]
      await store.setFilters({ tags: inputTags })
      expect(store.activeTagIds).toEqual([1, 2])
      expect(store.activeTagIds).not.toBe(inputTags)
    })

    it('supports clearing tags with empty array', async () => {
      store.activeTagIds = [1]
      get_request.mockResolvedValueOnce({ data: [] })
      await store.setFilters({ tags: [] })
      expect(store.activeTagIds).toEqual([])
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active')
    })
  })

  describe('toggleTagFilter', () => {
    it('adds a tag id when absent and refetches', async () => {
      get_request.mockResolvedValueOnce({ data: [] })
      await store.toggleTagFilter(8)
      expect(store.activeTagIds).toEqual([8])
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active&tags=8')
    })

    it('removes a tag id when already present', async () => {
      store.activeTagIds = [1, 2, 3]
      get_request.mockResolvedValueOnce({ data: [] })
      await store.toggleTagFilter(2)
      expect(store.activeTagIds).toEqual([1, 3])
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active&tags=1%2C3')
    })

    it('keeps the archived scope when toggling a tag', async () => {
      // Togglear una etiqueta dentro de Archivados no debe devolver al usuario
      // a la vista de activos: el scope viaja explícito en el refetch.
      store.archiveScope = 'archived'
      get_request.mockResolvedValueOnce({ data: [] })
      await store.toggleTagFilter(8)
      expect(store.activeTagIds).toEqual([8])
      expect(get_request).toHaveBeenCalledWith('documents/?scope=archived&tags=8')
    })
  })

  describe('fetchDocument', () => {
    it('sets currentDocument on success', async () => {
      get_request.mockResolvedValueOnce({ data: { id: 5, title: 'Doc' } })
      const result = await store.fetchDocument(5)
      expect(result.success).toBe(true)
      expect(store.currentDocument).toEqual({ id: 5, title: 'Doc' })
    })

    it('returns failure when detail fetch errors', async () => {
      get_request.mockRejectedValueOnce({ response: { data: {} } })
      const result = await store.fetchDocument(1)
      expect(result.success).toBe(false)
      expect(store.error).toBe('fetch_detail_failed')
    })
  })

  describe('createFromMarkdown', () => {
    it('returns the new ID for loading its editor', async () => {
      const payload = { title: 'T', content_markdown: '# Hi' }
      create_request.mockResolvedValueOnce({ data: { id: 9 } })
      const result = await store.createFromMarkdown(payload)
      expect(create_request).toHaveBeenCalledWith('documents/create-from-markdown/', payload)
      expect(result.success).toBe(true)
      expect(result.data.id).toBe(9)
      expect(store.currentDocument).toBeNull()
    })

    it('returns errors when create fails', async () => {
      create_request.mockRejectedValueOnce({ response: { data: { err: 1 } } })
      const result = await store.createFromMarkdown({})
      expect(result.success).toBe(false)
      expect(store.error).toBe('create_from_markdown_failed')
    })
  })

  describe('updateDocument', () => {
    it('preserves loaded content when merging a write summary', async () => {
      store.currentDocument = { id: 2, content_markdown: '# Kept' }
      patch_request.mockResolvedValueOnce({ data: { id: 2, title: 'Up' } })
      const result = await store.updateDocument(2, { title: 'Up' })
      expect(patch_request).toHaveBeenCalledWith('documents/2/update/', { title: 'Up' })
      expect(result.success).toBe(true)
      expect(store.currentDocument).toMatchObject({ id: 2, title: 'Up', content_markdown: '# Kept' })
    })

    it('returns errors when patch fails', async () => {
      patch_request.mockRejectedValueOnce({ response: { data: { a: 1 } } })
      const result = await store.updateDocument(1, {})
      expect(result.success).toBe(false)
      expect(store.error).toBe('update_failed')
    })
  })

  describe('deleteDocument', () => {
    it('removes id from list and clears current when same id', async () => {
      store.documents = [{ id: 1 }, { id: 2 }]
      store.currentDocument = { id: 1 }
      delete_request.mockResolvedValueOnce({})
      const result = await store.deleteDocument(1)
      expect(result.success).toBe(true)
      expect(store.documents).toEqual([{ id: 2 }])
      expect(store.currentDocument).toBeNull()
    })

    it('keeps currentDocument when deleting other id', async () => {
      store.currentDocument = { id: 2 }
      store.documents = [{ id: 1 }, { id: 2 }]
      delete_request.mockResolvedValueOnce({})
      await store.deleteDocument(1)
      expect(store.currentDocument).toEqual({ id: 2 })
    })

    it('returns failure when delete errors', async () => {
      delete_request.mockRejectedValueOnce({ response: { data: { d: 1 } } })
      const result = await store.deleteDocument(9)
      expect(result.success).toBe(false)
      expect(store.error).toBe('delete_failed')
    })
  })

  describe('duplicateDocument', () => {
    it('reloads the list after duplication', async () => {
      store.documents = [{ id: 1 }]
      create_request.mockResolvedValueOnce({ data: { id: 2, copy: true } })
      get_request.mockResolvedValueOnce({ data: [{ id: 2, copy: true }, { id: 1 }] })
      const result = await store.duplicateDocument(1)
      expect(create_request).toHaveBeenCalledWith('documents/1/duplicate/', {})
      expect(result.success).toBe(true)
      expect(store.documents[0]).toEqual({ id: 2, copy: true })
    })

    it('returns errors when duplicate fails', async () => {
      create_request.mockRejectedValueOnce({ response: { data: {} } })
      const result = await store.duplicateDocument(1)
      expect(result.success).toBe(false)
      expect(store.error).toBe('duplicate_failed')
    })
  })

  describe('downloadPdf', () => {
    beforeEach(() => {
      global.URL.createObjectURL = jest.fn(() => 'blob:x')
      global.URL.revokeObjectURL = jest.fn()
    })

    it('requests the pdf blob and triggers a download', async () => {
      get_request.mockResolvedValue({ data: new Blob(['x']) })
      const clickSpy = jest.fn()
      jest.spyOn(document, 'createElement').mockReturnValue({
        href: '', setAttribute: jest.fn(), click: clickSpy, remove: jest.fn(),
      })
      jest.spyOn(document.body, 'appendChild').mockImplementation(() => {})

      const result = await store.downloadPdf(3, 'My Doc')
      expect(get_request).toHaveBeenCalledWith(
        'documents/3/pdf/', { responseType: 'blob' })
      expect(clickSpy).toHaveBeenCalled()
      expect(result.success).toBe(true)
    })

    it('appends the template query when given a valid style', async () => {
      get_request.mockResolvedValue({ data: new Blob(['x']) })
      jest.spyOn(document, 'createElement').mockReturnValue({
        href: '', setAttribute: jest.fn(), click: jest.fn(), remove: jest.fn(),
      })
      jest.spyOn(document.body, 'appendChild').mockImplementation(() => {})

      await store.downloadPdf(1, 't', 'friendly')
      expect(get_request).toHaveBeenCalledWith(
        'documents/1/pdf/?template=friendly', { responseType: 'blob' })
    })

    it('ignores an unknown template value', async () => {
      get_request.mockResolvedValue({ data: new Blob(['x']) })
      jest.spyOn(document, 'createElement').mockReturnValue({
        href: '', setAttribute: jest.fn(), click: jest.fn(), remove: jest.fn(),
      })
      jest.spyOn(document.body, 'appendChild').mockImplementation(() => {})

      await store.downloadPdf(1, 't', 'bogus')
      expect(get_request).toHaveBeenCalledWith(
        'documents/1/pdf/', { responseType: 'blob' })
    })

    it('returns an error result on failure', async () => {
      get_request.mockRejectedValue(new Error('boom'))
      const result = await store.downloadPdf(1)
      expect(result.success).toBe(false)
    })

    it('surfaces the backend detail carried inside the error blob', async () => {
      // Con responseType: 'blob' el 400 llega como Blob, no como JSON: sin
      // leerlo el usuario sólo ve el mensaje genérico.
      get_request.mockRejectedValue({
        response: {
          status: 400,
          data: new Blob(
            [JSON.stringify({ detail: 'El documento no tiene contenido para generar el PDF.' })],
            { type: 'application/json' },
          ),
        },
      })

      const result = await store.downloadPdf(122, 'Estimate')

      expect(result.success).toBe(false)
      expect(result.message).toBe('El documento no tiene contenido para generar el PDF.')
    })

    it('falls back to the generic message when the error blob is not json', async () => {
      get_request.mockRejectedValue({
        response: { status: 500, data: new Blob(['<html>oops</html>'], { type: 'text/html' }) },
      })

      const result = await store.downloadPdf(1)

      expect(result.message).toBe('No se pudo descargar el PDF.')
    })
  })

  describe('archive scope', () => {
    it('requests the archived scope when asked for it', async () => {
      get_request.mockResolvedValueOnce({ data: [{ id: 9, title: 'Viejo' }] })

      const result = await store.fetchDocuments({ scope: 'archived' })

      expect(get_request).toHaveBeenCalledWith('documents/?scope=archived')
      expect(result.success).toBe(true)
      expect(store.documents).toEqual([{ id: 9, title: 'Viejo' }])
    })

    it('asks for the oldest first when the date order says so', async () => {
      store.dateOrder = 'oldest'
      get_request.mockResolvedValueOnce({ data: [] })

      await store.setFilters({ scope: 'archived' })

      expect(get_request).toHaveBeenCalledWith('documents/?scope=archived&order=oldest')
    })

    it('applies the date order outside the archived scope', async () => {
      store.dateOrder = 'oldest'
      get_request.mockResolvedValueOnce({ data: [] })

      await store.setFilters({ scope: 'all' })

      expect(get_request).toHaveBeenCalledWith('documents/?scope=all&order=oldest')
    })

    it('does not leak the manager order into shared callers', async () => {
      store.dateOrder = 'oldest'
      get_request.mockResolvedValueOnce({ data: [] })

      await store.fetchDocuments()

      expect(get_request).toHaveBeenCalledWith('documents/?scope=active')
    })

    it('composes the archived scope with the active tag filter', async () => {
      store.activeTagIds = [2, 5]
      get_request.mockResolvedValueOnce({ data: [] })

      await store.fetchDocuments({ scope: 'archived' })

      expect(get_request).toHaveBeenCalledWith('documents/?scope=archived&tags=2%2C5')
    })

    it('never inherits the scope from the store', async () => {
      // create.vue, edit.vue y las pestañas de diagnóstico llaman sin scope y
      // jamás deben heredar el archivado que el gestor haya dejado puesto.
      store.archiveScope = 'archived'
      get_request.mockResolvedValueOnce({ data: [] })

      await store.fetchDocuments()

      expect(get_request).toHaveBeenCalledWith('documents/?scope=active')
    })

    it('omits the folder param at the hierarchical root', async () => {
      store.activeFolderId = 'root'
      get_request.mockResolvedValueOnce({ data: [] })

      await store.fetchDocuments({ scope: 'archived' })

      expect(get_request).toHaveBeenCalledWith('documents/?scope=archived')
    })

    it('discards a stale list response', async () => {
      let resolveFirst
      get_request.mockReturnValueOnce(new Promise((r) => { resolveFirst = r }))
      get_request.mockResolvedValueOnce({ data: [{ id: 2, title: 'Nuevo' }] })

      const first = store.fetchDocuments({ scope: 'active' })
      await store.fetchDocuments({ scope: 'active' })
      resolveFirst({ data: [{ id: 1, title: 'Viejo' }] })
      await first

      expect(store.documents).toEqual([{ id: 2, title: 'Nuevo' }])
    })

    it('archiveDocument drops the row while the active scope is showing', async () => {
      store.documents = [{ id: 7, title: 'Viejo' }, { id: 8, title: 'Otro' }]
      patch_request.mockResolvedValueOnce({ data: { id: 7, is_archived: true } })

      const result = await store.archiveDocument(7)

      expect(patch_request).toHaveBeenCalledWith('documents/7/archive/', {})
      expect(result.success).toBe(true)
      expect(store.documents.map((d) => d.id)).toEqual([8])
    })

    it('archiveDocument keeps the row under the mixed scope, flipping its badge', async () => {
      store.archiveScope = 'all'
      store.documents = [{ id: 7, title: 'Viejo', is_archived: false }]
      patch_request.mockResolvedValueOnce({ data: { id: 7, title: 'Viejo', is_archived: true } })

      await store.archiveDocument(7)

      expect(store.documents).toEqual([{ id: 7, title: 'Viejo', is_archived: true }])
    })

    it('unarchiveDocument reports the container chain that came back', async () => {
      store.archiveScope = 'archived'
      store.documents = [{ id: 7, title: 'Viejo' }]
      patch_request.mockResolvedValueOnce({
        data: { id: 7, is_archived: false, restored_chain: [{ id: 4, name: 'temp' }] },
      })

      const result = await store.unarchiveDocument(7)

      expect(patch_request).toHaveBeenCalledWith('documents/7/unarchive/', {})
      expect(result.restoredChain).toEqual([{ id: 4, name: 'temp' }])
      expect(store.documents).toEqual([])
    })

    it('normalizes an archive failure into a Spanish message', async () => {
      store.documents = [{ id: 7 }]
      patch_request.mockRejectedValueOnce(new Error('boom'))

      const result = await store.archiveDocument(7)

      expect(result.success).toBe(false)
      expect(result.message).toBe('No se pudo archivar el documento.')
      expect(store.documents).toHaveLength(1)
    })

    it('deleteDocument also removes the row from the search results', async () => {
      store.searchResults = [{ id: 7, title: 'Viejo' }]
      delete_request.mockResolvedValueOnce({})

      await store.deleteDocument(7)

      expect(store.searchResults).toEqual([])
    })
  })

  describe('global search', () => {
    it('ignores folder and scope so nothing stays hidden', async () => {
      store.activeFolderId = 7
      store.archiveScope = 'active'
      get_request.mockResolvedValueOnce({
        data: {
          results: [{ id: 9, is_archived: true }],
          count: 1, page: 1, page_size: 10, total_pages: 1,
        },
      })

      const result = await store.searchDocuments('mapeo')

      expect(get_request).toHaveBeenCalledWith(
        'documents/browse/?scope=all&search=mapeo&page=1&page_size=10',
        { signal: expect.any(AbortSignal) },
      )
      expect(result.success).toBe(true)
      expect(store.searchResults).toEqual([{ id: 9, is_archived: true }])
    })

    it('requests the oldest search results when selected', async () => {
      get_request.mockResolvedValueOnce({ data: { results: [] } })

      await store.searchDocuments('mapeo', { order: 'oldest' })

      expect(get_request).toHaveBeenCalledWith(
        'documents/browse/?scope=all&search=mapeo&page=1&page_size=10&order=oldest',
        { signal: expect.any(AbortSignal) },
      )
    })

    it('discards a stale search response', async () => {
      let resolveFirst
      get_request.mockReturnValueOnce(new Promise((r) => { resolveFirst = r }))
      get_request.mockResolvedValueOnce({ data: { results: [{ id: 2 }] } })

      const first = store.searchDocuments('ma')
      await store.searchDocuments('mapeo')
      resolveFirst({ data: { results: [{ id: 1 }] } })
      await first

      expect(store.searchResults).toEqual([{ id: 2 }])
    })

    it('turns the search loading flag on while searching and off when done', async () => {
      let resolve
      get_request.mockReturnValueOnce(new Promise((r) => { resolve = r }))

      const pending = store.searchDocuments('mapeo')
      expect(store.isSearchLoading).toBe(true)

      resolve({ data: { results: [] } })
      await pending

      expect(store.isSearchLoading).toBe(false)
    })

    it('a stale search response neither clears the flag nor writes results', async () => {
      let resolveFirst
      let resolveSecond
      get_request.mockReturnValueOnce(new Promise((r) => { resolveFirst = r }))
      get_request.mockReturnValueOnce(new Promise((r) => { resolveSecond = r }))

      const first = store.searchDocuments('ma')
      const second = store.searchDocuments('mapeo')
      resolveFirst({ data: { results: [{ id: 1 }] } })
      await first

      // La búsqueda vieja terminó, pero la vigente sigue en vuelo.
      expect(store.isSearchLoading).toBe(true)
      expect(store.searchResults).toEqual([])

      resolveSecond({ data: { results: [{ id: 2 }] } })
      await second

      expect(store.isSearchLoading).toBe(false)
      expect(store.searchResults).toEqual([{ id: 2 }])
    })
  })

  describe('panel counts', () => {
    it('fetches the authoritative sidebar totals', async () => {
      get_request.mockResolvedValueOnce({
        data: { documents: { active: 89, archived: 1 }, folders: { active: 25, archived: 1 } },
      })

      await store.fetchCounts()

      expect(get_request).toHaveBeenCalledWith('documents/counts/')
      expect(store.counts.documents.active).toBe(89)
      expect(store.counts.folders.archived).toBe(1)
    })

    it('merges a partial payload instead of blanking the sidebar', async () => {
      store.counts.documents.active = 89
      get_request.mockResolvedValueOnce({ data: { documents: { archived: 3 } } })

      await store.fetchCounts()

      expect(store.counts.documents.active).toBe(89)
      expect(store.counts.documents.archived).toBe(3)
    })
  })

  describe('association axes (client/project)', () => {
    it('sends client and project params when the axes are set', async () => {
      store.activeClientId = 4
      store.activeProjectId = 9
      get_request.mockResolvedValueOnce({ data: [] })
      await store.fetchDocuments()
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active&client=4&project=9')
    })

    it('sends the none sentinel for the unlinked cut', async () => {
      store.activeClientId = 'none'
      get_request.mockResolvedValueOnce({ data: [] })
      await store.fetchDocuments()
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active&client=none')
    })

    it('setFilters updates the axes and refetches with them', async () => {
      get_request.mockResolvedValueOnce({ data: [] })
      await store.setFilters({ client: 4, project: 'none' })
      expect(store.activeClientId).toBe(4)
      expect(store.activeProjectId).toBe('none')
      expect(get_request).toHaveBeenCalledWith('documents/?scope=active&client=4&project=none')
    })
  })

  describe('fetchFolderClientSuggestion', () => {
    it('asks the endpoint for the folder and returns its payload', async () => {
      get_request.mockResolvedValueOnce({
        data: { client: 3, client_display_name: 'Ana Pérez' },
      })
      const result = await store.fetchFolderClientSuggestion(12)
      expect(get_request).toHaveBeenCalledWith('documents/folder-client-suggestion/?folder=12')
      expect(result).toEqual({
        success: true,
        data: { client: 3, client_display_name: 'Ana Pérez' },
      })
    })

    it('reports failure without touching the list loading flag', async () => {
      get_request.mockRejectedValueOnce({ response: { data: { folder: 'x' } } })
      const result = await store.fetchFolderClientSuggestion(12)
      expect(result.success).toBe(false)
      expect(store.isLoading).toBe(false)
    })
  })

  describe('resolveFolderAssociation', () => {
    // La carpeta ahora DICE de quién es. Cuando lo dice, eso manda; la
    // heurística de mayoría queda como respaldo para las que todavía no lo
    // dicen (y es lo que la pasada retroactiva va apagando).
    const folderStore = { folderById: jest.fn() }

    beforeEach(() => {
      folderStore.folderById.mockReset()
      global.useDocumentFolderStore = jest.fn(() => folderStore)
    })

    it('takes the folder own client and project when it has them', async () => {
      folderStore.folderById.mockReturnValue({
        id: 3, client: 7, client_display_name: 'Kore SAS', project: 4,
      })

      const result = await store.resolveFolderAssociation(3)

      expect(result.data).toMatchObject({
        client: 7, client_display_name: 'Kore SAS', project: 4, source: 'folder',
      })
      expect(get_request).not.toHaveBeenCalled()
    })

    it('falls back to the majority suggestion when the folder says nothing', async () => {
      folderStore.folderById.mockReturnValue({ id: 3, client: null })
      get_request.mockResolvedValue({
        data: { client: 9, client_display_name: 'Ana Pérez' },
      })

      const result = await store.resolveFolderAssociation(3)

      expect(get_request).toHaveBeenCalledWith(
        'documents/folder-client-suggestion/?folder=3',
      )
      expect(result.data).toMatchObject({
        client: 9, client_display_name: 'Ana Pérez', project: null,
        source: 'suggestion',
      })
    })

    it('reports no association when neither the folder nor the majority says one', async () => {
      folderStore.folderById.mockReturnValue(null)
      get_request.mockResolvedValue({ data: { client: null } })

      const result = await store.resolveFolderAssociation(3)

      // Sigue siendo una respuesta exitosa con forma completa: "no hay dueño"
      // no es un error, y el form la lee igual que a una con cliente.
      expect(result.success).toBe(true)
      expect(result.data).toEqual({
        client: null, client_display_name: '', project: null, source: null,
      })
    })
  })
})
