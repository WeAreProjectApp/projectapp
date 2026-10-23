/**
 * CommercialConditionsForm — text-only editor.
 * Rates, currency and the package list moved to the «Tarifa por hora» tab and
 * to the catalog; this form must not render them, yet must still round-trip
 * them untouched so saving here never wipes the proposal's pricing.
 */
import { reactive } from 'vue';
import { mount } from '@vue/test-utils';
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';
import BaseRichTextListEditor from '../../components/base/BaseRichTextListEditor.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import CommercialConditionsForm from '../../components/BusinessProposal/admin/section-forms/CommercialConditionsForm.vue';
import { buildFormFromJson, formToJson } from '../../components/BusinessProposal/admin/sectionEditorUtils.js';

const BASE_JSON = {
  index: '17',
  title: 'Condiciones comerciales',
  packagesTitle: 'Paquetes',
  packagesIntro: 'intro',
  hourPackagesMode: 'manual',
  hourlyRate: 40,
  currency: 'USD',
  manualHourlyRate: 55,
  manualCurrency: 'USD',
  manualPackageRates: [{ packageId: 7, hourlyRate: 60 }],
  packages: [
    { id: 7, name: 'Pro', hours: 60, discountPercent: 10, note: 'x' },
    { id: 8, name: 'Ágil', hours: 20, discountPercent: 0, note: 'y', hourlyRate: 45 },
  ],
  effortBadge: 'badge',
  scopeTitle: 'Alcance',
  scopeParagraphs: ['p1'],
};

const originalUseI18n = global.useI18n;
beforeEach(() => { global.useI18n = () => ({ t: (key) => key }); });
afterAll(() => { global.useI18n = originalUseI18n; });

function mountForm(jsonOverrides = {}) {
  const form = reactive(
    buildFormFromJson({ ...BASE_JSON, ...jsonOverrides }, 'commercial_conditions', {}),
  );
  const wrapper = mount(CommercialConditionsForm, {
    props: { form, proposalData: {} },
    global: { components: { BaseRichTextEditor, BaseRichTextListEditor, BaseSegmented } },
  });
  return { wrapper, form };
}

describe('CommercialConditionsForm', () => {
  it('edits titles and scope but renders no rate, currency or package controls', () => {
    const { wrapper } = mountForm();

    const titleInput = wrapper.findAll('input').find((i) => i.element.value === 'Condiciones comerciales');
    expect(titleInput.attributes('disabled')).toBeUndefined();
    const scopeTextarea = wrapper.findAll('[data-testid="rich-text-source-input"]').find((t) => t.element.value.includes('p1'));
    expect(scopeTextarea.attributes('disabled')).toBeUndefined();

    expect(wrapper.findAll('select').map((select) => select.attributes('aria-label'))).toEqual([
      'richText.heading', 'richText.heading', 'richText.heading',
    ]);
    expect(wrapper.find('[data-testid="hour-packages-mode-manual"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="apply-base-rate-all"]').exists()).toBe(false);
    expect(wrapper.findAll('button').some((b) => b.text().includes('Agregar paquete'))).toBe(false);
    expect(wrapper.find('[data-testid="hour-rate-tab-hint"]').text()).toContain('Tarifa por hora');
  });

  it('saving an edited title hands back the manual rate settings untouched', async () => {
    const { wrapper, form } = mountForm();

    const titleInput = wrapper.findAll('input').find((i) => i.element.value === 'Condiciones comerciales');
    await titleInput.setValue('Condiciones editadas');

    const json = formToJson(form, 'commercial_conditions');
    expect(json.title).toBe('Condiciones editadas');
    expect(json.hourPackagesMode).toBe('manual');
    expect(json.manualHourlyRate).toBe(55);
    expect(json.manualCurrency).toBe('USD');
    expect(json.manualPackageRates).toEqual([{ packageId: 7, hourlyRate: 60 }]);
  });

  it('saving keeps the catalog-owned package list intact', () => {
    const { form } = mountForm();

    const json = formToJson(form, 'commercial_conditions');
    expect(json.packages).toHaveLength(2);
    expect(json.packages[0]).toMatchObject({ id: 7, name: 'Pro', hours: 60 });
    expect(json.packages[1].hourlyRate).toBe(45);
  });
});
