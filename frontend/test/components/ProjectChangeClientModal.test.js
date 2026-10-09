/**
 * ProjectChangeClientModal: the guided cascade for changing a project's
 * owner.
 *
 * Pins the agreed rules: the mode is chosen EVERY time (confirm stays
 * disabled until move/detach is picked — no preselection), the preview's
 * blocked and issued buckets are named before anything runs, client-history
 * blockers prevent applying, the payload carries the impact hash plus the
 * staleness ids the preview returned, and a 409
 * reloads the preview and drops the chosen mode instead of guessing.
 */
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import ProjectChangeClientModal from '../../components/panel/projects/ProjectChangeClientModal.vue';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
}));

const { get_request, create_request } = require('../../stores/services/request_http');

const PROJECT = { id: 1, name: 'Vastago' };

const PREVIEW = {
  data: {
    project: { id: 1, name: 'Vastago' },
    current_client: { profile_id: 7, name: 'Pepito' },
    new_client: { profile_id: 9, name: 'Juanito' },
    can_apply: true,
    blockers: [],
    impact_hash: 'a'.repeat(64),
    hostings_move: [],
    incomes_move: [
      { id: 8, label: 'Fase 1', kind_label: 'Esperado', period_label: 'Julio 2026' },
    ],
    incomes_blocked: [],
    clientless: [],
    draft_accounts: [],
    issued_accounts: [],
    communication_threads_detaching: [
      { id: 44, title: 'Aprobación del alcance' },
    ],
    other_documents_count: 0,
    hosting_ids: [],
    income_ids: [8],
    communication_thread_ids: [44],
    totals: {
      move: 1, blocked: 0, clientless: 0, drafts: 0, issued: 0, communications: 1,
    },
  },
};

const BLOCKED_PREVIEW = {
  data: {
    ...PREVIEW.data,
    can_apply: false,
    blockers: [
      {
        code: 'client_change_financial_history',
        message: 'El proyecto tiene cuentas o hosting con historia financiera; no puede trasladarse a otro cliente.',
        resource_type: 'hosting_record',
        resource_id: 4,
        resolution: 'create_new_project',
      },
      {
        code: 'issue_client_transfer_history',
        message: 'El proyecto conserva bugs o solicitudes del cliente actual. Cambiar de cliente expondría esa historia.',
        resource_type: 'bug_report',
        resource_id: 15,
        resolution: 'create_new_project',
      },
    ],
    impact_hash: 'b'.repeat(64),
    hostings_move: [{ id: 4, label: 'Pepito — vastago.com' }],
    incomes_blocked: [
      {
        id: 9, label: 'Con cuenta', kind_label: 'Esperado',
        period_label: 'Agosto 2026', reason: 'Tiene una cuenta de cobro activa.',
      },
    ],
    issued_accounts: [{ id: 31, title: 'CC', public_number: 'PA-KO-001', status_label: 'Issued' }],
    hosting_ids: [4],
    income_ids: [8, 9],
    totals: {
      move: 2, blocked: 1, clientless: 0, drafts: 0, issued: 1, communications: 1,
    },
  },
};

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: ['modelValue', 'testId', 'placeholder', 'showLinkedHint'],
  emits: ['update:modelValue', 'select'],
  template: '<div data-testid="client-autocomplete-stub" />',
};

