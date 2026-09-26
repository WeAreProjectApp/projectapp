/**
 * Tests for AccountingRowActionsModal: the menu behind an accounting row's
 * three-dot button. The owner lists the entries; the menu names the record,
 * closes, and only then hands the chosen action back.
 */
import { flushPromises, mount } from '@vue/test-utils';
import AccountingRowActionsModal from '../../../components/accounting/AccountingRowActionsModal.vue';

const RECORD = { id: 7, concept: 'Hosting AWS', notes: 'Renovar en octubre' };

const ACTIONS = [
  { id: 'history', action: 'view', label: 'Detalle e historial' },
  { id: 'notes', action: 'notes', label: 'Ver nota' },
  { id: 'edit', action: 'edit', label: 'Editar' },
  {
    id: 'retry',
    action: 'retry',
    label: 'Reintentar el envío',
    disabled: true,
    description: 'Este envío no admite reintento.',
  },
  { id: 'delete', action: 'delete', label: 'Eliminar', danger: true },
];

function mountModal(props = {}) {
  return mount(AccountingRowActionsModal, {
    props: {
      open: true,
      record: RECORD,
      title: 'Hosting AWS',
      subtitle: 'Septiembre 2026 · $120.000',
      actions: ACTIONS,
      testIdPrefix: 'expense',
      ...props,
    },
    global: {
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        BaseModal: {
          props: ['modelValue', 'kind', 'lockScroll'],
          emits: ['close'],
          template: '<div v-if="modelValue" :data-lock-scroll="String(lockScroll)"><slot /></div>',
        },
      },
    },
  });
}

function entryIds(wrapper) {
  return wrapper.findAll('li button').map((button) => button.attributes('data-testid'));
}

describe('AccountingRowActionsModal', () => {
  it('names the record and lists its entries in the order given', () => {
    const wrapper = mountModal();
    const modal = wrapper.get('[data-testid="expense-actions-modal"]');

    expect(modal.text()).toContain('Hosting AWS');
    expect(modal.text()).toContain('Septiembre 2026 · $120.000');
    expect(entryIds(wrapper)).toEqual([
      'expense-action-history-7',
      'expense-action-notes-7',
      'expense-action-edit-7',
      'expense-action-retry-7',
      'expense-action-delete-7',
    ]);
  });

  // Bug caught: opening the next dialog in the same flush as this close made
  // the two dialogs trade focus traps and scroll locks.
  it('closes before it hands the chosen entry to the owner', async () => {
    const calls = [];
    const wrapper = mountModal({
      onClose: () => calls.push('close'),
      onSelect: (id) => calls.push(`select:${id}`),
    });

    await wrapper.get('[data-testid="expense-action-edit-7"]').trigger('click');
    await flushPromises();

    expect(calls).toEqual(['close', 'select:edit']);
  });

  it('keeps the record the owner clears on close', async () => {
    let wrapper = null;
    wrapper = mountModal({ onClose: () => wrapper.setProps({ record: null }) });

    await wrapper.get('[data-testid="expense-action-history-7"]').trigger('click');
    await flushPromises();

    expect(wrapper.emitted('select')[0]).toEqual(['history', RECORD]);
  });

  it('explains a disabled entry with its visible reason', () => {
    const wrapper = mountModal();
    const retry = wrapper.get('[data-testid="expense-action-retry-7"]');

    expect(retry.attributes('disabled')).toBeDefined();
    expect(wrapper.get(`#${retry.attributes('aria-describedby')}`).text())
      .toBe('Este envío no admite reintento.');
  });

  it('closes from its Cerrar button without choosing', async () => {
    const wrapper = mountModal();

    await wrapper.get('[data-testid="base-modal-actions"] button').trigger('click');
    await flushPromises();

    expect(wrapper.emitted('close')).toHaveLength(1);
    expect(wrapper.emitted('select')).toBeUndefined();
  });

  it('keeps the test id an owner pins on an entry', () => {
    const wrapper = mountModal({
      testIdPrefix: 'email-log',
      actions: [
        { id: 'view-body', action: 'view', label: 'Ver el correo', testId: 'email-log-view-body-3' },
      ],
    });

    expect(entryIds(wrapper)).toEqual(['email-log-view-body-3']);
    expect(wrapper.find('[data-testid="email-log-actions-modal"]').exists()).toBe(true);
  });

  it('uses the owner suffix instead of the record id', () => {
    const wrapper = mountModal({ testIdPrefix: 'card-catalog', testIdSuffix: 'card-4' });

    expect(entryIds(wrapper)).toContain('card-catalog-action-edit-card-4');
  });

  it('leaves the page scroll lock to the modal it opens above', () => {
    const wrapper = mountModal({ lockScroll: false });

    expect(wrapper.get('[data-lock-scroll]').attributes('data-lock-scroll')).toBe('false');
  });
});
