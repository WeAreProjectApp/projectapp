"""Data migration coverage for conservative technical-resource ownership adoption."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def _before_0078_targets(graph):
    """Keep every independent app at its leaf while holding the two related apps before 0078."""
    cutoffs = {
        ('accounts', '0077_project_data_retention'),
        ('content', '0283_proposal_project_reassignment'),
    }
    descendants = {
        node for node in graph.nodes
        if any(cutoff in graph.forwards_plan(node) and node != cutoff for cutoff in cutoffs)
    }
    return sorted((set(graph.leaf_nodes()) - descendants) | cutoffs)


@pytest.mark.django_db(transaction=True)
def test_0078_adopts_only_a_unique_proposal_technical_key():
    """Fails if 0078 assigns an unknown or ambiguous legacy resource to an arbitrary proposal."""
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    old_targets = _before_0078_targets(executor.loader.graph)
    try:
        executor.migrate(old_targets)
        old = executor.loader.project_state(old_targets).apps
        User = old.get_model('auth', 'User')
        Project = old.get_model('accounts', 'Project')
        Phase = old.get_model('accounts', 'ProjectPhase')
        Deliverable = old.get_model('accounts', 'Deliverable')
        Proposal = old.get_model('content', 'BusinessProposal')
        Section = old.get_model('content', 'ProposalSection')
        client = User.objects.create(username='migration-0078-client')
        unique_project = Project.objects.create(name='Unique project', client=client)
        unique_proposal = Proposal.objects.create(title='Unique proposal', client_name='Client', slug='migration-0078-unique')
        unique_package = Deliverable.objects.create(project=unique_project, title='Unique package', uploaded_by=client)
        unique_proposal.deliverable_id = unique_package.pk
        unique_proposal.save(update_fields=['deliverable'])
        Phase.objects.create(project=unique_project, business_proposal=unique_proposal, order=1)
        Section.objects.create(
            proposal=unique_proposal, section_type='technical_document', title='Technical', order=1,
            content_json={'epics': [{'epicKey': 'proved-key', 'requirements': []}]},
        )
        proved = Deliverable.objects.create(project=unique_project, title='Proved resource', source_epic_key='proved-key', uploaded_by=client)
        unknown = Deliverable.objects.create(project=unique_project, title='Unknown resource', source_epic_key='unknown-key', uploaded_by=client)
        manifest_project = Project.objects.create(name='Manifest project', client=client)
        manifest_proposal = Proposal.objects.create(title='Manifest proposal', client_name='Client', slug='migration-0078-manifest')
        manifest_package = Deliverable.objects.create(project=manifest_project, title='Manifest package', uploaded_by=client)
        manifest_proposal.deliverable_id = manifest_package.pk
        manifest_proposal.platform_approval_manifest = {
            'technical_content': {'epics': [{'epicKey': 'manifest-key', 'requirements': []}]},
        }
        manifest_proposal.save(update_fields=['deliverable', 'platform_approval_manifest'])
        Phase.objects.create(project=manifest_project, business_proposal=manifest_proposal, order=1)
        manifested = Deliverable.objects.create(project=manifest_project, title='Manifest resource', source_epic_key='manifest-key', uploaded_by=client)
        ambiguous_project = Project.objects.create(name='Ambiguous project', client=client)
        first = Proposal.objects.create(title='First ambiguous proposal', client_name='Client', slug='migration-0078-first')
        second = Proposal.objects.create(title='Second ambiguous proposal', client_name='Client', slug='migration-0078-second')
        first_package = Deliverable.objects.create(project=ambiguous_project, title='First package', uploaded_by=client)
        second_package = Deliverable.objects.create(project=ambiguous_project, title='Second package', uploaded_by=client)
        first.deliverable_id = first_package.pk
        second.deliverable_id = second_package.pk
        first.save(update_fields=['deliverable'])
        second.save(update_fields=['deliverable'])
        Phase.objects.create(project=ambiguous_project, business_proposal=first, order=1)
        Phase.objects.create(project=ambiguous_project, business_proposal=second, order=2)
        ambiguous = Deliverable.objects.create(project=ambiguous_project, title='Ambiguous resource', source_epic_key='proved-key', uploaded_by=client)

        MigrationExecutor(connection).migrate(latest)
        current = MigrationExecutor(connection).loader.project_state(latest).apps
        CurrentDeliverable = current.get_model('accounts', 'Deliverable')

        assert CurrentDeliverable.objects.get(pk=proved.pk).source_proposal_id == unique_proposal.pk
        assert CurrentDeliverable.objects.get(pk=manifested.pk).source_proposal_id == manifest_proposal.pk
        assert CurrentDeliverable.objects.get(pk=unknown.pk).source_proposal_id is None
        assert CurrentDeliverable.objects.get(pk=ambiguous.pk).source_proposal_id is None
    finally:
        MigrationExecutor(connection).migrate(latest)
