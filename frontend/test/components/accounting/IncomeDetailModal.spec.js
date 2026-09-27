import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import IncomeDetailModal from '~/components/accounting/IncomeDetailModal.vue';
import { get_request } from '~/stores/services/request_http';

jest.mock('../../../stores/services/request_http', () => ({
  get_request: jest.fn(),
}));

/**
 * One income, read-only. Beyond the amounts, the load-bearing behaviour is
 * the settlement history: which pocket movement paid each line, and — when
 * that movement was an abono shared with other incomes — the reparto with
 * its siblings, which until now could only be read from the pocket side.
 */

const SHARED_MOVEMENT = {
  id: 90,
  concept: 'Abono Kore',
  movement_date: '2026-08-15',
  amount: '800000.00',
  is_shared: true,
  allocation_count: 3,
  allocations: [
    { income_id: 21, concept: 'Kore - Fase 2', amount: '500000.00' },
    { income_id: 22, concept: 'Kore - Fase 3 Inicio', amount: '200000.00' },
    { income_id: 23, concept: 'Kore - Fase 3 Diseño', amount: '100000.00' },
  ],
};

const OWN_MOVEMENT = {
  id: 91,
  concept: 'Transferencia Bancolombia',
  movement_date: '2026-09-01',
  amount: '150000.00',
  is_shared: false,
  allocation_count: 1,
  allocations: [{ income_id: 25, concept: 'Kore - Fase 2', amount: '150000.00' }],
};

function detail(overrides = {}) {
  return {
    income: {
      id: 11,
      concept: 'Kore - Fase 2',
      kind: 'expected',
      ledger: 'company',
      client_name: 'Kore SAS',
      project_name: 'Kore Web',
      period_label: 'Agosto 2026',
      period_date: '2026-08-01',
      total_amount: '900000.00',
      paid_amount: '650000.00',
      pending_amount: '250000.00',
      payment_status: 'partial',
      payment_status_label: 'Parcial',
      is_receivable_candidate: false,
      collection_confidence: '',
      ...(overrides.income || {}),
    },
    liquid: overrides.liquid ?? [
      {
        id: 21,
        concept: 'Kore - Fase 2',
        total_amount: '500000.00',
        period_date: '2026-08-15',
        movement: SHARED_MOVEMENT,
      },
      {
        id: 25,
        concept: 'Kore - Fase 2 saldo',
        total_amount: '150000.00',
        period_date: '2026-09-01',
        movement: OWN_MOVEMENT,
      },
    ],
    expenses: overrides.expenses ?? [],
    collection_account: overrides.collection_account ?? null,
  };
}

function mountModal(props = {}) {
  return mount(IncomeDetailModal, {
    props: { open: true, incomeId: 11, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          name: 'BaseModal',
          // closeOnEsc/closeOnBackdrop declared so the stacking guard is
          // readable back out as a prop.
          props: ['modelValue', 'size', 'titleId', 'closeOnEsc', 'closeOnBackdrop'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'disabled'],
          emits: ['click'],
          template: '<button type="button" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        IncomePaymentStateCell: {
          props: ['row'],
          template: '<span>{{ row.payment_status_label }}</span>',
        },
      },
    },
  });
}

async function open(props = {}) {
  const wrapper = mountModal(props);
  await flushPromises();
  return wrapper;
}

const historyRows = (w) => w.findAll('[data-testid="income-detail-settlement-row"]');
const repartoRows = (w) => w.findAll('[data-testid="pocket-allocation-row"]');

beforeEach(() => {
  setActivePinia(createPinia());
  get_request.mockReset();
  get_request.mockResolvedValue({ data: detail() });
});

describe('IncomeDetailModal — the income and what it was paid', () => {
  it('fetches the detail on open and heads it with the income identity', async () => {
    const wrapper = await open();

    expect(get_request).toHaveBeenCalledWith('accounting/incomes/11/detail/');
    expect(wrapper.find('[data-testid="income-detail-modal"]').text()).toContain('Kore - Fase 2');
    expect(wrapper.text()).toContain('Kore SAS');
    expect(wrapper.text()).toContain('Kore Web');
  });

  it('shows the three figures the payment state is derived from', async () => {
    const wrapper = await open();

    expect(wrapper.find('[data-testid="income-detail-total"]').text()).toContain('900.000');
    expect(wrapper.text()).toContain('650.000');
    expect(wrapper.text()).toContain('250.000');
  });

  it('shows the forecast classification with its manual inclusion state', async () => {
    get_request.mockResolvedValue({
      data: detail({
        income: {
          is_receivable_candidate: true,
          collection_confidence: 'high',
        },
      }),
    });

    const wrapper = await open();

    const forecast = wrapper.get('[data-testid="income-detail-receivable"]');
    expect(forecast.text()).toContain('Cobro muy probable');
    expect(forecast.text()).toContain('Incluido en la previsión');
    expect(forecast.get('[data-testid="receivable-confidence-dot"]').classes())
      .toContain('bg-success-strong');
  });

  it('merges liquid children and deductions into one history, oldest first', async () => {
    get_request.mockResolvedValue({
      data: detail({
        expenses: [{
          id: 60,
          concept: 'Retención en la fuente',
          total_amount: '90000.00',
          period_date: '2026-08-20',
          deduction_type_label: 'Retención',
        }],
      }),
    });
    const wrapper = await open();

    const texts = historyRows(wrapper).map((row) => row.text());
    expect(texts).toHaveLength(3);
    expect(texts[0]).toContain('Kore - Fase 2');
    expect(texts[1]).toContain('Retención en la fuente');
    expect(texts[2]).toContain('Kore - Fase 2 saldo');
  });

  it('says so plainly when nothing has been settled yet', async () => {
    get_request.mockResolvedValue({ data: detail({ liquid: [], expenses: [] }) });
    const wrapper = await open();

    expect(wrapper.find('[data-testid="income-detail-settlements-empty"]').text())
      .toContain('Sin liquidaciones registradas.');
    expect(historyRows(wrapper)).toHaveLength(0);
  });
});

