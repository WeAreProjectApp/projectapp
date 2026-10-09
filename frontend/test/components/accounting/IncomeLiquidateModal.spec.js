import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import IncomeLiquidateModal from '../../../components/accounting/IncomeLiquidateModal.vue';

// The covered-period block leans on `useHostingPeriod`, which resolves the
// accounting store at setup — even when the block itself stays hidden.
beforeEach(() => {
  setActivePinia(createPinia());
});

const PartnerSplitInputStub = {
  name: 'PartnerSplitInput',
  props: {
    total: [String, Number],
    gustavoAmount: [String, Number],
    carlosAmount: [String, Number],
    compact: Boolean,
  },
  emits: ['update:total', 'update:gustavoAmount', 'update:carlosAmount'],
  template: `
    <div data-testid="partner-split-stub" :data-compact="compact ? 'yes' : 'no'">
      <input data-testid="split-total" :value="total" @input="$emit('update:total', $event.target.value)" />
      <input data-testid="split-gustavo" :value="gustavoAmount" @input="$emit('update:gustavoAmount', $event.target.value)" />
      <input data-testid="split-carlos" :value="carlosAmount" @input="$emit('update:carlosAmount', $event.target.value)" />
    </div>
  `,
};

const expectedRecord = {
  id: 42,
  concept: 'Kore v2 (Fase 1) - Inicio 40%',
  kind: 'expected',
  ledger: 'company',
  period_label: 'Agosto 2026',
  period: '2026-08',
  total_amount: '1000000.00',
  paid_amount: '400000.00',
  pending_amount: '600000.00',
  payment_status: 'partial',
};

function mountModal(props = {}, stubs = {}) {
  return mount(IncomeLiquidateModal, {
    props: {
      open: true,
      record: expectedRecord,
      saving: false,
      ...props,
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'error', 'required', 'for', 'size'],
          template: '<div><label v-if="label">{{ label }}</label><slot /></div>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<input :type="type || \'text\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseCurrencyInput: {
          props: ['modelValue', 'decimals', 'size', 'error', 'placeholder', 'disabled', 'suggestion'],
          emits: ['update:modelValue'],
          // The real component emits a NUMBER (or null when empty), not the
          // typed string — the payload assertions depend on that contract.
          template:
            '<input type="text" inputmode="numeric" :value="modelValue" :data-suggestion="suggestion" :data-error="error ? \'true\' : undefined" @input="$emit(\'update:modelValue\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
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
            '<div><button v-for="o in options" :key="o.value" type="button" @click="$emit(\'update:modelValue\', o.value)">{{ o.label }}</button></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'loading', 'disabled'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseToggle: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
        },
        BaseSelect: {
          props: ['modelValue', 'options', 'size', 'error', 'disabled', 'placeholder'],
          emits: ['update:modelValue'],
          template:
            '<select :value="modelValue" :data-error="error ? \'true\' : undefined" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-if="placeholder" value="" disabled>{{ placeholder }}</option><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
        },
        BaseCollapse: {
          props: ['open', 'id'],
          template: '<div v-if="open"><slot /></div>',
        },
        BaseBadge: {
          props: ['variant', 'size'],
          template: '<span :data-variant="variant"><slot /></span>',
        },
        PartnerSplitInput: PartnerSplitInputStub,
        ...stubs,
      },
    },
  });
}

