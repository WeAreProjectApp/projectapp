/**
 * Tests for the hour_packages store.
 *
 * Covers: initial state, fetchAdminPackages (with/without nationality filter),
 * fetchAdminPackage, createPackage, updatePackage, deletePackage,
 * getPackageById getter.
 */
import { setActivePinia, createPinia } from 'pinia';
import { useHourPackagesStore } from '../../stores/hour_packages';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const {
  get_request, create_request, patch_request, delete_request,
} = require('../../stores/services/request_http');

const mockPackage = {
  id: 1,
  nationality: 'COL',
  currency: 'COP',
  name_es: 'Paquete Ágil',
  name_en: 'Agile Pack',
  pricing_model: 'requirements',
  xs_count: 30,
  s_count: 0,
  m_count: 0,
  validity_months: 12,
  reference_price: '1500000.00',
  total_price: '1350000.00',
  discount_percent: 0,
  is_active: true,
  order: 1,
};

describe('useHourPackagesStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useHourPackagesStore();
    jest.clearAllMocks();
    jest.restoreAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  describe('initial state', () => {
    it('has empty packages array and null currentPackage', () => {
      expect(store.packages).toEqual([]);
      expect(store.currentPackage).toBeNull();
      expect(store.isLoading).toBe(false);
      expect(store.isUpdating).toBe(false);
      expect(store.error).toBeNull();
    });
  });

  describe('fetchAdminPackages', () => {
    it('fetches all packages without filter', async () => {
      get_request.mockResolvedValue({ data: [mockPackage] });
      const result = await store.fetchAdminPackages();
      expect(get_request).toHaveBeenCalledWith('hour-packages/admin/');
      expect(result.success).toBe(true);
      expect(store.packages).toEqual([mockPackage]);
    });

    it('passes the nationality filter in the URL', async () => {
      get_request.mockResolvedValue({ data: [] });
      await store.fetchAdminPackages('EXT');
      expect(get_request).toHaveBeenCalledWith('hour-packages/admin/?nationality=EXT');
    });

    it('sets error on failure', async () => {
      get_request.mockRejectedValue(new Error('boom'));
      const result = await store.fetchAdminPackages('COL');
      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_failed');
    });
  });

  describe('fetchAdminPackage', () => {
    it('fetches detail and sets currentPackage', async () => {
      get_request.mockResolvedValue({ data: mockPackage });
      const result = await store.fetchAdminPackage(1);
      expect(get_request).toHaveBeenCalledWith('hour-packages/admin/1/detail/');
      expect(result.success).toBe(true);
      expect(store.currentPackage).toEqual(mockPackage);
    });

    it('sets error on failure', async () => {
      get_request.mockRejectedValue(new Error('boom'));
      const result = await store.fetchAdminPackage(1);
      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_failed');
    });
  });

  describe('createPackage', () => {
    it('creates a package and returns data', async () => {
      create_request.mockResolvedValue({ data: mockPackage });
      const result = await store.createPackage({ name_es: 'Paquete Ágil' });
      expect(create_request).toHaveBeenCalledWith(
        'hour-packages/admin/create/', { name_es: 'Paquete Ágil' },
      );
      expect(result.success).toBe(true);
      expect(store.currentPackage).toEqual(mockPackage);
    });

    it('propagates DRF field errors on failure', async () => {
      create_request.mockRejectedValue({
        response: { data: { xs_count: ['Incluye al menos un cupo XS, S o M.'] } },
      });
      const result = await store.createPackage({ xs_count: 0, s_count: 0, m_count: 0 });
      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ xs_count: ['Incluye al menos un cupo XS, S o M.'] });
      expect(store.error).toBe('create_failed');
    });
  });

  describe('updatePackage', () => {
    it('patches a package and updates currentPackage', async () => {
      const updated = { ...mockPackage, xs_count: 40 };
      patch_request.mockResolvedValue({ data: updated });
      const result = await store.updatePackage(1, { xs_count: 40 });
      expect(patch_request).toHaveBeenCalledWith(
        'hour-packages/admin/1/update/', { xs_count: 40 },
      );
      expect(result.success).toBe(true);
      expect(store.currentPackage).toEqual(updated);
    });

    it('propagates errors on failure', async () => {
      patch_request.mockRejectedValue({
        response: { data: { non_field_errors: ['La composición debe incluir al menos un cupo.'] } },
      });
      const result = await store.updatePackage(1, { xs_count: 0, s_count: 0, m_count: 0 });
      expect(result.success).toBe(false);
      expect(result.errors).toEqual({
        non_field_errors: ['La composición debe incluir al menos un cupo.'],
      });
      expect(store.error).toBe('update_failed');
    });
  });

  describe('deletePackage', () => {
    it('deletes a package and removes it from the list', async () => {
      store.packages = [mockPackage, { ...mockPackage, id: 2 }];
      store.currentPackage = mockPackage;
      delete_request.mockResolvedValue({});
      const result = await store.deletePackage(1);
      expect(delete_request).toHaveBeenCalledWith('hour-packages/admin/1/delete/');
      expect(result.success).toBe(true);
      expect(store.packages.map((p) => p.id)).toEqual([2]);
      expect(store.currentPackage).toBeNull();
    });

    it('sets error on failure', async () => {
      delete_request.mockRejectedValue(new Error('boom'));
      const result = await store.deletePackage(1);
      expect(result.success).toBe(false);
      expect(store.error).toBe('delete_failed');
    });
  });

  describe('settings', () => {
    it('fetchSettings stores the singleton', async () => {
      get_request.mockResolvedValue({ data: { default_view_mode: 'cards' } });
      const result = await store.fetchSettings();
      expect(get_request).toHaveBeenCalledWith('hour-packages/admin/settings/');
      expect(result.success).toBe(true);
      expect(store.settings).toEqual({ default_view_mode: 'cards' });
    });

    it('fetchSettings reports failure without throwing', async () => {
      get_request.mockRejectedValue(new Error('boom'));
      const result = await store.fetchSettings();
      expect(result.success).toBe(false);
      expect(store.settings).toBeNull();
    });

    it('updateSettings patches and stores the new value', async () => {
      patch_request.mockResolvedValue({ data: { default_view_mode: 'compare' } });
      const result = await store.updateSettings({ default_view_mode: 'compare' });
      expect(patch_request).toHaveBeenCalledWith(
        'hour-packages/admin/settings/update/', { default_view_mode: 'compare' },
      );
      expect(result.success).toBe(true);
      expect(store.settings).toEqual({ default_view_mode: 'compare' });
    });

    it('updateSettings propagates validation errors', async () => {
      patch_request.mockRejectedValue({
        response: { data: { default_view_mode: ['"x" is not a valid choice.'] } },
      });
      const result = await store.updateSettings({ default_view_mode: 'x' });
      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ default_view_mode: ['"x" is not a valid choice.'] });
    });

    it('updateSettings sends base rates and stores the propagation counts', async () => {
      const response = {
        default_view_mode: 'table',
        base_rate_col: '35000.00',
        base_rate_ext: '20.00',
        base_rate_usa: '30.00',
        updated_packages: { COL: 4, EXT: 4 },
      };
      patch_request.mockResolvedValue({ data: response });
      const payload = { base_rate_col: 35000, base_rate_ext: 20, base_rate_usa: 30 };
      const result = await store.updateSettings(payload);
      expect(patch_request).toHaveBeenCalledWith(
        'hour-packages/admin/settings/update/', payload,
      );
      expect(result.success).toBe(true);
      expect(result.data.updated_packages).toEqual({ COL: 4, EXT: 4 });
      expect(store.settings).toEqual(response);
    });

    it('updateSettings surfaces base-rate validation errors', async () => {
      patch_request.mockRejectedValue({
        response: { data: { base_rate_col: ['La tarifa base debe ser mayor a 0.'] } },
      });
      const result = await store.updateSettings({ base_rate_col: 0 });
      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ base_rate_col: ['La tarifa base debe ser mayor a 0.'] });
    });
  });

  describe('restoreDefaults', () => {
    it('posts the nationality and returns the fresh list', async () => {
      const fresh = [{ ...mockPackage, id: 10, xs_count: 40, s_count: 20, m_count: 10 }];
      create_request.mockResolvedValue({ data: fresh });
      const result = await store.restoreDefaults('COL');
      expect(create_request).toHaveBeenCalledWith(
        'hour-packages/admin/restore-defaults/', { nationality: 'COL' },
      );
      expect(result.success).toBe(true);
      expect(result.data).toEqual(fresh);
    });

    it('reports failure on error', async () => {
      create_request.mockRejectedValue(new Error('boom'));
      const result = await store.restoreDefaults('COL');
      expect(result.success).toBe(false);
    });
  });

  describe('getPackageById', () => {
    it('finds a package in the list', () => {
      store.packages = [mockPackage];
      expect(store.getPackageById(1)).toEqual(mockPackage);
      expect(store.getPackageById(99)).toBeUndefined();
    });
  });
});
