import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ProjectStateTransitionModal from '../../components/panel/projects/ProjectStateTransitionModal.vue';
import { useProjectStateStore } from '../../stores/project_states';
import { create_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
}));

const PROJECT = {
  id: 9,
  name: 'Kore',
  status_label: 'Activo',
  current_state: {
    id: 2,
    name: 'Activo',
    operational_effect: 'operating',
    description: 'Está entregado y operando.',
    operational_effect_help: 'Mantiene habilitados los cobros y los avisos.',
  },
};

const STATES = [
  {
    id: 2,
    name: 'Activo',
    color: 'emerald',
    operational_effect: 'operating',
    description: 'Está entregado y operando.',
    operational_effect_help: 'Mantiene habilitados los cobros y los avisos.',
    is_active: true,
    merged_into: null,
  },
  {
    id: 3,
    name: 'En evolución',
    color: 'blue',
    operational_effect: 'operating',
    description: 'Está en producción mientras se desarrolla una ampliación.',
    operational_effect_help: 'Mantiene habilitados los cobros y los avisos.',
    is_active: true,
    merged_into: null,
  },
  {
    id: 4,
    name: 'Suspendido',
    color: 'orange',
    operational_effect: 'suspended',
    description: 'El servicio puede reactivarse.',
    operational_effect_help: 'Detiene nuevos cobros y avisos.',
    is_active: true,
    merged_into: null,
  },
  {
    id: 6,
    name: 'Dado de baja',
    color: 'gray',
    operational_effect: 'decommissioned',
    description: 'Terminó de forma definitiva.',
    operational_effect_help: 'Cancela el servicio y los cobros futuros.',
    is_active: true,
    merged_into: null,
  },
];

