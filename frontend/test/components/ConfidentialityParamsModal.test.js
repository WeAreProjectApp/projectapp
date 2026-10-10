import { mount } from '@vue/test-utils';

import { useDiagnosticsStore } from '~/stores/diagnostics';

jest.mock('~/stores/diagnostics', () => ({
  useDiagnosticsStore: jest.fn(),
}));

import ConfidentialityParamsModal from '../../components/WebAppDiagnostic/ConfidentialityParamsModal.vue';

const updateConfidentialityParams = jest.fn();
useDiagnosticsStore.mockReturnValue({ updateConfidentialityParams });

function mountModal(storedParams = {}) {
  return mount(ConfidentialityParamsModal, {
    props: {
      visible: false,
      diagnostic: {
        id: 7,
        client: { name: 'Acme Corp', email: 'client@acme.com' },
        confidentiality_params: storedParams,
      },
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'kind'],
          template: '<div v-if="modelValue" :data-kind="kind"><slot /><slot name="footer" /></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'loading', 'disabled', 'type'],
          template: '<button :type="type || \'button\'" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
  });
}

// The watcher that fills the form runs on a visible transition, so the modal
// has to be opened rather than mounted already-open.
async function open(storedParams) {
  const wrapper = mountModal(storedParams);
  await wrapper.setProps({ visible: true });
  await wrapper.vm.$nextTick();
  return wrapper;
}

describe('ConfidentialityParamsModal — identificación del consultor', () => {
  beforeEach(() => {
    updateConfidentialityParams.mockReset();
    updateConfidentialityParams.mockResolvedValue({ success: true, data: {} });
  });

  it('does not save and explains why when the consultant has no document', async () => {
    const wrapper = await open({ contractor_nit: '', contractor_cedula: '' });

    await wrapper.find('form').trigger('submit');

    expect(updateConfidentialityParams).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('Indica el NIT o la cédula del consultor');
  });

  it('saves a consultant identified only by cédula', async () => {
    const wrapper = await open({ contractor_nit: '', contractor_cedula: '1037635428' });

    await wrapper.find('form').trigger('submit');

    expect(updateConfidentialityParams).toHaveBeenCalledTimes(1);
    const [, payload] = updateConfidentialityParams.mock.calls[0];
    expect(payload.contractor_cedula).toBe('1037635428');
    // handleSave strips empty keys, so the unused document never travels.
    expect(payload.contractor_nit).toBeUndefined();
  });

  it('saves a consultant identified only by NIT', async () => {
    const wrapper = await open({ contractor_nit: '900.123.456-7', contractor_cedula: '' });

    await wrapper.find('form').trigger('submit');

    expect(updateConfidentialityParams).toHaveBeenCalledTimes(1);
    const [, payload] = updateConfidentialityParams.mock.calls[0];
    expect(payload.contractor_nit).toBe('900.123.456-7');
  });

  it('leaves the client fields optional', async () => {
    const wrapper = await open({
      contractor_nit: '900.123.456-7',
      client_full_name: '',
      client_cedula: '',
    });

    await wrapper.find('form').trigger('submit');

    expect(updateConfidentialityParams).toHaveBeenCalledTimes(1);
  });
});

describe('ConfidentialityParamsModal — ancho del modal', () => {
  it('opens at the form width', async () => {
    const wrapper = await open();

    expect(wrapper.attributes('data-kind')).toBe('form');
  });
});
