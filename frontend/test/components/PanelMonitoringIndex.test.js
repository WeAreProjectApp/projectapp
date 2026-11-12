const { customRef, reactive, ref, nextTick } = require('vue')

const routerReplace = jest.fn()
let routeQuery = {}
let i18nLocale = ref('es-CO')
const originalGlobals = {
  definePageMeta: global.definePageMeta,
  useI18n: global.useI18n,
  useRoute: global.useRoute,
  useRouter: global.useRouter,
}
const mockStore = reactive({
  resources: [],
  sources: [],
  records: [],
  count: 0,
  pageSize: 25,
  detail: null,
  loading: false,
  saving: false,
  error: '',
  requestId: 0,
  snapshot: '',
  revision: '',
  capturedAt: '',
  summary: null,
  attention: [],
  snapshotSources: null,
  currentPage: 1,
  expired: false,
  list: jest.fn(),
  catalog: jest.fn(),
  close: jest.fn(),
  open: jest.fn(),
  note: jest.fn(),
  transition: jest.fn(),
})

global.definePageMeta = jest.fn()
global.useI18n = () => ({ t: key => key, locale: i18nLocale })
global.useRoute = () => ({ query: routeQuery })
global.useRouter = () => ({ replace: routerReplace })

jest.mock('../../stores/monitoring', () => ({
  useMonitoringStore: () => mockStore,
}))
jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }))

const { mount, flushPromises } = require('@vue/test-utils')
const { get_request } = require('../../stores/services/request_http')
const PanelMonitoringIndex = require('../../pages/panel/monitoring/index.vue').default

const MonitoringSelectStub = {
  props: ['modelValue', 'options', 'testId'],
  emits: ['update:modelValue'],
  template: `<div>
    <select :data-testid="testId" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option value=""></option><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
    <output :data-testid="\`${testId}-options\`">{{ options.map(option => \`${option.value}:${option.label}\`).join("|") }}</output>
  </div>`,
}

const BaseButtonStub = {
  emits: ['click'],
  template: '<button role="button" type="button" @click="$emit(\'click\', $event)"><slot /></button>',
}

