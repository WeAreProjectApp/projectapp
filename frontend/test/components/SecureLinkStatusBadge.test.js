import { mount } from '@vue/test-utils';
import SecureLinkStatusBadge from '../../components/secureLinks/SecureLinkStatusBadge.vue';

const labels = {
  'secureLinks.states.ready': 'Listo para compartir',
  'secureLinks.states.sent': 'Enviado',
  'secureLinks.states.opened': 'Abierto',
  'secureLinks.states.expired': 'Vencido',
  'secureLinks.states.revoked': 'Revocado',
  'secureLinks.states.receivedReady': 'Disponible para abrir',
};

global.useI18n = jest.fn(() => ({ t: (key) => labels[key] || key }));

describe('SecureLinkStatusBadge', () => {
  it.each([
    ['ready', false, 'secure-link-status-ready', 'Listo para compartir'],
    ['sent', false, 'secure-link-status-sent', 'Enviado'],
    ['opened', false, 'secure-link-status-opened', 'Abierto'],
    ['expired', false, 'secure-link-status-expired', 'Vencido'],
    ['revoked', false, 'secure-link-status-revoked', 'Revocado'],
    ['active', false, 'secure-link-status-ready', 'Listo para compartir'],
    ['consumed', false, 'secure-link-status-opened', 'Abierto'],
    ['ready', true, 'secure-link-status-ready', 'Disponible para abrir'],
  ])('renders %s as %s with its localized lifecycle label', (status, teamOnly, testid, label) => {
    // Fails if panel rows restore legacy Active/Used labels or call a received link ready to share.
    const wrapper = mount(SecureLinkStatusBadge, { props: { status, teamOnly } });

    expect(wrapper.get(`[data-testid="${testid}"]`).text()).toBe(label);
  });
});
