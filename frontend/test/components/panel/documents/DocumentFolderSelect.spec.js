/**
 * DocumentFolderSelect: el selector de carpeta de un documento, con búsqueda.
 *
 * Cubre el catálogo completo al enfocar, el filtrado local por ruta y dueño,
 * que sólo elegir o quitar escribe el modelo (resolver el rótulo nunca: un
 * formulario abierto dentro de una carpeta no puede nacer modificado), la
 * carpeta comprometida que no se ofrece, el reintento cuando la lectura falla
 * y el modo deshabilitado.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import DocumentFolderSelect from '../../../../components/panel/documents/DocumentFolderSelect.vue';
import { useDocumentFolderStore } from '../../../../stores/document_folders';

jest.mock('../../../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { get_request } = require('../../../../stores/services/request_http');

const VASTAGO = { project: 21, project_name: 'Vástago', client: 7, client_display_name: 'Vástago SAS' };

const FOLDERS = [
  {
    id: 5, name: 'Vástago', parent: null, folder_kind: 'project', ...VASTAGO,
    managed_project_state: { name: 'Activo', system_key: 'active' },
  },
  { id: 6, name: 'Cuentas de cobro', parent: 5, is_system_managed: true, ...VASTAGO },
  { id: 15, name: 'Anuladas a mano', parent: 6, ...VASTAGO },
  { id: 7, name: 'Entregables', parent: 5, ...VASTAGO },
  { id: 17, name: 'Sprint 1', parent: 7, ...VASTAGO },
  { id: 8, name: 'Kore', parent: null, folder_kind: 'project', client_display_name: 'Kore SAS' },
  { id: 9, name: 'Entregables', parent: 8, client_display_name: 'Kore SAS' },
  { id: 12, name: 'Plantillas', parent: null, folder_kind: 'manual' },
  { id: 14, name: 'Kore SAS', parent: null, folder_kind: 'client', client_display_name: 'Kore SAS' },
  { id: 3, name: 'Contratos' },
];

const mountedWrappers = [];

function mountSelect({ props = {}, folders = FOLDERS, isLoading = false } = {}) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useDocumentFolderStore();
  store.$patch({ folders, isLoading });
  const wrapper = mount(DocumentFolderSelect, {
    props: { testid: 'folder', ...props },
    global: {
      plugins: [pinia],
      stubs: {
        Teleport: true,
        BaseButton: {
          props: ['type'],
          emits: ['click'],
          template: '<button :type="type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  });
  mountedWrappers.push(wrapper);
  return { wrapper, store, input: wrapper.find('[data-testid="folder"]') };
}

function optionIds(wrapper) {
  return wrapper.findAll('[role="option"]').map((row) => row.attributes('data-testid'));
}

afterEach(() => {
  // El listbox flotante deja listeners en window mientras está abierto.
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount());
});

describe('DocumentFolderSelect', () => {
  it('names the combobox after its label and lists the whole catalog on focus', async () => {
    const { wrapper, input } = mountSelect();

    await input.trigger('focus');

    expect(wrapper.find('label').text()).toBe('Carpeta');
    expect(wrapper.find('label').attributes('for')).toBe(input.attributes('id'));
    expect(input.attributes('aria-expanded')).toBe('true');
    // La automática (6) no se ofrece; su hijo manual (15) sí.
    expect(optionIds(wrapper)).toEqual([5, 15, 7, 17, 8, 9, 12, 14, 3].map((id) => `folder-option-${id}`));
  });

  it('filters locally by path and commits the clicked option\'s numeric id', async () => {
    const { wrapper, input } = mountSelect();
    await input.trigger('focus');

    await input.setValue('vastago entre');

    expect(optionIds(wrapper)).toEqual(['folder-option-7', 'folder-option-17']);
    await wrapper.find('[data-testid="folder-option-7"]').trigger('click');
    expect(wrapper.emitted('update:modelValue')).toEqual([[7]]);
    expect(wrapper.emitted('select')[0][0]).toMatchObject({ id: 7, name: 'Entregables' });
    expect(input.element.value).toBe('Vástago / Entregables');
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
  });

  it('resolves the label of a value set before the folders arrive, without emitting', async () => {
    const { wrapper, store, input } = mountSelect({
      props: { modelValue: 7 },
      folders: [],
      isLoading: true,
    });
    await input.trigger('focus');
    expect(wrapper.text()).toContain('Cargando carpetas...');

    store.$patch({ folders: FOLDERS, isLoading: false });
    await input.trigger('keydown', { key: 'Escape' });

    expect(input.element.value).toBe('Vástago / Entregables');
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('keeps the committed folder while typing and restores its path on Escape', async () => {
    const { wrapper, input } = mountSelect({ props: { modelValue: 7 } });
    await input.trigger('focus');

    await input.setValue('zzz');
    await input.trigger('keydown', { key: 'Escape' });

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(input.element.value).toBe('Vástago / Entregables');
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
  });

  it('reopens on the whole catalog with the current folder highlighted', async () => {
    const { wrapper, input } = mountSelect({ props: { modelValue: 7 } });

    await input.trigger('focus');

    const current = wrapper.find('[data-testid="folder-option-7"]');
    expect(optionIds(wrapper)).toHaveLength(9);
    expect(current.attributes('aria-selected')).toBe('true');
    expect(input.attributes('aria-activedescendant')).toBe(current.attributes('id'));
    // Lo elegido queda a la vista como placeholder mientras se busca otra.
    expect(input.attributes('placeholder')).toBe('Vástago / Entregables');
  });

  it('moves the highlight with the arrow keys and commits it with Enter', async () => {
    const { wrapper, input } = mountSelect();
    await input.trigger('focus');

    await input.trigger('keydown', { key: 'ArrowUp' });
    expect(wrapper.find('[data-testid="folder-option-3"]').attributes('aria-selected')).toBe('true');
    await input.trigger('keydown', { key: 'ArrowDown' });
    await input.trigger('keydown', { key: 'ArrowDown' });
    await input.trigger('keydown', { key: 'Enter' });

    expect(wrapper.emitted('update:modelValue')).toEqual([[15]]);
    expect(input.element.value).toBe('Vástago / Cuentas de cobro / Anuladas a mano');
  });

  it('clearing unlinks the folder and empties the field', async () => {
    const { wrapper, input } = mountSelect({ props: { modelValue: 7 } });
    const clear = wrapper.find('[data-testid="folder-clear"]');
    expect(clear.attributes('aria-label')).toBe('Quitar carpeta');

    await clear.trigger('click');

    expect(wrapper.emitted('update:modelValue')).toEqual([[null]]);
    expect(wrapper.emitted('select')).toEqual([[null]]);
    expect(input.element.value).toBe('');
  });

  it('names a committed folder it does not offer, and an unknown one by its number', async () => {
    const { wrapper, input } = mountSelect({ props: { modelValue: 6 } });
    expect(input.element.value).toBe('Vástago / Cuentas de cobro');

    await wrapper.setProps({ modelValue: 99 });
    expect(input.element.value).toBe('Carpeta #99');

    await input.trigger('focus');
    expect(wrapper.find('[data-testid="folder-option-6"]').exists()).toBe(false);
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('explains a search without matches', async () => {
    const { wrapper, input } = mountSelect();
    await input.trigger('focus');

    await input.setValue('zzz');

    expect(wrapper.find('[data-testid="folder-empty"]').text())
      .toBe('Sin carpetas que coincidan con "zzz".');
  });

  it('says the folders failed to load and retries from the picker', async () => {
    get_request.mockResolvedValueOnce({ data: FOLDERS });
    const { wrapper, store, input } = mountSelect({ folders: [] });
    store.error = 'fetch_folders_failed';
    await input.trigger('focus');
    expect(wrapper.find('[data-testid="folder-error"]').text())
      .toContain('No se pudieron cargar las carpetas.');

    await wrapper.find('[data-testid="folder-retry"]').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenCalledWith('document-folders/?scope=all');
    expect(optionIds(wrapper)).toHaveLength(9);
  });

  it('tolerates a folders payload that is not a list', async () => {
    const { wrapper, input } = mountSelect({ folders: {} });

    await input.trigger('focus');

    expect(wrapper.find('[data-testid="folder-empty"]').text()).toBe('No hay carpetas todavía.');
  });

  it('stays closed and explains itself when disabled', async () => {
    const { wrapper, input } = mountSelect({
      props: { modelValue: 7, disabled: true, disabledReason: 'Documento de sólo lectura.' },
    });

    await input.trigger('focus');

    expect(input.attributes('disabled')).toBeDefined();
    expect(input.attributes('title')).toBe('Documento de sólo lectura.');
    expect(wrapper.find('[data-testid="folder-clear"]').exists()).toBe(false);
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
  });
});