function mountModal() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useProjectStateStore();
  store.states = STATES;
  const wrapper = mount(ProjectStateTransitionModal, {
    props: { open: false, project: PROJECT },
    global: {
      plugins: [pinia],
      stubs: {
        BaseModal: {
          props: ['modelValue'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseAlert: {
          props: ['variant'],
          template: '<div :role="variant === \'danger\' ? \'alert\' : undefined"><slot /></div>',
        },
        BaseBadge: { template: '<span><slot /></span>' },
        BaseFormField: {
          props: ['label', 'hint', 'required', 'error'],
          template: `
            <div>
              <label v-if="label">{{ label }}<span v-if="required">*</span></label>
              <slot :invalid="Boolean(error)" :error-id="error ? 'field-error' : undefined" />
              <p v-if="error" id="field-error" role="alert">{{ error }}</p>
              <p v-else-if="hint">{{ hint }}</p>
            </div>
          `,
        },
        BaseModalActions: {
          template: '<div data-testid="base-modal-actions"><slot /></div>',
        },
        BaseToggle: {
          props: ['modelValue', 'size'],
          emits: ['update:modelValue'],
          template: '<input type="checkbox" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'error'],
          emits: ['update:modelValue'],
          template: '<textarea :value="modelValue" :aria-invalid="error || undefined" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseButton: {
          props: ['disabled'],
          emits: ['click'],
          template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  });
  return { wrapper, store };
}

describe('ProjectStateTransitionModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('places a missing state message beside the selector after impact review', async () => {
    const { wrapper } = mountModal();
    await wrapper.setProps({ open: true });

    const target = wrapper.get('[data-testid="project-state-target"]');
    expect(target.attributes('aria-invalid')).toBeUndefined();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);

    await wrapper.get('[data-testid="project-state-preview"]').trigger('click');

    expect(create_request).not.toHaveBeenCalled();
    expect(target.attributes('aria-invalid')).toBe('true');
    expect(target.attributes('aria-describedby')).toBe('field-error');
    expect(wrapper.get('[role="alert"]').text())
      .toBe('Elige el nuevo estado del proyecto.');
    expect(wrapper.get('[data-testid="base-modal-actions"]')
      .find('[role="alert"]').exists()).toBe(false);

    await target.setValue('4');

    expect(target.attributes('aria-invalid')).toBeUndefined();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it('previews suspension consequences before confirmation', async () => {
    const impact = {
      target_effect: 'suspended',
      impact_token: 'a'.repeat(64),
      effective_at: '2026-08-26T10:00:00+00:00',
      pending_incomes: [],
      future_incomes: [],
      future_payments: [],
      active_hostings: [],
      blockers: [],
    };
    create_request.mockResolvedValueOnce({ data: impact });
    const { wrapper } = mountModal();
    await wrapper.setProps({ open: true });
    await wrapper.get('[data-testid="project-state-target"]').setValue('4');

    await wrapper.get('[data-testid="project-state-preview"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith(
      'projects/9/state-transitions/preview/',
      { state_id: 4 },
    );
    expect(wrapper.get('[data-testid="project-state-impact"]').text())
      .toContain('La deuda ya causada se conserva');
  });

  it('explains the evolving state before impact review', async () => {
    const { wrapper } = mountModal();
    await wrapper.setProps({ open: true });

    await wrapper.get('[data-testid="project-state-target"]').setValue('3');

    expect(wrapper.get('[data-testid="project-state-selected-help"]').text())
      .toContain('Está en producción mientras se desarrolla una ampliación.');
    expect(wrapper.get('[data-testid="project-transition-state-help"]')
      .attributes('aria-label')).toBe('Ayuda sobre el estado En evolución');
  });

  it('requires a debt decision before decommissioning', async () => {
    const impact = {
      target_effect: 'decommissioned',
      impact_token: 'b'.repeat(64),
      effective_at: '2026-08-26T10:00:00+00:00',
      pending_incomes: [{
        id: 41,
        concept: 'Hosting agosto',
        pending_amount: '120000.00',
      }],
      future_incomes: [],
      future_payments: [],
      active_hostings: [],
      blockers: [],
    };
    create_request
      .mockResolvedValueOnce({ data: impact })
      .mockResolvedValueOnce({
        data: { project: { ...PROJECT, status_label: 'Dado de baja' } },
      });
    const { wrapper } = mountModal();
    await wrapper.setProps({ open: true });
    await wrapper.get('[data-testid="project-state-target"]').setValue('6');
    await wrapper.get('[data-testid="project-state-preview"]').trigger('click');
    await flushPromises();

    const apply = wrapper.get('[data-testid="project-state-apply"]');
    const incomeDecision = wrapper.get('[data-testid="project-state-income-41"]');
    const note = wrapper.get('[data-testid="project-state-note"]');
    expect(apply.attributes('disabled')).toBeDefined();
    expect(incomeDecision.attributes('aria-invalid')).toBe('true');
    expect(note.attributes('aria-invalid')).toBe('true');
    expect(wrapper.findAll('[role="alert"]').map((alert) => alert.text())).toEqual([
      'Decide qué hacer con el ingreso "Hosting agosto".',
      'Escribe una nota porque la baja omite el paso previo por Suspendido.',
    ]);
    expect(wrapper.get('[data-testid="base-modal-actions"]')
      .find('[role="alert"]').exists()).toBe(false);

    await incomeDecision.setValue('keep_receivable');
    expect(incomeDecision.attributes('aria-invalid')).toBeUndefined();
    expect(wrapper.findAll('[role="alert"]').map((alert) => alert.text())).toEqual([
      'Escribe una nota porque la baja omite el paso previo por Suspendido.',
    ]);

    await note.setValue('Baja directa confirmada por el cliente.');
    expect(note.attributes('aria-invalid')).toBeUndefined();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(apply.attributes('disabled')).toBeUndefined();

    await apply.trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenLastCalledWith(
      'projects/9/state-transitions/',
      {
        state_id: 6,
        impact_token: 'b'.repeat(64),
        effective_at: '2026-08-26T10:00:00+00:00',
        note: 'Baja directa confirmada por el cliente.',
        resolutions: [{ income_id: 41, action: 'keep_receivable' }],
      },
    );
    expect(wrapper.emitted('changed')).toHaveLength(1);
  });
});
