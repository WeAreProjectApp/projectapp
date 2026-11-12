/**
 * Tests for the emails store.
 *
 * Covers: init, fetchDefaults, global fetchHistory, fetchEmailBody, sendEmail,
 * happy path, error handling, loading states.
 */
import { setActivePinia, createPinia } from 'pinia';
import { useEmailStore } from '../../stores/emails';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  put_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const {
  get_request,
  create_request,
  put_request,
  patch_request,
  delete_request,
} = require('../../stores/services/request_http');

describe('useEmailStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useEmailStore();
    jest.clearAllMocks();
    jest.restoreAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  // ── Initial state ──────────────────────────────────────────────────────────

  describe('initial state', () => {
    it('has empty history array', () => {
      expect(store.history).toEqual([]);
    });

    it('has default historyPagination', () => {
      expect(store.historyPagination).toEqual({ total: 0, page: 1, has_next: false });
    });

    it('has default defaults with greeting and footer', () => {
      expect(store.defaults).toEqual({ greeting: '', footer: '' });
    });

    it('has isSending as false', () => {
      expect(store.isSending).toBe(false);
    });

    it('has isLoadingHistory as false', () => {
      expect(store.isLoadingHistory).toBe(false);
    });

    it('has isLoadingDefaults as false', () => {
      expect(store.isLoadingDefaults).toBe(false);
    });

    it('has error as null', () => {
      expect(store.error).toBeNull();
    });
  });

  // ── fetchDefaults ──────────────────────────────────────────────────────────

  describe('fetchDefaults', () => {
    it('fetches defaults and returns success with data', async () => {
      const mockDefaults = { greeting: 'Hello', footer: 'Best regards' };
      get_request.mockResolvedValue({ data: mockDefaults });

      const result = await store.fetchDefaults();

      expect(get_request).toHaveBeenCalledWith('emails/defaults/');
      expect(store.defaults).toEqual(mockDefaults);
      expect(result).toEqual({ success: true, data: mockDefaults });
      expect(store.isLoadingDefaults).toBe(false);
    });

    it('sets isLoadingDefaults during request', async () => {
      let capturedLoading;
      get_request.mockImplementation(() => {
        capturedLoading = store.isLoadingDefaults;
        return Promise.resolve({ data: {} });
      });

      await store.fetchDefaults();

      expect(capturedLoading).toBe(true);
      expect(store.isLoadingDefaults).toBe(false);
    });

    it('handles API error and sets error state', async () => {
      get_request.mockRejectedValue(new Error('Network error'));

      const result = await store.fetchDefaults();

      expect(store.error).toBe('fetch_defaults_failed');
      expect(result).toEqual({ success: false });
      expect(store.isLoadingDefaults).toBe(false);
    });
  });

  // ── saveDefaults ───────────────────────────────────────────────────────────

  describe('saveDefaults', () => {
    const payload = { greeting: 'Hola {client_name}', footer: 'Saludos', signer: 'carlos' };

    it('puts payload to emails/defaults/ and updates defaults state', async () => {
      const mockResponse = {
        greeting: 'Hola ',
        footer: 'Saludos',
        config: { greeting: 'Hola {client_name}', footer: 'Saludos', signer: 'carlos' },
      };
      put_request.mockResolvedValue({ data: mockResponse });

      const result = await store.saveDefaults(payload);

      expect(put_request).toHaveBeenCalledWith('emails/defaults/', payload);
      expect(store.defaults).toEqual(mockResponse);
      expect(result).toEqual({ success: true, data: mockResponse });
      expect(store.isSavingDefaults).toBe(false);
    });

    it('sets isSavingDefaults during request', async () => {
      let capturedSaving;
      put_request.mockImplementation(() => {
        capturedSaving = store.isSavingDefaults;
        return Promise.resolve({ data: {} });
      });

      await store.saveDefaults(payload);

      expect(capturedSaving).toBe(true);
      expect(store.isSavingDefaults).toBe(false);
    });

    it('handles error with response.data.error', async () => {
      put_request.mockRejectedValue({
        response: { data: { error: 'El firmante seleccionado no es válido.' } },
      });

      const result = await store.saveDefaults({ ...payload, signer: 'nope' });

      expect(store.error).toBe('El firmante seleccionado no es válido.');
      expect(result).toEqual({
        success: false,
        error: 'El firmante seleccionado no es válido.',
      });
      expect(store.isSavingDefaults).toBe(false);
    });

    it('falls back to save_defaults_failed when no response error', async () => {
      put_request.mockRejectedValue(new Error('Network error'));

      const result = await store.saveDefaults(payload);

      expect(store.error).toBe('save_defaults_failed');
      expect(result).toEqual({ success: false, error: undefined });
    });
  });

  // ── fetchHistory ───────────────────────────────────────────────────────────

  describe('fetchHistory', () => {
    it('fetches page 1 and replaces history', async () => {
      const mockResults = [{ id: 1, subject: 'Email 1' }, { id: 2, subject: 'Email 2' }];
      get_request.mockResolvedValue({
        data: { results: mockResults, total: 10, page: 1, has_next: true },
      });

      const result = await store.fetchHistory(1);

      expect(get_request).toHaveBeenCalledWith('emails/history/?scope=all&page=1');
      expect(store.history).toEqual(mockResults);
      expect(result.success).toBe(true);
    });

    it('fetches page > 1 and appends to history', async () => {
      store.history = [{ id: 1, subject: 'Existing' }];
      const newResults = [{ id: 2, subject: 'New' }];
      get_request.mockResolvedValue({
        data: { results: newResults, total: 10, page: 2, has_next: false },
      });

      await store.fetchHistory(2);

      expect(store.history).toHaveLength(2);
      expect(store.history[0].subject).toBe('Existing');
      expect(store.history[1].subject).toBe('New');
    });

    it('updates historyPagination from response', async () => {
      get_request.mockResolvedValue({
        data: { results: [], total: 25, page: 3, has_next: true },
      });

      await store.fetchHistory(3);

      expect(store.historyPagination).toEqual({ total: 25, page: 3, has_next: true });
    });

    it('sets isLoadingHistory during request', async () => {
      let capturedLoading;
      get_request.mockImplementation(() => {
        capturedLoading = store.isLoadingHistory;
        return Promise.resolve({ data: { results: [], total: 0, page: 1, has_next: false } });
      });

      await store.fetchHistory();

      expect(capturedLoading).toBe(true);
      expect(store.isLoadingHistory).toBe(false);
    });

    it('handles API error and returns fallback data', async () => {
      get_request.mockRejectedValue(new Error('Server error'));

      const result = await store.fetchHistory();

      expect(store.error).toBe('fetch_history_failed');
      expect(result).toEqual({
        success: false,
        data: { results: [], total: 0, page: 1, has_next: false },
      });
      expect(store.isLoadingHistory).toBe(false);
    });

    it('defaults to page 1 when no argument provided', async () => {
      get_request.mockResolvedValue({
        data: { results: [], total: 0, page: 1, has_next: false },
      });

      await store.fetchHistory();

      expect(get_request).toHaveBeenCalledWith('emails/history/?scope=all&page=1');
    });

    it('sends the selected global-history filters', async () => {
      get_request.mockResolvedValue({
        data: { results: [], total: 0, page: 1, has_next: false },
      });

      await store.fetchHistory(1, {
        recipient: 'carlos',
        family: 'security',
        status: '',
        date_from: '2026-08-01',
      });

      expect(get_request).toHaveBeenCalledWith(
        'emails/history/?scope=all&page=1&recipient=carlos&family=security&date_from=2026-08-01',
      );
    });

    it('reuses filters when loading the next page', async () => {
      get_request.mockResolvedValue({
        data: { results: [], total: 0, page: 1, has_next: false },
      });
      await store.fetchHistory(1, { family: 'accounting' });
      get_request.mockResolvedValue({
        data: { results: [], total: 0, page: 2, has_next: false },
      });

      await store.fetchHistory(2);

      expect(get_request).toHaveBeenLastCalledWith(
        'emails/history/?scope=all&page=2&family=accounting',
      );
    });
  });

  describe('fetchEmailBody', () => {
    it('returns the retained outbound email body', async () => {
      const payload = { id: 12, text: 'Código 123456', html: '<p>123456</p>' };
      get_request.mockResolvedValue({ data: payload });

      const result = await store.fetchEmailBody(12);

      expect(get_request).toHaveBeenCalledWith('emails/history/12/body/');
      expect(result).toEqual({ success: true, data: payload });
    });

    it('returns the backend message when the body cannot load', async () => {
      get_request.mockRejectedValue({
        response: { data: { error: 'Este correo no tiene cuerpo.' } },
      });

      const result = await store.fetchEmailBody(12);

      expect(result).toEqual({
        success: false,
        message: 'Este correo no tiene cuerpo.',
      });
    });
  });

  describe('retryEmail', () => {
    it('posts an empty retry action for the original history record', async () => {
      // Fails if retrying sends a recipient override or targets another history record.
      const retried = { id: 23, retry_of: 12, status: 'sent' };
      create_request.mockResolvedValue({ data: retried });

      const result = await store.retryEmail(12);

      expect(create_request).toHaveBeenCalledWith('emails/history/12/retry/', {});
      expect(result).toEqual({ success: true, data: retried });
    });

    it('returns the server retry detail when reconstruction is unavailable', async () => {
      // Fails if the detail explaining why a historical email cannot be rebuilt is hidden.
      const failure = { detail: 'El pago original ya no está disponible.' };
      create_request.mockRejectedValue({ response: { data: failure } });

      const result = await store.retryEmail(12);

      expect(result).toEqual({
        success: false,
        data: failure,
        message: 'El pago original ya no está disponible.',
      });
    });
  });

  // ── sendEmail ──────────────────────────────────────────────────────────────

  describe('sendEmail', () => {
    const formData = { to: 'test@example.com', subject: 'Hello', body: 'World' };

    it('sends email with formData and returns success', async () => {
      const mockResponse = { id: 1, status: 'sent' };
      create_request.mockResolvedValue({ data: mockResponse });

      const result = await store.sendEmail(formData);

      expect(create_request).toHaveBeenCalledWith('emails/send/', formData);
      expect(result).toEqual({ success: true, data: mockResponse });
      expect(store.isSending).toBe(false);
    });

    it('sets isSending during request', async () => {
      let capturedSending;
      create_request.mockImplementation(() => {
        capturedSending = store.isSending;
        return Promise.resolve({ data: {} });
      });

      await store.sendEmail(formData);

      expect(capturedSending).toBe(true);
      expect(store.isSending).toBe(false);
    });

    it('handles error with response.data.error', async () => {
      create_request.mockRejectedValue({
        response: { data: { error: 'invalid_recipient' } },
      });

      const result = await store.sendEmail(formData);

      expect(store.error).toBe('invalid_recipient');
      expect(result).toEqual({ success: false, error: 'invalid_recipient' });
      expect(store.isSending).toBe(false);
    });

    it('falls back to send_failed when no response error', async () => {
      create_request.mockRejectedValue(new Error('Network error'));

      const result = await store.sendEmail(formData);

      expect(store.error).toBe('send_failed');
      expect(result).toEqual({ success: false, error: undefined });
    });
  });

  // ── previewEmail ────────────────────────────────────────────────────────────

  describe('previewEmail', () => {
    const payload = {
      subject: 'Hola',
      greeting: 'Hola Carlos',
      sections: [{ text: '**md**', markdown: true }],
      footer: 'Pie',
      attachment_names: ['doc.pdf'],
    };

    it('posts payload to emails/preview/ and returns html_preview', async () => {
      const mockResponse = { subject: 'Hola', html_preview: '<!doctype html>...' };
      create_request.mockResolvedValue({ data: mockResponse });

      const result = await store.previewEmail(payload);

      expect(create_request).toHaveBeenCalledWith('emails/preview/', payload);
      expect(result).toEqual({ success: true, data: mockResponse });
      expect(store.isLoadingPreview).toBe(false);
    });

    it('sets isLoadingPreview during request', async () => {
      let capturedLoading;
      create_request.mockImplementation(() => {
        capturedLoading = store.isLoadingPreview;
        return Promise.resolve({ data: {} });
      });

      await store.previewEmail(payload);

      expect(capturedLoading).toBe(true);
      expect(store.isLoadingPreview).toBe(false);
    });

    it('handles error and sets error state', async () => {
      create_request.mockRejectedValue({
        response: { data: { error: 'Las secciones deben ser un JSON válido.' } },
      });

      const result = await store.previewEmail(payload);

      expect(store.error).toBe('Las secciones deben ser un JSON válido.');
      expect(result).toEqual({
        success: false,
        error: 'Las secciones deben ser un JSON válido.',
      });
      expect(store.isLoadingPreview).toBe(false);
    });

    it('falls back to preview_failed when no response error', async () => {
      create_request.mockRejectedValue(new Error('Network error'));

      const result = await store.previewEmail(payload);

      expect(store.error).toBe('preview_failed');
      expect(result).toEqual({ success: false, error: undefined });
    });
  });

  describe('copy recipients', () => {
    const recipient = {
      id: 8,
      email: 'audit@example.com',
      is_active: true,
      families: ['proposals'],
    };

    it('loads copy configuration from the emails endpoint', async () => {
      const payload = {
        results: [recipient],
        families: [{ value: 'proposals', label: 'Propuestas' }],
        copy_mode: 'bcc',
      };
      get_request.mockResolvedValue({ data: payload });

      const result = await store.fetchCopyRecipients();

      expect(get_request).toHaveBeenCalledWith('emails/copy-recipients/');
      expect(store.copyRecipients).toEqual([recipient]);
      expect(store.copyFamilies).toEqual(payload.families);
      expect(result.success).toBe(true);
    });

    it('creates a copy recipient through the configuration endpoint', async () => {
      create_request.mockResolvedValue({ data: recipient });

      const result = await store.createCopyRecipient({
        email: recipient.email,
        families: recipient.families,
      });

      expect(create_request).toHaveBeenCalledWith(
        'emails/copy-recipients/',
        { email: recipient.email, families: recipient.families },
      );
      expect(store.copyRecipients).toEqual([recipient]);
      expect(result.success).toBe(true);
    });

    it('updates the configured family selection', async () => {
      store.copyRecipients = [recipient];
      const updated = { ...recipient, families: ['collections'] };
      patch_request.mockResolvedValue({ data: updated });

      const result = await store.updateCopyRecipient(8, {
        families: ['collections'],
      });

      expect(patch_request).toHaveBeenCalledWith(
        'emails/copy-recipients/8/',
        { families: ['collections'] },
      );
      expect(store.copyRecipients).toEqual([updated]);
      expect(result.success).toBe(true);
    });

    it('deletes a configured copy recipient', async () => {
      store.copyRecipients = [recipient];
      delete_request.mockResolvedValue({ data: null });

      const result = await store.deleteCopyRecipient(8);

      expect(delete_request).toHaveBeenCalledWith('emails/copy-recipients/8/');
      expect(store.copyRecipients).toEqual([]);
      expect(result.success).toBe(true);
    });

    it('returns validation details from recipient creation', async () => {
      create_request.mockRejectedValue({
        response: { data: { email: ['Ese correo ya está en la lista.'] } },
      });

      const result = await store.createCopyRecipient({ email: recipient.email });

      expect(result).toEqual({
        success: false,
        error: { email: ['Ese correo ya está en la lista.'] },
      });
    });
  });
});
