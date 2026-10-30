import { DOMWrapper, flushPromises, mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { h, ref } from 'vue';
import BaseModal from '../../../../components/base/BaseModal.vue';
import ContractSourcePicker from '../../../../components/accounting/billing/ContractSourcePicker.vue';
import ProjectCatalogSelect from '../../../../components/accounting/ProjectCatalogSelect.vue';
import { usePanelProjectsStore } from '../../../../stores/panel_projects';

const sources = [{ source_type: 'document', id: 31, title: 'Contrato_base', is_contract_like: true }];
const imeFlags = [
  ['isComposing', { isComposing: true }],
  ['keyCode229', { keyCode: 229 }],
];
const page = new DOMWrapper(document.body);
let mountedWrapper;

async function mountDialog(component = ContractSourcePicker, props = { sources }, initialValue = '') {
  const pinia = createPinia();
  usePanelProjectsStore(pinia).records = [{ id: 7, name: 'Proyecto activo', status: 'active' }];
  const opened = ref(true);
  const selected = ref(initialValue);
  mountedWrapper = mount({
    setup: () => () => h(BaseModal, {
      modelValue: opened.value,
      'onUpdate:modelValue': value => { opened.value = value; },
    }, { default: () => [
      h('h2', 'Documento del cobro'),
      h(component, { ...props, modelValue: selected.value, 'onUpdate:modelValue': value => { selected.value = value; } }),
      h('output', { 'data-testid': 'chosen-source' }, String(selected.value ?? '')),
    ] }),
  }, { attachTo: document.body, global: {
    plugins: [pinia],
    stubs: { NuxtLink: { template: '<a><slot /></a>' } },
  } });
  await flushPromises();
  const input = mountedWrapper.findComponent(component).get('input[role="combobox"]');
  input.element.focus();
  await flushPromises();
  return input;
}

function escape(input, flags = {}) {
  const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true, ...flags });
  input.element.dispatchEvent(event);
  return event;
}

afterEach(() => {
  mountedWrapper?.unmount();
  mountedWrapper = undefined;
  document.body.innerHTML = '';
});

describe('contract source IME inside a real modal', () => {
  it('keeps the composition session usable after Escape', async () => {
    const input = await mountDialog();
    await input.trigger('compositionstart');
    await input.setValue('Contrato');

    const event = escape(input, { isComposing: true });
    await flushPromises();

    expect(event.defaultPrevented).toBe(false);
    expect(page.find('[role="dialog"]').exists()).toBe(true);
    expect(page.find('[role="listbox"]').exists()).toBe(false);
    expect(input.element.value).toBe('Contrato');
    await input.trigger('compositionend');
    expect(page.find('[role="option"]').exists()).toBe(true);
    input.element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    await flushPromises();
    expect(page.get('[data-testid="chosen-source"]').text()).toBe('document:31');
    expect(page.find('[role="dialog"]').exists()).toBe(true);
  });

  it.each(imeFlags)('preserves native %s Escape with contract results open', async (_label, flags) => {
    const input = await mountDialog();
    await input.setValue('Contrato');

    const event = escape(input, flags);
    await flushPromises();

    expect(event.defaultPrevented).toBe(false);
    expect(page.find('[role="dialog"]').exists()).toBe(true);
    expect(page.find('[role="listbox"]').exists()).toBe(true);
    expect(input.element.value).toBe('Contrato');
    expect(page.get('[data-testid="chosen-source"]').text()).toBe('');
  });

  it('dismisses contract results on normal Escape without closing the modal', async () => {
    const input = await mountDialog();

    const event = escape(input);
    await flushPromises();

    expect(event.defaultPrevented).toBe(true);
    expect(page.find('[role="listbox"]').exists()).toBe(false);
    expect(page.find('[role="dialog"]').exists()).toBe(true);
  });

  it.each(imeFlags)('preserves native %s Escape in the existing project catalog', async (_label, flags) => {
    const input = await mountDialog(ProjectCatalogSelect, {}, null);
    await input.setValue('Proyecto');

    const event = escape(input, flags);
    await flushPromises();

    expect(event.defaultPrevented).toBe(false);
    expect(page.find('[role="dialog"]').exists()).toBe(true);
    expect(page.find('[role="listbox"]').exists()).toBe(true);
    expect(input.element.value).toBe('Proyecto');
    expect(page.get('[data-testid="chosen-source"]').text()).toBe('');
  });

  it('dismisses the project modal only after normal Escape has dismissed its results', async () => {
    const input = await mountDialog(ProjectCatalogSelect, {}, null);

    escape(input);
    await flushPromises();

    expect(page.find('[role="listbox"]').exists()).toBe(false);
    expect(page.find('[role="dialog"]').exists()).toBe(true);
    escape(input);
    await flushPromises();
    expect(page.find('[role="dialog"]').exists()).toBe(false);
  });
});
