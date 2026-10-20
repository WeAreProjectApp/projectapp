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

  // Bug caught: a row action opened a blank detail while its linked record was loading.
  it('shows a concrete loading state before the linked record arrives', () => {
    const wrapper = mountModal({ record: null, loading: true });

    expect(wrapper.get('[role="status"]').text()).toBe('Cargando el registro…');
  });

  // Bug caught: a transient linked-record failure had no recovery action.
  it('emits retry for a recoverable record error', async () => {
    const wrapper = mountModal({ record: null, error: 'failed' });

    expect(wrapper.get('[role="alert"]').get('p').text()).toBe('No se pudo cargar el registro.')
    await wrapper.get('[role="alert"]').get('button').trigger('click');

    expect(wrapper.emitted('retry')).toEqual([[]]);
  });

  // Bug caught: a deleted linked record exposed a retry that could not produce a detail.
  it('does not offer retry for a missing record', () => {
    const wrapper = mountModal({ record: null, error: 'missing' });

    expect(wrapper.get('[role="alert"]').get('p').text()).toBe('Este registro ya no existe.')
    expect(wrapper.findAll('button')).toHaveLength(1)
  });
});
