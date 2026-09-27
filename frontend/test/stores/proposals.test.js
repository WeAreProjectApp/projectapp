/**
 * Tests for the proposals store.
 *
 * Covers: fetchPublicProposal, fetchProposals, fetchProposal,
 * createProposal, createProposalFromJSON, updateProposal, deleteProposal,
 * duplicateProposal, sendProposal, resendProposal, toggleProposalActive,
 * updateSection, reorderSections, respondToProposal, commentOnProposal,
 * trackSectionViews, fetchProposalAnalytics, fetchProposalDashboard,
 * scheduleFollowup, shareProposal, fetchSharedProposal, checkAdminAuth,
 * fetchProposalDefaults, saveProposalDefaults, resetProposalDefaults,
 * fetchEmailTemplates, fetchEmailTemplateDetail, saveEmailTemplate,
 * previewEmailTemplate, resetEmailTemplate, fetchEmailDeliverability,
 * fetchDefaultContractTemplate, fetchCompanySettings,
 * uploadProposalDocument, sendDocumentsToClient, deleteProposalDocument,
 * getters: getProposalById, enabledSections, totalSections.
 */
import { setActivePinia, createPinia } from 'pinia';
import { useProposalStore } from '../../stores/proposals';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  put_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const {
  get_request, create_request, put_request, patch_request, delete_request,
} = require('../../stores/services/request_http');

