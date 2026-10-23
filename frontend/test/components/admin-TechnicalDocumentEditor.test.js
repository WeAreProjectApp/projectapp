import { mount } from '@vue/test-utils';

jest.mock('../../utils/technicalModuleStub', () => ({
  createGenericTechnicalEpicStub: jest.fn((id, label) => ({
    epicKey: `E-${id}`,
    title: label,
    description: '',
    linked_module_ids: [id],
    requirements: [],
  })),
}));

import { createGenericTechnicalEpicStub } from '../../utils/technicalModuleStub';
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import TechnicalDocumentEditor from '../../components/BusinessProposal/admin/TechnicalDocumentEditor.vue';

const baseSection = {
  id: 1,
  title: 'Technical Spec',
  is_wide_panel: false,
  content_json: {
    purpose: 'Sistema de gestión de propuestas',
    stack: [{ layer: 'Frontend', technology: 'Vue 3', rationale: 'Reactivity' }],
    epics: [],
  },
};

function mountTechnicalDocumentEditor(props = {}) {
  return mount(TechnicalDocumentEditor, {
    props: {
      section: baseSection,
      moduleLinkOptions: [],
      // The editor collapses sections and link grids by default; the suite
      // asserts against fully rendered content, so mount everything open.
      expandAll: true,
      ...props,
    },
    global: {
      components: { BaseRichTextEditor, BaseSegmented },
      stubs: {
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  });
}

function purposeSource(wrapper) {
  return wrapper.get('[data-testid="technical-purpose-textarea"] [data-testid="rich-text-source-input"]');
}

const originalUseI18n = global.useI18n;

beforeEach(() => {
  global.useI18n = () => ({ t: (key) => key });
});

afterAll(() => {
  global.useI18n = originalUseI18n;
});

describe('TechnicalDocumentEditor', () => {
  it('renders the editor wrapper', () => {
    const wrapper = mountTechnicalDocumentEditor();

    expect(wrapper.find('[data-testid="technical-document-editor"]').exists()).toBe(true);
  });

  it('renders the purpose textarea with prefilled value', () => {
    const wrapper = mountTechnicalDocumentEditor();

    expect(purposeSource(wrapper).element.value).toBe('Sistema de gestión de propuestas');
  });

  it('renders section headings for key sections', () => {
    const wrapper = mountTechnicalDocumentEditor();

    expect(wrapper.text()).toContain('Propósito');
    expect(wrapper.text()).toContain('Stack tecnológico');
  });

  it('shows module stub selector when moduleLinkOptions are provided', () => {
    const wrapper = mountTechnicalDocumentEditor({
      moduleLinkOptions: [{ id: 'mod-1', label: 'E-commerce' }],
    });

    expect(wrapper.text()).toContain('Plantilla genérica por módulo comercial');
  });

  it('does not show stub selector when moduleLinkOptions is empty', () => {
    const wrapper = mountTechnicalDocumentEditor({ moduleLinkOptions: [] });

    expect(wrapper.text()).not.toContain('Plantilla genérica por módulo comercial');
  });

  it('emits canonical linked_module_ids when the source content uses legacy ids', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: 'legacy-epic',
              title: 'Legacy Epic',
              linked_module_ids: ['views'],
              requirements: [
                { title: 'Legacy Req', linked_module_ids: ['pwa_module'] },
              ],
            },
          ],
        },
      },
      moduleLinkOptions: [
        { id: 'group-views', label: 'Vistas', aliases: ['group-views', 'views'] },
        { id: 'module-pwa_module', label: 'PWA', aliases: ['module-pwa_module', 'pwa_module'] },
      ],
    });

    const saveButton = wrapper.findAll('button').find((button) =>
      button.text().includes('Guardar detalle técnico'),
    );
    expect(saveButton).toBeTruthy();
    await saveButton.trigger('click');

    const emitted = wrapper.emitted('save');
    expect(emitted).toHaveLength(1);
    const payload = emitted[0][0].payload.content_json;
    expect(payload.epics[0].linked_module_ids).toEqual(['group-views']);
    expect(payload.epics[0].requirements[0].linked_module_ids).toEqual(['module-pwa_module']);
  });
});

// ── Dynamic row additions ────────────────────────────────────────────────────

