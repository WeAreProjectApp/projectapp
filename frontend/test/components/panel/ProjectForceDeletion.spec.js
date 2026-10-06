import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ProjectStateTransitionModal from '../../../components/panel/projects/ProjectStateTransitionModal.vue';
import { usePanelProjectsStore } from '../../../stores/panel_projects';
import { useProjectStateStore } from '../../../stores/project_states';
import translations from '../../../locales/projectAccess/es';

const PROJECT = {
  id: 7,
  name: 'Proyecto siete',
  status_label: 'Activo',
  current_state: { id: 2, operational_effect: 'operating' },
};
const PROJECT_EIGHT = {
  ...PROJECT,
  id: 8,
  name: 'Proyecto ocho',
};
const PREVIEW_SEVEN = {
  can_delete: true,
  impact_token: 'force-token-7',
  dependencies: [{ key: 'documents', label: 'Documentos', description: 'Archivos del proyecto.', count: 2 }],
  blockers: [],
};
const PREVIEW_EIGHT = {
  can_delete: true,
  impact_token: 'force-token-8',
  dependencies: [{ key: 'contracts', label: 'Contratos', description: 'Acuerdos del proyecto.', count: 4 }],
  blockers: [],
};
const t = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], translations) || key;

function mountModal(props = {}) {
  const pinia = createPinia();
  setActivePinia(pinia);
  useProjectStateStore().states = [{ id: 2, name: 'Activo', is_active: true }];
  const projectStore = usePanelProjectsStore();
  jest.spyOn(projectStore, 'previewDeletion').mockResolvedValue({ success: true, data: PREVIEW_SEVEN });
  jest.spyOn(projectStore, 'deleteProject').mockResolvedValue({ success: true });
  const wrapper = mount(ProjectStateTransitionModal, {
    props: {
      open: true,
      project: PROJECT,
      allowForceDelete: true,
      isSuperuser: true,
      ...props,
    },
    global: {
      stubs: {
        BaseModal: {
          props: ['modelValue'],
          emits: ['close'],
          template: '<div v-if="modelValue" role="dialog"><button data-testid="modal-request-close" @click="$emit(\'close\')">Cerrar</button><slot /><slot name="footer" /></div>',
        },
        BaseAlert: { template: '<div v-bind="$attrs"><slot /></div>' },
        BaseBadge: { template: '<span><slot /></span>' },
        BaseFormField: {
          props: ['label', 'hint', 'required'],
          template: '<label>{{ label }}<slot :error-id="undefined" /></label>',
        },
        BaseModalActions: { template: '<div><slot /></div>' },
        BaseToggle: {
          props: ['modelValue', 'disabled', 'onClass'],
          emits: ['update:modelValue'],
          template: '<button v-bind="$attrs" role="switch" :aria-checked="modelValue" :disabled="disabled" @click="$emit(\'update:modelValue\', !modelValue)">Alternar</button>',
        },
        BaseInput: {
          props: ['modelValue', 'disabled'],
          emits: ['update:modelValue'],
          template: '<input v-bind="$attrs" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseTextarea: { template: '<textarea />' },
        BaseButton: {
          props: ['disabled', 'loading'],
          emits: ['click'],
          template: '<button v-bind="$attrs" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
        },
      },
      mocks: { $t: t, $te: (key) => t(key) !== key },
    },
  });
  return { wrapper, projectStore };
}

async function enterForceMode(wrapper) {
  await wrapper.get('[data-testid="project-force-delete-toggle"]').trigger('click');
  await flushPromises();
}

describe('ProjectStateTransitionModal force deletion', () => {
  beforeEach(() => jest.clearAllMocks());
  afterEach(() => jest.restoreAllMocks());

  // Fails if a routine status transition exposes the destructive alternative.
  it.each([
    ['a direct state transition', { allowForceDelete: false, isSuperuser: true }],
    ['a non-superuser transition', { allowForceDelete: true, isSuperuser: false }],
  ])('hides force deletion for %s', async (_label, props) => {
    const { wrapper } = mountModal(props);
    await flushPromises();

    expect(wrapper.text()).not.toContain('Forzar eliminación');
  });

  // Fails if the authorized recovery path sends a preselected deletion category.
  it('loads the force review for an authorized deletion path', async () => {
    const { wrapper, projectStore } = mountModal();

    await enterForceMode(wrapper);

    expect(projectStore.previewDeletion).toHaveBeenCalledWith(7, { force: true, deleteKeys: [] });
    expect(wrapper.get('[data-testid="project-force-delete-dependencies"]').text()).toContain('Documentos (2)');
    expect(wrapper.get('[data-testid="project-delete-category-documents"]').attributes('aria-checked')).toBe('false');
    expect(wrapper.get('[data-testid="project-force-delete-dependencies"]').text()).toContain('Se conserva sin proyecto');
  });

  // Fails if a previous DELETE confirmation survives leaving the destructive review.
  it('clears the confirmation after leaving force mode', async () => {
    const { wrapper } = mountModal();
    await enterForceMode(wrapper);
    await wrapper.get('[data-testid="project-force-delete-confirmation"]').setValue('DELETE');

    await wrapper.get('[data-testid="project-force-delete-toggle"]').trigger('click');
    await wrapper.get('[data-testid="project-force-delete-toggle"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="project-force-delete-confirmation"]').element.value).toBe('');
  });

  // Fails if an old project's preview can populate a newly opened project.
  it('discards a stale preview after selecting another project', async () => {
    let resolveFirstPreview;
    const firstPreview = new Promise((resolve) => { resolveFirstPreview = resolve; });
    const { wrapper, projectStore } = mountModal();
    projectStore.previewDeletion
      .mockReturnValueOnce(firstPreview)
      .mockResolvedValueOnce({ success: true, data: PREVIEW_EIGHT });

    await wrapper.get('[data-testid="project-force-delete-toggle"]').trigger('click');
    await wrapper.setProps({ project: PROJECT_EIGHT });
    resolveFirstPreview({ success: true, data: PREVIEW_SEVEN });
    await flushPromises();
    await enterForceMode(wrapper);

    expect(projectStore.previewDeletion).toHaveBeenLastCalledWith(8, { force: true, deleteKeys: [] });
    expect(wrapper.get('[data-testid="project-force-delete-dependencies"]').text()).toContain('Contratos (4)');
  });

  // Fails if lowercase or padded confirmations authorize permanent deletion.
  it.each(['delete', 'DELETE '])('rejects the confirmation %s', async (confirmation) => {
    const { wrapper, projectStore } = mountModal();
    await enterForceMode(wrapper);
    await wrapper.get('[data-testid="project-force-delete-confirmation"]').setValue(confirmation);

    expect(wrapper.get('[data-testid="project-force-delete-confirm"]').element.disabled).toBe(true);
    expect(projectStore.deleteProject).not.toHaveBeenCalled();
  });

  // Fails if changing a category retains a DELETE confirmation or reuses the old selection token.
  it('reviews the selected category before allowing confirmation', async () => {
    const { wrapper, projectStore } = mountModal();
    await enterForceMode(wrapper);
    await wrapper.get('[data-testid="project-force-delete-confirmation"]').setValue('DELETE');

    projectStore.previewDeletion.mockResolvedValueOnce({
      success: true,
      data: { ...PREVIEW_SEVEN, impact_token: 'force-token-documents' },
    });
    await wrapper.get('[data-testid="project-delete-category-documents"]').trigger('click');
    await flushPromises();

    expect(projectStore.previewDeletion).toHaveBeenLastCalledWith(7, { force: true, deleteKeys: ['documents'] });
    expect(wrapper.get('[data-testid="project-force-delete-confirmation"]').element.value).toBe('');
    expect(wrapper.get('[data-testid="project-force-delete-dependencies"]').text()).toContain('Se elimina');
  });

  // Fails if the confirmed request drops the reviewed selection or its token.
  it('sends uppercase DELETE with the current selected categories', async () => {
    const { wrapper, projectStore } = mountModal();
    await enterForceMode(wrapper);
    projectStore.previewDeletion.mockResolvedValueOnce({
      success: true,
      data: { ...PREVIEW_SEVEN, impact_token: 'force-token-documents' },
    });
    await wrapper.get('[data-testid="project-delete-category-documents"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="project-force-delete-confirmation"]').setValue('DELETE');
    await wrapper.get('[data-testid="project-force-delete-confirm"]').trigger('click');
    await flushPromises();

    expect(projectStore.deleteProject).toHaveBeenCalledWith(7, {
      force: true,
      delete_keys: ['documents'],
      confirmation: 'DELETE',
      impact_token: 'force-token-documents',
    });
    expect(wrapper.emitted('deleted')[0]).toEqual([{ success: true }]);
  });

  // Fails if a stale-impact conflict closes the modal or reuses the old confirmation.
  it('keeps the modal open after a stale-impact conflict', async () => {
    const { wrapper, projectStore } = mountModal();
    projectStore.deleteProject.mockResolvedValue({
      success: false,
      message: 'Las dependencias cambiaron.',
      preview: { ...PREVIEW_EIGHT, blockers: [{ message: 'Hay un contrato compartido.' }] },
    });
    await enterForceMode(wrapper);
    await wrapper.get('[data-testid="project-force-delete-confirmation"]').setValue('DELETE');
    await wrapper.get('[data-testid="project-force-delete-confirm"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="project-force-delete-confirmation"]').element.value).toBe('');
    expect(wrapper.get('[data-testid="project-force-delete-error"]').text()).toBe('Las dependencias cambiaron.');
    expect(wrapper.emitted('close')).toBeUndefined();
  });

  // Fails if a pending destructive request accepts a duplicate submission or modal close.
  it('blocks another deletion request while the first one is pending', async () => {
    let resolveDelete;
    const pendingDelete = new Promise((resolve) => { resolveDelete = resolve; });
    const { wrapper, projectStore } = mountModal();
    projectStore.deleteProject.mockReturnValue(pendingDelete);
    await enterForceMode(wrapper);
    await wrapper.get('[data-testid="project-force-delete-confirmation"]').setValue('DELETE');

    await wrapper.get('[data-testid="project-force-delete-confirm"]').trigger('click');
    await wrapper.get('[data-testid="project-force-delete-confirm"]').trigger('click');
    await wrapper.get('[data-testid="modal-request-close"]').trigger('click');

    expect(projectStore.deleteProject).toHaveBeenCalledTimes(1);
    expect(wrapper.emitted('close')).toBeUndefined();
    resolveDelete({ success: true });
    await flushPromises();
  });
});
