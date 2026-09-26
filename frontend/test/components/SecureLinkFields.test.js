/**
 * SecureLinkFields renders the catalog fields for the chosen type: secrets are
 * masked inputs with a show toggle, long secrets and text areas are
 * multi-line, labels follow the language and every edit emits the new object.
 */
import { mount } from '@vue/test-utils';
import SecureLinkFields from '../../components/secureLinks/SecureLinkFields.vue';
import SecureLinkStatusBadge from '../../components/secureLinks/SecureLinkStatusBadge.vue';

global.useI18n = jest.fn(() => ({ t: (key) => key }));

const type = {
  key: 'server_access',
  label_es: 'Acceso a servidor',
  label_en: 'Server access',
  fields: [
    { key: 'host', label_es: 'Host o IP', label_en: 'Host or IP', kind: 'text', required: true, max_length: 200 },
    { key: 'url', label_es: 'URL', label_en: 'URL', kind: 'url', required: false, max_length: 500 },
    { key: 'password', label_es: 'Contraseña', label_en: 'Password', kind: 'secret', required: true, max_length: 2000 },
    { key: 'credential', label_es: 'Llave privada', label_en: 'Private key', kind: 'secret', required: true, max_length: 10000 },
    { key: 'note', label_es: 'Nota', label_en: 'Note', kind: 'textarea', required: false, max_length: 2000 },
  ],
};

function mountFields(props = {}) {
  return mount(SecureLinkFields, { props: { type, modelValue: { host: 'srv' }, ...props } });
}

describe('SecureLinkFields', () => {
  it('masks short secrets and reveals them with the toggle', async () => {
    const wrapper = mountFields();
    const password = wrapper.get('[data-testid="secure-link-field-password"]');

    expect(password.attributes('type')).toBe('password');
    await wrapper.get('[data-testid="secure-link-field-toggle-password"]').trigger('click');
    expect(password.attributes('type')).toBe('text');
  });

  it('uses multi-line controls for private keys and notes and a url input for links', () => {
    const wrapper = mountFields();

    expect(wrapper.get('[data-testid="secure-link-field-credential"]').element.tagName).toBe('TEXTAREA');
    expect(wrapper.get('[data-testid="secure-link-field-note"]').element.tagName).toBe('TEXTAREA');
    expect(wrapper.get('[data-testid="secure-link-field-url"]').attributes('type')).toBe('url');
  });

  it('labels fields in the recipient language and shows server errors', () => {
    const wrapper = mountFields({ language: 'en', errors: { password: 'Este campo es obligatorio.' } });

    expect(wrapper.text()).toContain('Host or IP');
    expect(wrapper.text()).toContain('Este campo es obligatorio.');
  });

  it('emits the whole value object when one field changes', async () => {
    const wrapper = mountFields();

    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('S3cr3t');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([{ host: 'srv', password: 'S3cr3t' }]);
  });

  it('renders nothing when no type is selected yet', () => {
    const wrapper = mountFields({ type: null });

    expect(wrapper.get('[data-testid="secure-link-fields"]').element.tagName).toBe('DIV');
    expect(wrapper.findAll('input, textarea')).toHaveLength(0);
  });
});

describe('SecureLinkStatusBadge', () => {
  it.each([
    ['active', 'Activo'], ['consumed', 'Usado'], ['expired', 'Vencido'], ['revoked', 'Revocado'], ['other', 'other'],
  ])('labels the %s status', (status, label) => {
    const wrapper = mount(SecureLinkStatusBadge, { props: { status } });

    expect(wrapper.text()).toBe(label);
  });
});