describe('TechnicalDocumentEditor dynamic rows', () => {
  // ── Stack rows ──────────────────────────────────────────────────────────

  it('adds a stack row when the + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaBtn = wrapper.findAll('button').find(b => b.text() === 'Fila');
    await filaBtn.trigger('click');

    // 1 pre-existing row + 1 new empty row
    expect(wrapper.vm.doc.stack).toHaveLength(2);
    expect(wrapper.vm.doc.stack[1]).toEqual({ layer: '', technology: '', rationale: '' });
  });

  it('removes a stack row when its delete button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const deleteBtn = wrapper.find('button[aria-label="Eliminar fila"]');
    await deleteBtn.trigger('click');

    expect(wrapper.vm.doc.stack).toHaveLength(0);
  });

  // ── Epics ───────────────────────────────────────────────────────────────

  it('adds a new epic when the + Módulo button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const addEpicBtn = wrapper.findAll('button').find(b => b.text() === 'Módulo');
    await addEpicBtn.trigger('click');

    expect(wrapper.vm.doc.epics).toHaveLength(1);
  });

  it('removes an epic when the Eliminar módulo button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [{ epicKey: 'mod-a', title: 'Module A', description: '', linked_module_ids: [], requirements: [] }],
        },
      },
    });

    const deleteBtn = wrapper.findAll('button').find(b => b.text() === 'Eliminar módulo');
    await deleteBtn.trigger('click');

    expect(wrapper.vm.doc.epics).toHaveLength(0);
  });

  // ── Requirements ────────────────────────────────────────────────────────

  it('adds a requirement to an epic when + Requerimiento is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [{ epicKey: 'mod-a', title: 'Module A', description: '', linked_module_ids: [], requirements: [] }],
        },
      },
    });

    const reqBtn = wrapper.findAll('button').find(b => b.text() === 'Requerimiento');
    await reqBtn.trigger('click');

    expect(wrapper.vm.doc.epics[0].requirements).toHaveLength(1);
  });

  it('removes a requirement from an epic when Quitar requerimiento is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: 'mod-a',
              title: 'Module A',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: 'req-1', title: 'Login', description: '', configuration: '', usageFlow: '', priority: 'high', linked_module_ids: [] },
              ],
            },
          ],
        },
      },
    });

    const quitarBtn = wrapper.findAll('button').find(b => b.text() === 'Quitar requerimiento');
    await quitarBtn.trigger('click');

    expect(wrapper.vm.doc.epics[0].requirements).toHaveLength(0);
  });

  // ── Save and validation ─────────────────────────────────────────────────

  it('emits save with serialized content_json when the save button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const emitted = wrapper.emitted('save');
    expect(emitted).toHaveLength(1);
    expect(emitted[0][0]).toMatchObject({ sectionId: baseSection.id });
    expect(emitted[0][0].payload.content_json).toBeDefined();
  });

  it('shows a validation error when two epics share the same epicKey', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'dup-key', title: 'First', description: '', linked_module_ids: [], requirements: [] },
            { epicKey: 'dup-key', title: 'Second', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.text()).toContain('epicKey duplicado');
  });

  it('accepts underscore epicKeys mirroring commercial ids (e.g. admin_module)', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'admin_module', title: 'Admin', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.text()).not.toContain('epicKey inválido');
    expect(wrapper.emitted('save')).toHaveLength(1);
  });

  // ── validate: epicKey format ───────────────────────────────────────────────

  it('shows validation error when epicKey contains uppercase letters', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'MyEpic', title: 'Invalid Key', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.text()).toContain('epicKey inválido');
  });

  it('shows validation error when epicKey contains spaces', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'my epic', title: 'Space Key', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.text()).toContain('epicKey inválido');
  });

  it('does not emit save when validation fails', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'INVALID', title: 'Bad', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.emitted('save')).toBeFalsy();
  });

  // ── validate: flowKey format ───────────────────────────────────────────────

  it('shows validation error when flowKey contains underscore characters', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: 'valid-epic',
              title: 'Epic',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: 'my_flow', title: 'Flow', description: '', configuration: '', usageFlow: '', priority: '', linked_module_ids: [] },
              ],
            },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.text()).toContain('flowKey inválido');
  });

  it('shows validation error when requirement has content but no title', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: '',
              title: 'Epic',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: 'my-flow', title: '', description: 'has content', configuration: '', usageFlow: '', priority: '', linked_module_ids: [] },
              ],
            },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.text()).toContain('título');
  });

  // ── handleSave: savedMsg ───────────────────────────────────────────────────

  it('shows saved message after a successful save', async () => {
    jest.useFakeTimers();
    const wrapper = mountTechnicalDocumentEditor();

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('✓ Guardado');
    jest.useRealTimers();
  });

  it('savedMsg is cleared after 3 seconds', async () => {
    jest.useFakeTimers();
    const wrapper = mountTechnicalDocumentEditor();

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');
    await wrapper.vm.$nextTick();

    jest.advanceTimersByTime(3001);
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).not.toContain('✓ Guardado');
    jest.useRealTimers();
  });

  // ── toggleLinkedId ─────────────────────────────────────────────────────────

  it('toggleLinkedId adds module id to epic linked_module_ids when checkbox is checked', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      moduleLinkOptions: [{ id: 'mod-auth', label: 'Auth' }],
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'auth', title: 'Auth Epic', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });

    const checkbox = wrapper.find('input[type="checkbox"]');
    await checkbox.trigger('change');
    await wrapper.vm.$nextTick();

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.epics[0].linked_module_ids).toContain('mod-auth');
  });

  it('toggleLinkedId removes module id from epic linked_module_ids when checkbox is unchecked', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      moduleLinkOptions: [{ id: 'mod-auth', label: 'Auth' }],
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'auth', title: 'Auth Epic', description: '', linked_module_ids: ['mod-auth'], requirements: [] },
          ],
        },
      },
    });

    const checkbox = wrapper.find('input[type="checkbox"]');
    await checkbox.trigger('change');
    await wrapper.vm.$nextTick();

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.epics[0].linked_module_ids).not.toContain('mod-auth');
  });

  // ── addApiDomain ───────────────────────────────────────────────────────────

  it('addApiDomain appends a domain row when the + Dominio button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const btn = wrapper.findAll('button').find(b => b.text() === 'Dominio');
    await btn.trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.apiDomains).toHaveLength(1);
  });

  // ── addMetric / addPractice ────────────────────────────────────────────────

  it('addMetric appends a metric row when the + Métrica button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const btn = wrapper.findAll('button').find(b => b.text() === 'Métrica');
    await btn.trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.performanceQuality.metrics).toHaveLength(1);
  });

  it('addPractice appends a practice row when the + Práctica button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const btn = wrapper.findAll('button').find(b => b.text() === 'Práctica');
    await btn.trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.performanceQuality.practices).toHaveLength(1);
  });

  // ── addEntityRow ───────────────────────────────────────────────────────────

  it('addEntityRow appends an entity row when the + Entidad button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const btn = wrapper.findAll('button').find(b => b.text() === 'Entidad');
    await btn.trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.dataModel.entities).toHaveLength(1);
  });

  // ── addPatternRow ──────────────────────────────────────────────────────────

  it('addPatternRow appends a pattern row when its + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[1].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.architecture.patterns).toHaveLength(1);
    expect(payload.architecture.patterns[0]).toEqual({ component: '', pattern: '', description: '' });
  });

  // ── addGrowthStrategyRow ───────────────────────────────────────────────────

  it('addGrowthStrategyRow appends a strategy row when its + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[2].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.growthReadiness.strategies).toHaveLength(1);
    expect(payload.growthReadiness.strategies[0]).toEqual({ dimension: '', preparation: '', evolution: '' });
  });

  // ── addIncluded / addExcluded ─────────────────────────────────────────────

  it('addIncluded appends an included integration row', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[3].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.integrations.included).toHaveLength(1);
  });

  it('addExcluded appends an excluded integration row', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[4].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.integrations.excluded).toHaveLength(1);
  });

  // ── addEnvironmentRow ─────────────────────────────────────────────────────

  it('addEnvironmentRow appends an environment row when its + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[5].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.environments).toHaveLength(1);
    expect(payload.environments[0]).toEqual({ name: '', purpose: '', url: '', database: '', whoAccesses: '' });
  });

  // ── addSecurityRow ────────────────────────────────────────────────────────

  it('addSecurityRow appends a security row when its + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[6].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.security).toHaveLength(1);
    expect(payload.security[0]).toEqual({ aspect: '', implementation: '' });
  });

  // ── addQualityDimension / addTestType ─────────────────────────────────────

  it('addQualityDimension appends a quality dimension row when its + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[7].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.quality.dimensions).toHaveLength(1);
    expect(payload.quality.dimensions[0]).toEqual({ dimension: '', evaluates: '', standard: '' });
  });

  it('addTestType appends a test type row when its + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[8].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.quality.testTypes).toHaveLength(1);
    expect(payload.quality.testTypes[0]).toEqual({ type: '', validates: '', tool: '', whenRun: '' });
  });

  // ── addDecision ───────────────────────────────────────────────────────────

  it('addDecision appends a decision row when its + Fila button is clicked', async () => {
    const wrapper = mountTechnicalDocumentEditor();

    const filaButtons = wrapper.findAll('button').filter(b => b.text() === 'Fila');
    await filaButtons[9].trigger('click');

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload.content_json;
    expect(payload.decisions).toHaveLength(1);
    expect(payload.decisions[0]).toEqual({ decision: '', alternative: '', reason: '' });
  });

  // ── validate: duplicate flowKey ───────────────────────────────────────────

  it('shows validation error when two requirements share the same flowKey', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: 'epic-a',
              title: 'Epic A',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: 'shared-flow', title: 'First req', description: '', configuration: '', usageFlow: '', priority: '', linked_module_ids: [] },
              ],
            },
            {
              epicKey: 'epic-b',
              title: 'Epic B',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: 'shared-flow', title: 'Second req', description: '', configuration: '', usageFlow: '', priority: '', linked_module_ids: [] },
              ],
            },
          ],
        },
      },
    });

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    expect(wrapper.text()).toContain('flowKey duplicado');
    expect(wrapper.emitted('save')).toBeFalsy();
  });

  // ── mergeContent branch coverage ─────────────────────────────────────────

  it('mergeContent returns empty purpose when content_json is null', () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: { ...baseSection, content_json: null },
    });
    expect(purposeSource(wrapper).element.value).toBe('');
  });

  it('mergeContent returns empty purpose when content_json.purpose is not a string', () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: { ...baseSection, content_json: { purpose: 42, epics: [] } },
    });
    expect(purposeSource(wrapper).element.value).toBe('');
  });

  it('mergeContent uses empty stack when content_json.stack is not an array', () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: { ...baseSection, content_json: { purpose: 'test', stack: 'invalid', epics: [] } },
    });
    // No stack rows should be shown beyond header
    const stackDeleteBtns = wrapper.findAll('button').filter(b => b.text() === 'Quitar fila');
    expect(stackDeleteBtns).toHaveLength(0);
  });

  it('mergeContent uses empty epics when content_json.epics is not an array', () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: { ...baseSection, content_json: { purpose: 'test', epics: 'invalid' } },
    });
    expect(wrapper.findAll('button').filter(b => b.text() === 'Eliminar módulo')).toHaveLength(0);
  });

  // ── validate branch coverage ──────────────────────────────────────────────

  it('validate accepts epicKey with numbers and hyphens', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: 'epic-1-auth', title: 'Auth', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });
    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');
    expect(wrapper.text()).not.toContain('epicKey inválido');
    expect(wrapper.emitted('save')).toBeTruthy();
  });

  it('validate skips epicKey format check when epicKey is empty', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            { epicKey: '', title: 'No key epic', description: '', linked_module_ids: [], requirements: [] },
          ],
        },
      },
    });
    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');
    expect(wrapper.text()).not.toContain('epicKey inválido');
    expect(wrapper.emitted('save')).toBeTruthy();
  });

  it('validate returns missing-title error when requirement.usageFlow is set but title is empty', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: '',
              title: 'Epic',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: '', title: '', description: '', configuration: '', usageFlow: 'User opens app', priority: '', linked_module_ids: [] },
              ],
            },
          ],
        },
      },
    });
    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');
    expect(wrapper.text()).toContain('título');
  });

  it('validate returns missing-title error when requirement.configuration is set but title is empty', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: '',
              title: 'Epic',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: '', title: '', description: '', configuration: 'config-data', usageFlow: '', priority: '', linked_module_ids: [] },
              ],
            },
          ],
        },
      },
    });
    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');
    expect(wrapper.text()).toContain('título');
  });

  // ── requirement removal index accuracy ───────────────────────────────────

  it('removes the second requirement from a two-requirement epic correctly', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...baseSection,
        content_json: {
          ...baseSection.content_json,
          epics: [
            {
              epicKey: 'my-epic',
              title: 'My Epic',
              description: '',
              linked_module_ids: [],
              requirements: [
                { flowKey: 'req-first', title: 'First', description: '', configuration: '', usageFlow: '', priority: '', linked_module_ids: [] },
                { flowKey: 'req-second', title: 'Second', description: '', configuration: '', usageFlow: '', priority: '', linked_module_ids: [] },
              ],
            },
          ],
        },
      },
    });

    const quitarBtns = wrapper.findAll('button').filter(b => b.text() === 'Quitar requerimiento');
    expect(quitarBtns).toHaveLength(2);

    await quitarBtns[1].trigger('click');

    expect(wrapper.findAll('button').filter(b => b.text() === 'Quitar requerimiento')).toHaveLength(1);
  });

  // ── insertGenericStub ──────────────────────────────────────────────────────

  it('insertGenericStub appends a stub epic when a module is selected and the button is clicked', async () => {
    createGenericTechnicalEpicStub.mockClear();

    const wrapper = mountTechnicalDocumentEditor({
      moduleLinkOptions: [{ id: 'mod-landing', label: 'Landing' }],
    });

    const select = wrapper.find('select');
    await select.setValue('mod-landing');

    const stubBtn = wrapper.findAll('button').find(b => b.text().includes('Insertar módulo genérico'));
    await stubBtn.trigger('click');

    expect(createGenericTechnicalEpicStub).toHaveBeenCalledWith('mod-landing', 'Landing');
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll('[data-testid="technical-epic-description-textarea"]').length).toBe(1);
  });
});


