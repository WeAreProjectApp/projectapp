/**
 * Tests for SectionEditor pure utility functions.
 *
 * Covers: arrToText, textToArr, buildFormFromJson, formToJson,
 * formToReadableText, groupToReadableText, buildSavePayload
 * for all 12 section types with form/paste mode and edge cases.
 */
import { mount } from '@vue/test-utils';
import {
  arrToText,
  textToArr,
  buildFormFromJson,
  formToJson,
  formToReadableText,
  groupToReadableText,
  buildSavePayload,
} from '../../components/BusinessProposal/admin/sectionEditorUtils.js';
import SectionEditor from '../../components/BusinessProposal/admin/SectionEditor.vue';

jest.mock('vuedraggable', () => ({
  __esModule: true,
  default: {
    name: 'DraggableStub',
    props: ['modelValue'],
    template: `
      <div>
        <template v-for="(element, index) in modelValue || []" :key="element.id || element._idx || index">
          <slot name="item" :element="element" :index="index" />
        </template>
        <slot />
      </div>
    `,
  },
}));

jest.mock('~/components/BusinessProposal/admin/EmojiIconField.vue', () => ({
  __esModule: true,
  default: {
    name: 'EmojiIconField',
    props: ['modelValue', 'label', 'placeholder'],
    template: `
      <label>
        <span>{{ label }}</span>
        <input
          :value="modelValue"
          :placeholder="placeholder"
          @input="$emit('update:modelValue', $event.target.value)"
        />
      </label>
    `,
  },
}));

jest.mock('~/components/BusinessProposal/admin/SectionPreviewModal.vue', () => ({
  __esModule: true,
  default: {
    name: 'SectionPreviewModal',
    props: ['visible', 'section', 'proposalData', 'subSection'],
    template: `
      <div v-if="visible" class="section-preview-stub">
        {{ subSection ? 'sub-preview-open' : 'preview-open' }}
      </div>
    `,
  },
}));

jest.mock('~/components/BusinessProposal/admin/TechnicalDocumentEditor.vue', () => ({
  __esModule: true,
  default: {
    name: 'TechnicalDocumentEditor',
    props: ['section', 'moduleLinkOptions'],
    template: `
      <button data-testid="technical-document-save" @click="$emit('save', { title: 'Technical' })">
        technical-document-editor
      </button>
    `,
  },
}));


// ─── Fixtures ────────────────────────────────────────────────────────────────

const greetingJson = {
  clientName: 'María García',
  inspirationalQuote: 'Design is how it works.',
};

const executiveSummaryJson = {
  index: '1',
  title: 'Resumen ejecutivo',
  paragraphs: ['Primer párrafo.', 'Segundo párrafo.'],
  highlightsTitle: 'Incluye',
  highlights: ['Diseño personalizado', 'Desarrollo responsivo'],
};

const contextDiagnosticJson = {
  index: '2',
  title: 'Contexto',
  paragraphs: ['El cliente busca fortalecer su presencia digital.'],
  issuesTitle: 'Desafíos',
  issues: ['Falta de presencia digital', 'Difícil captar clientes'],
  opportunityTitle: 'Oportunidad',
  opportunity: 'Crear una plataforma que genere confianza.',
};

const conversionStrategyJson = {
  index: '3',
  title: 'Estrategia',
  intro: 'La página se construirá como herramienta de conversión.',
  steps: [
    { title: 'Captar atención', bullets: ['Mensaje claro', 'Beneficio visible'] },
    { title: 'Construir confianza', bullets: ['Testimonios'] },
  ],
  resultTitle: 'Resultado',
  result: 'Una página que genere contactos.',
};

const designUxJson = {
  index: '4',
  title: 'Diseño UX',
  paragraphs: ['El desarrollo será una experiencia digital.'],
  focusTitle: 'Estructura',
  focusItems: ['Presentación clara', 'Integración redes sociales'],
  objectiveTitle: 'Objetivo',
  objective: 'Inspirar confianza.',
};

const creativeSupportJson = {
  index: '5',
  title: 'Acompañamiento',
  paragraphs: ['El cliente contará con acompañamiento cercano.'],
  includesTitle: 'Incluye',
  includes: ['Sesiones de revisión', 'Apoyo visual'],
  closing: 'Cada decisión será co-creación.',
};

const developmentStagesJson = {
  stages: [
    { icon: '✉️', title: 'Propuesta', description: 'Etapa actual.', current: true },
    { icon: '🎨', title: 'Diseño', description: 'Prototipo en Figma.' },
    { icon: '💻', title: 'Desarrollo', description: 'Implementación.' },
  ],
};

const functionalRequirementsJson = {
  index: '7',
  title: 'Requerimientos',
  intro: 'Detalle de requerimientos.',
  groups: [
    {
      id: 'views', icon: '🖥️', title: 'Vistas', description: 'Pantallas.',
      items: [
        { icon: '🏠', name: 'Home', description: 'Landing con CTAs.' },
        { icon: '📧', name: 'Contacto', description: 'Formulario.' },
      ],
    },
  ],
  additionalModules: [
    {
      icon: '📊', title: 'Analytics', description: 'Dashboard.',
      items: [{ icon: '📈', name: 'Reports', description: 'Reportes.' }],
    },
  ],
};

const functionalRequirementsJsonWithPrice = {
  index: '7',
  title: 'Requerimientos',
  intro: 'Detalle.',
  groups: [
    {
      id: 'views', icon: '🖥️', title: 'Vistas', description: 'Pantallas.',
      items: [
        { icon: '🏠', name: 'Home', description: 'Landing.', price: 500000 },
        { icon: '📧', name: 'Contacto', description: 'Form.', price: null },
        { icon: '📜', name: 'Términos', description: 'Políticas.' },
      ],
    },
  ],
  additionalModules: [],
};

const functionalRequirementsJsonWithPaste = {
  index: '7',
  title: 'Requerimientos',
  intro: 'Detalle.',
  groups: [
    {
      id: 'views', icon: '🖥️', title: 'Vistas', description: '',
      items: [], _editMode: 'paste', rawText: 'Pasted views content',
    },
  ],
  additionalModules: [
    {
      icon: '📊', title: 'Analytics', description: '',
      items: [], _editMode: 'paste', rawText: 'Pasted analytics',
    },
  ],
};

const timelineJson = {
  index: '8',
  title: 'Cronograma',
  introText: 'Fases del proyecto.',
  totalDuration: '1 mes',
  phases: [
    {
      title: 'Diseño', duration: '1 semana', description: 'Diseño visual.',
      tasks: ['Moodboard', 'Wireframes'], milestone: 'Diseño aprobado',
    },
  ],
};

const investmentJson = {
  index: '9',
  title: 'Inversión',
  introText: 'La inversión total es:',
  totalInvestment: '$3.500.000',
  currency: 'COP',
  whatsIncluded: [
    { icon: '🎨', title: 'Diseño', description: 'UX/UI' },
  ],
  paymentOptions: [
    { label: '40% al firmar', description: '$1.400.000' },
  ],
  hostingPlan: {
    title: 'Hosting, Mantenimiento y Soporte',
    description: 'Infraestructura optimizada.',
    specs: [
      { icon: '🧠', label: 'vCPU', value: '1 núcleo' },
      { icon: '🧮', label: 'RAM', value: '1 GB' },
    ],
    hostingPercent: 30,
    billingTiers: [
      { frequency: 'semiannual', months: 6, discountPercent: 20, label: 'Semestral', badge: 'Mejor precio' },
      { frequency: 'quarterly', months: 3, discountPercent: 10, label: 'Trimestral', badge: '10% dcto' },
    ],
    renewalNote: 'Renovación con SMLMV.',
    coverageNote: 'Cubre mantenimiento, soporte y recursos.',
  },
  paymentMethods: ['Transferencia', 'Nequi'],
  valueReasons: ['Diseño a medida', 'Código optimizado'],
};

const investmentJsonLegacy = {
  index: '9',
  title: 'Inversión',
  introText: 'La inversión total es:',
  totalInvestment: '$3.500.000',
  currency: 'COP',
  whatsIncluded: [],
  paymentOptions: [],
  hostingPlan: {
    title: 'Hosting Legacy',
    description: 'Infraestructura.',
    specs: [],
    hostingPercent: 30,
    monthlyLabel: 'por mes',
    annualLabel: 'Hosting anual — Año 1',
    renewalNote: '',
    coverageNote: '',
  },
  paymentMethods: [],
  valueReasons: [],
};

