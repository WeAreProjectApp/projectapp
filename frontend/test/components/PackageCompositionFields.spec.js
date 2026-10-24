import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

import PackageCompositionFields from '../../components/hour-packages/PackageCompositionFields.vue';
import { useHourPackagesStore } from '../../stores/hour_packages';

const SETTINGS = {
  xs_price_cop: 50000, s_price_cop: 125000, m_price_cop: 360000,
  exchange_rate: 4000, foreign_multiplier: 1.4, usa_multiplier: 1.8,
};
const MODEL = { nationality: 'COL', xs_count: 30, s_count: 20, m_count: 10, validity_months: 12, discount_percent: 25 };

async function mountFields({ modelValue = MODEL, settings = SETTINGS } = {}) {
  setActivePinia(createPinia());
  const store = useHourPackagesStore();
  store.settings = settings;
  store.fetchSettings = jest.fn().mockResolvedValue({ success: true });
  const wrapper = mount(PackageCompositionFields, { props: { modelValue } });
  await flushPromises();
  return wrapper;
}

describe('PackageCompositionFields', () => {
  // Falla si editar XS sustituye el formulario y elimina la nacionalidad o las demás tallas.
  it('emits a complete package model when the XS allowance changes', async () => {
    const wrapper = await mountFields();
    await wrapper.get('[data-testid="package-xs-count"]').setValue('40');
    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      nationality: 'COL', xs_count: 40, s_count: 20, m_count: 10, validity_months: 12, discount_percent: 25,
    });
  });

  // Falla si un paquete sin cupos parece válido y se puede cotizar.
  it('shows the exact allowance error when every size is zero', async () => {
    const wrapper = await mountFields({ modelValue: { ...MODEL, xs_count: 0, s_count: 0, m_count: 0 } });
    expect(wrapper.get('[role="alert"]').text()).toBe('Incluye al menos un cupo XS, S o M.');
  });

  // Falla si el precio COP ignora una talla, el descuento o el ahorro del paquete.
  it('renders the Colombian reference, savings, and total for the configured composition', async () => {
    const wrapper = await mountFields();
    expect(wrapper.get('[data-testid="package-price-preview"]').text())
      .toBe('Referencia: $7.600.000 COP · Ahorro: $1.900.000 COPTotal: $5.700.000 COP + IVA');
  });

  // Falla si se invierte el factor internacional o se usa el mercado equivocado para el total USD.
  it.each([
    ['EXT', '$2,660 USD', '$665 USD', '$1,995 USD'],
    ['USA', '$3,420 USD', '$855 USD', '$2,565 USD'],
  ])('uses the correct multiplier for %s packages', async (nationality, reference, savings, total) => {
    const wrapper = await mountFields({ modelValue: { ...MODEL, nationality } });
    expect(wrapper.get('[data-testid="package-price-preview"]').text())
      .toBe(`Referencia: ${reference} · Ahorro: ${savings}Total: ${total} + Tax`);
  });

  // Falla si el ahorro resta importes sin redondear y desincroniza el total mostrado al cliente.
  it('derives EXT savings from the individually rounded USD reference and total', async () => {
    const wrapper = await mountFields({
      modelValue: { ...MODEL, nationality: 'EXT', xs_count: 30, s_count: 0, m_count: 0, discount_percent: 10 },
      settings: { ...SETTINGS, exchange_rate: 3900 },
    });

    expect(wrapper.get('[data-testid="package-price-preview"]').text())
      .toBe('Referencia: $538.46 USD · Ahorro: $53.84 USDTotal: $484.62 USD + Tax');
  });

  // Falla si una tasa contable inválida presenta USD 0 como si fuera una cotización válida.
  it('shows the accounting-rate error instead of a USD preview when the exchange rate is zero', async () => {
    const wrapper = await mountFields({ modelValue: { ...MODEL, nationality: 'EXT' }, settings: { ...SETTINGS, exchange_rate: 0 } });
    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo calcular el precio. Revisa la configuración y la tasa de Contabilidad.');
  });
});
