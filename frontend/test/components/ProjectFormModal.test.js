/**
 * ProjectFormModal: the module's create/edit form.
 *
 * Covers the PA-38 minimum (name + client validate on submit), the client
 * immutability on edit (the payload must not carry client_profile_id), the
 * non-blocking duplicate warning, and the orphans-panel seed that leaves
 * only the name to type.
 */
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import ProjectFormModal from '../../components/panel/projects/ProjectFormModal.vue';
import { get_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: {
    modelValue: { type: Number, default: null },
    initialLabel: { type: String, default: '' },
    testId: { type: String, default: '' },
    allowCreate: { type: Boolean, default: false },
    error: { type: Boolean, default: false },
    errorDescribedBy: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'select', 'create-new'],
  template: '<div data-testid="client-autocomplete-stub" />',
};

const CLIENT = { id: 7, name: 'Deivis Ríos', company: 'Vástago', email: 'deivis@example.com' };

const RECORD = {
  id: 3,
  name: 'Vástago',
  description: 'App de gestión',
  status: 'suspended',
  status_label: 'Suspendido',
  current_state: {
    id: 12,
    name: 'Suspendido',
    system_key: 'suspended',
    operational_effect: 'suspended',
  },
  client: { profile_id: 7, name: 'Deivis Ríos', company: 'Vástago' },
};