function mountModal(props = {}) {
  setActivePinia(createPinia());
  return mount(ProjectChangeClientModal, {
    props: { open: false, project: PROJECT, ...props },
    global: {
      stubs: {
        ClientAutocomplete: ClientAutocompleteStub,
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

async function openAndPickClient(wrapper) {
  await wrapper.setProps({ open: true });
  await flushPromises();
  const picker = wrapper.findComponent(ClientAutocompleteStub);
  await picker.vm.$emit('update:modelValue', 9);
  await picker.vm.$emit('select', { id: 9, name: 'Juanito' });
  await flushPromises();
}

const confirmButton = (wrapper) =>
  wrapper.find('[data-testid="project-change-client-confirm"]');

async function pickMode(wrapper, label) {
  await wrapper
    .find('[data-testid="project-change-client-mode"]')
    .findAll('button')
    .find((button) => button.text() === label)
    .trigger('click');
  await flushPromises();
}

describe('ProjectChangeClientModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    get_request.mockResolvedValue(PREVIEW);
  });

  it('loads the labelled impact for the selected destination', async () => {
    get_request.mockResolvedValue(BLOCKED_PREVIEW);
    const wrapper = mountModal();

    await openAndPickClient(wrapper);

    expect(get_request).toHaveBeenCalledWith(
      'projects/1/change-client/preview/?client_profile_id=9',
    );
    const text = wrapper.find('[data-testid="project-change-client-preview"]').text();
    expect(text).toContain('vastago.com');
    expect(wrapper.find('[data-testid="project-change-client-blocked"]').text())
      .toContain('conservan su cliente');
    expect(wrapper.find('[data-testid="project-change-client-issued"]').text())
      .toContain('no se reasignan');
    expect(wrapper.find('[data-testid="project-change-client-communications"]').text())
      .toContain('conservan su cliente original');
  });

  it('prevents applying a preview blocked by client history', async () => {
    get_request.mockResolvedValue(BLOCKED_PREVIEW);
    const wrapper = mountModal();

    await openAndPickClient(wrapper);

    const alert = wrapper.get('[data-testid="project-change-client-blockers"]');
    expect(alert.get('h4').text()).toBe('No se puede cambiar el cliente de este proyecto');
    expect(alert.findAll('li').map((item) => item.text()))
      .toEqual(BLOCKED_PREVIEW.data.blockers.map((blocker) => blocker.message));
    expect(wrapper.get('[data-testid="project-change-client-resolution"]').text())
      .toBe('La historia financiera o de entregas queda con el cliente actual. Crea un proyecto nuevo para el cliente destino.');
    expect(wrapper.find('[data-testid="project-change-client-mode"]').exists()).toBe(false);
    expect(confirmButton(wrapper).attributes('disabled')).toBe('');

    await confirmButton(wrapper).trigger('click');
    await flushPromises();

    expect(create_request).not.toHaveBeenCalled();
    expect(wrapper.emitted('changed')).toBeUndefined();
  });

  it.each([
    ['the current preview', PREVIEW, { expected_impact_hash: PREVIEW.data.impact_hash }],
    ['a preview without a hash', { data: { ...PREVIEW.data, impact_hash: undefined } }, {}],
  ])('confirms the selected cascade using %s', async (_label, preview, impactPayload) => {
    create_request.mockResolvedValue({
      data: {
        project: { id: 1 },
        moved: { hostings: 0, incomes: 1, draft_accounts: 0 },
        detached: { hostings: 0, incomes: 0, draft_accounts: 0 },
        detached_communications: 1,
        skipped: { issued_accounts: 0, clientless: 0, other_documents: 0 },
      },
    });
    // changeClient refetches the projects listing after applying.
    get_request.mockImplementation((url) => (
      url.startsWith('projects/?')
        ? Promise.resolve({ data: { results: [], meta: {} } })
        : Promise.resolve(preview)
    ));
    const wrapper = mountModal();

    await openAndPickClient(wrapper);
    expect(confirmButton(wrapper).attributes('disabled')).toBe('');
    await pickMode(wrapper, 'Mover al nuevo cliente');
    expect(confirmButton(wrapper).attributes('disabled')).toBeUndefined();
    await confirmButton(wrapper).trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('projects/1/change-client/', {
      client_profile_id: 9,
      mode: 'move',
      hosting_ids: [],
      income_ids: [8],
      communication_thread_ids: [44],
      ...impactPayload,
    });
    expect(wrapper.emitted('changed')).toHaveLength(1);
  });

  it('requires a fresh mode choice after a stale impact conflict', async () => {
    create_request.mockRejectedValue({
      response: {
        status: 409,
        data: {
          error: '1 registro se vinculó al proyecto después de la vista previa.',
          code: 'records_changed',
          changed_ids: [12],
        },
      },
    });
    const wrapper = mountModal();

    await openAndPickClient(wrapper);
    await pickMode(wrapper, 'Desvincular del proyecto');
    await confirmButton(wrapper).trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="project-change-client-error"]').text())
      .toContain('cambiaron mientras confirmabas');
    // Two preview loads: the pick and the reload after the conflict.
    expect(get_request).toHaveBeenCalledTimes(2);
    expect(confirmButton(wrapper).attributes('disabled')).toBe('');
    expect(wrapper.emitted('changed')).toBeUndefined();
  });
});