describe('IncomeDetailModal — which movement paid each line', () => {
  it('labels an abono child Abono while the ordinary one stays Liquidación', async () => {
    const wrapper = await open();
    const texts = historyRows(wrapper).map((row) => row.text());

    expect(texts[0]).toContain('Abono');
    expect(texts[1]).toContain('Liquidación');
  });

  it('offers the reparto only on the shared movement, naming the other plainly', async () => {
    const wrapper = await open();

    expect(wrapper.find('[data-testid="income-detail-movement-21"]').text())
      .toContain('Abono · 3 ingresos');
    // The 1:1 movement has nothing to open, so it is named as text.
    expect(wrapper.find('[data-testid="income-detail-movement-25"]').text())
      .toContain('Transferencia Bancolombia');
    expect(wrapper.find('[data-testid="income-detail-movement-25"]').element.tagName)
      .toBe('SPAN');
  });

  it('opens the reparto with the siblings this income cannot otherwise see', async () => {
    const wrapper = await open();
    expect(repartoRows(wrapper)).toHaveLength(0);

    await wrapper.find('[data-testid="income-detail-movement-21"]').trigger('click');

    expect(repartoRows(wrapper)).toHaveLength(3);
    // "Fase 3 Inicio" is paid by the same transfer but belongs to another
    // income — it appears nowhere in this income's own history.
    const reparto = wrapper.find('[data-testid="pocket-allocations-modal"]').text();
    expect(reparto).toContain('Kore - Fase 3 Inicio');
    expect(wrapper.find('[data-testid="pocket-allocations-total"]').text())
      .toContain('800.000');
  });

  it('stops answering Esc and the backdrop while the reparto sits on top', async () => {
    const wrapper = await open();
    // The detail's own modal is the first one in the template; the reparto
    // mounts after it.
    const outer = () => wrapper.findAllComponents({ name: 'BaseModal' })[0];
    expect(outer().props('closeOnEsc')).toBe(true);

    await wrapper.find('[data-testid="income-detail-movement-21"]').trigger('click');
    expect(outer().props('closeOnEsc')).toBe(false);
    expect(outer().props('closeOnBackdrop')).toBe(false);
  });

  it('marks a settlement that never passed through the pocket', async () => {
    get_request.mockResolvedValue({
      data: detail({
        liquid: [{
          id: 30,
          concept: 'Liquidación a socios',
          total_amount: '400000.00',
          period_date: '2026-08-10',
          movement: null,
        }],
      }),
    });
    const wrapper = await open();

    const row = historyRows(wrapper)[0];
    expect(row.text()).toContain('—');
    expect(row.text()).toContain('400.000');
    expect(wrapper.find('[data-testid="income-detail-movement-30"]').exists()).toBe(false);
  });
});

describe('IncomeDetailModal — the edges', () => {
  it('surfaces a failed load instead of an empty history', async () => {
    get_request.mockRejectedValue(new Error('boom'));
    const wrapper = await open();

    expect(wrapper.find('[data-testid="income-detail-error"]').text())
      .toContain('No se pudo cargar el ingreso.');
    expect(historyRows(wrapper)).toHaveLength(0);
  });

  it('waits for the modal to be opened before fetching anything', async () => {
    const wrapper = mountModal({ open: false });
    await flushPromises();
    expect(get_request).not.toHaveBeenCalled();

    await wrapper.setProps({ open: true });
    await flushPromises();

    expect(get_request).toHaveBeenCalledWith('accounting/incomes/11/detail/');
    expect(wrapper.text()).toContain('Kore - Fase 2');
  });

  it('hands the income back when Duplicar is pressed', async () => {
    const wrapper = await open();

    await wrapper.find('[data-testid="income-detail-duplicate"]').trigger('click');

    expect(wrapper.emitted('duplicate')).toHaveLength(1);
    expect(wrapper.emitted('duplicate')[0][0].id).toBe(11);
  });
});
