import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ProjectDeleteModal from '../../../components/panel/projects/ProjectDeleteModal.vue';
import { usePanelProjectsStore } from '../../../stores/panel_projects';
import translations from '../../../locales/projectAccess/es';

const project = { id: 7, name: 'Proyecto de prueba', client_name: 'Cliente de prueba' };
const empty = { can_delete: true, blockers: [] };
const blocked = { can_delete: false, blockers: [{ key: 'incomes', label: 'Ingresos', count: 3 }, { key: 'documents', label: 'Documentos', count: 2 }] };
const t = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], translations) || key;

async function openModal(preview = empty) {
  const store = usePanelProjectsStore();
  jest.spyOn(store, 'previewDeletion').mockResolvedValue({ success: true, data: preview });
  jest.spyOn(store, 'deleteProject').mockResolvedValue({ success: true });
  const wrapper = mount(ProjectDeleteModal, {
    props: { project },
    global: {
      stubs: { NuxtLink: { template: '<a><slot /></a>' }, BaseModal: { template: '<div role="dialog"><slot /></div>' } },
      mocks: { $t: t, $te: (key) => t(key) !== key },
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
    expect(wrapper.get('[role="alert"]').text()).toBe('Servicio no disponible');
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
});
