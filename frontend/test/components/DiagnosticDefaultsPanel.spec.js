/**
 * Tests for DiagnosticDefaultsPanel.vue.
 *
 * Covers: rendering, slug pattern preview, payment validation,
 * payment sync, loadDefaults on mount, language change reload,
 * save success/error toasts, disabled save button, confirmReset.
 */

// Nuxt auto-import globals — must be set before the component is required
global.useLocalePath = () => (path) => path;
global.useRoute = () => ({ query: {}, path: '/', params: {}, name: '' });

import { mount } from '@vue/test-utils';
import { usePanelNotify } from '../../composables/usePanelNotify';

const mockDiagnosticsStore = {
  fetchDiagnosticDefaults: jest.fn(),
  saveDiagnosticDefaults: jest.fn(),
  resetDiagnosticDefaults: jest.fn(),
};

jest.mock('../../stores/diagnostics', () => ({
  useDiagnosticsStore: () => mockDiagnosticsStore,
}));

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

jest.mock('../../composables/usePanelRefresh', () => ({
  usePanelRefresh: jest.fn(),
}));

import DiagnosticDefaultsPanel from '../../components/panel/defaults/DiagnosticDefaultsPanel.vue';

const notify = usePanelNotify();

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

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

function mountPanel() {
  return mount(DiagnosticDefaultsPanel, {
    global: {
      stubs: {
        ResponsiveTabs: { template: '<div />' },
        ConfirmModal: { template: '<div />' },
        UiTooltip: { template: '<div><slot /></div>' },
        NuxtLink: { template: '<a><slot /></a>' },
        BaseInput: BaseInputStub,
        BaseChoiceSelect: BaseSelectStub,
        BaseTextarea: BaseTextareaStub,
        BaseButton: BaseButtonStub,
        BaseTabs: BaseTabsStub,
        BaseTooltip: { template: '<div><slot /></div>' },
        BaseFormField: { template: '<div><slot /></div>' },
        BaseBadge: { template: '<span><slot /></span>' },
        BaseToggle: { template: '<input type="checkbox" />' },
      },
    },
  });
}

