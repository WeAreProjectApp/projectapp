import { flushPromises, mount } from '@vue/test-utils';
import ClientRetainedProjectDataModal from '../../../components/clients/ClientRetainedProjectDataModal.vue';
import { create_request, get_request } from '../../../stores/services/request_http';

jest.mock('../../../stores/services/request_http', () => ({
  get_request: jest.fn(), create_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn(),
}));

jest.mock('#imports', () => {
  const { ref } = require('vue');
  const labels = {
    'projectAccess.retention.fields.title': 'Título',
    'projectAccess.retention.fields.content': 'Contenido',
  };
  return { useI18n: () => ({ t: (key) => labels[key] || key, locale: ref('es') }) };
});

const CLIENT_A = { id: 14, company: 'Cliente A' };
const CLIENT_B = { id: 15, company: 'Cliente B' };
const CONTEXT = {
  id: 23,
  project_name: 'Portal anterior',
  categories: [{ key: 'documents', label: 'Documentos', description: 'Archivos que se conservaron.', count: 1 }],
};
const DOCUMENT = {
  id: '9', key: 'documents', title: 'Manual de operación',
  fields: { title: 'Manual de operación', content: 'Guía interna' },
  files: [], can_reveal: false,
};
const translate = (key) => ({
  'projectAccess.retention.title': 'Datos sin proyecto',
  'projectAccess.retention.hint': 'Consulta y descarga de datos conservados. No se pueden editar desde aquí.',
  'projectAccess.retention.originalProject': 'Nombre del proyecto de origen, ya eliminado.',
  'projectAccess.retention.reveal': 'Revelar contenido oculto',
  'projectAccess.retention.hide': 'Ocultar contenido',
  'projectAccess.retention.close': 'Cerrar',
  'projectAccess.retention.back': 'Volver a los proyectos de origen',
  'projectAccess.retention.next': 'Siguiente',
  'projectAccess.retention.download': 'Descargar',
}[key] || key);