describe('IncomeLiquidateModal', () => {
  it('names the expected income being settled', () => {
    const wrapper = mountModal();

    expect(wrapper.text()).toContain('Liquidar ingreso esperado');
    expect(wrapper.text()).toContain('Kore v2 (Fase 1) - Inicio 40%');
    expect(wrapper.text()).toContain('Agosto 2026');
  });

  it('prefills the amount with what is still owed, not the full projection', () => {
    // They often pay late AND short, so the remainder is the useful default.
    const wrapper = mountModal();

    expect(wrapper.find('[data-testid="split-total"]').element.value)
      .toBe('600000.00');
    expect(wrapper.find('[data-testid="income-liquidate-pending"]').text())
      .toContain('600.000');
  });

  it('defaults to the exact payment date prefilled with today', () => {
    // 20:00 local: toISOString() would already be tomorrow in Bogotá
    // (UTC-5) — this pins the local-date formatting.
    jest.useFakeTimers().setSystemTime(new Date('2026-07-27T20:00:00'));
    try {
      const wrapper = mountModal();

      const dateInput = wrapper.find('input[type="date"]');
      expect(dateInput.exists()).toBe(true);
      expect(dateInput.element.value).toBe('2026-07-27');
    } finally {
      jest.useRealTimers();
    }
  });

  it('downgrades to month-only via the toggle and back', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="date"]').setValue('2026-11-17');
    await wrapper
      .find('[data-testid="income-liquidate-exact-date"]')
      .setValue(false);

    // The typed date is kept, reduced to the month the user can fix.
    expect(wrapper.find('input[type="month"]').element.value).toBe('2026-11');

    await wrapper
      .find('[data-testid="income-liquidate-exact-date"]')
      .setValue(true);
    expect(wrapper.find('input[type="date"]').element.value).toBe('2026-11-01');
  });

  it('submits the exact payment date', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="date"]').setValue('2026-11-17');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0].period_date).toBe('2026-11-17');
  });

  it('submits a month-only settlement with no allocations', async () => {
    // `kind`, `ledger` and the parent link are derived server-side from the
    // record the settle endpoint is called on.
    const wrapper = mountModal();

    await wrapper
      .find('[data-testid="income-liquidate-exact-date"]')
      .setValue(false);
    await wrapper.find('input[type="month"]').setValue('2026-11');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.period_date).toBe('2026-11');
    expect(payload.total_amount).toBe('600000.00');
    expect(payload.deductions).toEqual([]);
    expect(payload.expected_incomes).toEqual([]);
  });

  it('defaults the destination to pocket and omits a split left blank', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="date"]').setValue('2026-11-17');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    // Money defaults into the pocket; distributing to the partners is the
    // explicit choice.
    expect(payload.destination).toBe('pocket');
    // PartnerSplitInput fills the automatic split as soon as it mounts (this
    // stub never does): a split still blank is left out, and the server's
    // split_half applies the same whole-peso halves.
    expect(payload.gustavo_amount).toBeUndefined();
    expect(payload.carlos_amount).toBeUndefined();
  });

  // Bug caught: the modal opened on the pending amount with the 50/50 toggle
  // on and both partner fields empty, so nobody saw what each partner got.
  it('shows and submits the automatic split of the prefilled amount', async () => {
    const wrapper = mountModal({}, { PartnerSplitInput: false });
    await flushPromises();

    expect(wrapper.get('[data-testid="partner-split-gustavo"]').element.value).toBe('300000');
    expect(wrapper.get('[data-testid="partner-split-carlos"]').element.value).toBe('300000');

    await wrapper.find('input[type="date"]').setValue('2026-11-17');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.gustavo_amount).toBe(300000);
    expect(payload.carlos_amount).toBe(300000);
  });

  it('sends the split when the user fills it', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="split-gustavo"]').setValue('400000');
    await wrapper.find('[data-testid="split-carlos"]').setValue('200000');
    await wrapper.find('input[type="date"]').setValue('2026-11-17');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.gustavo_amount).toBe('400000');
    expect(payload.carlos_amount).toBe('200000');
  });

  it('allows overriding the amount for a partial payment', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="split-total"]').setValue('250000');
    await wrapper.find('input[type="date"]').setValue('2026-09-15');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.total_amount).toBe('250000');
  });

  it('falls back to the total when the record has no pending amount', () => {
    const wrapper = mountModal({
      record: { ...expectedRecord, pending_amount: null },
    });

    expect(wrapper.find('[data-testid="split-total"]').element.value)
      .toBe('1000000.00');
  });

  it('omits the split and hides destination for a personal ledger', async () => {
    const wrapper = mountModal({
      record: { ...expectedRecord, ledger: 'gustavo' },
    });

    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Destino');

    await wrapper.find('input[type="date"]').setValue('2026-11-17');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.gustavo_amount).toBeUndefined();
    expect(payload.carlos_amount).toBeUndefined();
  });

  // Falla si la compactación visual desconecta el total o uno de los socios.
  it('keeps every company split control in compact mode', () => {
    const wrapper = mountModal();
    const split = wrapper.get('[data-testid="partner-split-stub"]');

    expect(split.attributes('data-compact')).toBe('yes');
    expect(wrapper.get('[data-testid="split-total"]').element.value).toBe('600000.00');
    expect(wrapper.get('[data-testid="split-gustavo"]').element.value).toBe('');
    expect(wrapper.get('[data-testid="split-carlos"]').element.value).toBe('');
  });

  // Falla si la redistribución elimina la fecha al no mostrar el reparto personal.
  it('keeps the payment date for a personal settlement', async () => {
    const wrapper = mountModal({ record: { ...expectedRecord, ledger: 'gustavo' } });

    await wrapper.find('input[type="date"]').setValue('2026-11-17');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0].period_date).toBe('2026-11-17');
  });

  // Falla si una llamada directa liquida una fila local que aún necesita cuenta emitida.
  it('does not emit settlement when a client account is still a draft', async () => {
    const wrapper = mountModal({
      record: {
        ...expectedRecord,
        client: 12,
        collection_account_status: 'draft',
      },
    });

    expect(wrapper.get('[data-testid="income-liquidate-submit"]').element.disabled).toBe(true);
    expect(wrapper.get('[data-testid="income-liquidate-submit-reason"]').text())
      .toBe('Primero genera y emite una cuenta de cobro para este ingreso.');

    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')).toBeUndefined();
  });

  it('emits close when Cancelar is clicked', async () => {
    const wrapper = mountModal();

    const cancel = wrapper.findAll('button').find((b) => b.text() === 'Cancelar');
    await cancel.trigger('click');

    expect(wrapper.emitted('close')).toEqual([[]]);
  });

  // ── Shortfall (the money that did not arrive) ──

  const shortfall = (wrapper) =>
    wrapper.find('[data-testid="income-liquidate-shortfall"]');

  /** Receive less than pending so the shortfall section appears. */
  async function receiveShort(wrapper, amount = '550000') {
    await wrapper.find('[data-testid="split-total"]').setValue(amount);
  }

  const submitButton = (wrapper) =>
    wrapper.find('[data-testid="income-liquidate-submit"]');

  it('hides the shortfall section when the full pending amount is received', () => {
    const wrapper = mountModal();

    expect(shortfall(wrapper).exists()).toBe(false);
  });

  it('shows the shortfall as soon as the payment falls short', async () => {
    const wrapper = mountModal();

    await receiveShort(wrapper);

    expect(shortfall(wrapper).exists()).toBe(true);
    expect(shortfall(wrapper).text()).toContain('50.000');
  });

  it('warns that an unallocated balance stays pending', async () => {
    const wrapper = mountModal();

    await receiveShort(wrapper);

    expect(wrapper.find('[data-testid="income-liquidate-remaining"]').text())
      .toContain('quedará pendiente');
    // Not allocating is allowed — that is today's behaviour.
    expect(submitButton(wrapper).element.disabled).toBe(false);
  });

  it('submits the shortfall as a deduction', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    // The concept is an explicit choice now — rows start unselected.
    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('50000');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.deductions).toEqual([
      { type: 'gateway_fee', detail: '', amount: 50000 },
    ]);
  });

  it('submits a residual-only resolution with zero received', async () => {
    // Nothing new arrived — the whole pending was a fee. The server closes
    // the expected without creating a liquid child.
    const wrapper = mountModal();

    await wrapper.find('[data-testid="split-total"]').setValue('0');
    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('600000');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.total_amount).toBe('0');
    expect(payload.deductions).toEqual([
      { type: 'gateway_fee', detail: '', amount: 600000 },
    ]);
  });

  it('coerces an emptied amount to zero', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="split-total"]').setValue('');
    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('600000');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.total_amount).toBe(0);
  });

  it('reports the balance as fully resolved once it is allocated', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('50000');

    expect(wrapper.find('[data-testid="income-liquidate-remaining"]').text())
      .toContain('queda cerrado');
  });

  it('requires the free text when the concept is "Otro"', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper.find('[data-testid="deduction-type-0"]').setValue('other');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('50000');

    expect(submitButton(wrapper).element.disabled).toBe(true);

    await wrapper
      .find('[data-testid="deduction-detail-0"]').setValue('Descuento pactado');

    expect(submitButton(wrapper).element.disabled).toBe(false);
  });

  it('submits follow-up expected incomes for a balance that will be collected', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper
      .find('[data-testid="income-liquidate-followups-toggle"]').trigger('click');
    await wrapper.find('[data-testid="followup-concept-0"]').setValue('Saldo septiembre');
    await wrapper.find('[data-testid="followup-period-0"]').setValue('2026-09');
    await wrapper.find('[data-testid="followup-amount-0"]').setValue('50000');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.expected_incomes).toEqual([
      { concept: 'Saldo septiembre', period_date: '2026-09', amount: 50000 },
    ]);
  });

  it('splits the shortfall between a deduction and a follow-up income', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('8000');
    await wrapper
      .find('[data-testid="income-liquidate-followups-toggle"]').trigger('click');
    await wrapper.find('[data-testid="followup-concept-0"]').setValue('Saldo');
    await wrapper.find('[data-testid="followup-period-0"]').setValue('2026-09');
    await wrapper.find('[data-testid="followup-amount-0"]').setValue('42000');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.deductions).toHaveLength(1);
    expect(payload.expected_incomes).toHaveLength(1);
  });

  it('blocks the submit when the allocation exceeds the shortfall', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('80000');

    expect(wrapper.find('[data-testid="income-liquidate-remaining"]').text())
      .toContain('Te pasaste');
    expect(submitButton(wrapper).element.disabled).toBe(true);

    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')).toBeFalsy();
  });

  it('supports more than one follow-up expected income', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper
      .find('[data-testid="income-liquidate-followups-toggle"]').trigger('click');
    await wrapper
      .find('[data-testid="income-liquidate-add-followup"]').trigger('click');

    expect(wrapper.findAll('[data-testid^="income-liquidate-followup-"]'))
      .toHaveLength(2);
  });

  // ── Assisted distribution: badge, suggestion, per-line validation ──

  it('starts a new deduction row with no concept selected', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    const select = wrapper.find('[data-testid="deduction-type-0"]');
    expect(select.element.value).toBe('');
    expect(select.text()).toContain('Seleccionar concepto');
  });

  it('reflects the allocation state in the badge tone', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    const badge = () =>
      wrapper.find('[data-testid="income-liquidate-remaining"] [data-variant]');
    expect(badge().attributes('data-variant')).toBe('info');

    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('50000');
    expect(badge().attributes('data-variant')).toBe('success');

    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('99000');
    expect(badge().attributes('data-variant')).toBe('danger');
  });

  it('suggests the unassigned remainder on the line amounts', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    expect(
      wrapper.find('[data-testid="deduction-amount-0"]').attributes('data-suggestion'),
    ).toBe('50000');

    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('30000');
    await wrapper
      .find('[data-testid="income-liquidate-add-deduction"]').trigger('click');

    expect(
      wrapper.find('[data-testid="deduction-amount-1"]').attributes('data-suggestion'),
    ).toBe('20000');
  });

  it('flags the deduction row that still needs a concept', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('50000');

    expect(wrapper.find('[data-testid="deduction-error-0"]').text())
      .toBe('Selecciona el concepto.');
    expect(
      wrapper.find('[data-testid="deduction-type-0"]').attributes('data-error'),
    ).toBe('true');
    expect(submitButton(wrapper).element.disabled).toBe(true);
  });

  it('flags an empty or non-positive amount on an active row', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    expect(wrapper.find('[data-testid="deduction-error-0"]').text())
      .toBe('Ingresa el monto.');

    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('0');
    expect(wrapper.find('[data-testid="deduction-error-0"]').text())
      .toBe('El monto debe ser mayor a cero.');
  });

  it('marks the row that pushed the allocation over the balance', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('80000');

    const error = wrapper.find('[data-testid="deduction-error-0"]');
    expect(error.text()).toContain('supera el saldo');
    expect(error.text()).toContain('30.000');
    // The typed value is kept — the user must see what they wrote.
    expect(wrapper.find('[data-testid="deduction-amount-0"]').element.value)
      .toBe('80000');

    // Fixing the amount clears the flag on its own.
    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('50000');
    expect(wrapper.find('[data-testid="deduction-error-0"]').exists()).toBe(false);
  });

  it('no longer blocks the submit on an untouched follow-up row', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    // Opening adds a prefilled row; collapsing leaves it behind — it used
    // to jam the submit invisibly from inside the closed group.
    await wrapper
      .find('[data-testid="income-liquidate-followups-toggle"]').trigger('click');
    await wrapper
      .find('[data-testid="income-liquidate-followups-toggle"]').trigger('click');

    expect(submitButton(wrapper).element.disabled).toBe(false);

    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')[0][0].expected_incomes).toEqual([]);
  });

  it('explains why the submit is disabled', async () => {
    const wrapper = mountModal();
    await receiveShort(wrapper);

    const reason = () =>
      wrapper.find('[data-testid="income-liquidate-submit-reason"]');

    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('50000');
    expect(reason().text())
      .toBe('Hay líneas de gasto incompletas: revisa concepto y monto.');

    await wrapper.find('[data-testid="deduction-type-0"]').setValue('gateway_fee');
    expect(reason().text()).toBe('');

    await wrapper.find('[data-testid="deduction-amount-0"]').setValue('80000');
    expect(reason().text()).toContain('La distribución supera el saldo por resolver');
  });
});

