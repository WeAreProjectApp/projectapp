import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

import ProposalHourRateTab from '../../components/panel/proposal/ProposalHourRateTab.vue';
import { useProposalStore } from '../../stores/proposals';
import { useHourPackagesStore } from '../../stores/hour_packages';

const mockNotify = { error: jest.fn(), success: jest.fn(), warning: jest.fn() };
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));

const CATALOG = [
  { id: 7, name_es: 'Ágil', name_en: 'Agile', note_es: 'Ideal para ajustes puntuales.', note_en: '', xs_count: 30, s_count: 0, m_count: 0, validity_months: 12, reference_price: 1500000, discount_percent: 10, total_price: 1350000, is_active: true },
  { id: 8, name_es: 'Pro', name_en: 'Pro', note_es: 'Para evolución continua.', note_en: '', xs_count: 30, s_count: 20, m_count: 0, validity_months: 12, reference_price: 4000000, discount_percent: 15, total_price: 3400000, is_active: true },
];
const PROPOSAL = { id: 3, nationality: 'COL', language: 'es', status: 'draft' };

function buildSection(content = {}) {
  return { id: 42, section_type: 'commercial_conditions', is_enabled: true, content_json: {
    scopeTitle: 'Alcance acordado', pricingModel: 'requirements', hourPackagesMode: 'auto',
    hourPackagesEnabled: true, packages: [], ...content,
  } };
}

async function mountTab({ content = {}, catalog = CATALOG, fetchResult = { success: true } } = {}) {
  setActivePinia(createPinia());
  const proposalStore = useProposalStore();
  const packageStore = useHourPackagesStore();
  proposalStore.currentProposal = { ...PROPOSAL, sections: [buildSection(content)] };
  proposalStore.updateSection = jest.fn().mockResolvedValue({ success: true });
  packageStore.fetchAdminPackages = jest.fn().mockImplementation(async () => {
    packageStore.packages = catalog;
    return fetchResult;
  });
  const wrapper = mount(ProposalHourRateTab, { props: { proposal: PROPOSAL } });
  await flushPromises();
  return { wrapper, proposalStore };
}

const savedJson = (store) => store.updateSection.mock.calls[0][1].content_json;

