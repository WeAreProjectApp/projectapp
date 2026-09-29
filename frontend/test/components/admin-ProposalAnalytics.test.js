jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn() }));
import { get_request } from '~/stores/services/request_http';

import { mount } from '@vue/test-utils';

global.useProposalStore = jest.fn(() => ({
  fetchProposalAnalytics: jest.fn().mockResolvedValue({ success: false, data: null }),
}));

global.useTooltipTexts = jest.fn(() => ({
  analytics: {
    engagementScore: 'Puntaje de engagement',
    summary: 'Resumen de visitas y actividad',
  },
}));

import ProposalAnalytics from '../../components/BusinessProposal/admin/ProposalAnalytics.vue';

const richAnalytics = {
  total_views: 5,
  unique_sessions: 3,
  responded_at: null,
  first_viewed_at: '2026-04-01T10:00:00Z',
  last_viewed_at: '2026-04-10T10:00:00Z',
  time_to_first_view_hours: 2,
  time_to_response_hours: null,
  sections: [
    { section_type: 'intro', section_title: 'Introducción', total_time_seconds: 120, avg_time_seconds: 65 },
    { section_type: 'investment', section_title: 'Inversión', total_time_seconds: 60, avg_time_seconds: 25 },
  ],
  skipped_sections: [],
  funnel: [
    { section_type: 'intro', section_title: 'Intro', reached_count: 3, drop_off_percent: 0 },
    { section_type: 'technical_document_public', section_title: 'Técnico público', reached_count: 2, drop_off_percent: 33 },
  ],
  device_breakdown: { desktop: 2, mobile: 1, tablet: 0 },
  by_view_mode: { technical: { sessions: 2, total_time_seconds: 180 } },
  technical_engagement: { total_time_seconds: 50 },
  comparison: {
    avg_time_to_first_view_hours: 5,
    avg_time_to_response_hours: 48,
    avg_views: 3,
  },
  timeline: [
    { id: 1, change_type: 'sent', actor_type: 'seller', description: 'Propuesta enviada', created_at: '2026-04-01T09:00:00Z', field_name: null },
    { id: 2, change_type: 'viewed', actor_type: 'client', description: '', created_at: '2026-04-01T11:00:00Z', field_name: null },
  ],
  sessions: [{ id: 1, session_id: 'abc123def456xyz', viewed_at: '2026-04-10T10:00:00Z', reading_time_seconds: 180, device_type: 'desktop' }],
  engagement_score: 75,
  calc_events: [],
};

