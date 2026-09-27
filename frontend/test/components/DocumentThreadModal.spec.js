import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

import DocumentThreadModal from '../../components/panel/documents/DocumentThreadModal.vue';
import BaseResponsiveTabs from '../../components/base/BaseResponsiveTabs.vue';
import { useDocumentThreadStore } from '../../stores/document_threads';

const mockRequestConfirm = jest.fn();
const mockNotifySuccess = jest.fn();

jest.mock('../../composables/useConfirmModal', () => ({
  useConfirmModal: () => ({
    confirmState: { value: { open: false } },
    requestConfirm: mockRequestConfirm,
    handleConfirmed: jest.fn(),
    handleCancelled: jest.fn(),
  }),
}));

jest.mock('../../composables/usePanelNotify', () => ({
  usePanelNotify: () => ({ success: mockNotifySuccess }),
}));

const sourceDocument = {
  id: 11,
  title: 'Acta de inicio',
  issue_date: '2026-08-01',
  created_at: '2026-08-02T02:00:00Z',
  content_markdown: '# Acta',
  folder: { id: 1, name: 'Contratos' },
  client: { id: 2, name: 'Cliente Atlas' },
  project: { id: 3, name: 'Proyecto Atlas' },
};

const candidate = {
  id: 12,
  title: 'Aprobación final',
  issue_date: null,
  created_at: '2026-08-16T01:00:00Z',
  default_occurred_on: '2026-08-15',
  is_archived: false,
  available: true,
  folder: { id: 4, name: 'Entregas' },
  client: { id: 5, name: 'Cliente Boreal' },
  project: { id: 6, name: 'Proyecto Boreal' },
};

