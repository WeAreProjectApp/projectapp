/**
 * Tests for useProposalStatusChange (shared confirm + PATCH + notify flow).
 *
 * Covers: same-status no-op, natural transitions without confirm, forced
 * transitions requiring confirm, cancellation, the negotiating interception,
 * email-delivery warnings with resend action, and error notifications.
 */

const mockUpdateProposalStatus = jest.fn();
jest.mock('../../stores/proposals', () => ({
  useProposalStore: () => ({ updateProposalStatus: mockUpdateProposalStatus }),
}));

const mockNotify = {
  success: jest.fn(),
  warning: jest.fn(),
  error: jest.fn(),
};
jest.mock('../../composables/usePanelNotify', () => ({
  usePanelNotify: () => mockNotify,
}));

const { useProposalStatusChange } = require('../../composables/useProposalStatusChange');

function buildProposal(overrides = {}) {
  return {
    id: 7,
    status: 'sent',
    available_transitions: ['negotiating', 'rejected'],
    ...overrides,
  };
}

describe('useProposalStatusChange', () => {
  let requestConfirm;

  beforeEach(() => {
    jest.clearAllMocks();
    requestConfirm = jest.fn().mockResolvedValue(true);
    mockUpdateProposalStatus.mockResolvedValue({ success: true, email_delivery: null });
  });

  it('returns null without PATCH when the status is unchanged', async () => {
    const { changeStatus } = useProposalStatusChange({ requestConfirm });
    const result = await changeStatus(buildProposal(), 'sent');

    expect(result).toBeNull();
    expect(mockUpdateProposalStatus).not.toHaveBeenCalled();
  });

  it('PATCHes a natural non-email transition without confirmation', async () => {
    const { changeStatus } = useProposalStatusChange({ requestConfirm });
    const result = await changeStatus(buildProposal(), 'rejected');

    expect(requestConfirm).not.toHaveBeenCalled();
    expect(mockUpdateProposalStatus).toHaveBeenCalledWith(7, 'rejected');
    expect(result.success).toBe(true);
    expect(mockNotify.success).toHaveBeenCalled();
  });

  it('asks for confirmation on forced transitions and aborts on cancel', async () => {
    requestConfirm.mockResolvedValue(false);
    const { changeStatus } = useProposalStatusChange({ requestConfirm });
    const result = await changeStatus(buildProposal(), 'finished');

    expect(requestConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Forzar cambio de estado', variant: 'warning' }),
    );
    expect(result).toBeNull();
    expect(mockUpdateProposalStatus).not.toHaveBeenCalled();
  });

  it('PATCHes a forced transition after confirmation', async () => {
    const { changeStatus } = useProposalStatusChange({ requestConfirm });
    const result = await changeStatus(buildProposal(), 'draft');

    expect(requestConfirm).toHaveBeenCalled();
    expect(mockUpdateProposalStatus).toHaveBeenCalledWith(7, 'draft');
    expect(result.success).toBe(true);
  });

  it('asks for confirmation on the natural draft→sent email transition', async () => {
    const { changeStatus } = useProposalStatusChange({ requestConfirm });
    await changeStatus(
      buildProposal({ status: 'draft', available_transitions: ['sent'] }), 'sent',
    );

    expect(requestConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Enviar propuesta' }),
    );
    expect(mockUpdateProposalStatus).toHaveBeenCalledWith(7, 'sent');
  });

  it('intercepts natural negotiating with onNegotiate instead of PATCHing', async () => {
    const onNegotiate = jest.fn();
    const { changeStatus } = useProposalStatusChange({ requestConfirm, onNegotiate });
    const proposal = buildProposal();
    const result = await changeStatus(proposal, 'negotiating');

    expect(onNegotiate).toHaveBeenCalledWith(proposal);
    expect(result).toBeNull();
    expect(mockUpdateProposalStatus).not.toHaveBeenCalled();
  });

  it('warns with a resend action when the client email failed', async () => {
    mockUpdateProposalStatus.mockResolvedValue({
      success: true,
      email_delivery: { ok: false, detail: 'SMTP caido' },
    });
    const resend = jest.fn();
    const { changeStatus } = useProposalStatusChange({ requestConfirm, resend });
    await changeStatus(
      buildProposal({ status: 'draft', available_transitions: ['sent'] }), 'sent',
    );

    expect(mockNotify.warning).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Estado actualizado',
        detail: 'SMTP caido',
        action: expect.objectContaining({ label: 'Reenviar' }),
      }),
    );
    mockNotify.warning.mock.calls[0][0].action.handler();
    expect(resend).toHaveBeenCalledWith(7);
  });

  it('notifies an error when the backend rejects the change', async () => {
    mockUpdateProposalStatus.mockResolvedValue({
      success: false, message: 'Ya está en ese estado', hint: 'Recarga',
    });
    const { changeStatus } = useProposalStatusChange({ requestConfirm });
    const result = await changeStatus(buildProposal(), 'rejected');

    expect(result.success).toBe(false);
    expect(mockNotify.error).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Ya está en ese estado', detail: 'Recarga' }),
    );
  });
  it.each([
    ['natural', { status: 'negotiating', available_transitions: ['accepted'] }],
    ['forced', { status: 'draft', available_transitions: ['sent'] }],
  ])('opens approval review before a %s acceptance', async (_kind, state) => {
    const onAccept = jest.fn();
    const proposal = buildProposal(state);
    const { changeStatus } = useProposalStatusChange({ requestConfirm, onAccept });
    await changeStatus(proposal, 'accepted');
    expect(onAccept).toHaveBeenCalledWith(proposal);
    expect(mockUpdateProposalStatus).not.toHaveBeenCalled();
  });

  it('keeps approval closed when forced acceptance is cancelled', async () => {
    requestConfirm.mockResolvedValue(false);
    const onAccept = jest.fn();
    const { changeStatus, updatingId } = useProposalStatusChange({ requestConfirm, onAccept });
    const result = await changeStatus(buildProposal({ status: 'draft' }), 'accepted');
    expect(requestConfirm).toHaveBeenCalledWith({
      title: 'Forzar cambio de estado',
      message: 'La propuesta pasará de «Borrador» a «Aceptada» fuera del flujo normal. No se enviarán correos ni se ejecutarán automatizaciones.',
      variant: 'warning',
      confirmText: 'Forzar cambio',
    });
    expect(result).toBeNull();
    expect(updatingId.value).toBeNull();
    expect(onAccept).not.toHaveBeenCalled();
    expect(mockUpdateProposalStatus).not.toHaveBeenCalled();
  });

});