function mountModal(props = {}, attachToBody = false) {
  setActivePinia(createPinia());
  return mount(ProjectFormModal, {
    props: { open: true, saving: false, ...props },
    attachTo: attachToBody ? document.body : undefined,
    global: {
      plugins: [createPinia()],
      stubs: {
        ClientAutocomplete: ClientAutocompleteStub,
        ClientFormFields: true,
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'required', 'error'],
          template: `
            <div>
              <label v-if="label">{{ label }}<span v-if="required">*</span></label>
              <slot :invalid="Boolean(error)" :error-id="error ? 'field-error' : undefined" />
              <p v-if="error" role="alert">{{ error }}</p>
              <p v-else-if="hint">{{ hint }}</p>
            </div>
          `,
        },
        BaseFormRow: { template: '<div><slot /></div>' },
        BaseModalActions: { template: '<div data-testid="base-modal-actions"><slot /></div>' },
        BaseInput: {
          props: ['modelValue', 'type', 'placeholder', 'error'],
          emits: ['update:modelValue'],
          template:
            '<input :type="type || \'text\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'rows'],
          emits: ['update:modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSelect: {
          props: ['modelValue', 'options'],
          emits: ['update:modelValue'],
          template: `
            <select :value="modelValue">
              <option v-for="option in options" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          `,
        },
        BaseToggle: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: `
            <button
              type="button"
              :aria-pressed="String(modelValue)"
              @click="$emit('update:modelValue', !modelValue)"
            >Alternar</button>
          `,
        },
        BaseButton: {
          props: ['variant', 'size', 'disabled', 'type'],
          // `emits` declared so the parent's @click doesn't ALSO fall through
          // as a native listener (it would double-fire every handler).
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  });
}

describe('ProjectFormModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    get_request.mockImplementation((url) => Promise.resolve({
      data: url.startsWith('project-states/')
        ? [{
          id: 10,
          name: 'En desarrollo',
          system_key: 'development',
          operational_effect: 'development',
          is_active: true,
          merged_into: null,
          group: 4,
        }]
        : [{ id: 4, name: 'Ciclo del proyecto', selection_mode: 'exclusive' }],
    }));
  });

  it('places validation beside each missing required field after submit', async () => {
    const wrapper = mountModal();
    await flushPromises();

    const submit = () => wrapper.find('[data-testid="project-form-submit"]');
    expect(submit().attributes('disabled')).toBeUndefined();

    await wrapper.find('form').trigger('submit');

    expect(wrapper.findAll('[role="alert"]').map((alert) => alert.text())).toEqual([
      'Escribe el nombre del proyecto.',
      'Elige o crea un cliente.',
    ]);
    expect(wrapper.emitted('submit')).toBeUndefined();

    await wrapper.find('[data-testid="project-form-name"]').setValue('Kore');
    expect(wrapper.text()).not.toContain('Escribe el nombre del proyecto.');

    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('select', CLIENT);
    await flushPromises();
    expect(wrapper.text()).not.toContain('Elige o crea un cliente.');

    await wrapper.find('form').trigger('submit');
    const payload = wrapper.emitted('submit')[0][0];
    expect(payload).toEqual({
      name: 'Kore',
      client_profile_id: 7,
      description: '',
      state_id: 10,
    });
  });

  it('submits the preselected client from the footer save action', async () => {
    // Falla si mover Guardar fuera del form deja de disparar el submit nativo.
    const wrapper = mountModal({ seedClient: CLIENT }, true);
    await flushPromises();

    await wrapper.get('[data-testid="project-form-name"]').setValue('Portal de aliados');

    const submit = wrapper.get('[data-testid="project-form-submit"]');
    submit.element.click();
    await flushPromises();

    expect(wrapper.emitted('submit')[0][0]).toEqual({
      name: 'Portal de aliados',
      client_profile_id: 7,
      description: '',
      state_id: 10,
    });
    wrapper.unmount();
  });

  it('renders En desarrollo as the initial state selection', async () => {
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="project-form-status"]').element.value).toBe('10');
  });

  it('omits the redundant default-state help', async () => {
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="project-form-status"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Si no eliges un estado');
    expect(wrapper.text()).not.toContain('(opcional)');
  });

  it('exposes inline client creation from the selector', async () => {
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.findComponent(ClientAutocompleteStub).props('allowCreate')).toBe(true);
  });

  it('hydrates the edit form from the project record', async () => {
    const wrapper = mountModal({ record: RECORD });
    await flushPromises();

    // Falla si abrir una edición deja valores del formulario anterior.
    expect(wrapper.find('[data-testid="project-form-name"]').element.value).toBe('Vástago');
    expect(wrapper.find('[data-testid="project-form-client-readonly"]').text())
      .toContain('Deivis Ríos');
    expect(wrapper.findComponent(ClientAutocompleteStub).exists()).toBe(false);
  });

  it('omits the client from an edit payload', async () => {
    const wrapper = mountModal({ record: RECORD });
    await flushPromises();

    // Falla si una actualización vuelve a enviar un cliente que el backend rechaza.
    await wrapper.find('[data-testid="project-form-name"]').setValue('Vástago App');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload).toEqual({
      name: 'Vástago App',
      description: 'App de gestión',
    });
    expect(payload).not.toHaveProperty('client_profile_id');
  });

  it('omits the obsolete document-manager control', async () => {
    const wrapper = mountModal({ record: RECORD });
    await flushPromises();

    // Falla si el formulario vuelve a ofrecer una regla de inclusión ya eliminada.
    expect(wrapper.get('[data-testid="project-form-name"]').element.value).toBe('Vástago');
    expect(wrapper.find('[data-testid="project-form-document-manager"]').exists()).toBe(false);
  });

  it('warns about a same-name project for the same client without blocking', async () => {
    const wrapper = mountModal({
      existingProjects: [
        { id: 9, name: 'Vástago', client: { profile_id: 7 } },
      ],
    });
    await flushPromises();

    await wrapper.find('[data-testid="project-form-name"]').setValue('vastago');
    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('select', CLIENT);
    await flushPromises();

    expect(wrapper.find('[data-testid="project-form-duplicate-warning"]').exists()).toBe(true);
    expect(
      wrapper.find('[data-testid="project-form-submit"]').attributes('disabled'),
    ).toBeUndefined();
  });

  it('stays silent when the same name belongs to another client', async () => {
    const wrapper = mountModal({
      existingProjects: [
        { id: 9, name: 'Vástago', client: { profile_id: 99 } },
      ],
    });
    await flushPromises();

    await wrapper.find('[data-testid="project-form-name"]').setValue('Vástago');
    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('select', CLIENT);
    await flushPromises();

    expect(wrapper.find('[data-testid="project-form-duplicate-warning"]').exists()).toBe(false);
  });

  it('a seeded client leaves only the name to type', async () => {
    const wrapper = mountModal({
      seedClient: { id: 7, name: 'Deivis Ríos' },
    });
    await flushPromises();

    await wrapper.find('[data-testid="project-form-name"]').setValue('Vástago');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.client_profile_id).toBe(7);
    expect(payload.name).toBe('Vástago');
  });

  it('emits the guided client-change request from an edit', async () => {
    const wrapper = mountModal({ record: RECORD });
    await flushPromises();

    // Falla si el acceso guiado deja de comunicar la intención a la página.
    await wrapper
      .find('[data-testid="project-form-change-client"]')
      .trigger('click');

    expect(wrapper.emitted('change-client')).toEqual([[]]);
  });

  it('omits the guided client-change entry from a new project', async () => {
    const wrapper = mountModal();
    await flushPromises();

    // Falla si un proyecto nuevo recibe una acción reservada para cambios con impacto.
    expect(wrapper.get('[data-testid="project-form-name"]').element.value).toBe('');
    expect(wrapper.find('[data-testid="project-form-change-client"]').exists()).toBe(false);
  });
});