function withRichData(extraProps = {}, data = richAnalytics) {
  global.useProposalStore = jest.fn(() => ({
    fetchProposalAnalytics: jest.fn().mockResolvedValue({ success: true, data }),
  }));
  return mount(ProposalAnalytics, {
    props: { proposalId: 42, proposal: null, ...extraProps },
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

function mountProposalAnalytics(props = {}) {
  return mount(ProposalAnalytics, {
    props: {
      proposalId: 42,
      proposal: null,
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

describe('ProposalAnalytics', () => {
  it('shows loading state on mount', () => {
    const wrapper = mountProposalAnalytics();

    // loading is true before the async fetch resolves
    expect(wrapper.text()).toContain('Cargando analytics');
  });

  it('renders the component wrapper', () => {
    const wrapper = mountProposalAnalytics();

    expect(wrapper.find('div').exists()).toBe(true);
  });

  it('shows no-data state after fetch returns no data', async () => {
    const wrapper = mountProposalAnalytics();

    // Wait for onMounted async fetch to complete
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('No hay datos de analytics');
  });

  it('passes proposalId to the analytics fetch on mount', async () => {
    const mockFetch = jest.fn().mockResolvedValue({ success: false, data: null });
    global.useProposalStore = jest.fn(() => ({ fetchProposalAnalytics: mockFetch }));

    mountProposalAnalytics({ proposalId: 99 });

    expect(mockFetch).toHaveBeenCalledWith(99);
  });
});

// ── Rich analytics data ────────────────────────────────────────────────────

describe('ProposalAnalytics with data', () => {
  beforeEach(() => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({ success: true, data: richAnalytics }),
    }));
  });

  it('renders section titles from sections array after data loads', async () => {
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('Introducción');
  });

  it('renders the total reading time from section times', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // totalReadingTime = 120 + 60 = 180s → formatTime(180) = '3m'
    expect(wrapper.text()).toContain('3m');
  });

  it('renders section read-through percentage', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // sectionCoverage = round(2 / (2+0) * 100) = 100%
    expect(wrapper.text()).toContain('100%');
  });

  it('renders funnel exec detail sections in the funnel tab', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // funnel has one exec_detail section: 'Intro'
    expect(wrapper.text()).toContain('Intro');
  });

  it('renders timeline events with actor labels', async () => {
    const wrapper = withRichData();
    await flushPromises();

    // timeline has actor_type: 'seller' → 'Ventas'
    expect(wrapper.text()).toContain('Ventas');
  });

  it('renders timeline events with actor_type client → Cliente', async () => {
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('Cliente');
  });

  it('renders comparison faster-than-average emoji (🔥) for ttfv below avg', async () => {
    // time_to_first_view_hours=2, avg=5 → 2 < 5 → '🔥'
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('🔥');
  });

  it('renders the sent timeline event label', async () => {
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('Enviada');
  });

  it('renders the durable first-view notification failure', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      first_view_notification: {
        status: 'failed',
        attempts: 4,
        sent_at: null,
        last_error: 'SMTP unavailable',
        can_retry: true,
      },
    });
    await flushPromises();

    expect(wrapper.get('[data-testid="first-view-notification-status"]').text())
      .toContain('Falló');
    expect(wrapper.text()).toContain('SMTP unavailable');
  });

  it('retries a failed first-view notification from the panel', async () => {
    const retry = jest.fn().mockResolvedValue({
      success: true,
      data: {
        status: 'pending', attempts: 0, last_error: '', can_retry: false,
      },
    });
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: {
          ...richAnalytics,
          first_view_notification: {
            status: 'failed', attempts: 4, last_error: 'SMTP unavailable', can_retry: true,
          },
        },
      }),
      retryFirstViewNotification: retry,
    }));
    const wrapper = mountProposalAnalytics();
    await flushPromises();

    await wrapper.get('[data-testid="retry-first-view-notification"]').trigger('click');
    await flushPromises();

    expect(retry).toHaveBeenCalledWith(42);
    expect(wrapper.get('[data-testid="first-view-notification-status"]').text())
      .toContain('Pendiente');
  });
});

// ── suggestions computed ───────────────────────────────────────────────────

describe('ProposalAnalytics suggestions', () => {
  it('shows the 🔧 suggestion when technical engagement >= 40s', async () => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: { ...richAnalytics, technical_engagement: { total_time_seconds: 45 } },
      }),
    }));
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('🔧');
  });

  it('shows 💰 suggestion when investment section was skipped', async () => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: {
          ...richAnalytics,
          sections: [],
          skipped_sections: [{ section_type: 'investment', section_title: 'Inversión' }],
        },
      }),
    }));
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('💰');
  });

  it('shows 🔥 suggestion when total_views >= 3 and not responded', async () => {
    const wrapper = withRichData({}, { ...richAnalytics, total_views: 4, responded_at: null });
    await flushPromises();

    expect(wrapper.text()).toContain('4 veces');
  });

  it('shows 🔄 suggestion for rejected proposals', async () => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: { ...richAnalytics },
      }),
    }));
    const wrapper = mount(ProposalAnalytics, {
      props: { proposalId: 42, proposal: { status: 'rejected' } },
      global: { stubs: { QuestionMarkCircleIcon: { template: '<span />' }, UiTooltip: { template: '<div><slot /><slot name="trigger" /></div>' } } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('🔄');
  });
});

// ── formatTime function ────────────────────────────────────────────────────

describe('ProposalAnalytics formatTime', () => {
  it('shows < 1s for zero seconds', async () => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: {
          ...richAnalytics,
          sections: [{ section_type: 'intro', section_title: 'Test', total_time_seconds: 0, avg_time_seconds: 0 }],
        },
      }),
    }));
    const wrapper = withRichData();
    await flushPromises();

    expect(wrapper.text()).toContain('< 1s');
  });

  it('shows seconds for values under 60', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [{ section_type: 'intro', section_title: 'Test', total_time_seconds: 30, avg_time_seconds: 30 }],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('30s');
  });
});

// ── downloadCSV ───────────────────────────────────────────────────────────

