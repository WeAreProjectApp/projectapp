import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import IncomeFormModal from '../../../components/accounting/IncomeFormModal.vue';
import BaseAlert from '../../../components/base/BaseAlert.vue';
import { get_request } from '../../../stores/services/request_http';
import { useProposalClientsStore } from '../../../stores/proposal_clients';
import BaseFormField from '../../../components/base/BaseFormField.vue';
import BaseInput from '../../../components/base/BaseInput.vue';

jest.mock('../../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: ['modelValue', 'initialLabel', 'testId', 'placeholder'],
  emits: ['update:modelValue', 'select', 'create-new'],
  template: '<div data-testid="client-autocomplete-stub" />',
};

const PartnerSplitInputStub = {
  name: 'PartnerSplitInput',
  props: ['total', 'gustavoAmount', 'carlosAmount'],
  emits: ['update:total', 'update:gustavoAmount', 'update:carlosAmount'],
  template: `
    <div data-testid="partner-split-stub">
      <input data-testid="split-total" :value="total" @input="$emit('update:total', $event.target.value)" />
      <input data-testid="split-gustavo" :value="gustavoAmount" @input="$emit('update:gustavoAmount', $event.target.value)" />
      <input data-testid="split-carlos" :value="carlosAmount" @input="$emit('update:carlosAmount', $event.target.value)" />
    </div>
  `,
};

