import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick, ref } from 'vue';
import SecureLinkTypeField from '../../components/secureLinks/SecureLinkTypeField.vue';

global.useI18n = jest.fn(() => ({ t: (key) => key }));

const types = [
  { key: 'credentials', label_es: 'Credenciales', label_en: 'Credentials' },
  { key: 'custom', label_es: 'Personalizado', label_en: 'Custom' },
  { key: 'server_access', label_es: 'Acceso a servidor', label_en: 'Server access' },
];

const mounted = [];

function mountField(props = {}) {
  const wrapper = mount(SecureLinkTypeField, {
    attachTo: document.body,
    props: { modelValue: 'credentials', types, ...props },
  });
  mounted.push(wrapper);
  return wrapper;
}

function mountControlledField() {
  const Harness = defineComponent({
    components: { SecureLinkTypeField },
    setup() {
      return { selectedType: ref('credentials'), types };
    },
    template: '<SecureLinkTypeField v-model="selectedType" :types="types" />',
  });
  const wrapper = mount(Harness, { attachTo: document.body });
  mounted.push(wrapper);
  return wrapper;
}

function listbox(wrapper) {
  return document.getElementById(wrapper.get('[data-testid="secure-link-type"]').attributes('aria-controls'));
}

function option(wrapper, label) {
  return [...listbox(wrapper).children]
    .find((element) => element.textContent.trim() === label);
}

describe('SecureLinkTypeField', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount());
    document.body.innerHTML = '';
  });

  it('emits the custom catalog key selected from the accessible listbox', async () => {
    // Fails if the type control regresses to a native select or sends display text instead of the catalog key.
    const wrapper = mountField();

    await wrapper.get('[data-testid="secure-link-type"]').trigger('click');
    await flushPromises();
    expect(listbox(wrapper).getAttribute('role')).toBe('listbox');
    expect(listbox(wrapper).children).toHaveLength(3);
    await option(wrapper, 'Personalizado').click();

    expect(wrapper.emitted('update:modelValue')).toEqual([['custom']]);
  });

  it('focuses the custom-name editor after selecting Custom', async () => {
    // Fails if a Custom type can be selected but cannot receive its required name.
    const wrapper = mountControlledField();

    expect(wrapper.findAll('[data-testid="secure-link-field-custom_name"]')).toHaveLength(0);
    await wrapper.get('[data-testid="secure-link-type"]').trigger('click');
    await flushPromises();
    await option(wrapper, 'Personalizado').click();
    await nextTick();

    expect(document.activeElement).toBe(wrapper.get('[data-testid="secure-link-field-custom_name"]').element);
  });

  it('emits the next catalog key when the listbox is selected with the keyboard', async () => {
    // Fails if ArrowDown and Enter stop selecting an accessible listbox option.
    const wrapper = mountField({ modelValue: 'custom' });
    const trigger = wrapper.get('[data-testid="secure-link-type"]');

    await trigger.trigger('keydown', { key: 'ArrowDown' });
    await trigger.trigger('keydown', { key: 'ArrowDown' });
    await trigger.trigger('keydown', { key: 'Enter' });

    expect(wrapper.emitted('update:modelValue')).toEqual([['server_access']]);
  });
});