describe('ProposalAnalytics downloadCSV', () => {
  it('downloads the proposal analytics CSV without opening a window', async () => {
    const blob = new Blob(['date,views\n2026-09-29,2'], { type: 'text/csv' });
    get_request.mockResolvedValue({ data: blob, headers: { 'content-type': 'text/csv' } });
    URL.createObjectURL = jest.fn().mockReturnValue('blob:csv');
    URL.revokeObjectURL = jest.fn();
    const saved = [];
    const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { saved.push(this.download); });
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({ success: true, data: richAnalytics }),
    }));
    const wrapper = withRichData();
    await flushPromises();

    await wrapper.findAll('button').find((btn) => btn.text().includes('CSV')).trigger('click');

    await flushPromises();
    expect(saved).toEqual(['proposals-analytics.csv']);
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    click.mockRestore();
  });
});

// ── sectionAnalyticsTypeLabel ──────────────────────────────────────────────

describe('ProposalAnalytics sectionAnalyticsTypeLabel', () => {
  it('renders det. técnico (vista pública) label for technical_document_public sections', async () => {
    const wrapper = withRichData({}, {
      ...richAnalytics,
      sections: [{ section_type: 'technical_document_public', section_title: 'Técnico', total_time_seconds: 90, avg_time_seconds: 45 }],
    });
    await flushPromises();

    expect(wrapper.text()).toContain('det. técnico');
  });
});

// ── heatEmoji and sortedSections ──────────────────────────────────────────

describe('ProposalAnalytics heat and sorted sections', () => {
  it('renders heat emoji for sections sorted by time descending', async () => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: {
          ...richAnalytics,
          sections: [
            { section_type: 'intro', section_title: 'Primera', total_time_seconds: 200, avg_time_seconds: 100 },
            { section_type: 'investment', section_title: 'Segunda', total_time_seconds: 50, avg_time_seconds: 25 },
          ],
        },
      }),
    }));
    const wrapper = withRichData();
    await flushPromises();

    // heatEmoji for idx=0, total=2 → ratio=0 → <= 0.15 → '🔴'
    expect(wrapper.text()).toContain('🔴');
  });
});

// ── hasDeviceData and lastVisitedAt ───────────────────────────────────────

describe('ProposalAnalytics device data', () => {
  it('renders device breakdown when device data is available', async () => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: { ...richAnalytics, device_breakdown: { desktop: 3, mobile: 2, tablet: 1 } },
      }),
    }));
    const wrapper = withRichData();
    await flushPromises();

    // The numbers should appear in the device section
    expect(wrapper.text()).toContain('3');
  });
});

// ── formatTimelineDescription ──────────────────────────────────────────────

function withTimeline(events, extraData = {}) {
  global.useProposalStore = jest.fn(() => ({
    fetchProposalAnalytics: jest.fn().mockResolvedValue({
      success: true,
      data: { ...richAnalytics, timeline: events, ...extraData },
    }),
  }));
  return mount(ProposalAnalytics, {
    props: { proposalId: 42, proposal: null },
    global: {
      stubs: {
        QuestionMarkCircleIcon: { template: '<span />' },
        UiTooltip: { template: '<div><slot /><slot name="trigger" /></div>' },
      },
    },
  });
}

