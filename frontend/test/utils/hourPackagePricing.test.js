import {
  bestValuePackageId,
  effectiveRate,
  formatPackageMoney,
  totalPrice,
  composition,
} from '../../utils/hourPackagePricing';

const pkg = (overrides = {}) => ({
  id: 1,
  hours: 10,
  hourly_rate: '100000',
  discount_percent: '20',
  is_active: true,
  ...overrides,
});

describe('hourPackagePricing', () => {
  it('applies the discount to the hourly rate', () => {
    expect(effectiveRate(pkg())).toBe(80000);
  });

  it('treats a missing discount as zero', () => {
    expect(effectiveRate(pkg({ discount_percent: undefined }))).toBe(100000);
  });

  it('multiplies hours by the effective rate for the total', () => {
    expect(totalPrice(pkg())).toBe(800000);
  });

  // Falla si una oferta por requerimientos recalcula el total redondeado que el backend ya congeló.
  it('uses the served total for requirement packages', () => {
    expect(totalPrice({
      pricing_model: 'requirements', xs_count: 30, s_count: 0, m_count: 0,
      reference_price: '538.46', discount_percent: '10', total_price: '484.62',
    })).toBe(484.62);
  });

  it('formats COP without decimals using dot grouping', () => {
    expect(formatPackageMoney(1234567.8, 'COP')).toBe('$1.234.568 COP');
  });

  it('formats USD keeping cents', () => {
    expect(formatPackageMoney(1234.56, 'USD')).toBe('$1,234.56 USD');
  });

  it('returns null as best value when no active discounted packages exist', () => {
    // quality: allow-negation-only (null is the public result when no package qualifies for highlighting)
    expect(bestValuePackageId([
      pkg({ discount_percent: '0' }),
      pkg({ id: 2, is_active: false }),
    ])).toBeNull();
  });

  it('picks the active package with the lowest effective rate', () => {
    expect(bestValuePackageId([
      pkg({ id: 1, discount_percent: '10' }),
      pkg({ id: 2, discount_percent: '30' }),
      pkg({ id: 3, discount_percent: '25', is_active: false }),
    ])).toBe(2);
  });

  // Falla si un paquete inactivo con más descuento se marca como la mejor oferta.
  it('picks the active requirement package with the largest discount', () => {
    expect(bestValuePackageId([
      { id: 1, pricing_model: 'requirements', discount_percent: '10', is_active: true },
      { id: 2, pricing_model: 'requirements', discount_percent: '15', is_active: true },
      { id: 3, pricing_model: 'requirements', discount_percent: '25', is_active: true },
      { id: 4, pricing_model: 'requirements', discount_percent: '35', is_active: false },
    ])).toBe(3);
  });

  // Falla si una tarjeta de requerimientos pierde una talla al resumir su composición.
  it('formats the three requirement allowances in their public order', () => {
    expect(composition({ xs_count: 30, s_count: 20, m_count: 10 })).toBe('30 XS · 20 S · 10 M');
  });
});
