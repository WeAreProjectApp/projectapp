import { getProposalNextAction } from '~/utils/proposalNextAction';

describe('getProposalNextAction', () => {
  it('returns null when proposal is nullish', () => {
    expect(getProposalNextAction(null)).toBeNull();
    expect(getProposalNextAction(undefined)).toBeNull();
  });

  it('suggests "send" for draft with client_email', () => {
    const result = getProposalNextAction({
      status: 'draft',
      client_email: 'a@b.com',
      available_transitions: ['sent'],
    });
    expect(result).toMatchObject({ key: 'send', label: 'Enviar al Cliente' });
  });

  it('returns null for draft without client_email', () => {
    const result = getProposalNextAction({
      status: 'draft',
      client_email: '',
      available_transitions: ['sent'],
    });
    expect(result).toBeNull();
  });

  it('suggests "negotiate" when sent has negotiating transition', () => {
    const result = getProposalNextAction({
      status: 'sent',
      client_email: 'a@b.com',
      available_transitions: ['negotiating', 'rejected'],
    });
    expect(result.key).toBe('negotiate');
  });

  it('suggests "negotiate" when viewed has negotiating transition', () => {
    const result = getProposalNextAction({
      status: 'viewed',
      available_transitions: ['negotiating', 'rejected'],
    });
    expect(result.key).toBe('negotiate');
  });

  it('suggests "launch" for negotiating without onboarding', () => {
    const result = getProposalNextAction({
      status: 'negotiating',
      available_transitions: ['accepted', 'rejected'],
      platform_onboarding_completed_at: null,
    });
    expect(result.key).toBe('launch');
  });

  it('suggests "approve" when negotiating is already onboarded and allows accepted', () => {
    const result = getProposalNextAction({
      status: 'negotiating',
      available_transitions: ['accepted', 'rejected'],
      platform_onboarding_completed_at: '2026-01-01T00:00:00Z',
    });
    expect(result.key).toBe('approve');
  });

  it('suggests "launch" for accepted without onboarding', () => {
    const result = getProposalNextAction({
      status: 'accepted',
      available_transitions: ['finished'],
      platform_onboarding_completed_at: null,
    });
    expect(result).toMatchObject({ key: 'launch', label: 'Completar revisión' });
  });

  it('suggests "finish" for accepted already onboarded', () => {
    const result = getProposalNextAction({
      status: 'accepted',
      available_transitions: ['finished'],
      platform_onboarding_completed_at: '2026-01-01T00:00:00Z',
    });
    expect(result.key).toBe('finish');
  });

  it('returns null for terminal statuses', () => {
    expect(getProposalNextAction({ status: 'finished', available_transitions: [] })).toBeNull();
    expect(getProposalNextAction({ status: 'rejected', available_transitions: [] })).toBeNull();
    expect(getProposalNextAction({ status: 'expired', available_transitions: [] })).toBeNull();
  });

  it('returns null when sent has no negotiating transition available', () => {
    const result = getProposalNextAction({
      status: 'sent',
      available_transitions: ['rejected'],
    });
    expect(result).toBeNull();
  });

  it('returns null when accepted has completed onboarding but cannot finish', () => {
    const result = getProposalNextAction({
      status: 'accepted',
      available_transitions: [],
      platform_onboarding_completed_at: '2026-01-01T00:00:00Z',
    });
    expect(result).toBeNull();
  });
});
