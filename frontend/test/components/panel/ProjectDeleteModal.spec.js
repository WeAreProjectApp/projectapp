import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ProjectDeleteModal from '../../../components/panel/projects/ProjectDeleteModal.vue';
import { usePanelProjectsStore } from '../../../stores/panel_projects';
import translations from '../../../locales/projectAccess/es';
import BaseToggle from '../../../components/base/BaseToggle.vue';
import BaseInput from '../../../components/base/BaseInput.vue';

jest.mock('#imports', () => ({
  useI18n: () => ({ locale: { value: 'es-co' }, t: (key, params) => mockTranslate(key, params) }),
}));

const project = { id: 7, name: 'Proyecto de prueba', client_name: 'Cliente de prueba' };
const empty = { can_delete: true, blockers: [] };
const blocked = { can_delete: false, blockers: [{ key: 'incomes', label: 'Ingresos', count: 3 }, { key: 'documents', label: 'Documentos', count: 2 }] };
const mockTranslate = (key, params = {}) => {
  const message = key.split('.').slice(1).reduce((value, part) => value?.[part], translations) || key;
  return message.replace(/\{(\w+)\}/g, (_, name) => params[name]);
};
const forcePreview = (deleteKeys, token) => ({
  success: true,
  data: {
    project: { id: 7 }, delete_keys: deleteKeys, impact_token: token, can_delete: true, blockers: [],
    dependencies: [{ key: 'documents', label: 'Documentos', label_en: 'Documents', count: 2,
      description: 'Documentos vinculados.', description_en: 'Linked documents.' }],
  },
});
const category = '[data-testid="project-delete-category-documents"]';
const forceConfirm = '[data-testid="project-force-delete-confirm"]';
const confirmation = '[data-testid="project-force-delete-confirmation"]';

async function openModal(preview = empty, isSuperuser = false) {
  const store = usePanelProjectsStore();
  jest.spyOn(store, 'previewDeletion').mockResolvedValue({ success: true, data: preview });
  jest.spyOn(store, 'deleteProject').mockResolvedValue({ success: true });
  const wrapper = mount(ProjectDeleteModal, {
    props: { project, isSuperuser },
    global: {
      components: { BaseToggle, BaseInput },
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        BaseModal: { template: '<div role="dialog"><slot /></div>' },
        BaseAlert: { template: '<div><slot /></div>' },
        BaseFormField: { template: '<label><slot /></label>' },
      },
      mocks: { $t: mockTranslate, $te: (key) => mockTranslate(key) !== key },
    },
  });
  await flushPromises();
  return { wrapper, store };
}

