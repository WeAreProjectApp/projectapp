import { createPinia, setActivePinia } from 'pinia';
import { useProposalStore } from '../../stores/proposals';
import { put_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(), create_request: jest.fn(), put_request: jest.fn(),
  patch_request: jest.fn(), delete_request: jest.fn(),
}));
beforeEach(() => {
  setActivePinia(createPinia());
  jest.clearAllMocks();
  put_request.mockResolvedValue({ data: { updated_at: '2026-10-23T22:00:00Z' } });
});

// Clearing obsolete root aliases is deliberate and must survive JSON serialization.
it('sends an empty root format map when normalized section defaults replace it', async () => {
  const store = useProposalStore();
  const sections = [{ section_type: 'greeting', content_json: {
    inspirationalQuote: '**New**', text_formats: { '/inspirationalQuote': 'markdown_html_v1' },
  } }];

  await store.saveProposalDefaults('es', sections, null, 'old-version', {});

  expect(put_request).toHaveBeenCalledWith('proposals/defaults/', {
    language: 'es', sections_json: sections, base_updated_at: 'old-version', text_formats: {},
  });
});

// Older clients must not erase annotations simply by omitting the optional argument.
it('leaves root format metadata untouched when no replacement is supplied', async () => {
  const store = useProposalStore();

  await store.saveProposalDefaults('es', [], null, 'old-version');

  expect(put_request).toHaveBeenCalledWith('proposals/defaults/', {
    language: 'es', sections_json: [], base_updated_at: 'old-version',
  });
});