function mountModal(props = {}) {
  return mount(ClientRetainedProjectDataModal, {
    props: { open: true, client: CLIENT_A, ...props },
    global: {
      stubs: {
        BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue" role="dialog"><slot /><slot name="footer" /></div>' },
        BaseAlert: { template: '<div><slot /></div>' },
        BaseModalActions: { template: '<div><slot /></div>' },
        BaseButton: { emits: ['click'], template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>' },
      },
      mocks: { $t: translate },
    },
  });
}

describe('ClientRetainedProjectDataModal', () => {
  beforeEach(() => jest.clearAllMocks());

  // Fails if opening the read-only consultation preloads secret values or record details.
  it('loads only the client contexts when opened', async () => {
    get_request.mockResolvedValueOnce({ data: { contexts: [CONTEXT] } });

    const wrapper = mountModal();
    await flushPromises();

    expect(get_request).toHaveBeenCalledWith('proposals/client-profiles/14/retained-project-data/');
    expect(get_request).toHaveBeenCalledTimes(1);
    expect(wrapper.get('[data-testid="retained-category-documents"]').text()).toBe('Documentos (1)');
    expect(wrapper.find('[data-testid="retained-data-record"]').exists()).toBe(false);
    expect(create_request).not.toHaveBeenCalled();
  });

  // Fails if choosing a category does not load its preserved records or reveals content without consent.
  it('loads a selected category without revealing secret values', async () => {
    get_request
      .mockResolvedValueOnce({ data: { contexts: [CONTEXT] } })
      .mockResolvedValueOnce({ data: {
        count: 1,
        results: [DOCUMENT],
      } });

    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="retained-category-documents"]').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenLastCalledWith('proposals/client-profiles/14/retained-project-data/?context=23&category=documents&page=1');
    expect(wrapper.get('[data-testid="retained-data-record"]').text()).toContain('Guía interna');
    expect(get_request).toHaveBeenCalledTimes(2);
    expect(create_request).not.toHaveBeenCalled();
  });

  it('reveals a retained credential only after its button is clicked', async () => {
    const accessContext = { ...CONTEXT, categories: [{ key: 'accesses', label: 'Accesos', count: 1 }] };
    get_request
      .mockResolvedValueOnce({ data: { contexts: [accessContext] } })
      .mockResolvedValueOnce({ data: { count: 1, results: [{
        id: '9', key: 'accesses', title: 'Acceso de producción', fields: {}, files: [], can_reveal: true,
      }] } });
    create_request.mockResolvedValueOnce({ data: { value: 'Secreto visible bajo demanda' } });
    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="retained-category-accesses"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).not.toContain('Secreto visible bajo demanda');
    expect(create_request).not.toHaveBeenCalled();

    await wrapper.findAll('button').find((button) => button.text() === 'Revelar contenido oculto').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledTimes(1);
    expect(create_request).toHaveBeenCalledWith('proposals/client-profiles/14/retained-project-data/23/accesses/9/reveal/', {});
    expect(wrapper.get('[data-testid="retained-data-record"]').text()).toContain('Secreto visible bajo demanda');
  });

  // Fails if a late response for one client replaces the data of another client.
  it('discards a late context response after the client changes', async () => {
    let resolveClientA;
    const delayedClientA = new Promise((resolve) => { resolveClientA = resolve; });
    get_request
      .mockReturnValueOnce(delayedClientA)
      .mockResolvedValueOnce({ data: { contexts: [] } });

    const wrapper = mountModal();
    await wrapper.setProps({ client: CLIENT_B });
    resolveClientA({ data: { contexts: [CONTEXT] } });
    await flushPromises();

    expect(get_request).toHaveBeenLastCalledWith('proposals/client-profiles/15/retained-project-data/');
    expect(wrapper.get('[data-testid="retained-data-empty"]').text()).toBe('projectAccess.retention.empty');
    expect(wrapper.text()).not.toContain('Portal anterior');
  });

  it('clears already displayed records when the client changes', async () => {
    let resolveClientB;
    get_request
      .mockResolvedValueOnce({ data: { contexts: [CONTEXT] } })
      .mockResolvedValueOnce({ data: { count: 1, results: [DOCUMENT] } })
      .mockReturnValueOnce(new Promise((resolve) => { resolveClientB = resolve; }));
    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="retained-category-documents"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Guía interna');

    await wrapper.setProps({ client: CLIENT_B });

    expect(wrapper.text()).not.toContain('Guía interna');
    resolveClientB({ data: { contexts: [] } });
    await flushPromises();
    expect(wrapper.find('[data-testid="retained-data-record"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Manual de operación');
  });

  it('loads the next page of original projects on demand', async () => {
    get_request
      .mockResolvedValueOnce({ data: { contexts: [CONTEXT], count: 51, page: 1 } })
      .mockResolvedValueOnce({ data: { contexts: [{ ...CONTEXT, id: 24, project_name: 'Otro origen' }], count: 51, page: 2 } });
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.findAll('button').find((button) => button.text() === 'Siguiente').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenLastCalledWith('proposals/client-profiles/14/retained-project-data/?page=2');
    expect(wrapper.text()).toContain('Otro origen');
    expect(wrapper.text()).not.toContain('Portal anterior');
    expect(create_request).not.toHaveBeenCalled();
  });

  it('removes previous records when the next page fails to load', async () => {
    get_request
      .mockResolvedValueOnce({ data: { contexts: [CONTEXT] } })
      .mockResolvedValueOnce({ data: { count: 51, results: [DOCUMENT] } })
      .mockRejectedValueOnce(new Error('service unavailable'));
    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="retained-category-documents"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Guía interna');

    await wrapper.findAll('button').find((button) => button.text() === 'Siguiente').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="retained-data-record"]').exists()).toBe(false);
    expect(wrapper.get('[role="alert"]').text()).toBe('projectAccess.retention.loadError');
    expect(get_request).toHaveBeenLastCalledWith('proposals/client-profiles/14/retained-project-data/?context=23&category=documents&page=2');
  });
});
