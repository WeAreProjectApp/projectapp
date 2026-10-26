import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import DashboardAttentionRadar from '../../components/panel/dashboard/DashboardAttentionRadar.vue';
import { usePanelDashboardStore } from '../../stores/panel_dashboard';
import { get_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));
global.useLocalePath = jest.fn(() => (path) => path);
global.useI18n = jest.fn(() => ({ locale: { value: 'es-co' } }));
const record = { id: 42, type: 'emails_failed', title: 'Invoice ACME', recipient: 'client@example.test', sent_at: '2026-10-26T12:00:00Z', error_message: 'No se pudo completar el envío de correo.', eligible: true, can_resend: true, destination: '/panel/emails?tab=history&email=42&radar=1' };
const item = { type: 'emails_failed', severity: 'danger', count: 6, meta: {} };
let wrappers;
function mountRadar(items = [item]) {
  const wrapper = mount(DashboardAttentionRadar, { props: { items }, global: { stubs: {
    BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue" role="dialog"><slot /></div>' },
    BaseButton: { props: ['as', 'to'], template: '<component :is="as === \'NuxtLink\' ? \'a\' : \'button\'" :href="to"><slot /></component>' },
    BaseActionIcon: true,
  } } });
  wrappers.push(wrapper);
  return wrapper;
}
beforeEach(() => {
  setActivePinia(createPinia());
  usePanelDashboardStore().summary = { attention: [{ ...item }] };
  wrappers = [];
  get_request.mockReset();
  get_request.mockResolvedValue({ data: { results: [record], total: 6, page: 1, has_next: true } });
});
afterEach(() => wrappers.forEach((wrapper) => wrapper.unmount()));

it('shows the positive empty state', () => {
  expect(mountRadar([]).get('[data-testid="attention-radar-empty"]').text()).toContain('Todo al día');
});
it('starts with collapsed alerts', () => {
  const wrapper = mountRadar();
  expect(wrapper.get('[data-testid="attention-item-emails_failed"]').attributes('aria-expanded')).toBe('false');
  expect(wrapper.find('[data-testid="radar-records-emails_failed"]').exists()).toBe(false);
});
it('loads identifying details when expanded', async () => {
  const wrapper = mountRadar();
  await wrapper.get('[data-testid="attention-item-emails_failed"]').trigger('click');
  await flushPromises();
  expect(wrapper.get('[data-testid="radar-record-emails_failed-42"]').text()).toContain('client@example.test');
  expect(wrapper.text()).toContain('No se pudo completar el envío de correo.');
});
it('preserves loaded records after collapsing', async () => {
  const wrapper = mountRadar();
  const header = wrapper.get('[data-testid="attention-item-emails_failed"]');
  await header.trigger('click');
  await flushPromises();
  await header.trigger('click');
  await header.trigger('click');
  expect(get_request).toHaveBeenCalledTimes(1);
  expect(wrapper.get('[data-testid="radar-record-emails_failed-42"]').text()).toContain('Invoice ACME');
});
it('appends the next page without duplicating records', async () => {
  const wrapper = mountRadar();
  await wrapper.get('[data-testid="attention-item-emails_failed"]').trigger('click');
  await flushPromises();
  get_request.mockResolvedValueOnce({ data: { results: [record, { ...record, id: 43 }], total: 6, page: 2, has_next: false } });
  await wrapper.get('[data-testid="radar-more-emails_failed"]').trigger('click');
  await flushPromises();
  expect(wrapper.findAll('[data-testid^="radar-record-emails_failed-"]')).toHaveLength(2);
  expect(wrapper.find('[data-testid="radar-more-emails_failed"]').exists()).toBe(false);
});
it('opens updated detail before offering the exact destination', async () => {
  const wrapper = mountRadar();
  await wrapper.get('[data-testid="attention-item-emails_failed"]').trigger('click');
  await flushPromises();
  get_request.mockResolvedValueOnce({ data: record });
  await wrapper.get('[data-testid="radar-record-emails_failed-42"]').trigger('click');
  await flushPromises();
  expect(wrapper.get('[role="dialog"]').text()).toContain('Invoice ACME');
  expect(wrapper.get('[data-testid="radar-detail-destination"]').attributes('href')).toBe(record.destination);
});
it('explains a deleted record without offering navigation', async () => {
  const wrapper = mountRadar();
  await wrapper.get('[data-testid="attention-item-emails_failed"]').trigger('click');
  await flushPromises();
  get_request.mockRejectedValueOnce({ response: { status: 404 } });
  await wrapper.get('[data-testid="radar-record-emails_failed-42"]').trigger('click');
  await flushPromises();
  expect(wrapper.get('[role="dialog"]').text()).toContain('ya no existe');
  expect(wrapper.find('[data-testid="radar-detail-destination"]').exists()).toBe(false);
});
it('recovers a failed list request', async () => {
  get_request.mockRejectedValueOnce(new Error('network'));
  const wrapper = mountRadar();
  await wrapper.get('[data-testid="attention-item-emails_failed"]').trigger('click');
  await flushPromises();
  await wrapper.get('[role="alert"] button').trigger('click');
  await flushPromises();
  expect(wrapper.get('[data-testid="radar-record-emails_failed-42"]').text()).toContain('Invoice ACME');
});
it('counts pending elements rather than alert groups', () => {
  const store = usePanelDashboardStore();
  store.summary.attention.push({ type: 'recurring_due', count: 1 });
  expect(store.attentionCount).toBe(7);
});
