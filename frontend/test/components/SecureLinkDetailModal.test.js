/**
 * SecureLinkDetailModal: loads the audit history, shows content only on demand,
 * copies the link, revokes active links, reactivates the others (optionally
 * rotating the URL) and surfaces server errors inline.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import SecureLinkDetailModal from '../../components/secureLinks/SecureLinkDetailModal.vue';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { get_request, create_request } = require('../../stores/services/request_http');

global.useI18n = jest.fn(() => ({ t: (key) => key }));

const baseDetail = {
  id: 7, title: 'Admin', type_label: 'Credenciales', origin_label: 'Equipo', status: 'active',
  team_only: false, created_by_name: 'Admin', client_name: 'Ana', project_name: 'Portal',
  expires_at: '2026-10-03T15:00:00Z', consumed_at: null,
  events: [{ id: 1, kind: 'reveal_blocked', kind_label: 'Intento rechazado', actor_name: '', ip_address: '198.51.100.7', details: { reason: 'consumed' }, created_at: '2026-09-26T15:00:00Z' }],
};

const content = { fields: [{ key: 'password', label: 'Contraseña', kind: 'secret', value: 'S3cr3t' }] };

function mountModal(detail = baseDetail) {
  setActivePinia(createPinia());
  get_request.mockResolvedValue({ data: detail });
  return mount(SecureLinkDetailModal, {
    props: { modelValue: true, linkId: 7 },
    global: {
      stubs: {
        BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
      },
    },
  });
}

describe('SecureLinkDetailModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.assign(navigator, { clipboard: { writeText: jest.fn().mockResolvedValue(undefined) } });
  });

  it('shows the history with the rejection reason and the association', async () => {
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="secure-link-events"]').text()).toContain('IP 198.51.100.7 · ya estaba usado');
    expect(wrapper.text()).toContain('Ana · Portal');
  });

  it('reveals and hides the content on demand', async () => {
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockResolvedValueOnce({ data: content });

    await wrapper.get('[data-testid="secure-link-view-content"]').trigger('click');
    await flushPromises();
    expect(wrapper.find('[data-testid="secure-link-content"]').exists()).toBe(true);

    await wrapper.get('[data-testid="secure-link-view-content"]').trigger('click');
    expect(wrapper.find('[data-testid="secure-link-content"]').exists()).toBe(false);
  });

  it('copies the link URL fetched from the server', async () => {
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockResolvedValueOnce({ data: { url: 'https://x/view#tok' } });

    await wrapper.get('[data-testid="secure-link-copy-url"]').trigger('click');
    await flushPromises();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://x/view#tok');
  });

  it('revokes an active link and reports the change', async () => {
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockResolvedValueOnce({ data: { ...baseDetail, status: 'revoked' } });

    await wrapper.get('[data-testid="secure-link-revoke"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('secure-links/7/revoke/', {});
    expect(wrapper.emitted('changed')).toHaveLength(1);
  });

  it('reactivates a used link generating a new URL and copies it', async () => {
    const wrapper = mountModal({ ...baseDetail, status: 'consumed', consumed_at: '2026-09-26T15:30:00Z' });
    await flushPromises();
    create_request.mockResolvedValueOnce({ data: { ...baseDetail, url: 'https://x/view#new' } });

    await wrapper.get('[data-testid="secure-link-reactivate-rotate"] input').setValue(true);
    await wrapper.get('[data-testid="secure-link-reactivate-submit"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('secure-links/7/reactivate/', { validity_days: 7, rotate: true });
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://x/view#new');
  });

  it('opens the edit form with the current values', async () => {
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockResolvedValueOnce({ data: content });

    await wrapper.get('[data-testid="secure-link-edit"]').trigger('click');
    await flushPromises();

    expect(wrapper.emitted('edit')[0][0].fields).toEqual({ password: 'S3cr3t' });
  });

  it('shows the server message when an action fails', async () => {
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockRejectedValueOnce({ response: { status: 500, data: { error: 'No pudimos descifrar este contenido.' } } });

    await wrapper.get('[data-testid="secure-link-view-content"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('No pudimos descifrar este contenido.');
  });
});
