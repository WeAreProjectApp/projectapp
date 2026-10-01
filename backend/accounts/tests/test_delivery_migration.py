"""The authorized legacy purge must not cascade into client/shared records."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.fixture(scope='module')
def migrated_snapshot(django_db_setup, django_db_blocker):
    """Build legacy rows, migrate them, and return their observable outcome."""
    with django_db_blocker.unblock():
        return _migrate_legacy_fixture()


def _legacy_targets(graph):
    """Return compatible migration leaves with accounts held at migration 0063."""
    cutoff = ('accounts', '0063_projectaccessnote_projectadminaccess')
    later_accounts = {
        node for node in graph.nodes
        if node[0] == 'accounts' and node != cutoff and cutoff in graph.forwards_plan(node)
    }
    incompatible = {
        node for node in graph.nodes
        if any(later_account in graph.forwards_plan(node) for later_account in later_accounts)
    }
    compatible = set(graph.nodes) - incompatible
    compatible_leaves = {
        node for node in compatible
        if not any(child.key in compatible for child in graph.node_map[node].children)
    }
    return sorted(compatible_leaves | {cutoff})


def _migrate_legacy_fixture():
    """Exercise the legacy migration boundary and always restore latest schema."""
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    try:
        old_target = _legacy_targets(executor.loader.graph)
        executor.migrate(old_target)
        old = executor.loader.project_state(old_target).apps
        User = old.get_model('auth', 'User')
        Project = old.get_model('accounts', 'Project')
        Phase = old.get_model('accounts', 'ProjectPhase')
        Proposal = old.get_model('content', 'BusinessProposal')
        ScopeItem = old.get_model('accounts', 'ProjectScopeItem')
        Requirement = old.get_model('accounts', 'Requirement')
        Comment = old.get_model('accounts', 'RequirementComment')
        History = old.get_model('accounts', 'RequirementHistory')
        Bug = old.get_model('accounts', 'BugReport')
        Change = old.get_model('accounts', 'ChangeRequest')
        Document = old.get_model('content', 'Document')
        Deliverable = old.get_model('accounts', 'Deliverable')
        DataModel = old.get_model('accounts', 'ProjectDataModelEntity')
        Income = old.get_model('content', 'IncomeRecord')
        Hosting = old.get_model('content', 'HostingRecord')

        user = User.objects.create(username='migration-client', email='migration@example.test')
        project = Project.objects.create(name='Migration project', client=user)
        proposal = Proposal.objects.create(title='Commercial proposal', client_name='Client', client_email=user.email)
        phase = Phase.objects.create(project=project, business_proposal=proposal, order=1,
                                     hosting_start_date='2026-09-30', hosting_activated_at='2026-09-30')
        scope = ScopeItem.objects.create(phase=phase, name='Old scope mirror')
        card = Requirement.objects.create(phase=phase, title='Old Kanban card', scope_item=scope)
        Comment.objects.create(requirement=card, user=user, content='Old card comment')
        History.objects.create(requirement=card, from_status='todo', to_status='done', changed_by=user)
        bug = Bug.objects.create(project=project, reported_by=user, title='Bug survives', source_requirement=card, phase=phase)
        change = Change.objects.create(project=project, created_by=user, title='Request survives',
                                       source_requirement=card, linked_requirement=card, phase=phase)
        document = Document.objects.create(project=project, client_user=user, title='Document survives', content_markdown='Content')
        deliverable = Deliverable.objects.create(project=project, title='Resource survives', uploaded_by=user)
        entity = DataModel.objects.create(project=project, name='Data model survives')
        income = Income.objects.create(project=project, concept='Income survives', kind='expected',
                                       total_amount='100000.00', period_date='2026-09-30')
        hosting = Hosting.objects.create(project=project, client_name='Client', monthly_value='50000.00', payment_modality='quarterly')

        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        current = executor.loader.project_state(latest).apps
        kept_bug = current.get_model('accounts', 'BugReport').objects.get(pk=bug.pk)
        kept_change = current.get_model('accounts', 'ChangeRequest').objects.get(pk=change.pk)

        return {
            'bug': {'title': kept_bug.title, 'source': kept_bug.source_requirement_id},
            'change': {'title': kept_change.title, 'source': kept_change.source_requirement_id,
                       'linked': kept_change.linked_requirement_id},
            'cards_count': current.get_model('accounts', 'Requirement').objects.count(),
            'phase_hosting_date': current.get_model('accounts', 'ProjectPhase').objects.get(pk=phase.pk).hosting_activated_at.isoformat(),
            'proposal_exists': current.get_model('content', 'BusinessProposal').objects.filter(pk=proposal.pk).exists(),
            'document_exists': current.get_model('content', 'Document').objects.filter(pk=document.pk).exists(),
            'resource_exists': current.get_model('accounts', 'Deliverable').objects.filter(pk=deliverable.pk).exists(),
            'data_model_exists': current.get_model('accounts', 'ProjectDataModelEntity').objects.filter(pk=entity.pk).exists(),
            'tables': connection.introspection.table_names(),
            'income_amount': str(current.get_model('content', 'IncomeRecord').objects.get(pk=income.pk).total_amount),
            'hosting_amount': str(current.get_model('content', 'HostingRecord').objects.get(pk=hosting.pk).monthly_value),
        }
    finally:
        MigrationExecutor(connection).migrate(latest)


def test_purge_preserves_report_content(migrated_snapshot):
    """The migration preserves bug and change request titles."""
    assert migrated_snapshot['bug']['title'] == 'Bug survives'
    assert migrated_snapshot['change']['title'] == 'Request survives'


def test_purge_clears_legacy_card_references(migrated_snapshot):
    """The migration removes card references and legacy card tables."""
    assert migrated_snapshot['bug']['source'] is None
    assert migrated_snapshot['change']['source'] is None
    assert migrated_snapshot['change']['linked'] is None
    assert migrated_snapshot['cards_count'] == 0
    assert 'accounts_requirementcomment' not in migrated_snapshot['tables']
    assert 'accounts_requirementhistory' not in migrated_snapshot['tables']
    assert 'accounts_projectscopeitem' not in migrated_snapshot['tables']


def test_purge_preserves_shared_project_records(migrated_snapshot):
    """The migration preserves project records outside the removed card graph."""
    assert migrated_snapshot['phase_hosting_date'] == '2026-09-30'
    assert migrated_snapshot['proposal_exists'] is True
    assert migrated_snapshot['document_exists'] is True
    assert migrated_snapshot['resource_exists'] is True
    assert migrated_snapshot['data_model_exists'] is True
    assert migrated_snapshot['income_amount'] == '100000.00'
    assert migrated_snapshot['hosting_amount'] == '50000.00'