describe('ProjectDeleteModal', () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => jest.restoreAllMocks());

  it('shows the selected project before confirming', async () => {
    const { wrapper } = await openModal();

    expect(wrapper.text()).toContain(project.name);
    expect(wrapper.get('[data-testid="project-delete-warning"]').text()).toContain('No se puede deshacer');
  });

  it('cancels without deleting', async () => {
    const { wrapper, store } = await openModal();

    await wrapper.findAll('button').find((button) => button.text() === 'Cancelar').trigger('click');

    expect(wrapper.emitted('close')).toHaveLength(1);
    expect(store.deleteProject).not.toHaveBeenCalled();
  });

  it('deletes only after explicit confirmation', async () => {
    const { wrapper, store } = await openModal();

    await wrapper.get('[data-testid="project-delete-confirm"]').trigger('click');
    await flushPromises();

    expect(store.deleteProject).toHaveBeenCalledWith(7);
    expect(wrapper.emitted('deleted')[0]).toEqual([{ success: true }]);
  });

  it('shows dependency names with their counts', async () => {
    const { wrapper } = await openModal(blocked);

    const rows = wrapper.get('[data-testid="project-delete-dependencies"]').findAll('tbody tr');
    expect(rows.map((row) => row.findAll('td').map((cell) => cell.text()))).toEqual([['Ingresos', '3'], ['Documentos', '2']]);
    expect(wrapper.find('[data-testid="project-delete-confirm"]').exists()).toBe(false);
  });

  it('offers the existing state flow when dependencies block deletion', async () => {
    const { wrapper, store } = await openModal(blocked);

    await wrapper.get('[data-testid="project-delete-change-state"]').trigger('click');

    expect(wrapper.emitted('change-state')[0]).toEqual([project]);
    expect(store.deleteProject).not.toHaveBeenCalled();
  });

  it('shows newly linked dependencies returned by confirmation', async () => {
    const { wrapper, store } = await openModal();
    store.deleteProject.mockResolvedValue({ success: false, message: 'Ahora tiene documentos', preview: blocked });

    await wrapper.get('[data-testid="project-delete-confirm"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="project-delete-dependencies"]').text()).toContain('Documentos');
    expect(wrapper.find('[data-testid="project-delete-confirm"]').exists()).toBe(false);
    expect(wrapper.emitted('deleted')).toBeUndefined();
  });

  it('allows retry after a failed delete request', async () => {
    const { wrapper, store } = await openModal();
    store.deleteProject.mockResolvedValueOnce({ success: false, message: 'Servicio no disponible' });

    await wrapper.get('[data-testid="project-delete-confirm"]').trigger('click');
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo eliminar el proyecto.');
    await wrapper.get('[data-testid="project-delete-confirm"]').trigger('click');
    await flushPromises();

    expect(wrapper.emitted('deleted')).toHaveLength(1);
  });

  it('refuses duplicate confirmation while deleting', async () => {
    const { wrapper, store } = await openModal();
    let resolve;
    store.deleteProject.mockReturnValue(new Promise((complete) => { resolve = complete; }));

    await wrapper.get('[data-testid="project-delete-confirm"]').trigger('click');
    await wrapper.get('[data-testid="project-delete-confirm"]').trigger('click');

    expect(store.deleteProject).toHaveBeenCalledTimes(1);
    resolve({ success: true });
    await flushPromises();
  });

  it('uses only the latest forced impact for confirmation', async () => {
    const { wrapper, store } = await openModal(blocked, true);
    let resolveEarlier;
    let resolveLatest;
    store.previewDeletion
      .mockResolvedValueOnce(forcePreview([], 'initial'))
      .mockReturnValueOnce(new Promise((resolve) => { resolveEarlier = resolve; }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveLatest = resolve; }));
    await wrapper.get('[data-testid="project-force-delete-toggle"]').trigger('click');
    await flushPromises();

    await wrapper.get(category).trigger('click');
    await wrapper.get(category).trigger('click');
    await wrapper.get(confirmation).setValue('DELETE');
    await wrapper.get(forceConfirm).trigger('click');
    expect(store.deleteProject).not.toHaveBeenCalled();

    resolveLatest(forcePreview([], 'latest'));
    resolveEarlier(forcePreview(['documents'], 'earlier'));
    await flushPromises();
    await wrapper.get(forceConfirm).trigger('click');

    expect(store.deleteProject).toHaveBeenCalledWith(7, {
      force: true, delete_keys: [], impact_token: 'latest', confirmation: 'DELETE',
    });
  });

  it('rejects an impact that echoes another selection', async () => {
    const { wrapper, store } = await openModal(blocked, true);
    store.previewDeletion
      .mockResolvedValueOnce(forcePreview([], 'initial'))
      .mockResolvedValueOnce(forcePreview([], 'mismatch'));
    await wrapper.get('[data-testid="project-force-delete-toggle"]').trigger('click');
    await flushPromises();

    await wrapper.get(category).trigger('click');
    await flushPromises();
    await wrapper.get(confirmation).setValue('DELETE');

    expect(wrapper.get(forceConfirm).attributes()).toHaveProperty('disabled');
    expect(wrapper.get(category).attributes('aria-checked')).toBe('true');
    expect(wrapper.get('[data-testid="project-force-delete-error"]').text()).toContain('No se pudieron comprobar');
  });
});
