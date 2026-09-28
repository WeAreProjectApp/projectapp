/**
 * SecureLinkFormModal: requires a title, creates links with validity and
 * language, edits metadata without resending the secret unless content was
 * loaded, and maps server field errors to their inputs.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { ref } from 'vue';
import es from '../../locales/secureLinks/es';
import { createPinia, setActivePinia } from 'pinia';
import SecureLinkFormModal from '../../components/secureLinks/SecureLinkFormModal.vue';
import { useSecureLinksStore } from '../../stores/secure_links';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { get_request, create_request, patch_request } = require('../../stores/services/request_http');

global.useI18n = jest.fn(() => ({
  locale: ref('es-co'),
  t: (key, params = {}) => {
    const value = key.replace('secureLinks.', '').split('.').reduce((part, name) => part?.[name], es) || key;
    return value.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? '');
  },
}));

const types = [{
  key: 'credentials', label_es: 'Credenciales', label_en: 'Credentials',
  fields: [{ key: 'password', label_es: 'Contraseña', label_en: 'Password', kind: 'secret', required: true, max_length: 2000 }],
}, {
  key: 'custom', label_es: 'Personalizado', label_en: 'Custom',
  fields: [
    { key: 'custom_name', label_es: 'Nombre del tipo', label_en: 'Type name', kind: 'text', required: true, max_length: 200 },
    { key: 'content', label_es: 'Contenido', label_en: 'Content', kind: 'textarea', required: true, max_length: 15000 },
  ],
}];

const stubs = {
  NuxtLink: true,
  BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>' },
  ClientAutocomplete: {
    name: 'ClientAutocomplete',
    props: ['modelValue'],
    emits: ['update:modelValue', 'select'],
    template: '<div data-testid="client-stub" />',
  },
  ProjectSelect: { props: ['modelValue'], template: '<div data-testid="project-stub" />' },
};

async function mountForm(props = {}, catalog = types) {
  setActivePinia(createPinia());
  useSecureLinksStore().types = catalog;
  const wrapper = mount(SecureLinkFormModal, { props: { modelValue: false, ...props }, global: { stubs } });
  await wrapper.setProps({ modelValue: true });
  await flushPromises();
  return wrapper;
}

describe('SecureLinkFormModal', () => {
  beforeEach(() => {
    get_request.mockReset(); create_request.mockReset(); patch_request.mockReset();
  });

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
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('rejected-by-server');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(wrapper.text()).toContain('Este campo es obligatorio.');
    expect(wrapper.emitted('saved')).toBeUndefined();
  });
  it('rejects missing content before sending a request', async () => {
    const wrapper = await mountForm();
    await wrapper.get('[data-testid="secure-link-title"]').setValue('Acceso');

    await wrapper.get('form').trigger('submit');

    expect(wrapper.text()).toContain('Este campo es obligatorio.');
    expect(create_request).not.toHaveBeenCalled();
  });

  it('creates custom content without associations', async () => {
    const wrapper = await mountForm();
    create_request.mockResolvedValueOnce({ data: { id: 10, url: 'https://example.test/#token' } });
    await wrapper.get('[data-testid="secure-link-type"]').setValue('custom');
    await wrapper.get('[data-testid="secure-link-title"]').setValue('Referencia');
    await wrapper.get('[data-testid="secure-link-field-custom_name"]').setValue('Instrucciones');
    await wrapper.get('[data-testid="secure-link-field-content"]').setValue('  Texto\ncon espacios  ');

    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith('secure-links/create/', expect.objectContaining({
      secret_type: 'custom', fields: { custom_name: 'Instrucciones', content: '  Texto\ncon espacios  ' },
      client: null, project: null,
    }));
    expect(wrapper.emitted('saved')[0][0].id).toBe(10);
  });

  it('recovers the catalog through the retry button', async () => {
    get_request.mockRejectedValueOnce(new Error('offline'));
    get_request.mockResolvedValueOnce({ data: { types } });
    const wrapper = await mountForm({}, []);

    expect(wrapper.get('[data-testid="secure-link-save"]').element.disabled).toBe(true);
    expect(wrapper.text()).toContain('No pudimos cargar los tipos de información.');
    await wrapper.get('[data-testid="secure-link-types-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="secure-link-save"]').element.disabled).toBe(false);
    expect(wrapper.find('[data-testid="secure-link-field-password"]').exists()).toBe(true);
  });

  it('keeps typed content after an HTML server error', async () => {
    const wrapper = await mountForm();
    create_request.mockRejectedValueOnce({ response: { status: 500, data: '<html>private traceback</html>' } });
    await wrapper.get('[data-testid="secure-link-title"]').setValue('Acceso');
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('do-not-lose-this');

    await wrapper.get('form').trigger('submit');
    await flushPromises();

    // Fails if a rejected save clears the password or exposes a server traceback.
    expect(wrapper.get('[data-testid="secure-link-general-error"]').text()).toBe('No se pudo crear el enlace.');
    expect(wrapper.text()).not.toContain('private traceback');
    expect(wrapper.get('[data-testid="secure-link-field-password"]').element.value).toBe('do-not-lose-this');
  });

  it('displays errors that have no visible field', async () => {
    const wrapper = await mountForm();
    create_request.mockRejectedValueOnce({ response: { status: 400, data: { recipient: ['Revisa el destinatario.'] } } });
    await wrapper.get('[data-testid="secure-link-title"]').setValue('Acceso');
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('test-value');

    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(wrapper.get('[data-testid="secure-link-general-error"]').text()).toBe('Revisa el destinatario.');
  });

  it('opens a new form without the previous credential', async () => {
    const wrapper = await mountForm();
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('previous-secret');
    await wrapper.get('[data-testid="secure-link-field-toggle-password"]').trigger('click');

    await wrapper.setProps({ modelValue: false });
    await wrapper.setProps({ modelValue: true });
    await flushPromises();

    const password = wrapper.get('[data-testid="secure-link-field-password"]');
    expect(password.element.value).toBe('');
    expect(password.attributes('type')).toBe('password');
    expect(password.attributes('autocomplete')).toBe('new-password');
  });

  it('discards incompatible fields when editing the content type', async () => {
    const wrapper = await mountForm({
      link: { id: 7, secret_type: 'credentials', title: 'Acceso' },
      initialFields: { password: 'old-secret' },
    });
    patch_request.mockResolvedValueOnce({ data: { id: 7 } });
    await wrapper.get('[data-testid="secure-link-type"]').setValue('custom');
    await wrapper.get('[data-testid="secure-link-field-custom_name"]').setValue('Notas');
    await wrapper.get('[data-testid="secure-link-field-content"]').setValue('new-content');

    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(patch_request).toHaveBeenCalledWith('secure-links/7/', expect.objectContaining({
      secret_type: 'custom', fields: { custom_name: 'Notas', content: 'new-content' },
    }));
  });

  it('ignores a second submit while creation is pending', async () => {
    const wrapper = await mountForm();
    let complete;
    create_request.mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }));
    await wrapper.get('[data-testid="secure-link-title"]').setValue('Acceso');
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('test-value');

    await wrapper.get('form').trigger('submit');
    await wrapper.get('form').trigger('submit');
    complete({ data: { id: 1 } });
    await flushPromises();

    expect(create_request).toHaveBeenCalledTimes(1);
  });

  it('disables cancellation while creation is pending', async () => {
    const wrapper = await mountForm();
    let complete;
    create_request.mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }));
    await wrapper.get('[data-testid="secure-link-title"]').setValue('Acceso');
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('keep-this-password');

    await wrapper.get('[data-testid="secure-link-form"]').trigger('submit');

    // Fails if Cancel closes a form while its secret is still being saved.
    expect(wrapper.get('[data-testid="secure-link-cancel"]').element.disabled).toBe(true);
    complete({ data: { id: 1 } });
    await flushPromises();
  });

});
