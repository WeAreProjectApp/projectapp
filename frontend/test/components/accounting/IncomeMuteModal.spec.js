/**
 * Tests for IncomeMuteModal.
 *
 * Covers what the operator actually decides here: silence until a date (the
 * default, so nothing gets silenced and forgotten) or indefinitely, and the
 * validation that stops a resume date that would expire the moment it is set.
 */
import { mount } from '@vue/test-utils';
import IncomeMuteModal from '../../../components/accounting/IncomeMuteModal.vue';

const RECORD = { id: 7, concept: 'Kore - Hosting julio', total_amount: '1000000.00' };

function mountModal(props = {}) {
  return mount(IncomeMuteModal, {
    props: { open: true, record: RECORD, saving: false, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'kind', 'size', 'titleId'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'error', 'required'],
          template:
            '<div><label v-if="label">{{ label }}</label><slot /><p v-if="error">{{ error }}</p></div>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'min'],
          emits: ['update:modelValue'],
          template:
            '<input :type="type || \'text\'" :min="min" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSegmented: {
          props: ['modelValue', 'options', 'size'],
          emits: ['update:modelValue'],
          template:
            '<div><button v-for="o in options" :key="o.value" type="button" :data-value="o.value" @click="$emit(\'update:modelValue\', o.value)">{{ o.label }}</button></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'disabled'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
  });
}

const dateInput = (wrapper) => wrapper.find('[data-testid="income-mute-date"]');
const submit = (wrapper) => wrapper.find('[data-testid="income-mute-submit"]');
const modeButton = (wrapper, value) =>
  wrapper.find(`[data-testid="income-mute-mode"] [data-value="${value}"]`);

function isoInDays(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

describe('IncomeMuteModal', () => {
  it('opens on "hasta una fecha" with a resume date already filled in', async () => {
    const wrapper = mountModal();
    expect(dateInput(wrapper).element.value).toBe(isoInDays(30));

    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')[0][0]).toEqual({
      muted: true,
      until: isoInDays(30),
    });
  });

  it('submits an indefinite mute with no resume date', async () => {
    const wrapper = mountModal();
    await modeButton(wrapper, 'indefinite').trigger('click');

    expect(dateInput(wrapper).exists()).toBe(false);
    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')[0][0]).toEqual({ muted: true, until: null });
  });

  it('blocks a resume date of today, which would expire on arrival', async () => {
    const wrapper = mountModal();
    await dateInput(wrapper).setValue(isoInDays(0));

    expect(submit(wrapper).element.disabled).toBe(true);
    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')).toBeUndefined();
  });

  it('blocks an empty resume date and says so', async () => {
    const wrapper = mountModal();
    await dateInput(wrapper).setValue('');

    expect(wrapper.text()).toContain('Elige la fecha en que se reanudan los avisos.');
    expect(submit(wrapper).element.disabled).toBe(true);
  });

  it('switching to indefinite clears the blocked state left by an empty date', async () => {
    const wrapper = mountModal();
    await dateInput(wrapper).setValue('');
    await modeButton(wrapper, 'indefinite').trigger('click');

    expect(submit(wrapper).element.disabled).toBe(false);
    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')[0][0]).toEqual({ muted: true, until: null });
  });
});
