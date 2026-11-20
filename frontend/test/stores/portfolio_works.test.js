/**
 * Tests for the portfolio_works store.
 *
 * Covers: initial state, fetchWorks, fetchWork, fetchAdminWorks,
 * createWork, updateWork, deleteWork, duplicateWork, getWorkById getter.
 */
import { setActivePinia, createPinia } from 'pinia';
import { usePortfolioWorksStore } from '../../stores/portfolio_works';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const {
  get_request, create_request, patch_request, delete_request,
} = require('../../stores/services/request_http');

const mockWork = {
  id: 1,
  title_es: 'Portal de Cliente',
  title_en: 'Client Portal',
  slug: 'client-portal',
  project_url: 'https://example.com',
};

describe('usePortfolioWorksStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = usePortfolioWorksStore();
    jest.clearAllMocks();
    jest.restoreAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  describe('initial state', () => {
    it('has empty works array', () => {
      expect(store.works).toEqual([]);
    });

    it('has null currentWork', () => {
      expect(store.currentWork).toBeNull();
    });

    it('has isLoading false', () => {
      expect(store.isLoading).toBe(false);
    });

    it('has null error', () => {
      expect(store.error).toBeNull();
    });
  });

  describe('fetchWorks', () => {
    it('fetches public works and updates state', async () => {
      get_request.mockResolvedValue({ data: [mockWork] });

      const result = await store.fetchWorks('es');

      expect(get_request).toHaveBeenCalledWith('portfolio/?lang=es');
      expect(store.works).toHaveLength(1);
      expect(result.success).toBe(true);
    });

    it('defaults to empty array when response.data is falsy', async () => {
      get_request.mockResolvedValue({ data: null });

      const result = await store.fetchWorks('es');

      expect(result.success).toBe(true);
      expect(store.works).toEqual([]);
    });

    it('handles API error gracefully', async () => {
      get_request.mockRejectedValue(new Error('Network error'));

      const result = await store.fetchWorks();

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_failed');
    });

    it('sets isLoading during fetch', async () => {
      get_request.mockResolvedValue({ data: [] });

      const promise = store.fetchWorks();
      expect(store.isLoading).toBe(true);
      await promise;
      expect(store.isLoading).toBe(false);
    });
  });

  describe('fetchWork', () => {
    it('fetches single work by slug', async () => {
      get_request.mockResolvedValue({ data: mockWork });

      const result = await store.fetchWork('client-portal', 'en');

      expect(get_request).toHaveBeenCalledWith('portfolio/client-portal/?lang=en');
      expect(store.currentWork).toEqual(mockWork);
      expect(result.success).toBe(true);
    });

    it('sets not_found error on 404', async () => {
      get_request.mockRejectedValue({ response: { status: 404 } });

      const result = await store.fetchWork('missing');

      expect(result.success).toBe(false);
      expect(store.error).toBe('not_found');
    });

    it('sets unknown error on other status', async () => {
      get_request.mockRejectedValue({ response: { status: 500 } });

      await store.fetchWork('error-slug');

      expect(store.error).toBe('unknown');
    });

    it('keeps the latest localized detail when an older response arrives later', async () => {
      let resolveEnglish;
      get_request.mockReturnValueOnce(new Promise(resolve => { resolveEnglish = resolve; }))
        .mockResolvedValueOnce({ data: { ...mockWork, title: 'Portal de Cliente' } });

      const englishRequest = store.fetchWork('client-portal', 'en');
      await store.fetchWork('client-portal', 'es');
      resolveEnglish({ data: { ...mockWork, title: 'Client Portal' } });
      await englishRequest;

      expect(store.currentWork.title).toBe('Portal de Cliente');
    });

    it('keeps the active detail loading after an obsolete request fails', async () => {
      let rejectPrevious;
      let resolveCurrent;
      get_request.mockReturnValueOnce(new Promise((_, reject) => { rejectPrevious = reject; }))
        .mockReturnValueOnce(new Promise(resolve => { resolveCurrent = resolve; }));

      const previousRequest = store.fetchWork('missing', 'en');
      const currentRequest = store.fetchWork('client-portal', 'en');
      rejectPrevious({ response: { status: 404 } });
      await previousRequest;

      expect(store.isLoading).toBe(true);
      expect(store.error).toBeNull();
      resolveCurrent({ data: mockWork });
      await currentRequest;
    });
  });

  describe('fetchAdminWorks', () => {
    it('fetches all admin works', async () => {
      get_request.mockResolvedValue({ data: [mockWork, { ...mockWork, id: 2 }] });

      const result = await store.fetchAdminWorks();

      expect(get_request).toHaveBeenCalledWith('portfolio/admin/');
      expect(store.works).toHaveLength(2);
      expect(result.success).toBe(true);
    });

    it('handles error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchAdminWorks();

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_failed');
    });
  });

  describe('createWork', () => {
    it('creates work and returns data', async () => {
      create_request.mockResolvedValue({ data: mockWork });

      const result = await store.createWork({ title_es: 'New' });

      expect(create_request).toHaveBeenCalledWith('portfolio/admin/create/', { title_es: 'New' });
      expect(store.currentWork).toEqual(mockWork);
      expect(result.success).toBe(true);
    });

    it('handles validation error', async () => {
      create_request.mockRejectedValue({ response: { data: { title_es: ['required'] } } });

      const result = await store.createWork({});

      expect(result.success).toBe(false);
      expect(store.error).toBe('create_failed');
    });
  });

  describe('updateWork', () => {
    it('updates work and returns data', async () => {
      const updated = { ...mockWork, title_es: 'Updated' };
      patch_request.mockResolvedValue({ data: updated });

      const result = await store.updateWork(1, { title_es: 'Updated' });

      expect(patch_request).toHaveBeenCalledWith('portfolio/admin/1/update/', { title_es: 'Updated' });
      expect(store.currentWork).toEqual(updated);
      expect(result.success).toBe(true);
    });
  });

  describe('deleteWork', () => {
    it('deletes work and removes from list', async () => {
      store.works = [mockWork, { ...mockWork, id: 2 }];
      delete_request.mockResolvedValue({});

      const result = await store.deleteWork(1);

      expect(delete_request).toHaveBeenCalledWith('portfolio/admin/1/delete/');
      expect(store.works).toHaveLength(1);
      expect(store.works[0].id).toBe(2);
      expect(result.success).toBe(true);
    });

    it('clears currentWork if it matches deleted id', async () => {
      store.currentWork = mockWork;
      delete_request.mockResolvedValue({});

      await store.deleteWork(1);

      expect(store.currentWork).toBeNull();
    });

    it('handles delete error', async () => {
      delete_request.mockRejectedValue(new Error('fail'));

      const result = await store.deleteWork(99);

      expect(result.success).toBe(false);
      expect(store.error).toBe('delete_failed');
    });
  });

  describe('duplicateWork', () => {
    it('duplicates work and prepends to list', async () => {
      const dup = { ...mockWork, id: 3, title_es: 'Copy' };
      create_request.mockResolvedValue({ data: dup });
      store.works = [mockWork];

      const result = await store.duplicateWork(1);

      expect(store.works[0].id).toBe(3);
      expect(result.success).toBe(true);
    });

    it('handles duplicate error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.duplicateWork(99);

      expect(result.success).toBe(false);
      expect(store.error).toBe('duplicate_failed');
    });
  });

  describe('fetchAdminWork', () => {
    it('fetches single admin work by id', async () => {
      get_request.mockResolvedValue({ data: mockWork });

      const result = await store.fetchAdminWork(1);

      expect(get_request).toHaveBeenCalledWith('portfolio/admin/1/detail/');
      expect(store.currentWork).toEqual(mockWork);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockWork);
    });

    it('handles error and sets fetch_failed', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchAdminWork(99);

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_failed');
    });

    it('sets isLoading during fetch', async () => {
      get_request.mockResolvedValue({ data: mockWork });

      const promise = store.fetchAdminWork(1);
      expect(store.isLoading).toBe(true);
      await promise;
      expect(store.isLoading).toBe(false);
    });
  });

  describe('createWorkFromJSON', () => {
    it('creates work from JSON and returns data', async () => {
      create_request.mockResolvedValue({ data: mockWork });

      const result = await store.createWorkFromJSON({ title_es: 'JSON Work' });

      expect(create_request).toHaveBeenCalledWith(
        'portfolio/admin/create-from-json/',
        { title_es: 'JSON Work' },
      );
      expect(store.currentWork).toEqual(mockWork);
      expect(result.success).toBe(true);
    });

    it('handles error with validation data', async () => {
      create_request.mockRejectedValue({ response: { data: { title_es: ['required'] } } });

      const result = await store.createWorkFromJSON({});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ title_es: ['required'] });
      expect(store.error).toBe('create_failed');
    });

    it('sets isUpdating during creation', async () => {
      create_request.mockResolvedValue({ data: mockWork });

      const promise = store.createWorkFromJSON({});
      expect(store.isUpdating).toBe(true);
      await promise;
      expect(store.isUpdating).toBe(false);
    });
  });

  describe('uploadCoverImage', () => {
    it('uploads file and updates currentWork', async () => {
      const mockFile = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });
      const updatedWork = { ...mockWork, cover_image: '/media/cover.jpg' };
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(updatedWork),
      });
      Object.defineProperty(document, 'cookie', {
        value: 'csrftoken=testtoken',
        writable: true,
      });

      const result = await store.uploadCoverImage(1, mockFile);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/portfolio/admin/1/upload-cover/',
        expect.objectContaining({ method: 'POST' }),
      );
      expect(store.currentWork).toEqual(updatedWork);
      expect(result.success).toBe(true);
    });

    it('handles missing csrf cookie gracefully', async () => {
      const mockFile = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });
      const updatedWork = { ...mockWork, cover_image: '/media/cover.jpg' };
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(updatedWork),
      });
      Object.defineProperty(document, 'cookie', {
        value: 'othercookie=abc',
        writable: true,
      });

      const result = await store.uploadCoverImage(1, mockFile);

      expect(result.success).toBe(true);
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/portfolio/admin/1/upload-cover/',
        expect.objectContaining({
          headers: { 'X-CSRFToken': '' },
        }),
      );
    });

    it('handles upload failure (non-ok response)', async () => {
      const mockFile = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });
      global.fetch = jest.fn().mockResolvedValue({ ok: false });

      const result = await store.uploadCoverImage(1, mockFile);

      expect(result.success).toBe(false);
      expect(store.error).toBe('upload_failed');
    });

    it('handles network error', async () => {
      const mockFile = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });
      global.fetch = jest.fn().mockRejectedValue(new Error('Network'));

      const result = await store.uploadCoverImage(1, mockFile);

      expect(result.success).toBe(false);
      expect(store.error).toBe('upload_failed');
    });

    it('sets isUpdating during upload', async () => {
      const mockFile = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockWork),
      });

      const promise = store.uploadCoverImage(1, mockFile);
      expect(store.isUpdating).toBe(true);
      await promise;
      expect(store.isUpdating).toBe(false);
    });
  });

  describe('downloadJSONTemplate', () => {
    it('fetches template and returns data', async () => {
      const template = { sections: ['greeting', 'investment'] };
      get_request.mockResolvedValue({ data: template });

      const result = await store.downloadJSONTemplate();

      expect(get_request).toHaveBeenCalledWith('portfolio/admin/json-template/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(template);
    });

    it('handles error gracefully', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.downloadJSONTemplate();

      expect(result.success).toBe(false);
    });
  });

  describe('updateWork error handling', () => {
    it('handles update error with validation data', async () => {
      patch_request.mockRejectedValue({ response: { data: { title_es: ['required'] } } });

      const result = await store.updateWork(1, {});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ title_es: ['required'] });
      expect(store.error).toBe('update_failed');
    });

    it('sets isUpdating during update', async () => {
      patch_request.mockResolvedValue({ data: mockWork });

      const promise = store.updateWork(1, { title_es: 'Up' });
      expect(store.isUpdating).toBe(true);
      await promise;
      expect(store.isUpdating).toBe(false);
    });
  });

  describe('error response null branch', () => {
    it('fetchWork returns unknown error when response has no status', async () => {
      get_request.mockRejectedValue(new Error('network'));

      const result = await store.fetchWork('slug');

      expect(result.success).toBe(false);
      expect(store.error).toBe('unknown');
      expect(result.status).toBeUndefined();
    });

    it('createWork errors is undefined when error has no response', async () => {
      create_request.mockRejectedValue(new Error('network'));

      const result = await store.createWork({});

      expect(result.success).toBe(false);
      expect(result.errors).toBeUndefined();
    });

    it('updateWork errors is undefined when error has no response', async () => {
      patch_request.mockRejectedValue(new Error('network'));

      const result = await store.updateWork(1, {});

      expect(result.success).toBe(false);
      expect(result.errors).toBeUndefined();
    });

    it('createWorkFromJSON errors is undefined when error has no response', async () => {
      create_request.mockRejectedValue(new Error('network'));

      const result = await store.createWorkFromJSON({});

      expect(result.success).toBe(false);
      expect(result.errors).toBeUndefined();
    });

    it('deleteWork does not clear currentWork when id does not match', async () => {
      store.currentWork = { ...mockWork, id: 99 };
      delete_request.mockResolvedValue({});

      await store.deleteWork(1);

      expect(store.currentWork).toEqual({ ...mockWork, id: 99 });
    });
  });

  describe('getWorkById getter', () => {
    it('finds work by id', () => {
      store.works = [mockWork, { ...mockWork, id: 2 }];

      expect(store.getWorkById(1)).toEqual(mockWork);
    });

    it('returns undefined for unknown id', () => {
      store.works = [mockWork];

      expect(store.getWorkById(999)).toBeUndefined();
    });
  });

  describe('fetchWork without error response', () => {
    it('falls back to unknown error when error has no response object', async () => {
      get_request.mockRejectedValue(new Error('Network'));

      const result = await store.fetchWork('slug');

      expect(result.success).toBe(false);
      expect(store.error).toBe('unknown');
      expect(result.status).toBeUndefined();
    });
  });

  describe('deleteWork preserves unrelated currentWork', () => {
    it('does not clear currentWork when deleting different id', async () => {
      store.currentWork = { ...mockWork, id: 2 };
      store.works = [mockWork, { ...mockWork, id: 2 }];
      delete_request.mockResolvedValue({});

      await store.deleteWork(1);

      expect(store.currentWork).toEqual({ ...mockWork, id: 2 });
    });
  });

  describe('uploadCoverImage empty cookie string', () => {
    it('handles empty document.cookie string without throwing', async () => {
      const mockFile = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockWork),
      });
      Object.defineProperty(document, 'cookie', {
        value: '',
        writable: true,
      });

      const result = await store.uploadCoverImage(1, mockFile);

      expect(result.success).toBe(true);
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/portfolio/admin/1/upload-cover/',
        expect.objectContaining({ headers: { 'X-CSRFToken': '' } }),
      );
    });
  });
});