describe('ProposalHourRateTab', () => {
  afterEach(() => jest.clearAllMocks());

  // Falla si el catálogo vuelve a mostrar horas en lugar de composición, vigencia y precio congelable.
  it('shows the active requirements catalog with composition, twelve-month validity, and package prices', async () => {
    const { wrapper } = await mountTab();
    const agile = wrapper.get('[data-testid="requirement-package-0"]').text();
    const pro = wrapper.get('[data-testid="requirement-package-1"]').text();
    expect(agile).toContain('30 XS · 0 S · 0 M');
    expect(agile).toContain('12 meses desde el pago');
    expect(agile).toContain('$1.500.000 COP');
    expect(agile).toContain('$1.350.000 COP + IVA');
    expect(pro).toContain('$3.400.000 COP + IVA');
    expect(wrapper.text()).not.toContain('Tarifa por hora');
  });

  // Falla si el modo manual reemplaza al cargar la composición negociada por el catálogo actual.
  it('preserves then saves manual requirement edits without losing the commercial scope', async () => {
    const { wrapper, proposalStore } = await mountTab({ content: { hourPackagesMode: 'manual', packages: [{ id: 91, name: 'Negociado', note: '', xsCount: 7, sCount: 2, mCount: 0, validityMonths: 12, referencePrice: 700000, discountPercent: 0, totalPrice: 700000 }] } });
    expect(wrapper.get('input[aria-label="Nombre del paquete 1"]').element.value).toBe('Negociado');
    expect(wrapper.get('input[aria-label="Cupos XS del paquete 1"]').element.value).toBe('7');
    expect(wrapper.get('input[aria-label="Referencia del paquete 1"]').element.value).toBe('700.000');
    await wrapper.get('[data-testid="packages-mode"]').setValue('auto');
    await wrapper.get('[data-testid="packages-mode"]').setValue('manual');
    expect(wrapper.get('input[aria-label="Nombre del paquete 1"]').element.value).toBe('Negociado');
    await wrapper.get('input[aria-label="Nombre del paquete 1"]').setValue('Ágil prioritario');
    await wrapper.get('input[aria-label="Cupos XS del paquete 1"]').setValue('40');
    await wrapper.get('input[aria-label="Referencia del paquete 1"]').setValue('1600000');
    await wrapper.get('[data-testid="hour-rate-save"]').trigger('click');
    await flushPromises();
    expect(savedJson(proposalStore)).toMatchObject({
      pricingModel: 'requirements', hourPackagesMode: 'manual', currency: 'COP', scopeTitle: 'Alcance acordado',
      packages: [expect.objectContaining({ name: 'Ágil prioritario', xsCount: 40, referencePrice: 1600000 })],
    });
  });

  // Falla si ocultar el bloque del PDF borra la composición o deja el flag de impresión activo.
  it('saves the PDF toggle as disabled without discarding the automatic catalog', async () => {
    const { wrapper, proposalStore } = await mountTab();
    await wrapper.get('[aria-label="Incluir paquetes de requerimientos en el PDF"]').setValue(false);
    await flushPromises();
    await wrapper.get('[data-testid="hour-rate-save"]').trigger('click');
    await flushPromises();
    expect(savedJson(proposalStore).hourPackagesEnabled).toBe(false);
    expect(savedJson(proposalStore).packages[0]).toMatchObject({ name: 'Ágil', xsCount: 30 });
  });

  // Falla si abrir una propuesta histórica convierte horas sin la revisión explícita del borrador.
  it('keeps legacy hours as a snapshot until a draft adopts the requirements catalog', async () => {
    const { wrapper, proposalStore } = await mountTab({ content: { pricingModel: 'hours', packages: [{ name: 'Bolsa histórica', hours: 20 }] } });
    expect(wrapper.get('[data-testid="packages-legacy-notice"]').text()).toContain('condiciones históricas de horas');
    await wrapper.get('[data-testid="packages-adopt"]').trigger('click');
    await flushPromises();
    expect(proposalStore.updateSection).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="requirement-package-0"]').text()).toContain('30 XS · 0 S · 0 M');
    await wrapper.get('[data-testid="hour-rate-save"]').trigger('click');
    await flushPromises();
    expect(savedJson(proposalStore).pricingModel).toBe('requirements');
  });

  // Falla si una oferta emitida reemplaza sus precios históricos con los precios actuales del catálogo.
  it('shows frozen requirement prices until refresh is explicitly saved', async () => {
    const { wrapper, proposalStore } = await mountTab({ content: { packagesFrozen: true, packages: [{ id: 7, name: 'Ágil histórico', note: '', xsCount: 30, sCount: 0, mCount: 0, validityMonths: 12, referencePrice: 1400000, discountPercent: 10, totalPrice: 1260000 }] } });
    expect(wrapper.get('[data-testid="requirement-package-0"]').text()).toContain('Ágil histórico');
    expect(wrapper.get('[data-testid="requirement-package-0"]').text()).toContain('$1.260.000 COP + IVA');
    await wrapper.get('[data-testid="packages-reset"]').trigger('click');
    await wrapper.get('[data-testid="hour-rate-save"]').trigger('click');
    await flushPromises();
    expect(savedJson(proposalStore).packagesFrozen).toBe(false);
    expect(savedJson(proposalStore).packages[0]).toMatchObject({ name: 'Ágil', xsCount: 30 });
  });

  // Falla si un rechazo del servidor aparenta guardado y borra la edición manual en pantalla.
  it('keeps a rejected manual edit visible and reports the save failure', async () => {
    const { wrapper, proposalStore } = await mountTab({ content: { hourPackagesMode: 'manual', packages: [{ id: 7, name: 'Ágil', note: '', xsCount: 30, sCount: 0, mCount: 0, validityMonths: 12, referencePrice: 1500000, discountPercent: 10, totalPrice: 1350000 }] } });
    proposalStore.updateSection.mockResolvedValue({ success: false });
    await wrapper.get('input[aria-label="Nombre del paquete 1"]').setValue('Ágil conservado');
    await wrapper.get('[data-testid="hour-rate-save"]').trigger('click');
    await flushPromises();
    expect(wrapper.get('input[aria-label="Nombre del paquete 1"]').element.value).toBe('Ágil conservado');
    expect(mockNotify.error).toHaveBeenCalledWith('No se pudieron guardar los paquetes. Revisa cupos, vigencia, referencia y descuento.');
  });

  // Falla si un catálogo que no pudo cargarse permite guardar una selección automática vacía.
  it('blocks automatic saving when the catalog request fails', async () => {
    const { wrapper } = await mountTab({ fetchResult: { success: false } });
    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo cargar el catálogo. Revisa la configuración y la tasa de cambio.');
    expect(wrapper.get('[data-testid="hour-rate-save"]').element.disabled).toBe(true);
  });
});