const finalNoteJson = {
  index: '10',
  title: 'Nota Final',
  message: 'Creemos firmemente.',
  personalNote: 'Estamos emocionados.',
  teamName: 'Project App',
  teamRole: 'Socio digital',
  contactEmail: 'team@projectapp.co',
  commitmentBadges: [
    { icon: '🤝', title: 'Compromiso', description: 'Dedicación.' },
  ],
  validityMessage: 'Válida 30 días.',
  thankYouMessage: 'Gracias.',
};

const nextStepsJson = {
  index: '11',
  title: 'Próximos pasos',
  introMessage: 'Estamos listos.',
  steps: [
    { title: 'Revisión', description: 'Revisa la propuesta.' },
    { title: 'Comenzamos', description: 'Kickoff meeting.' },
  ],
  ctaMessage: 'Contáctanos hoy.',
  primaryCTA: { text: 'WhatsApp', link: 'https://wa.me/123' },
  secondaryCTA: { text: 'Agendar', link: 'https://calendly.com/x' },
  contactMethods: [
    { icon: '📧', title: 'Email', value: 'hi@test.co', link: 'mailto:hi@test.co' },
  ],
  validityMessage: 'Válida 30 días.',
  thankYouMessage: 'Gracias.',
};

const processMethodologyJson = {
  index: '12',
  title: 'Metodología',
  intro: 'Así trabajamos.',
  steps: [
    { icon: '🔍', title: 'Descubrimiento', description: 'Definimos objetivos.', clientAction: 'Aprobar alcance' },
  ],
};

const roiProjectionJson = {
  index: '4',
  title: '📈 Proyección de retorno',
  subtitle: 'Outcomes test.',
  kpis: [
    { icon: '👁️', value: '90K', label: 'Visualizaciones', sublabel: 'mes 6', source: 'Benchmark' },
  ],
  scenariosTitle: 'Escenarios',
  scenarios: [
    {
      name: 'realistic', label: 'Realista', icon: '🎯',
      metrics: [
        { label: 'MAU', value: '80K' },
        { label: 'Total año 1', value: '$280M', emphasis: true },
      ],
    },
  ],
  ctaNote: 'Cubre la inversión.',
};

function buildSection(sectionType, contentJson, extra = {}) {
  return {
    id: 99,
    title: `Section ${sectionType}`,
    section_type: sectionType,
    is_wide_panel: false,
    content_json: contentJson,
    ...extra,
  };
}

function mountSectionEditor(props = {}) {
  return mount(SectionEditor, {
    props: {
      section: buildSection('greeting', greetingJson),
      proposalData: {
        title: 'Proyecto Base',
        client_name: 'Cliente Base',
        total_investment: 3500000,
        currency: 'COP',
        hosting_percent: 30,
      },
      moduleLinkOptions: [],
      ...props,
    },
    global: {
      stubs: {
      },
    },
  });
}

describe('SectionEditor component', () => {
  it('renders the technical document branch and forwards its save event', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('technical_document', {
        purpose: 'Propósito',
        stack: [],
        epics: [],
      }),
      moduleLinkOptions: [{ id: 'analytics', label: 'Analytics' }],
    });

    expect(wrapper.text()).toContain('technical-document-editor');
    await wrapper.find('[data-testid="technical-document-save"]').trigger('click');
    expect(wrapper.emitted('save')).toEqual([[{ title: 'Technical' }]]);
  });

  it.each([
    ['greeting', greetingJson],
    ['executive_summary', executiveSummaryJson],
    ['context_diagnostic', contextDiagnosticJson],
    ['conversion_strategy', conversionStrategyJson],
    ['design_ux', designUxJson],
    ['creative_support', creativeSupportJson],
    ['development_stages', developmentStagesJson],
    ['functional_requirements', functionalRequirementsJson],
    ['timeline', timelineJson],
    ['investment', investmentJson],
    ['final_note', finalNoteJson],
    ['next_steps', nextStepsJson],
    ['process_methodology', processMethodologyJson],
    ['roi_projection', roiProjectionJson],
  ])('mounts the %s branch without crashing', (sectionType, contentJson) => {
    const wrapper = mountSectionEditor({
      section: buildSection(sectionType, contentJson),
    });

    expect(wrapper.find('[data-testid="section-editor"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Guardar Sección');
  });

  it('renders the paste textarea when the section opens in paste mode', () => {
    const wrapper = mountSectionEditor({
      section: buildSection('executive_summary', {
        ...executiveSummaryJson,
        _editMode: 'paste',
        rawText: 'Resumen pegado',
      }),
    });

    expect(wrapper.find('[data-testid="paste-textarea"]').element.value).toBe('Resumen pegado');
  });

  it('switches to paste mode and mirrors the current form content', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('greeting', greetingJson),
    });

    await wrapper.findAll('button').find((button) => button.text() === 'Pegar contenido').trigger('click');

    expect(wrapper.find('[data-testid="paste-textarea"]').element.value).toContain('María García');
  });

  it('opens the main preview modal', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('greeting', greetingJson),
    });

    await wrapper.findAll('button').find((button) => button.text().includes('Previsualizar')).trigger('click');

    expect(wrapper.find('.section-preview-stub').text()).toContain('preview-open');
  });

  it('emits the saved payload in form mode', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('greeting', greetingJson),
    });

    await wrapper.find('input[type="text"]').setValue('Nuevo título');
    await wrapper.findAll('button').find((button) => button.text().includes('Guardar Sección')).trigger('click');

    expect(wrapper.emitted('save')[0][0]).toEqual(
      expect.objectContaining({
        sectionId: 99,
        payload: expect.objectContaining({
          title: 'Nuevo título',
          content_json: expect.objectContaining({ _editMode: 'form' }),
        }),
      }),
    );
  });

  it('emits rawText in paste mode saves', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('executive_summary', executiveSummaryJson),
    });

    await wrapper.findAll('button').find((button) => button.text() === 'Pegar contenido').trigger('click');
    await wrapper.find('[data-testid="paste-textarea"]').setValue('Texto pegado');
    await wrapper.findAll('button').find((button) => button.text().includes('Guardar Sección')).trigger('click');

    expect(wrapper.emitted('save')[0][0].payload.content_json).toEqual(
      expect.objectContaining({
        _editMode: 'paste',
        rawText: 'Texto pegado',
      }),
    );
  });

  it('blocks saving when a functional requirements optional item has no price', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('functional_requirements', {
        index: '7',
        title: 'Requerimientos',
        intro: 'Detalle.',
        groups: [
          {
            id: 'views',
            icon: '🖥️',
            title: 'Vistas',
            description: 'Pantallas.',
            items: [
              {
                icon: '🏠',
                name: 'Home',
                description: 'Landing.',
                is_required: false,
                price: null,
              },
            ],
          },
        ],
        additionalModules: [],
      }),
    });

    await wrapper.findAll('button').find((button) => button.text().includes('Guardar Sección')).trigger('click');

    expect(wrapper.text()).toContain('no tienen precio asignado');
    expect(wrapper.emitted('save')).toBeUndefined();
  });

  it('opens the sub-preview for a functional requirements group', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('functional_requirements', functionalRequirementsJson),
    });

    await wrapper.find('[data-testid="requirement-group-views"]').findAll('button')
      .find((button) => button.html().includes('M15 12a3 3'))
      .trigger('click');

    expect(wrapper.find('.section-preview-stub').text()).toContain('sub-preview-open');
  });

  it('switches a functional requirements group into paste mode with generated text', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('functional_requirements', functionalRequirementsJson),
    });

    await wrapper.find('[data-testid="requirement-group-views"]').findAll('button')
      .find((button) => button.text() === 'Pegar contenido')
      .trigger('click');

    expect(wrapper.find('[data-testid="group-paste-textarea"]').element.value).toContain('Vistas');
  });

  it('syncs the hosting percent when saving the investment section', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('investment', investmentJsonLegacy),
      proposalData: {
        title: 'Proyecto Base',
        client_name: 'Cliente Base',
        total_investment: 3500000,
        currency: 'COP',
        hosting_percent: 30,
      },
    });

    await wrapper.setProps({
      proposalData: {
        title: 'Proyecto Base',
        client_name: 'Cliente Base',
        total_investment: 3500000,
        currency: 'COP',
        hosting_percent: 45,
      },
    });
    await wrapper.findAll('button').find((button) => button.text().includes('Guardar Sección')).trigger('click');

    expect(wrapper.emitted('syncHostingPercent')).toEqual([[45]]);
  });

  it('auto-fills the investment form from proposalData when the section is empty', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('investment', {
        index: '9',
        title: 'Inversión',
        introText: '',
        totalInvestment: '',
        currency: '',
        whatsIncluded: [],
        paymentOptions: [],
        hostingPlan: {
          title: 'Hosting',
          description: '',
          specs: [],
          hostingPercent: null,
          billingTiers: [],
          renewalNote: '',
          coverageNote: '',
        },
        paymentMethods: [],
        valueReasons: [],
      }),
    });

    await wrapper.findAll('button').find((button) => button.text().includes('Mostrar')).trigger('click');

    expect(wrapper.find('textarea[readonly]').element.value).toContain('$3,500,000');
    expect(wrapper.find('textarea[readonly]').element.value).toContain('40% al firmar el contrato');
  });

  it('recalculates investment payment descriptions when proposalData.total_investment changes', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('investment', investmentJson),
    });

    await wrapper.setProps({
      proposalData: {
        title: 'Proyecto Base',
        client_name: 'Cliente Base',
        total_investment: 7000000,
        currency: 'COP',
        hosting_percent: 30,
      },
    });
    await wrapper.findAll('button').find((button) => button.text().includes('Mostrar')).trigger('click');

    expect(wrapper.find('textarea[readonly]').element.value).toContain('$2,800,000 COP');
  });

  it('updates functional requirements paste caches when form fields change in form mode', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('functional_requirements', functionalRequirementsJson),
    });

    const groupInputs = wrapper.find('[data-testid="requirement-group-views"]').findAll('input');
    await groupInputs[1].setValue('Vistas actualizadas');

    await wrapper.find('[data-testid="requirement-group-views"]').findAll('button')
      .find((button) => button.text() === 'Pegar contenido')
      .trigger('click');

    expect(wrapper.find('[data-testid="group-paste-textarea"]').element.value).toContain('Vistas actualizadas');
  });

  it('shows raw JSON for the current section when toggled open', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('greeting', greetingJson),
    });

    await wrapper.findAll('button').find((button) => button.text().includes('Mostrar')).trigger('click');

    expect(wrapper.find('textarea[readonly]').element.value).toContain('"clientName": "María García"');
  });

  it('blocks saving when an investment optional module has no price', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('investment', {
        ...investmentJson,
        modules: [
          {
            name: 'Módulo premium',
            is_required: false,
            price: null,
          },
        ],
      }),
    });

    await wrapper.findAll('button').find((button) => button.text().includes('Guardar Sección')).trigger('click');

    expect(wrapper.text()).toContain('Módulo premium');
    expect(wrapper.emitted('save')).toBeUndefined();
  });

  it('updates the form when the section prop changes', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('greeting', greetingJson),
    });

    await wrapper.setProps({
      section: buildSection('greeting', {
        clientName: 'Cliente Actualizado',
        inspirationalQuote: 'Nueva frase',
      }, { title: 'Greeting updated' }),
    });

    const inputs = wrapper.findAll('input');
    expect(inputs[0].element.value).toBe('Greeting updated');
    expect(inputs[2].element.value).toBe('Cliente Actualizado');
  });
});