describe('shortfall discoverability', () => {
  it('shows the hint until a shortfall appears', async () => {
    const wrapper = mountModal();

    expect(
      wrapper.find('[data-testid="income-liquidate-shortfall-hint"]').exists(),
    ).toBe(true);

    await wrapper.find('[data-testid="split-total"]').setValue('550000');

    expect(
      wrapper.find('[data-testid="income-liquidate-shortfall-hint"]').exists(),
    ).toBe(false);
  });

  it('auto-expands the deductions group when the shortfall appears', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="split-total"]').setValue('550000');

    // No toggle click: the group opens itself with a row ready to fill.
    expect(
      wrapper.find('[data-testid="income-liquidate-deduction-0"]').exists(),
    ).toBe(true);
  });

  it('does not re-expand after the user collapses the group', async () => {
    const wrapper = mountModal();
    await wrapper.find('[data-testid="split-total"]').setValue('550000');

    await wrapper
      .find('[data-testid="income-liquidate-deductions-toggle"]').trigger('click');
    expect(
      wrapper.find('[data-testid="income-liquidate-deduction-0"]').exists(),
    ).toBe(false);

    await wrapper.find('[data-testid="split-total"]').setValue('400000');

    expect(
      wrapper.find('[data-testid="income-liquidate-deduction-0"]').exists(),
    ).toBe(false);
  });
});

