import {
  availableProposalGroups,
  proposalSectionQuery,
  resolveProposalSection,
} from '~/utils/proposalNavigation';

const groupIds = (status) => availableProposalGroups(status).map((group) => group.id);
const sectionIds = (status, groupId) => availableProposalGroups(status)
  .find((group) => group.id === groupId)
  .sections
  .map((section) => section.id);

describe('proposal navigation catalog', () => {
  // Fails if a draft exposes tools that are not available before the proposal is sent.
  it('keeps draft navigation limited to its four available groups', () => {
    expect(groupIds('draft')).toEqual(['general', 'proposal', 'communication', 'tracking']);
  });

  // Fails if sent proposals lose the Documents group that users need to review shared files.
  it('adds Documents after a proposal is sent', () => {
    expect(groupIds('sent')).toEqual(['general', 'proposal', 'communication', 'documents', 'tracking']);
  });

  // Fails if accepted proposals hide a top-level group needed after approval.
  it('exposes six ordered groups for accepted proposals', () => {
    expect(groupIds('accepted')).toEqual([
      'general', 'proposal', 'communication', 'documents', 'project', 'tracking',
    ]);
  });

  // Fails if accepted proposals hide either Project tool after work has been approved.
  it('exposes both Project tools for accepted proposals', () => {
    expect(sectionIds('accepted', 'project')).toEqual(['schedule', 'development']);
  });

  // Fails if finished work loses its schedule or still offers the closed Development tool.
  it('keeps only the schedule in Project after a proposal is finished', () => {
    expect(groupIds('finished')).toEqual([
      'general', 'proposal', 'communication', 'project', 'tracking',
    ]);
    expect(sectionIds('finished', 'project')).toEqual(['schedule']);
  });
});

describe('proposal navigation links', () => {
  // Fails if a shared legacy link is rejected before its proposal status has loaded.
  it('keeps a legacy email destination while proposal status is loading', () => {
    expect(resolveProposalSection({ tab: 'emails' }, null)).toBe('emails');
  });

  // Fails if a canonical Project link stops opening Development for an accepted proposal.
  it('resolves the canonical Development destination for accepted proposals', () => {
    expect(resolveProposalSection({ tab: 'project', section: 'development' }, 'accepted')).toBe('development');
  });

  // Fails if old schedule links stop working after the proposal is finished.
  it('resolves a legacy schedule destination for finished proposals', () => {
    expect(resolveProposalSection({ tab: 'schedule' }, 'finished')).toBe('schedule');
  });

  // Fails if a status-gated or malformed section can select a panel with no available content.
  it('returns General for an unavailable canonical Project section', () => {
    expect(resolveProposalSection({ tab: 'project', section: 'development' }, 'finished')).toBe('general');
  });

  // Fails if an unknown grouped link can select an editor panel that does not exist.
  it('returns General for an unknown canonical destination', () => {
    expect(resolveProposalSection({ tab: 'unknown', section: 'missing' }, 'accepted')).toBe('general');
  });

  // Fails if Development links stop carrying their group and leaf identifiers.
  it('serializes Development as its Project destination', () => {
    expect(proposalSectionQuery('development')).toEqual({ tab: 'project', section: 'development' });
  });

  // Fails if General starts adding navigation parameters to shared editor links.
  it('serializes General without navigation parameters', () => {
    expect(proposalSectionQuery('general')).toEqual({});
  });
});
