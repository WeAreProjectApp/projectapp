import { createPinia, setActivePinia } from 'pinia';
import { useProposalStore } from '../../stores/proposals';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  put_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { patch_request } = require('../../stores/services/request_http');

const settings = {
  duration_options: [3, 6, 9],
  notice_options: [30, 60, 90],
  default_duration: 9,
  default_renewal_notice: 60,
  default_termination_notice: 60,
};

describe('useProposalStore service contract settings', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useProposalStore();
    jest.clearAllMocks();
  });

  it('patches the nested service-contract settings payload', async () => {
    // Falla si el panel administra los valores en una ruta o forma que el serializador no recibe.
    const response = { service_contract_settings: settings };
    patch_request.mockResolvedValue({ data: response });

    const result = await store.saveServiceContractSettings(settings);

    expect(patch_request).toHaveBeenCalledWith('proposals/company-settings/', { service_contract_settings: settings });
    expect(result).toEqual({ success: true, data: response });
  });

  it('returns nested service-contract serializer errors', async () => {
    // Falla si el formulario pierde el detalle que necesita mostrar después de un PATCH rechazado.
    const errors = { duration_options: ['Las opciones no pueden repetirse.'] };
    patch_request.mockRejectedValue({ response: { data: { service_contract_settings: errors } } });

    const result = await store.saveServiceContractSettings(settings);

    expect(result).toEqual({ success: false, errors });
  });
});
