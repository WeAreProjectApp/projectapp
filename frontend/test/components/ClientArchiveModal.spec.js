import { flushPromises, mount } from '@vue/test-utils';

import ClientArchiveModal from '../../components/clients/ClientArchiveModal.vue';

const mockStore = {
  previewClientArchive: jest.fn(),
  archiveClient: jest.fn(),
  unarchiveClient: jest.fn(),
};

jest.mock('~/stores/proposal_clients', () => ({
  useProposalClientsStore: () => mockStore,
}), { virtual: true });

// Stubs declare their emits: without them the native fallthrough fires the
// handler a second time and a single click reads as two.
const BaseModalStub = {
  props: ['modelValue'],
  emits: ['close'],
  template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
};
const BaseButtonStub = {
  props: ['loading', 'disabled'],
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
};
const BaseAlertStub = { template: '<div><slot /></div>' };
const BaseControlGateStub = {
  props: ['reasons'],
  template: '<div><slot :describedBy="null" /></div>',
};

function previewWith(overrides = {}) {
  return {
    success: true,
    data: {
      client_id: 1,
      client_name: 'Ana',
      target_state_id: 4,
      target_state_name: 'Suspendido',
      projects: [{
        project_id: 7,
        project_name: 'Portal Ana',
        current_state: 'Activo',
        impact_token: 'tok-7',
        future_incomes: [{ id: 1 }],
        future_payments: [],
        active_hostings: [],
        blockers: [],
      }],
      skipped: [],
      totals: { future_incomes: 1, future_payments: 0, active_hostings: 0 },
      ...overrides,
    },
  };
}

function mountModal(client = { id: 1, name: 'Ana', is_archived: false }) {
  return mount(ClientArchiveModal, {
    props: { open: true, client },
    global: {
      stubs: {
        BaseModal: BaseModalStub,
        BaseButton: BaseButtonStub,
        BaseAlert: BaseAlertStub,
        BaseControlGate: BaseControlGateStub,
      },
    },
  });
}

describe('ClientArchiveModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore.previewClientArchive.mockResolvedValue(previewWith());
    mockStore.archiveClient.mockResolvedValue({ success: true, data: {} });
    mockStore.unarchiveClient.mockResolvedValue({ success: true, data: {} });
  });

  it('names what the cascade will cancel before confirming', async () => {
    const wrapper = mountModal();
    await flushPromises();

    const impact = wrapper.get('[data-testid="client-archive-impact"]').text();
    // Suspending cancels future incomes and nothing brings them back, so the
    // count has to be on screen before the confirm button is usable.
    expect(impact).toContain('1 ingresos futuros se marcarán como cancelados.');
    expect(impact).toContain('Reactivar después no revierte esas cancelaciones.');
    expect(impact).toContain('Portal Ana');
  });

  it('confirms with one impact token per project', async () => {
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="client-archive-confirm"]').trigger('click');
    await flushPromises();

    expect(mockStore.archiveClient).toHaveBeenCalledWith(1, [
      { project_id: 7, impact_token: 'tok-7' },
    ]);
    expect(wrapper.emitted('changed')[0][0].archived).toBe(true);
  });

  it('says a client with no active projects costs nothing', async () => {
    mockStore.previewClientArchive.mockResolvedValue(
      previewWith({ projects: [], totals: { future_incomes: 0, future_payments: 0, active_hostings: 0 } }),
    );
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="client-archive-no-projects"]').text())
      .toContain('No tiene proyectos activos');
  });

  it('reports the projects it will not touch', async () => {
    mockStore.previewClientArchive.mockResolvedValue(previewWith({
      skipped: [{ project_id: 9, project_name: 'Viejo', reason: 'ya_no_activo', label: 'Ya está en "Completado".' }],
    }));
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="client-archive-skipped"]').text())
      .toContain('Ya está en "Completado".');
  });

  it('blocks the confirm while the preview has not arrived', async () => {
    let resolvePreview;
    mockStore.previewClientArchive.mockReturnValue(new Promise((resolve) => {
      resolvePreview = resolve;
    }));
    const wrapper = mountModal();

    expect(wrapper.get('[data-testid="client-archive-confirm"]').element.disabled)
      .toBe(true);

    resolvePreview(previewWith());
    await flushPromises();

    expect(wrapper.get('[data-testid="client-archive-confirm"]').element.disabled)
      .toBe(false);
  });

  it('does not preview when unarchiving, and warns the projects stay put', async () => {
    const wrapper = mountModal({ id: 1, name: 'Ana', is_archived: true });
    await flushPromises();

    expect(mockStore.previewClientArchive).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="client-archive-unarchive-note"]').text())
      .toContain('Sus proyectos siguen suspendidos');

    await wrapper.get('[data-testid="client-archive-confirm"]').trigger('click');
    await flushPromises();

    expect(mockStore.unarchiveClient).toHaveBeenCalledWith(1);
    expect(wrapper.emitted('changed')[0][0].archived).toBe(false);
  });

  it('re-previews after a stale confirmation instead of retrying blind', async () => {
    const wrapper = mountModal();
    await flushPromises();
    mockStore.archiveClient.mockResolvedValue({
      success: false,
      errors: { error: 'projects_changed', message: 'La lista de proyectos cambió.' },
    });

    await wrapper.get('[data-testid="client-archive-confirm"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="client-archive-error"]').text())
      .toContain('La lista de proyectos cambió.');
    // Confirming again must not reuse the tokens the backend just rejected.
    expect(mockStore.previewClientArchive).toHaveBeenCalledTimes(2);
    expect(wrapper.emitted('changed')).toBeUndefined();
  });
});
