import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ClientEmailsModal from '../../components/clients/ClientEmailsModal.vue';
import { useProposalClientsStore } from '../../stores/proposal_clients';

jest.mock('~/composables/usePanelNotify', () => ({
  usePanelNotify: () => ({ success: jest.fn(), error: jest.fn() }),
}), { virtual: true });

const CLIENT = { id: 7, name: 'Ana Cliente' };

const row = (overrides = {}) => ({
  id: 1,
  template_key: 'collection_account_sent',
  template_label: 'Cuenta de cobro',
  recipient: 'ana@example.com',
  subject: 'Cuenta de cobro 001',
  status: 'sent',
  status_label: 'Sent',
  audience: 'client',
  audience_label: 'Al cliente',
  has_body: true,
  is_retryable: false,
  retry_blocked_reason: '',
  targets: [],
  ...overrides,
});

function page(results, count = results.length) {
  return { success: true, data: { results, count, page: 1, num_pages: 1 } };
}

// Stubs declare their emits: without that, the native fallthrough fires the
// parent handler a second time and the assertions drift.
const stubs = {
  BaseModal: {
    props: ['modelValue', 'closeOnEsc', 'closeOnBackdrop'],
    emits: ['update:modelValue'],
    template: `<div
      data-testid="modal-shell"
      :data-close-on-esc="String(closeOnEsc)"
      :data-close-on-backdrop="String(closeOnBackdrop)"
    ><slot /></div>`,
  },
  BaseSegmented: {
    props: ['modelValue', 'options'],
    emits: ['update:modelValue'],
    template: `<div><button
      v-for="o in options" :key="o.value"
      :data-testid="'seg-' + o.value"
      @click="$emit('update:modelValue', o.value)">{{ o.label }}</button></div>`,
  },
  BaseButton: {
    emits: ['click'],
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  },
  EmailLogTable: {
    props: { entries: Array, retryingId: [Number, String], nested: Boolean },
    emits: ['view-body', 'retry', 'menu-open-change'],
    template: `<div data-testid="table" :data-nested="String(nested)">
      <button v-for="e in entries" :key="e.id"
        :data-testid="'view-' + e.id"
        @click="$emit('view-body', e)">{{ e.subject }}</button>
      <button v-for="e in entries" :key="'r' + e.id"
        :data-testid="'retry-' + e.id"
        @click="$emit('retry', e)">Reintentar</button>
      <button data-testid="open-row-menu" @click="$emit('menu-open-change', true)">Menú</button>
    </div>`,
  },
};

function mountModal(store) {
  return mount(ClientEmailsModal, {
    props: { open: true, client: CLIENT },
    global: { stubs },
  });
}

describe('ClientEmailsModal', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useProposalClientsStore();
  });

  it('opens on what reached the client and labels both groups with their totals', async () => {
    store.fetchClientEmails = jest.fn((id, { audience } = {}) => Promise.resolve(
      page([row()], audience === 'internal' ? 4 : 2),
    ));

    const wrapper = mountModal(store);
    await flushPromises();

    expect(store.fetchClientEmails).toHaveBeenCalledWith(7, {
      audience: 'client', page: 1,
    });
    expect(wrapper.text()).toContain('Al cliente (2)');
    expect(wrapper.text()).toContain('Internos (4)');
  });

  it('refetches from the server when the group changes', async () => {
    // Server-side because the list paginates: filtering one loaded page would
    // misreport what the other group holds.
    store.fetchClientEmails = jest.fn(() => Promise.resolve(page([row()])));
    const wrapper = mountModal(store);
    await flushPromises();
    store.fetchClientEmails.mockClear();

    await wrapper.get('[data-testid="seg-internal"]').trigger('click');
    await flushPromises();

    expect(store.fetchClientEmails).toHaveBeenCalledWith(7, {
      audience: 'internal', page: 1,
    });
  });

  it('hands the row up so the page can open the viewer over this modal', async () => {
    store.fetchClientEmails = jest.fn(() => Promise.resolve(page([row()])));
    const wrapper = mountModal(store);
    await flushPromises();

    await wrapper.get('[data-testid="view-1"]').trigger('click');

    expect(wrapper.emitted('view-body')[0][0].id).toBe(1);
  });

  it('stops answering Esc while the viewer is open above it', async () => {
    // BaseModal's keydown listener is global, so without this both would close.
    store.fetchClientEmails = jest.fn(() => Promise.resolve(page([row()])));
    const wrapper = mount(ClientEmailsModal, {
      props: { open: true, client: CLIENT, previewOpen: true },
      global: { stubs },
    });
    await flushPromises();

    const shell = wrapper.get('[data-testid="modal-shell"]');
    expect(shell.attributes('data-close-on-esc')).toBe('false');
    expect(shell.attributes('data-close-on-backdrop')).toBe('false');
  });

  it('stops answering Esc while a row menu is open above it', async () => {
    // The row menu is another BaseModal with the same global Esc listener.
    store.fetchClientEmails = jest.fn(() => Promise.resolve(page([row()])));
    const wrapper = mountModal(store);
    await flushPromises();

    expect(wrapper.get('[data-testid="table"]').attributes('data-nested')).toBe('true');
    await wrapper.get('[data-testid="open-row-menu"]').trigger('click');

    const shell = wrapper.get('[data-testid="modal-shell"]');
    expect(shell.attributes('data-close-on-esc')).toBe('false');
    expect(shell.attributes('data-close-on-backdrop')).toBe('false');
  });

  it('answers Esc normally when nothing is stacked above it', async () => {
    store.fetchClientEmails = jest.fn(() => Promise.resolve(page([row()])));
    const wrapper = mountModal(store);
    await flushPromises();

    expect(wrapper.get('[data-testid="modal-shell"]').attributes('data-close-on-esc'))
      .toBe('true');
  });

  it('surfaces the reason a send could not be retried', async () => {
    store.fetchClientEmails = jest.fn(() => Promise.resolve(page([row()])));
    store.retryClientEmail = jest.fn(() => Promise.resolve({
      success: false, message: 'Los correos de propuestas no se reenvían desde aquí.',
    }));
    const wrapper = mountModal(store);
    await flushPromises();

    await wrapper.get('[data-testid="retry-1"]').trigger('click');
    await flushPromises();

    expect(store.retryClientEmail).toHaveBeenCalledWith(7, 1);
  });

  it('says so when the history cannot be loaded', async () => {
    store.fetchClientEmails = jest.fn(() => Promise.resolve({
      success: false, message: 'No se pudieron cargar los correos.',
    }));
    const wrapper = mountModal(store);
    await flushPromises();

    expect(wrapper.get('[data-testid="client-emails-error"]').text())
      .toContain('No se pudieron cargar los correos.');
  });
});