function mountModal(document = sourceDocument) {
  return mount(DocumentThreadModal, {
    props: { modelValue: true, document },
    global: {
      components: { BaseResponsiveTabs },
      stubs: {
        Teleport: true,
        Transition: false,
        NuxtLink: { template: '<a><slot /></a>' },
        BaseModal: {
          props: ['modelValue'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseAlert: { template: '<div><slot /></div>' },
        BaseBadge: { template: '<span><slot /></span>' },
        BaseCheckbox: { template: '<label><slot /></label>' },
        BaseEmptyState: { props: ['title'], template: '<div>{{ title }}</div>' },
        BasePagination: true,
        ConfirmModal: true,
        PdfPreviewPane: true,
        DocumentMarkdownBody: { props: ['markdown'], template: '<div>{{ markdown }}</div>' },
      },
    },
  });
}

function prepareStandaloneStore(store) {
  jest.spyOn(store, 'fetchThread').mockResolvedValue({ success: true, data: null });
  jest.spyOn(store, 'fetchDocumentDetail').mockResolvedValue({
    success: true,
    data: sourceDocument,
  });
  jest.spyOn(store, 'fetchCandidates').mockImplementation(async () => {
    store.candidates = [candidate];
    store.candidateCount = 1;
    return { success: true, data: [candidate] };
  });
}

describe('DocumentThreadModal', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useDocumentThreadStore();
    mockRequestConfirm.mockReset();
    mockNotifySuccess.mockReset();
  });

  it('starts a standalone thread from the source document', async () => {
    prepareStandaloneStore(store);

    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="document-thread-name"]').element.value)
      .toBe('Acta de inicio');
    expect(wrapper.get('[data-testid="thread-date-11"]').element.value)
      .toBe('2026-08-01');
    expect(wrapper.get('[data-testid="thread-member-11"]').text())
      .toContain('Contratos · Cliente Atlas · Proyecto Atlas');
  });

  it('creates a thread from a selected search result', async () => {
    prepareStandaloneStore(store);
    jest.spyOn(store, 'createThread').mockImplementation(async (payload) => {
      store.currentThread = {
        id: 90,
        title: payload.title,
        items: payload.items.map((item) => ({
          occurred_on: item.occurred_on,
          document: item.document_id === 11 ? sourceDocument : candidate,
        })),
      };
      return { success: true, data: store.currentThread };
    });
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="thread-candidate-12"]').trigger('click');
    await wrapper.get('[data-testid="document-thread-save"]').trigger('click');
    await flushPromises();

    expect(store.createThread).toHaveBeenCalledWith({
      title: 'Acta de inicio',
      items: [
        { document_id: 11, occurred_on: '2026-08-01' },
        { document_id: 12, occurred_on: '2026-08-15' },
      ],
    });
    expect(wrapper.emitted('saved')[0][0].thread.id).toBe(90);
  });

  it('opens an existing thread in chronological order', async () => {
    const existing = {
      id: 90,
      title: 'Historia de aprobación',
      items: [
        { occurred_on: '2026-08-20', document: sourceDocument },
        { occurred_on: '2026-08-05', document: candidate },
      ],
    };
    store.currentThread = existing;
    jest.spyOn(store, 'fetchThread').mockImplementation(async () => {
      store.currentThread = existing;
      return { success: true, data: existing };
    });
    jest.spyOn(store, 'fetchCandidates').mockResolvedValue({ success: true, data: [] });

    const wrapper = mountModal();
    await flushPromises();
    const timelineItems = wrapper.findAll('[data-testid^="thread-timeline-"]');

    expect(wrapper.get('[data-testid="document-thread-timeline"]').exists()).toBe(true);
    expect(timelineItems.map((item) => item.text())).toEqual([
      expect.stringContaining('Aprobación final'),
      expect.stringContaining('Acta de inicio'),
    ]);
  });

  it('asks for confirmation before saving an existing thread with one remaining document', async () => {
    const existing = {
      id: 90,
      title: 'Historia de aprobación',
      items: [
        { occurred_on: '2026-08-01', document: sourceDocument },
        { occurred_on: '2026-08-15', document: candidate },
      ],
    };
    store.currentThread = existing;
    jest.spyOn(store, 'fetchThread').mockImplementation(async () => {
      store.currentThread = existing;
      return { success: true, data: existing };
    });
    jest.spyOn(store, 'fetchCandidates').mockResolvedValue({ success: true, data: [] });
    jest.spyOn(store, 'updateThread').mockResolvedValue({
      success: true,
      data: { dissolved: true },
    });
    mockRequestConfirm.mockResolvedValue(true);

    const wrapper = mountModal();
    await flushPromises();

    const relateTab = wrapper.findAll('[role="tab"]').find(tab => tab.text().includes('Relacionar'));
    await relateTab.trigger('click');
    const candidateMember = wrapper.findAllComponents({ name: 'BaseActionButton' })
      .find(action => action.props('label') === 'Retirar Aprobación final del hilo');
    await candidateMember.getComponent({ name: 'BaseButton' }).trigger('click');
    await wrapper.get('[data-testid="document-thread-save"]').trigger('click');
    await flushPromises();

    // Falla si retirar un miembro disuelve el hilo sin consentimiento explícito.
    expect(mockRequestConfirm).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Disolver el hilo',
      confirmText: 'Disolver y guardar',
    }));
    expect(store.updateThread).toHaveBeenCalledWith(90, {
      title: 'Historia de aprobación',
      items: [{ document_id: 11, occurred_on: '2026-08-01' }],
    });
  });

  it('does not save a one-member existing thread when dissolution is cancelled', async () => {
    const existing = {
      id: 90,
      title: 'Historia de aprobación',
      items: [
        { occurred_on: '2026-08-01', document: sourceDocument },
        { occurred_on: '2026-08-15', document: candidate },
      ],
    };
    store.currentThread = existing;
    jest.spyOn(store, 'fetchThread').mockImplementation(async () => {
      store.currentThread = existing;
      return { success: true, data: existing };
    });
    jest.spyOn(store, 'fetchCandidates').mockResolvedValue({ success: true, data: [] });
    jest.spyOn(store, 'updateThread');
    mockRequestConfirm.mockResolvedValue(false);

    const wrapper = mountModal();
    await flushPromises();

    const relateTab = wrapper.findAll('[role="tab"]').find(tab => tab.text().includes('Relacionar'));
    await relateTab.trigger('click');
    const candidateMember = wrapper.findAllComponents({ name: 'BaseActionButton' })
      .find(action => action.props('label') === 'Retirar Aprobación final del hilo');
    await candidateMember.getComponent({ name: 'BaseButton' }).trigger('click');
    await wrapper.get('[data-testid="document-thread-save"]').trigger('click');
    await flushPromises();

    // Falla si cancelar la confirmación igual persiste la disolución.
    expect(mockRequestConfirm).toHaveBeenCalledTimes(1);
    expect(store.updateThread).not.toHaveBeenCalled();
  });

  it('disables candidates already linked to another thread and explains why', async () => {
    const occupiedCandidate = {
      ...candidate,
      id: 13,
      title: 'Contrato vigente',
      available: false,
      is_archived: true,
      unavailable_reason: 'Este documento ya pertenece a otro hilo.',
      thread_summary: { id: 90, title: 'Historia de aprobación', document_count: 4 },
    };
    jest.spyOn(store, 'fetchThread').mockResolvedValue({ success: true, data: null });
    jest.spyOn(store, 'fetchDocumentDetail').mockResolvedValue({
      success: true,
      data: sourceDocument,
    });
    jest.spyOn(store, 'fetchCandidates').mockImplementation(async () => {
      store.candidates = [occupiedCandidate];
      store.candidateCount = 1;
      return { success: true, data: [occupiedCandidate] };
    });

    const wrapper = mountModal();
    await flushPromises();
    const row = wrapper.get('[data-testid="thread-candidate-13"]');

    // Falla si un documento ocupado puede añadirse o pierde la explicación del bloqueo.
    expect(row.attributes('aria-disabled')).toBe('true');
    expect(row.attributes('aria-describedby')).toBe('thread-candidate-reason-13');
    const candidates = wrapper.get('[data-testid="document-thread-candidates"]');
    expect(candidates.text()).toContain('Este documento ya pertenece a otro hilo.');
    // El tamaño del hilo ocupante y el archivado se muestran sin copia nueva.
    expect(candidates.text()).toContain('Hilo · 4');
    expect(candidates.text()).toContain('Archivado');

    await row.trigger('click');

    expect(wrapper.find('[data-testid="thread-member-13"]').exists()).toBe(false);
  });

  it('explains a candidate already added to the draft', async () => {
    prepareStandaloneStore(store);
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="thread-candidate-12"]').trigger('click');
    const row = wrapper.get('[data-testid="thread-candidate-12"]');

    // Falla si un candidato ya agregado queda gris sin decir por qué.
    expect(row.attributes('aria-disabled')).toBe('true');
    expect(wrapper.get('[data-testid="document-thread-candidates"]').text())
      .toContain('Ya está en este hilo.');

    await row.trigger('click');

    expect(wrapper.findAll('[data-testid="thread-member-12"]')).toHaveLength(1);
  });

  it('shows the server conflict without closing the workspace', async () => {
    prepareStandaloneStore(store);
    jest.spyOn(store, 'createThread').mockResolvedValue({
      success: false,
      message: 'El documento ya pertenece a otro hilo.',
    });
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="thread-candidate-12"]').trigger('click');
    await wrapper.get('[data-testid="document-thread-save"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('El documento ya pertenece a otro hilo.');
    expect(wrapper.emitted('saved')).toBeFalsy();
    expect(wrapper.emitted('update:modelValue')).toBeFalsy();
  });
});