// ─── arrToText / textToArr ───────────────────────────────────────────────────

describe('arrToText', () => {
  it('joins array with newlines', () => {
    expect(arrToText(['a', 'b', 'c'])).toBe('a\nb\nc');
  });

  it('returns empty string for empty array', () => {
    expect(arrToText([])).toBe('');
  });

  it('returns string as-is if not an array', () => {
    expect(arrToText('already text')).toBe('already text');
  });

  it('returns empty string for null', () => {
    expect(arrToText(null)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(arrToText(undefined)).toBe('');
  });
});

describe('textToArr', () => {
  it('splits text by newlines and trims', () => {
    expect(textToArr('a\n  b  \nc')).toEqual(['a', 'b', 'c']);
  });

  it('filters empty lines', () => {
    expect(textToArr('a\n\n\nb')).toEqual(['a', 'b']);
  });

  it('returns empty array for empty string', () => {
    expect(textToArr('')).toEqual([]);
  });

  it('returns empty array for null', () => {
    expect(textToArr(null)).toEqual([]);
  });

  it('returns empty array for undefined', () => {
    expect(textToArr(undefined)).toEqual([]);
  });

  it('handles single line', () => {
    expect(textToArr('single')).toEqual(['single']);
  });
});


// ─── buildFormFromJson ───────────────────────────────────────────────────────

describe('buildFormFromJson', () => {
  describe('greeting', () => {
    it('builds form from full content_json', () => {
      const form = buildFormFromJson(greetingJson, 'greeting');
      expect(form.clientName).toBe('María García');
      expect(form.inspirationalQuote).toBe('Design is how it works.');
    });

    it('uses proposalData.client_name as fallback', () => {
      const form = buildFormFromJson({}, 'greeting', { client_name: 'Fallback' });
      expect(form.clientName).toBe('Fallback');
    });

    it('defaults to empty strings when no data', () => {
      const form = buildFormFromJson({}, 'greeting');
      expect(form.clientName).toBe('');
      expect(form.inspirationalQuote).toBe('');
    });

    it('handles null json', () => {
      const form = buildFormFromJson(null, 'greeting');
      expect(form.clientName).toBe('');
    });
  });

  describe('executive_summary', () => {
    it('converts paragraphs array to newline text', () => {
      const form = buildFormFromJson(executiveSummaryJson, 'executive_summary');
      expect(form.paragraphs).toBe('Primer párrafo.\nSegundo párrafo.');
      expect(form.highlights).toBe('Diseño personalizado\nDesarrollo responsivo');
      expect(form.index).toBe('1');
    });

    it('defaults empty arrays to empty string', () => {
      const form = buildFormFromJson({ paragraphs: [], highlights: [] }, 'executive_summary');
      expect(form.paragraphs).toBe('');
      expect(form.highlights).toBe('');
    });
  });

  describe('context_diagnostic', () => {
    it('builds form with issues and opportunity', () => {
      const form = buildFormFromJson(contextDiagnosticJson, 'context_diagnostic');
      expect(form.issues).toBe('Falta de presencia digital\nDifícil captar clientes');
      expect(form.opportunity).toBe('Crear una plataforma que genere confianza.');
    });
  });

  describe('conversion_strategy', () => {
    it('builds form with steps containing bullet text', () => {
      const form = buildFormFromJson(conversionStrategyJson, 'conversion_strategy');
      expect(form.steps).toHaveLength(2);
      expect(form.steps[0].bullets).toBe('Mensaje claro\nBeneficio visible');
      expect(form.result).toBe('Una página que genere contactos.');
    });

    it('defaults to empty steps array', () => {
      const form = buildFormFromJson({}, 'conversion_strategy');
      expect(form.steps).toEqual([]);
    });
  });

  describe('design_ux', () => {
    it('builds form with focusItems and objective', () => {
      const form = buildFormFromJson(designUxJson, 'design_ux');
      expect(form.focusItems).toBe('Presentación clara\nIntegración redes sociales');
      expect(form.objective).toBe('Inspirar confianza.');
    });
  });

  describe('creative_support', () => {
    it('builds form with includes and closing', () => {
      const form = buildFormFromJson(creativeSupportJson, 'creative_support');
      expect(form.includes).toBe('Sesiones de revisión\nApoyo visual');
      expect(form.closing).toBe('Cada decisión será co-creación.');
    });
  });

  describe('development_stages', () => {
    it('builds form with stages and current flag', () => {
      const form = buildFormFromJson(developmentStagesJson, 'development_stages');
      expect(form.stages).toHaveLength(3);
      expect(form.stages[0].current).toBe(true);
      expect(form.stages[1].current).toBe(false);
    });

    it('defaults to empty stages', () => {
      const form = buildFormFromJson({}, 'development_stages');
      expect(form.stages).toEqual([]);
    });
  });

  describe('functional_requirements', () => {
    it('builds form with groups and items', () => {
      const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
      expect(form.groups).toHaveLength(1);
      expect(form.groups[0].items).toHaveLength(2);
      expect(form.groups[0].id).toBe('views');
      expect(form.additionalModules).toHaveLength(1);
    });

    it('restores paste mode from _editMode in groups', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPaste, 'functional_requirements');
      expect(form.groups[0]._pasteMode).toBe(true);
      expect(form.groups[0]._pasteText).toBe('Pasted views content');
      expect(form.additionalModules[0]._pasteMode).toBe(true);
      expect(form.additionalModules[0]._pasteText).toBe('Pasted analytics');
    });

    it('sets _collapsed to true by default', () => {
      const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
      expect(form.groups[0]._collapsed).toBe(true);
      expect(form.additionalModules[0]._collapsed).toBe(true);
    });

    it('defaults form mode when _editMode absent', () => {
      const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
      expect(form.groups[0]._pasteMode).toBe(false);
      expect(form.groups[0]._pasteText).toBe('');
    });

    it('preserves price field on items when present', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPrice, 'functional_requirements');
      expect(form.groups[0].items[0].price).toBe(500000);
    });

    it('defaults price to null when missing from item', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPrice, 'functional_requirements');
      expect(form.groups[0].items[2].price).toBeNull();
    });

    it('preserves explicit null price', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPrice, 'functional_requirements');
      expect(form.groups[0].items[1].price).toBeNull();
    });
  });

  describe('timeline', () => {
    it('builds form with phases and tasks as text', () => {
      const form = buildFormFromJson(timelineJson, 'timeline');
      expect(form.phases).toHaveLength(1);
      expect(form.phases[0].tasks).toBe('Moodboard\nWireframes');
      expect(form.totalDuration).toBe('1 mes');
    });
  });

  describe('investment', () => {
    it('builds form with payment options and methods as text', () => {
      const form = buildFormFromJson(investmentJson, 'investment');
      expect(form.totalInvestment).toBe('$3.500.000');
      expect(form.whatsIncluded).toHaveLength(1);
      expect(form.paymentOptions).toHaveLength(1);
      expect(form.paymentMethods).toBe('Transferencia\nNequi');
      expect(form.valueReasons).toBe('Diseño a medida\nCódigo optimizado');
    });

    it('defaults currency to COP', () => {
      const form = buildFormFromJson({}, 'investment');
      expect(form.currency).toBe('COP');
    });

    it('reads hostingPercent from hostingPlan', () => {
      const form = buildFormFromJson(investmentJson, 'investment');
      expect(form.hostingPlan.hostingPercent).toBe(30);
    });

    it('defaults hostingPercent to 60 when missing', () => {
      const json = { ...investmentJson, hostingPlan: { title: 'Hosting' } };
      const form = buildFormFromJson(json, 'investment');
      expect(form.hostingPlan.hostingPercent).toBe(60);
    });

    it('reads billingTiers from hostingPlan', () => {
      const form = buildFormFromJson(investmentJson, 'investment');
      expect(form.hostingPlan.billingTiers).toHaveLength(2);
      expect(form.hostingPlan.billingTiers[0].frequency).toBe('semiannual');
      expect(form.hostingPlan.billingTiers[0].discountPercent).toBe(20);
      expect(form.hostingPlan.billingTiers[1].frequency).toBe('quarterly');
      expect(form.hostingPlan.billingTiers[1].discountPercent).toBe(10);
    });

    it('provides default billingTiers when missing from json', () => {
      const json = { ...investmentJson, hostingPlan: { title: 'Hosting' } };
      const form = buildFormFromJson(json, 'investment');
      expect(form.hostingPlan.billingTiers).toHaveLength(3);
      expect(form.hostingPlan.billingTiers[0].months).toBe(9);
      expect(form.hostingPlan.billingTiers[1].months).toBe(6);
      expect(form.hostingPlan.billingTiers[2].months).toBe(3);
    });

    it('backward compat: legacy json without billingTiers gets default tiers', () => {
      const form = buildFormFromJson(investmentJsonLegacy, 'investment');
      expect(form.hostingPlan.billingTiers).toHaveLength(3);
      expect(form.hostingPlan.hostingPercent).toBe(30);
      expect(form.hostingPlan).not.toHaveProperty('monthlyLabel');
      expect(form.hostingPlan).not.toHaveProperty('annualLabel');
    });
  });

  describe('final_note', () => {
    it('builds form with badges and contact info', () => {
      const form = buildFormFromJson(finalNoteJson, 'final_note');
      expect(form.commitmentBadges).toHaveLength(1);
      expect(form.contactEmail).toBe('team@projectapp.co');
      expect(form.validityMessage).toBe('Válida 30 días.');
    });
  });

  describe('next_steps', () => {
    it('builds form with steps, CTAs, and contact methods', () => {
      const form = buildFormFromJson(nextStepsJson, 'next_steps');
      expect(form.steps).toHaveLength(2);
      expect(form.primaryCTA.text).toBe('WhatsApp');
      expect(form.secondaryCTA.link).toBe('https://calendly.com/x');
      expect(form.contactMethods).toHaveLength(1);
    });

    it('defaults CTAs to empty text/link', () => {
      const form = buildFormFromJson({}, 'next_steps');
      expect(form.primaryCTA).toEqual({ text: '', link: '' });
      expect(form.secondaryCTA).toEqual({ text: '', link: '' });
    });
  });

  describe('unknown type', () => {
    it('returns empty object for unknown section type', () => {
      const form = buildFormFromJson({ foo: 'bar' }, 'unknown_type');
      expect(form).toEqual({});
    });
  });
});


