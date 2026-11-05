import { mount } from '@vue/test-utils';
import DefinitionEditor from '../../components/RequirementCalculator/DefinitionEditor.vue';

const originalUseI18n = global.useI18n;

function definition() {
  return {
    title: 'Calculadora general',
    methodology: 'Clasifica por señales observables.',
    project_rules: ['No cabe en XL'],
    sizes: ['XS', 'S', 'M', 'L', 'XL'].map((id, index) => ({
      id,
      label: id,
      definition: `Definición ${id}`,
      examples: [`Ejemplo ${id}`],
      points: String(index + 1),
      hours_min: '2',
      hours_max: '7',
      standard_value_cop: '50000',
    })),
    signals: [{ id: 'single-signal', label: 'Formulario simple', description: 'Un formulario sin integraciones.', size: 'S', surcharge_percent: '0' }],
    modifiers: [{ id: 'scope', label: 'Alcance', kind: 'percentage', minimum: '0', maximum: '10', applies_to: ['S'], exclusive_group: '' }],
    families: [{ label: 'Formulario', small: 'Un campo', medium: 'Validación', large: 'Integración', extra_large: 'Migración' }],
    calibration: { minimum_samples: '3', deviation_percent: '30', hourly_cost_cop: '50000' },
  };
}

function mountEditor(modelValue) {
  return mount(DefinitionEditor, {
    props: { modelValue, parametersOnly: true },
    global: {
      stubs: {
        BaseButton: { template: '<button type="button"><slot /></button>' },
      },
    },
  });
}

describe('RequirementCalculator DefinitionEditor', () => {
  beforeEach(() => {
    global.useI18n = () => ({ t: (key) => ({
      'requirementCalculator.parametersOnly': 'Variante del proyecto',
      'requirementCalculator.sizes': 'Tallas y parámetros internos',
      'requirementCalculator.points': 'Puntos de referencia',
      'requirementCalculator.methodology': 'Instrucciones de clasificación',
      'requirementCalculator.addSignal': 'Agregar señal',
      'requirementCalculator.addModifier': 'Agregar modificador',
    }[key] || key) });
  });

  afterAll(() => { global.useI18n = originalUseI18n; });

  // Falla si una versión de proyecto vuelve a editar textos o agrega reglas de la definición canónica.
  it('hides the canonical definition controls for a project version', () => {
    const modelValue = definition();
    const wrapper = mountEditor(modelValue);

    expect(wrapper.text()).toContain('Variante del proyecto');
    expect(wrapper.find('[data-testid="calculator-title"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Instrucciones de clasificación');
    expect(wrapper.text()).not.toContain('Agregar señal');
    expect(wrapper.text()).not.toContain('Agregar modificador');
  });

  // Falla si el parámetro negociable de una talla deja de escribir el valor elegido en la versión de proyecto.
  it('updates the selected size points', async () => {
    const modelValue = definition();
    const wrapper = mountEditor(modelValue);

    expect(wrapper.get('[data-testid="calculator-XS-points"]').element.value).toBe('1');

    await wrapper.get('[data-testid="calculator-XS-points"]').setValue('13');

    expect(modelValue.sizes[0].points).toBe(13);
  });
});
