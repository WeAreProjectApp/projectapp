import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

const mockGetRequest = jest.fn();
const mockCreateRequest = jest.fn();
const mockNotify = { success: jest.fn(), error: jest.fn() };

jest.mock('~/stores/services/request_http', () => ({
  get_request: (...args) => mockGetRequest(...args),
  create_request: (...args) => mockCreateRequest(...args),
  put_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn(),
}));
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));

import ProposalActivityTab from '~/components/panel/proposal/ProposalActivityTab.vue';

const proposal = { id: 117 };
const activity = (id, description) => ({
  id,
  change_type: 'note',
  description,
  created_at: '2026-10-07T12:00:00Z',
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function mountTab(props = {}) {
  const pinia = createPinia();
  setActivePinia(pinia);
  return mount(ProposalActivityTab, {
    props: { proposal, ...props },
    global: {
      plugins: [pinia],
      stubs: {
        BaseButton: { emits: ['click'], template: '<button role="button" v-bind="$attrs" type="button" @click="$emit(\'click\')"><slot /></button>' },
        BaseControlGate: { template: '<div><slot /></div>' },
        BaseInput: { props: ['modelValue', 'size', 'type', 'placeholder'], emits: ['update:modelValue'], template: '<input role="textbox" :type="type" :placeholder="placeholder" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
        BaseSelect: { props: ['modelValue', 'size'], emits: ['update:modelValue'], template: '<select role="combobox" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
        BaseTooltip: { template: '<span><slot name="trigger" /><slot /></span>' },
      },
    },
  });
}

function buttonByText(wrapper, text) {
  return wrapper.findAll('[role="button"]').find((button) => button.text() === text);
}

describe('ProposalActivityTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.useTooltipTexts = () => ({ proposalEdit: { logActivity: '', activityHistory: '' } });
  });

  // Falla si Cargar más reemplaza la página inicial o duplica una actividad que se actualizó.
  it('merges a later cursor page with the loaded activity timeline', async () => {
    mockGetRequest
      .mockResolvedValueOnce({ data: { results: [activity(1, 'Nota inicial')], next_cursor: 'cursor-2' } })
      .mockResolvedValueOnce({ data: { results: [activity(1, 'Nota actualizada'), activity(2, 'Nota más antigua')], next_cursor: null } });
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.get('[data-testid="proposal-activity-load-more"]').trigger('click');
    await flushPromises();

    expect(mockGetRequest.mock.calls).toEqual([
      ['proposals/117/activity/', { params: { page_size: 20 } }],
      ['proposals/117/activity/', { params: { cursor: 'cursor-2', page_size: 20 } }],
    ]);
    expect(wrapper.text()).toContain('Nota actualizada');
    expect(wrapper.text()).toContain('Nota más antigua');
    expect(wrapper.text()).not.toContain('Nota inicial');
    wrapper.unmount();
  });

  // Falla si una página posterior con error borra lo que ya había visto el usuario.
  it('retries a failed later page without discarding loaded activity', async () => {
    mockGetRequest
      .mockResolvedValueOnce({ data: { results: [activity(1, 'Actividad ya visible')], next_cursor: 'cursor-2' } })
      .mockRejectedValueOnce({ response: { status: 500 } })
      .mockResolvedValueOnce({ data: { results: [activity(2, 'Actividad recuperada')], next_cursor: 'cursor-3' } })
      .mockResolvedValueOnce({ data: { results: [activity(3, 'Actividad de la continuación')], next_cursor: null } });
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.get('[data-testid="proposal-activity-load-more"]').trigger('click');
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('No se pudo cargar la actividad. Vuelve a intentarlo.');
    expect(wrapper.text()).toContain('Actividad ya visible');

    await buttonByText(wrapper, 'Reintentar').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="proposal-activity-load-more"]').trigger('click');
    await flushPromises();

    expect(mockGetRequest.mock.calls).toEqual([
      ['proposals/117/activity/', { params: { page_size: 20 } }],
      ['proposals/117/activity/', { params: { cursor: 'cursor-2', page_size: 20 } }],
      ['proposals/117/activity/', { params: { cursor: 'cursor-2', page_size: 20 } }],
      ['proposals/117/activity/', { params: { cursor: 'cursor-3', page_size: 20 } }],
    ]);
    expect(wrapper.text()).toContain('Actividad ya visible');
    expect(wrapper.text()).toContain('Actividad recuperada');
    expect(wrapper.text()).toContain('Actividad de la continuación');
    wrapper.unmount();
  });

  // Falla si una nota guardada mientras llega la primera página desaparece al resolver esa carga.
  it('keeps a newly submitted note when the initial activity request resolves afterwards', async () => {
    const initialPage = deferred();
    mockGetRequest.mockReturnValueOnce(initialPage.promise);
    mockCreateRequest.mockResolvedValue({ data: activity(77, 'Nota que no puede perderse') });
    const wrapper = mountTab();

    await wrapper.get('[role="textbox"]').setValue('Nota que no puede perderse');
    await buttonByText(wrapper, 'Agregar').trigger('click');
    await flushPromises();
    initialPage.resolve({ data: { results: [activity(1, 'Actividad del servidor')], next_cursor: null } });
    await flushPromises();

    expect(mockCreateRequest).toHaveBeenCalledWith(
      'proposals/117/log-activity/',
      { change_type: 'note', description: 'Nota que no puede perderse' },
    );
    expect(wrapper.text()).toContain('Nota que no puede perderse');
    expect(wrapper.text()).toContain('Actividad del servidor');
    wrapper.unmount();
  });

  // Falla si una respuesta tardía de otra propuesta reemplaza la actividad y el cursor actuales.
  it('keeps the current proposal timeline when the prior proposal response arrives late', async () => {
    const firstProposalPage = deferred();
    const secondProposalPage = deferred();
    mockGetRequest
      .mockReturnValueOnce(firstProposalPage.promise)
      .mockReturnValueOnce(secondProposalPage.promise)
      .mockResolvedValueOnce({ data: { results: [activity(119, 'Página adicional de 118')], next_cursor: null } });
    const wrapper = mountTab();

    await wrapper.setProps({ proposal: { id: 118 } });
    secondProposalPage.resolve({ data: { results: [activity(118, 'Actividad de propuesta 118')], next_cursor: 'cursor-118' } });
    await flushPromises();
    firstProposalPage.resolve({ data: { results: [activity(117, 'Actividad obsoleta de 117')], next_cursor: 'cursor-117' } });
    await flushPromises();

    expect(wrapper.text()).toContain('Actividad de propuesta 118');
    expect(wrapper.text()).not.toContain('Actividad obsoleta de 117');
    await wrapper.get('[data-testid="proposal-activity-load-more"]').trigger('click');
    await flushPromises();
    expect(mockGetRequest).toHaveBeenLastCalledWith('proposals/118/activity/', { params: { cursor: 'cursor-118', page_size: 20 } });
    expect(wrapper.text()).toContain('Página adicional de 118');
    wrapper.unmount();
  });

  // Falla si una nota de la propuesta anterior aparece después de abrir otra propuesta.
  it('does not insert a late note after the operator opens another proposal', async () => {
    const firstProposalPage = deferred();
    const secondProposalPage = deferred();
    const lateNote = deferred();
    mockGetRequest.mockReturnValueOnce(firstProposalPage.promise).mockReturnValueOnce(secondProposalPage.promise);
    mockCreateRequest.mockReturnValueOnce(lateNote.promise);
    const wrapper = mountTab();

    await wrapper.get('[role="textbox"]').setValue('Nota tardía de 117');
    await buttonByText(wrapper, 'Agregar').trigger('click');
    await wrapper.setProps({ proposal: { id: 118 } });
    secondProposalPage.resolve({ data: { results: [activity(118, 'Actividad actual de 118')], next_cursor: null } });
    await flushPromises();
    lateNote.resolve({ data: activity(77, 'Nota tardía de 117') });
    await flushPromises();

    expect(mockCreateRequest).toHaveBeenCalledWith('proposals/117/log-activity/', { change_type: 'note', description: 'Nota tardía de 117' });
    expect(wrapper.text()).toContain('Actividad actual de 118');
    expect(wrapper.text()).not.toContain('Nota tardía de 117');
    wrapper.unmount();
  });

  // Falla si un 500 borra una nota sin guardar o bloquea repetir su envío.
  it('keeps a failed note draft available for a successful retry', async () => {
    mockGetRequest.mockResolvedValue({ data: { results: [activity(1, 'Actividad inicial')], next_cursor: null } });
    mockCreateRequest
      .mockRejectedValueOnce({ response: { status: 500 } })
      .mockResolvedValueOnce({ data: activity(78, 'Nota para reintentar') });
    const wrapper = mountTab();
    await flushPromises();
    const description = wrapper.get('[role="textbox"]');

    await description.setValue('Nota para reintentar');
    await buttonByText(wrapper, 'Agregar').trigger('click');
    await flushPromises();

    expect(description.element.value).toBe('Nota para reintentar');
    expect(buttonByText(wrapper, 'Agregar').text()).toBe('Agregar');
    await buttonByText(wrapper, 'Agregar').trigger('click');
    await flushPromises();

    expect(mockCreateRequest.mock.calls).toEqual([
      ['proposals/117/log-activity/', { change_type: 'note', description: 'Nota para reintentar' }],
      ['proposals/117/log-activity/', { change_type: 'note', description: 'Nota para reintentar' }],
    ]);
    expect(description.element.value).toBe('');
    expect(wrapper.text()).toContain('Nota para reintentar');
    wrapper.unmount();
  });

  // Falla si la respuesta de una nota previa borra el segundo borrador que el operador acaba de escribir.
  it('keeps a newer draft after the first submitted note resolves', async () => {
    const firstNote = deferred();
    mockGetRequest.mockResolvedValue({ data: { results: [], next_cursor: null } });
    mockCreateRequest.mockReturnValueOnce(firstNote.promise);
    const wrapper = mountTab();
    await flushPromises();
    const description = wrapper.get('[role="textbox"]');

    await description.setValue('Primera nota');
    await buttonByText(wrapper, 'Agregar').trigger('click');
    await description.setValue('Segundo borrador');
    firstNote.resolve({ data: activity(79, 'Primera nota') });
    await flushPromises();

    expect(mockCreateRequest).toHaveBeenCalledWith('proposals/117/log-activity/', { change_type: 'note', description: 'Primera nota' });
    expect(wrapper.text()).toContain('Primera nota');
    expect(description.element.value).toBe('Segundo borrador');
    wrapper.unmount();
  });
});
