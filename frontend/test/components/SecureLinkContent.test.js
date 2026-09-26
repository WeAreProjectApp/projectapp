/**
 * SecureLinkContent: revealed values start masked for secrets, are rendered as
 * text (never HTML) and can be copied field by field.
 */
import { mount } from '@vue/test-utils';
import SecureLinkContent from '../../components/secureLinks/SecureLinkContent.vue';

global.useI18n = jest.fn(() => ({
  t: (key, params) => (params?.label ? `${key}:${params.label}` : key),
}));

const fields = [
  { key: 'service', label: 'Servicio', kind: 'text', value: '<b>Django</b>' },
  { key: 'password', label: 'Contraseña', kind: 'secret', value: 'S3cr3t!' },
];

function mountContent() {
  return mount(SecureLinkContent, { props: { fields } });
}

describe('SecureLinkContent', () => {
  beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: jest.fn().mockResolvedValue(undefined) } });
  });

  it('masks secrets until the user chooses to show them', async () => {
    const wrapper = mountContent();
    const secret = wrapper.get('[data-testid="secure-link-text-password"]');

    expect(secret.text()).toBe('••••••••');
    await wrapper.get('[data-testid="secure-link-reveal-password"]').trigger('click');
    expect(secret.text()).toBe('S3cr3t!');
  });

  it('renders user content as text instead of HTML', () => {
    const wrapper = mountContent();

    expect(wrapper.get('[data-testid="secure-link-text-service"]').text()).toBe('<b>Django</b>');
    expect(wrapper.find('b').exists()).toBe(false);
  });

  it('copies the exact value of a field even while it is masked', async () => {
    const wrapper = mountContent();

    await wrapper.get('[data-testid="secure-link-copy-password"]').trigger('click');

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('S3cr3t!');
  });
});
