import { mount } from '@vue/test-utils';
import CostCoverage from '../../components/RequirementCalculator/CostCoverage.vue';
import messages from '../../locales/requirementCalculator/es';

const originalI18n = global.useI18n;
const measured = {
  size: 'XS', definition_digest: 'version-a', corpus_digest: 'xs-a', samples: 3, verified_cost_samples: 3,
  median_verified_cost_cop: '70000', standard_value_cop: '50000', covers_verified_median_cost: false,
  economic_status: 'provisional', last_review: null,
};
const missing = {
  ...measured, size: 'M', corpus_digest: 'm-a', samples: 0, verified_cost_samples: 0,
  median_verified_cost_cop: null, covers_verified_median_cost: null,
};

function mountCoverage() {
  return mount(CostCoverage, { props: { rows: [measured, missing] },
    global: { stubs: { BaseButton: { template: '<button><slot /></button>' } } } });
}

describe('Cobertura económica del paquete', () => {
  beforeEach(() => {
    global.useI18n = () => ({ t: (key, values = {}) => {
      const label = key.split('.').slice(1).reduce((entry, part) => entry[part], messages);
      return label.replace(/\{(\w+)\}/g, (_, field) => values[field]);
    } });
  });
  afterAll(() => { global.useI18n = originalI18n; });

  it('shows the supported deficit while a size with zero samples stays provisional', () => {
    const wrapper = mountCoverage();
    const xs = wrapper.get('[data-testid="calculator-cost-XS"]');
    const medium = wrapper.get('[data-testid="calculator-cost-M"]');

    expect(xs.text()).toContain('El valor estándar es inferior al costo mediano respaldado.');
    expect(xs.text()).toContain('70000 COP');
    expect(medium.text()).toContain('0 cierres con costo respaldado de 0');
    expect(medium.find('form').exists()).toBe(false);
    expect(wrapper.emitted('accept')).toBeUndefined();
  });

  it('sends the reviewed corpus and its written justification on explicit submission', async () => {
    const wrapper = mountCoverage();
    const xs = wrapper.get('[data-testid="calculator-cost-XS"]');
    expect(xs.get('button[type="submit"]').element.disabled).toBe(true);

    await xs.get('textarea').setValue('  Contrastado con la bitácora ficticia.  ');
    await xs.get('form').trigger('submit');

    expect(wrapper.emitted('accept')).toEqual([[measured, 'Contrastado con la bitácora ficticia.']]);
  });
});