function defaultStubs() {
  return {
    BaseButton: BaseButtonStub,
    BaseFormField: { template: '<div><slot /></div>' },
    BaseInput: { props: ['id', 'modelValue'], emits: ['update:modelValue'], template: '<input :data-testid="id" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
    BaseModal: { template: '<div><slot /></div>' },
    BaseModalActions: { template: '<div><slot /></div>' },
    MonitoringSelect: MonitoringSelectStub,
    BaseTextarea: { template: '<textarea />' },
  }
}

function mountPage() {
  return mount(PanelMonitoringIndex, { global: { stubs: defaultStubs() } })
}

function resource(id, name, kind) {
  return { id, name, kind }
}

function source(id, resourceId, resourceName, name, lastSeenAt = '2026-09-24T10:00:00Z') {
  return {
    id,
    resource: resourceId,
    resource_name: resourceName,
    name,
    health: 'current',
    last_seen_at: lastSeenAt,
    last_error: '',
  }
}

function buttonWithLabel(wrapper, label) {
  return wrapper.findAll('[role="button"]').find(button => button.text() === label)
}

describe('panel/monitoring index page', () => {
  let wrapper

  beforeEach(() => {
    routeQuery = {}
    i18nLocale = ref('es-CO')
    routerReplace.mockReset().mockResolvedValue(undefined)
    mockStore.resources = []
    mockStore.sources = []
    mockStore.records = []
    mockStore.count = 0
    mockStore.pageSize = 25
    mockStore.detail = null
    mockStore.loading = false
    mockStore.saving = false
    mockStore.error = ''
    mockStore.requestId = 0
    mockStore.currentPage = 1
    mockStore.snapshot = ''
    mockStore.revision = ''
    mockStore.capturedAt = ''
    mockStore.summary = null
    mockStore.attention = []
    mockStore.snapshotSources = null
    mockStore.expired = false
    mockStore.list.mockReset().mockResolvedValue(true)
    mockStore.catalog.mockReset().mockResolvedValue(undefined)
    mockStore.close.mockReset()
    mockStore.open.mockReset().mockResolvedValue(undefined)
    mockStore.note.mockReset().mockResolvedValue(undefined)
    mockStore.transition.mockReset().mockResolvedValue(undefined)
    get_request.mockReset()
    jest.useFakeTimers()
  })

  afterEach(() => {
    wrapper?.unmount()
    jest.useRealTimers()
  })

  afterAll(() => {
    Object.entries(originalGlobals).forEach(([key, value]) => {
      if (value === undefined) delete global[key]
      else global[key] = value
    })
  })

  it('keeps the project source when a query resource id has the other primitive type', async () => {
    // Falla si el filtro de recurso deja de comparar sus ids como texto o si el tab acepta una fuente de otro tipo.
    routeQuery = { resource: '1' }
    mockStore.resources = [
      resource(1, 'Proyecto Uno', 'project'),
      resource(1, 'Servidor duplicado', 'server'),
      resource('1', 'Servidor Uno', 'server'),
    ]
    mockStore.sources = [
      source(11, 1, 'Proyecto Uno', 'Inspector'),
      source(12, '1', 'Servidor Uno', 'Healthcheck'),
      source(13, 99, 'Huérfano', 'Archivo'),
    ]
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.get('[data-testid="monitor-resource-options"]').text()).toBe(':monitoring.any|1:Proyecto Uno')
    expect(wrapper.get('[data-testid="monitor-source-options"]').text()).toBe(':monitoring.any|11:Proyecto Uno · Inspector')
  })

  it('updates project options after a catalog resource changes kind', async () => {
    // Falla si el índice de recursos queda en caché después de que el catálogo cambia de tipo.
    mockStore.resources = [
      resource(1, 'Proyecto Uno', 'project'),
      resource(2, 'Servidor Uno', 'server'),
    ]
    mockStore.sources = [
      source(11, 1, 'Proyecto Uno', 'Inspector'),
      source(12, 2, 'Servidor Uno', 'Healthcheck'),
    ]
    wrapper = mountPage()
    await flushPromises()
    mockStore.resources[0].kind = 'server'
    await nextTick()

    expect(wrapper.get('[data-testid="monitor-resource-options"]').text()).toBe(':monitoring.any')
    expect(wrapper.get('[data-testid="monitor-source-options"]').text()).toBe(':monitoring.any')
  })

  it('lists project, server, and orphan sources in reports', async () => {
    // Falla si Reports conserva la partición del tab Project y oculta fuentes que deben revisarse juntas.
    mockStore.resources = [
      resource(1, 'Proyecto Uno', 'project'),
      resource(2, 'Servidor Uno', 'server'),
    ]
    mockStore.sources = [
      source(11, 1, 'Proyecto Uno', 'Inspector'),
      source(12, 2, 'Servidor Uno', 'Healthcheck'),
      source(13, 99, 'Huérfano', 'Archivo'),
    ]
    wrapper = mountPage()
    await flushPromises()
    await buttonWithLabel(wrapper, 'monitoring.reports').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="monitor-resource-options"]').text()).toBe(':monitoring.any|1:Proyecto Uno · monitoring.projectLabel|2:Servidor Uno · monitoring.serverLabel')
    expect(wrapper.get('[data-testid="monitor-source-options"]').text()).toBe(':monitoring.any|11:Proyecto Uno · Inspector|12:Servidor Uno · Healthcheck|13:Huérfano · Archivo')
  })

  it('does not reread resource ids when sources grow from one to ten thousand', async () => {
    // Falla si filtrar fuentes vuelve a recorrer ids de recursos para cada una de las diez mil entradas.
    const idReads = jest.fn()
    mockStore.resources = Array.from({ length: 50 }, (_, index) => {
      const item = { name: `Recurso ${index + 1}`, kind: 'project' }
      Object.defineProperty(item, 'id', {
        enumerable: true,
        get: () => {
          idReads()
          return index + 1
        },
      })
      return item
    })
    mockStore.sources = [source(51, 1, 'Recurso 1', 'Inspector')]
    wrapper = mountPage()
    await flushPromises()
    expect(wrapper.get('[data-testid="monitor-source-options"]').text()).toBe(':monitoring.any|51:Recurso 1 · Inspector')
    const baselineReads = idReads.mock.calls.length
    expect(baselineReads).toBeLessThanOrEqual(100)
    mockStore.sources = [
      source(51, 1, 'Recurso 1', 'Inspector'),
      ...Array.from({ length: 9999 }, (_, index) => source(index + 52, -1, 'Fuera del catálogo', `Archivo ${index + 1}`, null)),
    ]
    await nextTick()

    expect(wrapper.get('[data-testid="monitor-source-options"]').text()).toBe(':monitoring.any|51:Recurso 1 · Inspector')
    expect(idReads).toHaveBeenCalledTimes(baselineReads)
  })

  it('renders the missing-date sentinel for a source without a last-seen value', async () => {
    // Falla si una fuente sin fecha deja de mostrar el centinela que evita presentar una fecha falsa al operador.
    mockStore.resources = [resource(1, 'Proyecto Uno', 'project')]
    mockStore.sources = [source(11, 1, 'Proyecto Uno', 'Sin fecha', null)]
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.get('[data-testid="monitoring-page"]').text()).toContain('Proyecto Uno · Sin fechamonitoring.current · —')
  })

  it('reformats source dates after a locale change without rereading locale for every source', async () => {
    // Falla si el formatter se crea por cada fila o si queda desconectado del locale reactivo anterior.
    let currentLocale = 'es-CO'
    let triggerLocale
    let localeReads = 0
    i18nLocale = customRef((track, trigger) => {
      triggerLocale = trigger
      return {
        get() {
          track()
          localeReads += 1
          return currentLocale
        },
        set(value) {
          currentLocale = value
          trigger()
        },
      }
    })
    mockStore.resources = [resource(1, 'Proyecto Uno', 'project')]
    mockStore.sources = [source(11, 1, 'Proyecto Uno', 'Inspector')]
    wrapper = mountPage()
    await flushPromises()

    const spanishDate = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date('2026-09-24T10:00:00Z'))
    expect(wrapper.get('[data-testid="monitoring-page"]').text()).toContain(`Proyecto Uno · Inspectormonitoring.current · ${spanishDate}`)
    expect(localeReads).toBe(1)
    mockStore.sources = Array.from({ length: 50 }, (_, index) => source(index + 11, 1, 'Proyecto Uno', `Inspector ${index + 1}`))
    await nextTick()
    expect(localeReads).toBe(1)
    currentLocale = 'en-US'
    triggerLocale()
    await nextTick()

    const englishDate = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date('2026-09-24T10:00:00Z'))
    expect(localeReads).toBe(2)
    expect(wrapper.get('[data-testid="monitoring-page"]').text()).toContain(`Proyecto Uno · Inspector 1monitoring.current · ${englishDate}`)
  })

  it('waits 300 ms before applying a text search as a new first-page snapshot', async () => {
    // Falla si cada letra dispara una consulta o si la búsqueda conserva una página e instantánea anteriores.
    wrapper = mountPage()
    await flushPromises()
    mockStore.list.mockClear()

    await wrapper.get('[data-testid="monitor-search"]').setValue('disco lleno')
    jest.advanceTimersByTime(299)
    await flushPromises()
    expect(mockStore.list).toHaveBeenCalledTimes(0)

    jest.advanceTimersByTime(1)
    await flushPromises()
    expect(mockStore.list).toHaveBeenCalledWith({ kind: 'project', page: 1, search: 'disco lleno', snapshot: 'new' }, false)
  })

  it('applies a selected project immediately from the monitoring dropdown', async () => {
    // Falla si el dropdown nuevo deja la selección local sin recargar el conjunto filtrado.
    mockStore.resources = [resource(1, 'Proyecto Uno', 'project')]
    wrapper = mountPage()
    await flushPromises()
    mockStore.list.mockClear()

    await wrapper.get('[data-testid="monitor-resource"]').setValue('1')
    jest.advanceTimersByTime(0)
    await flushPromises()

    expect(mockStore.list).toHaveBeenCalledWith({ kind: 'project', page: 1, resource: '1', snapshot: 'new' }, false)
  })

  it('shows an invalid-date alert without listing records', async () => {
    // Falla si un intervalo invertido se envía al servidor y presenta resultados engañosos.
    wrapper = mountPage()
    await flushPromises()
    mockStore.list.mockClear()

    await wrapper.get('[data-testid="monitor-since"]').setValue('2026-11-12')
    await wrapper.get('[data-testid="monitor-until"]').setValue('2026-11-01')
    jest.runOnlyPendingTimers()
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('monitoring.invalidDates')
    expect(mockStore.list).toHaveBeenCalledTimes(0)
  })

  it('clears active filters and returns the listing to its first page', async () => {
    // Falla si Limpiar filtros conserva una búsqueda, una fecha o la página anterior.
    routeQuery = { page: '7', resource: '1', search: 'disco', since: '2026-11-01', until: '2026-11-10' }
    mockStore.resources = [resource(1, 'Proyecto Uno', 'project')]
    wrapper = mountPage()
    await flushPromises()
    mockStore.list.mockClear()

    await buttonWithLabel(wrapper, 'monitoring.clearFilters').trigger('click')
    jest.advanceTimersByTime(0)
    await flushPromises()

    expect(mockStore.list).toHaveBeenCalledWith({ kind: 'project', page: 1, snapshot: 'new' }, false)
  })

  it('drills into critical active cases from the severity indicator', async () => {
    // Falla si el indicador crítico sólo parece interactivo y no limita el listado a alertas activas críticas.
    mockStore.summary = { total: 10, active: { critical: 7, warning: 2, info: 1 }, followup: 4 }
    wrapper = mountPage()
    await flushPromises()
    mockStore.list.mockClear()

    await wrapper.get('[data-testid="monitoring-summary"]').findAll('button').find(button => button.text() === 'monitoring.activeSeverity7').trigger('click')
    jest.advanceTimersByTime(0)
    await flushPromises()

    expect(mockStore.list).toHaveBeenCalledWith({ kind: 'project', page: 1, condition: 'active', severity: 'critical', snapshot: 'new' }, false)
  })

  it('drills into pending follow-ups from the summary indicator', async () => {
    // Falla si el indicador de seguimiento no muestra sólo los casos que todavía requieren gestión humana.
    mockStore.summary = { total: 10, active: { critical: 7, warning: 2, info: 1 }, followup: 4 }
    wrapper = mountPage()
    await flushPromises()
    mockStore.list.mockClear()

    await wrapper.get('[data-testid="monitoring-summary"]').findAll('button').find(button => button.text() === 'monitoring.followupTotal4').trigger('click')
    jest.advanceTimersByTime(0)
    await flushPromises()

    expect(mockStore.list).toHaveBeenCalledWith({ kind: 'project', page: 1, followup: 'true', snapshot: 'new' }, false)
  })

  it('announces a newer revision before refreshing the filtered first page', async () => {
    // Falla si el sondeo de 60 segundos reemplaza eventos que el operador todavía está revisando, o si Actualizar pierde los filtros.
    routeQuery = { resource: '1', search: 'disco', page: '3' }
    mockStore.resources = [resource(1, 'Proyecto Uno', 'project')]
    mockStore.revision = 'snapshot-a'
    get_request
      .mockResolvedValueOnce({ data: { hosts: [], revision: 'snapshot-a' } })
      .mockResolvedValueOnce({ data: { hosts: [], revision: 'snapshot-b' } })
      .mockResolvedValue({ data: { hosts: [], revision: 'snapshot-b' } })
    wrapper = mountPage()
    await flushPromises()
    mockStore.list.mockClear()

    jest.advanceTimersByTime(60000)
    await flushPromises()

    expect(mockStore.list).toHaveBeenCalledTimes(0)
    expect(wrapper.get('[role="status"]').text()).toBe('monitoring.newDatamonitoring.refresh')

    await wrapper.get('[role="status"]').get('[role="button"]').trigger('click')
    await flushPromises()

    expect(mockStore.list).toHaveBeenCalledWith({ kind: 'project', page: 1, resource: '1', search: 'disco', snapshot: 'new' }, false)
  })

  it('uses snapshot sources instead of the global catalog for source indicators', async () => {
    // Falla si una página conserva fuentes de otro corte y muestra un contador de cobertura distinto al de sus eventos.
    mockStore.summary = { total: 1, active: { critical: 0, warning: 0, info: 0 }, followup: 0 }
    mockStore.sources = [source(11, 1, 'Proyecto de catálogo', 'Inspector')]
    mockStore.snapshotSources = [{ ...source(22, 2, 'Proyecto del corte', 'Sonda'), health: 'no_data' }]
    wrapper = mountPage()
    await flushPromises()

    expect(buttonWithLabel(wrapper, 'monitoring.sourcesWithoutData1').text()).toBe('monitoring.sourcesWithoutData1')
  })
})
