/**
 * Tests for ProposalDefaultsPanel.vue.
 *
 * Covers: rendering, slug preview, handleSaveGeneral success/error,
 * loadDefaults on mount, section loading, toggleSection,
 * switchLanguage, handleReset/confirmReset, email template loading,
 * selectEmailTemplate, JSON tab save/error,
 * handleApplyDefaultsTechnicalJson error.
 */

// ESM/UMD packages in the deep component chain that Jest can't parse directly
jest.mock('marked', () => ({ marked: jest.fn((t) => t) }));
jest.mock('dompurify', () => ({ default: { sanitize: jest.fn((t) => t) } }));
jest.mock('vue3-emoji-picker', () => ({ default: { name: 'EmojiPicker', template: '<div />' } }));

const mockProposalStore = {
  fetchProposalDefaults: jest.fn(),
  saveProposalDefaults: jest.fn(),
  resetProposalDefaults: jest.fn(),
  fetchEmailTemplates: jest.fn(),
  fetchEmailTemplateDetail: jest.fn(),
  saveEmailTemplate: jest.fn(),
  resetEmailTemplate: jest.fn(),
  previewEmailTemplate: jest.fn(),
};

// Nuxt auto-imports — must be set before the component is required
global.useProposalStore = jest.fn(() => mockProposalStore);
global.useRoute = () => ({ query: {} });

let capturedConfirmOpts = null;
const mockConfirmModal = {
  confirmState: { open: false, title: '', message: '', confirmText: '', cancelText: '', variant: '' },
  requestConfirm: jest.fn((opts) => { capturedConfirmOpts = opts; }),
  handleConfirmed: jest.fn(),
  handleCancelled: jest.fn(),
};

jest.mock('../../composables/useConfirmModal', () => ({
  useConfirmModal: () => mockConfirmModal,
}));

let capturedRefreshHandler = null;
jest.mock('../../composables/usePanelRefresh', () => ({
  usePanelRefresh: (fn) => { capturedRefreshHandler = fn; },
}));

jest.mock('../../composables/useSellerPrompt', () => {
  const { ref } = require('vue');
  return {
    useSellerPrompt: () => ({
      promptText: ref(''),
      isEditing: ref(false),
      DEFAULT_PROMPT: '',
      loadSavedPrompt: jest.fn(),
      savePrompt: jest.fn(),
      resetPrompt: jest.fn(),
      copyPrompt: jest.fn().mockResolvedValue(undefined),
      downloadPrompt: jest.fn(),
    }),
  };
});

jest.mock('../../composables/useTechnicalPrompt', () => {
  const { ref } = require('vue');
  return {
    useTechnicalPrompt: () => ({
      promptText: ref(''),
      isEditing: ref(false),
      DEFAULT_PROMPT: '',
      loadSavedPrompt: jest.fn(),
      savePrompt: jest.fn(),
      resetPrompt: jest.fn(),
      copyPrompt: jest.fn().mockResolvedValue(undefined),
      downloadPrompt: jest.fn(),
    }),
  };
});

import { mount } from '@vue/test-utils';
import ProposalDefaultsPanel from '../../components/panel/defaults/ProposalDefaultsPanel.vue';

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

const defaultDataResponse = {
  success: true,
  data: {
    default_currency: 'COP',
    default_total_investment: 0,
    hosting_percent: 30,
    hosting_discount_semiannual: 20,
    hosting_discount_quarterly: 10,
    expiration_days: 21,
    reminder_days: 3,
    urgency_reminder_days: 7,
    default_discount_percent: 0,
    default_slug_pattern: '{client_name}',
    sections_json: [],
    updated_at: null,
  },
};

const BaseInputStub = {
  props: ['modelValue', 'type', 'placeholder', 'disabled'],
  emits: ['update:modelValue'],
  template: '<input :type="type || \'text\'" :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
};

const BaseSelectStub = {
  props: ['modelValue', 'options', 'disabled'],
  emits: ['update:modelValue'],
  template: '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="opt in (options || [])" :key="opt.value ?? opt" :value="opt.value ?? opt">{{ opt.label ?? String(opt) }}</option></select>',
};

const BaseTextareaStub = {
  props: ['modelValue', 'rows', 'placeholder', 'disabled'],
  emits: ['update:modelValue'],
  template: '<textarea :value="modelValue" :rows="rows" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
};

const BaseButtonStub = {
  props: ['type', 'disabled', 'loading', 'as', 'to', 'variant', 'size'],
  emits: ['click'],
  template: '<button :type="type || \'button\'" :disabled="disabled || loading" @click="$emit(\'click\', $event)"><slot /></button>',
};

const BaseTabsStub = {
  props: ['modelValue', 'tabs'],
  emits: ['update:modelValue'],
  template: '<div><button v-for="t in tabs" :key="t.id" type="button" @click="$emit(\'update:modelValue\', t.id)">{{ t.label }}</button></div>',
};

function mountPanel(tabOverride = 'general', stubOverrides = {}) {
  global.useRoute = () => ({ query: { tab: tabOverride } });
  return mount(ProposalDefaultsPanel, {
    global: {
      stubs: {
        ...defaultStubs(),
        ...stubOverrides,
      },
    },
  });
}

