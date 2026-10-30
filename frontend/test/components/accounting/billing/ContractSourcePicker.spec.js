import { mount } from '@vue/test-utils';
import ContractSourcePicker from '../../../../components/accounting/billing/ContractSourcePicker.vue';

const sources = [
  { id: 1, source_type: 'document', title: 'Corrida diaria', is_contract_like: false, created_at: '2026-03-01T12:00:00Z', folder_path: '' },
  { id: 3, source_type: 'proposal_document', title: 'Contrato_base', is_contract_like: true, created_at: '2026-02-01T12:00:00Z', proposal_title: 'Propuesta inicial' },
  { id: 2, source_type: 'document', title: 'Contrato_base', is_contract_like: true, created_at: '2026-01-01T12:00:00Z', folder_path: 'Legal / Versiones' },
];

function mountPicker(props = {}) {
  return mount(ContractSourcePicker, {
    props: { sources, ...props },
    global: { stubs: {
      NuxtLink: { template: '<a><slot /></a>' },
      BaseFloatingListbox: { props: ['open', 'id'], template: '<div v-if="open" :id="id" role="listbox"><slot /></div>' },
    } },
  });
}

describe('ContractSourcePicker', () => {
  it('shows contractual sources first and distinguishes every version by date and location', async () => {
    const wrapper = mountPicker();
    await wrapper.get('input').trigger('focus');

    expect(wrapper.findAll('[role="option"]').map(row => row.attributes('data-testid'))).toEqual([
      'billing-contract-source-option-proposal_document:3', 'billing-contract-source-option-document:2', 'billing-contract-source-option-document:1',
    ]);
    expect(wrapper.text()).toContain('Legal / Versiones');
    expect(wrapper.text()).toContain('Propuesta: Propuesta inicial');
    expect(wrapper.text()).toContain('Sin carpeta');
    expect(wrapper.findAll('[role="option"]')[1].text()).toContain('1/01/2026');
  });

  it('filters and highlights safely without interpreting document markup', async () => {
    const wrapper = mountPicker({ sources: [{ ...sources[1], title: '<img src=x> Revisión_Contrato' }] });
    await wrapper.get('input').setValue('vision contrato');

    expect(wrapper.findAll('[role="option"]')).toHaveLength(1);
    expect(wrapper.get('mark').text()).toBe('visión_Contrato');
    expect(wrapper.find('img').exists()).toBe(false);
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('chooses with arrows and Enter, exposing the active and selected options', async () => {
    const wrapper = mountPicker();
    const input = wrapper.get('input');
    await input.trigger('keydown', { key: 'ArrowDown' });
    expect(input.attributes('aria-activedescendant')).toBe(wrapper.findAll('[role="option"]')[0].attributes('id'));
    await input.trigger('keydown', { key: 'ArrowDown' });
    await input.trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['document:2']);
    await wrapper.setProps({ modelValue: 'document:2' });
    expect(input.element.value).toBe('Contrato_base');
    await input.trigger('focus');
    expect(wrapper.get('[data-testid="billing-contract-source-option-document:2"]').attributes('aria-selected')).toBe('true');
  });

  it('keeps composite identities when source types share a numeric id', async () => {
    const wrapper = mountPicker({ sources: [sources[1], { ...sources[2], id: 3 }] });
    await wrapper.get('input').trigger('focus');
    await wrapper.get('[data-testid="billing-contract-source-option-document:3"]').trigger('click');
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['document:3']);
  });

  it('shows no matches without turning text into a selection and clears deliberately', async () => {
    const wrapper = mountPicker({ modelValue: 'document:2' });
    await wrapper.get('input').setValue('inexistente');
    expect(wrapper.get('[role="status"]').text()).toContain('Sin coincidencias');
    await wrapper.get('input').trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    await wrapper.get('[data-testid="billing-link-contract-source-clear"]').trigger('click');
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual(['']);
  });

  it.each(['Escape', 'Tab'])('closes on %s without committing the search', async key => {
    const wrapper = mountPicker({ modelValue: 'document:2' });
    await wrapper.get('input').setValue('corrida');
    await wrapper.get('input').trigger('keydown', { key });
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
    expect(wrapper.get('input').element.value).toBe('Contrato_base');
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('discards search and results when project sources are replaced', async () => {
    const wrapper = mountPicker();
    await wrapper.get('input').setValue('contrato');
    await wrapper.setProps({ sources: [{ ...sources[0], id: 18, title: 'Nuevo proyecto' }], modelValue: '' });
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
    expect(wrapper.get('input').element.value).toBe('');
    await wrapper.get('input').trigger('focus');
    expect(wrapper.findAll('[role="option"]')).toHaveLength(1);
    expect(wrapper.text()).toContain('Nuevo proyecto');
  });

  it.each(['Enter', 'Escape', 'ArrowDown'])('leaves %s to the IME until composition ends', async key => {
    const wrapper = mountPicker();
    const input = wrapper.get('input');
    await input.trigger('focus');
    await input.trigger('compositionstart');
    await input.setValue('Contrato');
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
    const event = new KeyboardEvent('keydown', { key, isComposing: true, cancelable: true });
    input.element.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    await input.trigger('compositionend');
    expect(wrapper.findAll('[role="option"]')).toHaveLength(2);
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('does not select when a legacy IME reports keyCode 229', async () => {
    const wrapper = mountPicker();
    await wrapper.get('input').setValue('Contrato');
    await wrapper.get('input').trigger('keydown', { key: 'Enter', keyCode: 229 });
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(wrapper.findAll('[role="option"]')).toHaveLength(2);
  });

  it('scrolls the active option into view when navigating beyond the first result', async () => {
    const wrapper = mountPicker();
    const scrollIntoView = jest.fn();
    await wrapper.get('input').trigger('focus');
    const option = wrapper.findAll('[role="option"]')[2];
    option.element.scrollIntoView = scrollIntoView;
    const lookup = jest.spyOn(document, 'getElementById').mockReturnValue(option.element);
    await wrapper.get('input').trigger('keydown', { key: 'ArrowUp' });
    expect(wrapper.get('input').attributes('aria-activedescendant')).toBe(option.attributes('id'));
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' });
    lookup.mockRestore();
  });
});
