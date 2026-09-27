import { flushPromises, mount } from '@vue/test-utils';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';
import ServiceContractSettings from '../../components/BusinessProposal/admin/ServiceContractSettings.vue';

const store = {
  fetchCompanySettings: jest.fn(),
  saveServiceContractSettings: jest.fn(),
};

global.useProposalStore = () => store;
global.useI18n = () => ({
  t: (key, values = {}) => ({
    'serviceContract.settingsTitle': 'Datos del contrato de servicio',
    'serviceContract.settingsHint': 'Opciones globales para generar contratos.',
    'serviceContract.emptyList': 'Agrega al menos una opción.',
    'serviceContract.invalidNumber': 'Escribe un entero entre 1 y 999.',
    'serviceContract.duplicates': 'Las opciones no pueden repetirse.',
    'serviceContract.chooseDefault': 'Selecciona un valor incluido en las opciones.',
    'serviceContract.saveError': 'No se pudo guardar la configuración. Revisa los valores e inténtalo de nuevo.',
    'serviceContract.save': 'Guardar',
    'serviceContract.loading': 'Cargando configuración…',
    'serviceContract.retry': 'Reintentar',
    'serviceContract.duration_options': 'Duración (meses)',
    'serviceContract.notice_options': 'Preavisos (días calendario)',
    'serviceContract.optionLabel': `${values.catalog}: opción ${values.index}`,
    'serviceContract.removeOption': `Quitar opción ${values.index} de ${values.catalog}`,
    'serviceContract.addOption': `Agregar opción de ${values.catalog}`,
    'serviceContract.defaultLabel': `${values.field}: preselección`,
    'serviceContract.fields.service_initial_term': 'Duración inicial',
    'serviceContract.fields.service_renewal_notice_days': 'Preaviso para no renovar',
    'serviceContract.fields.service_termination_notice_days': 'Preaviso de terminación',
  }[key] || key),
});

const BaseButtonStub = {
  props: ['type', 'disabled', 'loading'],
  emits: ['click'],
  template: '<button v-bind="$attrs" :type="type || \'button\'" :disabled="disabled || loading" @click="$emit(\'click\', $event)"><slot /></button>',
};

function settings(overrides = {}) {
  return {
    duration_options: [3, 6, 9],
    notice_options: [30, 60, 90],
    default_duration: 9,
    default_renewal_notice: 60,
    default_termination_notice: 60,
    ...overrides,
  };
}

function mountSettings() {
  return mount(ServiceContractSettings, {
    global: {
      components: {
        BaseFormField,
        BaseInput,
        BaseSelect,
      },
      stubs: {
        BaseButton: BaseButtonStub,
      },
    },
  });
}

describe('ServiceContractSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('keeps duplicate catalog values out of the save request', async () => {
    // Falla si una configuración inválida llega a la API en vez de mostrarse al administrador.
    store.fetchCompanySettings.mockResolvedValue({ success: true, data: { service_contract_settings: settings() } });
    const wrapper = mountSettings();
    await flushPromises();

    await wrapper.findAll('input').at(0).setValue('6');

    await wrapper.get('form').trigger('submit');

    expect(wrapper.text()).toContain('Las opciones no pueden repetirse.');
    expect(store.saveServiceContractSettings).not.toHaveBeenCalled();
  });

  it('submits sorted settings after the server rejects them', async () => {
    // Falla si el panel envía catálogos desordenados o descarta el error devuelto por el servidor.
    store.fetchCompanySettings.mockResolvedValue({
      success: true,
      data: {
        service_contract_settings: settings({
          duration_options: [12, 3],
          notice_options: [90, 30],
          default_duration: 3,
          default_renewal_notice: 30,
          default_termination_notice: 30,
        }),
      },
    });
    store.saveServiceContractSettings.mockResolvedValue({
      success: false,
      errors: { default_duration: ['Selecciona una duración válida.'] },
    });
    const wrapper = mountSettings();
    await flushPromises();

    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(store.saveServiceContractSettings).toHaveBeenCalledWith({
      duration_options: [3, 12],
      notice_options: [30, 90],
      default_duration: 3,
      default_renewal_notice: 30,
      default_termination_notice: 30,
    });
    expect(wrapper.text()).toContain('Selecciona una duración válida.');
    expect(wrapper.findAll('input').at(0).element.value).toBe('12');
  });
});