function defaultStubs() {
  return {
    ResponsiveTabs: { template: '<div />' },
    ConfirmModal: { template: '<div />' },
    SectionEditor: { template: '<div data-testid="section-editor" />' },
    TechnicalDocumentEditor: { template: '<div data-testid="technical-editor" />' },
    SectionPreviewModal: { template: '<div />' },
    PromptSubTabsPanel: { template: '<div><slot name="commercial" /><slot name="technical" /></div>' },
    TabSplitLayout: { template: '<div><slot name="main" /><slot name="aside" /></div>' },
    UiTooltip: { template: '<div><slot /></div>' },
    NuxtLink: { template: '<a><slot /></a>' },
    Teleport: { template: '<div><slot /></div>' },
    Transition: { template: '<div><slot /></div>' },
    BaseModal: {
      props: ['modelValue'],
      template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
    },
    BaseInput: BaseInputStub,
    BaseSelect: BaseSelectStub,
    BaseTextarea: BaseTextareaStub,
    BaseButton: BaseButtonStub,
    BaseTabs: BaseTabsStub,
    BaseTooltip: {
      template: '<div><slot name="trigger" tooltip-id="test-tooltip" /><slot /></div>',
    },
    BaseFormField: { template: '<div><slot /></div>' },
    BaseBadge: { template: '<span><slot /></span>' },
    BaseToggle: { template: '<input type="checkbox" />' },
  };
}

