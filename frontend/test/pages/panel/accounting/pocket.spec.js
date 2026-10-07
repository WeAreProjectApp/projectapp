import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';

const mockClipboardWrite = jest.fn();
const mockStore = reactive({
  isLoading: false,
  error: null,
  pocketMovements: [{ id: 1, direction: 'out', amount: 350000, movement_date: '2026-10-07', concept: 'Neto filtrado' }],
  metaFor: jest.fn(() => ({ balance: '1234567' })),
  fetchRecords: jest.fn().mockResolvedValue({ success: true }),
});

jest.mock('~/stores/accounting', () => ({ useAccountingStore: () => mockStore }));
jest.mock('~/composables/useIsMobile', () => {
  const { ref } = jest.requireActual('vue');
  return { useIsMobile: () => ({ isMobile: ref(false) }) };
});
jest.mock('~/composables/usePanelRefresh', () => ({ usePanelRefresh: jest.fn() }));
jest.mock('~/composables/useAccountingFilters', () => {
  const { ref } = jest.requireActual('vue');
  return {
    useAccountingFilters: () => ({
      currentFilters: ref({}), searchInput: ref(''), savedTabs: ref([]), activeTabId: ref(null),
      isFilterPanelOpen: ref(false), hasActiveFilters: ref(true), activeFilterCount: ref(1),
      isTabLimitReached: ref(false), applyFilters: (records) => records,
      countTabs: () => ({}), resetFilters: jest.fn(), selectTab: jest.fn(), saveTab: jest.fn(),
      deleteTab: jest.fn(), renameTab: jest.fn(), restoreTab: jest.fn(), rebaseTab: jest.fn(), reorderTabs: jest.fn(),
    }),
    matchDateRange: jest.fn(), matchNumberRange: jest.fn(), matchIncludes: jest.fn(), matchBooleanIncludes: jest.fn(),
  };
});
jest.mock('~/composables/useAccountingCrudPage', () => {
  const { ref, computed } = jest.requireActual('vue');
  return {
    useAccountingCrudPage: () => ({
      isModalOpen: ref(false), editingRecord: ref(null), openCreateModal: jest.fn(), lastMutatedId: ref(null),
      openEditModal: jest.fn(), closeModal: jest.fn(), handleSubmit: jest.fn(), confirmDeleteRecord: jest.fn(),
      confirmState: ref({ open: false }), handleConfirmed: jest.fn(), handleCancelled: jest.fn(), currentPage: ref(1),
      totalPages: ref(1), totalItems: ref(1), rangeFrom: ref(1), rangeTo: ref(1), pagedRecords: computed(() => []),
      prevPage: jest.fn(), nextPage: jest.fn(), goToPage: jest.fn(), handleCreateFilterTab: jest.fn(),
      handleResetFilters: jest.fn(), sortKey: ref('movement_date'), sortDir: ref('desc'), toggleSort: jest.fn(),
    }),
  };
});

import PocketPage from '~/pages/panel/accounting/pocket.vue';

const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');

function mountPage() {
  return mount(PocketPage, {
    shallow: true,
    global: {
      stubs: {
        BasePageShell: { template: '<div><slot /></div>' },
        BaseInput: true,
        UiFilterToggleButton: true,
        BaseActionButton: {
          props: ['disabled', 'statusLabel', 'statusTone'], emits: ['click'],
          template: '<button v-bind="$attrs" :disabled="disabled" type="button" @click="$emit(\'click\')"><span role="status">{{ statusLabel }}</span></button>',
        },
      },
    },
  });
}

describe('pocket balance copy', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore.isLoading = false;
    mockStore.error = null;
    global.definePageMeta = jest.fn();
    mockClipboardWrite.mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: mockClipboardWrite },
    });
  });

  afterEach(() => {
    if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard);
    else delete navigator.clipboard;
  });

  // Falla si el botón copia el neto filtrado en lugar del saldo total del servidor.
  it('copies the server balance in displayed COP format despite active filters', async () => {
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.get('[data-testid="pocket-balance"]').text()).toBe('$1.234.567');
    expect(wrapper.get('[data-testid="pocket-filtered-net"]').text()).toContain('neto $-350.000');
    await wrapper.get('[data-testid="pocket-copy-balance"]').trigger('click');
    await flushPromises();

    expect(mockClipboardWrite).toHaveBeenCalledWith('$1.234.567');
    expect(wrapper.get('[data-testid="pocket-copy-balance"] [role="status"]').text()).toBe('Saldo copiado');
    wrapper.unmount();
  });

  // Falla si un rechazo del portapapeles deja al usuario creyendo que el saldo se copió.
  it('shows local error feedback when copying the balance fails', async () => {
    mockClipboardWrite.mockRejectedValueOnce(new Error('permission denied'));
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="pocket-copy-balance"]').trigger('click');
    await flushPromises();

    expect(mockClipboardWrite).toHaveBeenCalledWith('$1.234.567');
    expect(wrapper.get('[data-testid="pocket-copy-balance"] [role="status"]').text()).toBe('No se pudo copiar');
    wrapper.unmount();
  });

  // Falla si se intenta copiar un saldo que todavía carga o cuyo listado falló.
  it.each([
    ['loading', true, null],
    ['fetch failure', false, 'fetch_failed'],
  ])('does not call the clipboard while the balance is unavailable: %s', async (_state, isLoading, error) => {
    mockStore.isLoading = isLoading;
    mockStore.error = error;
    const wrapper = mountPage();
    await flushPromises();
    const copy = wrapper.get('[data-testid="pocket-copy-balance"]');

    expect(copy.element.disabled).toBe(true);
    await copy.trigger('click');
    expect(mockClipboardWrite).toHaveBeenCalledTimes(0);
    wrapper.unmount();
  });
});