function mountModal(props = {}) {
  const pinia = createPinia();
  setActivePinia(pinia);
  return mount(IncomeFormModal, {
    props: {
      open: true,
      record: null,
      saving: false,
      ...props,
    },
    global: {
      plugins: [pinia],
      // The real alert, not a stub: the copy it renders is what the operator
      // reads to tell a chained date from a guess.
      components: { BaseAlert, BaseFormField, BaseInput },
      stubs: {
        ClientAutocomplete: ClientAutocompleteStub,
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseCurrencyInput: {
          props: ['modelValue', 'decimals', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<input type="text" inputmode="numeric" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'rows', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSegmented: {
          props: ['modelValue', 'options', 'size', 'fullWidth'],
          emits: ['update:modelValue'],
          template:
            '<div><button v-for="o in options" :key="o.value" type="button" :aria-selected="modelValue === o.value" @click="$emit(\'update:modelValue\', o.value)">{{ o.label }}</button></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'loading', 'disabled'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseToggle: {
          props: ['modelValue', 'size', 'disabled', 'ariaLabel'],
          emits: ['update:modelValue'],
          template:
            '<button type="button" role="switch" :aria-checked="modelValue" @click="$emit(\'update:modelValue\', !modelValue)" />',
        },
        BaseSelect: {
          props: ['modelValue', 'options', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-if="placeholder" value="" disabled>{{ placeholder }}</option><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
        },
        PartnerSplitInput: PartnerSplitInputStub,
      },
    },
  });
}

function segmentedButton(wrapper, label) {
  return wrapper.findAll('button').find((b) => b.text() === label);
}

/**
 * Answer the antecedent lookup the hosting block makes on open. Every other
 * GET keeps returning undefined, which is what the rest of this file expects.
 */
function mockPeriodSuggestion({ suggestedStart, previousEnd = null }) {
  get_request.mockImplementation((url) => (
    url.startsWith('accounting/incomes/period-suggestion/')
      ? Promise.resolve({
        data: { suggested_start: suggestedStart, previous_period_end: previousEnd },
      })
      : undefined
  ));
}

/** The hosting block, opened on a create with a known antecedent. */
async function mountHostingCreate(suggestion = { suggestedStart: '2026-09-01' }) {
  mockPeriodSuggestion(suggestion);
  const wrapper = mountModal();
  await segmentedButton(wrapper, 'Hosting').trigger('click');
  await flushPromises();
  return wrapper;
}

afterEach(() => {
  get_request.mockReset();
  jest.restoreAllMocks();
});

describe('IncomeFormModal', () => {
  function expectDescribedError(wrapper, testId, message) {
    const control = wrapper.get(`[data-testid="${testId}"]`);
    const errorId = control.attributes('aria-describedby');
    const error = wrapper.findAll('[role="alert"]')
      .find((node) => node.attributes('id') === errorId);
    expect(control.attributes('aria-invalid')).toBe('true');
    expect(error.exists()).toBe(true);
    expect(error.text()).toBe(message);
  }

  // Falla si el alta rápida manda un cliente sin nombre al store o esconde el motivo junto al campo.
  it('rejects an empty inline income client name', async () => {
    const wrapper = mountModal();
    const createClient = jest.spyOn(useProposalClientsStore(), 'createClient');
    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', '');
    await flushPromises();

    await wrapper.get('[data-testid="income-form-inline-client-save"]').trigger('click');

    expect(createClient).toHaveBeenCalledTimes(0);
    expectDescribedError(wrapper, 'income-form-inline-client-name', 'Escribe el nombre del cliente.');
  });

  // Falla si un error de correo del servidor deja de señalar el dato que debe corregirse.
  it('places inline income email rejection on its control', async () => {
    const wrapper = mountModal();
    jest.spyOn(useProposalClientsStore(), 'createClient').mockResolvedValue({
      success: false,
      errors: { email: ['Ese correo ya existe.'] },
    });
    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', 'Nueva cliente');
    await flushPromises();

    await wrapper.get('[data-testid="income-form-inline-client-save"]').trigger('click');
    await flushPromises();

    const emailControl = wrapper.get('[data-testid="income-form-inline-client-email"]');
    const emailError = wrapper.get(`#${emailControl.attributes('aria-describedby')}`);
    expect(emailControl.attributes('aria-invalid')).toBe('true');
    expect(emailError.attributes('role')).toBe('alert');
    expect(emailError.text()).toBe('Ese correo ya existe.');
  });
  it('renders an empty form in create mode', () => {
    const wrapper = mountModal();

    expect(wrapper.text()).toContain('Nuevo Ingreso');
    expect(wrapper.find('input[type="text"]').element.value).toBe('');
    // The period is the exception: it prefills with today's exact date.
    expect(wrapper.find('[data-testid="income-form-period"]').attributes('type'))
      .toBe('date');
    expect(wrapper.find('textarea').element.value).toBe('');
    expect(wrapper.find('[data-testid="split-total"]').element.value).toBe('');
    expect(wrapper.find('[data-testid="income-form-submit"]').exists()).toBe(true);
  });

  it('submits forecast fields as independent decisions', async () => {
    const wrapper = mountModal();
    await segmentedButton(wrapper, 'Desarrollo').trigger('click');
    await wrapper.get('[data-testid="income-form-confidence"]').setValue('high');

    expect(wrapper.get('[data-testid="income-form-candidate"]').attributes('aria-checked'))
      .toBe('false');

    await wrapper.get('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      is_receivable_candidate: false,
      collection_confidence: 'high',
    });
  });

  it('hydrates the saved forecast while editing', () => {
    const wrapper = mountModal({
      record: {
        concept: 'Hosting Acme',
        kind: 'expected',
        ledger: 'company',
        origin: 'development',
        payment_status: 'pending',
        is_receivable_candidate: true,
        collection_confidence: 'medium',
      },
    });

    expect(wrapper.get('[data-testid="income-form-confidence"]').element.value).toBe('medium');
    expect(wrapper.get('[data-testid="income-form-candidate"]').attributes('aria-checked'))
      .toBe('true');
  });

  it('keeps a paid forecast classification visible without editable controls', () => {
    const wrapper = mountModal({
      record: {
        concept: 'Hosting Acme',
        kind: 'expected',
        ledger: 'company',
        origin: 'development',
        payment_status: 'paid',
        is_receivable_candidate: false,
        collection_confidence: 'high',
      },
    });

    expect(wrapper.get('[data-testid="income-form-receivable-readonly"]').text())
      .toContain('Cobro muy probable');
    expect(wrapper.find('[data-testid="income-form-confidence"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="income-form-candidate"]').exists()).toBe(false);
  });

  it('resets forecast state while duplicating', () => {
    const wrapper = mountModal({
      seed: {
        concept: 'Hosting Acme',
        kind: 'expected',
        ledger: 'company',
        origin: 'development',
        is_receivable_candidate: true,
        collection_confidence: 'low',
      },
    });

    expect(wrapper.get('[data-testid="income-form-confidence"]').element.value).toBe('');
    expect(wrapper.get('[data-testid="income-form-candidate"]').attributes('aria-checked'))
      .toBe('false');
  });

  it('defaults to the exact date prefilled with today', () => {
    // 20:00 local: toISOString() would already be tomorrow in Bogotá
    // (UTC-5) — this pins the local-date formatting.
    jest.useFakeTimers().setSystemTime(new Date('2026-07-27T20:00:00'));
    try {
      const wrapper = mountModal();

      const input = wrapper.find('[data-testid="income-form-period"]');
      expect(input.attributes('type')).toBe('date');
      expect(input.element.value).toBe('2026-07-27');
    } finally {
      jest.useRealTimers();
    }
  });

  it('downgrades to month-only via the toggle keeping the typed value', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="income-form-period"]').setValue('2026-11-17');
    await wrapper.find('[data-testid="income-form-exact-date"]').trigger('click');

    const input = wrapper.find('[data-testid="income-form-period"]');
    expect(input.attributes('type')).toBe('month');
    expect(input.element.value).toBe('2026-11');
  });

  const EDIT_RECORD = {
    concept: 'Página web Acme',
    kind: 'liquid',
    period: '2026-05',
    period_date: '2026-05-01',
    destination: 'pocket',
    total_amount: '1000000',
    gustavo_amount: '600000',
    carlos_amount: '400000',
    notes: 'Pago parcial',
  };

  it('prefills the form from record in edit mode', () => {
    const wrapper = mountModal({ record: { ...EDIT_RECORD } });

    expect(wrapper.text()).toContain('Editar Ingreso');
    expect(wrapper.find('input[type="text"]').element.value).toBe('Página web Acme');
    // Edits always open as a full date; day 01 is the month-only sentinel.
    const period = wrapper.find('[data-testid="income-form-period"]');
    expect(period.attributes('type')).toBe('date');
    expect(period.element.value).toBe('2026-05-01');
    expect(wrapper.find('textarea').element.value).toBe('Pago parcial');
  });

  it('prefills the exact day from period_date in edit mode', () => {
    // `period` would truncate to the month and silently reset the day.
    const wrapper = mountModal({
      record: { ...EDIT_RECORD, period_date: '2026-05-17' },
    });

    const period = wrapper.find('[data-testid="income-form-period"]');
    expect(period.attributes('type')).toBe('date');
    expect(period.element.value).toBe('2026-05-17');
  });

  it('prefills the split amounts and pocket destination in edit mode', () => {
    const wrapper = mountModal({ record: { ...EDIT_RECORD } });

    expect(wrapper.find('[data-testid="split-total"]').element.value).toBe('1000000');
    expect(wrapper.find('[data-testid="split-gustavo"]').element.value).toBe('600000');
    expect(wrapper.find('[data-testid="split-carlos"]').element.value).toBe('400000');
    // kind=liquid makes the destination segmented visible
    expect(wrapper.text()).toContain('Destino');
    expect(segmentedButton(wrapper, 'Bolsillo ProjectApp').attributes('aria-selected')).toBe('true');
  });

  it('emits submit with backend field names including split amounts', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Anticipo cliente');
    // The business line is required: nothing new lands unclassified.
    await segmentedButton(wrapper, 'Otro').trigger('click');
    // Month-only entry is still possible through the toggle.
    await wrapper.find('[data-testid="income-form-exact-date"]').trigger('click');
    await wrapper.find('[data-testid="income-form-period"]').setValue('2026-06');
    await segmentedButton(wrapper, 'Líquido').trigger('click');
    await segmentedButton(wrapper, 'Bolsillo ProjectApp').trigger('click');
    await wrapper.find('[data-testid="split-total"]').setValue('1500');
    await wrapper.find('[data-testid="split-gustavo"]').setValue('900');
    await wrapper.find('[data-testid="split-carlos"]').setValue('600');
    await wrapper.find('textarea').setValue('Con nota');

    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')).toHaveLength(1);
    expect(wrapper.emitted('submit')[0][0]).toEqual({
      concept: 'Anticipo cliente',
      kind: 'liquid',
      period_date: '2026-06',
      destination: 'pocket',
      ledger: 'company',
      total_amount: '1500',
      vat_rate: 19,
      gustavo_amount: '900',
      carlos_amount: '600',
      client: null,
      project: null,
      origin: 'other',
      // Nulls on purpose: an edit away from hosting clears its window.
      period_start: null,
      period_end: null,
      period_cadence: '',
      notes: 'Con nota',
    });
  });

  const DUPLICATE_SEED = {
    concept: 'Kore - Hosting anual',
    kind: 'expected',
    period_date: '2027-03-01',
    period_date_source: 'hosting_cycle',
    destination: 'partners',
    ledger: 'company',
    client: 7,
    client_name: 'Ana Cliente',
    project: 3,
    project_name: 'Kore',
    origin: 'hosting',
    total_amount: '1200000.00',
    gustavo_amount: '600000.00',
    carlos_amount: '600000.00',
    notes: 'Renovar antes del corte',
  };

  it('opens as a duplicate prefilled from the seed', () => {
    const wrapper = mountModal({ seed: { ...DUPLICATE_SEED } });

    expect(wrapper.text()).toContain('Duplicar Ingreso');
    expect(wrapper.find('input[type="text"]').element.value)
      .toBe('Kore - Hosting anual');
    // A hosting seed shows the window block: the proposed date is the start.
    expect(wrapper.find('[data-testid="income-form-period-start"]').element.value)
      .toBe('2027-03-01');
    expect(wrapper.find('[data-testid="split-total"]').element.value)
      .toBe('1200000.00');
    expect(wrapper.find('textarea').element.value)
      .toBe('Renovar antes del corte');
  });

  it('leaves the date empty when the seed has no cycle to propose', () => {
    const wrapper = mountModal({
      seed: { ...DUPLICATE_SEED, period_date: null, period_date_source: null },
    });

    const period = wrapper.find('[data-testid="income-form-period-start"]');
    expect(period.element.value).toBe('');
    // Required is what forces a date before the duplicate can be saved.
    expect(period.attributes('required')).toBeDefined();
    expect(wrapper.find('[data-testid="income-form-period-hint"]').exists())
      .toBe(false);
  });

  // Counted from an original dated 2026-07-01. The server computes them so
  // the day is clamped once, in one place.
  const CYCLE_OPTIONS = [
    { months: 1, date: '2026-08-01' },
    { months: 3, date: '2026-10-01' },
    { months: 6, date: '2027-01-01' },
    { months: 12, date: '2027-07-01' },
  ];

  function seedWithCycles(overrides = {}) {
    return {
      ...DUPLICATE_SEED,
      period_date: null,
      period_date_source: null,
      cycle_options: CYCLE_OPTIONS,
      ...overrides,
    };
  }

  it('shortcuts on a hosting duplicate pick the cadence and propose the end', async () => {
    // One mechanism, not two: the shortcut writes the selector, and the end
    // fills from start + cadence (inclusive: the next cycle starts after it).
    const wrapper = mountModal({
      seed: seedWithCycles({ period_date: '2026-07-01' }),
    });

    const shortcuts = wrapper.findAll('[data-testid^="income-form-cycle-"]');
    expect(shortcuts.map((b) => b.text()))
      .toEqual(['+1 mes', '+3 meses', '+6 meses', '+1 año']);

    await wrapper.get('[data-testid="income-form-cycle-3"]').trigger('click');

    expect(wrapper.find('[data-testid="income-form-period-cadence"]').element.value)
      .toBe('quarterly');
    expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
      .toBe('2026-09-30');
  });

  it('marks the chosen cadence and moves the mark when another is picked', async () => {
    const wrapper = mountModal({ seed: seedWithCycles() });
    const pressed = () => wrapper
      .findAll('[data-testid^="income-form-cycle-"]')
      .map((b) => b.attributes('aria-pressed'));

    expect(pressed()).toEqual(['false', 'false', 'false', 'false']);

    await wrapper.get('[data-testid="income-form-cycle-1"]').trigger('click');
    expect(pressed()).toEqual(['true', 'false', 'false', 'false']);

    await wrapper.get('[data-testid="income-form-cycle-12"]').trigger('click');
    expect(pressed()).toEqual(['false', 'false', 'false', 'true']);
  });

  it('writes the shortcut in month granularity when the day is not tracked', async () => {
    // Outside hosting the shortcuts keep their original job: writing the
    // single date, in whichever granularity the toggle is on.
    const wrapper = mountModal({ seed: seedWithCycles({ origin: 'development' }) });

    await wrapper.get('[data-testid="income-form-exact-date"]').trigger('click');
    await wrapper.get('[data-testid="income-form-cycle-3"]').trigger('click');

    const period = wrapper.find('[data-testid="income-form-period"]');
    expect(period.attributes('type')).toBe('month');
    expect(period.element.value).toBe('2026-10');
  });

  it('offers no shortcuts for a single date outside a duplicate', async () => {
    const created = mountModal();
    expect(created.find('[data-testid="income-form-cycles"]').exists()).toBe(false);

    const edited = mountModal({
      record: { ...EDIT_RECORD },
      seed: seedWithCycles(),
    });
    expect(edited.find('[data-testid="income-form-cycles"]').exists()).toBe(false);
  });

  it('says where a proposed date came from, and stops once it is changed', async () => {
    const wrapper = mountModal({ seed: { ...DUPLICATE_SEED } });

    expect(wrapper.get('[data-testid="income-form-period-hint"]').text())
      .toContain('hosting');

    await wrapper.find('[data-testid="income-form-period-start"]').setValue('2027-04-15');

    expect(wrapper.find('[data-testid="income-form-period-hint"]').exists())
      .toBe(false);
  });

  it('submits the duplicate as a plain create payload', async () => {
    const wrapper = mountModal({ seed: { ...DUPLICATE_SEED } });

    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toEqual({
      concept: 'Kore - Hosting anual',
      kind: 'expected',
      destination: 'partners',
      ledger: 'company',
      total_amount: '1200000.00',
      vat_rate: null,
      gustavo_amount: '600000.00',
      carlos_amount: '600000.00',
      client: 7,
      project: 3,
      origin: 'hosting',
      is_receivable_candidate: false,
      collection_confidence: '',
      // Hosting sends the window and lets the backend derive period_date
      // from its start — two values would be two chances to disagree.
      period_start: '2027-03-01',
      period_end: '',
      period_cadence: '',
      notes: 'Renovar antes del corte',
    });
  });

  describe('hosting period block', () => {
    it('swaps the single date for the window when the origin turns to hosting', async () => {
      const wrapper = mountModal();

      expect(wrapper.find('[data-testid="income-form-period"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="income-form-period-start"]').exists()).toBe(false);

      await segmentedButton(wrapper, 'Hosting').trigger('click');

      expect(wrapper.find('[data-testid="income-form-period"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="income-form-period-start"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="income-form-period-end"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="income-form-period-cadence"]').exists()).toBe(true);
    });

    it('keeps what was typed and seeds the start when switching origin', async () => {
      const wrapper = mountModal();

      await wrapper.find('input[type="text"]').setValue('Acme - Hosting');
      await wrapper.find('[data-testid="income-form-period"]').setValue('2026-11-17');
      await segmentedButton(wrapper, 'Hosting').trigger('click');

      // Only the date block changes shape; nothing already written is lost.
      expect(wrapper.find('input[type="text"]').element.value).toBe('Acme - Hosting');
      expect(wrapper.find('[data-testid="income-form-period-start"]').element.value)
        .toBe('2026-11-17');
    });

    it('proposes the inclusive end from start + cadence, editable after', async () => {
      const wrapper = mountModal();
      await segmentedButton(wrapper, 'Hosting').trigger('click');

      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2026-08-15');
      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('annual');

      // Inclusive: the next cycle starts the day after this end.
      const end = wrapper.find('[data-testid="income-form-period-end"]');
      expect(end.element.value).toBe('2027-08-14');

      await end.setValue('2027-08-20');
      expect(end.element.value).toBe('2027-08-20');
    });

    it('a custom cadence proposes nothing — both dates are handwritten', async () => {
      const wrapper = mountModal();
      await segmentedButton(wrapper, 'Hosting').trigger('click');

      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2026-08-15');
      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('custom');

      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value).toBe('');
    });

    it('submits the window instead of the single date for hosting', async () => {
      const wrapper = mountModal();
      await segmentedButton(wrapper, 'Hosting').trigger('click');

      await wrapper.find('input[type="text"]').setValue('Acme - Hosting');
      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2026-08-15');
      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('semiannual');
      await wrapper.find('form').trigger('submit');

      const payload = wrapper.emitted('submit')[0][0];
      expect(payload.period_start).toBe('2026-08-15');
      expect(payload.period_end).toBe('2027-02-14');
      expect(payload.period_cadence).toBe('semiannual');
      expect(payload.period_date).toBeUndefined();
    });

    it('hints when the seed proposed the window from the recorded period', async () => {
      const wrapper = mountModal({
        seed: {
          ...DUPLICATE_SEED,
          period_date: '2027-03-01',
          period_date_source: 'income_period',
          period_start: '2027-03-01',
          period_end: '2028-02-29',
          period_cadence: 'annual',
        },
      });

      expect(wrapper.get('[data-testid="income-form-period-hint"]').text())
        .toContain('periodicidad registrada');

      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2027-04-01');

      expect(wrapper.find('[data-testid="income-form-period-hint"]').exists())
        .toBe(false);
    });

    it('reads as a window: start and end share a row, cadence sits with Tipo', async () => {
      // A range split across two rows stops reading as a range, and the
      // cadence is chosen before the dates it proposes.
      const wrapper = await mountHostingCreate();
      const rows = wrapper.findAll('form > div.grid');

      const dateRow = rows.find(
        (row) => row.find('[data-testid="income-form-period-start"]').exists(),
      );
      expect(dateRow.find('[data-testid="income-form-period-end"]').exists()).toBe(true);

      const cadenceRow = rows.find(
        (row) => row.find('[data-testid="income-form-period-cadence"]').exists(),
      );
      expect(cadenceRow.text()).toContain('Tipo');
      expect(cadenceRow.find('[data-testid="income-form-period-start"]').exists())
        .toBe(false);
    });

    it('opens the window on the period after the last one recorded', async () => {
      // Nothing typed yet: the cadence is what the operator picks first, and
      // the antecedent is what says where the window goes.
      const wrapper = await mountHostingCreate({
        suggestedStart: '2026-09-01', previousEnd: '2026-08-31',
      });

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('quarterly');

      expect(wrapper.find('[data-testid="income-form-period-start"]').element.value)
        .toBe('2026-09-01');
      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2026-11-30');
      expect(wrapper.get('[data-testid="income-form-period-hint"]').text())
        .toContain('El período anterior terminó');
    });

    it('recomputes the end when the origin seeded the start programmatically', async () => {
      // The defect this delivery fixes: switching origin writes the start
      // without the operator touching the field, and picking a cadence after
      // that used to leave the end untouched.
      mockPeriodSuggestion({ suggestedStart: '2026-09-01' });
      const wrapper = mountModal();
      await wrapper.find('[data-testid="income-form-period"]').setValue('2026-11-17');
      await segmentedButton(wrapper, 'Hosting').trigger('click');
      await flushPromises();

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('semiannual');

      expect(wrapper.find('[data-testid="income-form-period-start"]').element.value)
        .toBe('2026-11-17');
      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2027-05-16');
    });

    it('follows the start with the end, keeping the chosen cadence', async () => {
      const wrapper = await mountHostingCreate();

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('quarterly');
      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2026-10-01');

      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2026-12-31');
      expect(wrapper.find('[data-testid="income-form-period-cadence"]').element.value)
        .toBe('quarterly');
    });

    it('turns the cadence to Personalizada when the end is written by hand', async () => {
      // The form must never show a Trimestral over a window that is not one.
      const wrapper = await mountHostingCreate();

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('quarterly');
      await wrapper.find('[data-testid="income-form-period-end"]').setValue('2027-01-15');

      expect(wrapper.find('[data-testid="income-form-period-cadence"]').element.value)
        .toBe('custom');
      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2027-01-15');
    });

    it('stops proposing once the cadence is Personalizada', async () => {
      const wrapper = await mountHostingCreate();

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('custom');
      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2026-10-01');
      await wrapper.find('[data-testid="income-form-period-end"]').setValue('2026-10-20');

      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2026-10-20');
      expect(wrapper.find('[data-testid="income-form-period-cadence"]').element.value)
        .toBe('custom');
    });

    it('anchors every shortcut on the same period instead of walking forward', async () => {
      const wrapper = await mountHostingCreate({ suggestedStart: '2026-09-01' });

      await wrapper.get('[data-testid="income-form-cycle-12"]').trigger('click');
      expect(wrapper.find('[data-testid="income-form-period-start"]').element.value)
        .toBe('2026-09-01');
      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2027-08-31');

      // Re-lengthening the same window, not opening the one after it.
      await wrapper.get('[data-testid="income-form-cycle-1"]').trigger('click');
      expect(wrapper.find('[data-testid="income-form-period-start"]').element.value)
        .toBe('2026-09-01');
      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2026-09-30');
      expect(wrapper.find('[data-testid="income-form-period-cadence"]').element.value)
        .toBe('monthly');
    });

    it('offers the shortcuts while opening a period and never while editing one', async () => {
      const created = await mountHostingCreate();
      expect(created.find('[data-testid="income-form-cycles"]').exists()).toBe(true);

      const edited = mountModal({
        record: {
          ...EDIT_RECORD,
          origin: 'hosting',
          period_start: '2026-05-01',
          period_end: '2026-07-31',
          period_cadence: 'quarterly',
        },
      });
      await flushPromises();
      expect(edited.find('[data-testid="income-form-cycles"]').exists()).toBe(false);
    });

    it('keeps the stored end when an edit opens on a window that disagrees', async () => {
      // Prefilling writes start, end and cadence at once; treating that batch
      // as a cadence choice would overwrite the end actually saved.
      const wrapper = mountModal({
        record: {
          ...EDIT_RECORD,
          origin: 'hosting',
          period_start: '2026-05-01',
          period_end: '2026-06-15',
          period_cadence: 'quarterly',
        },
      });
      await flushPromises();

      expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
        .toBe('2026-06-15');
    });

    it('still opens a window when the antecedent cannot be fetched', async () => {
      // The lookup is a convenience, not a precondition: a failing request
      // must leave the operator with a usable block, not an inert one.
      get_request.mockImplementation(() => Promise.reject(new Error('boom')));
      jest.useFakeTimers().setSystemTime(new Date('2026-08-15T09:00:00'));
      try {
        const wrapper = mountModal();
        await segmentedButton(wrapper, 'Hosting').trigger('click');
        await flushPromises();

        await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('monthly');

        expect(wrapper.find('[data-testid="income-form-period-start"]').element.value)
          .toBe('2026-08-15');
        expect(wrapper.find('[data-testid="income-form-period-end"]').element.value)
          .toBe('2026-09-14');
        // Nothing to say about a period that was never resolved.
        expect(wrapper.find('[data-testid="income-form-period-hint"]').exists())
          .toBe(false);
      } finally {
        jest.useRealTimers();
      }
    });

    it('refuses an end that does not come after the start, and says why', async () => {
      const wrapper = await mountHostingCreate();

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('custom');
      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2026-09-01');
      await wrapper.find('[data-testid="income-form-period-end"]').setValue('2026-09-01');
      await wrapper.find('form').trigger('submit');

      expectDescribedError(
        wrapper,
        'income-form-period-end',
        'La fecha de fin debe ser posterior a la de inicio.',
      );
      expect(wrapper.emitted('submit')).toBeUndefined();
    });
  });

  describe('duplicate period anchor', () => {
    /**
     * Every case here runs on a system clock far away from the dates asserted.
     * That is the point of the block: a duplicate must count from the record
     * it copies, and today is the answer these tests exist to rule out.
     */
    const CLOCK = '2026-11-20T09:00:00';

    function seedWithAnchor(anchor, overrides = {}) {
      return {
        ...DUPLICATE_SEED,
        period_date: null,
        period_date_source: null,
        period_start: null,
        period_end: null,
        period_cadence: '',
        cycle_options: CYCLE_OPTIONS,
        period_anchor: {
          source: 'original_date',
          start: null,
          origin_start: null,
          origin_end: null,
          origin_date: '2026-02-01',
          ...anchor,
        },
        ...overrides,
      };
    }

    /** Mount a duplicate with the clock pinned away from every expectation. */
    function mountDuplicate(seed) {
      jest.useFakeTimers().setSystemTime(new Date(CLOCK));
      return mountModal({ seed });
    }

    const notice = (wrapper) => wrapper
      .find('[data-testid="income-form-anchor-notice"]');
    const startOf = (wrapper) => wrapper
      .find('[data-testid="income-form-period-start"]').element.value;
    const endOf = (wrapper) => wrapper
      .find('[data-testid="income-form-period-end"]').element.value;

    afterEach(() => {
      jest.useRealTimers();
    });

    it('counts an original with no window from its own date, not from today', async () => {
      // The everyday case: the original predates the window block and its
      // client holds several hostings, so the catalog cannot decide either.
      const wrapper = mountDuplicate(seedWithAnchor());

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('quarterly');

      expect(startOf(wrapper)).toBe('2026-05-01');
      expect(endOf(wrapper)).toBe('2026-07-31');
    });

    it('re-reads the whole window when the periodicity changes on that anchor', async () => {
      // With no recorded end, the length just chosen is what decides where the
      // original's period closed — so the start moves with it.
      const wrapper = mountDuplicate(seedWithAnchor());

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('quarterly');
      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('annual');

      expect(startOf(wrapper)).toBe('2027-02-01');
      expect(endOf(wrapper)).toBe('2028-01-31');
    });

    it('chains a shortcut from the original date too', async () => {
      const wrapper = mountDuplicate(seedWithAnchor());

      await wrapper.get('[data-testid="income-form-cycle-3"]').trigger('click');

      expect(startOf(wrapper)).toBe('2026-05-01');
      expect(endOf(wrapper)).toBe('2026-07-31');
      expect(wrapper.find('[data-testid="income-form-period-cadence"]').element.value)
        .toBe('quarterly');
    });

    it('keeps a recorded window pinned while the periodicity only moves the end', async () => {
      // The opposite half of the rule: here the original DOES state where its
      // period closed, so no cadence may move where the next one opens.
      const wrapper = mountDuplicate(seedWithAnchor({
        source: 'income_period',
        start: '2026-08-01',
        origin_start: '2026-02-01',
        origin_end: '2026-07-31',
      }, { period_start: '2026-08-01', period_cadence: 'semiannual' }));

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('quarterly');
      expect(startOf(wrapper)).toBe('2026-08-01');
      expect(endOf(wrapper)).toBe('2026-10-31');

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('annual');
      expect(startOf(wrapper)).toBe('2026-08-01');
      expect(endOf(wrapper)).toBe('2027-07-31');
    });

    it('leaves a start written by hand where the operator put it', async () => {
      const wrapper = mountDuplicate(seedWithAnchor());

      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('quarterly');
      await wrapper.find('[data-testid="income-form-period-start"]').setValue('2026-06-10');
      await wrapper.find('[data-testid="income-form-period-cadence"]').setValue('annual');

      expect(startOf(wrapper)).toBe('2026-06-10');
      expect(endOf(wrapper)).toBe('2027-06-09');
    });

    it('says the duplicate continues the window the original recorded', () => {
      const wrapper = mountDuplicate(seedWithAnchor({
        source: 'income_period',
        start: '2026-08-01',
        origin_start: '2026-02-01',
        origin_end: '2026-07-31',
      }, { period_start: '2026-08-01' }));

      const text = notice(wrapper).text();
      expect(text).toContain('cubre del');
      expect(text).toContain('1 feb 2026');
      expect(text).toContain('31 jul 2026');
      expect(text).toContain('1 ago 2026');
    });

    it('says the count came from the hosting cycle over the original date', () => {
      const wrapper = mountDuplicate(seedWithAnchor({
        source: 'hosting_cycle',
        start: '2026-05-01',
      }, { period_date: '2026-05-01' }));

      const text = notice(wrapper).text();
      expect(text).toContain('ciclo del hosting');
      expect(text).toContain('1 feb 2026');
      expect(text).toContain('1 may 2026');
    });

    it('says the calculation waits on the periodicity when only a date is known', () => {
      const wrapper = mountDuplicate(seedWithAnchor());

      const text = notice(wrapper).text();
      expect(text).toContain('1 feb 2026');
      expect(text).toContain('periodicidad');
    });

    it('admits when there is nothing at all to chain with', () => {
      // Reached only when the original carries no date either. Saying so is
      // the whole point: a window opening on today looks exactly like one
      // that continues something.
      const wrapper = mountDuplicate(seedWithAnchor({
        source: null, origin_date: null,
      }));

      expect(notice(wrapper).text()).toContain('no encadena con nada');
    });

    it('claims no provenance for a draft that carries no anchor', () => {
      // A draft built before the anchor travelled still opens and still works;
      // it just does not get to assert where its dates came from.
      const wrapper = mountDuplicate({ ...DUPLICATE_SEED });

      expect(notice(wrapper).exists()).toBe(false);
      expect(startOf(wrapper)).toBe('2027-03-01');
    });

    it('explains nothing when no period is being opened', async () => {
      // Real timers here: nothing below asserts a date, and mountHostingCreate
      // awaits a request the fake clock would leave hanging.
      const duplicatedDevelopment = mountModal({
        seed: seedWithAnchor({}, { origin: 'development' }),
      });
      expect(notice(duplicatedDevelopment).exists()).toBe(false);

      const created = await mountHostingCreate();
      expect(notice(created).exists()).toBe(false);

      const edited = mountModal({
        record: {
          ...EDIT_RECORD,
          origin: 'hosting',
          period_start: '2026-05-01',
          period_end: '2026-07-31',
          period_cadence: 'quarterly',
        },
        seed: seedWithAnchor(),
      });
      await flushPromises();
      expect(notice(edited).exists()).toBe(false);
    });
  });

  it('prefers the record over the seed, so an edit is never seeded', () => {
    const wrapper = mountModal({
      record: { ...EDIT_RECORD },
      seed: { ...DUPLICATE_SEED },
    });

    expect(wrapper.text()).toContain('Editar Ingreso');
    expect(wrapper.find('input[type="text"]').element.value).toBe('Página web Acme');
  });

  it('personal ledger hides the split and destination controls', async () => {
    const wrapper = mountModal();

    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(true);

    await segmentedButton(wrapper, 'Líquido').trigger('click');
    await segmentedButton(wrapper, 'Personal Gustavo').trigger('click');

    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Destino');
    expect(wrapper.text()).toContain('Cómo introduces el valor');
  });

  it('keeps the 19% VAT default after choosing a personal ledger', async () => {
    // Fails if changing a new income to a personal ledger silently drops its default VAT.
    const wrapper = mountModal();

    await segmentedButton(wrapper, 'Personal Gustavo').trigger('click');
    await wrapper.find('input[type="text"]').setValue('Ingreso personal');
    await segmentedButton(wrapper, 'Otro').trigger('click');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0].vat_rate).toBe(19);
  });

  it('personal ledger submits its VAT-aware capture without split amounts', async () => {
    const wrapper = mountModal();

    await segmentedButton(wrapper, 'Líquido').trigger('click');
    await segmentedButton(wrapper, 'Personal Gustavo').trigger('click');
    await wrapper.find('input[type="text"]').setValue('Ingreso personal');
    await wrapper.find('[data-testid="income-form-period"]').setValue('2026-06-15');
    await wrapper.find('[data-testid="vat-amount"]').setValue('54099');
    await segmentedButton(wrapper, 'Otro').trigger('click');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload).toMatchObject({
      ledger: 'gustavo',
      destination: 'partners',
      vat_rate: 19,
      amount: 54099,
      amount_mode: 'vat_included',
    });
    expect(payload).not.toHaveProperty('total_amount');
    expect(payload).not.toHaveProperty('gustavo_amount');
    expect(payload).not.toHaveProperty('carlos_amount');
  });

  it('prefills ledger from record and switching back to company restores split', async () => {
    const wrapper = mountModal({
      record: {
        concept: 'Universidad Nacional',
        kind: 'liquid',
        period: '2026-02',
        period_date: '2026-02-01',
        destination: 'partners',
        ledger: 'gustavo',
        total_amount: '1400000',
        gustavo_amount: '1400000',
        carlos_amount: '0',
        notes: '',
      },
    });

    expect(segmentedButton(wrapper, 'Personal Gustavo').attributes('aria-selected')).toBe('true');
    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(false);

    await segmentedButton(wrapper, 'Empresa').trigger('click');
    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(true);
  });

  it('always includes notes so edits can clear them', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Sin nota');
    await segmentedButton(wrapper, 'Otro').trigger('click');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.notes).toBe('');
  });

  it('hides destination when kind is expected and forces it back to partners', async () => {
    const wrapper = mountModal();

    // default kind is expected -> destination hidden
    expect(wrapper.text()).not.toContain('Destino');

    await segmentedButton(wrapper, 'Líquido').trigger('click');
    expect(wrapper.text()).toContain('Destino');

    await segmentedButton(wrapper, 'Bolsillo ProjectApp').trigger('click');
    await segmentedButton(wrapper, 'Esperado').trigger('click');
    expect(wrapper.text()).not.toContain('Destino');

    await wrapper.find('input[type="text"]').setValue('Ingreso esperado');
    await wrapper.find('[data-testid="income-form-period"]').setValue('2026-07-15');
    await segmentedButton(wrapper, 'Otro').trigger('click');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.kind).toBe('expected');
    expect(payload.destination).toBe('partners');
    expect(payload.ledger).toBe('company');
  });

  it('offers Perdido as a kind', () => {
    const wrapper = mountModal();

    expect(segmentedButton(wrapper, 'Perdido').attributes('aria-selected')).toBe('false');
  });

  it('drops a pocket destination when switching to Perdido', async () => {
    // Pocket is liquid-only server-side: a stale destination would 400.
    const wrapper = mountModal();

    await segmentedButton(wrapper, 'Líquido').trigger('click');
    await segmentedButton(wrapper, 'Bolsillo ProjectApp').trigger('click');
    await segmentedButton(wrapper, 'Perdido').trigger('click');
    expect(wrapper.text()).not.toContain('Destino');

    await wrapper.find('input[type="text"]').setValue('Catherine Ruiz Candles');
    await wrapper.find('[data-testid="income-form-period"]').setValue('2026-07-15');
    await segmentedButton(wrapper, 'Otro').trigger('click');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.kind).toBe('lost');
    expect(payload.destination).toBe('partners');
  });

  it('emits close when Cancelar is clicked', async () => {
    const wrapper = mountModal();

    const cancel = wrapper.findAll('button').find((b) => b.text() === 'Cancelar');
    await cancel.trigger('click');

    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('disables submit and shows Guardando... while saving', () => {
    const wrapper = mountModal({ saving: true });

    const submit = wrapper.find('[data-testid="income-form-submit"]');
    expect(submit.attributes('disabled')).toBeDefined();
    expect(submit.text()).toContain('Guardando...');
  });

  it('pre-fills the only project on create but never on edit (PA-51)', async () => {
    const creating = mountModal();
    await flushPromises();
    expect(
      creating.findComponent({ name: 'ProjectSelect' }).props('autoSelectSingle'),
    ).toBe(true);

    const editing = mountModal({ record: { ...EDIT_RECORD } });
    await flushPromises();
    expect(
      editing.findComponent({ name: 'ProjectSelect' }).props('autoSelectSingle'),
    ).toBe(false);
  });

  describe('business line', () => {
    /** The origin the control is currently showing as chosen. */
    function selectedOrigin(wrapper) {
      const chosen = wrapper
        .find('[data-testid="income-form-origin"]')
        .findAll('button')
        .find((button) => button.attributes('aria-selected') === 'true');
      return chosen ? chosen.text() : '';
    }

    // Each line of business with the date block it governs. Hosting is the
    // one that covers a window; the other three are point payments.
    const LINES = [
      { origin: 'development', label: 'Desarrollo', hosting: false },
      { origin: 'hosting', label: 'Hosting', hosting: true },
      { origin: 'diagnostic', label: 'Diagnóstico', hosting: false },
      { origin: 'other', label: 'Otro', hosting: false },
    ];

    it.each(LINES)(
      'opens a $origin duplicate already on $label, with its own date block',
      async ({ origin, label, hosting }) => {
        const wrapper = mountModal({
          seed: { ...DUPLICATE_SEED, origin, period_date: '2027-03-01' },
        });
        await flushPromises();

        expect(selectedOrigin(wrapper)).toBe(label);
        // The origin is what decides this, which is why losing it opens the
        // form configured as a different kind of income than the original.
        expect(wrapper.find('[data-testid="income-form-period-cadence"]').exists())
          .toBe(hosting);
        expect(wrapper.find('[data-testid="income-form-period-start"]').exists())
          .toBe(hosting);
        expect(wrapper.find('[data-testid="income-form-period"]').exists())
          .toBe(!hosting);
      },
    );

    it('says so when the original carried no business line', async () => {
      const wrapper = mountModal({
        seed: { ...DUPLICATE_SEED, origin: '', period_anchor: null },
      });
      await flushPromises();

      expect(selectedOrigin(wrapper)).toBe('');
      // Without this the blank reads as a copy that failed, which is exactly
      // how it was reported.
      expect(wrapper.find('[data-testid="income-form-origin-notice"]').text())
        .toContain('El ingreso original no tiene origen registrado');
    });

    it('stays quiet when the original carried one', async () => {
      const wrapper = mountModal({ seed: { ...DUPLICATE_SEED } });
      await flushPromises();

      expect(wrapper.find('[data-testid="income-form-origin-notice"]').exists())
        .toBe(false);
    });

    it('does not explain itself on a plain create', async () => {
      const wrapper = mountModal();
      await flushPromises();

      // Nothing was copied, so there is no original to report on.
      expect(wrapper.find('[data-testid="income-form-origin-notice"]').exists())
        .toBe(false);
    });

    it('refuses to save without one, and only after the first attempt', async () => {
      const wrapper = mountModal();
      await wrapper.find('input[type="text"]').setValue('Anticipo cliente');

      // A form that opens already complaining teaches the operator to ignore it.
      expect(wrapper.find('[data-testid="form-field-error"]').exists()).toBe(false);

      await wrapper.find('form').trigger('submit');

      expect(wrapper.emitted('submit')).toBeUndefined();
      const originError = wrapper.findAll('[role="alert"]')
        .find((node) => node.text() === 'Elige la línea de negocio del ingreso.');
      expect(originError).toBeDefined();

      await segmentedButton(wrapper, 'Diagnóstico').trigger('click');
      await wrapper.find('form').trigger('submit');

      expect(wrapper.emitted('submit')).toHaveLength(1);
      expect(wrapper.emitted('submit')[0][0].origin).toBe('diagnostic');
    });
  });
});
