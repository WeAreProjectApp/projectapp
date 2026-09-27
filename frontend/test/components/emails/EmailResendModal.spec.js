import { flushPromises, mount } from '@vue/test-utils';
import EmailResendModal from '../../../components/emails/EmailResendModal.vue';

const mockStore = {
  isResending: false,
  resendEmail: jest.fn(),
};

jest.mock('../../../stores/emails', () => ({
  useEmailStore: () => mockStore,
}));

const entry = {
  id: 9,
  recipient: 'original@example.com',
  subject: 'Propuesta exacta',
  attachments: [{ id: 4, filename: 'propuesta.pdf' }],
};

const EmailRecipientFieldsStub = {
  name: 'EmailRecipientFields',
  props: ['toRecipients', 'ccRecipients'],
  emits: ['update:toRecipients', 'update:ccRecipients'],
  template: `
    <div>
      <input
        data-testid="email-resend-to"
        :value="toRecipients[0]?.email || ''"
        @input="$emit('update:toRecipients', $event.target.value ? [{ email: $event.target.value }] : [])"
      >
      <input
        data-testid="email-resend-cc"
        :value="ccRecipients[0]?.email || ''"
        @input="$emit('update:ccRecipients', $event.target.value ? [{ email: $event.target.value }] : [])"
      >
    </div>
  `,
};

function mountModal(props = {}) {
  return mount(EmailResendModal, {
    props: { open: true, entry, ...props },
    global: {
      stubs: {
        BaseModal: { template: '<div><slot /><slot name="footer" /></div>' },
        EmailRecipientFields: EmailRecipientFieldsStub,
        BaseButton: {
          template: '<button><slot /></button>',
        },
        BaseAlert: { template: '<div><slot /></div>' },
      },
    },
  });
}

describe('EmailResendModal', () => {
  beforeEach(() => {
    mockStore.isResending = false;
    mockStore.resendEmail.mockReset().mockResolvedValue({
      success: true,
      data: { email_log_id: 22 },
    });
  });

  it('shows the locked subject and retained attachment', () => {
    const wrapper = mountModal();

    expect(wrapper.text()).toContain('Propuesta exacta');
    expect(wrapper.text()).toContain('propuesta.pdf');
    expect(wrapper.text()).toContain('Sólo puedes cambiar los destinatarios');
  });

  it('submits the edited recipient without editable message fields', async () => {
    const wrapper = mountModal();
    await wrapper.get('[data-testid="email-resend-to"]').setValue('nuevo@example.com');

    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(mockStore.resendEmail).toHaveBeenCalledWith(
      9,
      [{ email: 'nuevo@example.com' }],
      [],
    );
    expect(wrapper.emitted('resent')[0]).toEqual([{ email_log_id: 22 }]);
  });

  it('keeps the modal open with a server failure message', async () => {
    mockStore.resendEmail.mockResolvedValue({
      success: false,
      message: 'SMTP no disponible.',
    });
    const wrapper = mountModal();

    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(wrapper.text()).toContain('SMTP no disponible.');
    expect(wrapper.emitted('resent')).toBeUndefined();
  });
});
