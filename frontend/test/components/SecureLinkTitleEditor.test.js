/**
 * SecureLinkTitleEditor: renames a secure link in place from its detail.
 * Saves a trimmed, changed title; Escape cancels without closing the detail
 * modal; invalid titles never reach the server; server errors stay next to
 * the field with the draft intact.
 */
import { flushPromises, mount } from '@vue/test-utils';
import SecureLinkTitleEditor from '../../components/secureLinks/SecureLinkTitleEditor.vue';

global.useI18n = jest.fn(() => ({
  t: (key, params = {}) => (params.max ? `${key}:${params.max}` : key),
}));

const mounted = [];

function mountEditor(props = {}) {
  const wrapper = mount(SecureLinkTitleEditor, {
    props: { title: 'Admin', save: jest.fn().mockResolvedValue({ success: true }), ...props },
    attachTo: document.body,
    global: { stubs: { NuxtLink: true } },
  });
  mounted.push(wrapper);
  return wrapper;
}

async function startEditing(wrapper, value) {
  await wrapper.get('[data-testid="secure-link-title-edit"]').trigger('click');
  await flushPromises();
  if (value !== undefined) await wrapper.get('[data-testid="secure-link-title-input"]').setValue(value);
}

async function submit(wrapper) {
  await wrapper.get('[data-testid="secure-link-title-form"]').trigger('submit');
  await flushPromises();
}

describe('SecureLinkTitleEditor', () => {
  afterEach(() => { mounted.splice(0).forEach((wrapper) => wrapper.unmount()); });

  it('saves a changed title, trimmed, and returns to the heading', async () => {
    const save = jest.fn().mockResolvedValue({ success: true });
    const wrapper = mountEditor({ save });

    await startEditing(wrapper, '  Acceso al hosting  ');
    expect(document.activeElement).toBe(wrapper.get('[data-testid="secure-link-title-input"]').element);
    await submit(wrapper);

    expect(save).toHaveBeenCalledWith('Acceso al hosting');
    expect(wrapper.find('[data-testid="secure-link-title-form"]').exists()).toBe(false);
  });

  it('cancels with Escape without letting the key reach the detail modal', async () => {
    const save = jest.fn();
    const onWindowKey = jest.fn();
    window.addEventListener('keydown', onWindowKey);
    const wrapper = mountEditor({ save });

    await startEditing(wrapper, 'Borrador');
    await wrapper.get('[data-testid="secure-link-title-input"]').trigger('keydown', { key: 'Escape' });

    // Fails if Escape bubbles to window, where the detail modal closes on it.
    expect(onWindowKey).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="secure-link-title-form"]').exists()).toBe(false);
    expect(wrapper.get('h3').text()).toBe('Admin');
    expect(save).not.toHaveBeenCalled();
    window.removeEventListener('keydown', onWindowKey);
  });

  it.each([
    ['empty', '   ', 'secureLinks.panel.titleRequired'],
    ['too long', 'a'.repeat(161), 'secureLinks.validation.maxLength:160'],
  ])('rejects an %s title before saving', async (_label, value, message) => {
    const save = jest.fn();
    const wrapper = mountEditor({ save });

    await startEditing(wrapper, value);
    await submit(wrapper);

    expect(wrapper.get('[data-testid="secure-link-title-error"]').text()).toBe(message);
    expect(save).not.toHaveBeenCalled();
  });

  it('closes without a request when the title did not change', async () => {
    const save = jest.fn();
    const wrapper = mountEditor({ save });

    await startEditing(wrapper, ' Admin ');
    await submit(wrapper);

    expect(save).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="secure-link-title-form"]').exists()).toBe(false);
  });

  it('keeps the draft and shows the server error next to the field', async () => {
    const save = jest.fn().mockResolvedValue({
      success: false,
      error: { message: 'No se pudo guardar el enlace.', fieldErrors: { title: ['Máximo 160 caracteres.'] } },
    });
    const wrapper = mountEditor({ save });

    await startEditing(wrapper, 'Acceso nuevo');
    await submit(wrapper);

    expect(wrapper.get('[data-testid="secure-link-title-error"]').text()).toBe('Máximo 160 caracteres.');
    expect(wrapper.get('[data-testid="secure-link-title-input"]').element.value).toBe('Acceso nuevo');
    expect(wrapper.get('[data-testid="secure-link-title-input"]').attributes('aria-invalid')).toBe('true');
  });

  it('does not start editing while another detail action runs', async () => {
    const wrapper = mountEditor({ disabled: true });

    await startEditing(wrapper);

    expect(wrapper.find('[data-testid="secure-link-title-form"]').exists()).toBe(false);
  });
});
