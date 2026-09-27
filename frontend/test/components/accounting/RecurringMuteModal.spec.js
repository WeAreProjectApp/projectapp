import { mount } from '@vue/test-utils';

import RecurringMuteModal from '~/components/accounting/RecurringMuteModal.vue';

const RECORD = {
  id: 12,
  name: 'Figma equipo',
  price: '270000.00',
  currency: 'COP',
};

function mountModal() {
  return mount(RecurringMuteModal, {
    props: { open: true, record: RECORD, saving: false },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'kind', 'size'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'error'],
          template: '<div><label>{{ label }}</label><slot /><p v-if="error">{{ error }}</p></div>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'min'],
          emits: ['update:modelValue'],
          template: '<input :type="type" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)">',
        },
        BaseSegmented: {
          props: ['modelValue', 'options'],
          emits: ['update:modelValue'],
          template: '<div><button v-for="option in options" :key="option.value" type="button" :data-value="option.value" @click="$emit(\'update:modelValue\', option.value)">{{ option.label }}</button></div>',
        },
        BaseButton: {
          props: ['type', 'disabled'],
          emits: ['click'],
          template: '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
  });
}

function isoInDays(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

describe('RecurringMuteModal', () => {
  it('defaults to a thirty-day pause', async () => {
    const wrapper = mountModal();

    expect(wrapper.get('[data-testid="recurring-mute-date"]').element.value)
      .toBe(isoInDays(30));
    await wrapper.get('form').trigger('submit');
    expect(wrapper.emitted('submit')[0][0]).toEqual({
      muted: true,
      until: isoInDays(30),
    });
  });

  it('submits an indefinite pause without a date', async () => {
    const wrapper = mountModal();

    await wrapper.get('[data-value="indefinite"]').trigger('click');
    await wrapper.get('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toEqual({ muted: true, until: null });
  });

  it('blocks a pause that expires today', async () => {
    const wrapper = mountModal();

    await wrapper.get('[data-testid="recurring-mute-date"]').setValue(isoInDays(0));
    await wrapper.get('form').trigger('submit');

    expect(wrapper.text()).toContain('Elige una fecha posterior a hoy.');
    expect(wrapper.emitted('submit')).toBeUndefined();
  });
});
