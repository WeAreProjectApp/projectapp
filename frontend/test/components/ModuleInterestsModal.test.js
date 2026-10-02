import { defineComponent, h } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  put_request: jest.fn(),
}));

jest.mock('../../composables/useExplainerVideos', () => ({
  useExplainerVideo: jest.fn(() => null),
}));

jest.mock('../../composables/useProposalDarkMode', () => ({
  useProposalDarkMode: jest.fn(() => ({ isDark: require('vue').ref(false) })),
}));

import { get_request, put_request } from '../../stores/services/request_http';
import ModuleInterestsModal from '../../components/BusinessProposal/ModuleInterestsModal.vue';

const BaseModalStub = defineComponent({
  props: ['modelValue'],
  setup(_props, { slots }) {
    return () => h('section', { 'data-testid': 'modal-shell' }, [slots.default?.(), slots.footer?.()]);
  },
});

const BaseButtonStub = defineComponent({
  props: ['disabled', 'loading'],
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      disabled: props.disabled,
      onClick: () => { if (!props.disabled) emit('click'); },
    }, slots.default?.());
  },
});

const catalog = {
  categories: [{
    id: 8,
    name: 'Automatización',
    modules: [{ id: 41, icon: '🧩', name: 'Agenda inteligente', summary: 'Organiza tus reservas.' }],
  }],
  show_explainer_video: false,
};

function loadCatalogWith(interests = []) {
  get_request
    .mockResolvedValueOnce({ data: catalog })
    .mockResolvedValueOnce({ data: { modules: interests } });
}

function mountModal(props = {}) {
  return mount(ModuleInterestsModal, {
    props: { visible: true, proposalUuid: 'proposal-uuid', language: 'es', ...props },
    global: {
      stubs: {
        BaseModal: BaseModalStub,
        BaseButton: BaseButtonStub,
        ModuleDetails: { template: '<div />' },
      },
    },
  });
}

function interestCheckbox(wrapper) {
  return wrapper.get('input[aria-label="Me interesa: Agenda inteligente"]');
}

function buttonWithText(wrapper, text) {
  return wrapper.findAll('button').find((button) => button.text() === text);
}

describe('ModuleInterestsModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('saves the selected catalog module for the proposal', async () => {
    // Fails if an interest uses the retired calculator endpoint or changes the proposal price.
    loadCatalogWith();
    put_request.mockResolvedValueOnce({ data: { modules: [{ id: 41 }], status: 'saved' } });
    const wrapper = mountModal();
    await flushPromises();

    await interestCheckbox(wrapper).setValue(true);
    await buttonWithText(wrapper, 'Guardar mi interés').trigger('click');
    await flushPromises();

    expect(get_request.mock.calls).toEqual([
      ['additional-modules/public/?lang=es'],
      ['proposals/proposal-uuid/module-interests/'],
    ]);
    expect(put_request).toHaveBeenCalledWith('proposals/proposal-uuid/module-interests/', { module_ids: [41] });
    expect(wrapper.text()).toContain('Tu selección no cambia la propuesta, la inversión ni el plazo.');
  });

  it('renders a retry action after the catalog request fails', async () => {
    // Fails if a transient catalog failure leaves the customer without a recovery path.
    get_request
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ data: { modules: [] } })
      .mockResolvedValueOnce({ data: catalog })
      .mockResolvedValueOnce({ data: { modules: [] } });
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe('No pudimos cargar los módulos. Inténtalo de nuevo.Reintentar');

    await buttonWithText(wrapper, 'Reintentar').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="module-interests-modal"]').text()).toContain('Agenda inteligente');
  });

  it('preserves the selected module after saving fails', async () => {
    // Fails if a failed interest request clears the module the customer selected.
    loadCatalogWith();
    put_request.mockRejectedValueOnce(new Error('offline'));
    const wrapper = mountModal();
    await flushPromises();

    await interestCheckbox(wrapper).setValue(true);
    await buttonWithText(wrapper, 'Guardar mi interés').trigger('click');
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe('No pudimos guardar tu interés. Tu selección sigue aquí; puedes reintentar.');
    expect(interestCheckbox(wrapper).element.checked).toBe(true);
  });

  it('keeps preview interests in the browser', async () => {
    // Fails if an administrative preview writes a public interest to the proposal.
    loadCatalogWith();
    const wrapper = mountModal({ preview: true });
    await flushPromises();

    await interestCheckbox(wrapper).setValue(true);
    await buttonWithText(wrapper, 'Guardar mi interés').trigger('click');
    await flushPromises();

    expect(put_request).not.toHaveBeenCalled();
    expect(wrapper.get('[role="alert"]').text()).toBe('Vista previa: el interés no se guardará.');
  });
});