describe('linked_item_ids (item traceability)', () => {
  const ITEM_OPTIONS = [
    {
      groupId: 'views',
      groupLabel: '🖥️ Vistas',
      items: [
        { id: 'item-views-home', label: '🏠 Home' },
        { id: 'item-views-contacto', label: '📧 Contacto' },
      ],
    },
  ];

  const sectionWithEpic = {
    ...baseSection,
    content_json: {
      ...baseSection.content_json,
      epics: [{
        epicKey: 'views',
        title: 'Vistas',
        description: '',
        linked_module_ids: [],
        requirements: [{
          flowKey: 'req-home',
          title: 'Home dinámico',
          description: '',
          configuration: '',
          usageFlow: '',
          priority: '',
          linked_module_ids: [],
          linked_item_ids: ['item-views-home'],
        }],
      }],
    },
  };

  it('renders the grouped item checkboxes when itemLinkOptions are provided', () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: sectionWithEpic,
      itemLinkOptions: ITEM_OPTIONS,
    });

    const block = wrapper.find('[data-testid="technical-req-item-links"]');
    expect(block.exists()).toBe(true);
    expect(block.text()).toContain('Vistas');
    expect(block.text()).toContain('Home');
    expect(block.text()).toContain('Contacto');
  });

  it('hides the item block when itemLinkOptions is empty', () => {
    const wrapper = mountTechnicalDocumentEditor({ section: sectionWithEpic });
    expect(wrapper.find('[data-testid="technical-req-item-links"]').exists()).toBe(false);
  });

  it('checks the boxes for already-linked items', () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: sectionWithEpic,
      itemLinkOptions: ITEM_OPTIONS,
    });

    const boxes = wrapper.find('[data-testid="technical-req-item-links"]').findAll('input[type="checkbox"]');
    expect(boxes[0].element.checked).toBe(true);  // item-views-home
    expect(boxes[1].element.checked).toBe(false); // item-views-contacto
  });

  it('toggling a checkbox updates linked_item_ids in the save payload', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: sectionWithEpic,
      itemLinkOptions: ITEM_OPTIONS,
    });

    const boxes = wrapper.find('[data-testid="technical-req-item-links"]').findAll('input[type="checkbox"]');
    await boxes[1].trigger('change');
    await wrapper.findAll('button').find((b) => b.text().startsWith('Guardar detalle')).trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload;
    expect(payload.content_json.epics[0].requirements[0].linked_item_ids)
      .toEqual(['item-views-home', 'item-views-contacto']);
  });

  it('normalizes camelCase linkedItemIds from incoming content_json', () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: {
        ...sectionWithEpic,
        content_json: {
          ...sectionWithEpic.content_json,
          epics: [{
            epicKey: 'views',
            title: 'Vistas',
            requirements: [{ flowKey: 'r', title: 'R', linkedItemIds: ['item-views-home', 'item-views-home'] }],
          }],
        },
      },
      itemLinkOptions: ITEM_OPTIONS,
    });

    const boxes = wrapper.find('[data-testid="technical-req-item-links"]').findAll('input[type="checkbox"]');
    expect(boxes[0].element.checked).toBe(true);
  });

  it('addRequirement initializes linked_item_ids as an empty array', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: sectionWithEpic,
      itemLinkOptions: ITEM_OPTIONS,
    });

    await wrapper.findAll('button').find((b) => b.text() === 'Requerimiento').trigger('click');
    await wrapper.findAll('button').find((b) => b.text().startsWith('Guardar detalle')).trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload;
    const reqs = payload.content_json.epics[0].requirements;
    expect(reqs[reqs.length - 1].linked_item_ids).toEqual([]);
  });

  it('blocks saving when an included commercial item has no requirement link', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: sectionWithEpic,
      itemLinkOptions: ITEM_OPTIONS.map((group) => ({ ...group, isRequiredForCoverage: true })),
    });

    await wrapper.findAll('button').find((button) => button.text().startsWith('Guardar detalle')).trigger('click');

    expect(wrapper.emitted('save')).toBeFalsy();
    expect(wrapper.text()).toContain('Faltan 1 items obligatorios');
  });

  it('shows unlinked optional items without blocking the save', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      section: sectionWithEpic,
      itemLinkOptions: ITEM_OPTIONS.map((group) => ({ ...group, isRequiredForCoverage: false })),
    });

    await wrapper.findAll('button').find((button) => button.text().startsWith('Guardar detalle')).trigger('click');

    expect(wrapper.emitted('save')).toHaveLength(1);
    expect(wrapper.text()).toContain('items opcionales aún no enlazados');
  });
});

