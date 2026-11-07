import { createPinia, setActivePinia } from 'pinia';
import { useProposalClientsStore } from '../../stores/proposal_clients';
import { get_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));

const pendingResponse = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const rows = [{ id: 12, name: 'PA-216 QA client' }];
const counts = { all: 1, active: 1, orphans: 0, archived: 0 };
const zeroCounts = { all: 0, active: 0, orphans: 0, archived: 0 };

beforeEach(() => {
  setActivePinia(createPinia());
  jest.resetAllMocks();
});

describe('Client register query consistency', () => {
  it('publishes rows only after their status counts finish', async () => {
    const store = useProposalClientsStore();
    const waitingCounts = pendingResponse();
    get_request.mockResolvedValueOnce({ data: rows }).mockReturnValueOnce(waitingCounts.promise);

    const load = store.fetchClientRegister({ search: 'PA-216' });
    await Promise.resolve();
    expect(store.clients).toEqual([]);
    waitingCounts.resolve({ data: counts });
    await load;

    expect({ rows: store.clients, counts: store.statusCounts, loading: store.isLoading })
      .toEqual({ rows, counts, loading: false });
  });

  it('ignores an older query that completes after the empty result', async () => {
    const store = useProposalClientsStore();
    const oldRows = pendingResponse();
    const oldCounts = pendingResponse();
    get_request.mockReturnValueOnce(oldRows.promise).mockReturnValueOnce(oldCounts.promise)
      .mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: zeroCounts });

    const oldLoad = store.fetchClientRegister();
    await store.fetchClientRegister({ search: '[QA006] Cliente A' });
    oldRows.resolve({ data: rows });
    oldCounts.resolve({ data: counts });
    await oldLoad;

    expect({ rows: store.clients, counts: store.statusCounts }).toEqual({ rows: [], counts: zeroCounts });
  });

  it('invalidates the pending query before the debounce launches its replacement', async () => {
    const store = useProposalClientsStore();
    store.clients = rows;
    store.statusCounts = counts;
    const oldRows = pendingResponse();
    get_request.mockReturnValueOnce(oldRows.promise).mockResolvedValueOnce({ data: counts });

    const load = store.fetchClientRegister();
    store.invalidateClientRegister();
    oldRows.resolve({ data: rows });
    await load;

    expect({ rows: store.clients, counts: store.statusCounts, loading: store.isLoading })
      .toEqual({ rows: [], counts: {}, loading: true });
  });

  it.each([0, 1])('clears previous results when register endpoint %i fails', async (failedEndpoint) => {
    const store = useProposalClientsStore();
    store.clients = rows;
    store.statusCounts = counts;
    const requests = [Promise.resolve({ data: rows }), Promise.resolve({ data: counts })];
    requests[failedEndpoint] = Promise.reject({ response: { data: { error: 'unavailable' } } });
    get_request.mockReturnValueOnce(requests[0]).mockReturnValueOnce(requests[1]);

    await store.fetchClientRegister({ search: 'missing' });

    expect({ rows: store.clients, counts: store.statusCounts, error: store.error, loading: store.isLoading })
      .toEqual({ rows: [], counts: {}, error: 'unavailable', loading: false });
  });

  it('restores the register when the search is cleared', async () => {
    const store = useProposalClientsStore();
    get_request.mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: zeroCounts })
      .mockResolvedValueOnce({ data: rows }).mockResolvedValueOnce({ data: counts });
    await store.fetchClientRegister({ search: 'missing' });

    await store.fetchClientRegister({ search: '' });

    expect({ rows: store.clients, counts: store.statusCounts }).toEqual({ rows, counts });
  });
});
