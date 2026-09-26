/**
 * SecureLinkFormModal: requires a title, creates links with validity and
 * language, edits metadata without resending the secret unless content was
 * loaded, and maps server field errors to their inputs.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import SecureLinkFormModal from '../../components/secureLinks/SecureLinkFormModal.vue';
import { useSecureLinksStore } from '../../stores/secure_links';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { create_request, patch_request } = require('../../stores/services/request_http');

global.useI18n = jest.fn(() => ({ t: (key) => key }));

const types = [{
  key: 'credentials', label_es: 'Credenciales', label_en: 'Credentials',
  fields: [{ key: 'password', label_es: 'Contraseña', label_en: 'Password', kind: 'secret', required: true, max_length: 2000 }],
}];

const stubs = {
  BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
  ClientAutocomplete: {
    name: 'ClientAutocomplete',
    props: ['modelValue'],
    emits: ['update:modelValue', 'select'],
    template: '<div data-testid="client-stub" />',
  },
  ProjectSelect: { props: ['modelValue'], template: '<div data-testid="project-stub" />' },
};

async function mountForm(props = {}) {
  setActivePinia(createPinia());
  useSecureLinksStore().types = types;
  const wrapper = mount(SecureLinkFormModal, { props: { modelValue: false, ...props }, global: { stubs } });
  await wrapper.setProps({ modelValue: true });
  await flushPromises();
  return wrapper;
}

describe('SecureLinkFormModal', () => {
  beforeEach(() => jest.clearAllMocks());

  it('asks for a title before calling the server', async () => {
    const wrapper = await mountForm();

    await wrapper.get('form').trigger('submit');

    expect(wrapper.text()).toContain('Escribe un título para reconocer el enlace.');
    expect(create_request).not.toHaveBeenCalled();
  });

  it('creates a link with its content, client, validity and language', async () => {
    const wrapper = await mountForm();
    create_request.mockResolvedValueOnce({ data: { id: 9, url: 'https://x#t' } });

    await wrapper.get('[data-testid="secure-link-title"]').setValue('Admin');
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('S3cr3t');
    const client = wrapper.findComponent({ name: 'ClientAutocomplete' });
    client.vm.$emit('update:modelValue', 4);
    client.vm.$emit('select', { id: 4, name: 'Ana' });
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('secure-links/create/', {
      secret_type: 'credentials', title: 'Admin', fields: { password: 'S3cr3t' },
      client: 4, project: null, language: 'es', validity_days: 7,
    });
    expect(wrapper.emitted('saved')[0][0].url).toBe('https://x#t');
  });

  it('edits only metadata when the content was not loaded', async () => {
    const link = { id: 7, title: 'Viejo', secret_type: 'credentials', client: null, project: null, language: 'es' };
    const wrapper = await mountForm({ link });
    patch_request.mockResolvedValueOnce({ data: { ...link, title: 'Nuevo' } });

    await wrapper.get('[data-testid="secure-link-title"]').setValue('Nuevo');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(patch_request).toHaveBeenCalledWith('secure-links/7/', { title: 'Nuevo', client: null, project: null });
  });

  it('shows the server error on the missing secret field', async () => {
    const wrapper = await mountForm();
    create_request.mockRejectedValueOnce({ response: { status: 400, data: { error: 'Revisa los datos del formulario.', password: ['Este campo es obligatorio.'] } } });

    await wrapper.get('[data-testid="secure-link-title"]').setValue('Sin clave');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(wrapper.text()).toContain('Este campo es obligatorio.');
    expect(wrapper.emitted('saved')).toBeUndefined();
  });
});
