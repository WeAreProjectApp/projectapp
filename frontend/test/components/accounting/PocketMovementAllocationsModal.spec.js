import { mount } from '@vue/test-utils';
import PocketMovementAllocationsModal from '../../../components/accounting/PocketMovementAllocationsModal.vue';

/**
 * The read-only reparto of an abono: which incomes one pocket movement
 * covered and with how much each. Fed from two directions — the pocket
 * ledger row and, since the income detail learned to name its movement, from
 * the income side too — so the shape it tolerates is a contract.
 */

function movement(overrides = {}) {
  return {
    id: 90,
    concept: 'Abono Kore',
    movement_date: '2026-08-15',
    amount: '800000.00',
    allocations: [
      { income_id: 21, expected_income_id: 11, concept: 'Kore - Fase 2', amount: '500000.00' },
      { income_id: 22, expected_income_id: 12, concept: 'Kore - Fase 3', amount: '300000.00' },
    ],
    ...overrides,
  };
}

function mountModal(props = {}) {
  return mount(PocketMovementAllocationsModal, {
    props: { open: true, movement: movement(), ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size', 'titleId'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'disabled'],
          // Declared on purpose: without it the listener is applied twice —
          // once bound, once via native attribute fallthrough — and a single
          // click emits two events.
          emits: ['click'],
          template: '<button type="button" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
  });
}

const rows = (wrapper) => wrapper.findAll('[data-testid="pocket-allocation-row"]');
const total = (wrapper) => wrapper.find('[data-testid="pocket-allocations-total"]').text();

describe('PocketMovementAllocationsModal — the reparto is the whole point', () => {
  it('lists one row per allocation, in order, with its concept and amount', () => {
    const wrapper = mountModal();

    expect(rows(wrapper)).toHaveLength(2);
    expect(rows(wrapper)[0].text()).toContain('Kore - Fase 2');
    expect(rows(wrapper)[0].text()).toContain('500.000');
    expect(rows(wrapper)[1].text()).toContain('Kore - Fase 3');
    expect(rows(wrapper)[1].text()).toContain('300.000');
  });

  it('totals the allocations, not the movement amount', () => {
    // The two deliberately disagree: a movement of 900k whose reparto only
    // accounts for 800k. Reading `amount` here instead of summing would hide
    // exactly that — an abono booked for more than it imputed.
    const wrapper = mountModal({
      movement: movement({
        amount: '900000.00',
        allocations: [
          { income_id: 21, concept: 'Kore - Fase 2', amount: '500000.00' },
          { income_id: 22, concept: 'Kore - Fase 3', amount: '300000.00' },
        ],
      }),
    });

    expect(total(wrapper)).toContain('800.000');
  });

  it('sums the string amounts numerically instead of concatenating them', () => {
    // The API sends decimals as strings, so this is the real contract.
    const wrapper = mountModal();

    expect(total(wrapper)).toContain('800.000');
    expect(total(wrapper)).not.toContain('500000.00300000.00');
  });

  it('names the movement it is breaking down: concept, date and amount', () => {
    const wrapper = mountModal();
    const subtitle = wrapper.find('[data-testid="pocket-allocations-modal"] p').text();

    expect(subtitle).toContain('Abono Kore');
    expect(subtitle).toContain('2026');
    expect(subtitle).toContain('800.000');
  });

  it('renders an empty reparto instead of throwing when there is no movement', () => {
    const wrapper = mountModal({ movement: null });

    expect(rows(wrapper)).toHaveLength(0);
    expect(total(wrapper)).toContain('0');
  });

  it('survives a payload whose allocations are missing or not a list', () => {
    const wrapper = mountModal({ movement: movement({ allocations: undefined }) });

    expect(rows(wrapper)).toHaveLength(0);
    expect(total(wrapper)).toContain('0');
  });

  it('emits close exactly once when Cerrar is pressed', async () => {
    const wrapper = mountModal();

    await wrapper.find('button').trigger('click');

    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('renders the reparto only once it is opened', async () => {
    const wrapper = mountModal({ open: false });
    expect(rows(wrapper)).toHaveLength(0);

    await wrapper.setProps({ open: true });

    expect(rows(wrapper)).toHaveLength(2);
    expect(total(wrapper)).toContain('800.000');
  });
});
