"""The policy registry must cover real reverse metadata without silent drift."""
from content.services.client_merge_policy import (
    AUTHORSHIP_RELATIONS,
    DIRECT_POLICIES,
    NEVER,
    RELATION_POLICIES,
    discover_relations,
    policy_drift,
)


def test_every_reverse_relation_has_exactly_one_policy():
    """Fails if any real User/UserProfile relation is missing from the reviewed registry."""
    assert set(discover_relations()) | set(DIRECT_POLICIES) == set(RELATION_POLICIES)
    assert policy_drift() == {'missing': [], 'stale': []}


def test_hidden_client_relations_are_discovered():
    """Fails if a '+' relationship disappears from the inventory used by merge planning."""
    assert {
        'content.LinktreeTemplate.client', 'accounts.ProjectIdea.recipient',
        'accounts.ProjectIdeaCollection.recipient', 'accounts.ProjectClientAccessPolicy.recipient',
        'accounts.ProjectClientAccessEvent.recipient',
    } <= set(discover_relations())


def test_authorship_classification_never_matches_a_commercial_owner():
    """Fails if actor classification accidentally consumes a client/recipient/owner pointer."""
    assert set(key.rsplit('.', 1)[1] for key in AUTHORSHIP_RELATIONS).isdisjoint({'client', 'recipient', 'owner'})
    assert set(RELATION_POLICIES[key] for key in AUTHORSHIP_RELATIONS) == {NEVER}
    assert len(AUTHORSHIP_RELATIONS) == len(set(AUTHORSHIP_RELATIONS))


def test_stale_registry_entries_are_reported(monkeypatch):
    """Fails if a removed model relation silently stays in the policy registry."""
    monkeypatch.setitem(RELATION_POLICIES, 'accounts.RemovedModel.client', NEVER)

    assert policy_drift()['stale'] == ['accounts.RemovedModel.client']
