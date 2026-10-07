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
  // Fails if drafts cannot reach their client and project relationship data.
  it('keeps Project data in draft navigation', () => {
    expect(groupIds('draft')).toEqual(['general', 'proposal', 'communication', 'documents', 'project', 'tracking']);
    expect(sectionIds('draft', 'project')).toEqual(['project-data']);
  });

  // Fails if sent proposals lose the relationship data needed before acceptance.
  it('keeps Project data in sent navigation', () => {
    expect(groupIds('sent')).toEqual(['general', 'proposal', 'communication', 'documents', 'project', 'tracking']);
    expect(sectionIds('sent', 'project')).toEqual(['project-data']);
  });

  // Fails if accepted proposals hide a top-level group needed after approval.
  it('exposes six ordered groups for accepted proposals', () => {
    expect(groupIds('accepted')).toEqual([
      'general', 'proposal', 'communication', 'documents', 'project', 'tracking',
    ]);
  });

  // Fails if accepted proposals hide their relationship data or either delivery tool.
  it('exposes project data and delivery tools for accepted proposals', () => {
    expect(sectionIds('accepted', 'project')).toEqual(['project-data', 'schedule', 'development']);
  });

  // Fails if finished work loses its relationship data or still offers the closed Development tool.
  it('keeps project data and schedule after a proposal is finished', () => {
    expect(groupIds('finished')).toEqual([
      'general', 'proposal', 'communication', 'documents', 'project', 'tracking',
    ]);
    expect(sectionIds('finished', 'project')).toEqual(['project-data', 'schedule']);
  });
});

describe('proposal navigation links', () => {
  test.each(['draft', 'expired', 'finished'])('resolves the Documents link for a %s proposal', (status) => {
    // Falla si un estado fuera de negociación abre General en vez de los documentos contractuales.
    expect(resolveProposalSection({ tab: 'documents' }, status)).toBe('documents');
  });

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

  // Fails if saved Resources links still point at the former Communication tab.
  it('resolves the old Communication Resources URL and serializes the new Proposal URL', () => {
    expect(resolveProposalSection({ tab: 'communication', section: 'resources' }, 'accepted')).toBe('resources');
    expect(proposalSectionQuery('resources')).toEqual({ tab: 'proposal', section: 'resources' });
  });

  // Fails if email configuration falls back into General after the tab move.
  it('resolves Correos within Communication', () => {
    expect(resolveProposalSection({ tab: 'communication', section: 'emails' }, 'draft')).toBe('emails');
    expect(proposalSectionQuery('emails')).toEqual({ tab: 'communication' });
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
