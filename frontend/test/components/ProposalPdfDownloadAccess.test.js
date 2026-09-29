import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';
import PdfDownloadButton from '../../components/BusinessProposal/PdfDownloadButton.vue';
import ProposalClosing from '../../components/BusinessProposal/ProposalClosing.vue';

jest.mock('../../composables/useSectionAnimations', () => ({ useSectionAnimations: jest.fn() }));
jest.mock('canvas-confetti', () => jest.fn());

const expiredMessage = 'Esta propuesta está vencida. Solicita una versión actualizada para descargar el PDF.';
let proposal;
let wrapper;

beforeEach(() => {
  proposal = reactive({ uuid: 'proposal-uuid', title: 'Sample', language: 'es', status: 'sent', created_at: '2026-01-01T12:00:00Z' });
  global.useProposalStore = jest.fn(() => ({ currentProposal: proposal }));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, blob: async () => new Blob(['%PDF']) });
  global.URL.createObjectURL = jest.fn(() => 'blob:download');
  global.URL.revokeObjectURL = jest.fn();
  jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => {
  wrapper?.unmount();
  jest.restoreAllMocks();
});

it.each(['detailed', 'technical'])('explains expired %s downloads without requesting a file', async (viewMode) => {
  proposal.status = 'expired';
  wrapper = mount(PdfDownloadButton, { props: { viewMode } });

  await wrapper.get('button').trigger('click');

  expect(wrapper.get('button').element.disabled).toBe(true);
  expect(wrapper.get('[role="status"]').text()).toBe(expiredMessage);
  expect(global.fetch).not.toHaveBeenCalled();
});

it('explains a date-based expiry in English', () => {
  proposal.language = 'en';
  proposal.expires_at = '2000-01-01T00:00:00Z';
  wrapper = mount(PdfDownloadButton);

  expect(wrapper.get('button').element.disabled).toBe(true);
  expect(wrapper.get('[role="status"]').text()).toBe('This proposal has expired. Request an updated version to download the PDF.');
});

it('blocks another attempt after a late expiry response', async () => {
  global.fetch.mockResolvedValue({ ok: false, status: 410 });
  wrapper = mount(PdfDownloadButton);

  await wrapper.get('button').trigger('click');
  await flushPromises();
  await wrapper.get('button').trigger('click');

  expect(wrapper.get('[role="status"]').text()).toBe(expiredMessage);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(global.URL.createObjectURL).not.toHaveBeenCalled();
});

it.each([500, 429])('allows a successful retry after HTTP %s', async (status) => {
  global.fetch.mockResolvedValueOnce({ ok: false, status });
  wrapper = mount(PdfDownloadButton);
  await wrapper.get('button').trigger('click');
  await flushPromises();
  expect(wrapper.get('[role="status"]').text()).toBe('No se pudo descargar el PDF. Inténtalo nuevamente.');

  await wrapper.get('button').trigger('click');
  await flushPromises();

  expect(wrapper.find('[role="status"]').exists()).toBe(false);
  expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:download');
});

it('reports a network failure visibly', async () => {
  global.fetch.mockRejectedValueOnce(new TypeError('offline'));
  wrapper = mount(PdfDownloadButton);

  await wrapper.get('button').trigger('click');
  await flushPromises();

  expect(wrapper.get('[role="status"]').text()).toContain('Inténtalo nuevamente');
  expect(wrapper.get('button').element.disabled).toBe(false);
});

it('keeps the selected scope in a technical download', async () => {
  wrapper = mount(PdfDownloadButton, { props: { viewMode: 'technical', selectedModuleIds: ['module-a'] } });

  await wrapper.get('button').trigger('click');
  await flushPromises();

  expect(global.fetch).toHaveBeenCalledWith('/api/proposals/proposal-uuid/pdf/?selected_modules=module-a&doc=technical');
  expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
});

it('keeps the legal draft available on expired proposals', async () => {
  proposal.status = 'expired';
  wrapper = mount(PdfDownloadButton, { props: { viewMode: 'legal' } });

  await wrapper.get('button').trigger('click');
  await flushPromises();

  expect(global.fetch).toHaveBeenCalledWith('/api/proposals/proposal-uuid/contract/draft-pdf/');
  expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
});

it('removes the closing download link destination when expired', () => {
  proposal.status = 'accepted';
  proposal.expired_meta = { expired_at: '2000-01-01T00:00:00Z' };
  wrapper = mount(ProposalClosing, { props: { proposal } });

  const link = wrapper.get('a[download]');
  expect(link.attributes('href')).toBeUndefined();
  expect(link.attributes('aria-disabled')).toBe('true');
  expect(wrapper.get('[role="status"]').text()).toBe(expiredMessage);
});

it('shows late expiry from the closing download', async () => {
  proposal.status = 'accepted';
  global.fetch.mockResolvedValueOnce({ ok: false, status: 410 });
  wrapper = mount(ProposalClosing, { props: { proposal } });

  await wrapper.get('a[download]').trigger('click');
  await flushPromises();

  expect(wrapper.get('[role="status"]').text()).toBe(expiredMessage);
  expect(wrapper.get('a[download]').attributes('href')).toBeUndefined();
});