describe('DiagnosticDefaultsPanel', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    capturedConfirmOpts = null;
    mockDiagnosticsStore.fetchDiagnosticDefaults.mockReset().mockResolvedValue({ success: true, data: {} });
    mockDiagnosticsStore.saveDiagnosticDefaults.mockReset().mockResolvedValue({ success: true, data: {} });
    mockDiagnosticsStore.resetDiagnosticDefaults.mockReset().mockResolvedValue({ success: true });
    mockConfirmModal.requestConfirm.mockClear();
    mockConfirmModal.handleConfirmed.mockClear();
    mockConfirmModal.handleCancelled.mockClear();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    notify.clearAll();
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe('rendering', () => {
    it('renders the language selector', () => {
      const wrapper = mountPanel();

      expect(wrapper.find('[data-testid="defaults-language"]').exists()).toBe(true);
    });

    it('renders the save button', () => {
      const wrapper = mountPanel();

      expect(wrapper.find('[data-testid="defaults-save-btn"]').exists()).toBe(true);
    });

    it('renders the reset button', () => {
      const wrapper = mountPanel();

      expect(wrapper.find('[data-testid="defaults-reset-btn"]').exists()).toBe(true);
    });

    it('renders the slug pattern input', () => {
      const wrapper = mountPanel();

      expect(wrapper.find('[data-testid="diagnostic-defaults-slug-pattern"]').exists()).toBe(true);
    });

    it('renders the JSON config view section', () => {
      const wrapper = mountPanel();

      expect(wrapper.find('[data-testid="defaults-json-view"]').exists()).toBe(true);
    });
  });

  // ── Slug pattern preview ──────────────────────────────────────────────────

  describe('slugPatternPreview', () => {
    it('shows preview text for the default slug pattern', () => {
      const wrapper = mountPanel();

      expect(wrapper.text()).toContain('/diagnostic/');
    });

    it('renders client_name placeholder as slugified sample', async () => {
      const wrapper = mountPanel();

      // Default pattern is '{client_name}' → slug of 'María López' = 'maria-lopez'
      expect(wrapper.text()).toContain('maria-lopez');
    });

    it('shows plain text as slugified preview when pattern has no placeholders', async () => {
      const wrapper = mountPanel();

      await wrapper.find('[data-testid="diagnostic-defaults-slug-pattern"]').setValue('Mi Diagnóstico');
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('mi-diagnostico');
    });
  });

  // ── Payment validation ─────────────────────────────────────────────────────

  describe('payment validation', () => {
    it('does not show payment warning when initial and final sum to 100', () => {
      const wrapper = mountPanel();

      expect(wrapper.find('[data-testid="defaults-payment-warning"]').exists()).toBe(false);
    });

    it('shows payment warning when store returns values that do not sum to 100', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({
        success: true,
        data: { payment_initial_pct: 70, payment_final_pct: 40 },
      });
      const wrapper = mountPanel();
      await flushPromises();
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="defaults-payment-warning"]').exists()).toBe(true);
    });

    it('disables save button when loaded payment values do not sum to 100', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({
        success: true,
        data: { payment_initial_pct: 70, payment_final_pct: 40 },
      });
      const wrapper = mountPanel();
      await flushPromises();
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="defaults-save-btn"]').element.disabled).toBe(true);
    });

    it('enables save button when payment sum is 100', () => {
      const wrapper = mountPanel();

      expect(wrapper.find('[data-testid="defaults-save-btn"]').element.disabled).toBe(false);
    });
  });

  // ── Payment sync ──────────────────────────────────────────────────────────

  describe('payment sync', () => {
    it('shows 70 in the final input when store loads initial=30 and final=70', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({
        success: true,
        data: { payment_initial_pct: 30, payment_final_pct: 70 },
      });
      const wrapper = mountPanel();
      await flushPromises();
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="defaults-payment-final"]').element.value).toBe('70');
    });

    it('shows 80 in the initial input when store loads initial=80 and final=20', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({
        success: true,
        data: { payment_initial_pct: 80, payment_final_pct: 20 },
      });
      const wrapper = mountPanel();
      await flushPromises();
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="defaults-payment-initial"]').element.value).toBe('80');
    });

    it('shows no payment warning when loaded values sum to 100', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({
        success: true,
        data: { payment_initial_pct: 30, payment_final_pct: 70 },
      });
      const wrapper = mountPanel();
      await flushPromises();
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="defaults-payment-warning"]').exists()).toBe(false);
    });
  });

  // ── loadDefaults on mount ─────────────────────────────────────────────────

  describe('loadDefaults', () => {
    it('calls fetchDiagnosticDefaults with es on mount', async () => {
      mountPanel();
      await flushPromises();

      expect(mockDiagnosticsStore.fetchDiagnosticDefaults).toHaveBeenCalledWith('es');
    });

    it('applies returned config data to the form', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({
        success: true,
        data: {
          language: 'es',
          default_currency: 'USD',
          default_investment_amount: 5000,
          default_duration_label: '6 semanas',
          payment_initial_pct: 50,
          payment_final_pct: 50,
          reminder_days: 10,
          urgency_reminder_days: 20,
          expiration_days: 30,
          default_slug_pattern: '{client_name}',
        },
      });
      const wrapper = mountPanel();
      await flushPromises();
      await wrapper.vm.$nextTick();

      expect(wrapper.find('[data-testid="defaults-currency"]').element.value).toBe('USD');
    });

    it('shows error toast when fetchDiagnosticDefaults fails', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({ success: false });
      mountPanel();
      await flushPromises();
      await wrapper_nextTick();

      expect(notify.notifications.value).toHaveLength(1);
      expect(notify.notifications.value[0].type).toBe('error');
    });
  });

  // ── Language change ───────────────────────────────────────────────────────

  describe('language change', () => {
    it('reloads defaults when the language selector changes', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockClear();
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('[data-testid="defaults-language"]').setValue('en');
      await flushPromises();

      expect(mockDiagnosticsStore.fetchDiagnosticDefaults).toHaveBeenCalledWith('en');
    });
  });

  // ── Save ──────────────────────────────────────────────────────────────────

  describe('handleSaveGeneral', () => {
    it('calls saveDiagnosticDefaults when form is submitted', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockDiagnosticsStore.saveDiagnosticDefaults).toHaveBeenCalled();
    });

    it('shows success toast when save succeeds', async () => {
      mockDiagnosticsStore.saveDiagnosticDefaults.mockResolvedValue({ success: true, data: {} });
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(notify.notifications.value).toHaveLength(1);
      expect(notify.notifications.value[0].type).toBe('success');
    });

    it('shows error toast when save fails', async () => {
      mockDiagnosticsStore.saveDiagnosticDefaults.mockResolvedValue({
        success: false,
        errors: { detail: 'Error al guardar.' },
      });
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(notify.notifications.value).toHaveLength(1);
      expect(notify.notifications.value[0].type).toBe('error');
    });

    it('does not call saveDiagnosticDefaults when loaded payment values do not sum to 100', async () => {
      mockDiagnosticsStore.fetchDiagnosticDefaults.mockResolvedValue({
        success: true,
        data: { payment_initial_pct: 70, payment_final_pct: 40 },
      });
      const wrapper = mountPanel();
      await flushPromises();
      mockDiagnosticsStore.saveDiagnosticDefaults.mockClear();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockDiagnosticsStore.saveDiagnosticDefaults).not.toHaveBeenCalled();
    });
  });

  // ── Confirm reset ──────────────────────────────────────────────────────────

  describe('confirmReset', () => {
    it('calls requestConfirm when the reset button is clicked', async () => {
      const wrapper = mountPanel();

      await wrapper.find('[data-testid="defaults-reset-btn"]').trigger('click');

      expect(mockConfirmModal.requestConfirm).toHaveBeenCalled();
    });

    it('calls resetDiagnosticDefaults when the confirm callback is invoked', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('[data-testid="defaults-reset-btn"]').trigger('click');
      await capturedConfirmOpts.onConfirm();
      await flushPromises();

      expect(mockDiagnosticsStore.resetDiagnosticDefaults).toHaveBeenCalled();
    });

    it('shows success toast after a successful reset', async () => {
      const wrapper = mountPanel();
      await flushPromises();

      await wrapper.find('[data-testid="defaults-reset-btn"]').trigger('click');
      await capturedConfirmOpts.onConfirm();
      await flushPromises();

      expect(notify.notifications.value).toHaveLength(1);
      expect(notify.notifications.value[0].type).toBe('success');
    });
  });
});

// Helper to avoid using wrapper.vm directly in the few cases
// where only Vue's tick is needed without a wrapper reference.
async function wrapper_nextTick() {
  const { nextTick } = await import('vue');
  await nextTick();
}
