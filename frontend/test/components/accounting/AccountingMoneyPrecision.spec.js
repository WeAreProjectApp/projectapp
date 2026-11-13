import { mount } from '@vue/test-utils';
import BaseResponsiveTable from '~/components/base/BaseResponsiveTable.vue';
import IncomeGroupedTable from '~/components/accounting/IncomeGroupedTable.vue';

const rows = [{ id: 1, concept: 'Ingreso ficticio', total_amount: '119.03' }];
const columns = [
  { key: 'concept', label: 'Concepto', responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' } },
  { key: 'total_amount', label: 'Total', format: 'money', moneyDecimals: 'auto', responsive: { compact: 'group', portrait: 'group', landscape: 'keep' } },
];

describe('Income display precision', () => {
  it('keeps cents in the classic table cell', () => {
    const wrapper = mount(BaseResponsiveTable, { props: { columns, rows, showActions: false } });
    expect(wrapper.get('[data-testid="accounting-row-1"]').text()).toContain('$119,03 COP');
  });

  it('keeps cents in compact grouped details', () => {
    const wrapper = mount(BaseResponsiveTable, { props: { columns, rows, showActions: false } });
    expect(wrapper.get('[data-testid="responsive-group-compact"]').text()).toContain('$119,03 COP');
  });

  it('retains whole-unit formatting for columns that do not opt in', () => {
    const wrapper = mount(BaseResponsiveTable, {
      props: { columns: [{ key: 'total_amount', label: 'Total', format: 'money' }], rows, showActions: false },
    });
    expect(wrapper.get('[data-testid="accounting-row-1"]').text()).toContain('$119 COP');
  });

  it('keeps cents in a grouped income row', () => {
    const wrapper = mount(IncomeGroupedTable, {
      props: {
        columns, showActions: false, moneyDecimals: 'auto',
        groups: [{ id: 1, name: 'Cliente ficticio', count: 1, billed: 119.03, pending: 119.03, collected: 0, rows }],
      },
    });
    expect(wrapper.get('[data-testid="accounting-row-1"]').text()).toContain('$119,03 COP');
  });

  it('keeps cents in the group subtotal', () => {
    const wrapper = mount(IncomeGroupedTable, {
      props: {
        columns, showActions: false, moneyDecimals: 'auto',
        groups: [{ id: 1, name: 'Cliente ficticio', count: 1, billed: 119.03, pending: 119.03, collected: 0, rows }],
      },
    });
    expect(wrapper.get('[data-testid="income-group-1"]').text()).toContain('$119,03 COP');
  });
});
