import { setActivePinia, createPinia } from 'pinia';
import { usePanelProjectsStore } from '../../stores/panel_projects';
import { useAccountingStore } from '../../stores/accounting';
import { get_request, delete_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(), create_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn(),
}));

describe('panel project deletion', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setActivePinia(createPinia());
  });

  it('returns the dependency preview for the selected project', async () => {
    get_request.mockResolvedValue({ data: { can_delete: false, blockers: [{ key: 'incomes', count: 2 }] } });

    const result = await usePanelProjectsStore().previewDeletion(7);

    expect(get_request).toHaveBeenCalledWith('projects/7/delete-preview/');
    expect(result.data.blockers).toEqual([{ key: 'incomes', count: 2 }]);
  });

  // Fails if the forced-delete review silently falls back to the safe preview endpoint.
  it('requests the forced dependency preview separately', async () => {
    get_request.mockResolvedValue({ data: { can_delete: true, impact_token: 'force-token-7' } });

    const result = await usePanelProjectsStore().previewDeletion(7, { force: true });

    expect(get_request).toHaveBeenCalledWith('projects/7/delete-preview/?force=true');
    expect(result.data.impact_token).toBe('force-token-7');
  });

  it('returns a recoverable preview failure', async () => {
    get_request.mockRejectedValue({ response: { status: 503, data: { error: 'No disponible' } } });

    const result = await usePanelProjectsStore().previewDeletion(7);

    expect(result).toMatchObject({ success: false, status: 503, message: 'No disponible' });
  });

  it('refreshes the project list after deletion', async () => {
    const store = usePanelProjectsStore();
    store.records = [{ id: 7 }, { id: 8 }];
    delete_request.mockResolvedValue({ status: 204 });
    get_request.mockResolvedValue({ data: { results: [{ id: 8 }], meta: { total: 1 } } });

    const result = await store.deleteProject(7);

    expect(result.success).toBe(true);
    expect(store.records).toEqual([{ id: 8 }]);
    expect(store.meta.total).toBe(1);
  });

  // Fails if an ordinary deletion starts sending the force-delete confirmation body.
  it('keeps ordinary deletion bodyless', async () => {
    delete_request.mockResolvedValue({ status: 204 });
    get_request.mockResolvedValue({ data: { results: [], meta: { total: 0 } } });

    await usePanelProjectsStore().deleteProject(7);

    expect(delete_request).toHaveBeenCalledWith('projects/7/delete/');
  });

  // Fails if the destructive confirmation or the reviewed dependency token is dropped.
  it('sends the forced deletion body unchanged', async () => {
    const payload = { force: true, confirmation: 'DELETE', impact_token: 'force-token-7' };
    delete_request.mockResolvedValue({ status: 204 });
    get_request.mockResolvedValue({ data: { results: [], meta: { total: 0 } } });

    await usePanelProjectsStore().deleteProject(7, payload);

    expect(delete_request).toHaveBeenCalledWith('projects/7/delete/', payload);
  });

  it('invalidates stale project pickers after deletion', async () => {
    const accounting = useAccountingStore();
    accounting.projectsByClient = { 4: [{ id: 7, name: 'Unused' }] };
    delete_request.mockResolvedValue({ status: 204 });
    get_request.mockResolvedValue({ data: { results: [], meta: { total: 0 } } });

    await usePanelProjectsStore().deleteProject(7);

    expect(accounting.projectsByClient).toEqual({});
  });

  it('keeps the row when deletion is blocked', async () => {
    const store = usePanelProjectsStore();
    store.records = [{ id: 7 }];
    const preview = { code: 'project_delete_blocked', error: 'Dependencias', can_delete: false, blockers: [{ key: 'documents', count: 1 }] };
    delete_request.mockRejectedValue({ response: { status: 409, data: preview } });

    const result = await store.deleteProject(7);

    expect(result).toMatchObject({ success: false, preview });
    expect(store.records).toEqual([{ id: 7 }]);
    expect(store.isUpdating).toBe(false);
  });

  it('treats a failed refresh as a completed deletion', async () => {
    const store = usePanelProjectsStore();
    store.records = [{ id: 7 }];
    delete_request.mockResolvedValue({ status: 204 });
    get_request.mockRejectedValue(new Error('Network'));

    const result = await store.deleteProject(7);

    expect(result).toEqual({ success: true, refreshFailed: true });
    expect(store.records).toEqual([]);
  });
});
