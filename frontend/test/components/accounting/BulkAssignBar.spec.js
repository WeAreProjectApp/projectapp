import { mount, flushPromises } from '@vue/test-utils';

// Mock Headless UI the way BaseDropdown.spec does: the stubbed MenuItems
// renders unconditionally, so the actions are queryable without driving the
// focus machinery — while the REAL BaseDropdown still maps our items, so the
// danger class, the disabled attribute and the reason line stay under test.
jest.mock('@headlessui/vue', () => ({
  Menu: { name: 'Menu', props: ['as'], template: '<div class="hl-menu"><slot /></div>' },
  MenuButton: {
    name: 'MenuButton',
    props: ['as'],
    template: '<div class="hl-menu-button"><slot /></div>',
  },
  MenuItems: { name: 'MenuItems', template: '<div class="hl-menu-items"><slot /></div>' },
  MenuItem: {
    name: 'MenuItem',
    props: ['disabled'],
    template: '<div class="hl-menu-item"><slot :active="false" :disabled="disabled || false" /></div>',
  },
}));

import BulkAssignBar from '../../../components/accounting/BulkAssignBar.vue';

const NuxtLink = {
  name: 'NuxtLink',
  props: ['to'],
  template: '<a class="nuxt-link"><slot /></a>',
};

const BulkAssignModalStub = {
  name: 'BulkAssignModal',
  props: ['open', 'target', 'rows', 'selectedIds', 'entity', 'recordLabel', 'testidPrefix', 'busy'],
  emits: ['close', 'submit'],
  template: '<div v-if="open" data-testid="assign-modal-stub">{{ target }}</div>',
};

const ENTITY = { singular: 'hosting', plural: 'hostings' };

const ROWS = [
  { id: 1, client: null, project: null, client_name: 'Kore - Marca', domain_url: 'kore.com.co' },
  { id: 2, client: null, project: null, client_name: 'Huella - Marca', domain_url: 'tuhuella.co' },
  { id: 3, client: 7, project: null, client_display_name: 'Kore SAS', domain_url: 'a.com' },
  {
    id: 4,
    client: 7,
    project: 41,
    project_name: 'Vieja Web',
    client_display_name: 'Kore SAS',
    domain_url: 'b.com',
  },
];

function mountBar(props = {}) {
  return mount(BulkAssignBar, {
    props: {
      rows: ROWS,
      selected: [1, 2],
      filteredIds: [1, 2, 3],
      entity: ENTITY,
      testidPrefix: 'hostings',
      recordLabel: (row) => row.domain_url,
      ...props,
    },
    global: {
      components: { NuxtLink },
      stubs: {
        BulkAssignModal: BulkAssignModalStub,
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          template: '<div v-if="modelValue" data-testid="modal"><slot /><slot name="footer" /></div>',
        },
      },
    },
  });
}

/** The menu's actions, as the operator reads them. */
const actionLabels = (wrapper) => wrapper
  .findAll('.hl-menu-item')
  .map((item) => item.text());

const action = (wrapper, label) => wrapper
  .findAll('.hl-menu-item')
  .find((item) => item.text().includes(label));

/** Whether the menu offers `label` at all. */
const offers = (wrapper, label) => Boolean(action(wrapper, label));

async function runAction(wrapper, label) {
  await action(wrapper, label).find('button').trigger('click');
  await flushPromises();
}

async function confirm(wrapper) {
  await wrapper.find('[data-testid="confirm-modal-confirm"]').trigger('click');
  await flushPromises();
}

describe('BulkAssignBar — one control, and what hangs off it', () => {
  it('collapses the whole bar into a count and a single actions trigger', () => {
    const wrapper = mountBar();

    expect(wrapper.find('[data-testid="hostings-bulk-bar"]').text())
      .toContain('2 seleccionados');
    expect(wrapper.find('[data-testid="hostings-bulk-actions"]').exists()).toBe(true);
    // Nothing else is laid out: the picker and the four action buttons moved.
    expect(wrapper.find('[data-testid="hostings-bulk-target"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="hostings-bulk-client"]').exists()).toBe(false);
  });

  it('shuts the trigger while a mutation is in flight', () => {
    const wrapper = mountBar({ busy: true });

    expect(wrapper.find('[data-testid="hostings-bulk-actions"]').element.disabled)
      .toBe(true);
  });

  it('opens the assign modal on the target the chosen action names', async () => {
    const wrapper = mountBar({ projectEnabled: true });
    expect(wrapper.find('[data-testid="assign-modal-stub"]').exists()).toBe(false);

    await runAction(wrapper, 'Asignar proyecto');

    expect(wrapper.find('[data-testid="assign-modal-stub"]').text()).toBe('project');
  });

  it('routes what the modal submits to the emit its target belongs to', async () => {
    const wrapper = mountBar({ projectEnabled: true });
    const modal = wrapper.findComponent(BulkAssignModalStub);

    await modal.vm.$emit('submit', { ids: [1], client: 5, mode: 'assign', plan: {} });
    await modal.vm.$emit('submit', { ids: [3], project: 40, mode: 'assign', plan: {} });

    expect(wrapper.emitted('submit')[0][0].client).toBe(5);
    expect(wrapper.emitted('submit-project')[0][0].project).toBe(40);
  });
});

