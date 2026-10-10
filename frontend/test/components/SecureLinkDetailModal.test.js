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

const { get_request, create_request, patch_request } = require('../../stores/services/request_http');

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

  it('refreshes the delivery metadata after a manual send mark', async () => {
    // Fails if manual delivery posts to the wrong endpoint or leaves the panel on its stale Ready metadata.
    const sentDetail = {
      ...baseDetail,
      lifecycle_status: 'sent',
      sent_at: '2026-09-29T15:20:00Z',
    };
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockResolvedValueOnce({ data: sentDetail });
    get_request.mockResolvedValueOnce({ data: sentDetail });

    await wrapper.get('[data-testid="secure-link-mark-sent"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('secure-links/7/mark-sent/', {});
    expect(wrapper.emitted('changed')).toHaveLength(1);
    expect(wrapper.get('[data-testid="secure-link-status-sent"]').text()).toBe('secureLinks.states.sent');
    expect(wrapper.text()).toContain('Mar, 29 sep 2026, 10:20');
  });

  it.each([
    ['team-only', { ...baseDetail, team_only: true }],
    ['already-sent', { ...baseDetail, sent_at: '2026-09-29T15:20:00Z' }],
  ])('does not offer manual delivery for a %s link', async (_label, detail) => {
    // Fails if team-owned or already-sent links can be recorded as manually delivered again.
    const wrapper = mountModal(detail);
    await flushPromises();

    expect(wrapper.findAll('[data-testid="secure-link-mark-sent"]')).toHaveLength(0);
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

  it('retries a deleted detail after a 404 error', async () => {
    get_request.mockRejectedValueOnce({ response: { status: 404, data: { error: 'No existe.' } } });
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="secure-link-detail-error"]').text()).toContain('secureLinks.panel.deleted');
    await wrapper.get('[data-testid="secure-link-detail-retry"]').trigger('click');
    await flushPromises();

    // Fails if a 404 keeps the detail modal in its loading state or cannot recover.
    expect(wrapper.get('[data-testid="secure-link-events"]').text()).toContain('IP 198.51.100.7 · ya estaba usado');
    expect(wrapper.text()).not.toContain('secureLinks.panel.deleted');
  });

  it('does not render late content after selecting another link', async () => {
    let resolveContent;
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockImplementationOnce(() => new Promise((resolve) => { resolveContent = resolve; }));

    await wrapper.get('[data-testid="secure-link-view-content"]').trigger('click');
    get_request.mockResolvedValue({ data: { ...baseDetail, id: 8, title: 'Other secure link' } });
    await wrapper.setProps({ linkId: 8 });
    await flushPromises();
    resolveContent({ data: content });
    await flushPromises();

    // Fails if a late decrypt response reveals the former link's secret in the current modal.
    expect(wrapper.text()).toContain('Other secure link');
    expect(wrapper.text()).not.toContain('S3cr3t');
    expect(wrapper.emitted('changed')).toBeUndefined();
  });

  it('does not render the previous detail after switching links', async () => {
    let resolveFirst;
    get_request
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce({ data: { ...baseDetail, id: 8, title: 'Replacement link' } });
    const wrapper = mountModal();

    await wrapper.setProps({ linkId: 8 });
    await flushPromises();
    resolveFirst({ data: baseDetail });
    await flushPromises();

    // Fails if a detail response from the prior link replaces the selected link.
    expect(wrapper.text()).toContain('Replacement link');
  });

  it('offers a single edit option, through the content', async () => {
    const wrapper = mountModal();
    await flushPromises();

    // Fails if the detail shows a second "Editar" beside "Editar contenido" again.
    expect(wrapper.findAll('[data-testid="secure-link-edit"]')).toHaveLength(0);
    expect(wrapper.findAll('[data-testid="secure-link-edit-content"]')).toHaveLength(1);
  });

  it('renames the link in place with a title-only update', async () => {
    const renamed = {
      ...baseDetail,
      title: 'Admin del portal',
      events: [{ id: 2, kind: 'updated', kind_label: 'Editado', actor_name: 'Admin', ip_address: '', details: {}, created_at: '2026-10-09T15:00:00Z' }],
    };
    const wrapper = mountModal();
    await flushPromises();
    patch_request.mockResolvedValueOnce({ data: renamed });

    await wrapper.get('[data-testid="secure-link-title-edit"]').trigger('click');
    await wrapper.get('[data-testid="secure-link-title-input"]').setValue('  Admin del portal ');
    await wrapper.get('[data-testid="secure-link-title-form"]').trigger('submit');
    await flushPromises();

    // Fails if renaming decrypts the secret or sends the associations along with the title.
    expect(patch_request).toHaveBeenCalledWith('secure-links/7/', { title: 'Admin del portal' });
    expect(create_request).not.toHaveBeenCalled();
    expect(wrapper.emitted('changed')).toHaveLength(1);
    expect(wrapper.get('[data-testid="secure-link-title-editor"] h3').text()).toBe('Admin del portal');
    expect(wrapper.get('[data-testid="secure-link-events"]').text()).toContain('Editado');
  });

  it('loads decrypted fields before opening content editing', async () => {
    const wrapper = mountModal();
    await flushPromises();
    create_request.mockResolvedValueOnce({ data: content });

    await wrapper.get('[data-testid="secure-link-edit-content"]').trigger('click');
    await flushPromises();

    // Fails if content editing opens without the decrypted field values.
    expect(create_request).toHaveBeenCalledWith('secure-links/7/content/', {});
    expect(wrapper.emitted('edit')[0][0]).toEqual({ link: baseDetail, fields: { password: 'S3cr3t' } });
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
