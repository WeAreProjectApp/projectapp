"""Relation inventory: every relation into an anchor record carries a decision, and every decision is live."""
from content.services.data_integrity import catalog, relation_inventory


def test_every_relation_into_an_anchor_has_a_decision():
    """Fails if a relation into a project, client, proposal, document, folder, thread, income or hosting lands
    without saying which rule watches it or why none does: an unknown relation never passes."""
    assert relation_inventory.undecided() == []


def test_no_decision_outlives_its_relation():
    """Fails if a decision names a relation that no longer exists, which would hide a drifted inventory."""
    assert relation_inventory.stale() == []


def test_covered_relations_cite_rules_the_catalog_has():
    """Fails if a relation claims to be covered by a rule the catalog does not have (renamed or removed)."""
    assert relation_inventory.unknown_rules(rule.id for rule in catalog.rules()) == []


def test_an_undecided_relation_is_caught():
    """Fails if the inventory would let a new relation through: an unknown key must come back undecided."""
    found = {**relation_inventory.discover(), 'content.Imaginary.client': 'accounts.UserProfile'}

    assert relation_inventory.undecided(found) == ['content.Imaginary.client']
