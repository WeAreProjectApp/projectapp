import { ref } from 'vue';
import { mount } from '@vue/test-utils';
import ProjectAccessModal from '../../components/panel/projects/ProjectAccessModal.vue';

const mockGoToPlatform = jest.fn();
const mockIsBridging = ref(false);

jest.mock('../../composables/usePanelToPlatformBridge', () => ({
  usePanelToPlatformBridge: () => ({
    goToPlatform: mockGoToPlatform,
    isBridging: mockIsBridging,
  }),
}));

function mountAccessModal() {
  global.useI18n = () => ({ t: (key) => key });
  return mount(ProjectAccessModal, {
    props: { open: true, project: { id: 45, name: 'Proyecto de prueba' } },
    global: {
      stubs: {
        BaseModal: { props: ['modelValue'], template: '<section v-if="modelValue"><slot /></section>' },
        EntityHistoryTabs: { template: '<div><slot /></div>' },
        ProjectAccessEditor: { template: '<div />' },
        ProjectClientAccessPolicyEditor: { template: '<div />' },
      },
    },
  });
}

describe('ProjectAccessModal', () => {
  afterEach(() => {
    jest.clearAllMocks();
    mockIsBridging.value = false;
    delete global.useI18n;
  });

  // Falla si el detalle abre por nombre u omite el acceso directo al espacio del mismo proyecto.
  it('opens the exact platform project from the detail header', async () => {
    const wrapper = mountAccessModal();

    const spaceLink = wrapper.get('[data-testid="project-detail-space-link"]');
    expect(spaceLink.text()).toContain('Abrir espacio en la plataforma');
    await spaceLink.trigger('click');

    expect(mockGoToPlatform).toHaveBeenCalledWith('/platform/projects/45');
    wrapper.unmount();
  });
});
