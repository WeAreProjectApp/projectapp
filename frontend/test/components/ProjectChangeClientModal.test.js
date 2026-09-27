/**
 * ProjectChangeClientModal: the guided cascade for changing a project's
 * owner.
 *
 * Pins the agreed rules: the mode is chosen EVERY time (confirm stays
 * disabled until move/detach is picked — no preselection), the preview's
 * blocked and issued buckets are named before anything runs, the apply
 * payload carries the staleness ids the preview returned, and a 409
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
    hostings_move: [{ id: 4, label: 'Pepito — vastago.com' }],
    incomes_move: [
      { id: 8, label: 'Fase 1', kind_label: 'Esperado', period_label: 'Julio 2026' },
    ],
    incomes_blocked: [
      {
        id: 9, label: 'Con cuenta', kind_label: 'Esperado',
        period_label: 'Agosto 2026', reason: 'Tiene una cuenta de cobro activa.',
      },
    ],
    clientless: [],
    draft_accounts: [],
    issued_accounts: [{ id: 31, title: 'CC', public_number: 'PA-KO-001', status_label: 'Issued' }],
    communication_threads_detaching: [
      { id: 44, title: 'Aprobación del alcance' },
    ],
    other_documents_count: 0,
    hosting_ids: [4],
    income_ids: [8, 9],
    communication_thread_ids: [44],
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

  it('loads the preview when the destination is picked and names every bucket', async () => {
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

  it('keeps the confirm disabled until a mode is explicitly chosen', async () => {
    const wrapper = mountModal();

    await openAndPickClient(wrapper);
    expect(confirmButton(wrapper).attributes('disabled')).toBe('');

    await pickMode(wrapper, 'Mover al nuevo cliente');

    expect(confirmButton(wrapper).attributes('disabled')).toBeUndefined();
  });

  it('applies with the mode and the staleness ids the preview returned', async () => {
    create_request.mockResolvedValue({
      data: {
        project: { id: 1 },
        moved: { hostings: 1, incomes: 1, draft_accounts: 0 },
        detached: { hostings: 0, incomes: 1, draft_accounts: 0 },
        detached_communications: 1,
        skipped: { issued_accounts: 1, clientless: 0, other_documents: 0 },
      },
    });
    // changeClient refetches the projects listing after applying.
    get_request.mockImplementation((url) => (
      url.startsWith('projects/?')
        ? Promise.resolve({ data: { results: [], meta: {} } })
        : Promise.resolve(PREVIEW)
    ));
    const wrapper = mountModal();

    await openAndPickClient(wrapper);
    await pickMode(wrapper, 'Mover al nuevo cliente');
    await confirmButton(wrapper).trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('projects/1/change-client/', {
      client_profile_id: 9,
      mode: 'move',
      hosting_ids: [4],
      income_ids: [8, 9],
      communication_thread_ids: [44],
    });
    expect(wrapper.emitted('changed')).toHaveLength(1);
  });

  it('a 409 reloads the preview and drops the chosen mode', async () => {
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