// ─── formToJson ──────────────────────────────────────────────────────────────

describe('formToJson', () => {
  describe('greeting', () => {
    it('serializes greeting form to json', () => {
      const form = { clientName: 'Test', inspirationalQuote: 'Quote' };
      const json = formToJson(form, 'greeting');
      expect(json).toEqual({ clientName: 'Test', inspirationalQuote: 'Quote' });
    });
  });

  describe('executive_summary', () => {
    it('converts newline text to arrays', () => {
      const form = buildFormFromJson(executiveSummaryJson, 'executive_summary');
      const json = formToJson(form, 'executive_summary');
      expect(json.paragraphs).toEqual(['Primer párrafo.', 'Segundo párrafo.']);
      expect(json.highlights).toEqual(['Diseño personalizado', 'Desarrollo responsivo']);
    });

    it('produces empty arrays from empty text', () => {
      const form = { index: '', title: '', paragraphs: '', highlightsTitle: '', highlights: '' };
      const json = formToJson(form, 'executive_summary');
      expect(json.paragraphs).toEqual([]);
      expect(json.highlights).toEqual([]);
    });
  });

  describe('context_diagnostic', () => {
    it('serializes issues and opportunity', () => {
      const form = buildFormFromJson(contextDiagnosticJson, 'context_diagnostic');
      const json = formToJson(form, 'context_diagnostic');
      expect(json.issues).toEqual(['Falta de presencia digital', 'Difícil captar clientes']);
      expect(json.opportunity).toBe('Crear una plataforma que genere confianza.');
    });
  });

  describe('conversion_strategy', () => {
    it('serializes steps with bullet arrays', () => {
      const form = buildFormFromJson(conversionStrategyJson, 'conversion_strategy');
      const json = formToJson(form, 'conversion_strategy');
      expect(json.steps[0].bullets).toEqual(['Mensaje claro', 'Beneficio visible']);
      expect(json.steps[1].bullets).toEqual(['Testimonios']);
    });
  });

  describe('design_ux', () => {
    it('serializes focusItems as array', () => {
      const form = buildFormFromJson(designUxJson, 'design_ux');
      const json = formToJson(form, 'design_ux');
      expect(json.focusItems).toEqual(['Presentación clara', 'Integración redes sociales']);
    });
  });

  describe('creative_support', () => {
    it('serializes includes as array', () => {
      const form = buildFormFromJson(creativeSupportJson, 'creative_support');
      const json = formToJson(form, 'creative_support');
      expect(json.includes).toEqual(['Sesiones de revisión', 'Apoyo visual']);
      expect(json.closing).toBe('Cada decisión será co-creación.');
    });
  });

  describe('development_stages', () => {
    it('includes current flag only when true', () => {
      const form = buildFormFromJson(developmentStagesJson, 'development_stages');
      const json = formToJson(form, 'development_stages');
      expect(json.stages[0].current).toBe(true);
      expect(json.stages[1]).not.toHaveProperty('current');
    });
  });

  describe('functional_requirements', () => {
    it('serializes groups with form mode metadata', () => {
      const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
      const json = formToJson(form, 'functional_requirements');
      expect(json.groups[0]._editMode).toBe('form');
      expect(json.groups[0]).not.toHaveProperty('rawText');
      expect(json.groups[0].items).toHaveLength(2);
    });

    it('serializes groups with paste mode metadata', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPaste, 'functional_requirements');
      const json = formToJson(form, 'functional_requirements');
      expect(json.groups[0]._editMode).toBe('paste');
      expect(json.groups[0].rawText).toBe('Pasted views content');
    });

    it('serializes additionalModules with paste mode', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPaste, 'functional_requirements');
      const json = formToJson(form, 'functional_requirements');
      expect(json.additionalModules[0]._editMode).toBe('paste');
      expect(json.additionalModules[0].rawText).toBe('Pasted analytics');
    });

    it('strips internal _pasteMode/_pasteText/_collapsed from output', () => {
      const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
      const json = formToJson(form, 'functional_requirements');
      expect(json.groups[0]).not.toHaveProperty('_pasteMode');
      expect(json.groups[0]).not.toHaveProperty('_pasteText');
      expect(json.groups[0]).not.toHaveProperty('_collapsed');
    });

    it('includes price in serialized items when value is set', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPrice, 'functional_requirements');
      const json = formToJson(form, 'functional_requirements');
      expect(json.groups[0].items[0].price).toBe(500000);
    });

    it('omits price key from serialized items when null', () => {
      const form = buildFormFromJson(functionalRequirementsJsonWithPrice, 'functional_requirements');
      const json = formToJson(form, 'functional_requirements');
      expect(json.groups[0].items[1]).not.toHaveProperty('price');
      expect(json.groups[0].items[2]).not.toHaveProperty('price');
    });
  });

  describe('timeline', () => {
    it('serializes phases with tasks as array', () => {
      const form = buildFormFromJson(timelineJson, 'timeline');
      const json = formToJson(form, 'timeline');
      expect(json.phases[0].tasks).toEqual(['Moodboard', 'Wireframes']);
    });
  });

  describe('investment', () => {
    it('serializes payment methods and value reasons as arrays', () => {
      const form = buildFormFromJson(investmentJson, 'investment');
      const json = formToJson(form, 'investment');
      expect(json.paymentMethods).toEqual(['Transferencia', 'Nequi']);
      expect(json.valueReasons).toEqual(['Diseño a medida', 'Código optimizado']);
    });

    it('serializes hostingPercent in hostingPlan', () => {
      const form = buildFormFromJson(investmentJson, 'investment');
      const json = formToJson(form, 'investment');
      expect(json.hostingPlan.hostingPercent).toBe(30);
    });

    it('serializes billingTiers in hostingPlan', () => {
      const form = buildFormFromJson(investmentJson, 'investment');
      const json = formToJson(form, 'investment');
      expect(json.hostingPlan.billingTiers).toHaveLength(2);
      expect(json.hostingPlan.billingTiers[0].frequency).toBe('semiannual');
      expect(json.hostingPlan.billingTiers[0].discountPercent).toBe(20);
      expect(json.hostingPlan).not.toHaveProperty('monthlyLabel');
      expect(json.hostingPlan).not.toHaveProperty('annualLabel');
    });

    it('defaults hostingPercent to 60 during serialization when missing', () => {
      const form = buildFormFromJson({ hostingPlan: { title: 'H' } }, 'investment');
      const json = formToJson(form, 'investment');
      expect(json.hostingPlan.hostingPercent).toBe(60);
    });

    // formToJson is a whitelist: a hostingPlan key absent from it is destroyed
    // on the next save of the section, silently.
    it('survives the round trip when the operator unchecks the free-month block', () => {
      const form = buildFormFromJson(investmentJson, 'investment');
      form.hostingPlan.freeMonthsVisible = false;
      const json = formToJson(form, 'investment');
      expect(json.hostingPlan.freeMonthsVisible).toBe(false);
    });

    it('keeps an unchecked block unchecked across a reload', () => {
      const stored = {
        ...investmentJson,
        hostingPlan: {
          ...investmentJson.hostingPlan, freeMonths: 2, freeMonthsVisible: false,
        },
      };
      const json = formToJson(buildFormFromJson(stored, 'investment'), 'investment');
      expect(json.hostingPlan.freeMonthsVisible).toBe(false);
      expect(json.hostingPlan.freeMonths).toBe(2);
    });

    it('derives visibility from the count for content that predates the flag', () => {
      const withMonths = formToJson(
        buildFormFromJson(
          { hostingPlan: { title: 'H', freeMonths: 1 } }, 'investment',
        ), 'investment',
      );
      const withoutMonths = formToJson(
        buildFormFromJson(
          { hostingPlan: { title: 'H', freeMonths: 0 } }, 'investment',
        ), 'investment',
      );
      expect(withMonths.hostingPlan.freeMonthsVisible).toBe(true);
      expect(withoutMonths.hostingPlan.freeMonthsVisible).toBe(false);
    });
  });

  describe('final_note', () => {
    it('serializes badges and contact info', () => {
      const form = buildFormFromJson(finalNoteJson, 'final_note');
      const json = formToJson(form, 'final_note');
      expect(json.commitmentBadges).toHaveLength(1);
      expect(json.contactEmail).toBe('team@projectapp.co');
    });
  });

  describe('next_steps', () => {
    it('serializes CTAs and contact methods', () => {
      const form = buildFormFromJson(nextStepsJson, 'next_steps');
      const json = formToJson(form, 'next_steps');
      expect(json.primaryCTA.text).toBe('WhatsApp');
      expect(json.contactMethods).toHaveLength(1);
      expect(json.validityMessage).toBe('Válida 30 días.');
    });
  });

  describe('unknown type', () => {
    it('returns empty object', () => {
      expect(formToJson({}, 'unknown')).toEqual({});
    });
  });
});


