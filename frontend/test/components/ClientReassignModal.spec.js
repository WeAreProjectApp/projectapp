import { flushPromises, mount } from '@vue/test-utils';
import ClientReassignModal from '../../components/clients/ClientReassignModal.vue';

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: ['modelValue'],
  emits: ['update:modelValue', 'select'],
  template: '<div data-testid="client-picker" />',
};

function mountModal() {
  return mount(ClientReassignModal, {
    props: {
      modelValue: true,
      item: {
        type: 'proposal',
        title: 'Propuesta Atlas',
        sourceClientId: 7,
        sourceClientName: 'Cliente actual',
      },
    },
    global: {
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        ClientAutocomplete: ClientAutocompleteStub,
        BaseModal: {
          props: ['modelValue'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: { template: '<div><slot /></div>' },
        BaseAlert: { template: '<div role="alert"><slot /></div>' },
      },
    },
  });
}

async function selectClient(wrapper, client) {
  const picker = wrapper.findComponent(ClientAutocompleteStub);
  picker.vm.$emit('update:modelValue', client.id);
  picker.vm.$emit('select', client);
  await flushPromises();
}

describe('ClientReassignModal', () => {
  it('blocks reassignment to the current client', async () => {
    const wrapper = mountModal();

    await selectClient(wrapper, { id: 7, name: 'Cliente actual' });

    expect(wrapper.get('[role="alert"]').text()).toContain('distinto');
    expect(wrapper.get('[data-testid="client-reassign-confirm"]').attributes('disabled'))
      .toBeDefined();
  });

  it('confirms the selected destination client', async () => {
    const wrapper = mountModal();

    await selectClient(wrapper, { id: 9, name: 'Cliente destino' });
    await wrapper.get('[data-testid="client-reassign-confirm"]').trigger('click');

    expect(wrapper.emitted('confirm')).toEqual([[
      { targetClientId: 9, targetName: 'Cliente destino' },
    ]]);
  });
});
