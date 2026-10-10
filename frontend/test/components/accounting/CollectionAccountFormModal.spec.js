import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import CollectionAccountFormModal from '../../../components/accounting/CollectionAccountFormModal.vue';

jest.mock('../../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

jest.mock('@vueuse/core', () => ({
  useDebounceFn: (fn) => fn,
  onClickOutside: jest.fn(),
}));

jest.mock('../../../utils/downloadFile', () => ({
  downloadUrl: jest.fn(),
  filenameFromDisposition: jest.fn(() => ''),
}));

const { downloadUrl } = require('../../../utils/downloadFile');

const { get_request, create_request, patch_request } = require('../../../stores/services/request_http');

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: ['modelValue', 'testId'],
  emits: ['update:modelValue', 'select', 'create-new'],
  template: '<div data-testid="client-autocomplete-stub" />',
};

const IncomeFormModalStub = {
  name: 'IncomeFormModal',
  props: ['open', 'record', 'saving'],
  emits: ['close', 'submit'],
  template: '<div v-if="open" data-testid="income-form-stub" />',
};

const CollectionAccountProjectContextStub = {
  name: 'CollectionAccountProjectContext',
  props: ['projectId', 'modelValue', 'validationError'],
  emits: ['update:modelValue', 'valid', 'validation-message'],
  template: '<div data-testid="collection-account-project-context-stub"><p v-if="validationError" role="alert">{{ validationError }}</p></div>',
};

const clientFixture = {
  id: 5,
  name: 'Ana Pérez',
  company: 'Acme Soluciones',
  email: 'ana@acme.co',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
};

const incomeFixture = {
  id: 8,
  client: null,
  client_name: null,
  concept: 'Desarrollo módulo de reportes',
  kind: 'expected',
  kind_label: 'Esperado',
  total_amount: '1490000.00',
  pending_amount: '1490000.00',
  paid_amount: 0,
  has_collection_account: false,
  collection_account_number: null,
};

const linkedIncomeFixture = {
  ...incomeFixture,
  id: 9,
  concept: 'Hosting Kore renovación',
  has_collection_account: true,
  collection_account_number: 'PA-KORE-001',
};

const otherClientFixture = {
  id: 7,
  name: 'Luis Torres',
  company: 'Torrios SAS',
  email: 'luis@torrios.co',
  nit: '900111222',
  cedula: '',
  is_email_placeholder: false,
};

const clientWithoutEmailFixture = {
  ...clientFixture,
  id: 15,
  email: 'cliente_15@temp.example.com',
  is_email_placeholder: true,
};

/** Rows the incomes endpoint answers with; per-test via `mockIncomes`. */
let incomeResults = [];
const mountedWrappers = [];

function mockIncomes(rows) {
  incomeResults = rows;
}

/** The last URL the incomes endpoint was asked for. */
function lastIncomeUrl() {
  return get_request.mock.calls
    .map(([url]) => url)
    .filter((url) => url.startsWith('accounting/incomes/'))
    .at(-1);
}

function incomeUrls() {
  return get_request.mock.calls
    .map(([url]) => url)
    .filter((url) => url.startsWith('accounting/incomes/'));
}

function mockRequests() {
  incomeResults = [incomeFixture, linkedIncomeFixture];
  get_request.mockImplementation((url) => {
    const profileMatch = /client-profiles\/(\d+)\//.exec(url);
    if (profileMatch) {
      const id = Number(profileMatch[1]);
      return Promise.resolve({
        data: id === otherClientFixture.id ? otherClientFixture : clientFixture,
      });
    }
    if (url.includes('next-number')) {
      return Promise.resolve({
        data: {
          suggested_number: 'PA-ACME-003',
          billing_code: 'ACME',
          issuer_city: 'Bogotá',
        },
      });
    }
    return Promise.resolve({ data: { results: incomeResults } });
  });
  create_request.mockImplementation((url) => {
    if (url.includes('preview')) {
      return Promise.resolve({
        data: {
          subject: 'Cuenta de cobro PA-ACME-003 — ProjectApp',
          html_body: '<p>Valor a pagar</p>',
          public_number: 'PA-ACME-003',
          total: '1490000.00',
          due_date: '2026-08-13',
          customer_email: 'ana@acme.co',
          issue_date: '2026-08-05',
          customer_name: 'Acme Soluciones',
          project_name: 'Portal Acme',
          billing_concept: 'Desarrollo módulo de reportes',
          pdf_url: '/api/accounting/collection-accounts/preview/tok123/PA-ACME-003.pdf',
        },
      });
    }
    return Promise.resolve({
      data: {
        document: { id: 33, public_number: 'PA-ACME-003' },
        email_sent: true,
      },
    });
  });
  patch_request.mockResolvedValue({
    data: {
      ...clientWithoutEmailFixture,
      email: 'nuevo@acme.co',
      is_email_placeholder: false,
    },
  });
}

function mountModal(props = {}) {
  const wrapper = mount(CollectionAccountFormModal, {
    props: { open: true, ...props },
    attachTo: document.body,
    global: {
      plugins: [createPinia()],
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          name: 'BaseModal',
          props: ['modelValue', 'kind', 'fullHeight', 'closeOnEsc', 'closeOnBackdrop', 'lockScroll'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'error', 'required', 'for', 'size'],
          // The hint is rendered like the real component does: it is where a
          // field says what happens to what you type in it.
          template:
            '<div :data-invalid="error ? true : undefined"><label v-if="label">{{ label }}</label>'
            + '<slot :error-id="error ? `${label}-error` : undefined" :invalid="Boolean(error)" />'
            + '<p v-if="error" role="alert">{{ error }}</p><p v-else-if="hint">{{ hint }}</p></div>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'size', 'error', 'placeholder', 'disabled', 'min', 'max', 'maxlength', 'title'],
          emits: ['update:modelValue'],
          // min/max are rendered, not just declared: they are the native guard
          // that keeps a negative plazo out of the form.
          template:
            '<input :type="type || \'text\'" :value="modelValue" :placeholder="placeholder" :disabled="disabled" :title="title" :min="min" :max="max" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseCurrencyInput: {
          props: ['modelValue', 'decimals', 'size', 'error', 'placeholder', 'disabled', 'suggestion'],
          emits: ['update:modelValue'],
          template:
            '<input type="text" inputmode="numeric" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'rows', 'placeholder'],
          emits: ['update:modelValue'],
          template:
            '<textarea :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSegmented: {
          props: ['modelValue', 'options', 'fullWidth', 'size', 'disabled'],
          emits: ['update:modelValue'],
          // Mirrors the real control's per-option lock and selected state: the
          // income filters rely on both.
          template:
            '<div><button v-for="o in options" :key="o.value" type="button"'
            + ' :data-testid="o.testId" :disabled="disabled || o.disabled"'
            + ' :aria-selected="String(modelValue === o.value)"'
            + ' @click="!(disabled || o.disabled) && $emit(\'update:modelValue\', o.value)">'
            + '{{ o.label }}</button></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'disabled', 'type', 'iconOnly', 'loading'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
        ClientAutocomplete: ClientAutocompleteStub,
        IncomeFormModal: IncomeFormModalStub,
        CollectionAccountProjectContext: CollectionAccountProjectContextStub,
      },
    },
  });
  mountedWrappers.push(wrapper);
  return wrapper;
}