describe('covered period of a hosting charge', () => {
  // A hosting charge from before the period fields existed: the block exists
  // for exactly this record.
  const legacyHosting = {
    ...expectedRecord,
    id: 230,
    concept: 'Vastago (Hosting) - Semestre 1',
    origin: 'hosting',
    period_date: '2026-10-01',
    period_start: null,
    period_end: null,
    period_cadence: '',
  };

  const block = (wrapper) =>
    wrapper.find('[data-testid="income-liquidate-period-block"]');

  async function submit(wrapper) {
    await wrapper.find('form').trigger('submit');
    return wrapper.emitted('submit')?.[0]?.[0];
  }

  it('stays out of the way of an income that is not hosting', () => {
    const wrapper = mountModal();

    expect(block(wrapper).exists()).toBe(false);
  });

  it('stays out of the way of a hosting that already recorded its window', () => {
    const wrapper = mountModal({
      record: {
        ...legacyHosting,
        period_start: '2026-08-01',
        period_end: '2026-10-31',
        period_cadence: 'quarterly',
      },
    });

    expect(block(wrapper).exists()).toBe(false);
  });

  it('opens the window on the charge date when there is none recorded', () => {
    const wrapper = mountModal({ record: legacyHosting });

    expect(block(wrapper).exists()).toBe(true);
    expect(
      wrapper.find('[data-testid="income-liquidate-period-start"]').element.value,
    ).toBe('2026-10-01');
  });

  it('computes the end of the period from the periodicity', async () => {
    const wrapper = mountModal({ record: legacyHosting });

    await wrapper
      .find('[data-testid="income-liquidate-period-cadence"]')
      .setValue('semiannual');

    expect(
      wrapper.find('[data-testid="income-liquidate-period-end"]').element.value,
    ).toBe('2027-03-31');
  });

  it('sends the completed window alongside the settlement', async () => {
    const wrapper = mountModal({ record: legacyHosting });
    await wrapper
      .find('[data-testid="income-liquidate-period"]')
      .setValue('2026-11-17');
    await wrapper
      .find('[data-testid="income-liquidate-period-cadence"]')
      .setValue('semiannual');

    const payload = await submit(wrapper);

    expect(payload.period).toEqual({
      period_start: '2026-10-01',
      period_end: '2027-03-31',
      period_cadence: 'semiannual',
    });
    // The payment keeps its own date: the window describes the charge.
    expect(payload.period_date).toBe('2026-11-17');
  });

  it('settles with no window at all when the block is left untouched', async () => {
    const wrapper = mountModal({ record: legacyHosting });

    const payload = await submit(wrapper);

    // It went through — with no window attached to it.
    expect(payload.concept).toBe('Vastago (Hosting) - Semestre 1');
    expect(payload.period).toBeUndefined();
  });

  it('refuses to send a window that was started and left half written', async () => {
    const wrapper = mountModal({ record: legacyHosting });
    await wrapper
      .find('[data-testid="income-liquidate-period-cadence"]')
      .setValue('semiannual');

    await wrapper.find('[data-testid="income-liquidate-period-end"]').setValue('');

    expect(wrapper.find('[data-testid="income-liquidate-submit-reason"]').text())
      .toContain('Completa el período que cubre el cobro, o déjalo vacío.');
    expect(await submit(wrapper)).toBeUndefined();
  });

  it('flags an end that does not come after the start', async () => {
    const wrapper = mountModal({ record: legacyHosting });

    await wrapper
      .find('[data-testid="income-liquidate-period-end"]')
      .setValue('2026-09-30');

    expect(wrapper.find('[data-testid="income-liquidate-submit-reason"]').text())
      .toContain('La fecha de fin debe ser posterior a la de inicio.');
    expect(await submit(wrapper)).toBeUndefined();
  });
});
