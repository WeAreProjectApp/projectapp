/**
 * ProjectAssignUnlinkedModal: the confirmation step of the PA-51 assign flow.
 *
 * Covers the preview render (everything checked by default), unchecking a
 * row before confirming (only confirmed ids travel), the 409 contract (the
 * plan moved → reload the preview, never guess), and the empty state.
 */
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import ProjectAssignUnlinkedModal from '../../components/panel/projects/ProjectAssignUnlinkedModal.vue';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
}));

const { get_request, create_request } = require('../../stores/services/request_http');

const PREVIEW = {
  data: {
    client: { profile_id: 7, name: 'Deivis Ríos' },
    hostings: [{ id: 4, label: 'Deivis — Vastago' }],
    incomes: [
      { id: 8, label: 'Vastago - Fase 1', kind_label: 'Esperado', period_label: 'Julio 2026' },
      { id: 9, label: 'Vastago - Fase 2', kind_label: 'Esperado', period_label: 'Agosto 2026' },
    ],
    total: 3,
  },
};

const PROJECT = { id: 1, name: 'Vastago' };

function mountModal(props = {}) {
  setActivePinia(createPinia());
  return mount(ProjectAssignUnlinkedModal, {
    props: { open: false, project: PROJECT, ...props },
    global: {
      stubs: {
        BaseModal: {
          props: ['modelValue', 'size', 'titleId'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'disabled'],
          emits: ['click'],
          template:
            '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  });
}

async function openModal(wrapper) {
  await wrapper.setProps({ open: true });
  await flushPromises();
}

const checkbox = (wrapper, testid) =>
  wrapper.find(`[data-testid="${testid}"] input[type="checkbox"]`);

describe('ProjectAssignUnlinkedModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    get_request.mockResolvedValue(PREVIEW);
  });

  it('loads the preview on open with everything checked', async () => {
    const wrapper = mountModal();
    await openModal(wrapper);

    expect(get_request).toHaveBeenCalledWith('projects/1/unlinked-records/');
    expect(checkbox(wrapper, 'project-assign-unlinked-hosting-4').element.checked).toBe(true);
    expect(checkbox(wrapper, 'project-assign-unlinked-income-8').element.checked).toBe(true);
    expect(wrapper.find('[data-testid="project-assign-unlinked-confirm"]').text())
      .toContain('Asignar 3 registros');
  });

  it('sends only the ids left checked', async () => {
    create_request.mockResolvedValueOnce({
      data: { assigned_hostings: 1, assigned_incomes: 1, project: PROJECT },
    });
    const wrapper = mountModal();
    await openModal(wrapper);

    await checkbox(wrapper, 'project-assign-unlinked-income-9').setValue(false);
    await wrapper.find('[data-testid="project-assign-unlinked-confirm"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('projects/1/assign-unlinked/', {
      hosting_ids: [4],
      income_ids: [8],
      document_ids: [],
    });
    expect(wrapper.emitted('assigned')).toHaveLength(1);
  });

  it('a preview without documents renders the other sections and no documents one', async () => {
    const wrapper = mountModal();
    await openModal(wrapper);

    expect(wrapper.text()).toContain('Hostings (1)');
    expect(wrapper.text()).toContain('Ingresos (2)');
    expect(wrapper.text()).not.toContain('Documentos (');
  });

  it('a 409 reloads the preview instead of assigning blind', async () => {
    create_request.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { error: 'La lista cambió.', code: 'records_changed', changed_ids: [8] },
      },
    });
    const wrapper = mountModal();
    await openModal(wrapper);

    await wrapper.find('[data-testid="project-assign-unlinked-confirm"]').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[data-testid="project-assign-unlinked-error"]').text())
      .toContain('La lista cambió');
    expect(wrapper.emitted('assigned')).toBeUndefined();
  });

  describe('documents section (F7)', () => {
    const DOCS_PREVIEW = {
      data: {
        ...PREVIEW.data,
        documents: [
          { id: 12, label: 'Contrato Vastago', type_label: 'Documento', number: '' },
          { id: 13, label: 'CC F7', type_label: 'Cuenta de cobro', number: 'PA-DEIVISRI-001' },
        ],
        total: 5,
      },
    };

    beforeEach(() => {
      get_request.mockResolvedValue(DOCS_PREVIEW);
    });

    it('renders the documents checked by default, cuentas by their number', async () => {
      const wrapper = mountModal();
      await openModal(wrapper);

      expect(wrapper.text()).toContain('Documentos (2)');
      expect(checkbox(wrapper, 'project-assign-unlinked-document-12').element.checked).toBe(true);
      const cuentaRow = wrapper.find('[data-testid="project-assign-unlinked-document-13"]');
      expect(cuentaRow.text()).toContain('PA-DEIVISRI-001');
      expect(wrapper.find('[data-testid="project-assign-unlinked-confirm"]').text())
        .toContain('Asignar 5 registros');
    });

    it('sends only the document ids left checked', async () => {
      create_request.mockResolvedValueOnce({
        data: {
          assigned_hostings: 1,
          assigned_incomes: 2,
          assigned_documents: 1,
          project: PROJECT,
        },
      });
      const wrapper = mountModal();
      await openModal(wrapper);

      await checkbox(wrapper, 'project-assign-unlinked-document-12').setValue(false);
      await wrapper.find('[data-testid="project-assign-unlinked-confirm"]').trigger('click');
      await flushPromises();

      expect(create_request).toHaveBeenCalledWith('projects/1/assign-unlinked/', {
        hosting_ids: [4],
        income_ids: [8, 9],
        document_ids: [13],
      });
      expect(wrapper.emitted('assigned')).toHaveLength(1);
    });
  });

  it('an empty backlog says so and offers no confirm button', async () => {
    get_request.mockResolvedValue({
      data: { client: { profile_id: 7, name: 'Deivis' }, hostings: [], incomes: [], total: 0 },
    });
    const wrapper = mountModal();
    await openModal(wrapper);

    expect(wrapper.find('[data-testid="project-assign-unlinked-empty"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="project-assign-unlinked-confirm"]').exists()).toBe(false);
  });
});