describe('BulkAssignBar — the menu only offers what the selection allows', () => {
  it('hides Desvincular when nothing selected has a client to lose', () => {
    const wrapper = mountBar({ selected: [1, 2] });

    expect(offers(wrapper, 'Desvincular cliente')).toBe(false);
    expect(offers(wrapper, 'Asignar cliente')).toBe(true);
  });

  it('shows Desvincular as soon as a selected row is linked', () => {
    const wrapper = mountBar({ selected: [1, 3] });

    expect(offers(wrapper, 'Desvincular cliente')).toBe(true);
  });

  it('paints Desvincular as the destructive action it is', () => {
    const wrapper = mountBar({ selected: [1, 3] });

    expect(action(wrapper, 'Desvincular cliente').find('button').classes())
      .toContain('text-danger-strong');
  });

  it('offers the project actions only where the page enables them', () => {
    expect(offers(mountBar(), 'Asignar proyecto')).toBe(false);
    expect(offers(mountBar({ projectEnabled: true }), 'Asignar proyecto')).toBe(true);
  });

  it('offers Quitar proyecto only when the selection has one to lose', () => {
    const withProject = mountBar({ projectEnabled: true, selected: [4] });
    const without = mountBar({ projectEnabled: true, selected: [3] });

    expect(offers(withProject, 'Quitar proyecto')).toBe(true);
    expect(offers(without, 'Quitar proyecto')).toBe(false);
  });

  it('never renders a divider with nothing under it', () => {
    // Hostings enables projects but NOT the abono, and this selection has
    // nothing to unlink — so the menu is two entries and no separators.
    const wrapper = mountBar({ projectEnabled: true, selected: [1, 2] });

    expect(actionLabels(wrapper)).toEqual(['Asignar cliente', 'Asignar proyecto']);
    expect(wrapper.findAll('.border-t.border-border-muted')).toHaveLength(0);
  });
});

describe('BulkAssignBar — nothing runs without confirmation', () => {
  it('names the client the rows are being taken from before unlinking', async () => {
    const wrapper = mountBar({ selected: [1, 3] });

    await runAction(wrapper, 'Desvincular cliente');

    expect(wrapper.find('[data-testid="modal"]').text())
      .toContain('1 hosting quedará sin cliente: 1 de Kore SAS.');
    // Singular breakdown: a single row does not read as "1 quedan".
    expect(wrapper.find('[data-testid="client-bulk-summary-unlink"]').text())
      .toBe('1 queda sin cliente');
    expect(wrapper.find('[data-testid="client-bulk-summary-unchanged"]').text())
      .toBe('1 sin cambios');

    await confirm(wrapper);

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      ids: [3],
      client: null,
      mode: 'unlink',
    });
  });

  it('emits nothing when the confirmation is cancelled', async () => {
    const wrapper = mountBar({ selected: [1, 3] });

    await runAction(wrapper, 'Desvincular cliente');
    await wrapper.findAll('button').find((b) => b.text() === 'Cancelar').trigger('click');
    await flushPromises();

    expect(wrapper.emitted('submit') ?? []).toHaveLength(0);
    // Backing out leaves the selection exactly where it was, ready to retry.
    expect(wrapper.find('[data-testid="hostings-bulk-bar"]').text())
      .toContain('2 seleccionados');
  });

  it('clears the project of the rows that have one, and only those', async () => {
    const wrapper = mountBar({ projectEnabled: true, selected: [3, 4] });

    await runAction(wrapper, 'Quitar proyecto');
    await confirm(wrapper);

    expect(wrapper.emitted('submit-project')[0][0]).toMatchObject({
      ids: [4],
      project: null,
      mode: 'unlink',
    });
  });
});

describe('BulkAssignBar — selection plumbing', () => {
  it('hands the parent every filtered id when asked to select them all', async () => {
    const wrapper = mountBar();

    await wrapper.find('[data-testid="hostings-select-all-filtered"]').trigger('click');

    expect(wrapper.emitted('update:selected')[0][0]).toEqual([1, 2, 3]);
  });

  it('drops the offer once everything filtered is already selected', () => {
    const wrapper = mountBar({ selected: [1, 2, 3] });

    expect(wrapper.find('[data-testid="hostings-select-all-filtered"]').exists())
      .toBe(false);
  });

  it('flags the selected rows the active filter no longer shows', () => {
    const wrapper = mountBar({ selected: [1, 4], filteredIds: [1, 2, 3] });

    expect(wrapper.find('[data-testid="hostings-bulk-outside"]').text())
      .toContain('1 fuera del filtro actual');
  });

  it('says nothing about the filter while the whole selection passes it', () => {
    const wrapper = mountBar({ selected: [1, 2], filteredIds: [1, 2, 3] });

    expect(wrapper.find('[data-testid="hostings-bulk-outside"]').exists()).toBe(false);
  });

  it('hands back an empty selection when cancelled', async () => {
    const wrapper = mountBar();

    await wrapper.findAll('button').find((b) => b.text() === 'Cancelar').trigger('click');

    expect(wrapper.emitted('update:selected')[0][0]).toEqual([]);
  });
});

