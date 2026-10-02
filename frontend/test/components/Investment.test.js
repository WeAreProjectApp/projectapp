import { mount } from '@vue/test-utils';

global.IntersectionObserver = jest.fn(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

jest.mock('../../composables/useSectionAnimations', () => ({
  useSectionAnimations: jest.fn(),
}));

jest.mock('../../composables/useExpirationTimer', () => ({
  useExpirationTimer: jest.fn(() => ({
    daysRemaining: require('vue').ref(30),
    urgencyLevel: require('vue').ref('normal'),
  })),
}));

jest.mock('../../composables/useAnimatedNumber', () => ({
  useAnimatedNumber: jest.fn(() => ({
    animated: require('vue').ref(0),
  })),
}));

import Investment from '../../components/BusinessProposal/Investment.vue';
import { useAnimatedNumber } from '../../composables/useAnimatedNumber';

const defaultProps = {
  title: 'Inversión y Formas de Pago',
  introText: 'Conoce el detalle de tu inversión.',
  totalInvestment: '$1.490.000',
  currency: 'COP',
  index: '9',
};

function mountInvestment(props = {}) {
  return mount(Investment, {
    props: { ...defaultProps, ...props },
    global: {
      stubs: {
        ModuleInterestsModal: {
          props: ['visible'],
          template: '<div data-testid="module-interests-modal-stub">{{ visible }}</div>',
        },
        InvestmentDetailedTeaser: { template: '<div class="teaser-stub" />' },
        Transition: true,
      },
    },
  });
}

describe('Investment', () => {
  it('renders the section element', () => {
    const wrapper = mountInvestment();

    expect(wrapper.find('section').exists()).toBe(true);
  });

  it('renders the title prop', () => {
    const wrapper = mountInvestment();

    expect(wrapper.text()).toContain('Inversión y Formas de Pago');
  });

  it('renders the intro text prop', () => {
    const wrapper = mountInvestment();

    expect(wrapper.text()).toContain('Conoce el detalle de tu inversión.');
  });

  it('shows IVA on the investment total', () => {
    const wrapper = mountInvestment();

    expect(wrapper.text()).toContain('COP + IVA');
  });

  it('opens the module interests modal from the renamed trigger', async () => {
    // Fails if the investment page still opens the removed price calculator.
    const wrapper = mountInvestment();

    const trigger = wrapper.findAll('button').find((button) => button.text() === '🧩 Explorar módulos adicionales');
    await trigger.trigger('click');

    expect(wrapper.get('[data-testid="module-interests-modal-stub"]').text()).toBe('true');
  });

  describe('hosting billing tiers', () => {
    const billingTiers = [
      { frequency: 'nine_month', months: 9, discountPercent: 40, label: 'Cada 9 meses', badge: '' },
      { frequency: 'semiannual', months: 6, discountPercent: 20, label: 'Semestral', badge: '' },
      { frequency: 'quarterly', months: 3, discountPercent: 10, label: 'Trimestral', badge: '' },
    ];

    function hostingPlanWith(percent, tiers = billingTiers) {
      return {
        title: 'Hosting',
        description: '',
        specs: [],
        hostingPercent: percent,
        billingTiers: tiers,
      };
    }

    it('renders the investment when no hosting plan is configured', () => {
      const wrapper = mountInvestment({ hostingPlan: null });

      expect(wrapper.text()).toContain('Inversión y Formas de Pago');
      expect(wrapper.find('.hosting-plan').exists()).toBe(false);
    });

    it('recomputes the tier monthly-equivalent from hostingPlan.hostingPercent', () => {
      const at30 = mountInvestment({
        totalInvestment: '$1.200.000',
        hostingPlan: hostingPlanWith(30),
      });
      const at50 = mountInvestment({
        totalInvestment: '$1.200.000',
        hostingPlan: hostingPlanWith(50),
      });

      // monthly base 1.200.000 * 30% / 12 = 30.000; quarterly 10% off -> 27.000
      expect(at30.text()).toContain('$27.000');
      // monthly base 1.200.000 * 50% / 12 = 50.000; quarterly 10% off -> 45.000
      expect(at50.text()).toContain('$45.000');
    });

    it('applies the quarterly discountPercent from billingTiers to the rendered tier', () => {
      const tiers = [
        { frequency: 'quarterly', months: 3, discountPercent: 25, label: 'Trimestral', badge: '' },
      ];
      const wrapper = mountInvestment({
        totalInvestment: '$1.200.000',
        hostingPlan: hostingPlanWith(30, tiers),
      });

      // 25% discount badge is rendered on the trimestral card
      expect(wrapper.text()).toContain('25%');
    });

    it.each(['accepted', 'rejected', 'finished'])(
      'hides the tier discount badge when proposal status is %s',
      (status) => {
        const tiers = [
          { frequency: 'quarterly', months: 3, discountPercent: 25, label: 'Trimestral', badge: '' },
        ];
        const wrapper = mountInvestment({
          totalInvestment: '$1.200.000',
          hostingPlan: hostingPlanWith(30, tiers),
          proposalStatus: status,
        });

        expect(wrapper.text()).not.toContain('25%');
      },
    );
  });

  describe('resolved-status notice suppression', () => {
    const discountProps = {
      discountPercent: 15,
      discountedInvestment: '$1.266.500',
    };

  it('renders the limited-time discount banner while the proposal is still open', () => {
    const wrapper = mountInvestment({ ...discountProps, proposalStatus: 'sent' });

    expect(wrapper.find('.discount-banner').exists()).toBe(true);
  });

  it('keeps the migrated discount reference separate from the agreed total', () => {
    // Fails if a migrated offer shows its old price as the proposal total instead of only as a discount reference.
    useAnimatedNumber.mockImplementationOnce((value) => ({ animated: require('vue').ref(value.value) }));
    const wrapper = mountInvestment({
      totalInvestment: '$1.800.000',
      paymentOptions: [],
      discountPercent: 15,
      discountedInvestment: '$1.530.000',
      discountOriginalInvestment: '$2.400.000',
      proposalStatus: 'sent',
    });

    expect(wrapper.text()).toContain('$1.800.000');
    expect(wrapper.text()).toContain('$1.530.000');
    expect(wrapper.text()).toContain('$2.400.000');
  });

    it.each(['accepted', 'rejected', 'finished'])(
      'hides the limited-time discount banner when status is %s',
      (status) => {
        const wrapper = mountInvestment({ ...discountProps, proposalStatus: status });

        expect(wrapper.find('.discount-banner').exists()).toBe(false);
      },
    );
  });

  // Bug fix: "Tres pagos flexibles" amounts must derive from the LABEL percent
  // applied to the currently displayed total — not from the stored description
  // amount × ratio (which double-scaled when the backend rebuilds descriptions
  // at effective×pct and the frontend then multiplies by effective/base).
  describe('payment options — split derived from label percent × displayed total', () => {
    const splitOptions = [
      { label: '40% al firmar el contrato ✍️', description: '$2.160.000 COP' },
      { label: '30% al aprobar el diseño final ✅', description: '$1.620.000 COP' },
      { label: '30% al desplegar el sitio web 🚀', description: '$1.620.000 COP' },
    ];

    it('renders amounts as effectiveTotal × labelPercent (sums to effectiveTotal)', () => {
      const wrapper = mountInvestment({
        totalInvestment: '$5.400.000',
        effectiveTotal: 9_720_000, // 5.400.000 × 1.8 (e.g. AI module 80%)
        paymentOptions: splitOptions,
      });
      const text = wrapper.text();
      // 9.720.000 × 0.4 = 3.888.000
      expect(text).toContain('$3.888.000');
      // 9.720.000 × 0.3 = 2.916.000
      expect(text).toContain('$2.916.000');
      expect(text).toContain('$3.888.000 COP + IVA');
      expect(text.match(/\$2\.916\.000 COP \+ IVA/g)).toHaveLength(2);
      // 3.888.000 + 2.916.000 + 2.916.000 === 9.720.000 (effective)
    });

    it('does not double-scale when stored descriptions are already effective-derived (Bug 87)', () => {
      // This is the production state for proposal 87 after a backend
      // _resync_investment_from_modules: descriptions saved at effective×pct.
      const storedAtEffective = [
        { label: '40% al firmar', description: '$3.888.000 COP' }, // already effective×0.4
        { label: '30% diseño',     description: '$2.916.000 COP' },
        { label: '30% final',      description: '$2.916.000 COP' },
      ];
      const wrapper = mountInvestment({
        totalInvestment: '$5.400.000',
        effectiveTotal: 9_720_000,
        paymentOptions: storedAtEffective,
      });
      const text = wrapper.text();
      // Same correct outputs as the base-derived case — no dependency on stored amount.
      expect(text).toContain('$3.888.000');
      expect(text).toContain('$2.916.000');
      // Old buggy behavior would have scaled $3.888.000 by 1.8 → $6.998.400.
      expect(text).not.toContain('$6.998.400');
    });

    it('falls back to base when no effectiveTotal prop is provided', () => {
      const wrapper = mountInvestment({
        totalInvestment: '$5.400.000',
        paymentOptions: splitOptions,
      });
      const text = wrapper.text();
      // 5.400.000 × 0.4 = 2.160.000
      expect(text).toContain('$2.160.000');
      // 5.400.000 × 0.3 = 1.620.000
      expect(text).toContain('$1.620.000');
    });

    it('leaves descriptions untouched when label has no parseable percent', () => {
      const wrapper = mountInvestment({
        totalInvestment: '$5.400.000',
        effectiveTotal: 9_720_000,
        paymentOptions: [
          { label: 'Cuota inicial fija', description: '$100.000 COP' },
        ],
      });
      // Free-form payment option should keep its original amount.
      expect(wrapper.text()).toContain('$100.000');
    });

    it('renders each complete tax-qualified amount in its dedicated value element', () => {
      const wrapper = mountInvestment({
        totalInvestment: '$280.000.000',
        paymentOptions: [
          { label: '40% al firmar', description: '$112.000.000 COP + IVA' },
          { label: '30% al aprobar diseño', description: '$84.000.000 COP + IVA' },
          { label: '30% al aprobar QA', description: '$84.000.000 COP + IVA' },
        ],
      });

      expect(wrapper.findAll('[data-testid="payment-option-amount"]').map(node => node.text())).toEqual([
        '$112.000.000 COP + IVA',
        '$84.000.000 COP + IVA',
        '$84.000.000 COP + IVA',
      ]);
    });
  });

  describe('hosting: nine-month tier, free month, renewal', () => {
    it('renders the nine-month 40% tier by default', () => {
      const wrapper = mountInvestment();
      expect(wrapper.text()).toContain('Cada 9 meses');
      expect(wrapper.text()).toContain('40%');
    });

    it('renders the free-month gift bucket by default', () => {
      const wrapper = mountInvestment();
      expect(wrapper.text()).toContain('mes de hosting gratis');
    });

    it('hides the free-month bucket when freeMonths is 0', () => {
      // Backward compatibility: content written before freeMonthsVisible
      // existed used a zero count as the way to hide the block.
      const wrapper = mountInvestment({
        hostingPlan: { title: 'Hosting', hostingPercent: 80, freeMonths: 0 },
      });
      expect(wrapper.text()).not.toContain('mes de hosting gratis');
      // The rest of the hosting subsection is untouched by the gate.
      expect(wrapper.text()).toContain('Hosting');
    });

    it('hides the bucket when freeMonthsVisible is false despite a count', () => {
      const wrapper = mountInvestment({
        hostingPlan: {
          title: 'Hosting Administrado', hostingPercent: 80,
          freeMonths: 3, freeMonthsVisible: false,
          freeMonthNote: 'Tres meses de regalo.',
        },
      });
      // The surrounding subsection must survive — only the gift is gated.
      expect(wrapper.text()).toContain('Hosting Administrado');
      expect(wrapper.text()).not.toContain('Tres meses de regalo.');
      expect(wrapper.text()).not.toContain('meses de hosting gratis');
    });

    it('shows the bucket when freeMonthsVisible is true and the count is 0', () => {
      const wrapper = mountInvestment({
        hostingPlan: {
          title: 'Hosting', hostingPercent: 80,
          freeMonths: 0, freeMonthsVisible: true,
          freeMonthNote: 'Hosting gratis hasta la entrega.',
        },
      });
      expect(wrapper.text()).toContain('Hosting gratis hasta la entrega.');
      // With no number to announce, the title drops it instead of lying.
      expect(wrapper.text()).toContain('Hosting gratis');
      expect(wrapper.text()).not.toContain('0 meses de hosting gratis');
    });

    it('puts the real count in the title instead of a fixed "1 mes"', () => {
      const wrapper = mountInvestment({
        hostingPlan: {
          title: 'Hosting', hostingPercent: 80, freeMonths: 3,
        },
      });
      expect(wrapper.text()).toContain('3 meses de hosting gratis');
    });

    it('never renders renewal conditions in the web view (PDF-only)', () => {
      const wrapper = mountInvestment({
        hostingPlan: {
          title: 'Hosting',
          hostingPercent: 80,
          renewalNote: 'Primer parrafo de renovacion.\n\nSegundo parrafo.',
        },
      });
      // Renewal terms live only in the generated PDF, not the public web view.
      expect(wrapper.text()).not.toContain('Renovaciones');
      expect(wrapper.text()).not.toContain('Primer parrafo de renovacion.');
    });
  });
});