// ─── Round-trip: buildFormFromJson → formToJson ──────────────────────────────

describe('buildFormFromJson → formToJson round-trip', () => {
  const cases = [
    { type: 'greeting', json: greetingJson },
    { type: 'executive_summary', json: executiveSummaryJson },
    { type: 'context_diagnostic', json: contextDiagnosticJson },
    { type: 'conversion_strategy', json: conversionStrategyJson },
    { type: 'design_ux', json: designUxJson },
    { type: 'creative_support', json: creativeSupportJson },
    { type: 'development_stages', json: developmentStagesJson },
    { type: 'timeline', json: timelineJson },
    { type: 'investment', json: investmentJson },
    { type: 'final_note', json: finalNoteJson },
    { type: 'next_steps', json: nextStepsJson },
  ];

  it.each(cases)('round-trips $type correctly', ({ type, json }) => {
    const form = buildFormFromJson(json, type);
    const result = formToJson(form, type);
    // Compare key fields — the round-trip should preserve data
    for (const key of Object.keys(json)) {
      expect(result).toHaveProperty(key);
    }
  });

  it('round-trips functional_requirements preserving group items', () => {
    const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
    const result = formToJson(form, 'functional_requirements');
    expect(result.groups[0].items).toHaveLength(2);
    expect(result.groups[0].items[0].name).toBe('Home');
    expect(result.additionalModules[0].items[0].name).toBe('Reports');
  });
});


// ─── formToReadableText ──────────────────────────────────────────────────────

