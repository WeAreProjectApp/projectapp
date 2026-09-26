/**
 * Tests for AccountingRowActionsButton: the kebab that alone fills an
 * accounting table's leading track and only opens the row's actions menu.
 */
import { mount } from '@vue/test-utils';
import AccountingRowActionsButton from '../../../components/accounting/AccountingRowActionsButton.vue';

const BaseButtonStub = {
  props: ['variant', 'size', 'iconOnly', 'disabled', 'loading', 'type'],
  emits: ['click'],
  template:
    '<button :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
};

function mountButton(props = {}) {
  return mount(AccountingRowActionsButton, {
    props: { label: 'Acciones de Hosting AWS', testId: 'expense-actions-7', ...props },
    global: { stubs: { BaseButton: BaseButtonStub } },
  });
}

describe('AccountingRowActionsButton', () => {
  it('names its row and asks the owner to open the menu', async () => {
    const wrapper = mountButton();
    const button = wrapper.get('[data-testid="expense-actions-7"]');

    expect(button.attributes('aria-label')).toBe('Acciones de Hosting AWS');
    await button.trigger('click');

    expect(wrapper.emitted('open')).toHaveLength(1);
  });

  // The 56px track holds one 44px target, never a second control beside it.
  it('keeps the coarse-pointer target', () => {
    const wrapper = mountButton();

    expect(wrapper.get('[data-testid="expense-actions-7"]').classes())
      .toEqual(expect.arrayContaining(['h-11', 'w-11', 'shrink-0']));
  });

  it('refuses a second click while an action of its menu is working', async () => {
    const wrapper = mountButton({ busy: true, busyLabel: 'Reintentando' });
    const button = wrapper.get('[data-testid="expense-actions-7"]');

    expect(button.attributes('aria-label')).toBe('Reintentando');
    expect(button.attributes('disabled')).toBeDefined();

    await button.trigger('click');

    expect(wrapper.emitted('open')).toBeUndefined();
  });
});
