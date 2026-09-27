import { mount } from '@vue/test-utils';
import CardSnapshotFormModal from '../../../components/accounting/CardSnapshotFormModal.vue';

const CATALOG = [
  { name: 'T.C 0064', credit_limit: '8000000.00' },
  { name: 'T.C 0655', credit_limit: '5000000.00' },
];

function mountModal(props = {}) {
  return mount(CardSnapshotFormModal, {
    props: {
      open: true,
      record: null,
      saving: false,
      cards: CATALOG,
      ...props,
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'error', 'required', 'for', 'size'],
          template: '<div><label v-if="label">{{ label }}</label><slot /></div>',
        },
        BaseSelect: {
          props: ['modelValue', 'options', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)">'
            + '<option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>'
            + '</select>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'size', 'error', 'placeholder', 'disabled', 'list'],
          emits: ['update:modelValue'],
          template:
            '<input :type="type || \'text\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseCurrencyInput: {
          props: ['modelValue', 'decimals', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<input type="text" inputmode="numeric" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'rows', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'loading', 'disabled'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
  });
}

describe('CardSnapshotFormModal', () => {
  it('renders a card dropdown from the catalog and no debt input', () => {
    const wrapper = mountModal();
    const options = wrapper.findAll('option').map((option) => option.text());
    expect(options).toContain('T.C 0064');
    expect(options).toContain('T.C 0655');
    expect(wrapper.text()).not.toContain('Deuda');
    // Only the "Disponible" currency input remains.
    expect(wrapper.findAll('input[inputmode="numeric"]')).toHaveLength(1);
  });

  it('shows the computed debt preview (cupo − disponible)', async () => {
    const wrapper = mountModal();
    await wrapper.find('select').setValue('T.C 0064');
    await wrapper.find('input[inputmode="numeric"]').setValue('3000000');
    const preview = wrapper.find('[data-testid="card-snapshot-debt-preview"]');
    expect(preview.text()).toContain('Deuda:');
    expect(preview.text()).toContain('5.000.000');
  });

  it('blocks submit when available exceeds the cupo', async () => {
    const wrapper = mountModal();
    await wrapper.find('select').setValue('T.C 0655');
    await wrapper.find('input[inputmode="numeric"]').setValue('9000000');
    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')).toBeUndefined();
    expect(wrapper.text()).toContain('no puede superar el cupo');
  });

  it('emits submit without debt_amount', async () => {
    const wrapper = mountModal();
    await wrapper.find('select').setValue('T.C 0655');
    await wrapper.find('input[type="date"]').setValue('2026-07-03');
    await wrapper.find('input[inputmode="numeric"]').setValue('500000');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toEqual({
      snapshot_date: '2026-07-03',
      card_name: 'T.C 0655',
      available_amount: 500000,
      notes: '',
    });
  });

  it('keeps a legacy card name selectable in edit mode', () => {
    const wrapper = mountModal({
      record: {
        snapshot_date: '2026-06-17',
        card_name: 'T.C Vieja',
        available_amount: '413226.00',
        notes: 'Corte de junio',
      },
    });
    expect(wrapper.text()).toContain('Editar Registro de Tarjeta');
    const options = wrapper.findAll('option').map((option) => option.text());
    expect(options).toContain('T.C Vieja (fuera de catálogo)');
    expect(wrapper.find('select').element.value).toBe('T.C Vieja');
  });
});
