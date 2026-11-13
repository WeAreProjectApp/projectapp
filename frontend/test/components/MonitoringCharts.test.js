import { flushPromises, mount } from '@vue/test-utils'
import MonitoringCharts from '../../components/monitoring/MonitoringCharts.vue'

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }))
jest.mock('../../composables/useChartTheme', () => ({
  useChartTheme: () => {
    const { ref } = require('vue')
    return { palette: ref({ measures: ['#1D4ED8', '#059669', '#B91C1C'] }), baseOptions: ref({ chart: {}, tooltip: {} }) }
  },
}))

const { get_request } = require('../../stores/services/request_http')

global.useI18n = () => ({ t: key => key, locale: { value: 'es-CO' } })

const LazyApexChartStub = { props: ['options', 'series', 'type', 'height'], template: '<div data-testid="monitoring-apex-chart" />' }
const BaseButtonStub = { template: '<button role="button" type="button"><slot /></button>' }

const measuredSeries = {
  last_observed_at: '2026-11-12T14:00:00Z',
  points: [
    { timestamp: '2026-11-12T13:00:00Z', count: 1, average: { ram_used_bytes: 1073741824, ram_total_bytes: 2147483648, disk_used_bytes: 2147483648, disk_total_bytes: 4294967296, cpu_percent: 42, load_1m: 1.5, cpu_count: 4 }, max: { ram_used_bytes: 1610612736, disk_used_bytes: 3221225472, cpu_percent: 67, load_1m: 2 } },
    { timestamp: '2026-11-12T14:00:00Z', count: 0, average: {}, max: {} },
  ],
}

function mountCharts() {
  return mount(MonitoringCharts, {
    props: { serverId: 'server-5' },
    global: { stubs: { ClientOnly: { template: '<div><slot /></div>' }, LazyApexChart: LazyApexChartStub, MonitoringSelect: true, BaseButton: BaseButtonStub } },
  })
}

function chartById(wrapper, id) {
  return wrapper.findAllComponents(LazyApexChartStub).find(chart => chart.props('options').chart.id === id)
}

describe('MonitoringCharts', () => {
  beforeEach(() => jest.clearAllMocks())

  it('passes measured RAM values and a missing sample gap to the chart', async () => {
    // Falla si una muestra ausente se convierte en cero y oculta el hueco real de telemetría.
    get_request.mockResolvedValue({ data: measuredSeries })
    const wrapper = mountCharts()
    await flushPromises()

    expect(chartById(wrapper, 'monitor-ram-server-5').props('series')).toEqual([
      { name: 'monitoring.averageMeasured', data: [['2026-11-12T13:00:00Z', 1], ['2026-11-12T14:00:00Z', null]] },
      { name: 'monitoring.maximumMeasured', data: [['2026-11-12T13:00:00Z', 1.5], ['2026-11-12T14:00:00Z', null]] },
      { name: 'monitoring.totalCapacity', data: [['2026-11-12T13:00:00Z', 2], ['2026-11-12T14:00:00Z', null]] },
    ])
  })

  it('shows the no-history message when the series has no measured samples', async () => {
    // Falla si una respuesta sin muestras muestra gráficas que parecen datos reales.
    get_request.mockResolvedValue({ data: { last_observed_at: null, points: [{ timestamp: '2026-11-12T14:00:00Z', count: 0, average: {}, max: {} }] } })
    const wrapper = mountCharts()
    await flushPromises()

    expect(wrapper.text()).toContain('monitoring.noHistory')
  })

  it('retries a failed series request and renders the recovered measurement', async () => {
    // Falla si una falla transitoria deja las tendencias sin una acción de recuperación.
    get_request.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ data: measuredSeries })
    const wrapper = mountCharts()
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('monitoring.loadmonitoring.refresh')
    await wrapper.findAll('[role="button"]').find(button => button.text() === 'monitoring.refresh').trigger('click')
    await flushPromises()

    expect(get_request.mock.calls).toEqual([
      ['monitoring/servers/server-5/series/', { params: { period: '24h' } }],
      ['monitoring/servers/server-5/series/', { params: { period: '24h' } }],
    ])
    expect(chartById(wrapper, 'monitor-ram-server-5').props('series')[0].data[0]).toEqual(['2026-11-12T13:00:00Z', 1])
  })
})