// ── Collapse-by-default layout ───────────────────────────────────────────────

describe('TechnicalDocumentEditor collapse behavior', () => {
  const epicSection = {
    ...baseSection,
    content_json: {
      ...baseSection.content_json,
      epics: [{
        epicKey: 'auth',
        title: 'Auth',
        description: 'Login y sesión',
        linked_module_ids: [],
        requirements: [{
          flowKey: 'login',
          title: 'Login',
          description: '',
          configuration: '',
          usageFlow: '',
          linked_module_ids: [],
          linked_item_ids: [],
        }],
      }],
    },
  };

  it('starts with only Propósito expanded when expandAll is off', () => {
    const wrapper = mountTechnicalDocumentEditor({ expandAll: false, section: epicSection });

    expect(wrapper.find('[data-testid="technical-purpose-textarea"]').exists()).toBe(true);
    // Collapsed sections keep their header visible but do not mount their body.
    expect(wrapper.find('[data-testid="technical-section-toggle-stack"]').exists()).toBe(true);
    expect(wrapper.find('input[placeholder="Capa"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="technical-epic-description-textarea"]').exists()).toBe(false);
  });

  it('mounts a section body on header click and unmounts it on the second click', async () => {
    const wrapper = mountTechnicalDocumentEditor({ expandAll: false });

    const toggle = wrapper.find('[data-testid="technical-section-toggle-stack"]');
    await toggle.trigger('click');
    expect(wrapper.find('input[placeholder="Capa"]').exists()).toBe(true);

    await toggle.trigger('click');
    expect(wrapper.find('input[placeholder="Capa"]').exists()).toBe(false);
  });

  it('emits the full content_json on save even with every section collapsed', async () => {
    const wrapper = mountTechnicalDocumentEditor({ expandAll: false, section: epicSection });

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Guardar detalle técnico'));
    await saveBtn.trigger('click');

    const emitted = wrapper.emitted('save');
    expect(emitted).toHaveLength(1);
    const payload = emitted[0][0].payload.content_json;
    expect(payload.stack).toHaveLength(1);
    expect(payload.epics[0].requirements[0].flowKey).toBe('login');
  });

  it('reveals the requirement link grids only after the disclosure click', async () => {
    const wrapper = mountTechnicalDocumentEditor({
      expandAll: false,
      section: epicSection,
      moduleLinkOptions: [{ id: 'group-views', label: 'Vistas', aliases: ['group-views'] }],
      itemLinkOptions: [{ groupId: 'views', groupLabel: 'Vistas', items: [{ id: 'item-views-home', label: 'Home' }] }],
    });

    // Section collapsed: not even the disclosure exists yet.
    expect(wrapper.find('[data-testid="technical-req-links-toggle"]').exists()).toBe(false);

    await wrapper.find('[data-testid="technical-section-toggle-epics"]').trigger('click');
    expect(wrapper.find('[data-testid="technical-req-links-toggle"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="technical-req-item-links"]').exists()).toBe(false);

    await wrapper.find('[data-testid="technical-req-links-toggle"]').trigger('click');
    expect(wrapper.find('[data-testid="technical-req-item-links"]').exists()).toBe(true);
  });
});