describe('ProposalDefaultsPanel', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    capturedConfirmOpts = null;
    mockProposalStore.fetchProposalDefaults.mockReset().mockResolvedValue(defaultDataResponse);
    mockProposalStore.saveProposalDefaults.mockReset().mockResolvedValue({ success: true, data: {} });
    mockProposalStore.resetProposalDefaults.mockReset().mockResolvedValue({ success: true });
    mockProposalStore.fetchEmailTemplates.mockReset().mockResolvedValue({ success: true, data: [] });
    mockProposalStore.fetchEmailTemplateDetail.mockReset().mockResolvedValue({
      success: true,
      data: { editable_fields: [], is_active: true },
    });
    mockProposalStore.saveEmailTemplate.mockReset().mockResolvedValue({ success: true });
    mockProposalStore.resetEmailTemplate.mockReset().mockResolvedValue({ success: true });
    mockProposalStore.previewEmailTemplate.mockReset().mockResolvedValue({ success: false });
    mockConfirmModal.requestConfirm.mockClear();
    global.navigator = { clipboard: { writeText: jest.fn().mockResolvedValue(undefined) } };
    global.URL = { createObjectURL: jest.fn().mockReturnValue('blob://mock'), revokeObjectURL: jest.fn() };
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe('rendering', () => {
    it('renders the panel intro text', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      expect(wrapper.text()).toContain('Configura los valores iniciales');
    });

    it('renders the slug pattern input', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      expect(wrapper.find('[data-testid="defaults-slug-pattern"]').exists()).toBe(true);
    });

    it('shows maria-lopez in the slug preview for the default {client_name} pattern', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      expect(wrapper.text()).toContain('maria-lopez');
    });
  });

  // ── handleSaveGeneral ─────────────────────────────────────────────────────

  describe('handleSaveGeneral', () => {
    it('calls saveProposalDefaults when the general form is submitted', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockProposalStore.saveProposalDefaults).toHaveBeenCalled();
    });

    it('shows success feedback after saving general defaults', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('Valores generales guardados correctamente.');
    });

    it('shows error feedback when save fails', async () => {
      mockProposalStore.saveProposalDefaults.mockResolvedValue({ success: false });
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('Error al guardar los valores generales.');
    });
  });

  // ── loadDefaults ──────────────────────────────────────────────────────────

  describe('loadDefaults', () => {
    it('calls fetchProposalDefaults with es on mount', async () => {
      mountPanel();
      await flushPromises();

      expect(mockProposalStore.fetchProposalDefaults).toHaveBeenCalledWith('es');
    });

    it('applies the returned currency to the form selects', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        ...defaultDataResponse,
        data: { ...defaultDataResponse.data, default_currency: 'USD' },
      });
      const wrapper = mountPanel();
      await flushPromises();
      await wrapper.vm.$nextTick();

      const currencySelect = wrapper.findAll('select').at(1);
      expect(currencySelect.element.value).toBe('USD');
    });

    it('renders section titles after defaults are loaded', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [
            { section_type: 'intro', title: 'Introducción al proyecto', order: 0, content_json: {} },
          ],
        },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      expect(wrapper.text()).toContain('Introducción al proyecto');
    });
  });

  // ── switchLanguage ────────────────────────────────────────────────────────

  describe('switchLanguage', () => {
    it('calls loadDefaults with en when the English button is clicked without pending changes', async () => {
      const wrapper = mountPanel('sections');
      await flushPromises();
      mockProposalStore.fetchProposalDefaults.mockClear();

      await wrapper.findAll('button').find((btn) => btn.text() === 'English').trigger('click');
      await flushPromises();

      expect(mockProposalStore.fetchProposalDefaults).toHaveBeenCalledWith('en');
    });
  });

  // ── toggleSection ─────────────────────────────────────────────────────────

  describe('toggleSection', () => {
    it('shows the section editor when a section row header is clicked', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [
            { section_type: 'intro', title: 'Introducción', order: 0, content_json: {} },
          ],
        },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      await wrapper.find('div.cursor-pointer').trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="section-editor"]').exists()).toBe(true);
    });
  });

  // ── handleSaveAll — stale snapshot guard ──────────────────────────────────

  describe('handleSaveAll', () => {
    const LOADED_AT = '2026-07-28T03:15:23.672677Z';

    // The panel keeps sections_json in memory from page load and writes it back
    // wholesale, so every save must state which version it edited.
    async function mountWithAnEditedSection() {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [
            { section_type: 'intro', title: 'Introducción', order: 0, content_json: {} },
          ],
          updated_at: LOADED_AT,
        },
      });
      const wrapper = mountPanel('sections', {
        SectionEditor: {
          template: '<button data-testid="section-editor" @click="$emit(\'save\', { sectionId: 0, payload: { title: \'Nuevo\', content_json: {} } })" />',
        },
      });
      await flushPromises();
      await wrapper.find('div.cursor-pointer').trigger('click');
      await wrapper.vm.$nextTick();
      await wrapper.find('[data-testid="section-editor"]').trigger('click');
      await wrapper.vm.$nextTick();
      return wrapper;
    }

    function saveAllButton(wrapper) {
      return wrapper.findAll('button').find(
        b => b.text().includes('Guardar Todos los Cambios'),
      );
    }

    it('sends the version it loaded so the backend can refuse a stale overwrite', async () => {
      const wrapper = await mountWithAnEditedSection();

      await saveAllButton(wrapper).trigger('click');
      await flushPromises();

      expect(mockProposalStore.saveProposalDefaults).toHaveBeenCalledWith(
        'es', expect.any(Array), null, LOADED_AT,
      );
    });

    it('shows the conflict message when the stored defaults moved on', async () => {
      mockProposalStore.saveProposalDefaults.mockResolvedValue({
        success: false,
        code: 'stale_defaults',
        message: 'Los valores por defecto cambiaron desde que abriste esta página.',
      });
      const wrapper = await mountWithAnEditedSection();

      await saveAllButton(wrapper).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('cambiaron desde que abriste esta página');
    });

    it('keeps the edited sections on screen after a conflict', async () => {
      mockProposalStore.saveProposalDefaults.mockResolvedValue({
        success: false,
        code: 'stale_defaults',
        message: 'Los valores por defecto cambiaron desde que abriste esta página.',
      });
      const wrapper = await mountWithAnEditedSection();

      await saveAllButton(wrapper).trigger('click');
      await flushPromises();

      // Still marked as pending, so the admin can copy them over the current
      // version instead of losing the work to an automatic refresh.
      expect(wrapper.text()).toContain('sección(es) modificada(s)');
    });

    it('adopts the version returned by a successful save as the next base', async () => {
      mockProposalStore.saveProposalDefaults.mockResolvedValue({
        success: true,
        data: { updated_at: '2026-07-28T15:00:00.000000Z' },
      });
      const wrapper = await mountWithAnEditedSection();

      await saveAllButton(wrapper).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Valores por defecto guardados correctamente');
      expect(mockProposalStore.fetchProposalDefaults).toHaveBeenCalledTimes(1);
    });
  });

  // ── handleReset / confirmReset ────────────────────────────────────────────

  describe('handleReset', () => {
    it('shows the reset confirmation when Restaurar valores originales is clicked', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }],
        },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Restaurar valores originales')).trigger('click');

      expect(wrapper.text()).toContain('¿Restaurar valores originales?');
    });
  });

  describe('confirmReset', () => {
    it('calls resetProposalDefaults when the reset is confirmed', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }],
        },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Restaurar valores originales')).trigger('click');
      await wrapper.findAll('button').find((btn) => btn.text().includes('Sí, restaurar')).trigger('click');
      await flushPromises();

      expect(mockProposalStore.resetProposalDefaults).toHaveBeenCalledWith('es');
    });
  });

  // ── Email templates ───────────────────────────────────────────────────────

  describe('email templates', () => {
    it('calls fetchEmailTemplates on mount', async () => {
      mountPanel();
      await flushPromises();

      expect(mockProposalStore.fetchEmailTemplates).toHaveBeenCalled();
    });

    it('renders email template names from the loaded list', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValue({
        success: true,
        data: [
          { template_key: 'tpl-1', name: 'Correo de seguimiento', category: 'client', description: '', editable_fields_count: 2, is_customized: false, is_active: true },
        ],
      });
      const wrapper = mountPanel('emails');
      await flushPromises();

      expect(wrapper.text()).toContain('Correo de seguimiento');
    });

    it('calls fetchEmailTemplateDetail when a template is selected', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValue({
        success: true,
        data: [
          { template_key: 'tpl-1', name: 'Template 1', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true },
        ],
      });
      const wrapper = mountPanel('emails');
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Template 1')).trigger('click');
      await flushPromises();

      expect(mockProposalStore.fetchEmailTemplateDetail).toHaveBeenCalledWith('tpl-1');
    });
  });

  // ── JSON tab ──────────────────────────────────────────────────────────────

  describe('JSON tab', () => {
    it('shows an error message when saveEditJson receives invalid JSON', async () => {
      const wrapper = mountPanel('json');
      await flushPromises();

      // There are 3 "Editar" buttons (prompt×2, json×1); the JSON tab's is last
      const editarButtons = wrapper.findAll('button').filter((btn) => btn.text() === 'Editar');
      await editarButtons[editarButtons.length - 1].trigger('click');
      await wrapper.vm.$nextTick();

      // JSON edit textarea is conditionally rendered (v-else-if); it's the last font-mono textarea
      const jsonTextarea = wrapper.findAll('textarea.font-mono').at(-1);
      await jsonTextarea.setValue('{ invalid json }');
      await wrapper.findAll('button').find((btn) => btn.text().includes('Guardar cambios')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('JSON inválido');
    });

    it('calls saveProposalDefaults when valid JSON with sections is saved', async () => {
      const wrapper = mountPanel('json');
      await flushPromises();

      const editarButtons = wrapper.findAll('button').filter((btn) => btn.text() === 'Editar');
      await editarButtons[editarButtons.length - 1].trigger('click');
      await wrapper.vm.$nextTick();

      const validJson = JSON.stringify({
        language: 'es',
        sections: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }],
      });
      const jsonTextarea = wrapper.findAll('textarea.font-mono').at(-1);
      await jsonTextarea.setValue(validJson);
      await wrapper.findAll('button').find((btn) => btn.text().includes('Guardar cambios')).trigger('click');
      await flushPromises();

      expect(mockProposalStore.saveProposalDefaults).toHaveBeenCalled();
    });
  });

  // ── handleApplyDefaultsTechnicalJson ─────────────────────────────────────

  describe('handleApplyDefaultsTechnicalJson', () => {
    it('shows JSON error when the technical JSON textarea contains invalid JSON', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [
            { section_type: 'technical_document', title: 'Det. técnico', order: 0, content_json: { epics: [] } },
          ],
        },
      });
      const wrapper = mountPanel('technical');
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text() === 'JSON').trigger('click');
      await wrapper.vm.$nextTick();

      const technicalJsonTextarea = wrapper.find('textarea[rows="24"]');
      await technicalJsonTextarea.setValue('not valid json {');
      await wrapper.findAll('button').find((btn) => btn.text().includes('Aplicar a plantilla')).trigger('click');

      expect(wrapper.text()).toContain('JSON inválido');
    });
  });

  // ── Language switch ───────────────────────────────────────────────────────

  describe('language switch', () => {
    it('calls fetchProposalDefaults with en when the English button is clicked', async () => {
      const wrapper = mountPanel('general');
      await flushPromises();

      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce(defaultDataResponse);
      const enBtn = wrapper.findAll('button').find(b => b.text() === 'English');
      await enBtn.trigger('click');
      await flushPromises();

      expect(mockProposalStore.fetchProposalDefaults).toHaveBeenCalledWith('en');
    });

    it('calls requestConfirm when switching language with unsaved section changes', async () => {
      const wrapper = mountPanel('general');
      await flushPromises();

      // Manually mark a section as unsaved via internal state
      wrapper.vm.savedSections.add(0);
      await wrapper.vm.$nextTick();

      const enBtn = wrapper.findAll('button').find(b => b.text() === 'English');
      await enBtn.trigger('click');

      expect(mockConfirmModal.requestConfirm).toHaveBeenCalledWith(
        expect.objectContaining({ title: expect.stringContaining('Cambios') })
      );
    });
  });

  // ── Email template editing ────────────────────────────────────────────────

  describe('email template editing', () => {
    it('renders editable fields when a template with fields is loaded', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'welcome', name: 'Bienvenida', category: 'client', description: '', editable_fields_count: 1, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: {
          editable_fields: [{ key: 'subject', label: 'Asunto', type: 'text', current_value: 'Hola!', default_value: 'Hola' }],
          is_active: true,
        },
      });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Bienvenida')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Asunto');
    });

    it('opens the email preview modal when the Vista previa button is clicked', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'welcome', name: 'Bienvenida', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true },
      });
      mockProposalStore.previewEmailTemplate.mockResolvedValueOnce({
        success: true,
        data: { html_preview: '<p>Preview</p>', subject: 'Test' },
      });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Bienvenida')).trigger('click');
      await flushPromises();

      const previewBtn = wrapper.findAll('button').find(b => b.text().includes('Vista previa'));
      expect(previewBtn).toBeTruthy();
      await previewBtn.trigger('click');
      await flushPromises();

      expect(mockProposalStore.previewEmailTemplate).toHaveBeenCalledWith('welcome');
    });

    it('sets emailShowResetConfirm when the Restaurar button is clicked', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'welcome', name: 'Bienvenida', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true },
      });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Bienvenida')).trigger('click');
      await flushPromises();

      const restaurarBtn = wrapper.findAll('button').find(b => b.text() === 'Restaurar');
      await restaurarBtn.trigger('click');

      expect(wrapper.vm.emailShowResetConfirm).toBe(true);
    });
  });

  // ── Prompt tab ────────────────────────────────────────────────────────────

  describe('prompt tab', () => {
    it('shows the copied confirmation after the Copiar button is clicked', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      const copyBtn = wrapper.findAll('button').find(b => b.text() === 'Copiar' || b.text() === '¡Copiado!');
      expect(copyBtn).toBeTruthy();
      await copyBtn.trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('¡Copiado!');
    });

    it('renders the Descargar .md button in the prompt tab', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      const dlBtn = wrapper.findAll('button').find(b => b.text().includes('Descargar .md'));
      expect(dlBtn).toBeTruthy();
      await dlBtn.trigger('click');

      expect(wrapper.exists()).toBe(true);
    });

    it('shows editing textarea after Editar is clicked for the commercial prompt', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      const editarBtns = wrapper.findAll('button').filter(b => b.text() === 'Editar');
      await editarBtns[0].trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.find('textarea[rows="30"]').exists()).toBe(true);
    });

    it('hides the editing textarea after Cancelar is clicked', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      await wrapper.findAll('button').filter(b => b.text() === 'Editar')[0].trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text() === 'Cancelar').trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.find('textarea[rows="30"]').exists()).toBe(false);
    });

    it('shows success message after Guardar cambios is clicked in the commercial prompt section', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      await wrapper.findAll('button').filter(b => b.text() === 'Editar')[0].trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text() === 'Guardar cambios').trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Prompt guardado correctamente.');
    });
  });

  // ── handleSaveAll ─────────────────────────────────────────────────────────

  describe('handleSaveAll', () => {
    it('calls saveProposalDefaults and shows success message when sections are pending', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      wrapper.vm.savedSections.add(0);
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text().includes('Guardar Todos los Cambios')).trigger('click');
      await flushPromises();

      expect(mockProposalStore.saveProposalDefaults).toHaveBeenCalled();
      expect(wrapper.text()).toContain('Valores por defecto guardados correctamente.');
    });

    it('shows error message when saveProposalDefaults fails in handleSaveAll', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });
      mockProposalStore.saveProposalDefaults.mockResolvedValueOnce({ success: false });
      const wrapper = mountPanel('sections');
      await flushPromises();

      wrapper.vm.savedSections.add(0);
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text().includes('Guardar Todos los Cambios')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Error al guardar los valores por defecto.');
    });
  });

  // ── confirmReset error branch ──────────────────────────────────────────────

  describe('confirmReset error', () => {
    it('shows error message when resetProposalDefaults fails', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });
      mockProposalStore.resetProposalDefaults.mockResolvedValueOnce({ success: false });

      const wrapper = mountPanel('sections');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text().includes('Restaurar valores originales')).trigger('click');
      await wrapper.findAll('button').find(b => b.text().includes('Sí, restaurar')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Error al restaurar los valores por defecto.');
    });
  });

  // ── handleSectionPreview ─────────────────────────────────────────────────

  describe('handleSectionPreview', () => {
    it('sets showSectionPreview when the eye icon button is clicked on a section row', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      await wrapper.find('button[aria-label="Vista previa"]').trigger('click');

      expect(wrapper.vm.showSectionPreview).toBe(true);
    });
  });

  // ── handleSaveEmailTemplate ───────────────────────────────────────────────

  describe('handleSaveEmailTemplate', () => {
    it('shows success message after saving email template changes', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'tpl-save', name: 'Save Template', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true },
      });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Save Template')).trigger('click');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text() === 'Guardar Cambios').trigger('click');
      await flushPromises();

      expect(mockProposalStore.saveEmailTemplate).toHaveBeenCalledWith('tpl-save', expect.any(Object));
      expect(wrapper.text()).toContain('Plantilla guardada correctamente.');
    });

    it('shows error message when saving email template fails', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'tpl-fail', name: 'Fail Template', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true },
      });
      mockProposalStore.saveEmailTemplate.mockResolvedValueOnce({ success: false });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Fail Template')).trigger('click');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text() === 'Guardar Cambios').trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Error al guardar la plantilla.');
    });
  });

  // ── confirmResetEmailTemplate ─────────────────────────────────────────────

  describe('confirmResetEmailTemplate', () => {
    it('calls resetEmailTemplate and shows success message after confirming reset', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'tpl-rst', name: 'Reset Template', category: 'client', description: '', editable_fields_count: 0, is_customized: true, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true },
      });
      mockProposalStore.resetEmailTemplate.mockResolvedValueOnce({ success: true });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Reset Template')).trigger('click');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text() === 'Restaurar').trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text() === 'Sí, restaurar').trigger('click');
      await flushPromises();

      expect(mockProposalStore.resetEmailTemplate).toHaveBeenCalledWith('tpl-rst');
      expect(wrapper.text()).toContain('Plantilla restaurada a los valores originales.');
    });

    it('shows error message when resetEmailTemplate fails', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'tpl-rst-err', name: 'Reset Err Template', category: 'client', description: '', editable_fields_count: 0, is_customized: true, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true },
      });
      mockProposalStore.resetEmailTemplate.mockResolvedValueOnce({ success: false });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Reset Err Template')).trigger('click');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text() === 'Restaurar').trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text() === 'Sí, restaurar').trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Error al restaurar la plantilla.');
    });
  });

  // ── emailInsertVariable ───────────────────────────────────────────────────

  describe('emailInsertVariable', () => {
    it('shows variable feedback toast when a variable chip is clicked with no focused field', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'tpl-var', name: 'Var Template', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true, available_variables: ['client_name'] },
      });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Var Template')).trigger('click');
      await flushPromises();

      const varChip = wrapper.findAll('code').find(c => c.text().includes('client_name'));
      await varChip.trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('{client_name}');
    });
  });

  // ── cancelEditJson ────────────────────────────────────────────────────────

  describe('cancelEditJson', () => {
    it('exits editing mode when Cancelar is clicked in the JSON tab', async () => {
      const wrapper = mountPanel('json');
      await flushPromises();

      const editarButtons = wrapper.findAll('button').filter(b => b.text() === 'Editar');
      await editarButtons.at(-1).trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text() === 'Cancelar').trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.findAll('button').some(b => b.text() === 'Editar')).toBe(true);
    });
  });

  // ── saveEditJson missing sections ─────────────────────────────────────────

  describe('saveEditJson missing sections', () => {
    it('shows error message when the saved JSON has no sections array', async () => {
      const wrapper = mountPanel('json');
      await flushPromises();

      const editarButtons = wrapper.findAll('button').filter(b => b.text() === 'Editar');
      await editarButtons.at(-1).trigger('click');
      await wrapper.vm.$nextTick();

      const jsonTextarea = wrapper.findAll('textarea.font-mono').at(-1);
      await jsonTextarea.setValue(JSON.stringify({ language: 'es', general: {} }));
      await wrapper.findAll('button').find(b => b.text().includes('Guardar cambios')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('sections');
    });
  });

  // ── copyDefaultsJson ──────────────────────────────────────────────────────

  describe('copyDefaultsJson', () => {
    it('calls navigator.clipboard.writeText when the JSON Copiar button is clicked', async () => {
      const writeText = jest.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });

      const wrapper = mountPanel('json');
      await flushPromises();

      const copiarButtons = wrapper.findAll('button').filter(b => b.text() === 'Copiar');
      await copiarButtons.at(-1).trigger('click');
      await flushPromises();

      expect(writeText).toHaveBeenCalled();
    });
  });

  // ── downloadDefaultsJson ──────────────────────────────────────────────────

  describe('downloadDefaultsJson', () => {
    it('calls URL.createObjectURL when Descargar .json is clicked', async () => {
      const wrapper = mountPanel('json');
      await flushPromises();

      const dlBtn = wrapper.findAll('button').find(b => b.text().includes('Descargar .json'));
      await dlBtn.trigger('click');

      expect(URL.createObjectURL).toHaveBeenCalled();
    });
  });

  // ── handleApplyDefaultsTechnicalJson extra branches ───────────────────────

  describe('handleApplyDefaultsTechnicalJson extra', () => {
    it('shows error when no technical_document section exists in the loaded template', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });
      const wrapper = mountPanel('technical');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text() === 'JSON').trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text().includes('Aplicar a plantilla')).trigger('click');

      expect(wrapper.text()).toContain('No hay sección technical_document');
    });

    it('shows success message when valid JSON is applied to an existing technical section', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [{ section_type: 'technical_document', title: 'Det. técnico', order: 0, content_json: { epics: [] } }],
        },
      });
      const wrapper = mountPanel('technical');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text() === 'JSON').trigger('click');
      await wrapper.vm.$nextTick();

      const technicalTextarea = wrapper.find('textarea[rows="24"]');
      await technicalTextarea.setValue(JSON.stringify({ epics: [{ epicKey: 'ep-1', title: 'Landing', requirements: [] }] }));
      await wrapper.findAll('button').find(b => b.text().includes('Aplicar a plantilla')).trigger('click');

      expect(wrapper.text()).toContain('Plantilla técnica actualizada en memoria.');
    });
  });

  // ── formatDate ────────────────────────────────────────────────────────────

  describe('formatDate', () => {
    it('displays the last updated label when configUpdatedAt is set by loadDefaults', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, updated_at: '2024-01-15T10:30:00Z', sections_json: [] },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      expect(wrapper.text()).toContain('Última actualización:');
    });
  });

  // ── refreshData ───────────────────────────────────────────────────────────

  describe('refreshData', () => {
    it('registers a handler that re-fetches defaults when invoked', async () => {
      capturedRefreshHandler = null;
      mountPanel();
      await flushPromises();

      mockProposalStore.fetchProposalDefaults.mockClear();
      expect(typeof capturedRefreshHandler).toBe('function');

      await capturedRefreshHandler();
      await flushPromises();

      expect(mockProposalStore.fetchProposalDefaults).toHaveBeenCalled();
    });
  });

  // ── loadDefaults failure branch ───────────────────────────────────────────

  describe('loadDefaults failure', () => {
    it('does not update generalForm when fetchProposalDefaults returns success: false', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({ success: false });
      const wrapper = mountPanel();
      await flushPromises();

      // The default slug pattern input should still render (form not updated, keeps initial values)
      expect(wrapper.find('[data-testid="defaults-slug-pattern"]').exists()).toBe(true);
    });
  });

  // ── switchLanguage same-language guard ────────────────────────────────────

  describe('switchLanguage same-language guard', () => {
    it('does not call fetchProposalDefaults when switching to the already-selected language', async () => {
      const wrapper = mountPanel('general');
      await flushPromises();

      mockProposalStore.fetchProposalDefaults.mockClear();

      // Default language is 'es'; clicking Español again should be a no-op
      const esBtn = wrapper.findAll('button').find(b => b.text() === 'Español');
      await esBtn.trigger('click');
      await flushPromises();

      expect(mockProposalStore.fetchProposalDefaults).not.toHaveBeenCalled();
    });
  });

  // ── filteredEmailTemplates category filter ────────────────────────────────

  describe('filteredEmailTemplates', () => {
    it('shows only client templates when the Cliente category button is clicked', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [
          { template_key: 'cli-1', name: 'Correo cliente', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true },
          { template_key: 'int-1', name: 'Correo interno', category: 'internal', description: '', editable_fields_count: 0, is_customized: false, is_active: true },
        ],
      });

      const wrapper = mountPanel('emails');
      await flushPromises();

      expect(wrapper.text()).toContain('Correo cliente');
      expect(wrapper.text()).toContain('Correo interno');

      const clienteBtn = wrapper.findAll('button').find(b => b.text().startsWith('Cliente'));
      await clienteBtn.trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('Correo cliente');
      expect(wrapper.text()).not.toContain('Correo interno');
    });
  });

  // ── confirmReset success feedback ─────────────────────────────────────────

  describe('confirmReset success feedback', () => {
    it('shows success feedback and reloads defaults after a successful reset', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValue({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });

      const wrapper = mountPanel('sections');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text().includes('Restaurar valores originales')).trigger('click');
      await wrapper.findAll('button').find(b => b.text().includes('Sí, restaurar')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Valores restaurados a los originales del sistema.');
    });
  });

  // ── slugPatternPreview branches ───────────────────────────────────────────

  describe('slugPatternPreview', () => {
    it('falls back to maria-lopez when the slug pattern input is cleared', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('[data-testid="defaults-slug-pattern"]').setValue('');
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('maria-lopez');
    });

    it('shows e-commerce in slug preview when pattern contains {project_type}', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('[data-testid="defaults-slug-pattern"]').setValue('{project_type}');
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('e-commerce');
    });
  });

  // ── handleSaveGeneral language switch ─────────────────────────────────────

  describe('handleSaveGeneral language switch', () => {
    it('calls loadDefaults with the new language when the language select is changed before saving', async () => {
      const wrapper = mountPanel();
      await flushPromises();
      mockProposalStore.fetchProposalDefaults.mockClear();

      await wrapper.findAll('select').at(0).setValue('en');
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockProposalStore.fetchProposalDefaults).toHaveBeenCalledWith('en');
    });
  });

  // ── handleSaveSection ─────────────────────────────────────────────────────

  describe('handleSaveSection', () => {
    it('shows local feedback when called with a string sectionId in default-N format', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      wrapper.vm.handleSaveSection({ sectionId: 'default-0', payload: { title: 'Updated', content_json: {} } });
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('Sección actualizada localmente');
    });

    it('shows local feedback when called with a numeric sectionId', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, sections_json: [{ section_type: 'intro', title: 'Intro', order: 0, content_json: {} }] },
      });
      const wrapper = mountPanel('sections');
      await flushPromises();

      wrapper.vm.handleSaveSection({ sectionId: 0, payload: { title: 'Numeric Update', content_json: {} } });
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('Sección actualizada localmente');
    });
  });

  // ── defaultsTechnicalEpicCount non-array epics ────────────────────────────

  describe('defaultsTechnicalEpicCount', () => {
    it('shows 0 módulo(s) when technical_document section has non-array epics', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [{ section_type: 'technical_document', title: 'Det. técnico', order: 0, content_json: { epics: null } }],
        },
      });
      const wrapper = mountPanel('json');
      await flushPromises();

      expect(wrapper.text()).toContain('0 módulo(s)');
    });
  });

  // ── handleApplyDefaultsTechnicalJson array branch ─────────────────────────

  describe('handleApplyDefaultsTechnicalJson array branch', () => {
    it('shows error when the technical JSON textarea contains a JSON array instead of object', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: {
          ...defaultDataResponse.data,
          sections_json: [{ section_type: 'technical_document', title: 'Det. técnico', order: 0, content_json: { epics: [] } }],
        },
      });
      const wrapper = mountPanel('technical');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text() === 'JSON').trigger('click');
      await wrapper.vm.$nextTick();

      const technicalTextarea = wrapper.find('textarea[rows="24"]');
      await technicalTextarea.setValue('[1, 2, 3]');
      await wrapper.findAll('button').find(b => b.text().includes('Aplicar a plantilla')).trigger('click');

      expect(wrapper.text()).toContain('debe ser un objeto JSON');
    });
  });

  // ── Technical prompt tab ──────────────────────────────────────────────────

  describe('technical prompt tab', () => {
    it('shows editing textarea after Editar is clicked for the technical prompt', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      const editarBtns = wrapper.findAll('button').filter(b => b.text() === 'Editar');
      await editarBtns[1].trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.find('textarea[rows="28"]').exists()).toBe(true);
    });

    it('hides the editing textarea after Cancelar is clicked for the technical prompt', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      await wrapper.findAll('button').filter(b => b.text() === 'Editar')[1].trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text() === 'Cancelar').trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.find('textarea[rows="28"]').exists()).toBe(false);
    });

    it('shows success message after Guardar cambios is clicked in the technical prompt section', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      await wrapper.findAll('button').filter(b => b.text() === 'Editar')[1].trigger('click');
      await wrapper.vm.$nextTick();

      await wrapper.findAll('button').find(b => b.text() === 'Guardar cambios').trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Prompt técnico guardado correctamente.');
    });

    it('shows ¡Copiado! after the Copiar button is clicked for the technical prompt', async () => {
      const wrapper = mountPanel('prompt');
      await flushPromises();

      const copiarBtns = wrapper.findAll('button').filter(b => b.text() === 'Copiar' || b.text() === '¡Copiado!');
      await copiarBtns[1].trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('¡Copiado!');
    });
  });

  // ── handleEmailPreview error branch ──────────────────────────────────────

  describe('handleEmailPreview error', () => {
    it('shows error feedback when previewEmailTemplate returns success false', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'tpl-prev-err', name: 'Preview Err Template', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValueOnce({
        success: true,
        data: { editable_fields: [], is_active: true },
      });
      mockProposalStore.previewEmailTemplate.mockResolvedValueOnce({ success: false });

      const wrapper = mountPanel('emails');
      await flushPromises();
      await wrapper.findAll('button').find(b => b.text().includes('Preview Err Template')).trigger('click');
      await flushPromises();

      await wrapper.findAll('button').find(b => b.text().includes('Vista previa')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Error al generar la vista previa.');
    });
  });

  // ── selectEmailTemplate same-key guard ───────────────────────────────────

  describe('selectEmailTemplate same-key guard', () => {
    it('does not call fetchEmailTemplateDetail a second time when the same template is clicked again', async () => {
      mockProposalStore.fetchEmailTemplates.mockResolvedValueOnce({
        success: true,
        data: [{ template_key: 'tpl-same', name: 'Same Template', category: 'client', description: '', editable_fields_count: 0, is_customized: false, is_active: true }],
      });
      mockProposalStore.fetchEmailTemplateDetail.mockResolvedValue({
        success: true,
        data: { editable_fields: [], is_active: true },
      });

      const wrapper = mountPanel('emails');
      await flushPromises();
      const tplBtn = wrapper.findAll('button').find(b => b.text().includes('Same Template'));
      await tplBtn.trigger('click');
      await flushPromises();
      mockProposalStore.fetchEmailTemplateDetail.mockClear();

      await tplBtn.trigger('click');
      await flushPromises();

      expect(mockProposalStore.fetchEmailTemplateDetail).not.toHaveBeenCalled();
    });
  });

  // ── loadDefaults non-string currency fallback ─────────────────────────────

  describe('loadDefaults non-string currency', () => {
    it('falls back to COP when default_currency is not a string', async () => {
      mockProposalStore.fetchProposalDefaults.mockResolvedValueOnce({
        success: true,
        data: { ...defaultDataResponse.data, default_currency: 42 },
      });
      const wrapper = mountPanel('general');
      await flushPromises();

      const currencySelect = wrapper.findAll('select').at(1);
      expect(currencySelect.element.value).toBe('COP');
    });
  });

  // ── saveEditJson null section branch ─────────────────────────────────────

  describe('saveEditJson null section', () => {
    it('shows error message when a section in the JSON array is null', async () => {
      const wrapper = mountPanel('json');
      await flushPromises();

      const editarButtons = wrapper.findAll('button').filter(b => b.text() === 'Editar');
      await editarButtons.at(-1).trigger('click');
      await wrapper.vm.$nextTick();

      const jsonTextarea = wrapper.findAll('textarea.font-mono').at(-1);
      await jsonTextarea.setValue(JSON.stringify({ language: 'es', sections: [null] }));
      await wrapper.findAll('button').find(b => b.text().includes('Guardar cambios')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('debe ser un objeto');
    });
  });
});
