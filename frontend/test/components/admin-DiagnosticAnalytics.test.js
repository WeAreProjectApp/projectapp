jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn() }));
import { get_request } from '~/stores/services/request_http';

import { mount } from '@vue/test-utils';

global.useTooltipTexts = jest.fn(() => ({
  analytics: {
    engagementScore: 'Puntaje de engagement',
    summary: 'Resumen de visitas y actividad',
    comparison: 'Comparación con el promedio global',
    funnel: 'Embudo de secciones',
    devices: 'Dispositivos desde los que se accedió',
    sessionHistory: 'Historial de sesiones',
    sectionEngagement: 'Tiempo por sección',
    skippedSections: 'Secciones no visitadas',
  },
}));

import DiagnosticAnalytics from '../../components/WebAppDiagnostic/admin/DiagnosticAnalytics.vue';

const emptyLoader = jest.fn().mockResolvedValue({ success: false, data: null });

const richAnalytics = {
  total_views: 4,
  unique_sessions: 2,
  responded_at: null,
  first_viewed_at: '2026-04-01T10:00:00Z',
  last_viewed_at: '2026-04-10T10:00:00Z',
  time_to_first_view_hours: 1,
  time_to_response_hours: null,
  sections: [
    { section_type: 'purpose', section_title: 'Propósito', total_time_seconds: 120, avg_time_seconds: 60 },
    { section_type: 'cost', section_title: 'Costo', total_time_seconds: 40, avg_time_seconds: 20 },
  ],
  skipped_sections: [],
  funnel: [
    { section_type: 'purpose', section_title: 'Propósito', reached_count: 2, drop_off_percent: 0 },
    { section_type: 'cost', section_title: 'Costo', reached_count: 1, drop_off_percent: 50 },
  ],
  device_breakdown: { desktop: 1, mobile: 1, tablet: 0 },
  comparison: {
    avg_time_to_first_view_hours: 5,
    avg_time_to_response_hours: 24,
    avg_views: 2,
  },
  timeline: [
    { id: 1, change_type: 'sent', actor_type: 'seller', description: 'Diagnóstico enviado', created_at: '2026-04-01T09:00:00Z', field_name: null },
    { id: 2, change_type: 'viewed', actor_type: 'client', description: '', created_at: '2026-04-01T11:00:00Z', field_name: null },
  ],
  sessions: [{ id: 1, session_id: 'sess123456789abc', viewed_at: '2026-04-10T10:00:00Z', reading_time_seconds: 160, device_type: 'desktop' }],
  engagement_score: 60,
};

function withRichData(extraProps = {}, data = richAnalytics) {
  const loader = jest.fn().mockResolvedValue({ success: true, data });
  return mount(DiagnosticAnalytics, {
    props: { diagnosticId: 42, loader, diagnostic: null, ...extraProps },
    global: {
      stubs: {
        QuestionMarkCircleIcon: { template: '<span class="q-icon" />' },
        UiTooltip: { template: '<div><slot /><slot name="trigger" /></div>' },
      },
    },
  });
}

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

function mountComponent(props = {}) {
  return mount(DiagnosticAnalytics, {
    props: {
      diagnosticId: 42,
      loader: emptyLoader,
      diagnostic: null,
      ...props,
    },
    global: {
      stubs: {
        QuestionMarkCircleIcon: { template: '<span class="q-icon" />' },
        UiTooltip: { template: '<div><slot /><slot name="trigger" /></div>' },
      },
    },
  });
}

describe('DiagnosticAnalytics', () => {
  it('shows a loading skeleton on mount', () => {
    const wrapper = mountComponent();

    expect(wrapper.find('[data-testid="analytics-loading"]').exists()).toBe(true);
  });

  it('shows the error state with retry when the loader fails', async () => {
    const wrapper = mountComponent();

    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="analytics-error-state"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Reintentar');
  });

  it('shows the never-viewed empty state when the loader succeeds without data', async () => {
    const mockLoader = jest.fn().mockResolvedValue({ success: true, data: null });
    const wrapper = mountComponent({ loader: mockLoader });

    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('aún no ha sido visto');
  });

  it('calls the loader with no arguments on mount', () => {
    const mockLoader = jest.fn().mockResolvedValue({ success: false, data: null });
    mountComponent({ loader: mockLoader });

    expect(mockLoader).toHaveBeenCalledTimes(1);
  });

  it('re-fetches when diagnosticId prop changes', async () => {
    const mockLoader = jest.fn().mockResolvedValue({ success: false, data: null });
    const wrapper = mountComponent({ loader: mockLoader });

    await wrapper.setProps({ diagnosticId: 99 });

    expect(mockLoader).toHaveBeenCalledTimes(2);
  });
});

// ── Rich analytics data ────────────────────────────────────────────────────

