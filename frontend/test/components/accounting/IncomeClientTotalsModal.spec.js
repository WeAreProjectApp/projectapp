import { mount } from '@vue/test-utils';
import IncomeClientTotalsModal from '~/components/accounting/IncomeClientTotalsModal.vue';
import { NO_CLIENT_KEY } from '~/utils/incomeClients';

// 2 incomes for client A (1 expected + 1 liquid, so billed/collected never
// double-count) plus 1 unassigned expected income.
const ROWS = [
  {
    id: 1,
    kind: 'expected',
    client: 5,
    client_name: 'Acme SAS',
    total_amount: '1000000.00',
    pending_amount: '400000.00',
  },
  {
    id: 2,
    kind: 'liquid',
    client: 5,
    client_name: 'Acme SAS',
    total_amount: '600000.00',
    pending_amount: null,
  },
  {
    id: 3,
    kind: 'expected',
    client: null,
    client_name: null,
    total_amount: '200000.00',
    pending_amount: '200000.00',
  },
];

// 1 active hosting linked to client A plus 1 active hosting with no client.
const HOSTING_ROWS = [
  {
    id: 10,
    client: 5,
    client_name: 'Acme SAS',
    is_active: true,
    monthly_value: '80000.00',
    total_paid: '960000.00',
    cycles_count: 12,
  },
  {
    id: 11,
    client: null,
    client_name: null,
    is_active: true,
    monthly_value: '45000.00',
    total_paid: '90000.00',
    cycles_count: 2,
  },
];

function mountModal(props = {}) {
  return mount(IncomeClientTotalsModal, {
    props: {
      open: true,
      rows: ROWS,
      hostingRows: HOSTING_ROWS,
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
        BaseButton: {
          props: ['variant', 'type'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
  });
}

describe('IncomeClientTotalsModal', () => {
  it('renders the income table footer sums and marks the unassigned row "por completar"', () => {
    const wrapper = mountModal();

    // Falls if the groupByClient/sumClientGroups wiring breaks and the
    // footer shows the wrong billed/pending totals: billed = 1,000,000
    // (expected) + 200,000 (unassigned expected) = 1,200,000; pending =
    // 400,000 + 200,000 = 600,000 (the liquid row never adds to pending).
    expect(wrapper.find('[data-testid="income-client-billed-sum"]').text())
      .toBe('$1.200.000 COP');
    expect(wrapper.find('[data-testid="income-client-pending-sum"]').text())
      .toBe('$600.000 COP');

    const unassignedRow = wrapper.find(`[data-testid="income-client-row-${NO_CLIENT_KEY}"]`);
    expect(unassignedRow.text()).toContain('por completar');
  });

  it('renders the hosting table footer sum and marks the unlinked row "por vincular"', () => {
    const wrapper = mountModal();

    // Falls if the component-local hostingSums reduce (unlike the income
    // side's tested sumClientGroups) stops summing every bucket — e.g. drops
    // the unassigned group — silently undercounting the standing monthly
    // cost: 80,000 (client A) + 45,000 (unlinked) = 125,000.
    expect(wrapper.find('[data-testid="hosting-client-monthly-sum"]').text())
      .toBe('$125.000 COP');

    const unlinkedRow = wrapper.find(`[data-testid="hosting-client-row-${NO_CLIENT_KEY}"]`);
    expect(unlinkedRow.text()).toContain('por vincular');
  });
});