describe('useProposalStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useProposalStore();
    jest.clearAllMocks();
    jest.restoreAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  describe('initial state', () => {
    it('has empty proposals array', () => {
      expect(store.proposals).toEqual([]);
    });

    it('has null currentProposal', () => {
      expect(store.currentProposal).toBeNull();
    });

    it('has isLoading false', () => {
      expect(store.isLoading).toBe(false);
    });

    it('has isUpdating false', () => {
      expect(store.isUpdating).toBe(false);
    });

    it('has error null', () => {
      expect(store.error).toBeNull();
    });
  });

  describe('getters', () => {
    it('getProposalById finds proposal', () => {
      store.proposals = [{ id: 1, title: 'A' }, { id: 2, title: 'B' }];
      expect(store.getProposalById(2)).toEqual({ id: 2, title: 'B' });
    });

    it('getProposalById returns undefined for missing id', () => {
      store.proposals = [{ id: 1 }];
      expect(store.getProposalById(99)).toBeUndefined();
    });

    it('enabledSections returns sorted enabled sections', () => {
      store.currentProposal = {
        sections: [
          { id: 1, is_enabled: true, order: 2 },
          { id: 2, is_enabled: false, order: 0 },
          { id: 3, is_enabled: true, order: 1 },
        ],
      };
      const result = store.enabledSections;
      expect(result).toHaveLength(2);
      expect(result[0].order).toBe(1);
      expect(result[1].order).toBe(2);
    });

    it('enabledSections returns empty array when no proposal', () => {
      expect(store.enabledSections).toEqual([]);
    });

    it('enabledSections returns empty array when sections is null', () => {
      store.currentProposal = { sections: null };
      expect(store.enabledSections).toEqual([]);
    });

    it('enabledSections returns empty array when sections is undefined', () => {
      store.currentProposal = {};
      expect(store.enabledSections).toEqual([]);
    });

    it('totalSections returns 0 when sections is null', () => {
      store.currentProposal = { sections: null };
      expect(store.totalSections).toBe(0);
    });

    it('totalSections returns 0 when sections is undefined', () => {
      store.currentProposal = {};
      expect(store.totalSections).toBe(0);
    });

    it('totalSections returns 0 when no sections are enabled', () => {
      store.currentProposal = {
        sections: [{ id: 1, is_enabled: false }],
      };
      expect(store.totalSections).toBe(0);
    });

    it('totalSections counts only enabled sections', () => {
      store.currentProposal = {
        sections: [
          { id: 1, is_enabled: true },
          { id: 2, is_enabled: false },
          { id: 3, is_enabled: true },
        ],
      };
      expect(store.totalSections).toBe(2);
    });
  });

  describe('fetchPublicProposal', () => {
    it('fetches proposal by UUID via the UUID endpoint', async () => {
      const realUuid = 'a1b2c3d4-e5f6-7890-abcd-1234567890ab';
      const data = { id: 1, uuid: realUuid, slug: 'maria-lopez', title: 'Test' };
      get_request.mockResolvedValue({ data });

      const result = await store.fetchPublicProposal(realUuid);

      expect(get_request).toHaveBeenCalledWith(`proposals/${realUuid}/`);
      expect(store.currentProposal).toEqual(data);
      expect(result.success).toBe(true);
    });

    it('fetches proposal by slug via the by-slug endpoint', async () => {
      const data = { id: 2, uuid: 'a1b2c3d4-e5f6-7890-abcd-1234567890ab', slug: 'maria-lopez', title: 'Test' };
      get_request.mockResolvedValue({ data });

      await store.fetchPublicProposal('maria-lopez');

      expect(get_request).toHaveBeenCalledWith('proposals/by-slug/maria-lopez/');
    });

    it('returns expired flag when response contains expired_meta', async () => {
      const data = {
        id: 1, uuid: 'exp-uuid', title: 'Expired',
        expired_meta: { seller_name: 'Seller', whatsapp_url: 'https://wa.me/123' },
      };
      get_request.mockResolvedValue({ data });

      const result = await store.fetchPublicProposal('exp-uuid');

      expect(result.success).toBe(true);
      expect(result.expired).toBe(true);
      expect(result.data).toEqual(data);
      expect(store.currentProposal).toEqual(data);
    });

    it('sets expired error on 410', async () => {
      get_request.mockRejectedValue({ response: { status: 410 } });

      const result = await store.fetchPublicProposal('expired-uuid');

      expect(result.success).toBe(false);
      expect(store.error).toBe('expired');
    });

    it('stores partial data from 410 response for ProposalExpired', async () => {
      get_request.mockRejectedValue({
        response: {
          status: 410,
          data: {
            client_name: 'Acme Corp',
            title: 'Expired Proposal',
            uuid: 'exp-uuid-123',
            expired_at: '2026-03-01T00:00:00Z',
          },
        },
      });

      await store.fetchPublicProposal('exp-uuid-123');

      expect(store.error).toBe('expired');
      expect(store.currentProposal).toEqual({
        client_name: 'Acme Corp',
        title: 'Expired Proposal',
        uuid: 'exp-uuid-123',
        expired_at: '2026-03-01T00:00:00Z',
        seller_name: '',
        whatsapp_url: '',
        total_investment: '',
        currency: '',
      });
    });

    it('uses fallback values when 410 partial data has missing fields', async () => {
      get_request.mockRejectedValue({
        response: {
          status: 410,
          data: {},
        },
      });

      await store.fetchPublicProposal('fallback-uuid');

      expect(store.error).toBe('expired');
      expect(store.currentProposal).toEqual({
        client_name: '',
        title: '',
        uuid: 'fallback-uuid',
        expired_at: null,
        seller_name: '',
        whatsapp_url: '',
        total_investment: '',
        currency: '',
      });
    });

    it('sets not_found error on 404', async () => {
      get_request.mockRejectedValue({ response: { status: 404 } });

      const _result = await store.fetchPublicProposal('missing-uuid');

      expect(store.error).toBe('not_found');
    });

    it('sets unknown error on other status', async () => {
      get_request.mockRejectedValue({ response: { status: 500 } });

      const _result = await store.fetchPublicProposal('error-uuid');

      expect(store.error).toBe('unknown');
    });

    it('sets unknown error when error has no response property', async () => {
      get_request.mockRejectedValue(new Error('network'));

      const result = await store.fetchPublicProposal('uuid');

      expect(result.success).toBe(false);
      expect(store.error).toBe('unknown');
      expect(result.status).toBeUndefined();
    });

    it('resets isLoading after request', async () => {
      get_request.mockResolvedValue({ data: {} });

      await store.fetchPublicProposal('uuid');

      expect(store.isLoading).toBe(false);
    });
  });

  describe('fetchContractTerms', () => {
    it('returns the masked contract payload', async () => {
      const data = { clauses: [{ id: 'clause-01', title: 'Objeto' }] };
      get_request.mockResolvedValue({ data });

      const result = await store.fetchContractTerms('proposal-uuid');

      expect(get_request).toHaveBeenCalledWith(
        'proposals/proposal-uuid/contract-terms/',
      );
      expect(result).toEqual({ success: true, data });
    });

    it('returns the API error without mutating proposal state', async () => {
      store.currentProposal = { uuid: 'proposal-uuid' };
      get_request.mockRejectedValue({
        response: { status: 503, data: { error: 'No disponible' } },
      });

      const result = await store.fetchContractTerms('proposal-uuid');

      expect(result).toEqual({
        success: false,
        status: 503,
        error: 'No disponible',
      });
      expect(store.currentProposal).toEqual({ uuid: 'proposal-uuid' });
    });
  });

  describe('fetchProposals', () => {
    it('fetches all proposals without filter', async () => {
      get_request.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }] });

      const result = await store.fetchProposals();

      expect(get_request).toHaveBeenCalledWith('proposals/');
      expect(store.proposals).toHaveLength(2);
      expect(result.success).toBe(true);
    });

    it('fetches proposals with status filter', async () => {
      get_request.mockResolvedValue({ data: [{ id: 1, status: 'sent' }] });

      await store.fetchProposals('sent');

      expect(get_request).toHaveBeenCalledWith('proposals/?status=sent');
    });

    it('handles error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchProposals();

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_failed');
    });
  });

  describe('fetchProposal', () => {
    it('fetches single proposal by id', async () => {
      const data = { id: 5, title: 'Test', sections: [] };
      get_request.mockResolvedValue({ data });

      const result = await store.fetchProposal(5);

      expect(get_request).toHaveBeenCalledWith('proposals/5/detail/');
      expect(store.currentProposal).toEqual(data);
      expect(result.success).toBe(true);
    });

    it('handles error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const _result = await store.fetchProposal(99);

      expect(store.error).toBe('fetch_failed');
    });
  });

  describe('createProposal', () => {
    it('creates proposal and sets currentProposal', async () => {
      const newData = { id: 10, title: 'New', sections: [] };
      create_request.mockResolvedValue({ data: newData });

      const payload = { title: 'New', client_name: 'Client' };
      const result = await store.createProposal(payload);

      expect(create_request).toHaveBeenCalledWith('proposals/create/', payload);
      expect(store.currentProposal).toEqual(newData);
      expect(result.success).toBe(true);
    });

    it('handles validation error', async () => {
      create_request.mockRejectedValue({
        response: { data: { title: ['Required'] } },
      });

      const result = await store.createProposal({});

      expect(result.success).toBe(false);
      expect(store.error).toBe('create_failed');
    });

    it('handles error without response property', async () => {
      create_request.mockRejectedValue(new Error('network'));

      const result = await store.createProposal({});

      expect(result.success).toBe(false);
      expect(result.errors).toBeUndefined();
    });
  });

  describe('createProposalFromJSON', () => {
    it('calls create-from-json endpoint with full payload', async () => {
      const responseData = { id: 20, title: 'From JSON', sections: [] };
      create_request.mockResolvedValue({ data: responseData });

      const jsonData = {
        title: 'From JSON',
        client_name: 'JSON Client',
        sections: { general: { clientName: 'JSON Client' } },
      };
      const result = await store.createProposalFromJSON(jsonData);

      expect(create_request).toHaveBeenCalledWith('proposals/create-from-json/', jsonData);
      expect(store.currentProposal).toEqual(responseData);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(responseData);
    });

    it('sets isUpdating true during request and false after', async () => {
      let capturedUpdating = false;
      create_request.mockImplementation(() => {
        capturedUpdating = store.isUpdating;
        return Promise.resolve({ data: { id: 21, sections: [] } });
      });

      await store.createProposalFromJSON({ title: 'X', sections: { general: { clientName: 'X' } } });

      expect(capturedUpdating).toBe(true);
      expect(store.isUpdating).toBe(false);
    });

    it('returns failure and sets error on network error', async () => {
      create_request.mockRejectedValue(new Error('network error'));

      const result = await store.createProposalFromJSON({ sections: {} });

      expect(result.success).toBe(false);
      expect(store.error).toBe('create_from_json_failed');
    });

    it('returns validation errors from response data on 400', async () => {
      create_request.mockRejectedValue({
        response: { data: { sections: ['general key required'] } },
      });

      const result = await store.createProposalFromJSON({});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ sections: ['general key required'] });
    });
  });

  describe('exportProposalJSON', () => {
    it('fetches export JSON and returns data', async () => {
      const exportData = { general: { clientName: 'Test' }, _meta: { title: 'Prop' } };
      get_request.mockResolvedValue({ data: exportData });

      const result = await store.exportProposalJSON(42);

      expect(get_request).toHaveBeenCalledWith('proposals/42/export-json/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(exportData);
    });

    it('returns failure on error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.exportProposalJSON(42);

      expect(result.success).toBe(false);
    });
  });

  describe('updateProposalFromJSON', () => {
    it('calls update-from-json endpoint and sets currentProposal', async () => {
      const responseData = { id: 1, title: 'Updated', sections: [] };
      put_request.mockResolvedValue({ data: responseData });

      const jsonData = {
        title: 'Updated',
        client_name: 'Client',
        sections: { general: { clientName: 'Client' } },
      };
      const result = await store.updateProposalFromJSON(1, jsonData);

      expect(put_request).toHaveBeenCalledWith('proposals/1/update-from-json/', jsonData);
      expect(store.currentProposal).toEqual(responseData);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(responseData);
    });

    it('sets isUpdating true during request and false after', async () => {
      let capturedUpdating = false;
      put_request.mockImplementation(() => {
        capturedUpdating = store.isUpdating;
        return Promise.resolve({ data: { id: 1, sections: [] } });
      });

      await store.updateProposalFromJSON(1, { title: 'X', sections: { general: { clientName: 'X' } } });

      expect(capturedUpdating).toBe(true);
      expect(store.isUpdating).toBe(false);
    });

    it('returns failure and sets error on network error', async () => {
      put_request.mockRejectedValue(new Error('network error'));

      const result = await store.updateProposalFromJSON(1, { sections: {} });

      expect(result.success).toBe(false);
      expect(store.error).toBe('update_from_json_failed');
    });

    it('returns validation errors from response data on 400', async () => {
      put_request.mockRejectedValue({
        response: { data: { sections: ['general key required'] } },
      });

      const result = await store.updateProposalFromJSON(1, {});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ sections: ['general key required'] });
    });
  });

  describe('updateProposal', () => {
    it('updates proposal metadata', async () => {
      const updated = { id: 1, title: 'Updated' };
      patch_request.mockResolvedValue({ data: updated });

      const result = await store.updateProposal(1, { title: 'Updated' });

      expect(patch_request).toHaveBeenCalledWith('proposals/1/update/', { title: 'Updated' });
      expect(store.currentProposal).toEqual(updated);
      expect(result.success).toBe(true);
    });

    it('handles error', async () => {
      patch_request.mockRejectedValue(new Error('fail'));

      const _result = await store.updateProposal(1, {});

      expect(store.error).toBe('update_failed');
    });

    it('handles error with response data', async () => {
      patch_request.mockRejectedValue({
        response: { data: { title: ['Required'] } },
      });

      const result = await store.updateProposal(1, {});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ title: ['Required'] });
    });
  });

  describe('deleteProposal', () => {
    it('removes proposal from list', async () => {
      store.proposals = [{ id: 1 }, { id: 2 }];
      delete_request.mockResolvedValue({});

      const result = await store.deleteProposal(1);

      expect(delete_request).toHaveBeenCalledWith('proposals/1/delete/');
      expect(store.proposals).toEqual([{ id: 2 }]);
      expect(result.success).toBe(true);
    });

    it('clears currentProposal if matching', async () => {
      store.currentProposal = { id: 1 };
      store.proposals = [{ id: 1 }];
      delete_request.mockResolvedValue({});

      await store.deleteProposal(1);

      expect(store.currentProposal).toBeNull();
    });

    it('keeps null currentProposal unchanged on delete', async () => {
      store.currentProposal = null;
      store.proposals = [{ id: 1 }];
      delete_request.mockResolvedValue({});

      await store.deleteProposal(1);

      expect(store.currentProposal).toBeNull();
      expect(store.proposals).toEqual([]);
    });

    it('handles error', async () => {
      delete_request.mockRejectedValue(new Error('fail'));

      const _result = await store.deleteProposal(1);

      expect(store.error).toBe('delete_failed');
    });

    it('propagates backend error message and keeps the proposal', async () => {
      store.proposals = [{ id: 1 }, { id: 2 }];
      delete_request.mockRejectedValue({
        response: { status: 409, data: { error: 'Vinculada a un proyecto' } },
      });

      const result = await store.deleteProposal(1);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Vinculada a un proyecto');
      // List untouched because the delete failed.
      expect(store.proposals).toEqual([{ id: 1 }, { id: 2 }]);
    });
  });

  describe('sendProposal', () => {
    it('sends proposal and updates currentProposal', async () => {
      const sentData = { id: 1, status: 'sent', sent_at: '2026-03-04' };
      create_request.mockResolvedValue({ data: sentData });

      const result = await store.sendProposal(1);

      expect(create_request).toHaveBeenCalledWith('proposals/1/send/', {});
      expect(store.currentProposal).toEqual(sentData);
      expect(result.success).toBe(true);
    });

    it('handles send error', async () => {
      create_request.mockRejectedValue({
        response: { data: { error: 'Missing email' } },
      });

      const result = await store.sendProposal(1);

      expect(result.success).toBe(false);
      expect(store.error).toBe('send_failed');
    });

    it('handles send error without response property', async () => {
      create_request.mockRejectedValue(new Error('network'));

      const result = await store.sendProposal(1);

      expect(result.success).toBe(false);
      expect(result.errors).toBeUndefined();
    });

    it('propagates email_delivery from backend response', async () => {
      const sentData = {
        id: 1,
        status: 'sent',
        email_delivery: {
          ok: false,
          reason: 'placeholder_email',
          detail: 'El correo del cliente está vacío.',
        },
      };
      create_request.mockResolvedValue({ data: sentData });

      const result = await store.sendProposal(1);

      expect(result.success).toBe(true);
      expect(result.email_delivery).toEqual(sentData.email_delivery);
    });

    it('email_delivery is null when backend omits the field', async () => {
      create_request.mockResolvedValue({ data: { id: 1, status: 'sent' } });

      const result = await store.sendProposal(1);

      expect(result.success).toBe(true);
      expect(result.email_delivery).toBeNull();
    });
  });

  describe('updateSection', () => {
    const wrap = (section, extras = {}) => ({
      data: { section, proposal_totals: { total_investment: '0', effective_total_investment: '0' }, ...extras },
    });

    it('updates section content_json and syncs currentProposal', async () => {
      store.currentProposal = {
        sections: [
          { id: 10, section_type: 'greeting', content_json: { clientName: 'Old' } },
          { id: 11, section_type: 'timeline', content_json: {} },
        ],
      };
      const updatedSection = {
        id: 10,
        section_type: 'greeting',
        content_json: { clientName: 'New Client' },
      };
      patch_request.mockResolvedValue(wrap(updatedSection));

      const result = await store.updateSection(10, {
        content_json: { clientName: 'New Client' },
      });

      expect(patch_request).toHaveBeenCalledWith(
        'proposals/sections/10/update/',
        { content_json: { clientName: 'New Client' } },
      );
      expect(result.success).toBe(true);
      expect(store.currentProposal.sections[0]).toEqual(updatedSection);
    });

    it('updates section with complex content_json (executive_summary)', async () => {
      store.currentProposal = {
        sections: [{ id: 20, section_type: 'executive_summary', content_json: {} }],
      };
      const complexContent = {
        index: '1',
        title: 'Executive Summary',
        paragraphs: ['First paragraph.', 'Second paragraph.'],
        highlightsTitle: 'Includes',
        highlights: ['Custom design', 'Responsive development', 'SEO optimization'],
      };
      const updatedSection = { id: 20, section_type: 'executive_summary', content_json: complexContent };
      patch_request.mockResolvedValue(wrap(updatedSection));

      const result = await store.updateSection(20, { content_json: complexContent });

      expect(result.success).toBe(true);
      expect(store.currentProposal.sections[0].content_json.paragraphs).toHaveLength(2);
      expect(store.currentProposal.sections[0].content_json.highlights).toHaveLength(3);
    });

    it('updates section with functional_requirements content_json', async () => {
      store.currentProposal = {
        sections: [{ id: 30, section_type: 'functional_requirements', content_json: {} }],
      };
      const reqContent = {
        index: '7',
        title: 'Functional Requirements',
        intro: 'Project requirements.',
        groups: [
          {
            id: 'views',
            icon: '🖥️',
            title: 'Views',
            description: 'Website screens.',
            items: [
              { icon: '🏠', name: 'Home', description: 'Main landing.' },
              { icon: '📧', name: 'Contact', description: 'Contact form.' },
            ],
          },
        ],
        additionalModules: [],
      };
      patch_request.mockResolvedValue(wrap(
        { id: 30, section_type: 'functional_requirements', content_json: reqContent },
      ));

      const result = await store.updateSection(30, { content_json: reqContent });

      expect(result.success).toBe(true);
      expect(store.currentProposal.sections[0].content_json.groups[0].items).toHaveLength(2);
    });

    it('handles section update error', async () => {
      patch_request.mockRejectedValue(new Error('fail'));

      const _result = await store.updateSection(10, {});

      expect(store.error).toBe('update_section_failed');
    });

    it('handles section update error with response data', async () => {
      patch_request.mockRejectedValue({
        response: { data: { content_json: ['Invalid'] } },
      });

      const result = await store.updateSection(10, {});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ content_json: ['Invalid'] });
    });

    it('skips local sync when currentProposal is null', async () => {
      store.currentProposal = null;
      patch_request.mockResolvedValue(wrap({ id: 10 }));

      const result = await store.updateSection(10, { title: 'New' });

      expect(result.success).toBe(true);
    });

    it('skips local sync when section id not found', async () => {
      store.currentProposal = {
        sections: [{ id: 99, section_type: 'other' }],
      };
      patch_request.mockResolvedValue(wrap({ id: 10 }));

      const result = await store.updateSection(10, { title: 'New' });

      expect(result.success).toBe(true);
      expect(store.currentProposal.sections[0].id).toBe(99);
    });

    it('updates proposal totals from wrapped response', async () => {
      store.currentProposal = {
        total_investment: '1000000',
        effective_total_investment: '1250000',
        sections: [
          { id: 30, section_type: 'functional_requirements', content_json: {} },
        ],
      };
      const updatedSection = {
        id: 30,
        section_type: 'functional_requirements',
        content_json: { groups: [] },
      };
      patch_request.mockResolvedValue({
        data: {
          section: updatedSection,
          proposal_totals: {
            total_investment: '1000000',
            effective_total_investment: '1000000.00',
          },
        },
      });

      const result = await store.updateSection(30, { content_json: { groups: [] } });

      expect(result.success).toBe(true);
      expect(result.data).toEqual(updatedSection);
      expect(store.currentProposal.sections[0]).toEqual(updatedSection);
      expect(store.currentProposal.effective_total_investment).toBe('1000000.00');
      expect(store.currentProposal.total_investment).toBe('1000000');
    });

    it('replaces auto-resynced investment_section when returned', async () => {
      store.currentProposal = {
        total_investment: '1000000',
        effective_total_investment: '1250000',
        sections: [
          { id: 30, section_type: 'functional_requirements', content_json: {} },
          { id: 31, section_type: 'investment', content_json: { totalInvestment: '$old' } },
        ],
      };
      const updatedFr = { id: 30, section_type: 'functional_requirements', content_json: {} };
      const resyncedInvestment = {
        id: 31,
        section_type: 'investment',
        content_json: { totalInvestment: '$1.000.000', paymentOptions: [] },
      };
      patch_request.mockResolvedValue({
        data: {
          section: updatedFr,
          proposal_totals: {
            total_investment: '1000000',
            effective_total_investment: '1000000.00',
          },
          investment_section: resyncedInvestment,
        },
      });

      await store.updateSection(30, { content_json: {} });

      expect(store.currentProposal.sections[1]).toEqual(resyncedInvestment);
      expect(store.currentProposal.sections[1].content_json.totalInvestment).toBe('$1.000.000');
    });
  });

  describe('reorderSections', () => {
    it('reorders sections and updates local order', async () => {
      store.currentProposal = {
        sections: [
          { id: 1, order: 0 },
          { id: 2, order: 1 },
        ],
      };
      create_request.mockResolvedValue({});

      const newOrder = [{ id: 1, order: 1 }, { id: 2, order: 0 }];
      const result = await store.reorderSections(99, newOrder);

      expect(create_request).toHaveBeenCalledWith(
        'proposals/99/reorder-sections/',
        { sections: newOrder },
      );
      expect(result.success).toBe(true);
      expect(store.currentProposal.sections.find(s => s.id === 1).order).toBe(1);
      expect(store.currentProposal.sections.find(s => s.id === 2).order).toBe(0);
    });

    it('handles reorder error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.reorderSections(1, []);

      expect(result.success).toBe(false);
    });

    it('skips local order update when currentProposal is null', async () => {
      store.currentProposal = null;
      create_request.mockResolvedValue({});

      const result = await store.reorderSections(1, [{ id: 1, order: 0 }]);

      expect(result.success).toBe(true);
    });
  });

  describe('createSection', () => {
    it('creates a section and appends it with updated totals', async () => {
      store.currentProposal = {
        id: 99,
        sections: [{ id: 1, section_type: 'greeting', order: 0 }],
        total_investment: '100',
        effective_total_investment: '100',
      };
      create_request.mockResolvedValue({
        data: {
          section: { id: 7, section_type: 'timeline', order: 1 },
          proposal_totals: { total_investment: '100', effective_total_investment: '150' },
        },
      });

      const result = await store.createSection(99, 'timeline');

      expect(create_request).toHaveBeenCalledWith(
        'proposals/99/sections/create/',
        { section_type: 'timeline' },
      );
      expect(result.success).toBe(true);
      expect(result.data.id).toBe(7);
      expect(store.currentProposal.sections.map((s) => s.id)).toEqual([1, 7]);
      expect(store.currentProposal.effective_total_investment).toBe('150');
    });

    it('propagates the normalized error on failure', async () => {
      create_request.mockRejectedValue({
        response: {
          status: 400,
          data: { error: 'La propuesta ya tiene una sección de este tipo.', code: 'section_already_exists' },
        },
      });

      const result = await store.createSection(99, 'greeting');

      expect(result.success).toBe(false);
      expect(result.code).toBe('section_already_exists');
      expect(result.message).toBe('La propuesta ya tiene una sección de este tipo.');
    });
  });

  describe('deleteSection', () => {
    it('deletes a section and removes it locally with updated totals', async () => {
      store.currentProposal = {
        id: 99,
        sections: [
          { id: 1, section_type: 'greeting', order: 0 },
          { id: 7, section_type: 'timeline', order: 1 },
        ],
        total_investment: '100',
        effective_total_investment: '150',
      };
      delete_request.mockResolvedValue({
        data: {
          deleted: true,
          section_type: 'timeline',
          proposal_totals: { total_investment: '100', effective_total_investment: '100' },
        },
      });

      const result = await store.deleteSection(7);

      expect(delete_request).toHaveBeenCalledWith('proposals/sections/7/delete/');
      expect(result.success).toBe(true);
      expect(store.currentProposal.sections.map((s) => s.id)).toEqual([1]);
      expect(store.currentProposal.effective_total_investment).toBe('100');
    });

    it('propagates the guard error for confirmed functional requirements', async () => {
      delete_request.mockRejectedValue({
        response: {
          status: 400,
          data: { error: 'No se puede eliminar.', code: 'fr_has_confirmed_selection', hint: 'Desactiva la sección.' },
        },
      });

      const result = await store.deleteSection(3);

      expect(result.success).toBe(false);
      expect(result.code).toBe('fr_has_confirmed_selection');
      expect(result.hint).toBe('Desactiva la sección.');
    });
  });

  describe('respondToProposal', () => {
    it('accepts proposal and updates currentProposal status', async () => {
      store.currentProposal = { uuid: 'abc', status: 'sent' };
      create_request.mockResolvedValue({ data: { status: 'accepted' } });

      const result = await store.respondToProposal('abc', 'accepted');

      expect(create_request).toHaveBeenCalledWith('proposals/abc/respond/', { action: 'accepted' });
      expect(result.success).toBe(true);
      expect(store.currentProposal.status).toBe('accepted');
    });

    it('rejects proposal', async () => {
      store.currentProposal = { uuid: 'abc', status: 'sent' };
      create_request.mockResolvedValue({ data: { status: 'rejected' } });

      const _result = await store.respondToProposal('abc', 'rejected');

      expect(store.currentProposal.status).toBe('rejected');
    });

    it('handles error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.respondToProposal('abc', 'accepted');

      expect(result.success).toBe(false);
    });

    it('does not update status when currentProposal is null', async () => {
      store.currentProposal = null;
      create_request.mockResolvedValue({ data: { status: 'accepted' } });

      const result = await store.respondToProposal('abc', 'accepted');

      expect(result.success).toBe(true);
      expect(store.currentProposal).toBeNull();
    });

    it('does not update status when uuid does not match', async () => {
      store.currentProposal = { uuid: 'xyz', status: 'sent' };
      create_request.mockResolvedValue({ data: { status: 'accepted' } });

      const result = await store.respondToProposal('abc', 'accepted');

      expect(result.success).toBe(true);
      expect(store.currentProposal.status).toBe('sent');
    });
  });

  describe('checkAdminAuth', () => {
    it('returns success with user data', async () => {
      get_request.mockResolvedValue({ data: { user: { username: 'admin', is_staff: true } } });

      const result = await store.checkAdminAuth();

      expect(get_request).toHaveBeenCalledWith('auth/check/');
      expect(result.success).toBe(true);
      expect(result.user.is_staff).toBe(true);
    });

    it('returns failure on error', async () => {
      get_request.mockRejectedValue(new Error('unauthorized'));

      const result = await store.checkAdminAuth();

      expect(result.success).toBe(false);
    });

    it('exposes HTTP status when server responded', async () => {
      get_request.mockRejectedValue({ response: { status: 403 } });

      const result = await store.checkAdminAuth();

      expect(result).toEqual({ success: false, status: 403 });
    });

    it('returns null status on network error', async () => {
      get_request.mockRejectedValue(new Error('ECONNREFUSED'));

      const result = await store.checkAdminAuth();

      expect(result).toEqual({ success: false, status: null });
    });
  });

  describe('duplicateProposal', () => {
    it('duplicates proposal and prepends to list', async () => {
      store.proposals = [{ id: 1, title: 'Original' }];
      const duplicated = { id: 2, title: 'Original (copy)' };
      create_request.mockResolvedValue({ data: duplicated });

      const result = await store.duplicateProposal(1);

      expect(create_request).toHaveBeenCalledWith('proposals/1/duplicate/', {});
      expect(result.success).toBe(true);
      expect(result.data).toEqual(duplicated);
      expect(store.proposals[0]).toEqual(duplicated);
    });

    it('sets error on failure', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.duplicateProposal(1);

      expect(result.success).toBe(false);
      expect(store.error).toBe('duplicate_failed');
    });
  });

  describe('resendProposal', () => {
    it('resends proposal and updates currentProposal', async () => {
      const resent = { id: 1, status: 'sent', sent_at: '2026-03-07' };
      create_request.mockResolvedValue({ data: resent });

      const result = await store.resendProposal(1);

      expect(create_request).toHaveBeenCalledWith('proposals/1/resend/', {});
      expect(result.success).toBe(true);
      expect(store.currentProposal).toEqual(resent);
    });

    it('posts the edited personalized message when provided', async () => {
      const message = 'Mensaje actualizado para el cliente.';
      create_request.mockResolvedValue({
        data: { id: 1, status: 'sent', email_intro: message },
      });

      const result = await store.resendProposal(1, message);

      expect(create_request).toHaveBeenCalledWith(
        'proposals/1/resend/',
        { email_intro: message },
      );
      expect(result.success).toBe(true);
    });

    it('sets error on failure', async () => {
      create_request.mockRejectedValue({ response: { data: { error: 'not sent' } } });

      const result = await store.resendProposal(1);

      expect(result.success).toBe(false);
      expect(store.error).toBe('resend_failed');
      expect(result.errors).toEqual({ error: 'not sent' });
    });
  });

  describe('fetchProposalsByClient', () => {
    it('returns the list when the request succeeds', async () => {
      const list = [{ id: 1, client: { id: 7 } }, { id: 2, client: { id: 7 } }];
      get_request.mockResolvedValue({ data: list });

      const result = await store.fetchProposalsByClient(7);

      expect(get_request).toHaveBeenCalledWith('proposals/?client_id=7');
      expect(result).toEqual({ success: true, data: list });
    });

    it('returns success=false with empty data on failure', async () => {
      get_request.mockRejectedValue(new Error('boom'));

      const result = await store.fetchProposalsByClient(7);

      expect(result).toEqual({ success: false, data: [] });
    });
  });

  describe('sendMultiProposal', () => {
    it('posts proposal_ids and propagates email_delivery', async () => {
      const responseData = {
        id: 12,
        status: 'sent',
        email_delivery: { ok: true, reason: 'sent', detail: 'group=abc' },
        transitions: { 12: 'sent', 18: 'resent' },
      };
      create_request.mockResolvedValue({ data: responseData });

      const result = await store.sendMultiProposal(12, [12, 18]);

      expect(create_request).toHaveBeenCalledWith(
        'proposals/12/send-multi/',
        { proposal_ids: [12, 18] },
      );
      expect(result.success).toBe(true);
      expect(result.email_delivery).toEqual(responseData.email_delivery);
      expect(store.currentProposal).toEqual(responseData);
    });

    it('returns error and surfaces backend payload on failure', async () => {
      create_request.mockRejectedValue({
        response: {
          data: { error: 'Algunas propuestas no pertenecen al mismo cliente.' },
        },
      });

      const result = await store.sendMultiProposal(12, [12, 99]);

      expect(result.success).toBe(false);
      expect(store.error).toBe('send_multi_failed');
      expect(result.errors).toEqual({
        error: 'Algunas propuestas no pertenecen al mismo cliente.',
      });
    });

    it('email_delivery is null when backend omits the field', async () => {
      create_request.mockResolvedValue({ data: { id: 12, status: 'sent' } });

      const result = await store.sendMultiProposal(12, [12, 18]);

      expect(result.success).toBe(true);
      expect(result.email_delivery).toBeNull();
    });
  });

  describe('toggleProposalActive', () => {
    it('toggles active and updates currentProposal when matching', async () => {
      store.currentProposal = { id: 5, is_active: true };
      store.proposals = [{ id: 5, is_active: true }];
      const toggled = { id: 5, is_active: false };
      create_request.mockResolvedValue({ data: toggled });

      const result = await store.toggleProposalActive(5);

      expect(create_request).toHaveBeenCalledWith('proposals/5/toggle-active/', {});
      expect(result.success).toBe(true);
      expect(store.currentProposal).toEqual(toggled);
      expect(store.proposals[0].is_active).toBe(false);
    });

    it('updates proposals list even when currentProposal differs', async () => {
      store.currentProposal = { id: 99 };
      store.proposals = [{ id: 5, is_active: true }];
      create_request.mockResolvedValue({ data: { id: 5, is_active: false } });

      const result = await store.toggleProposalActive(5);

      expect(result.success).toBe(true);
      expect(store.proposals[0].is_active).toBe(false);
      expect(store.currentProposal.id).toBe(99);
    });

    it('sets error on failure', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.toggleProposalActive(5);

      expect(result.success).toBe(false);
      expect(store.error).toBe('toggle_active_failed');
    });
  });

  describe('commentOnProposal', () => {
    it('submits comment and returns success', async () => {
      const responseData = { status: 'comment_received' };
      create_request.mockResolvedValue({ data: responseData });

      const result = await store.commentOnProposal('uuid-1', 'Need lower price');

      expect(create_request).toHaveBeenCalledWith(
        'proposals/uuid-1/comment/',
        { comment: 'Need lower price' },
      );
      expect(result.success).toBe(true);
      expect(result.data).toEqual(responseData);
    });

    it('returns failure on error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.commentOnProposal('uuid-1', 'text');

      expect(result.success).toBe(false);
    });
  });

  describe('trackSectionViews', () => {
    it('sends tracking payload and returns success', async () => {
      create_request.mockResolvedValue({});
      const payload = { session_id: 'ses_1', sections: [{ section_type: 'greeting' }] };

      const result = await store.trackSectionViews('uuid-1', payload);

      expect(create_request).toHaveBeenCalledWith('proposals/uuid-1/track/', payload);
      expect(result.success).toBe(true);
    });

    it('returns failure on error', async () => {
      create_request.mockRejectedValue(new Error('network'));

      const result = await store.trackSectionViews('uuid-1', {});

      expect(result.success).toBe(false);
    });
  });

  describe('fetchProposalAnalytics', () => {
    it('fetches analytics data', async () => {
      const analytics = { total_views: 10, unique_sessions: 3 };
      get_request.mockResolvedValue({ data: analytics });

      const result = await store.fetchProposalAnalytics(1);

      expect(get_request).toHaveBeenCalledWith('proposals/1/analytics/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(analytics);
    });

    it('returns failure on error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchProposalAnalytics(1);

      expect(result.success).toBe(false);
    });
  });

  describe('retryFirstViewNotification', () => {
    it('posts to the durable first-view retry endpoint', async () => {
      const notification = { status: 'pending', attempts: 0 };
      create_request.mockResolvedValue({ data: notification });

      const result = await store.retryFirstViewNotification(17);

      expect(create_request).toHaveBeenCalledWith(
        'proposals/17/notifications/first-view/retry/',
        {},
      );
      expect(result).toEqual({ success: true, data: notification });
    });
  });

  describe('fetchProposalDashboard', () => {
    it('fetches dashboard KPIs', async () => {
      const dashboard = { total_proposals: 5, acceptance_rate: 0.6 };
      get_request.mockResolvedValue({ data: dashboard });

      const result = await store.fetchProposalDashboard();

      expect(get_request).toHaveBeenCalledWith('proposals/dashboard/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(dashboard);
    });

    it('returns failure on error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchProposalDashboard();

      expect(result.success).toBe(false);
    });
  });

  describe('scheduleFollowup', () => {
    it('schedules followup with default 3 months', async () => {
      const responseData = { followup_scheduled_at: '2026-06-07' };
      create_request.mockResolvedValue({ data: responseData });

      const result = await store.scheduleFollowup('uuid-1');

      expect(create_request).toHaveBeenCalledWith(
        'proposals/uuid-1/schedule-followup/',
        { months: 3 },
      );
      expect(result.success).toBe(true);
      expect(result.data).toEqual(responseData);
    });

    it('schedules followup with custom months', async () => {
      create_request.mockResolvedValue({ data: {} });

      await store.scheduleFollowup('uuid-1', 6);

      expect(create_request).toHaveBeenCalledWith(
        'proposals/uuid-1/schedule-followup/',
        { months: 6 },
      );
    });

    it('returns failure on error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.scheduleFollowup('uuid-1');

      expect(result.success).toBe(false);
    });
  });

  describe('shareProposal', () => {
    it('creates share link and returns data', async () => {
      const shareData = { uuid: 'share-uuid', url: '/proposals/shared/share-uuid/' };
      create_request.mockResolvedValue({ data: shareData });

      const result = await store.shareProposal('uuid-1', { name: 'Alice', email: 'a@co.com' });

      expect(create_request).toHaveBeenCalledWith(
        'proposals/uuid-1/share/',
        { name: 'Alice', email: 'a@co.com' },
      );
      expect(result.success).toBe(true);
      expect(result.data).toEqual(shareData);
    });

    it('returns failure on error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.shareProposal('uuid-1', {});

      expect(result.success).toBe(false);
    });
  });

  describe('fetchSharedProposal', () => {
    it('fetches shared proposal and sets currentProposal', async () => {
      const proposal = { id: 1, title: 'Shared' };
      get_request.mockResolvedValue({ data: proposal });

      const result = await store.fetchSharedProposal('share-uuid');

      expect(get_request).toHaveBeenCalledWith('proposals/shared/share-uuid/');
      expect(result.success).toBe(true);
      expect(store.currentProposal).toEqual(proposal);
    });

    it('appends query params when provided', async () => {
      get_request.mockResolvedValue({ data: {} });

      await store.fetchSharedProposal('share-uuid', { name: 'Bob', email: 'b@co.com' });

      expect(get_request).toHaveBeenCalledWith(
        'proposals/shared/share-uuid/?name=Bob&email=b%40co.com',
      );
    });

    it('sets expired error on 410', async () => {
      get_request.mockRejectedValue({ response: { status: 410 } });

      const result = await store.fetchSharedProposal('expired-uuid');

      expect(result.success).toBe(false);
      expect(store.error).toBe('expired');
      expect(result.status).toBe(410);
    });

    it('sets not_found error on 404', async () => {
      get_request.mockRejectedValue({ response: { status: 404 } });

      const result = await store.fetchSharedProposal('missing-uuid');

      expect(result.success).toBe(false);
      expect(store.error).toBe('not_found');
    });

    it('sets unknown error on other status', async () => {
      get_request.mockRejectedValue({ response: { status: 500 } });

      const result = await store.fetchSharedProposal('error-uuid');

      expect(result.success).toBe(false);
      expect(store.error).toBe('unknown');
    });

    it('resets isLoading after request', async () => {
      get_request.mockResolvedValue({ data: {} });

      await store.fetchSharedProposal('uuid');

      expect(store.isLoading).toBe(false);
    });
  });

  describe('fetchClients', () => {
    it('returns success with data on resolved request', async () => {
      const clients = [{ client_name: 'Acme', total_proposals: 2 }];
      get_request.mockResolvedValue({ data: clients });

      const result = await store.fetchClients();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(clients);
      expect(get_request).toHaveBeenCalledWith('proposals/clients/');
    });

    it('returns success false on rejected request', async () => {
      get_request.mockRejectedValue(new Error('Network error'));

      const result = await store.fetchClients();

      expect(result.success).toBe(false);
    });
  });

  describe('logActivity', () => {
    it('logs activity and returns data', async () => {
      create_request.mockResolvedValue({ data: { id: 1, change_type: 'call' } });

      const result = await store.logActivity(5, { change_type: 'call', description: 'Called' });

      expect(create_request).toHaveBeenCalledWith(
        'proposals/5/log-activity/',
        { change_type: 'call', description: 'Called' },
      );
      expect(result.success).toBe(true);
    });

    it('returns success false on error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.logActivity(5, {});

      expect(result.success).toBe(false);
    });
  });

  describe('fetchAlerts', () => {
    it('fetches alerts and returns data', async () => {
      const alerts = [{ id: 1, alert_type: 'not_viewed' }];
      get_request.mockResolvedValue({ data: alerts });

      const result = await store.fetchAlerts();

      expect(get_request).toHaveBeenCalledWith('proposals/alerts/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(alerts);
    });

    it('returns empty array on error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchAlerts();

      expect(result.success).toBe(false);
      expect(result.data).toEqual([]);
    });
  });

  describe('createAlert', () => {
    it('creates alert and returns data', async () => {
      const alertData = { id: 1, alert_type: 'reminder' };
      create_request.mockResolvedValue({ data: alertData });

      const result = await store.createAlert({ proposal: 1, alert_type: 'reminder', message: 'Test' });

      expect(create_request).toHaveBeenCalledWith(
        'proposals/alerts/create/',
        expect.objectContaining({ alert_type: 'reminder' }),
      );
      expect(result.success).toBe(true);
    });

    it('returns validation errors on failure', async () => {
      create_request.mockRejectedValue({ response: { data: { message: ['required'] } } });

      const result = await store.createAlert({});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ message: ['required'] });
    });
  });

  describe('dismissAlert', () => {
    it('dismisses alert by id', async () => {
      patch_request.mockResolvedValue({});

      const result = await store.dismissAlert(42);

      expect(patch_request).toHaveBeenCalledWith('proposals/alerts/42/dismiss/', {});
      expect(result.success).toBe(true);
    });

    it('dismisses computed alert with payload', async () => {
      patch_request.mockResolvedValue({});

      const result = await store.dismissAlert(17, {
        computed_alert_type: 'not_viewed',
        ref_date: '2026-03-10T12:00:00+00:00',
      });

      expect(patch_request).toHaveBeenCalledWith('proposals/alerts/17/dismiss/', {
        computed_alert_type: 'not_viewed',
        ref_date: '2026-03-10T12:00:00+00:00',
      });
      expect(result.success).toBe(true);
    });

    it('returns success false on error', async () => {
      patch_request.mockRejectedValue(new Error('fail'));

      const result = await store.dismissAlert(99);

      expect(result.success).toBe(false);
    });
  });

  describe('updateProposalStatus', () => {
    it('updates status and returns success', async () => {
      patch_request.mockResolvedValue({ data: { id: 1, status: 'viewed' } });
      store.proposals = [{ id: 1, status: 'sent' }];

      const result = await store.updateProposalStatus(1, 'viewed');

      expect(patch_request).toHaveBeenCalledWith('proposals/1/update-status/', { status: 'viewed' });
      expect(result.success).toBe(true);
      expect(store.proposals[0].status).toBe('viewed');
    });

    it('updates currentProposal when it matches', async () => {
      patch_request.mockResolvedValue({ data: { id: 5, status: 'expired' } });
      store.currentProposal = { id: 5, status: 'sent' };

      const result = await store.updateProposalStatus(5, 'expired');

      expect(result.success).toBe(true);
      expect(store.currentProposal).toEqual({ id: 5, status: 'expired' });
    });

    it('returns success false on error', async () => {
      patch_request.mockRejectedValue(new Error('fail'));

      const result = await store.updateProposalStatus(1, 'viewed');

      expect(result.success).toBe(false);
      expect(store.error).toBe('update_status_failed');
    });

    it('updates status to finished from accepted', async () => {
      patch_request.mockResolvedValue({ data: { id: 7, status: 'finished' } });
      store.proposals = [{ id: 7, status: 'accepted' }];

      const result = await store.updateProposalStatus(7, 'finished');

      expect(patch_request).toHaveBeenCalledWith('proposals/7/update-status/', { status: 'finished' });
      expect(result.success).toBe(true);
      expect(store.proposals[0].status).toBe('finished');
    });

    it('propagates email_delivery on draft→sent transitions', async () => {
      const respData = {
        id: 9,
        status: 'sent',
        email_delivery: { ok: true, reason: 'sent', detail: '' },
      };
      patch_request.mockResolvedValue({ data: respData });
      store.proposals = [{ id: 9, status: 'draft' }];

      const result = await store.updateProposalStatus(9, 'sent');

      expect(result.success).toBe(true);
      expect(result.email_delivery).toEqual(respData.email_delivery);
    });

    it('email_delivery is null for transitions that do not send email', async () => {
      patch_request.mockResolvedValue({ data: { id: 1, status: 'viewed' } });
      store.proposals = [{ id: 1, status: 'sent' }];

      const result = await store.updateProposalStatus(1, 'viewed');

      expect(result.email_delivery).toBeNull();
    });
  });

  describe('fetchScorecard', () => {
    it('fetches scorecard and returns data', async () => {
      get_request.mockResolvedValue({ data: { score: 8, checks: [] } });

      const result = await store.fetchScorecard(1);

      expect(get_request).toHaveBeenCalledWith('proposals/1/scorecard/');
      expect(result.success).toBe(true);
      expect(result.data.score).toBe(8);
    });

    it('returns success false on error', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchScorecard(1);

      expect(result.success).toBe(false);
    });
  });

  describe('bulkAction', () => {
    it('performs bulk action and returns data', async () => {
      create_request.mockResolvedValue({ data: { affected: 3, action: 'delete' } });

      const result = await store.bulkAction([1, 2, 3], 'delete');

      expect(create_request).toHaveBeenCalledWith('proposals/bulk-action/', { ids: [1, 2, 3], action: 'delete' });
      expect(result.success).toBe(true);
      expect(result.data.affected).toBe(3);
    });

    it('returns success false on error', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.bulkAction([], 'expire');

      expect(result.success).toBe(false);
    });
  });

  describe('fetchProposalDefaults', () => {
    it('fetches defaults for given language', async () => {
      const data = { sections: [{ section_type: 'greeting' }] };
      get_request.mockResolvedValue({ data });

      const result = await store.fetchProposalDefaults('en');

      expect(get_request).toHaveBeenCalledWith('proposals/defaults/?lang=en');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('defaults to es language', async () => {
      get_request.mockResolvedValue({ data: {} });

      await store.fetchProposalDefaults();

      expect(get_request).toHaveBeenCalledWith('proposals/defaults/?lang=es');
    });

    it('sets error on failure', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchProposalDefaults();

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_defaults_failed');
    });
  });

  describe('saveProposalDefaults', () => {
    it('saves defaults and returns data', async () => {
      const data = { id: 1, language: 'es' };
      put_request.mockResolvedValue({ data });

      const sections = [{ section_type: 'greeting', title: 'Saludo' }];
      const result = await store.saveProposalDefaults('es', sections);

      expect(put_request).toHaveBeenCalledWith('proposals/defaults/', {
        language: 'es',
        sections_json: sections,
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('saves general defaults without sections_json when only expiration_days is provided', async () => {
      const data = { id: 1, language: 'es', expiration_days: 21 };
      put_request.mockResolvedValue({ data });

      const result = await store.saveProposalDefaults(
        'es',
        null,
        { expiration_days: 21 },
      );

      expect(put_request).toHaveBeenCalledWith('proposals/defaults/', {
        language: 'es',
        expiration_days: 21,
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('sets error on failure', async () => {
      put_request.mockRejectedValue({
        response: { data: { sections_json: ['Required'] } },
      });

      const result = await store.saveProposalDefaults('es', []);

      expect(result.success).toBe(false);
      expect(store.error).toBe('save_defaults_failed');
      expect(result.errors).toEqual({ sections_json: ['Required'] });
    });

    it('sends the edited version so the backend can refuse a stale overwrite', async () => {
      put_request.mockResolvedValue({ data: { id: 1 } });
      const sections = [{ section_type: 'greeting', title: 'Saludo' }];

      await store.saveProposalDefaults('es', sections, null, '2026-07-28T03:15:23.672677Z');

      expect(put_request).toHaveBeenCalledWith('proposals/defaults/', {
        language: 'es',
        sections_json: sections,
        base_updated_at: '2026-07-28T03:15:23.672677Z',
      });
    });

    it('omits the version when no sections are written', async () => {
      put_request.mockResolvedValue({ data: { id: 1 } });

      await store.saveProposalDefaults(
        'es', null, { expiration_days: 21 }, '2026-07-28T03:15:23.672677Z',
      );

      expect(put_request).toHaveBeenCalledWith('proposals/defaults/', {
        language: 'es',
        expiration_days: 21,
      });
    });

    it('surfaces the stale-defaults conflict to the caller', async () => {
      put_request.mockRejectedValue({
        response: {
          status: 409,
          data: {
            error: 'Los valores por defecto cambiaron desde que abriste esta página.',
            code: 'stale_defaults',
          },
        },
      });

      const result = await store.saveProposalDefaults('es', [], null, '2020-01-01T00:00:00Z');

      expect(result.success).toBe(false);
      expect(result.code).toBe('stale_defaults');
      expect(result.message).toContain('cambiaron desde que abriste');
    });
  });

  describe('resetProposalDefaults', () => {
    it('resets defaults for given language', async () => {
      const data = { sections: [{ section_type: 'greeting' }] };
      create_request.mockResolvedValue({ data });

      const result = await store.resetProposalDefaults('en');

      expect(create_request).toHaveBeenCalledWith('proposals/defaults/reset/', { language: 'en' });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('defaults to es language', async () => {
      create_request.mockResolvedValue({ data: {} });

      await store.resetProposalDefaults();

      expect(create_request).toHaveBeenCalledWith('proposals/defaults/reset/', { language: 'es' });
    });

    it('sets error on failure', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.resetProposalDefaults();

      expect(result.success).toBe(false);
      expect(store.error).toBe('reset_defaults_failed');
    });
  });

  describe('fetchEmailTemplates', () => {
    it('fetches all email templates', async () => {
      const data = [{ template_key: 'proposal_sent' }];
      get_request.mockResolvedValue({ data });

      const result = await store.fetchEmailTemplates();

      expect(get_request).toHaveBeenCalledWith('email-templates/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('sets error on failure', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchEmailTemplates();

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_email_templates_failed');
    });
  });

  describe('fetchEmailTemplateDetail', () => {
    it('fetches single template by key', async () => {
      const data = { template_key: 'proposal_sent', editable_fields: [] };
      get_request.mockResolvedValue({ data });

      const result = await store.fetchEmailTemplateDetail('proposal_sent');

      expect(get_request).toHaveBeenCalledWith('email-templates/proposal_sent/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('sets error on failure', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchEmailTemplateDetail('proposal_sent');

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_email_template_detail_failed');
    });
  });

  describe('saveEmailTemplate', () => {
    it('saves template overrides and returns data', async () => {
      const data = { template_key: 'proposal_sent', is_active: true };
      put_request.mockResolvedValue({ data });

      const payload = { content_overrides: { greeting: 'Hi' }, is_active: true };
      const result = await store.saveEmailTemplate('proposal_sent', payload);

      expect(put_request).toHaveBeenCalledWith('email-templates/proposal_sent/', payload);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('sets error on failure', async () => {
      put_request.mockRejectedValue({
        response: { data: { content_overrides: ['Invalid'] } },
      });

      const result = await store.saveEmailTemplate('proposal_sent', {});

      expect(result.success).toBe(false);
      expect(store.error).toBe('save_email_template_failed');
      expect(result.errors).toEqual({ content_overrides: ['Invalid'] });
    });
  });

  describe('previewEmailTemplate', () => {
    it('fetches HTML preview for template', async () => {
      const data = { html: '<h1>Preview</h1>' };
      get_request.mockResolvedValue({ data });

      const result = await store.previewEmailTemplate('proposal_sent');

      expect(get_request).toHaveBeenCalledWith('email-templates/proposal_sent/preview/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('sets error on failure', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.previewEmailTemplate('proposal_sent');

      expect(result.success).toBe(false);
      expect(store.error).toBe('preview_email_template_failed');
    });
  });

  describe('resetEmailTemplate', () => {
    it('resets template to defaults', async () => {
      const data = { template_key: 'proposal_sent', content_overrides: {} };
      create_request.mockResolvedValue({ data });

      const result = await store.resetEmailTemplate('proposal_sent');

      expect(create_request).toHaveBeenCalledWith('email-templates/proposal_sent/reset/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('sets error on failure', async () => {
      create_request.mockRejectedValue(new Error('fail'));

      const result = await store.resetEmailTemplate('proposal_sent');

      expect(result.success).toBe(false);
      expect(store.error).toBe('reset_email_template_failed');
    });
  });

  describe('requestMagicLink', () => {
    it('returns success on successful request', async () => {
      create_request.mockResolvedValue({});

      const result = await store.requestMagicLink('client@test.com');

      expect(create_request).toHaveBeenCalledWith('proposals/request-link/', { email: 'client@test.com' });
      expect(result.success).toBe(true);
    });

    it('returns failure and logs error on rejection', async () => {
      create_request.mockRejectedValue(new Error('network'));

      const result = await store.requestMagicLink('fail@test.com');

      expect(result.success).toBe(false);
      expect(console.error).toHaveBeenCalled();
    });
  });

  describe('fetchEmailDeliverability', () => {
    it('fetches deliverability dashboard stats', async () => {
      const data = { total_sent: 50, delivered: 48 };
      get_request.mockResolvedValue({ data });

      const result = await store.fetchEmailDeliverability();

      expect(get_request).toHaveBeenCalledWith('email-deliverability/');
      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
    });

    it('sets error on failure', async () => {
      get_request.mockRejectedValue(new Error('fail'));

      const result = await store.fetchEmailDeliverability();

      expect(result.success).toBe(false);
      expect(store.error).toBe('fetch_email_deliverability_failed');
    });
  });

  // -----------------------------------------------------------------------
  // Contract & document management actions
  // -----------------------------------------------------------------------

  describe('fetchDefaultContractTemplate', () => {
    it('returns success with template data', async () => {
      const data = { id: 1, name: 'Standard', content_markdown: '# Contract' };
      get_request.mockResolvedValueOnce({ data });

      const result = await store.fetchDefaultContractTemplate();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
      expect(get_request).toHaveBeenCalledWith('proposals/contract-template/default/');
    });

    it('returns failure on rejected request', async () => {
      get_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.fetchDefaultContractTemplate();

      expect(result.success).toBe(false);
    });
  });

  describe('fetchCompanySettings', () => {
    it('returns success with settings data', async () => {
      const data = { contractor_full_name: 'Carlos', bank_name: 'Bancolombia' };
      get_request.mockResolvedValueOnce({ data });

      const result = await store.fetchCompanySettings();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
      expect(get_request).toHaveBeenCalledWith('proposals/company-settings/');
    });

    it('returns failure on rejected request', async () => {
      get_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.fetchCompanySettings();

      expect(result.success).toBe(false);
    });
  });

  describe('uploadProposalDocument', () => {
    it('returns success on resolved request', async () => {
      const docData = { id: 10, title: 'Annex', document_type: 'legal_annex' };
      create_request.mockResolvedValueOnce({ data: docData });

      const formData = new FormData();
      const result = await store.uploadProposalDocument(1, formData);

      expect(result.success).toBe(true);
      expect(result.data).toEqual(docData);
      expect(create_request).toHaveBeenCalledWith('proposals/1/documents/upload/', formData);
    });

    it('returns failure on rejected request', async () => {
      create_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.uploadProposalDocument(1, new FormData());

      expect(result.success).toBe(false);
    });
  });

  describe('sendDocumentsToClient', () => {
    it('returns success with data on resolved request', async () => {
      const response = { message: 'Sent to client@test.com' };
      create_request.mockResolvedValueOnce({ data: response });

      const payload = { documents: ['commercial'], subject: 'Test' };
      const result = await store.sendDocumentsToClient(5, payload);

      expect(result.success).toBe(true);
      expect(result.data).toEqual(response);
      expect(create_request).toHaveBeenCalledWith('proposals/5/documents/send/', payload);
    });

    it('returns failure on rejected request', async () => {
      create_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.sendDocumentsToClient(5, {});

      expect(result.success).toBe(false);
    });
  });

  describe('sendDiscountOffer', () => {
    it('posts to the discount-offer endpoint and returns success', async () => {
      create_request.mockResolvedValueOnce({ data: { message: 'ok' } });

      const result = await store.sendDiscountOffer(7);

      expect(result.success).toBe(true);
      expect(create_request).toHaveBeenCalledWith('proposals/7/discount-offer/send/', {});
    });

    it('returns failure with backend message on rejection', async () => {
      create_request.mockRejectedValueOnce({ response: { data: { error: 'sin descuento' } } });

      const result = await store.sendDiscountOffer(7);

      expect(result.success).toBe(false);
      expect(result.message).toBe('sin descuento');
    });
  });

  describe('deleteProposalDocument', () => {
    it('returns success on resolved request', async () => {
      delete_request.mockResolvedValueOnce({ data: {} });

      const result = await store.deleteProposalDocument(1, 10);

      expect(result.success).toBe(true);
      expect(delete_request).toHaveBeenCalledWith('proposals/1/documents/10/delete/');
    });

    it('returns failure on rejected request', async () => {
      delete_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.deleteProposalDocument(1, 10);

      expect(result.success).toBe(false);
    });

    it('refreshes currentProposal when id matches', async () => {
      store.currentProposal = { id: 1, title: 'P' };
      delete_request.mockResolvedValueOnce({ data: {} });
      get_request.mockResolvedValueOnce({ data: { id: 1, title: 'Refreshed' } });

      const result = await store.deleteProposalDocument(1, 10);

      expect(result.success).toBe(true);
      expect(get_request).toHaveBeenCalledWith('proposals/1/detail/');
    });
  });

  describe('previewSync', () => {
    it('returns success with data on resolved request', async () => {
      const data = { requirements: [{ id: 1 }] };
      create_request.mockResolvedValueOnce({ data });

      const result = await store.previewSync(5, { items: [] });

      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
      expect(create_request).toHaveBeenCalledWith(
        'proposals/sections/5/sync-preview/',
        { content_json: { items: [] } },
      );
    });

    it('returns failure with errors on rejected request', async () => {
      create_request.mockRejectedValueOnce({ response: { data: { detail: 'bad' } } });

      const result = await store.previewSync(5, {});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ detail: 'bad' });
    });
  });

  describe('applySync', () => {
    it('returns success and updates matching section', async () => {
      store.currentProposal = { id: 1, sections: [{ id: 5, title: 'old' }] };
      const section = { id: 5, title: 'new' };
      create_request.mockResolvedValueOnce({ data: { section } });

      const result = await store.applySync(5, { items: [] });

      expect(result.success).toBe(true);
      expect(store.currentProposal.sections[0].title).toBe('new');
      expect(store.isUpdating).toBe(false);
    });

    it('returns success when section not found in list', async () => {
      store.currentProposal = { id: 1, sections: [{ id: 99, title: 'other' }] };
      create_request.mockResolvedValueOnce({ data: { section: { id: 5, title: 'new' } } });

      const result = await store.applySync(5, {});

      expect(result.success).toBe(true);
      expect(store.currentProposal.sections[0].title).toBe('other');
    });

    it('returns success when currentProposal has no sections', async () => {
      store.currentProposal = null;
      create_request.mockResolvedValueOnce({ data: {} });

      const result = await store.applySync(5, {});

      expect(result.success).toBe(true);
    });

    it('returns failure with errors on rejected request', async () => {
      create_request.mockRejectedValueOnce({ response: { data: { detail: 'fail' } } });

      const result = await store.applySync(5, {});

      expect(result.success).toBe(false);
      expect(result.errors).toEqual({ detail: 'fail' });
      expect(store.isUpdating).toBe(false);
    });
  });

  describe('saveContractAndNegotiate', () => {
    it('returns success and updates currentProposal when id matches', async () => {
      store.currentProposal = { id: 1, status: 'draft' };
      const data = { id: 1, status: 'negotiating' };
      create_request.mockResolvedValueOnce({ data });

      const result = await store.saveContractAndNegotiate(1, { rate: 100 });

      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
      expect(store.currentProposal).toEqual(data);
      expect(store.isUpdating).toBe(false);
    });

    it('updates proposal in list when found', async () => {
      store.proposals = [{ id: 1, status: 'draft' }];
      const data = { id: 1, status: 'negotiating' };
      create_request.mockResolvedValueOnce({ data });

      await store.saveContractAndNegotiate(1, { rate: 100 });

      expect(store.proposals[0].status).toBe('negotiating');
    });

    it('does not update currentProposal when id differs', async () => {
      store.currentProposal = { id: 99, status: 'draft' };
      create_request.mockResolvedValueOnce({ data: { id: 1, status: 'negotiating' } });

      await store.saveContractAndNegotiate(1, {});

      expect(store.currentProposal.id).toBe(99);
    });

    it('returns failure and sets error on rejected request', async () => {
      create_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.saveContractAndNegotiate(1, {});

      expect(result.success).toBe(false);
      expect(store.error).toBe('contract_save_failed');
      expect(store.isUpdating).toBe(false);
    });
  });

  describe('updateContractParams', () => {
    it('returns success and updates currentProposal when id matches', async () => {
      store.currentProposal = { id: 1, status: 'negotiating' };
      const data = { id: 1, status: 'negotiating', rate: 200 };
      patch_request.mockResolvedValueOnce({ data });

      const result = await store.updateContractParams(1, { rate: 200 });

      expect(result.success).toBe(true);
      expect(result.data).toEqual(data);
      expect(store.currentProposal).toEqual(data);
      expect(store.isUpdating).toBe(false);
    });

    it('does not update currentProposal when id differs', async () => {
      store.currentProposal = { id: 99 };
      patch_request.mockResolvedValueOnce({ data: { id: 1, rate: 200 } });

      await store.updateContractParams(1, {});

      expect(store.currentProposal.id).toBe(99);
    });

    it('returns failure on rejected request', async () => {
      patch_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.updateContractParams(1, {});

      expect(result.success).toBe(false);
      expect(store.isUpdating).toBe(false);
    });

    it('names the separate document being generated', async () => {
      // Falla si generar el contrato de servicio no le dice al backend qué documento es.
      patch_request.mockResolvedValueOnce({ data: { id: 1 } });

      await store.updateContractParams(1, { service_initial_term: 'doce (12) meses' }, 'service');

      expect(patch_request).toHaveBeenCalledWith('proposals/1/contract/update/', {
        contract_params: { service_initial_term: 'doce (12) meses' },
        variant: 'service',
      });
    });

    it('surfaces the service terms the backend still needs', async () => {
      // Falla si un 400 del contrato de servicio se pierde sin explicar qué falta.
      patch_request.mockRejectedValueOnce({
        response: { status: 400, data: { service_initial_term: ['Indica este dato del contrato de servicio.'] } },
      });

      const result = await store.updateContractParams(1, {}, 'service');

      expect(result.success).toBe(false);
      expect(result.message).toBe('Indica este dato del contrato de servicio.');
    });
  });

  describe('updateContractModality', () => {
    it('persists the modality and refreshes the open proposal', async () => {
      // Falla si el cambio de modalidad no actualiza la propuesta que muestra el tab.
      store.currentProposal = { id: 1, contract_modality: 'single' };
      const data = { id: 1, contract_modality: 'split', proposal_documents: [] };
      patch_request.mockResolvedValueOnce({ data });

      const result = await store.updateContractModality(1, 'split');

      expect(patch_request).toHaveBeenCalledWith('proposals/1/contract/modality/', { contract_modality: 'split' });
      expect(result.success).toBe(true);
      expect(store.currentProposal).toEqual(data);
      expect(store.isUpdating).toBe(false);
    });

    it('returns the backend reason when the modality is locked', async () => {
      // Falla si el panel no puede explicar por qué no cambió la modalidad.
      store.currentProposal = { id: 1, contract_modality: 'single' };
      patch_request.mockRejectedValueOnce({
        response: {
          status: 409,
          data: { error: 'La modalidad de cierre sólo se cambia durante la negociación.', code: 'modality_locked' },
        },
      });

      const result = await store.updateContractModality(1, 'split');

      expect(result).toMatchObject({ success: false, code: 'modality_locked' });
      expect(result.message).toBe('La modalidad de cierre sólo se cambia durante la negociación.');
      expect(store.currentProposal.contract_modality).toBe('single');
    });
  });

  describe('uploadProposalDocument (currentProposal refresh)', () => {
    it('refreshes currentProposal when id matches', async () => {
      store.currentProposal = { id: 1, title: 'P' };
      create_request.mockResolvedValueOnce({ data: { id: 10 } });
      get_request.mockResolvedValueOnce({ data: { id: 1, title: 'Refreshed' } });

      const result = await store.uploadProposalDocument(1, new FormData());

      expect(result.success).toBe(true);
      expect(get_request).toHaveBeenCalledWith('proposals/1/detail/');
    });
  });

  describe('sendComposedEmail', () => {
    it('returns success with data on resolved request', async () => {
      create_request.mockResolvedValueOnce({ data: { sent: true } });

      const result = await store.sendComposedEmail(1, new FormData());

      expect(result.success).toBe(true);
      expect(result.data).toEqual({ sent: true });
    });

    it('returns failure on rejected request', async () => {
      create_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.sendComposedEmail(1, new FormData());

      expect(result.success).toBe(false);
    });
  });

  describe('fetchEmailDefaults', () => {
    it('returns success with data on resolved request', async () => {
      get_request.mockResolvedValueOnce({ data: { subject: 'Hello' } });

      const result = await store.fetchEmailDefaults(1);

      expect(result.success).toBe(true);
      expect(result.data).toEqual({ subject: 'Hello' });
    });

    it('returns failure with empty data on rejected request', async () => {
      get_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.fetchEmailDefaults(1);

      expect(result.success).toBe(false);
      expect(result.data).toEqual({});
    });
  });

  describe('fetchEmailHistory', () => {
    it('returns success with data on resolved request', async () => {
      get_request.mockResolvedValueOnce({ data: { results: [], total: 0 } });

      const result = await store.fetchEmailHistory(1);

      expect(result.success).toBe(true);
      expect(get_request).toHaveBeenCalledWith('proposals/1/branded-email/history/?page=1');
    });

    it('uses provided page parameter', async () => {
      get_request.mockResolvedValueOnce({ data: { results: [] } });

      await store.fetchEmailHistory(1, 3);

      expect(get_request).toHaveBeenCalledWith('proposals/1/branded-email/history/?page=3');
    });

    it('returns failure with default data on rejected request', async () => {
      get_request.mockRejectedValueOnce(new Error('fail'));

      const result = await store.fetchEmailHistory(1);

      expect(result.success).toBe(false);
      expect(result.data).toEqual({ results: [], total: 0, page: 1, has_next: false });
    });
  });

  describe('proposal-email basePath routing', () => {
    it('sendComposedEmail uses proposal-email path', async () => {
      create_request.mockResolvedValueOnce({ data: { sent: true } });

      await store.sendComposedEmail(1, new FormData(), 'proposal-email');

      expect(create_request).toHaveBeenCalledWith(
        'proposals/1/proposal-email/send/',
        expect.any(FormData),
      );
    });

    it('fetchEmailDefaults uses proposal-email path', async () => {
      get_request.mockResolvedValueOnce({ data: { greeting: 'Hi' } });

      await store.fetchEmailDefaults(1, 'proposal-email');

      expect(get_request).toHaveBeenCalledWith('proposals/1/proposal-email/defaults/');
    });

    it('fetchEmailHistory uses proposal-email path', async () => {
      get_request.mockResolvedValueOnce({ data: { results: [] } });

      await store.fetchEmailHistory(1, 1, 'proposal-email');

      expect(get_request).toHaveBeenCalledWith('proposals/1/proposal-email/history/?page=1');
    });
  });

  describe('project schedule actions', () => {
    it('updateProjectStage calls PUT on the stage endpoint with the dates payload', async () => {
      put_request.mockResolvedValueOnce({
        data: {
          id: 1,
          stage_key: 'design',
          stage_label: 'Diseño',
          start_date: '2026-04-01',
          end_date: '2026-04-15',
          completed_at: null,
        },
      });

      const result = await store.updateProjectStage(42, 'design', {
        start_date: '2026-04-01',
        end_date: '2026-04-15',
      });

      expect(put_request).toHaveBeenCalledWith(
        'proposals/42/stages/design/',
        { start_date: '2026-04-01', end_date: '2026-04-15' },
      );
      expect(result.success).toBe(true);
    });

    it('updateProjectStage merges the returned stage into currentProposal.project_stages', async () => {
      store.currentProposal = {
        id: 42,
        project_stages: [
          { id: 1, stage_key: 'design', start_date: null, end_date: null },
          { id: 2, stage_key: 'development', start_date: null, end_date: null },
        ],
      };
      put_request.mockResolvedValueOnce({
        data: {
          id: 1,
          stage_key: 'design',
          start_date: '2026-04-01',
          end_date: '2026-04-15',
        },
      });

      await store.updateProjectStage(42, 'design', {
        start_date: '2026-04-01',
        end_date: '2026-04-15',
      });

      const updated = store.currentProposal.project_stages.find(
        (s) => s.stage_key === 'design',
      );
      expect(updated.start_date).toBe('2026-04-01');
      expect(updated.end_date).toBe('2026-04-15');
    });

    it('updateProjectStage returns success false when the request rejects', async () => {
      put_request.mockRejectedValueOnce({
        response: { data: { end_date: ['error'] } },
      });

      const result = await store.updateProjectStage(42, 'design', {
        start_date: '2026-04-15',
        end_date: '2026-04-01',
      });

      expect(result.success).toBe(false);
      expect(result.error).toEqual({ end_date: ['error'] });
    });

    it('completeProjectStage POSTs to the complete endpoint', async () => {
      create_request.mockResolvedValueOnce({
        data: {
          id: 1,
          stage_key: 'design',
          completed_at: '2026-04-15T12:00:00Z',
        },
      });

      const result = await store.completeProjectStage(42, 'design');

      expect(create_request).toHaveBeenCalledWith(
        'proposals/42/stages/design/complete/',
        {},
      );
      expect(result.success).toBe(true);
    });

    it('completeProjectStage updates the merged stage with completed_at', async () => {
      store.currentProposal = {
        id: 42,
        project_stages: [
          { id: 1, stage_key: 'design', completed_at: null },
        ],
      };
      create_request.mockResolvedValueOnce({
        data: {
          id: 1,
          stage_key: 'design',
          completed_at: '2026-04-15T12:00:00Z',
        },
      });

      await store.completeProjectStage(42, 'design');

      const updated = store.currentProposal.project_stages.find(
        (s) => s.stage_key === 'design',
      );
      expect(updated.completed_at).toBe('2026-04-15T12:00:00Z');
    });

    it('completeProjectStage returns success false when the request rejects', async () => {
      create_request.mockRejectedValueOnce(new Error('boom'));

      const result = await store.completeProjectStage(42, 'design');

      expect(result.success).toBe(false);
    });
  });
});