describe('formToReadableText', () => {
  it('generates text for greeting', () => {
    const form = buildFormFromJson(greetingJson, 'greeting');
    const text = formToReadableText(form, 'greeting');
    expect(text).toContain('María García');
    expect(text).toContain('Design is how it works.');
  });

  it('generates text for executive_summary with bullets', () => {
    const form = buildFormFromJson(executiveSummaryJson, 'executive_summary');
    const text = formToReadableText(form, 'executive_summary');
    expect(text).toContain('Primer párrafo.');
    expect(text).toContain('Incluye');
    expect(text).toContain('- Diseño personalizado');
  });

  it('generates text for context_diagnostic', () => {
    const form = buildFormFromJson(contextDiagnosticJson, 'context_diagnostic');
    const text = formToReadableText(form, 'context_diagnostic');
    expect(text).toContain('Desafíos');
    expect(text).toContain('- Falta de presencia digital');
    expect(text).toContain('Crear una plataforma');
  });

  it('generates text for conversion_strategy with steps', () => {
    const form = buildFormFromJson(conversionStrategyJson, 'conversion_strategy');
    const text = formToReadableText(form, 'conversion_strategy');
    expect(text).toContain('Captar atención');
    expect(text).toContain('- Mensaje claro');
  });

  it('generates text for design_ux', () => {
    const form = buildFormFromJson(designUxJson, 'design_ux');
    const text = formToReadableText(form, 'design_ux');
    expect(text).toContain('- Presentación clara');
    expect(text).toContain('Inspirar confianza.');
  });

  it('generates text for creative_support', () => {
    const form = buildFormFromJson(creativeSupportJson, 'creative_support');
    const text = formToReadableText(form, 'creative_support');
    expect(text).toContain('- Sesiones de revisión');
    expect(text).toContain('co-creación');
  });

  it('generates text for functional_requirements including title, intro and group overviews', () => {
    const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
    const text = formToReadableText(form, 'functional_requirements');
    expect(text).toContain('Requerimientos');
    expect(text).toContain('Detalle de requerimientos.');
    expect(text).toContain('Vistas');
    expect(text).toContain('Pantallas.');
    expect(text).toContain('Analytics');
    expect(text).toContain('Dashboard.');
  });

  it('generates text for functional_requirements excluding individual items', () => {
    const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
    const text = formToReadableText(form, 'functional_requirements');
    expect(text).not.toContain('**Home**');
    expect(text).not.toContain('**Contacto**');
    expect(text).not.toContain('**Reports**');
  });

  it('generates text for development_stages', () => {
    const form = buildFormFromJson(developmentStagesJson, 'development_stages');
    const text = formToReadableText(form, 'development_stages');
    expect(text).toContain('Propuesta');
    expect(text).toContain('(actual)');
  });

  it('generates text for timeline', () => {
    const form = buildFormFromJson(timelineJson, 'timeline');
    const text = formToReadableText(form, 'timeline');
    expect(text).toContain('1 mes');
    expect(text).toContain('Diseño aprobado');
  });

  it('generates text for investment', () => {
    const form = buildFormFromJson(investmentJson, 'investment');
    const text = formToReadableText(form, 'investment');
    expect(text).toContain('$3.500.000');
    expect(text).toContain('Qué incluye:');
  });

  it('generates text for investment with hostingPercent', () => {
    const form = buildFormFromJson(investmentJson, 'investment');
    const text = formToReadableText(form, 'investment');
    expect(text).toContain('Hosting: 30% de la inversión total');
  });

  it('generates text for final_note', () => {
    const form = buildFormFromJson(finalNoteJson, 'final_note');
    const text = formToReadableText(form, 'final_note');
    expect(text).toContain('Creemos firmemente.');
    expect(text).toContain('team@projectapp.co');
  });

  it('generates text for next_steps', () => {
    const form = buildFormFromJson(nextStepsJson, 'next_steps');
    const text = formToReadableText(form, 'next_steps');
    expect(text).toContain('Pasos:');
    expect(text).toContain('- Revisión:');
    expect(text).toContain('Contacto:');
  });

  it('returns empty string for empty form', () => {
    const text = formToReadableText({}, 'greeting');
    expect(text).toBe('');
  });

  it('returns empty string for unknown type', () => {
    const text = formToReadableText({}, 'unknown');
    expect(text).toBe('');
  });
});


// ─── groupToReadableText ─────────────────────────────────────────────────────

describe('groupToReadableText', () => {
  it('generates text with title, description and items', () => {
    const group = {
      icon: '🖥️',
      title: 'Vistas',
      description: 'Pantallas del sitio.',
      items: [
        { icon: '🏠', name: 'Home', description: 'Landing.' },
        { icon: '📧', name: 'Contacto', description: 'Formulario.' },
      ],
    };
    const text = groupToReadableText(group);
    expect(text).toContain('🖥️ Vistas');
    expect(text).toContain('Pantallas del sitio.');
    expect(text).toContain('- 🏠 **Home**: Landing.');
    expect(text).toContain('- 📧 **Contacto**: Formulario.');
  });

  it('handles group with no description', () => {
    const group = {
      title: 'Test',
      description: '',
      items: [{ icon: '', name: 'Item', description: 'Desc' }],
    };
    const text = groupToReadableText(group);
    expect(text).toBe('Test\n-  **Item**: Desc');
  });

  it('handles group with no items', () => {
    const group = { title: 'Empty', icon: '📦', description: 'Just description.', items: [] };
    const text = groupToReadableText(group);
    expect(text).toBe('📦 Empty\nJust description.');
  });

  it('returns empty string for empty group', () => {
    const text = groupToReadableText({ description: '', items: [] });
    expect(text).toBe('');
  });
});


// ─── buildSavePayload ────────────────────────────────────────────────────────

describe('buildSavePayload', () => {
  it('builds payload in form mode with _editMode form', () => {
    const form = { clientName: 'Test', inspirationalQuote: 'Quote' };
    const result = buildSavePayload(form, 'greeting', false, '', 'Greeting', false, 101);
    expect(result.sectionId).toBe(101);
    expect(result.payload.title).toBe('Greeting');
    expect(result.payload.content_json._editMode).toBe('form');
    expect(result.payload.content_json).not.toHaveProperty('rawText');
    expect(result.payload.content_json.clientName).toBe('Test');
  });

  it('builds payload in paste mode with _editMode paste and rawText', () => {
    const form = { clientName: '', inspirationalQuote: '' };
    const rawText = 'Pasted greeting content';
    const result = buildSavePayload(form, 'greeting', true, rawText, 'Greeting', false, 101);
    expect(result.payload.content_json._editMode).toBe('paste');
    expect(result.payload.content_json.rawText).toBe('Pasted greeting content');
  });

  it('includes is_wide_panel in payload', () => {
    const form = buildFormFromJson(functionalRequirementsJson, 'functional_requirements');
    const result = buildSavePayload(form, 'functional_requirements', false, '', 'Reqs', true, 301);
    expect(result.payload.is_wide_panel).toBe(true);
  });

  it('handles empty paste text', () => {
    const form = { clientName: '', inspirationalQuote: '' };
    const result = buildSavePayload(form, 'greeting', true, '', 'Greeting', false, 101);
    expect(result.payload.content_json.rawText).toBe('');
    expect(result.payload.content_json._editMode).toBe('paste');
  });

  it('form mode deletes rawText even if present', () => {
    const form = { clientName: 'X', inspirationalQuote: 'Y' };
    const result = buildSavePayload(form, 'greeting', false, 'stale text', 'Greeting', false, 101);
    expect(result.payload.content_json).not.toHaveProperty('rawText');
  });
});


// ─── Edge cases ──────────────────────────────────────────────────────────────