describe('BulkAssignBar — a deleted record is not a filtered one', () => {
  it('counts only what the page still holds once the deleted id is pruned', () => {
    const wrapper = mountBar({ selected: [1, 2], rows: ROWS.slice(0, 2) });

    expect(wrapper.find('[data-testid="hostings-bulk-bar"]').text())
      .toContain('2 seleccionados');
  });

  it('leaves on its own when the pruning empties the selection', async () => {
    const wrapper = mountBar();

    await wrapper.setProps({ selected: [] });

    expect(wrapper.find('[data-testid="hostings-bulk-bar"]').exists()).toBe(false);
  });

  it('keeps a still-existing row that the filter hides, and says so', () => {
    const wrapper = mountBar({ selected: [4], filteredIds: [1, 2, 3] });

    expect(wrapper.find('[data-testid="hostings-bulk-outside"]').text())
      .toContain('1 fuera del filtro actual');
    expect(wrapper.find('[data-testid="hostings-bulk-bar"]').text())
      .toContain('1 seleccionado');
  });

  it('leaves a stale id out of the payload it submits', async () => {
    // id 9 was deleted elsewhere; the plan resolves ids against `rows`.
    const wrapper = mountBar({ selected: [3, 9] });

    await runAction(wrapper, 'Desvincular cliente');
    await confirm(wrapper);

    expect(wrapper.emitted('submit')[0][0].ids).toEqual([3]);
  });
});

describe('BulkAssignBar — Liquidar behind settleEnabled', () => {
  const INCOME_ROWS = [
    {
      id: 11, kind: 'expected', ledger: 'company',
      total_amount: '800000.00', pending_amount: '500000.00', client: 5, concept: 'Kore - Fase 2',
      collection_account_status: 'issued',
    },
    {
      id: 12, kind: 'expected', ledger: 'company',
      total_amount: '300000.00', pending_amount: '0.00', client: 5, concept: 'Kore - Fase 1',
    },
    {
      id: 13, kind: 'liquid', ledger: 'company',
      total_amount: '200000.00', pending_amount: null, client: 5, concept: 'Kore - abono',
    },
  ];

  function mountIncomes(props = {}) {
    return mountBar({
      rows: INCOME_ROWS,
      selected: [11, 12],
      filteredIds: [11, 12, 13],
      entity: { singular: 'ingreso', plural: 'ingresos' },
      testidPrefix: 'incomes',
      recordLabel: (row) => row.concept,
      settleEnabled: true,
      ...props,
    });
  }

  it('offers the action only behind the prop, so Hostings stays untouched', () => {
    expect(offers(mountIncomes(), 'Liquidar')).toBe(true);
    expect(offers(mountBar(), 'Liquidar')).toBe(false);
  });

  // Falla si el resumen vuelve a mostrar el saldo como si fuera el valor original.
  test.each([
    [[11], 'Valor total seleccionado: $800.000 COP', 'Saldo pendiente seleccionado: $500.000 COP'],
    [[11, 12, 13], 'Valor total seleccionado: $1.300.000 COP', 'Saldo pendiente seleccionado: $500.000 COP'],
  ])('shows the selected money summary for ids %o', (selected, total, pending) => {
    const wrapper = mountIncomes({ selected });

    expect(wrapper.get('[data-testid="incomes-selected-total"]').text())
      .toBe(total);
    expect(wrapper.get('[data-testid="incomes-selected-pending"]').text())
      .toBe(pending);
  });

  it('emits the settlement eligibility summary', async () => {
    const wrapper = mountIncomes({ selected: [11, 12, 13] });

    await runAction(wrapper, 'Liquidar');

    expect(wrapper.emitted('submit-settle')[0][0]).toEqual({
      ids: [11],
      excludedCount: 2,
    });
  });

  it('goes dead with its reason on the item when nothing can take an abono', () => {
    const wrapper = mountIncomes({ selected: [12, 13] });
    const item = action(wrapper, 'Liquidar');

    expect(item.find('button').element.disabled).toBe(true);
    // The reason rides on the item itself: a disabled Headless UI MenuItem
    // takes no focus and swallows the pointer, so a tooltip is unreachable.
    expect(item.text()).toContain('Para liquidar se necesitan ingresos esperados de la empresa con saldo pendiente.');
  });

  // Falla si la acción deja de enviar una fila válida sólo porque su cuenta está en borrador.
  it('emits a settlement request for a draft collection account', async () => {
    const wrapper = mountIncomes({
      rows: [{ ...INCOME_ROWS[0], collection_account_status: 'draft' }],
      selected: [11],
    });

    await runAction(wrapper, 'Liquidar');

    expect(wrapper.emitted('submit-settle')[0][0]).toEqual({
      ids: [11],
      excludedCount: 0,
    });
  });
});