async function selectClient(wrapper, client = clientFixture) {
  const autocomplete = wrapper.findComponent(ClientAutocompleteStub);
  autocomplete.vm.$emit('update:modelValue', client.id);
  autocomplete.vm.$emit('select', client);
  await flushPromises();
}

/**
 * `useIsMobile` reads `window.matchMedia`, which jsdom does not implement — so
 * with no mock the modal stays in its desktop (two-column) branch. Call this to
 * put the component at a specific viewport width instead.
 */
function mockViewport(width) {
  window.matchMedia = jest.fn((query) => {
    const max = Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity);
    return {
      matches: width <= max,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    };
  });
}

/**
 * Whether the pane holding `testId` is collapsed by `v-show`.
 *
 * Not `isVisible()`: jsdom caches the computed style of an element that was
 * `display: none` and never refreshes it once Vue clears the inline style back
 * to '', so a pane that was toggled off and on again still reads as hidden.
 * The inline style is what `v-show` actually writes, and it is correct.
 */
function paneHidden(wrapper, testId) {
  return wrapper.find(`[data-testid="${testId}"]`)
    .element.closest('section').style.display === 'none';
}

async function goToPreview(wrapper) {
  await selectClient(wrapper);
  await wrapper.find('[data-testid="collection-form-preview"]').element.click();
  await flushPromises();
}

