import { mount } from '@vue/test-utils';

import EntityHistoryRecordModal from '../../components/history/EntityHistoryRecordModal.vue';

const SNAPSHOT = {
  id: 7,
  card_name: 'T.C 0064',
  snapshot_date: '2026-09-19',
  available_amount: '413226.00',
  debt_amount: '7586774.00',
  notes: 'Corte semanal',
  created_at: '2026-09-19T10:00:00Z',
};

const stubs = {
  NuxtLink: { template: '<a><slot /></a>' },
  BaseModal: {
    props: ['modelValue', 'kind'],
    emits: ['close'],
    template: '<div v-if="modelValue"><slot /></div>',
  },
  EntityHistoryTabs: {
    props: ['entityType', 'objectId'],
    template: '<section data-testid="history-tabs" :data-entity="entityType" :data-object="objectId"><slot /></section>',
  },
};

function mountModal(props = {}) {
  return mount(EntityHistoryRecordModal, {
    props: { open: true, entityType: 'card_snapshot', record: SNAPSHOT, ...props },
    global: { stubs },
  });
}

describe('EntityHistoryRecordModal', () => {
  it('binds the history to the fields of its record type', () => {
    const tabs = mountModal().get('[data-testid="history-tabs"]');

    expect(tabs.attributes('data-entity')).toBe('card_snapshot');
    expect(tabs.attributes('data-object')).toBe('7');
    expect(tabs.text()).toContain('Fecha del saldo');
    expect(tabs.text()).toContain('Corte semanal');
    expect(tabs.text()).not.toContain('created at');
  });

  // Row menus open it without a record first; it must stay closed until then.
  it('stays closed until the page hands it a record', () => {
    const wrapper = mountModal({ record: null });

    expect(wrapper.find('[data-testid="history-record-modal"]').exists()).toBe(false);
  });

  it('asks the page to close it', async () => {
    const wrapper = mountModal();

    await wrapper.get('button').trigger('click');

    expect(wrapper.emitted('close')).toHaveLength(1);
  });
});
