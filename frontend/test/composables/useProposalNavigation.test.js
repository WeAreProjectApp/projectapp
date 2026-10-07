import { effectScope, nextTick, ref } from 'vue';
import { useProposalNavigation } from '~/composables/useProposalNavigation';

function createNavigation(query, initialStatus) {
  const status = ref(initialStatus);
  const scope = effectScope();
  let navigation;

  scope.run(() => {
    navigation = useProposalNavigation({ query, status });
  });

  return { ...navigation, status, stop: () => scope.stop() };
}

describe('useProposalNavigation', () => {
  let navigation;

  beforeEach(() => {
    window.history.replaceState(null, '', '/panel/proposals/32/edit');
  });

  afterEach(() => {
    navigation?.stop();
    window.history.replaceState(null, '', '/');
  });

  // Fails if returning to a group discards the last tool selected by the editor.
  it('restores the last visited Proposal tool after returning to that group', () => {
    navigation = createNavigation({}, 'accepted');

    navigation.activeGroup.value = 'proposal';
    navigation.activeTab.value = 'json';
    navigation.activeGroup.value = 'general';
    navigation.activeGroup.value = 'proposal';

    expect(navigation.activeTab.value).toBe('json');
    expect([...navigation.visitedTabs.value]).toEqual(['general', 'sections', 'json']);
  });

  // Fails if a finished proposal remains on its unavailable Development panel.
  it('repairs Development to project data when an accepted proposal finishes', async () => {
    navigation = createNavigation({ tab: 'project', section: 'development' }, 'accepted');

    navigation.status.value = 'finished';
    await nextTick();

    expect(navigation.activeTab.value).toBe('project-data');
    expect([...navigation.visitedTabs.value]).toEqual(['development', 'project-data']);
  });

  // Fails if an unloaded legacy Development link mounts its panel before Draft permissions are known.
  it('repairs an unloaded legacy Development link to General when the proposal is a draft', async () => {
    navigation = createNavigation({ tab: 'development' }, null);

    expect([...navigation.visitedTabs.value]).toEqual([]);
    navigation.status.value = 'draft';
    await nextTick();

    expect(navigation.activeTab.value).toBe('general');
    expect([...navigation.visitedTabs.value]).toEqual(['general']);
  });

  // Fails if an unloaded canonical Development link mounts before Finished permissions reject it.
  it('repairs an unloaded canonical Development link to General when the proposal is finished', async () => {
    navigation = createNavigation({ tab: 'project', section: 'development' }, null);

    expect([...navigation.visitedTabs.value]).toEqual([]);
    navigation.status.value = 'finished';
    await nextTick();

    expect(navigation.activeTab.value).toBe('general');
    expect([...navigation.visitedTabs.value]).toEqual(['general']);
  });

  // Fails if finishing a proposal redirects away from its available Documents panel.
  it('keeps Documents selected when the proposal finishes', async () => {
    navigation = createNavigation({ tab: 'documents' }, 'accepted');

    navigation.status.value = 'finished';
    await nextTick();

    expect(navigation.activeTab.value).toBe('documents');
    expect([...navigation.visitedTabs.value]).toEqual(['documents']);
  });

  // Fails if grouped email navigation drops unrelated shared-link details.
  it('writes the canonical email destination without removing another query parameter or hash', async () => {
    window.history.replaceState(null, '', '/panel/proposals/32/edit?filter=unread#activity');
    navigation = createNavigation({ filter: 'unread' }, 'accepted');

    navigation.activeGroup.value = 'communication';
    await nextTick();

    expect(window.location.search).toBe('?filter=unread&tab=communication');
    expect(window.location.hash).toBe('#activity');
  });

  // Fails if returning to General removes shared-link parameters other than navigation state.
  it('removes only navigation parameters when General is selected', async () => {
    window.history.replaceState(
      null,
      '',
      '/panel/proposals/32/edit?tab=communication&section=emails&filter=unread#activity',
    );
    navigation = createNavigation({ tab: 'communication', section: 'emails', filter: 'unread' }, 'accepted');

    navigation.activeTab.value = 'general';
    await nextTick();

    expect(window.location.search).toBe('?filter=unread');
    expect(window.location.hash).toBe('#activity');
  });

  // Fails if an incoming legacy link is rewritten before the proposal status makes it safe to canonicalize.
  it('does not rewrite a legacy destination while proposal status is still loading', async () => {
    window.history.replaceState(null, '', '/panel/proposals/32/edit?tab=emails&filter=unread#activity');
    navigation = createNavigation({ tab: 'emails', filter: 'unread' }, null);
    await nextTick();

    expect(navigation.activeTab.value).toBe('emails');
    expect(window.location.search).toBe('?tab=emails&filter=unread');
    expect(window.location.hash).toBe('#activity');
  });
});
