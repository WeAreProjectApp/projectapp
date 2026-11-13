import { flushPromises, mount } from '@vue/test-utils';

import RequestDetail from '../../components/RequirementPackages/RequestDetail.vue';

const translations = {
  'requirementPackages.offered': 'Pendiente de aceptación',
  'requirementPackages.size': 'Talla',
  'requirementPackages.scope': 'Alcance propuesto',
  'requirementPackages.explanation': 'Por qué corresponde esta talla',
  'requirementPackages.assumptions': 'Supuestos',
  'requirementPackages.schedule': 'Fecha orientativa de entrega',
  'requirementPackages.scheduleConditions': 'Condiciones de la agenda',
  'requirementPackages.consent': 'Confirmo el alcance, la talla y la agenda orientativa de esta propuesta.',
  'requirementPackages.objection': 'Explica tu objeción',
  'requirementPackages.acceptance': 'Aceptar y utilizar un cupo {size}',
  'requirementPackages.object': 'Objetar la propuesta',
  'requirementPackages.noBalance': 'Necesitas un cupo vigente.',
  'requirementPackages.outside': 'Requiere una cotización independiente.',
};
const originalUseI18n = global.useI18n;

function requestRow() {
  return {
    id: 44,
    version: 9,
    title: 'Aviso de vencimiento',
    description: 'Mostrar un aviso antes del vencimiento.',
    status: 'offered',
    suggested_order_id: 'order-204',
    proposal: {
      id: 77,
      size: 'S',
      warranty: false,
      scope: 'Un aviso visible en el resumen.',
      explanation: 'Usa información ya disponible.',
      assumptions: 'No modifica la facturación.',
      schedule_conditions: 'Depende de la revisión del cliente.',
      delivery_from: '2026-11-14',
      delivery_until: '2026-11-18',
      examples: ['Aviso dentro del panel actual.'],
    },
    proposals: [],
  };
}

function mountDetail(api) {
  return mount(RequestDetail, {
    props: { api, row: requestRow() },
    global: {
      stubs: {
        BaseButton: {
          props: ['disabled'],
          emits: ['click'],
          template: '<button v-bind="$attrs" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseCheckbox: {
          props: ['modelValue', 'disabled'],
          emits: ['update:modelValue'],
          template: '<label><input data-testid="package-consent" type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.checked)" /><slot /></label>',
        },
        ProposalEditor: true,
      },
    },
  });
}

describe('RequirementPackages RequestDetail decisions', () => {
  let wrapper;

  beforeEach(() => {
    global.useI18n = () => ({
      t: (key, params = {}) =>
        (translations[key] || key).replace('{size}', params.size || ''),
    });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    global.useI18n = originalUseI18n;
  });

  // Falla si aceptar sin consentimiento consume un cupo, o si la decisión pierde la versión y la compra propuestas.
  it('sends the explicit consent decision with the proposed version and order', async () => {
    const api = {
      decide: jest.fn().mockResolvedValue({ id: 44, status: 'accepted' }),
      evaluate: jest.fn(),
    };
    wrapper = mountDetail(api);

    expect(wrapper.get('[data-testid="package-accept"]').element.disabled).toBe(true);
    await wrapper.get('[data-testid="package-consent"]').setValue(true);
    await wrapper.get('[data-testid="package-accept"]').trigger('click');
    await flushPromises();

    expect(api.decide).toHaveBeenCalledWith(44, {
      expected_version: 9,
      proposal_id: 77,
      decision: 'accept',
      message: '',
      order_id: 'order-204',
    });
    expect(wrapper.emitted('saved')).toEqual([[]]);
  });

  // Falla si rechazar una propuesta borra el motivo del cliente o esconde el error que debe corregir.
  it('preserves an objection draft and exposes the server message after a rejected decision', async () => {
    const api = {
      decide: jest.fn().mockRejectedValue({
        response: { data: { detail: 'La propuesta ya cambió.' } },
      }),
      evaluate: jest.fn(),
    };
    wrapper = mountDetail(api);
    const objection = wrapper.get('textarea');
    await objection.setValue('El alcance incluye una pantalla adicional.');
    await wrapper.get('[data-testid="package-object"]').trigger('click');
    await flushPromises();

    expect(api.decide).toHaveBeenCalledWith(44, {
      expected_version: 9,
      proposal_id: 77,
      decision: 'object',
      message: 'El alcance incluye una pantalla adicional.',
      order_id: 'order-204',
    });
    expect(wrapper.get('[role="alert"]').text()).toBe('La propuesta ya cambió.');
    expect(wrapper.get('textarea').element.value).toBe(
      'El alcance incluye una pantalla adicional.',
    );
  });
});