describe('CollectionAccountFormModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    jest.clearAllMocks();
    mockRequests();
    window.localStorage.clear();
    global.URL.createObjectURL = jest.fn(() => 'blob:preview-pdf');
    global.URL.revokeObjectURL = jest.fn();
    // The viewer probes the PDF URL before mounting the <embed>.
    global.fetch = jest.fn(() => Promise.resolve({ ok: true }));
  });

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount());
    delete window.matchMedia;
  });

  it('uses the compact form width before preview', () => {
    const wrapper = mountModal();

    expect(wrapper.findComponent({ name: 'BaseModal' }).props('kind')).toBe('form');
  });

  it('uses the workspace width for the preview step', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await goToPreview(wrapper);

    expect(wrapper.find('[data-testid="collection-preview-subject"]').exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'BaseModal' }).props('kind')).toBe('workspace');
  });

  it('prefills concept and amount from the income prop and locks the selector', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    expect(wrapper.find('[data-testid="collection-form-income-locked"]').text())
      .toContain('Desarrollo módulo de reportes');
    expect(wrapper.find('[data-testid="collection-form-income"]').exists()).toBe(false);
    expect(
      wrapper.find('[data-testid="collection-form-concept"]').element.value,
    ).toBe('Desarrollo módulo de reportes');
    expect(
      Number(wrapper.find('[data-testid="collection-form-amount"]').element.value),
    ).toBe(1490000);
  });

  // Falla si una cuenta creada después del pago vuelve a tomar el saldo cero.
  it('prefills the full income amount after the income is paid', async () => {
    const wrapper = mountModal({
      income: {
        ...incomeFixture,
        total_amount: '1000000.00',
        pending_amount: '0.00',
        paid_amount: '1000000.00',
        payment_status: 'paid',
      },
    });
    await flushPromises();

    expect(Number(wrapper.get('[data-testid="collection-form-amount"]').element.value))
      .toBe(1000000);
  });

  it('prefills the período facturado from a hosting income window', async () => {
    // The income already says what window this cuenta bills — re-typing it
    // was the gap that motivated recording the period at all.
    const wrapper = mountModal({
      income: {
        ...incomeFixture,
        period_start: '2026-08-15',
        period_end: '2027-08-14',
      },
    });
    await flushPromises();

    expect(
      wrapper.find('[data-testid="collection-form-period-start"]').element.value,
    ).toBe('2026-08-15');
    expect(
      wrapper.find('[data-testid="collection-form-period-end"]').element.value,
    ).toBe('2027-08-14');
  });

  it('leaves the período facturado empty when the income records none', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    expect(
      wrapper.find('[data-testid="collection-form-period-start"]').element.value,
    ).toBe('');
  });

  it('lists incomes and blocks the ones that already have a cuenta', async () => {
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.find('[data-testid="collection-form-income"]').trigger('focus');
    await flushPromises();

    const blocked = wrapper.find('[data-testid="collection-form-income-option-9"]');
    expect(blocked.text()).toContain('Ya tiene cuenta de cobro (PA-KORE-001)');

    await blocked.trigger('mousedown');
    expect(wrapper.find('[data-testid="collection-form-concept"]').element.value).toBe('');

    await wrapper.find('[data-testid="collection-form-income-option-8"]').trigger('mousedown');
    expect(wrapper.find('[data-testid="collection-form-concept"]').element.value)
      .toBe('Desarrollo módulo de reportes');
  });

  describe('income options scoped to the client', () => {
    const ownIncome = {
      ...incomeFixture,
      id: 11,
      client: 5,
      client_name: 'Acme Soluciones',
      concept: 'Acme - Fase 2',
    };
    const orphanIncome = {
      ...incomeFixture,
      id: 12,
      concept: 'Kore v2 (Fase 4) - Diseño 30%',
    };
    const otherClientIncome = {
      ...incomeFixture,
      id: 13,
      client: 7,
      client_name: 'Torrios SAS',
      concept: 'Torrios - Hosting anual',
    };

    async function openOptions(wrapper) {
      await wrapper.find('[data-testid="collection-form-income"]').trigger('focus');
      await flushPromises();
    }

    it('asks for every eligible income while no client is chosen', async () => {
      const wrapper = mountModal();
      await flushPromises();

      expect(lastIncomeUrl()).toContain('kind=expected%2Cliquid');
      expect(lastIncomeUrl()).not.toContain('client=');
      expect(wrapper.find('[data-testid="collection-form-income-kind-expected"]')
        .attributes('aria-selected')).toBe('true');
    });

    it('keeps a partially paid expected income in the default results', async () => {
      mockIncomes([{ ...ownIncome, payment_status: 'partial', pending_amount: '500000.00' }]);
      const wrapper = mountModal();
      await flushPromises();

      await selectClient(wrapper);
      await openOptions(wrapper);

      expect(wrapper.find('[data-testid="collection-form-income-option-11"]').exists())
        .toBe(true);
    });

    it('scopes to the chosen client without asking the server again', async () => {
      mockIncomes([ownIncome, orphanIncome, otherClientIncome]);
      const wrapper = mountModal();
      await flushPromises();

      await selectClient(wrapper);
      await openOptions(wrapper);

      // The request is the same whoever is billed: the alcance is decided here,
      // which is what makes the chip counts exact and the switch instant.
      expect(lastIncomeUrl()).not.toContain('client=');
      expect(incomeUrls()).toHaveLength(1);
      expect(wrapper.find('[data-testid="collection-form-income-option-11"]').exists())
        .toBe(true);
      expect(wrapper.find('[data-testid="collection-form-income-option-13"]').exists())
        .toBe(false);
      expect(wrapper.find('[data-testid="collection-form-income-option-12"]').exists())
        .toBe(false);
    });

    it('re-aims the list at the new client without a second request', async () => {
      mockIncomes([ownIncome, orphanIncome, otherClientIncome]);
      const wrapper = mountModal();
      await flushPromises();

      await selectClient(wrapper);
      await selectClient(wrapper, otherClientFixture);
      await openOptions(wrapper);

      expect(incomeUrls()).toHaveLength(1);
      expect(wrapper.find('[data-testid="collection-form-income-group-own"]').text())
        .toContain('De Torrios SAS (1)');
      expect(wrapper.find('[data-testid="collection-form-income-option-13"]').exists())
        .toBe(true);
      expect(wrapper.find('[data-testid="collection-form-income-option-11"]').exists())
        .toBe(false);
    });

    it('counts each alcance option and widens to the unassigned ones', async () => {
      mockIncomes([ownIncome, orphanIncome, otherClientIncome]);
      const wrapper = mountModal();
      await flushPromises();
      await selectClient(wrapper);
      await openOptions(wrapper);

      expect(wrapper.find('[data-testid="collection-form-income-scope-client"]').text())
        .toContain('Del cliente (1)');
      expect(wrapper.find('[data-testid="collection-form-income-scope-all"]').text())
        .toContain('Todos (3)');

      await wrapper.find('[data-testid="collection-form-income-scope-all"]').trigger('click');

      const orphanGroup = wrapper.find(
        '[data-testid="collection-form-income-group-orphan"]',
      );
      expect(orphanGroup.text()).toContain('Sin cliente (1)');
      expect(orphanGroup.text()).toContain('Al elegirlo se asigna a Acme Soluciones');
      expect(wrapper.find('[data-testid="collection-form-income-option-12"]').exists())
        .toBe(true);
      // The other client's row names its owner: that is the fact that decides
      // whether it can be billed here at all.
      expect(wrapper.find('[data-testid="collection-form-income-group-others"]').text())
        .toContain('De otros clientes (1)');
      expect(wrapper.find('[data-testid="collection-form-income-client-13"]').text())
        .toBe('Torrios SAS');
    });

    it('counts each estado option and filters without a request', async () => {
      mockIncomes([ownIncome, { ...ownIncome, id: 14, kind: 'liquid', kind_label: 'Líquido' }]);
      const wrapper = mountModal();
      await flushPromises();
      await selectClient(wrapper);
      await openOptions(wrapper);

      expect(wrapper.find('[data-testid="collection-form-income-kind-all"]').text())
        .toContain('Todos (2)');
      expect(wrapper.find('[data-testid="collection-form-income-kind-expected"]').text())
        .toContain('Esperados (1)');
      expect(wrapper.find('[data-testid="collection-form-income-kind-liquid"]').text())
        .toContain('Líquidos (1)');

      await wrapper.find('[data-testid="collection-form-income-kind-liquid"]').trigger('click');

      expect(wrapper.find('[data-testid="collection-form-income-option-14"]').exists())
        .toBe(true);
      expect(wrapper.find('[data-testid="collection-form-income-option-11"]').exists())
        .toBe(false);
      expect(incomeUrls()).toHaveLength(1);
    });

    it('leaves the list open when a filter is applied', async () => {
      mockIncomes([ownIncome, orphanIncome]);
      const wrapper = mountModal();
      await flushPromises();
      await selectClient(wrapper);
      await openOptions(wrapper);

      await wrapper.find('[data-testid="collection-form-income-scope-all"]').trigger('click');

      expect(wrapper.find('[role="listbox"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="collection-form-income"]').attributes('aria-expanded'))
        .toBe('true');
    });

    it('widens an empty expected result to every kind for the same client', async () => {
      mockIncomes([
        { ...ownIncome, kind: 'liquid', kind_label: 'Líquido' },
        orphanIncome,
      ]);
      const wrapper = mountModal();
      await flushPromises();
      await selectClient(wrapper);
      await openOptions(wrapper);

      const empty = wrapper.find('[data-testid="collection-form-income-empty"]');
      expect(empty.text()).toContain('Acme Soluciones no tiene ingresos esperados.');
      expect(wrapper.findAll('[data-testid^="collection-form-income-option-"]'))
        .toHaveLength(0);

      // Remove only the kind cut: the selected client's liquid income is one
      // click away, without leaking the global orphan into the list.
      const seeAll = wrapper.find('[data-testid="collection-form-income-see-all"]');
      expect(seeAll.text()).toContain('Ver todos (1)');
      await seeAll.trigger('click');

      expect(wrapper.find('[data-testid="collection-form-income-option-11"]').exists())
        .toBe(true);
      expect(wrapper.find('[data-testid="collection-form-income-option-12"]').exists())
        .toBe(false);
      expect(wrapper.find('[data-testid="collection-form-income-scope-client"]')
        .attributes('aria-selected')).toBe('true');
      expect(wrapper.find('[data-testid="collection-form-income-kind-all"]')
        .attributes('aria-selected')).toBe('true');
    });

    it('widens the scope when the client has no eligible income', async () => {
      mockIncomes([orphanIncome]);
      const wrapper = mountModal();
      await flushPromises();

      await selectClient(wrapper);
      await openOptions(wrapper);
      await wrapper.find('[data-testid="collection-form-income-see-all"]').trigger('click');

      expect(wrapper.find('[data-testid="collection-form-income-scope-all"]')
        .attributes('aria-selected')).toBe('true');
      expect(wrapper.find('[data-testid="collection-form-income-option-12"]').exists())
        .toBe(true);
    });

    it('resets alcance and estado when the client changes', async () => {
      mockIncomes([ownIncome, orphanIncome, otherClientIncome]);
      const wrapper = mountModal();
      await flushPromises();
      await selectClient(wrapper);
      await openOptions(wrapper);

      await wrapper.find('[data-testid="collection-form-income-scope-all"]').trigger('click');
      await wrapper.find('[data-testid="collection-form-income-kind-liquid"]').trigger('click');

      await selectClient(wrapper, otherClientFixture);
      await openOptions(wrapper);

      // Back to the defaults: no recorte of the previous client survives.
      expect(wrapper.find('[data-testid="collection-form-income-scope-client"]').attributes('aria-selected'))
        .toBe('true');
      expect(wrapper.find('[data-testid="collection-form-income-kind-expected"]').attributes('aria-selected'))
        .toBe('true');
      expect(wrapper.find('[data-testid="collection-form-income-option-12"]').exists())
        .toBe(false);
    });

    it('restores the expected default when the modal reopens', async () => {
      mockIncomes([ownIncome]);
      const wrapper = mountModal();
      await flushPromises();
      await openOptions(wrapper);
      await wrapper.find('[data-testid="collection-form-income-kind-all"]').trigger('click');

      await wrapper.setProps({ open: false });
      await wrapper.setProps({ open: true });
      await flushPromises();

      expect(wrapper.find('[data-testid="collection-form-income-kind-expected"]')
        .attributes('aria-selected')).toBe('true');
    });

    it("locks 'Del cliente' until a client is chosen", async () => {
      mockIncomes([ownIncome, orphanIncome, otherClientIncome]);
      const wrapper = mountModal();
      await flushPromises();
      await openOptions(wrapper);

      expect(wrapper.find('[data-testid="collection-form-income-scope-client"]').element.disabled)
        .toBe(true);
      expect(wrapper.find('[data-testid="collection-form-income-scope-all"]').attributes('aria-selected'))
        .toBe('true');
      // Nothing is scoped away yet, so the whole eligible ledger is on offer.
      expect(wrapper.findAll('[data-testid^="collection-form-income-option-"]'))
        .toHaveLength(3);
    });

    it('announces that an unassigned income will be adopted on issue', async () => {
      mockIncomes([orphanIncome]);
      const wrapper = mountModal();
      await flushPromises();
      await selectClient(wrapper);
      await openOptions(wrapper);
      await wrapper.find('[data-testid="collection-form-income-scope-all"]').trigger('click');

      await wrapper.find('[data-testid="collection-form-income-option-12"]').trigger('mousedown');
      await flushPromises();

      expect(wrapper.find('[data-testid="collection-form-income-orphan-notice"]').text())
        .toContain('al emitir quedará asignado a Acme Soluciones');
    });

    it('lists past the old eight-row cap and says how many are left out', async () => {
      mockIncomes(
        Array.from({ length: 30 }, (unused, index) => ({
          ...incomeFixture,
          id: 100 + index,
          concept: `Ingreso ${index}`,
        })),
      );
      const wrapper = mountModal();
      await flushPromises();
      await openOptions(wrapper);

      expect(
        wrapper.findAll('[data-testid^="collection-form-income-option-"]'),
      ).toHaveLength(25);
      expect(wrapper.find('[data-testid="collection-form-income-more-orphan"]').text())
        .toContain('Mostrando 25 de 30');
    });

    it('marks the income when it belongs to another client', async () => {
      mockIncomes([otherClientIncome]);
      const wrapper = mountModal();
      await flushPromises();
      await openOptions(wrapper);

      // Income first: it locks its own client, which this tab lets you undo.
      await wrapper.find('[data-testid="collection-form-income-option-13"]').trigger('mousedown');
      await flushPromises();
      await wrapper.find('[data-testid="collection-form-change-client"]').trigger('click');
      await selectClient(wrapper);

      expect(wrapper.find('[data-testid="collection-form-income-conflict"]').text())
        .toContain('Este ingreso es de Torrios SAS, no de Acme Soluciones');
      expect(wrapper.find('[data-testid="collection-form-preview"]').element.disabled)
        .toBe(false);
      await wrapper.find('[data-testid="collection-form-preview"]').element.click();
      expect(wrapper.text()).toContain('Resuelve el conflicto con el cliente del ingreso.');
      expect(create_request).not.toHaveBeenCalledWith(
        'accounting/collection-accounts/preview/',
        expect.anything(),
      );

      await wrapper.find('[data-testid="collection-form-use-income-client"]').trigger('click');
      await flushPromises();

      expect(wrapper.find('[data-testid="collection-form-income-conflict"]').exists())
        .toBe(false);
    });
  });

  it('selecting a client prefills the snapshot and the suggested consecutivo', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    await selectClient(wrapper);

    expect(get_request).toHaveBeenCalledWith(
      'accounting/collection-accounts/next-number/?client_profile_id=5',
    );
    expect(
      wrapper.find('[data-testid="collection-form-number"]').element.value,
    ).toBe('PA-ACME-003');
    expect(
      wrapper.find('[data-testid="collection-form-customer-name"]').element.value,
    ).toBe('Acme Soluciones');
    expect(
      wrapper.find('[data-testid="collection-form-customer-email"]').element.value,
    ).toBe('ana@acme.co');
    expect(
      wrapper.find('[data-testid="collection-form-customer-identification"]').element.value,
    ).toBe('901234567');
  });

  it('names the missing client and income before preview', async () => {
    // Fails if the form no longer tells the operator which two links are missing.
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="collection-form-preview"]').element.click();

    expect(wrapper.text()).toContain('Elige o crea un cliente.');
    expect(wrapper.text()).toContain('Selecciona un ingreso vinculado.');
    expect(create_request).not.toHaveBeenCalled();
  });

  it('names the missing amount and concept before preview', async () => {
    // Fails if an empty draft hides the amount or service description that must be completed.
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="collection-form-preview"]').element.click();

    expect(wrapper.text()).toContain('Ingresa un valor mayor a cero.');
    expect(wrapper.text()).toContain('Escribe el concepto del servicio.');
    expect(wrapper.find('[data-testid="collection-form-preview-gate-reasons"]').exists())
      .toBe(false);
  });

  it('warns immediately when the selected client has no real email', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    await selectClient(wrapper, clientWithoutEmailFixture);

    expect(wrapper.get('[data-testid="collection-form-client-email-warning"]').text())
      .toContain('Este cliente no tiene correo.');
    await wrapper.get('[data-testid="collection-form-preview"]').element.click();
    expect(wrapper.text()).toContain('Agrega y guarda el correo del cliente.');
    expect(wrapper.get('[data-testid="collection-form-customer-email"]').element.disabled)
      .toBe(true);
  });

  it('saves a missing client email without losing the account draft', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper, clientWithoutEmailFixture);
    await wrapper.get('[data-testid="collection-form-description"]')
      .setValue('Detalle que debe sobrevivir');
    await wrapper.get('[data-testid="collection-form-notes"]')
      .setValue('Nota que debe sobrevivir');

    await wrapper.get('[data-testid="collection-form-client-email-repair"]')
      .setValue('Nuevo@Acme.co');
    await wrapper.get('[data-testid="collection-form-client-email-save"]').trigger('click');
    await flushPromises();

    expect(patch_request).toHaveBeenCalledWith(
      'proposals/client-profiles/15/update/',
      { email: 'nuevo@acme.co' },
    );
    expect(wrapper.find('[data-testid="collection-form-client-email-warning"]').exists())
      .toBe(false);
    expect(wrapper.get('[data-testid="collection-form-customer-email"]').element.value)
      .toBe('nuevo@acme.co');
    expect(wrapper.get('[data-testid="collection-form-description"]').element.value)
      .toBe('Detalle que debe sobrevivir');
    expect(wrapper.get('[data-testid="collection-form-notes"]').element.value)
      .toBe('Nota que debe sobrevivir');
    expect(wrapper.get('[data-testid="collection-form-preview"]').element.disabled).toBe(false);
  });

  it('keeps the email repair open when validation or the API rejects it', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper, clientWithoutEmailFixture);

    await wrapper.get('[data-testid="collection-form-client-email-repair"]')
      .setValue('correo-invalido');
    await wrapper.get('[data-testid="collection-form-client-email-save"]').trigger('click');
    expect(wrapper.get('[data-testid="collection-form-client-email-error"]').text())
      .toContain('Escribe un correo válido');
    expect(patch_request).not.toHaveBeenCalled();

    patch_request.mockRejectedValueOnce({
      response: { data: { message: 'Otro usuario ya está usando ese correo.' } },
    });
    await wrapper.get('[data-testid="collection-form-client-email-repair"]')
      .setValue('duplicado@acme.co');
    await wrapper.get('[data-testid="collection-form-client-email-save"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="collection-form-client-email-error"]').text())
      .toContain('Otro usuario ya está usando ese correo.');
    expect(wrapper.get('[data-testid="collection-form-client-email-warning"]').exists())
      .toBe(true);
  });

  it('names the missing fixed payment date before preview', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    const fixed = wrapper.findAll('button')
      .find(button => button.text().includes('Fecha fija'));
    await fixed.trigger('click');

    await wrapper.get('[data-testid="collection-form-preview"]').element.click();
    expect(wrapper.text()).toContain('Selecciona la fecha fija de pago.');
    expect(wrapper.get('[data-testid="collection-form-preview"]').element.disabled)
      .toBe(false);
  });

  it('defaults an unpaid income without VAT to 19% in the preview payload', async () => {
    // Fails if a new cuenta from an unpaid income silently starts without the default VAT.
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    const [url, payload] = create_request.mock.calls.at(-1);
    expect(url).toBe('accounting/collection-accounts/preview/');
    expect(payload.public_number).toBeUndefined();
    expect(payload.client_profile_id).toBe(5);
    expect(payload.income_record_id).toBe(8);
    expect(payload.vat_rate).toBe(19);
    expect(payload.items[0]).toEqual({
      description: '',
      quantity: '1',
      amount: '1490000',
      amount_mode: 'vat_included',
      period_start: null,
      period_end: null,
    });
  });

  it('keeps an unknown VAT rate on a paid income while locking its amount', async () => {
    // Fails if opening a paid income retroactively assigns it the new 19% default.
    const wrapper = mountModal({
      income: { ...incomeFixture, kind: 'liquid', paid_amount: 120000, vat_rate: undefined },
    });
    await flushPromises();
    await selectClient(wrapper);

    expect(wrapper.get('[data-testid="collection-form-amount"]').element.disabled).toBe(true);
    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    const payload = create_request.mock.calls.at(-1)[1];
    expect(payload.vat_rate).toBeNull();
    expect(payload.items[0].amount).toBe('1490000');
  });

  it('sends a zero plazo as a real 0 rather than the default term', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    await wrapper.find('[data-testid="collection-form-term-days"]').setValue('0');
    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    // `Number(...) || 8` used to read the deliberate 0 as "empty" and bill the
    // cuenta at 8 days, so pago inmediato could not be expressed at all.
    const payload = create_request.mock.calls.at(-1)[1];
    expect(payload.payment_term_days).toBe(0);
    expect(payload.due_date).toBeUndefined();
  });

  it('still falls back to the default term when the plazo is left empty', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    await wrapper.find('[data-testid="collection-form-term-days"]').setValue('');
    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    expect(create_request.mock.calls.at(-1)[1].payment_term_days).toBe(8);
  });

  it('clamps a typed negative plazo to 0 instead of sending it to the API', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    // min="0" stops the spinner but not the keyboard; the serializer would
    // reject -5 with a 400, so the payload builder keeps it inside the bounds.
    await wrapper.find('[data-testid="collection-form-term-days"]').setValue('-5');
    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    expect(create_request.mock.calls.at(-1)[1].payment_term_days).toBe(0);
  });

  // The hint lives in the row help: a field hint inside an aligned row is
  // never rendered, which is how this copy went missing in the app.
  it('explains a zero plazo below the term row', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    expect(wrapper.get('[data-testid="collection-form-term-hint"]').text())
      .toBe('0 días = pago inmediato: la cuenta sale sin fecha de vencimiento.');
    expect(wrapper.find('[data-testid="collection-form-term-days"]').attributes('min'))
      .toBe('0');
  });

  it('drops the zero-plazo hint for a fixed date', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    expect(wrapper.find('[data-testid="collection-form-term-hint"]').exists()).toBe(true);

    // A 0 means nothing once the plazo is a date.
    await wrapper.findAll('button')
      .find((b) => b.text() === 'Fecha fija')
      .trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="collection-form-term-hint"]').exists()).toBe(false);
  });

  it('sends the long description as the detail line, not the short concept', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    const description = 'Requerimientos atendidos:\n\n- Formulario\n- Reporte';
    await wrapper.find('[data-testid="collection-form-description"]').setValue(description);
    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    const payload = create_request.mock.calls.at(-1)[1];
    // Two fields doing two jobs: the concepto heads the document, the
    // descripción fills the Descripción column of the detalle.
    expect(payload.billing_concept).toBe('Desarrollo módulo de reportes');
    expect(payload.items[0].description).toBe(description);
  });

  it('leaves the detail description empty so the backend falls back to the concept', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    // Not the concept copied client-side: the fallback lives in one place.
    expect(create_request.mock.calls.at(-1)[1].items[0].description).toBe('');
  });

  it('tells the operator the notes stay internal', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    // A field you fill that reaches nobody is worse than no field: the form
    // has to say which side of the client boundary it sits on.
    const notesField = wrapper
      .find('[data-testid="collection-form-notes"]')
      .element.closest('div');
    expect(notesField.textContent).toContain('Notas internas');
    expect(notesField.textContent).toContain('no aparecen en el PDF ni en el correo');
  });

  it('sends an edited consecutivo in the payload', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    const numberInput = wrapper.find('[data-testid="collection-form-number"]');
    await numberInput.setValue('PA-ACME-044');
    await numberInput.trigger('input');

    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    const payload = create_request.mock.calls.at(-1)[1];
    expect(payload.public_number).toBe('PA-ACME-044');
  });

  it('shows the preview and confirm sends the same payload and emits created', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    expect(wrapper.find('[data-testid="collection-preview-subject"]').text())
      .toContain('PA-ACME-003');
    const previewPayload = create_request.mock.calls.at(-1)[1];

    await wrapper.find('[data-testid="collection-form-confirm"]').trigger('click');
    await wrapper.find('[data-testid="confirm-modal-confirm"]').trigger('click');
    await flushPromises();

    const [confirmUrl, confirmPayload] = create_request.mock.calls.at(-1);
    expect(confirmUrl).toBe('accounting/collection-accounts/create/');
    expect(confirmPayload).toEqual(previewPayload);
    expect(wrapper.emitted('created')).toBeTruthy();
  });

  describe('last notice before sending', () => {
    async function openNotice(wrapper) {
      await flushPromises();
      await selectClient(wrapper);
      await wrapper.find('[data-testid="collection-form-preview"]').element.click();
      await flushPromises();
      await wrapper.find('[data-testid="collection-form-confirm"]').trigger('click');
    }

    const createCalls = () => create_request.mock.calls
      .filter(([url]) => url === 'accounting/collection-accounts/create/');
    const row = (wrapper, key) =>
      wrapper.find(`[data-testid="collection-send-notice-${key}"]`).text();

    it('names the cuenta before anything is sent', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await openNotice(wrapper);

      expect(createCalls()).toHaveLength(0);
      expect(row(wrapper, 'number')).toBe('PA-ACME-003');
      expect(row(wrapper, 'client')).toBe('Acme Soluciones');
      expect(row(wrapper, 'project')).toBe('Portal Acme');
      expect(row(wrapper, 'total')).toContain('1.490.000');
      expect(row(wrapper, 'recipient')).toBe('ana@acme.co');
    });

    it('backing out keeps the preview and sends nothing', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await openNotice(wrapper);

      const back = wrapper.findAll('button')
        .find((button) => button.text() === 'Volver a revisar');
      await back.trigger('click');
      await flushPromises();

      expect(createCalls()).toHaveLength(0);
      expect(wrapper.find('[data-testid="collection-send-notice-number"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="collection-preview-subject"]').exists()).toBe(true);
    });

    it('reads a zero-day term as no due date', async () => {
      const previewImpl = create_request.getMockImplementation();
      create_request.mockImplementation(async (url, body) => {
        const response = await previewImpl(url, body);
        if (url.includes('preview')) response.data.due_date = null;
        return response;
      });
      const wrapper = mountModal({ income: incomeFixture });
      await openNotice(wrapper);

      expect(row(wrapper, 'due')).toBe('Sin vencimiento (pago inmediato)');
    });

    it('falls back to the form when the preview names nothing new', async () => {
      const previewImpl = create_request.getMockImplementation();
      create_request.mockImplementation(async (url, body) => {
        const response = await previewImpl(url, body);
        if (url.includes('preview')) {
          const { issue_date, customer_name, project_name, billing_concept, ...older } = response.data;
          response.data = older;
        }
        return response;
      });
      const wrapper = mountModal({ income: incomeFixture });
      await openNotice(wrapper);

      expect(row(wrapper, 'issue')).toBe('Hoy');
      expect(row(wrapper, 'project')).toBe('Sin proyecto');
      expect(row(wrapper, 'concept')).toBe('Desarrollo módulo de reportes');
    });

    it('keeps Esc away from the wizard while the notice is open', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await openNotice(wrapper);

      const wizard = wrapper.findAllComponents({ name: 'BaseModal' })[0];
      expect(wizard.props('closeOnEsc')).toBe(false);
      expect(wizard.props('closeOnBackdrop')).toBe(false);
    });

    it('creates one cuenta and locks going back while it sends', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await openNotice(wrapper);
      create_request.mockImplementation((url) => (
        url.includes('preview') ? Promise.resolve({ data: {} }) : new Promise(() => {})
      ));

      await wrapper.find('[data-testid="confirm-modal-confirm"]').trigger('click');
      await wrapper.find('[data-testid="collection-form-confirm"]').trigger('click');
      await flushPromises();

      expect(createCalls()).toHaveLength(1);
      expect(wrapper.find('[data-testid="collection-form-back"]').attributes('disabled'))
        .toBeDefined();
    });
  });

  it('stays on the form when the preview request fails', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    create_request.mockImplementation((url) => {
      if (url.includes('preview')) {
        return Promise.reject({ response: { status: 500, data: {} } });
      }
      return Promise.resolve({
        data: { document: { id: 33, public_number: 'PA-ACME-003' }, email_sent: true },
      });
    });

    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    // Falls if goPreview() ever moves `step.value = 'preview'` before the
    // `!result.success` guard: the operator would see a stale/partial
    // preview instead of staying on the form with the error notification.
    expect(wrapper.find('[data-testid="collection-preview-subject"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="collection-form-concept"]').exists()).toBe(true);
  });

  it('volver a editar returns to the form keeping its state', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();
    await wrapper.find('[data-testid="collection-form-back"]').trigger('click');

    expect(
      wrapper.find('[data-testid="collection-form-concept"]').element.value,
    ).toBe('Desarrollo módulo de reportes');
    expect(
      wrapper.find('[data-testid="collection-form-number"]').element.value,
    ).toBe('PA-ACME-003');
  });

  it('preloads and locks the client when the income already carries one', async () => {
    const wrapper = mountModal({
      income: { ...incomeFixture, client: 5, client_name: 'Acme Soluciones' },
    });
    await flushPromises();

    // No second ask: the picker is replaced by a locked display...
    expect(wrapper.find('[data-testid="collection-form-client-locked"]').text())
      .toContain('Acme Soluciones');
    expect(wrapper.findComponent(ClientAutocompleteStub).exists()).toBe(false);
    // ...and the snapshot + suggested consecutivo arrived on their own.
    expect(get_request).toHaveBeenCalledWith('proposals/client-profiles/5/');
    expect(
      wrapper.find('[data-testid="collection-form-customer-email"]').element.value,
    ).toBe('ana@acme.co');
    expect(
      wrapper.find('[data-testid="collection-form-number"]').element.value,
    ).toBe('PA-ACME-003');

    await wrapper.find('[data-testid="collection-form-preview"]').element.click();
    await flushPromises();

    expect(create_request.mock.calls.at(-1)[1].client_profile_id).toBe(5);
  });

  it('keeps the suggested consecutivo while a saved client projection refreshes the document snapshot', async () => {
    // Fails if saving the client sheet leaves the document using stale address or identification data.
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();
    await selectClient(wrapper);

    patch_request.mockResolvedValueOnce({
      data: {
        ...clientFixture,
        address: 'Carrera 7 # 72-41',
        billing_customer: {
          name: 'Acme Soluciones SAS',
          identification_type: 'NIT',
          identification: '901234567-8',
          email: 'facturacion@acme.co',
          contact_name: 'Ana Pérez',
          address: 'Carrera 7 # 72-41',
        },
      },
    });
    await wrapper.get('[data-testid="collection-form-edit-client"]').trigger('click');
    await wrapper.get('[data-testid="collection-form-client-edit-address"]')
      .setValue('Carrera 7 # 72-41');
    await wrapper.get('[data-testid="collection-form-client-edit-save"]').trigger('click');
    await flushPromises();

    expect(patch_request).toHaveBeenCalledWith('proposals/client-profiles/5/update/', {
      name: 'Ana Pérez',
      email: 'ana@acme.co',
      phone: '',
      company: 'Acme Soluciones',
      nit: '901234567',
      cedula: '',
      address: 'Carrera 7 # 72-41',
      billing_code: '',
    });
    expect(wrapper.get('[data-testid="collection-form-customer-identification"]').element.value)
      .toBe('901234567-8');
    expect(wrapper.get('[data-testid="collection-form-customer-address"]').element.value)
      .toBe('Carrera 7 # 72-41');
    expect(wrapper.get('[data-testid="collection-form-number"]').element.value).toBe('PA-ACME-003');
  });

  it('shows the project context message before a preview request', async () => {
    // Fails if accounts opened from project income hide the actionable context error.
    const wrapper = mountModal({ income: { ...incomeFixture, project: 14 } });
    await flushPromises();
    await selectClient(wrapper);

    const context = wrapper.findComponent(CollectionAccountProjectContextStub);
    expect(context.props('projectId')).toBe(14);
    context.vm.$emit('valid', false);
    context.vm.$emit('validation-message', 'En «Cobro del proyecto», elige si cobras un contrato o el hosting.');
    await flushPromises();
    await wrapper.get('[data-testid="collection-form-preview"]').trigger('click');

    expect(wrapper.text()).toContain('En «Cobro del proyecto», elige si cobras un contrato o el hosting.');
    expect(create_request).not.toHaveBeenCalled();
  });

  it('create-new client opens the inline form and links the created profile', async () => {
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', 'Nuevo SAS');
    await flushPromises();

    const inline = wrapper.find('[data-testid="collection-form-inline-client"]');
    expect(inline.exists()).toBe(true);
    expect(
      wrapper.find('[data-testid="collection-form-inline-client-name"]').element.value,
    ).toBe('Nuevo SAS');

    create_request.mockResolvedValueOnce({
      data: { ...clientFixture, id: 12, name: 'Nuevo SAS', company: '' },
    });
    await wrapper.find('[data-testid="collection-form-inline-client-save"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith(
      'proposals/client-profiles/create/',
      expect.objectContaining({ name: 'Nuevo SAS' }),
    );
  });

  it('files the billing identity from the inline form, not just the name', async () => {
    // A cuenta de cobro needs the NIT for the customer snapshot and the código
    // for the consecutivo. The inline form used to ask for neither, so a client
    // created here came out incomplete and the código got auto-derived.
    const wrapper = mountModal({ income: incomeFixture });
    await flushPromises();

    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', 'G&M');
    await flushPromises();

    await wrapper
      .find('[data-testid="collection-form-inline-client-nit"]')
      .setValue('901234567-1');
    await wrapper
      .find('[data-testid="collection-form-inline-client-billing-code"]')
      .setValue('g&m');

    create_request.mockResolvedValueOnce({
      data: { ...clientFixture, id: 13, name: 'G&M', nit: '901234567-1' },
    });
    await wrapper.find('[data-testid="collection-form-inline-client-save"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith(
      'proposals/client-profiles/create/',
      expect.objectContaining({
        name: 'G&M',
        nit: '901234567-1',
        billing_code: 'G&M',
      }),
    );
    expect(wrapper.find('[data-testid="collection-form-inline-client"]').exists()).toBe(false);
    expect(
      wrapper.find('[data-testid="collection-form-number"]').element.value,
    ).toBe('PA-ACME-003');
  });

  describe('preview layout', () => {
    it('shows the email and the PDF side by side on wide screens', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      // The whole point of the review step: both pieces readable at once,
      // instead of the old stack where only one fit on screen.
      expect(paneHidden(wrapper, 'collection-preview-email')).toBe(false);
      expect(paneHidden(wrapper, 'collection-preview-pdf')).toBe(false);
      expect(wrapper.find('[data-testid="collection-preview-split-handle"]').exists()).toBe(true);
      // No tabs while both panes fit.
      expect(wrapper.find('[data-testid="collection-preview-tab-pdf"]').exists()).toBe(false);
    });

    it('embeds and opens the served PDF URL instead of a blob', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      const url = '/api/accounting/collection-accounts/preview/tok123/PA-ACME-003.pdf';
      // A blob: URL carries no filename, so Chrome's viewer named its download
      // (and its "Save to Drive") after the blob's UUID. A served URL ending in
      // the consecutivo, with the filename in Content-Disposition, does not.
      expect(wrapper.find('[data-testid="collection-preview-pdf"]').attributes('src'))
        .toBe(url);
      expect(global.URL.createObjectURL).not.toHaveBeenCalled();

      window.open = jest.fn();
      await wrapper.find('[data-testid="collection-preview-open-pdf"]').trigger('click');
      expect(window.open).toHaveBeenCalledWith(url, '_blank', 'noopener');
    });

    it('falls back to its own message, keeping the download exits, when the viewer fails', async () => {
      // The browser's connection-refused page inside the frame explains
      // nothing; the panel says what happened and where to review instead.
      global.fetch = jest.fn(() => Promise.reject(new Error('refused')));
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      expect(wrapper.find('[data-testid="collection-preview-pdf"]').exists()).toBe(false);
      expect(wrapper.get('[data-testid="collection-preview-pdf-error"]').text())
        .toContain('No pudimos mostrar la previsualización');
      expect(wrapper.find('[data-testid="collection-preview-download-pdf"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="collection-preview-open-pdf"]').exists()).toBe(true);
    });

    it('gives the PDF the wider column by default', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      const handle = wrapper.find('[data-testid="collection-preview-split-handle"]');
      expect(handle.element.parentElement.getAttribute('style'))
        .toContain('grid-template-columns: 40% 1rem minmax(0, 1fr)');
    });

    it('collapses into tabs below 1024px, landing on the email', async () => {
      mockViewport(800);
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      expect(wrapper.find('[data-testid="collection-preview-split-handle"]').exists()).toBe(false);
      expect(paneHidden(wrapper, 'collection-preview-email')).toBe(false);
      expect(paneHidden(wrapper, 'collection-preview-pdf')).toBe(true);

      await wrapper.find('[data-testid="collection-preview-tab-pdf"]').trigger('click');

      expect(paneHidden(wrapper, 'collection-preview-pdf')).toBe(false);
      expect(paneHidden(wrapper, 'collection-preview-email')).toBe(true);
    });

    it('lands on the PDF tab on a phone, where the document is what needs checking', async () => {
      mockViewport(400);
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      expect(paneHidden(wrapper, 'collection-preview-pdf')).toBe(false);
      expect(paneHidden(wrapper, 'collection-preview-email')).toBe(true);
      // Opening the document full size stays available on every layout.
      expect(wrapper.find('[data-testid="collection-preview-open-pdf"]').exists()).toBe(true);
    });

    it('clamps the dragged divider and remembers where it was left', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      const handle = wrapper.find('[data-testid="collection-preview-split-handle"]');
      handle.element.parentElement.getBoundingClientRect = () => ({
        left: 0, top: 0, width: 1000, height: 500, right: 1000, bottom: 500,
      });

      await handle.trigger('pointerdown', { pointerId: 1 });
      // Dragged to 90%: past the cap, so the PDF keeps a legible column.
      await handle.trigger('pointermove', { clientX: 900 });
      await handle.trigger('pointerup', { pointerId: 1 });

      expect(handle.element.parentElement.getAttribute('style'))
        .toContain('grid-template-columns: 60% 1rem minmax(0, 1fr)');
      expect(window.localStorage.getItem('projectapp-collection-preview-split')).toBe('60');
    });

    it('restores the stored divider position on the next preview', async () => {
      window.localStorage.setItem('projectapp-collection-preview-split', '55');

      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      const handle = wrapper.find('[data-testid="collection-preview-split-handle"]');
      expect(handle.element.parentElement.getAttribute('style'))
        .toContain('grid-template-columns: 55% 1rem minmax(0, 1fr)');
    });

    it('downloads the preview PDF under the consecutivo, not as untitled', async () => {
      const wrapper = mountModal({ income: incomeFixture });
      await flushPromises();
      await goToPreview(wrapper);

      await wrapper.find('[data-testid="collection-preview-download-pdf"]').trigger('click');

      // Downloaded from the served URL under an explicit name: the same bytes
      // the embedded viewer shows, so both save PA-ACME-003.pdf.
      expect(downloadUrl.mock.calls.at(-1)).toEqual([
        '/api/accounting/collection-accounts/preview/tok123/PA-ACME-003.pdf',
        'PA-ACME-003.pdf',
      ]);
    });
  });
});
