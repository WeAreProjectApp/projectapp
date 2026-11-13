import { createPinia, setActivePinia } from 'pinia';
import { usePlatformHelpAdminStore } from '../../stores/platform-help-admin';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
}));

const { get_request } = require('../../stores/services/request_http');

describe('usePlatformHelpAdminStore client search', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = usePlatformHelpAdminStore();
  });

  afterEach(() => { jest.clearAllMocks(); });

  // Falla si una búsqueda nueva deja visibles clientes de la página anterior durante la espera del debounce.
  it('invalidates pagination before the next client request begins', () => {
    store.clients = { results: [{ user_id: 17, name: 'Ada' }], page: 4, count: 31 };

    store.invalidateClients('ana');

    expect(store.clients).toEqual({ results: [], page: 1, count: 0 });
    expect(store.clientsSearch).toBe('ana');
    expect(store.clientsLoading).toBe(true);
    expect(get_request).not.toHaveBeenCalled();
  });

  // Falla si una respuesta antigua vuelve a insertar una página que fue invalidada durante el debounce.
  it('discards a response resolved after its search was invalidated', async () => {
    let resolvePrevious;
    get_request.mockImplementationOnce(() => new Promise((resolve) => { resolvePrevious = resolve; }));

    const previous = store.loadClients(3, 'ad');
    store.invalidateClients('ana');
    resolvePrevious({ data: { results: [{ user_id: 17, name: 'Ada' }], page: 3, count: 1 } });
    await previous;

    expect(store.clients).toEqual({ results: [], page: 1, count: 0 });
    expect(store.clientsLoading).toBe(true);
    expect(store.clientsError).toBe(false);
  });

  // Falla si una respuesta o error tardío reemplaza los resultados de una consulta posterior.
  it('keeps the newest results after older requests resolve and reject out of order', async () => {
    let rejectPrevious;
    get_request
      .mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectPrevious = reject; }))
      .mockResolvedValueOnce({ data: { results: [{ user_id: 28, name: 'Ana María' }], page: 1, count: 1 } });

    const previous = store.loadClients(2, 'an');
    const current = store.loadClients(1, 'ana');
    await current;
    rejectPrevious(new Error('old request failed'));
    await previous;

    expect(store.clients).toEqual({ results: [{ user_id: 28, name: 'Ana María' }], page: 1, count: 1 });
    expect(store.clientsSearch).toBe('ana');
    expect(store.clientsLoading).toBe(false);
    expect(store.clientsError).toBe(false);
  });

  // Falla si un error actual queda pegado después de una búsqueda posterior exitosa.
  it('clears the current error when a later client page loads', async () => {
    get_request
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ data: { results: [{ user_id: 35, name: 'Ángela' }], page: 2, count: 6 } });

    await store.loadClients(5, 'ang');
    expect(store.clientsError).toBe(true);
    expect(store.clients).toEqual({ results: [], page: 5, count: 0 });

    await store.loadClients(2, 'áng');

    expect(store.clientsError).toBe(false);
    expect(store.clients).toEqual({ results: [{ user_id: 35, name: 'Ángela' }], page: 2, count: 6 });
  });
});