describe('ProposalAnalytics formatTimelineDescription', () => {
  it('calc_confirmed renders Confirmó with module count', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'calc_confirmed',
      description: JSON.stringify({ selected: [1, 2], total: 5000, elapsed_seconds: 65 }),
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('Confirmó');
  });

  it('calc_abandoned renders Abandonó calculadora', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'calc_abandoned',
      description: JSON.stringify({ selected: [1], deselected: [2], total: null, elapsed_seconds: 0 }),
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('Abandonó calculadora');
  });

  it('updated with field_name title renders old and new values', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'updated',
      field_name: 'title',
      old_value: 'Viejo nombre',
      new_value: 'Nuevo nombre',
      actor_type: 'seller',
      description: '',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('Viejo nombre');
    expect(wrapper.text()).toContain('Nuevo nombre');
  });

  it('status_change renders Estado with old and new values', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'status_change',
      old_value: 'draft',
      new_value: 'sent',
      actor_type: 'seller',
      description: '',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('draft');
    expect(wrapper.text()).toContain('sent');
  });

  it('commented with prefix renders the bolded comment body', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'commented',
      description: 'Client left a comment: Great proposal!',
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('Great proposal!');
  });

  it('negotiating with Comment key renders the bolded reason', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'negotiating',
      description: 'Quiere negociar Comment: necesita descuento',
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('necesita descuento');
  });

  it('rejected with Reason key renders the bolded rejection reason', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'rejected',
      description: 'No aceptó Reason: presupuesto insuficiente',
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('presupuesto insuficiente');
  });

  it('cond_accepted with Conditional acceptance prefix renders condition', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'cond_accepted',
      description: 'Conditional acceptance: pago en dos cuotas',
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('pago en dos cuotas');
  });

  it('accepted with Condition key renders the bolded condition', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'accepted',
      description: 'Aceptó propuesta Condition: con garantía de 30 días',
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('con garantía de 30 días');
  });

  it('sent with " to email" renders the bolded recipient email', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'sent',
      description: 'Propuesta enviada to cliente@empresa.com.',
      actor_type: 'seller',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('cliente@empresa.com');
  });

  it('resent type with " to email" renders the bolded recipient email', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'resent',
      description: 'Propuesta reenviada to reenvio@empresa.com.',
      actor_type: 'seller',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('reenvio@empresa.com');
  });

  it('req_clicked renders bolded group title from JSON description', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'req_clicked',
      description: JSON.stringify({ group_title: 'Landing Page' }),
      actor_type: 'client',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('Landing Page');
  });

  it('created event with quoted title passes through escapeHtml', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'created',
      description: 'Propuesta "Acme Corp" creada',
      actor_type: 'seller',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('Acme Corp');
  });

  it('unknown change_type falls through to escapeHtml and renders description', async () => {
    const wrapper = withTimeline([{
      id: 1,
      change_type: 'unknown_type',
      description: 'Actividad desconocida',
      actor_type: 'seller',
      created_at: '2026-01-01T10:00:00Z',
    }]);
    await flushPromises();
    expect(wrapper.text()).toContain('Actividad desconocida');
  });
});

// ── share links and skipped sections ──────────────────────────────────────

describe('ProposalAnalytics share links and skipped sections', () => {
  it('renders share links table when share_links has entries', async () => {
    const wrapper = withTimeline([], {
      share_links: [
        { uuid: 'link-1', shared_by_name: 'Carlos', recipient_name: 'Ana', view_count: 2, first_viewed_at: null },
      ],
    });
    await flushPromises();
    expect(wrapper.text()).toContain('Tracking de propuestas compartidas');
    expect(wrapper.text()).toContain('Carlos');
  });

  it('renders skipped sections count when skipped_sections is non-empty', async () => {
    const wrapper = withTimeline([], {
      skipped_sections: [
        { section_type: 'context_diagnostic', section_title: 'Contexto' },
      ],
    });
    await flushPromises();
    expect(wrapper.text()).toContain('Contexto');
  });
});

// ── sectionInsights ────────────────────────────────────────────────────────

describe('ProposalAnalytics sectionInsights', () => {
  it('renders sectionInsights for top sections with known type and sufficient time', async () => {
    const wrapper = withTimeline([], {
      sections: [
        { section_type: 'investment', section_title: 'Inversión', total_time_seconds: 120, avg_time_seconds: 60 },
      ],
      skipped_sections: [],
    });
    await flushPromises();
    expect(wrapper.text()).toContain('Señal de interés en precio');
  });
});

// ── lastVisitedAt fallback ─────────────────────────────────────────────────

describe('ProposalAnalytics lastVisitedAt', () => {
  it('falls back to first session viewed_at when last_viewed_at is null', async () => {
    global.useProposalStore = jest.fn(() => ({
      fetchProposalAnalytics: jest.fn().mockResolvedValue({
        success: true,
        data: {
          ...richAnalytics,
          last_viewed_at: null,
          sessions: [{ id: 1, viewed_at: '2026-03-01T14:00:00Z', reading_time_seconds: 60, device_type: 'mobile', session_id: 'sess1' }],
        },
      }),
    }));
    const wrapper = mount(ProposalAnalytics, {
      props: { proposalId: 42, proposal: null },
      global: {
        stubs: {
          QuestionMarkCircleIcon: { template: '<span />' },
          UiTooltip: { template: '<div><slot /><slot name="trigger" /></div>' },
        },
      },
    });
    await flushPromises();
    expect(wrapper.text()).toContain('Dom, 1 mar 2026');
  });
});
