import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import SecureLinkDetailModal from '../../components/secureLinks/SecureLinkDetailModal.vue';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { get_request, create_request, patch_request } = require('../../stores/services/request_http');

const detailFor = (title) => ({
  id: 7,
  title,
  type_label: 'Credenciales',
  origin_label: 'Equipo',
  status: 'active',
  team_only: false,
  created_by_name: 'Admin',
  client_name: 'Ana',
  project_name: 'Portal',
  expires_at: '2026-10-03T15:00:00Z',
  consumed_at: null,
  events: [],
});

function mountDetail(detail) {
  setActivePinia(createPinia());
  get_request.mockResolvedValue({ data: detail });
  return mount(SecureLinkDetailModal, {
    props: { modelValue: true, linkId: 7 },
    global: { stubs: { BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' } } },
  });
}

describe('SecureLinkDetailModal title copy', () => {
  let originalClipboard;
  let originalUseI18n;
  const wrappers = [];

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    originalClipboard = navigator.clipboard;
    originalUseI18n = global.useI18n;
    global.useI18n = () => ({ t: (key) => key });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
  });

  afterEach(() => {
    wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: originalClipboard });
    global.useI18n = originalUseI18n;
  });

  // Falla si el botón copia una etiqueta, un secreto o una versión truncada en lugar del título completo.
  it.each([
    ['normal title', 'Acceso de administración'],
    ['accented title', 'Acceso ágil para María'],
    ['long title', `Título ${'de acceso '.repeat(14).trim()}`],
  ])('copies the exact %s without mutating the link', async (_label, title) => {
    const wrapper = mountDetail(detailFor(title));
    wrappers.push(wrapper);
    await flushPromises();

    await wrapper.get('[data-testid="secure-link-copy-title"]').trigger('click');
    await flushPromises();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(title);
    expect(wrapper.get('[data-testid="secure-link-title-editor"] h3').text()).toBe(title);
    expect(create_request).not.toHaveBeenCalled();
    expect(patch_request).not.toHaveBeenCalled();
  });

  // Falla si, tras renombrar, el botón conserva el título anterior en el portapapeles.
  it('copies the renamed title from the current detail', async () => {
    const wrapper = mountDetail(detailFor('Acceso inicial'));
    wrappers.push(wrapper);
    await flushPromises();
    patch_request.mockResolvedValueOnce({ data: detailFor('Acceso actualizado') });

    await wrapper.get('[data-testid="secure-link-title-edit"]').trigger('click');
    await wrapper.get('[data-testid="secure-link-title-input"]').setValue('Acceso actualizado');
    await wrapper.get('[data-testid="secure-link-title-form"]').trigger('submit');
    await flushPromises();
    await wrapper.get('[data-testid="secure-link-copy-title"]').trigger('click');
    await flushPromises();

    expect(patch_request).toHaveBeenCalledWith('secure-links/7/', { title: 'Acceso actualizado' });
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Acceso actualizado');
    expect(create_request).not.toHaveBeenCalled();
  });

  // Falla si un rechazo del portapapeles intenta guardar el título o altera la ficha abierta.
  it('shows copy feedback after a clipboard error without sending a mutation', async () => {
    navigator.clipboard.writeText.mockRejectedValueOnce(new Error('clipboard denied'));
    const wrapper = mountDetail(detailFor('Título intacto'));
    wrappers.push(wrapper);
    await flushPromises();

    await wrapper.get('[data-testid="secure-link-copy-title"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[role="status"]').text()).toBe('secureLinks.panel.titleCopyFailed');
    expect(wrapper.get('[data-testid="secure-link-title-editor"] h3').text()).toBe('Título intacto');
    expect(create_request).not.toHaveBeenCalled();
    expect(patch_request).not.toHaveBeenCalled();
  });
});