describe('edge cases', () => {
  it('buildFormFromJson handles undefined for all array fields', () => {
    const json = { index: '1', title: 'T' };
    const form = buildFormFromJson(json, 'executive_summary');
    expect(form.paragraphs).toBe('');
    expect(form.highlights).toBe('');
  });

  it('formToJson with whitespace-only text produces empty arrays', () => {
    const form = { index: '1', title: 'T', paragraphs: '   \n  \n  ', highlightsTitle: '', highlights: '' };
    const json = formToJson(form, 'executive_summary');
    expect(json.paragraphs).toEqual([]);
  });

  it('buildFormFromJson with extra unknown keys does not break', () => {
    const json = { clientName: 'X', unknownKey: 'ignored', inspirationalQuote: 'Q' };
    const form = buildFormFromJson(json, 'greeting');
    expect(form.clientName).toBe('X');
    expect(form).not.toHaveProperty('unknownKey');
  });

  it('formToJson for conversion_strategy with empty steps array', () => {
    const form = { index: '', title: '', intro: '', steps: [], resultTitle: '', result: '' };
    const json = formToJson(form, 'conversion_strategy');
    expect(json.steps).toEqual([]);
  });

  it('formToJson for development_stages with no current stages', () => {
    const form = {
      stages: [
        { icon: '🎨', title: 'Design', description: 'Desc', current: false },
      ],
    };
    const json = formToJson(form, 'development_stages');
    expect(json.stages[0]).not.toHaveProperty('current');
  });

  it('formToJson for functional_requirements with empty groups', () => {
    const form = { index: '', title: '', intro: '', groups: [], additionalModules: [] };
    const json = formToJson(form, 'functional_requirements');
    expect(json.groups).toEqual([]);
    expect(json.additionalModules).toEqual([]);
  });

  it('buildFormFromJson preserves scope metadata for groups', () => {
    const json = {
      index: '1', title: 'Reqs', intro: '',
      groups: [{
        id: 'gift_cards_module', icon: '🎁', title: 'Gift Cards',
        description: 'Desc', is_visible: false,
        is_calculator_module: true, default_selected: false,
        is_always_included: false, is_invite: false, invite_note: '',
        items: [],
      }],
      additionalModules: [{
        icon: '📬', title: 'Reports', description: 'Desc',
        is_visible: true, is_calculator_module: true,
        default_selected: true, is_always_included: false,
        is_invite: true, invite_note: 'Invite only',
        items: [],
      }],
    };
    const form = buildFormFromJson(json, 'functional_requirements');
    expect(form.groups[0].is_visible).toBe(false);
    expect(form.groups[0].is_calculator_module).toBe(true);
    expect(form.groups[0].default_selected).toBe(false);
    expect(form.groups[0].is_always_included).toBe(false);
    expect(form.additionalModules[0].is_visible).toBe(true);
    expect(form.additionalModules[0].is_invite).toBe(true);
    expect(form.additionalModules[0].invite_note).toBe('Invite only');
  });

  it('formToJson preserves scope metadata through round-trip', () => {
    const json = {
      index: '1', title: 'Reqs', intro: '',
      groups: [{
        id: 'gift_cards_module', icon: '🎁', title: 'Gift Cards',
        description: 'Desc', is_visible: false,
        is_calculator_module: true, default_selected: false,
        is_always_included: false, items: [],
      }],
      additionalModules: [],
    };
    const form = buildFormFromJson(json, 'functional_requirements');
    const output = formToJson(form, 'functional_requirements');
    expect(output.groups[0].is_visible).toBe(false);
    expect(output.groups[0].is_calculator_module).toBe(true);
    expect(output.groups[0].default_selected).toBe(false);
    expect(output.groups[0].is_always_included).toBe(false);
  });

  it('buildSavePayload for executive_summary in paste mode preserves structured data', () => {
    const form = buildFormFromJson(executiveSummaryJson, 'executive_summary');
    const result = buildSavePayload(form, 'executive_summary', true, 'Custom pasted text', 'Summary', false, 102);
    expect(result.payload.content_json.paragraphs).toEqual(['Primer párrafo.', 'Segundo párrafo.']);
    expect(result.payload.content_json.rawText).toBe('Custom pasted text');
    expect(result.payload.content_json._editMode).toBe('paste');
  });

  it('timeline with empty phases', () => {
    const form = { index: '', title: '', introText: '', totalDuration: '', phases: [] };
    const json = formToJson(form, 'timeline');
    expect(json.phases).toEqual([]);
  });

  it('investment with empty payment options and methods', () => {
    const form = buildFormFromJson({}, 'investment');
    const json = formToJson(form, 'investment');
    expect(json.whatsIncluded).toEqual([]);
    expect(json.paymentOptions).toEqual([]);
    expect(json.paymentMethods).toEqual([]);
    expect(json.valueReasons).toEqual([]);
  });

  it('next_steps with empty contact methods and steps', () => {
    const form = buildFormFromJson({}, 'next_steps');
    const json = formToJson(form, 'next_steps');
    expect(json.steps).toEqual([]);
    expect(json.contactMethods).toEqual([]);
  });
});


// ─── Paste panel detection helpers ───────────────────────────────────────────
// These replicate the logic from pages/proposal/[uuid]/index.vue

function isPastePanel(panel) {
  if (panel.section_type === 'functional_requirements_group') {
    return panel._group?._editMode === 'paste' && panel._group?.rawText;
  }
  return panel.content_json?._editMode === 'paste' && panel.content_json?.rawText;
}

function getPastePanelTitle(panel) {
  if (panel.section_type === 'functional_requirements_group') {
    return panel._group?.title || panel.title;
  }
  return panel.content_json?.title || panel.title;
}

function getPastePanelIndex(panel) {
  if (panel.section_type === 'functional_requirements_group') {
    return panel._subIndex || '';
  }
  return panel.content_json?.index || '';
}

function getPastePanelRawText(panel) {
  if (panel.section_type === 'functional_requirements_group') {
    return panel._group?.rawText || '';
  }
  return panel.content_json?.rawText || '';
}

describe('isPastePanel', () => {
  it('returns true for section with _editMode paste and rawText', () => {
    const panel = {
      section_type: 'executive_summary',
      content_json: { _editMode: 'paste', rawText: 'Some content' },
    };
    expect(isPastePanel(panel)).toBeTruthy();
  });

  it('returns false for section with _editMode form', () => {
    const panel = {
      section_type: 'executive_summary',
      content_json: { _editMode: 'form', paragraphs: ['P1'] },
    };
    expect(isPastePanel(panel)).toBeFalsy();
  });

  it('returns false for section with paste mode but empty rawText', () => {
    const panel = {
      section_type: 'executive_summary',
      content_json: { _editMode: 'paste', rawText: '' },
    };
    expect(isPastePanel(panel)).toBeFalsy();
  });

  it('returns false for section without _editMode', () => {
    const panel = {
      section_type: 'greeting',
      content_json: { clientName: 'Test' },
    };
    expect(isPastePanel(panel)).toBeFalsy();
  });

  it('returns true for functional_requirements_group with paste mode', () => {
    const panel = {
      section_type: 'functional_requirements_group',
      _group: { _editMode: 'paste', rawText: 'Group paste content', title: 'Vistas' },
    };
    expect(isPastePanel(panel)).toBeTruthy();
  });

  it('returns false for functional_requirements_group with form mode', () => {
    const panel = {
      section_type: 'functional_requirements_group',
      _group: { _editMode: 'form', title: 'Vistas', items: [] },
    };
    expect(isPastePanel(panel)).toBeFalsy();
  });

  it('returns false when content_json is empty object', () => {
    const panel = {
      section_type: 'context_diagnostic',
      content_json: {},
    };
    expect(isPastePanel(panel)).toBeFalsy();
  });
});

describe('getPastePanelTitle', () => {
  it('returns title from content_json for regular sections', () => {
    const panel = {
      section_type: 'executive_summary',
      title: 'Section Title',
      content_json: { title: 'Content Title', _editMode: 'paste', rawText: 'x' },
    };
    expect(getPastePanelTitle(panel)).toBe('Content Title');
  });

  it('falls back to panel title when content_json title is empty', () => {
    const panel = {
      section_type: 'executive_summary',
      title: 'Fallback Title',
      content_json: { title: '', _editMode: 'paste', rawText: 'x' },
    };
    expect(getPastePanelTitle(panel)).toBe('Fallback Title');
  });

  it('returns group title for functional_requirements_group', () => {
    const panel = {
      section_type: 'functional_requirements_group',
      title: 'Panel Title',
      _group: { title: 'Group Title' },
    };
    expect(getPastePanelTitle(panel)).toBe('Group Title');
  });
});

describe('getPastePanelIndex', () => {
  it('returns index from content_json for regular sections', () => {
    const panel = {
      section_type: 'executive_summary',
      content_json: { index: '1', _editMode: 'paste', rawText: 'x' },
    };
    expect(getPastePanelIndex(panel)).toBe('1');
  });

  it('returns _subIndex for functional_requirements_group', () => {
    const panel = {
      section_type: 'functional_requirements_group',
      _subIndex: '7.2',
    };
    expect(getPastePanelIndex(panel)).toBe('7.2');
  });

  it('returns empty string when index is missing', () => {
    const panel = {
      section_type: 'executive_summary',
      content_json: {},
    };
    expect(getPastePanelIndex(panel)).toBe('');
  });
});