describe('DiagnosticAnalytics with data', () => {
  it('renders section titles from sections array after data loads', async () => {
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('Propósito');
  });

  it('renders total reading time as sum of section times', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // totalReadingTime = 120 + 40 = 160s → formatTime(160) = '2m 40s'
    expect(wrapper.text()).toContain('2m 40s');
  });

  it('renders section read-through percentage', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // sectionCoverage = round(2 / (2+0) * 100) = 100%
    expect(wrapper.text()).toContain('100%');
  });

  it('renders funnel drop-off summary', async () => {
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('Funnel de navegación');
    expect(wrapper.text()).toContain('-50% de abandono');
  });

  it('renders timeline event actor labels', async () => {
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('Ventas');
    expect(wrapper.text()).toContain('Cliente');
  });

  it('renders comparison metrics from comparison data', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // time_to_first_view_hours=1, avg=5 → 1 < 5 → emoji 🔥 for faster
    expect(wrapper.text()).toContain('🔥');
  });

  it('renders the sent timeline event label', async () => {
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('Enviado');
  });

  it('renders device breakdown data', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // device_breakdown: desktop=1, mobile=1
    expect(wrapper.text()).toContain('Desktop');
  });
});

// ── suggestions computed ───────────────────────────────────────────────────

describe('DiagnosticAnalytics suggestions', () => {
  it('shows 💰 suggestion when cost section was skipped', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [],
      skipped_sections: [{ section_type: 'cost', section_title: 'Costo' }],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Costo y formas de pago');
  });

  it('shows 🔥 suggestion when total_views >= 3 and not responded', async () => {
    const wrapper = withRichData({}, { ...richAnalytics, total_views: 4, responded_at: null });
    await flushPromises();

    expect(wrapper.text()).toContain('4 veces');
  });

  it('shows 🔄 suggestion for rejected diagnostics', async () => {
    const loader = jest.fn().mockResolvedValue({ success: true, data: richAnalytics });
    const wrapper = mount(DiagnosticAnalytics, {
      props: { diagnosticId: 42, loader, diagnostic: { status: 'rejected' } },
      global: { stubs: { QuestionMarkCircleIcon: { template: '<span />' }, UiTooltip: { template: '<div><slot /><slot name="trigger" /></div>' } } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('rechazado');
  });
});

// ── sectionInsights ────────────────────────────────────────────────────────

describe('DiagnosticAnalytics sectionInsights', () => {
  it('shows purpose insight when purpose section has >= 10s', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [{ section_type: 'purpose', section_title: 'Propósito', total_time_seconds: 30, avg_time_seconds: 15 }],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Entiende la severidad');
  });

  it('shows cost insight for high cost section engagement', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [{ section_type: 'cost', section_title: 'Costo', total_time_seconds: 20, avg_time_seconds: 10 }],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Interés en el costo');
  });
});

// ── formatTime branches ────────────────────────────────────────────────────

describe('DiagnosticAnalytics formatTime', () => {
  it('shows < 1s for zero-second sections', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [{ section_type: 'purpose', section_title: 'Test', total_time_seconds: 0, avg_time_seconds: 0 }],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('< 1s');
  });

  it('shows seconds for sections under 60s', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [{ section_type: 'purpose', section_title: 'Test', total_time_seconds: 45, avg_time_seconds: 45 }],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('45s');
  });
});

// ── heatEmoji and sortedSections ──────────────────────────────────────────

describe('DiagnosticAnalytics heat sections', () => {
  it('shows 🔴 emoji for the most-visited section', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [
        { section_type: 'purpose', section_title: 'A', total_time_seconds: 200, avg_time_seconds: 100 },
        { section_type: 'cost', section_title: 'B', total_time_seconds: 30, avg_time_seconds: 15 },
      ],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('🔴');
  });
});

// ── downloadCSV ───────────────────────────────────────────────────────────

describe('DiagnosticAnalytics downloadCSV', () => {
  it('downloads the diagnostic analytics CSV without opening a window', async () => {
    const blob = new Blob(['date,views\n2026-09-29,2'], { type: 'text/csv' });
    get_request.mockResolvedValue({ data: blob, headers: { 'content-type': 'text/csv' } });
    URL.createObjectURL = jest.fn().mockReturnValue('blob:csv');
    URL.revokeObjectURL = jest.fn();
    const saved = [];
    const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { saved.push(this.download); });
    const wrapper = withRichData();
    await flushPromises();

    await wrapper.findAll('button').find((btn) => btn.text().includes('CSV')).trigger('click');

    await flushPromises();
    expect(saved).toEqual(['diagnostics-analytics.csv']);
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    click.mockRestore();
  });
});

// ── refresh exposed method ────────────────────────────────────────────────

describe('DiagnosticAnalytics refresh', () => {
  it('re-fetches analytics when refresh is called', async () => {
    const loader = jest.fn().mockResolvedValue({ success: true, data: richAnalytics });
    const wrapper = mount(DiagnosticAnalytics, {
      props: { diagnosticId: 42, loader, diagnostic: null },
      global: { stubs: { QuestionMarkCircleIcon: { template: '<span />' }, UiTooltip: { template: '<div><slot /><slot name="trigger" /></div>' } } },
    });
    await flushPromises();

    await wrapper.vm.refresh();
    await flushPromises();

    expect(loader).toHaveBeenCalledTimes(2);
  });
});
