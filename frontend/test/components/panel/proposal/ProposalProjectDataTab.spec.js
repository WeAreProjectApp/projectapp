import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

const mockGetRequest = jest.fn();
const mockCreateRequest = jest.fn();

jest.mock('~/stores/services/request_http', () => ({
  get_request: (...args) => mockGetRequest(...args),
  create_request: (...args) => mockCreateRequest(...args),
  put_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn(),
}));
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => ({ success: jest.fn(), error: jest.fn() }) }));
jest.mock('~/components/ui/ClientAutocomplete.vue', () => ({
  props: ['disabled', 'disabledReason', 'testId'],
  template: '<input :data-testid="testId" :disabled="disabled" :title="disabledReason" />',
}));

import ProposalProjectDataTab from '~/components/panel/proposal/ProposalProjectDataTab.vue';

const linkedProposal = {
  id: 117,
  status: 'accepted',
  client: { id: 61 },
  linked_project: { id: 14, name: 'Littigio' },
};

const contactForm = {
  client_id: 61,
  client_name: 'Littigio S.A.S.',
  client_email: 'contacto@littigio.co',
  client_phone: '+57 300 000 0000',
  client_company: 'Littigio',
};

function mountTab(props = {}) {
  const pinia = createPinia();
  setActivePinia(pinia);
  return mount(ProposalProjectDataTab, {
    props: { proposal: linkedProposal, form: { ...contactForm }, saving: false, ...props },
    global: {
      plugins: [pinia],
      stubs: {
        BaseInput: { props: ['modelValue', 'size', 'type'], template: '<input v-bind="$attrs" :type="type" :value="modelValue" />' },
        BaseButton: { props: ['disabled'], emits: ['click'], template: '<button role="button" v-bind="$attrs" :disabled="disabled" type="button" @click="$emit(\'click\')"><slot /></button>' },
        BaseSelect: { props: ['modelValue', 'disabled'], emits: ['update:modelValue'], template: '<select v-bind="$attrs" :disabled="disabled" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
        BaseTextarea: { props: ['modelValue', 'disabled'], emits: ['update:modelValue'], template: '<textarea v-bind="$attrs" :disabled="disabled" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
      },
    },
  });
}

function buttonByName(wrapper, name) {
  return wrapper.findAll('[role="button"]').find((button) => button.text() === name);
}

describe('ProposalProjectDataTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetRequest.mockResolvedValue({ data: { results: [] } });
    Object.defineProperty(global, 'crypto', {
      configurable: true,
      value: { randomUUID: jest.fn(() => 'reassignment-request-117') },
    });
  });

  // Falla si el selector permite cambiar el propietario de un proyecto vinculado.
  it('locks the linked project owner and requests only that client projects', async () => {
    const wrapper = mountTab();
    await flushPromises();

    expect(mockGetRequest).toHaveBeenCalledWith('projects/', { params: { client_profile_id: 61 } });
    const owner = wrapper.get('[data-testid="proposal-edit-client-autocomplete"]');
    expect(owner.element.disabled).toBe(true);
    expect(owner.attributes('title')).toBe('Cambia el propietario desde Proyectos para conservar las relaciones.');
    wrapper.unmount();
  });

  // Falla si vincular el proyecto también bloquea correcciones de contacto del cliente.
  it('keeps contact snapshots editable and emits the scoped save', async () => {
    const wrapper = mountTab();
    await flushPromises();

    expect(wrapper.get('[data-testid="edit-client-name"]').element.disabled).toBe(false);
    expect(wrapper.get('[data-testid="edit-client-email"]').element.disabled).toBe(false);
    expect(wrapper.get('[data-testid="edit-client-phone"]').element.disabled).toBe(false);
    expect(wrapper.get('[data-testid="edit-client-company"]').element.disabled).toBe(false);

    await buttonByName(wrapper, 'Guardar cliente').trigger('click');

    expect(wrapper.emitted('save-client')).toEqual([[]]);
    wrapper.unmount();
  });

  // Falla si Guardar permite editar un snapshot mientras la petición está en curso.
  it('disables the contact fieldset while saving', async () => {
    const wrapper = mountTab({ saving: true });
    await flushPromises();

    expect(wrapper.get('fieldset').element.disabled).toBe(true);
    expect(wrapper.get('[data-testid="edit-client-name"]').element.matches(':disabled')).toBe(true);
    expect(wrapper.get('[data-testid="edit-client-email"]').element.matches(':disabled')).toBe(true);
    expect(wrapper.get('[data-testid="edit-client-phone"]').element.matches(':disabled')).toBe(true);
    expect(wrapper.get('[data-testid="edit-client-company"]').element.matches(':disabled')).toBe(true);
    wrapper.unmount();
  });

  // Falla si el selector ofrece el proyecto actual, uno archivado o un proyecto de otro cliente.
  it('shows only active projects from the linked client as reassignment targets', async () => {
    mockGetRequest.mockResolvedValueOnce({ data: { results: [
      { id: 14, name: 'Littigio actual', status: 'active', client: { profile_id: 61 } },
      { id: 15, name: 'Littigio destino', status: 'active', client: { profile_id: 61 } },
      { id: 16, name: 'Littigio archivado', status: 'archived', client: { profile_id: 61 } },
      { id: 17, name: 'Otro cliente', status: 'active', client: { profile_id: 99 } },
    ] } });
    const wrapper = mountTab();
    await flushPromises();

    const options = Array.from(wrapper.get('[data-testid="proposal-reassignment-project"]').element.options);
    expect(options.map((option) => option.value)).toEqual(['', '15']);
    expect(options.map((option) => option.text)).toEqual(['Seleccionar proyecto', 'Littigio destino']);
    wrapper.unmount();
  });

  // Falla si un impacto con dependencias permite ejecutar una reasignación incompleta.
  it('shows preview blockers and prevents confirmation', async () => {
    mockGetRequest
      .mockResolvedValueOnce({ data: { results: [{ id: 15, name: 'Littigio destino', status: 'active', client: { profile_id: 61 } }] } })
      .mockResolvedValueOnce({ data: {
        source_project: { id: 14, name: 'Littigio actual' }, target_project: { id: 15, name: 'Littigio destino' },
        deliverable_ids: [71], phase_ids: [31], approval_file_ids: [], impact_hash: 'a'.repeat(64),
        blockers: [{ code: 'unowned_resources', message: 'Hay recursos sin propietario.' }],
      } });
    const wrapper = mountTab();
    await flushPromises();
    await wrapper.get('[data-testid="proposal-reassignment-project"]').setValue('15');
    await wrapper.get('[data-testid="proposal-reassignment-reason"]').setValue('Corregir proyecto creado por error');
    await wrapper.get('[data-testid="proposal-reassignment-preview"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="proposal-reassignment-impact"]').text()).toContain('Hay recursos sin propietario.');
    const confirm = wrapper.get('[data-testid="proposal-reassignment-confirm"]');
    expect(confirm.element.disabled).toBe(true);
    await confirm.trigger('click');
    expect(mockCreateRequest).toHaveBeenCalledTimes(0);
    wrapper.unmount();
  });

  // Falla si un 500 obliga a repetir la previsualización y pierde el identificador idempotente.
  it('retries a server failure with the reviewed request identifier', async () => {
    const impact = {
      source_project: { id: 14, name: 'Littigio actual' }, target_project: { id: 15, name: 'Littigio destino' },
      deliverable_ids: [71], phase_ids: [31], approval_file_ids: [208], impact_hash: 'b'.repeat(64), blockers: [],
    };
    mockGetRequest
      .mockResolvedValueOnce({ data: { results: [{ id: 15, name: 'Littigio destino', status: 'active', client: { profile_id: 61 } }] } })
      .mockResolvedValueOnce({ data: impact });
    mockCreateRequest
      .mockRejectedValueOnce({ response: { status: 500, data: { detail: 'Temporalmente no disponible' } } })
      .mockResolvedValueOnce({ data: { proposal: { id: 117, linked_project: { id: 15, name: 'Littigio destino' } } } });
    const wrapper = mountTab();
    await flushPromises();
    await wrapper.get('[data-testid="proposal-reassignment-project"]').setValue('15');
    await wrapper.get('[data-testid="proposal-reassignment-reason"]').setValue('Corregir proyecto creado por error');
    await wrapper.get('[data-testid="proposal-reassignment-preview"]').trigger('click');
    await flushPromises();

    await wrapper.get('[data-testid="proposal-reassignment-confirm"]').trigger('click');
    await flushPromises();
    expect(wrapper.get('[data-testid="proposal-reassignment-impact"]').text()).toContain('Littigio actual → Littigio destino');

    await wrapper.get('[data-testid="proposal-reassignment-confirm"]').trigger('click');
    await flushPromises();
    const payload = {
      target_project_id: 15,
      reason: 'Corregir proyecto creado por error',
      expected_impact_hash: 'b'.repeat(64),
      request_id: 'reassignment-request-117',
    };
    expect(mockCreateRequest.mock.calls).toEqual([
      ['proposals/117/project-reassignment/', payload],
      ['proposals/117/project-reassignment/', payload],
    ]);
    expect(wrapper.find('[data-testid="proposal-reassignment-impact"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