describe('getPastePanelRawText', () => {
  it('returns rawText from content_json for regular sections', () => {
    const panel = {
      section_type: 'executive_summary',
      content_json: { rawText: 'Pasted markdown content', _editMode: 'paste' },
    };
    expect(getPastePanelRawText(panel)).toBe('Pasted markdown content');
  });

  it('returns rawText from _group for functional_requirements_group', () => {
    const panel = {
      section_type: 'functional_requirements_group',
      _group: { rawText: 'Group pasted content' },
    };
    expect(getPastePanelRawText(panel)).toBe('Group pasted content');
  });

  it('returns empty string when rawText is missing', () => {
    const panel = {
      section_type: 'executive_summary',
      content_json: { _editMode: 'form' },
    };
    expect(getPastePanelRawText(panel)).toBe('');
  });
});


// ─── Mode persistence on reopen ──────────────────────────────────────────────

describe('mode persistence (SectionEditor remembers _editMode)', () => {
  it('buildFormFromJson from paste-mode content_json preserves pasteMode state', () => {
    const contentJson = {
      index: '1', title: 'Summary',
      paragraphs: ['P1'], highlightsTitle: 'H', highlights: ['H1'],
      _editMode: 'paste', rawText: 'Pasted summary text.',
    };
    // The SectionEditor initializes pasteMode from content._editMode === 'paste'
    const initialContent = contentJson;
    const pasteMode = initialContent._editMode === 'paste';
    const pasteText = initialContent.rawText || '';

    expect(pasteMode).toBe(true);
    expect(pasteText).toBe('Pasted summary text.');

    // Verify the form still builds correctly from the same content_json
    const form = buildFormFromJson(contentJson, 'executive_summary');
    expect(form.paragraphs).toBe('P1');
  });

  it('buildFormFromJson from form-mode content_json opens in form mode', () => {
    const contentJson = {
      index: '1', title: 'Summary',
      paragraphs: ['P1'], highlightsTitle: 'H', highlights: ['H1'],
      _editMode: 'form',
    };
    const pasteMode = contentJson._editMode === 'paste';
    const pasteText = contentJson.rawText || '';

    expect(pasteMode).toBe(false);
    expect(pasteText).toBe('');
  });

  it('buildFormFromJson from content_json without _editMode opens in form mode', () => {
    const contentJson = {
      index: '1', title: 'Summary',
      paragraphs: ['P1'], highlightsTitle: 'H', highlights: ['H1'],
    };
    const pasteMode = contentJson._editMode === 'paste';
    expect(pasteMode).toBe(false);
  });

  it('functional_requirements group remembers paste mode per group', () => {
    const contentJson = {
      index: '7', title: 'Reqs', intro: '',
      groups: [
        { id: 'views', icon: '', title: 'Views', description: '', items: [], _editMode: 'paste', rawText: 'Pasted views' },
        { id: 'comps', icon: '', title: 'Components', description: '', items: [], _editMode: 'form' },
      ],
      additionalModules: [],
    };

    const form = buildFormFromJson(contentJson, 'functional_requirements');
    expect(form.groups[0]._pasteMode).toBe(true);
    expect(form.groups[0]._pasteText).toBe('Pasted views');
    expect(form.groups[1]._pasteMode).toBe(false);
    expect(form.groups[1]._pasteText).toBe('');
  });
});


// ─── Form-to-paste auto-sync ─────────────────────────────────────────────────

describe('form-to-paste auto-sync (formToReadableText reflects form state)', () => {
  it('reflects updated form data when toggling to paste mode', () => {
    const form = buildFormFromJson(greetingJson, 'greeting');
    const textBefore = formToReadableText(form, 'greeting');
    expect(textBefore).toContain('María García');

    // Simulate user editing form
    form.clientName = 'Updated Client';
    const textAfter = formToReadableText(form, 'greeting');
    expect(textAfter).toContain('Updated Client');
    expect(textAfter).not.toContain('María García');
  });

  it('executive_summary: form changes reflect in paste text', () => {
    const form = buildFormFromJson(executiveSummaryJson, 'executive_summary');
    form.paragraphs = 'New paragraph.';
    const text = formToReadableText(form, 'executive_summary');
    expect(text).toContain('New paragraph.');
    expect(text).not.toContain('Primer párrafo.');
  });

  it('conversion_strategy: adding a step reflects in paste text', () => {
    const form = buildFormFromJson(conversionStrategyJson, 'conversion_strategy');
    form.steps.push({ title: 'New Step', bullets: 'New bullet' });
    const text = formToReadableText(form, 'conversion_strategy');
    expect(text).toContain('New Step');
    expect(text).toContain('- New bullet');
  });

  it('buildSavePayload in paste mode captures current paste text, not form text', () => {
    const form = buildFormFromJson(greetingJson, 'greeting');
    const customPasteText = 'Manually typed paste content, NOT from form.';
    const result = buildSavePayload(form, 'greeting', true, customPasteText, 'Greeting', false, 1);
    // rawText should be the custom paste text, not the auto-synced text
    expect(result.payload.content_json.rawText).toBe(customPasteText);
    // But structured data still comes from form
    expect(result.payload.content_json.clientName).toBe('María García');
  });
});


describe('functional_requirements item ids (traceability)', () => {
  const frJsonWithIds = {
    index: '7',
    title: 'Requerimientos',
    intro: 'Detalle.',
    groups: [{
      id: 'views', icon: '🖥️', title: 'Vistas', description: 'Páginas.',
      items: [
        { icon: '🏠', name: 'Home', description: 'Landing.', id: 'item-views-home' },
        { icon: '📧', name: 'Contacto', description: 'Formulario.' },
      ],
    }],
    additionalModules: [],
  };

  it('buildFormFromJson preserves existing item ids and defaults missing ones to empty string', () => {
    const form = buildFormFromJson(frJsonWithIds, 'functional_requirements');
    expect(form.groups[0].items[0].id).toBe('item-views-home');
    expect(form.groups[0].items[1].id).toBe('');
  });

  it('formToJson keeps existing item ids and auto-assigns missing ones', () => {
    const form = buildFormFromJson(frJsonWithIds, 'functional_requirements');
    const json = formToJson(form, 'functional_requirements');
    expect(json.groups[0].items[0].id).toBe('item-views-home');
    expect(json.groups[0].items[1].id).toBe('item-views-contacto');
  });

  it('buildSavePayload auto-assigns ids to items missing one', () => {
    const form = buildFormFromJson(frJsonWithIds, 'functional_requirements');
    const { payload } = buildSavePayload(
      form, 'functional_requirements', false, '', 'Reqs', false, 99,
    );
    const items = payload.content_json.groups[0].items;
    expect(items[0].id).toBe('item-views-home');
    expect(items[1].id).toBe('item-views-contacto');
  });

  it('mounted editor emits save payload with auto-assigned item ids', async () => {
    const wrapper = mountSectionEditor({
      section: buildSection('functional_requirements', frJsonWithIds),
    });

    await wrapper.findAll('button').find((b) => b.text() === 'Guardar Sección').trigger('click');

    const emitted = wrapper.emitted('save');
    expect(emitted).toHaveLength(1);
    const items = emitted[0][0].payload.content_json.groups[0].items;
    expect(items[0].id).toBe('item-views-home');
    expect(items[1].id).toBe('item-views-contacto');
  });

  it('renders an editable ID field per item', () => {
    const wrapper = mountSectionEditor({
      section: buildSection('functional_requirements', frJsonWithIds),
    });
    expect(wrapper.text()).toContain('ID (enlace técnico)');
  });
});

describe('SectionEditor dirty tracking', () => {
  it('emits dirty-change(true) when a field is edited', async () => {
    const wrapper = mountSectionEditor();
    const titleInput = wrapper.find('input[type="text"]');
    await titleInput.setValue('Nuevo título');

    const emitted = wrapper.emitted('dirty-change');
    expect(emitted).toBeTruthy();
    expect(emitted[emitted.length - 1][0]).toBe(true);
  });

  it('re-baselines to clean when the section prop is replaced (store refresh)', async () => {
    const wrapper = mountSectionEditor();
    await wrapper.find('input[type="text"]').setValue('Nuevo título');
    expect(wrapper.emitted('dirty-change').at(-1)[0]).toBe(true);

    await wrapper.setProps({
      section: buildSection('greeting', { proposalTitle: 'Guardado', clientName: 'Cliente' }, { title: 'Nuevo título' }),
    });
    await wrapper.vm.$nextTick();

    const emitted = wrapper.emitted('dirty-change');
    expect(emitted[emitted.length - 1][0]).toBe(false);
  });
});
