import { mount } from '@vue/test-utils';
import ConfirmationSummaryList from '../../../components/accounting/ConfirmationSummaryList.vue';

const rows = [
  { key: 'client', label: 'Cliente', value: 'Acme Soluciones' },
  { key: 'recipient', label: 'Se enviará a', value: 'pagos@acme.co' },
];

describe('ConfirmationSummaryList', () => {
  it('lists each fact with its label, in order', () => {
    const wrapper = mount(ConfirmationSummaryList, { props: { rows } });

    expect(wrapper.findAll('dt').map((term) => term.text()))
      .toEqual(['Cliente', 'Se enviará a']);
    expect(wrapper.findAll('dd').map((value) => value.text()))
      .toEqual(['Acme Soluciones', 'pagos@acme.co']);
  });

  it('gives every value its own test id under the prefix', () => {
    const wrapper = mount(ConfirmationSummaryList, {
      props: { rows, testid: 'notice' },
    });

    expect(wrapper.find('[data-testid="notice-recipient"]').text())
      .toBe('pagos@acme.co');
    expect(wrapper.find('[data-testid="notice"]').element.tagName).toBe('DL');
  });
});
