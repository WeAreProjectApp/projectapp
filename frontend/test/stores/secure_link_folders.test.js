/** Tests for the secure-link folder navigation store. */
import { setActivePinia, createPinia } from 'pinia';
import { useSecureLinkFoldersStore } from '../../stores/secure_link_folders';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { get_request } = require('../../stores/services/request_http');

describe('useSecureLinkFoldersStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useSecureLinkFoldersStore();
    jest.clearAllMocks();
  });

  it('keeps the latest folder tree when an earlier reload resolves last', async () => {
    let resolveFirst;
    let resolveSecond;
    get_request
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));

    const firstReload = store.fetchFolders();
    const latestReload = store.fetchFolders();
    resolveSecond({ data: {
      folders: [
        { id: 20, name: 'Current project', parent: null, is_archived: false, link_count: 4, archived_link_count: 0 },
        { id: 21, name: 'Current subfolder', parent: 20, is_archived: false, link_count: 1, archived_link_count: 2 },
      ],
      navigation: { projects: [{ id: 200, name: 'Current project' }], clients: [{ id: 300, name: 'Current client' }] },
    } });
    await latestReload;
    resolveFirst({ data: {
      folders: [{ id: 10, name: 'Outdated project', parent: null, is_archived: false, link_count: 9, archived_link_count: 0 }],
      navigation: { projects: [{ id: 100, name: 'Outdated project' }], clients: [] },
    } });

    // Fails if a slow reload restores the hierarchy from before a folder change.
    expect(await firstReload).toEqual({ success: false, stale: true });
    expect(store.folders).toEqual([
      { id: 20, name: 'Current project', parent: null, is_archived: false, link_count: 4, archived_link_count: 0, active_document_count: 4, archived_document_count: 0, active_children_count: 1, archived_children_count: 0 },
      { id: 21, name: 'Current subfolder', parent: 20, is_archived: false, link_count: 1, archived_link_count: 2, active_document_count: 1, archived_document_count: 2, active_children_count: 0, archived_children_count: 0 },
    ]);
    expect(store.navigation).toEqual({ projects: [{ id: 200, name: 'Current project' }], clients: [{ id: 300, name: 'Current client' }] });
  });
});
