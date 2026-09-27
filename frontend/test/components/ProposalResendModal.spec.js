import { flushPromises, mount } from '@vue/test-utils';

import ProposalResendModal from '../../components/BusinessProposal/admin/ProposalResendModal.vue';

const mockProposalStore = {
  resendProposal: jest.fn(),
};

jest.mock('../../stores/proposals', () => ({
  useProposalStore: () => mockProposalStore,
}));

const proposal = {
  id: 42,
  title: 'Portal de clientes',
  client_email: 'cliente@example.com',
  email_intro: 'Mensaje anterior que explica el alcance.',
};

const BaseModalStub = {
  props: ['modelValue'],
  template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
};

const BaseTextareaStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
};

const BaseButtonStub = {
  props: ['disabled'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
};

function mountModal(props = {}) {
  return mount(ProposalResendModal, {
    props: { visible: true, proposal, ...props },
    global: {
      stubs: {
        BaseModal: BaseModalStub,
        BaseTextarea: BaseTextareaStub,
        BaseButton: BaseButtonStub,
        BaseActionButton: { template: '<button type="button"><slot /></button>' },
        BaseModalActions: { template: '<div><slot /></div>' },
      },
    },
  });
}

describe('ProposalResendModal', () => {
  beforeEach(() => {
    mockProposalStore.resendProposal.mockReset().mockResolvedValue({
      success: true,
      email_delivery: { ok: true },
    });
  });

  it('preloads the message retained by the proposal', () => {
    const wrapper = mountModal();

    expect(wrapper.get('textarea').element.value).toBe(proposal.email_intro);
    expect(wrapper.text()).toContain('Puedes ajustar el mensaje antes de enviarlo.');
  });

  it('requires a nonblank message before resending', async () => {
    const wrapper = mountModal();

    await wrapper.get('textarea').setValue('   ');

    expect(wrapper.get('[data-testid="proposal-resend-confirm"]').attributes('disabled')).toBe('');
    expect(mockProposalStore.resendProposal).not.toHaveBeenCalled();
  });

  it('saves the trimmed edit through the resend request', async () => {
    const wrapper = mountModal();
    await wrapper.get('textarea').setValue('  Mensaje nuevo para resolver el cuello de botella.  ');

    await wrapper.get('[data-testid="proposal-resend-confirm"]').trigger('click');
    await flushPromises();

    expect(mockProposalStore.resendProposal).toHaveBeenCalledWith(
      42,
      'Mensaje nuevo para resolver el cuello de botella.',
    );
    expect(wrapper.emitted('resent')).toHaveLength(1);
    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('keeps the editor open and preserves the text after a server failure', async () => {
    mockProposalStore.resendProposal.mockResolvedValueOnce({
      success: false,
      message: 'No se pudo re-enviar.',
      hint: 'Revisa el correo del cliente.',
    });
    const wrapper = mountModal();
    const edited = 'Mensaje que debe seguir editable.';
    await wrapper.get('textarea').setValue(edited);

    await wrapper.get('[data-testid="proposal-resend-confirm"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('textarea').element.value).toBe(edited);
    expect(wrapper.text()).toContain('No se pudo re-enviar.');
    expect(wrapper.text()).toContain('Revisa el correo del cliente.');
    expect(wrapper.emitted('close')).toBeUndefined();
  });
});
